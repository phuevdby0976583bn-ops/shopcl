import logging
logger = logging.getLogger(__name__)
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import MyProfileCallback
from enums.bot_entity import BotEntity
from enums.entity_type import EntityType
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from handlers.common.common import enable_search
from handlers.user.constants import UserStates
from services.buy import BuyService
from services.notification import NotificationService
from services.payment import PaymentService
from services.referral import ReferralService
from services.user import UserService
from utils.custom_filters import IsUserExistFilter
from utils.utils import get_text

my_profile_router = Router()


@my_profile_router.message(F.text.in_(KB.get_localized_set(KB.MY_PROFILE)), IsUserExistFilter())
async def my_profile_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await my_profile(message=message, session=session, state=state, language=language)



async def _send_or_edit_profile(target, text: str, reply_markup=None):
    text_content = text or "..."
    if isinstance(target, Message):
        return await target.answer(text=text_content, reply_markup=reply_markup)
    else:
        callback = target
        if callback.message.caption:
            try:
                await callback.message.delete()
            except Exception:
                pass
            return await callback.message.answer(text=text_content, reply_markup=reply_markup)
        else:
            try:
                return await callback.message.edit_text(text=text_content, reply_markup=reply_markup)
            except Exception:
                return await callback.message.answer(text=text_content, reply_markup=reply_markup)

async def _edit_caption_or_text(message, text: str, reply_markup=None):
    if message.caption:
        try:
            return await message.edit_caption(caption=text, reply_markup=reply_markup)
        except Exception:
            pass
    try:
        return await message.edit_text(text=text, reply_markup=reply_markup)
    except Exception:
        return await message.answer(text=text, reply_markup=reply_markup)

async def my_profile(**kwargs):
    message: Message | CallbackQuery = kwargs.get("message") or kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    await state.clear()
    media, kb_builder = await UserService.get_my_profile_buttons(message.from_user.id, session, language)
    caption = getattr(media, "caption", "") or "👤 Ví & Thông tin cá nhân:"
    await _send_or_edit_profile(message, caption, kb_builder.as_markup())


async def top_up_balance(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    await state.set_state()
    msg_text, kb_builder = await UserService.get_top_up_buttons(callback_data, language)
    await _edit_caption_or_text(callback.message, msg_text, kb_builder.as_markup())


async def purchase_history(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    msg_text, kb_builder = await UserService.get_purchase_history_buttons(callback.from_user.id, callback_data,
                                                                          state, session, language)
    if callback.message.caption:
        await _edit_caption_or_text(callback.message, msg_text, kb_builder.as_markup())
    else:
        await callback.message.edit_text(text=msg_text, reply_markup=kb_builder.as_markup())


async def get_purchase(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    msg, kb_builder = await BuyService.get_purchase(callback_data, session, language)
    methods_map = {
        (True, True): ("edit_caption", "caption"),
        (True, False): ("edit_media", "media"),
        (False, True): ("edit_text", "text"),
        (False, False): ("edit_media", "media"),
    }

    has_caption = bool(callback.message.caption)
    is_string = isinstance(msg, str)
    method_name, param_name = methods_map[(has_caption, is_string)]

    method = getattr(callback.message, method_name)
    await method(**{param_name: msg}, reply_markup=kb_builder.as_markup())


async def get_purchased_item(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get("filter") is not None:
        media, kb_builder = await BuyService.get_purchased_item(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        media, kb_builder = await enable_search(callback_data, EntityType.SUBCATEGORY, callback_data.buy_id, state,
                                                UserStates.filter_purchase_history, language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await BuyService.get_purchased_item(callback_data, state, session, language)
    if callback.message.caption:
        await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())
    else:
        await callback.message.edit_text(text=media.caption, reply_markup=kb_builder.as_markup())


async def create_payment(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    try:
        await callback.answer()
    except Exception:
        pass

    try:
        response, kb_builder = await PaymentService.create(callback, callback_data, state, session, language)
        if isinstance(response, str):
            if callback.message.caption:
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer(text=response, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
            else:
                try:
                    await callback.message.edit_text(text=response, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
                except Exception:
                    await callback.message.answer(text=response, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
        else:
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer_photo(
                photo=response.media,
                caption=response.caption,
                reply_markup=kb_builder.as_markup(),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Error in create_payment: {e}", exc_info=True)
        try:
            await callback.answer(f"Lỗi: {e}", show_alert=True)
        except Exception:
            await callback.message.answer(f"⚠️ Có lỗi xảy ra khi tạo giao dịch: {e}")


async def edit_language(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    language: Language = kwargs.get("language")
    msg, kb_builder = await UserService.edit_language(callback.from_user.id, callback_data, session, language)
    await _edit_caption_or_text(callback.message, msg, kb_builder.as_markup())
    if callback_data.language is not None and callback_data.confirmation is True:
        try:
            from run import get_start_keyboard
            reply_markup = get_start_keyboard(callback_data.language, callback.from_user.id)
            await callback.message.answer(text=msg, reply_markup=reply_markup)
        except Exception:
            pass

async def referral_system(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    session: AsyncSession = kwargs.get("session")
    callback_data: MyProfileCallback = kwargs.get("callback_data")
    language: Language = kwargs.get("language")
    msg, kb_builder = await ReferralService.view_statistics(callback, callback_data, session, language)
    await _edit_caption_or_text(callback.message, msg, kb_builder.as_markup())


@my_profile_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_purchase_history))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    await state.update_data(filter=message.html_text)
    media, kb_builder = await BuyService.get_purchased_item(None, state, session, language)
    await NotificationService.answer_media(message, media, kb_builder.as_markup())


@my_profile_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.top_up_amount))
async def receive_top_up_amount(message: Message,
                                state: FSMContext,
                                session: AsyncSession,
                                language: Language):
    raw_text = (message.text or "").strip()
    if raw_text.startswith("/") or any(k in raw_text for k in ["Sản phẩm", "Đơn hàng", "Ví", "Hỗ trợ", "Products", "Orders", "Wallet"]):
        await state.clear()
        return

    try:
        media, kb_builder = await PaymentService.create(message,
                                                        None,
                                                        state,
                                                        session,
                                                        language)
        state_data = await state.get_data()
        if state_data.get("chat_id") and state_data.get("msg_id"):
            try:
                await message.bot.edit_message_media(chat_id=state_data.get("chat_id"),
                                                     message_id=state_data.get("msg_id"),
                                                     media=media,
                                                     reply_markup=kb_builder.as_markup())
                return
            except Exception:
                pass
        await NotificationService.answer_media(message, media, kb_builder.as_markup())
    except Exception as e:
        logger.error(f"Error in receive_top_up_amount: {e}", exc_info=True)
        await message.answer(f"❌ Có lỗi khi tạo hoá đơn nạp tiền: {e}")


@my_profile_router.callback_query(MyProfileCallback.filter(), IsUserExistFilter())
async def navigate(callback: CallbackQuery,
                   callback_data: MyProfileCallback,
                   session: AsyncSession,
                   state: FSMContext,
                   language: Language):
    current_level = callback_data.level

    levels = {
        0: my_profile,
        1: top_up_balance,
        2: create_payment,
        3: purchase_history,
        4: get_purchased_item,
        5: get_purchase,
        6: edit_language,
        7: referral_system
    }

    current_level_function = levels[current_level]

    kwargs = {
        "callback": callback,
        "session": session,
        "callback_data": callback_data,
        "state": state,
        "language": language
    }

    await current_level_function(**kwargs)
