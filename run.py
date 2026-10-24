import traceback
import logging
from aiogram import types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from config import SUPPORT_LINK
from bot import dp, main, redis, bot
from enums.bot_entity import BotEntity
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from handlers.common.review_management import review_management_router
from middleware.database import DBSessionMiddleware
from middleware.language import I18nMiddleware
from middleware.throttling_middleware import ThrottlingMiddleware
from models.user import UserDTO
from multibot import main as main_multibot
from handlers.user.cart import cart_router
from handlers.admin.admin import admin_router
from handlers.user.all_categories import all_categories_router, all_types
from handlers.user.my_profile import my_profile_router
from repositories.button_media import ButtonMediaRepository
from repositories.user import UserRepository
from services.media import MediaService
from services.notification import NotificationService
from services.review import ReviewService
from services.user import UserService
from db import session_commit
from utils.custom_filters import IsUserExistFilter, IsUserBannedFilter
from utils.utils import get_bot_photo_id, get_text

logging.basicConfig(level=logging.INFO)
main_router = Router()


def get_start_keyboard(language: Language, telegram_id: int):
    all_categories_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "all_categories"))
    my_profile_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "my_profile"))
    faq_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "faq"))
    help_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "help"))
    admin_menu_button = types.KeyboardButton(text=get_text(language, BotEntity.ADMIN, "menu"))
    reviews_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "reviews"))
    cart_button = types.KeyboardButton(text=get_text(language, BotEntity.USER, "cart"))

    keyboard = [
        [all_categories_button, my_profile_button],
        [faq_button, help_button],
        [reviews_button],
        [cart_button]
    ]
    if telegram_id in config.ADMIN_ID_LIST:
        keyboard.append([admin_menu_button])
    return types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2, keyboard=keyboard)


def get_language_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇻🇳 Tiếng Việt", callback_data="set_lang:vi")
    builder.button(text="🇬🇧 English", callback_data="set_lang:en")
    builder.button(text="🇮🇳 हिन्दी", callback_data="set_lang:hi")
    builder.button(text="🇨🇳 简体中文", callback_data="set_lang:zh")
    builder.adjust(2, 2)
    return builder.as_markup()


@main_router.message(CommandStart())
async def start(message: Message, session: AsyncSession, language: Language, command: CommandObject = None):
    telegram_id = message.from_user.id
    command_args = command.args if command else None
    await UserService.create_if_not_exist(UserDTO(
        telegram_username=message.from_user.username,
        telegram_id=telegram_id,
        language=language
    ), command_args, session)

    start_markup = get_start_keyboard(language, telegram_id)
    bot_info = await bot.get_me()
    bot_name = bot_info.username or "Shop"

    welcome_text = (
        f"👋 Chào mừng bạn đến với **@{bot_name}**! Phím tắt menu đã được gắn ở bên dưới:\n\n"
        f"🌐 **Chọn ngôn ngữ**\n"
        f"Vui lòng chọn ngôn ngữ trước khi vào shop."
    )

    lang_markup = get_language_inline_keyboard()

    # Gui tin kem ban phim menu va inline chon ngon ngu
    try:
        bot_photo_id = get_bot_photo_id()
        if bot_photo_id and bot_photo_id.strip() and bot_photo_id != "no_image_default":
            await message.answer_photo(
                photo=bot_photo_id,
                caption=welcome_text,
                reply_markup=lang_markup
            )
        else:
            await message.answer(text=welcome_text, reply_markup=lang_markup)
    except Exception as e:
        logging.warning(f"Failed to send start photo, fallback to text: {e}")
        await message.answer(text=welcome_text, reply_markup=lang_markup)

    # Dong thoi kich hoat ban phim reply keyboard menu
    menu_hint = {
        Language.VI: "👇 Bấm vào menu bên dưới để chọn chức năng:",
        Language.HI: "👇 फ़ंक्शन चुनने के लिए नीचे दिए गए मेनू पर क्लिक करें:",
        Language.ZH: "👇 点击下方菜单选择功能：",
        Language.EN: "👇 Use the menu below to navigate the shop:"
    }.get(language, "👇 Use the menu below to navigate the shop:")
    await message.answer(text=menu_hint, reply_markup=start_markup)


@main_router.callback_query(F.data.startswith("set_lang:"))
async def on_language_selected(callback: CallbackQuery, session: AsyncSession):
    lang_code = callback.data.split(":")[1]
    new_lang = Language.from_locale(lang_code)

    user_dto = await UserRepository.get_by_tgid(callback.from_user.id, session)
    if user_dto:
        user_dto.language = new_lang
        await UserRepository.update(user_dto, session)
        await session_commit(session)

    success_messages = {
        Language.VI: "🇻🇳 Bạn đã chọn **Tiếng Việt**. Menu bên dưới đã được cập nhật!",
        Language.EN: "🇬🇧 You selected **English**. The menu below has been updated!",
        Language.HI: "🇮🇳 आपने **हिन्दी** चुनी है। नीचे दिया गया मेनू अपडेट कर दिया गया है!",
        Language.ZH: "🇨🇳 您已选择 **简体中文**。下方菜单已更新！"
    }
    msg_text = success_messages.get(new_lang, success_messages[Language.EN])
    new_start_markup = get_start_keyboard(new_lang, callback.from_user.id)

    await callback.answer(f"Language: {new_lang.name}")
    try:
        await callback.message.edit_text(text=msg_text)
    except Exception:
        pass
    await callback.message.answer(text=get_text(new_lang, BotEntity.COMMON, "start_message"), reply_markup=new_start_markup)


@main_router.message(Command("products"))
async def cmd_products(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await all_types(callback=message, session=session, state=state, language=language)


@main_router.message(Command("help"))
async def cmd_help(message: Message, session: AsyncSession, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text=get_text(language, BotEntity.USER, "help_button"), url=SUPPORT_LINK)
    try:
        button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.HELP, session)
        media = MediaService.convert_to_media(button_media.media_id, caption=get_text(language, BotEntity.USER, "help_string"))
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    except Exception:
        await message.answer(get_text(language, BotEntity.USER, "help_string"), reply_markup=kb_builder.as_markup())


@main_router.message(Command("support"))
async def cmd_support(message: Message, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text="💬 Nhắn tin Admin", url=SUPPORT_LINK)
    support_info = (
        "🆘 **THÔNG TIN HỖ TRỢ / SUPPORT**\n\n"
        "• Kênh hỗ trợ trực tuyến 24/7.\n"
        "• Giải quyết các vấn đề nạp tiền, bảo hành tài khoản, tư vấn mua hàng.\n\n"
        "👉 Bấm nút bên dưới để gặp nhân viên hỗ trợ:"
    )
    await message.answer(support_info, reply_markup=kb_builder.as_markup())


@main_router.message(Command("warranty"))
async def cmd_warranty(message: Message, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text="🛡️ Gửi yêu cầu bảo hành", url=SUPPORT_LINK)
    warranty_info = (
        "🛡️ **CHÍNH SÁCH BẢO HÀNH & ĐỔI TRẢ**\n\n"
        "1. **Bảo hành 1 đổi 1** trong vòng 24 giờ kể từ lúc nhận hàng nếu tài khoản bị lỗi hệ thống.\n"
        "2. Vui lòng giữ nguyên thông tin ban đầu khi nhận đơn.\n"
        "3. Để được xử lý nhanh nhất, gửi kèm **Mã đơn hàng (Order ID)** cho Admin."
    )
    await message.answer(warranty_info, reply_markup=kb_builder.as_markup())


@main_router.message(Command("api"))
async def cmd_api(message: Message, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text="🔑 Đăng ký API Key", url=SUPPORT_LINK)
    api_info = (
        "🔑 **QUẢN LÝ KẾT NỐI API**\n\n"
        "• Hỗ trợ kết nối API cho các đối tác, tool tự động hoặc đại lý mua sỉ.\n"
        "• Tự động trừ tiền qua ví bot và trả dữ liệu tài khoản theo thời gian thực.\n\n"
        "👉 Vui lòng liên hệ Admin để cấp quyền API và nhận tài liệu tích hợp."
    )
    await message.answer(api_info, reply_markup=kb_builder.as_markup())


@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.FAQ)), IsUserExistFilter())
async def faq(message: Message, session: AsyncSession, language: Language):
    try:
        button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.FAQ, session)
        media = MediaService.convert_to_media(button_media.media_id, caption=get_text(language, BotEntity.USER, "faq_string"))
        await NotificationService.answer_media(message, media)
    except Exception:
        await message.answer(get_text(language, BotEntity.USER, "faq_string"))


@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.HELP)), IsUserExistFilter())
async def support(message: Message, session: AsyncSession, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(text=get_text(language, BotEntity.USER, "help_button"), url=SUPPORT_LINK)
    try:
        button_media = await ButtonMediaRepository.get_by_button(KeyboardButton.HELP, session)
        media = MediaService.convert_to_media(button_media.media_id, caption=get_text(language, BotEntity.USER, "help_string"))
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    except Exception:
        await message.answer(get_text(language, BotEntity.USER, "help_string"), reply_markup=kb_builder.as_markup())


@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.REVIEWS)), IsUserExistFilter())
async def support_reviews(message: Message, session: AsyncSession, language: Language):
    try:
        media, kb_builder = await ReviewService.get_reviews_paginated(None, session, language)
        await NotificationService.answer_media(message, media, reply_markup=kb_builder.as_markup())
    except Exception as e:
        logging.warning(f"Error reviews: {e}")
        await message.answer("Chưa có đánh giá nào.")


@main_router.error(F.update.message.as_("message"))
async def error_handler(event: ErrorEvent, message: Message):
    await message.answer("Oops, something went wrong!")
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {event.exception}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    await NotificationService.send_to_admins(admin_notification, None)


throttling_middleware = ThrottlingMiddleware(redis)
users_routers = Router()
users_routers.include_routers(
    all_categories_router,
    my_profile_router,
    cart_router,
    review_management_router
)
users_routers.message.middleware(throttling_middleware)
users_routers.callback_query.middleware(throttling_middleware)
main_router.include_router(admin_router)
main_router.include_routers(users_routers)
main_router.message.middleware(DBSessionMiddleware())
main_router.callback_query.middleware(DBSessionMiddleware())
main_router.message.middleware(I18nMiddleware())
main_router.callback_query.middleware(I18nMiddleware())


@main_router.message(IsUserBannedFilter())
async def banned_message(message: Message, language: Language):
    await message.answer(text=get_text(language, BotEntity.COMMON, "banned"))


@main_router.callback_query(IsUserBannedFilter())
async def banned_callback(callback: CallbackQuery, language: Language):
    banned_text = get_text(language, BotEntity.COMMON, "banned")
    if callback.message.text:
        await callback.message.edit_text(banned_text)
    else:
        await callback.message.delete()
        await callback.message.answer(banned_text)


@main_router.message(F.text)
async def fallback_any_text(message: Message, session: AsyncSession, language: Language):
    await start(message, session, language, None)


if __name__ == '__main__':
    if config.MULTIBOT:
        main_multibot(main_router)
    else:
        dp.include_router(main_router)
        main()
