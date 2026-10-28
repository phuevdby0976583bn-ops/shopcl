import utils.multipart_fix  # noqa: F401
import traceback
import logging
from aiogram import types, F, Router
from aiogram.filters import Command, CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import ErrorEvent, Message, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import MyProfileCallback

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
from models.user import UserDTO, User
from multibot import main as main_multibot
from handlers.user.cart import cart_router
from handlers.user.deposit import deposit_router
from handlers.admin.admin import admin_router, admin
from handlers.user.all_categories import all_categories_router, all_types
from handlers.user.my_profile import my_profile_router, my_profile
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

BUTTON_TOP_UP = {
    Language.VI: "💰 Nạp tiền",
    Language.EN: "💰 Deposit",
    Language.HI: "💰 जमा",
    Language.ZH: "💰 充值",
    Language.FR: "💰 Dépôt",
    Language.DE: "💰 Einzahlen",
    Language.IT: "💰 Deposito",
    Language.ES: "💰 Depositar",
}

BUTTON_PRODUCTS = {
    Language.VI: "🛒 Sản phẩm",
    Language.EN: "🛒 Products",
    Language.HI: "🛒 उत्पाद",
    Language.ZH: "🛒 商品",
    Language.FR: "🛒 Produits",
    Language.DE: "🛒 Produkte",
    Language.IT: "🛒 Prodotti",
    Language.ES: "🛒 Productos",
}

BUTTON_ORDERS = {
    Language.VI: "📦 Đơn hàng",
    Language.EN: "📦 Orders",
    Language.HI: "📦 ऑर्डर",
    Language.ZH: "📦 订单",
    Language.FR: "📦 Commandes",
    Language.DE: "📦 Bestellungen",
    Language.IT: "📦 Ordini",
    Language.ES: "📦 Pedidos",
}

BUTTON_WALLET = {
    Language.VI: "💳 Ví",
    Language.EN: "💳 Wallet",
    Language.HI: "💳 वॉलेट",
    Language.ZH: "💳 钱包",
    Language.FR: "💳 Portefeuille",
    Language.DE: "💳 Geldbörse",
    Language.IT: "💳 Portafoglio",
    Language.ES: "💳 Billetera",
}

BUTTON_SUPPORT = {
    Language.VI: "💬 Hỗ trợ",
    Language.EN: "💬 Support",
    Language.HI: "💬 सहायता",
    Language.ZH: "💬 客服支持",
    Language.FR: "💬 Support",
    Language.DE: "💬 Support",
    Language.IT: "💬 Supporto",
    Language.ES: "💬 Soporte",
}

BUTTON_WARRANTY = {
    Language.VI: "🛡️ Bảo hành",
    Language.EN: "🛡️ Warranty",
    Language.HI: "🛡️ वारंटी",
    Language.ZH: "🛡️ 售后",
    Language.FR: "🛡️ Garantie",
    Language.DE: "🛡️ Garantie",
    Language.IT: "🛡️ Garanzia",
    Language.ES: "🛡️ Garantía",
}

BUTTON_ADMIN = {
    Language.VI: "⚙️ Quản trị viên",
    Language.EN: "⚙️ Admin Menu",
    Language.HI: "⚙️ व्यवस्थापक",
    Language.ZH: "⚙️ 管理员",
    Language.FR: "⚙️ Menu Admin",
    Language.DE: "⚙️ Admin-Menü",
    Language.IT: "⚙️ Menu Admin",
    Language.ES: "⚙️ Menú Admin",
}

BUTTON_LANGUAGE = {
    Language.VI: "🌐 Ngôn ngữ",
    Language.EN: "🌐 Language",
    Language.HI: "🌐 भाषा",
    Language.ZH: "🌐 语言",
    Language.FR: "🌐 Langue",
    Language.DE: "🌐 Sprache",
    Language.IT: "🌐 Lingua",
    Language.ES: "🌐 Idioma",
}


def get_start_keyboard(language: Language, telegram_id: int):
    prod_btn = types.KeyboardButton(text=BUTTON_PRODUCTS.get(language, "🛒 Products"))
    orders_btn = types.KeyboardButton(text=BUTTON_ORDERS.get(language, "📦 Orders"))
    wallet_btn = types.KeyboardButton(text=BUTTON_WALLET.get(language, "💳 Wallet"))
    support_btn = types.KeyboardButton(text=BUTTON_SUPPORT.get(language, "💬 Support"))

    lang_btn = types.KeyboardButton(text=BUTTON_LANGUAGE.get(language, "🌐 Language"))

    keyboard = [
        [prod_btn, orders_btn],
        [wallet_btn, support_btn],
        [lang_btn]
    ]
    if telegram_id in config.ADMIN_ID_LIST:
        admin_btn = types.KeyboardButton(text=BUTTON_ADMIN.get(language, "⚙️ Admin Menu"))
        keyboard.append([admin_btn])

    placeholders = {
        Language.VI: "⚡ Chọn menu bên dưới để mua hàng hoặc nạp tiền...",
        Language.EN: "⚡ Choose an option below to buy or deposit...",
        Language.HI: "⚡ नीचे दिए गए विकल्पों में से चुनें...",
        Language.ZH: "⚡ 请在下方选择菜单进行购买或充值...",
        Language.FR: "⚡ Choisissez une option ci-dessous...",
        Language.DE: "⚡ Wählen Sie eine Option unten...",
        Language.IT: "⚡ Seleziona un'opzione in basso...",
        Language.ES: "⚡ Selecciona una opción abajo...",
    }
    placeholder = placeholders.get(language, placeholders[Language.EN])

    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder=placeholder
    )


def get_language_inline_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🇻🇳 Tiếng Việt", callback_data="set_lang:vi")
    builder.button(text="🇬🇧 English", callback_data="set_lang:en")
    builder.button(text="🇮🇳 हिन्दी", callback_data="set_lang:hi")
    builder.button(text="🇨🇳 简体中文", callback_data="set_lang:zh")
    builder.button(text="🇫🇷 Français", callback_data="set_lang:fr")
    builder.button(text="🇩🇪 Deutsch", callback_data="set_lang:de")
    builder.button(text="🇮🇹 Italiano", callback_data="set_lang:it")
    builder.button(text="🇪🇸 Español", callback_data="set_lang:es")
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


@main_router.message(CommandStart())
@main_router.message(Command("menu"))
@main_router.message(Command("shop"))
@main_router.message(Command("home"))
@main_router.message(Command("main"))
async def start(message: Message, session: AsyncSession, language: Language, command: CommandObject = None):
    telegram_id = message.from_user.id
    command_args = command.args if command else None
    await UserService.create_if_not_exist(UserDTO(
        telegram_username=message.from_user.username,
        telegram_id=telegram_id,
        language=language
    ), command_args, session)
    from utils.custom_filters import cache_user_exists
    from middleware.language import set_cached_user_language
    cache_user_exists(telegram_id)
    set_cached_user_language(telegram_id, language)

    start_markup = get_start_keyboard(language, telegram_id)
    bot_info = await bot.get_me()
    bot_name = bot_info.username or "Shop"

    welcome_text = {
        Language.VI: (
            f"👋 Chào mừng bạn đến với **@{bot_name}** - Shop Clone Facebook tự động 24/7!\n\n"
            f"⚡ **Cam kết: Tự động Check Live UID Facebook qua Graph API ngay khi bàn giao!**\n"
            f"💳 **Nạp tiền tự động: Binance Pay (0% phí) & Crypto Blockchain.**\n\n"
            f"👇 Vui lòng bấm vào menu bên dưới để bắt đầu:"
        ),
        Language.EN: (
            f"👋 Welcome to **@{bot_name}** - Automated Facebook Clone Shop 24/7!\n\n"
            f"⚡ **Guarantee: Auto Live UID check via Facebook Graph API upon delivery!**\n"
            f"💳 **Instant deposit: Binance Pay (0% Fee) & Crypto Blockchain.**\n\n"
            f"👇 Use the menu buttons below to get started:"
        ),
        Language.HI: (
            f"👋 **@{bot_name}** में आपका स्वागत है - 24/7 स्वचालित फेसबुक क्लोन शॉप!\n\n"
            f"👇 शुरू करने के लिए नीचे दिए गए मेनू का उपयोग करें:"
        ),
        Language.ZH: (
            f"👋 欢迎来到 **@{bot_name}** - 24/7 自动发货 Facebook Clone 商城！\n\n"
            f"👇 请使用下方菜单按钮开始选购："
        ),
        Language.FR: (
            f"👋 Bienvenue sur **@{bot_name}** - Boutique Clone Facebook automatique 24/7 !\n\n"
            f"⚡ **Vérification automatique en direct de l'UID Facebook via Graph API à la livraison !**\n"
            f"💳 **Recharge instantanée : Binance Pay (0% frais) & Crypto Blockchain.**\n\n"
            f"👇 Utilisez les boutons ci-dessous pour commencer :"
        ),
        Language.DE: (
            f"👋 Willkommen bei **@{bot_name}** - Automatisierter Facebook Clone Shop 24/7!\n\n"
            f"⚡ **Live-Überprüfung der Facebook-UID über Graph API bei Auslieferung!**\n"
            f"💳 **Sofortige Aufladung: Binance Pay (0% Gebühr) & Krypto-Blockchain.**\n\n"
            f"👇 Nutzen Sie die Menütasten unten, um zu beginnen:"
        ),
        Language.IT: (
            f"👋 Benvenuto su **@{bot_name}** - Negozio Facebook Clone automatico 24/7!\n\n"
            f"⚡ **Verifica automatica Live UID Facebook tramite Graph API alla consegna!**\n"
            f"💳 **Ricarica immediata: Binance Pay (0% commissioni) & Crypto Blockchain.**\n\n"
            f"👇 Usa i pulsanti del menu in basso per iniziare:"
        ),
        Language.ES: (
            f"👋 ¡Bienvenido a **@{bot_name}** - Tienda automática de Clones de Facebook 24/7!\n\n"
            f"⚡ **¡Verificación Live UID automática de Facebook mediante Graph API al entregar!**\n"
            f"💳 **Recarga inmediata: Binance Pay (0% comisión) y Criptomonedas.**\n\n"
            f"👇 Usa los botones del menú de abajo para comenzar:"
        )
    }.get(language, f"👋 Welcome to **@{bot_name}**!")

    try:
        await message.answer(text=welcome_text, reply_markup=start_markup)
    except Exception as e:
        logging.warning(f"Failed to send start text: {e}")


@main_router.callback_query(F.data.startswith("set_lang:"))
async def on_language_selected(callback: CallbackQuery, session: AsyncSession):
    from utils.localizator import Localizator
    from middleware.language import set_cached_user_language
    from models.user import UserDTO
    lang_code = callback.data.split(":")[1]
    new_lang = Language.from_locale(lang_code)

    set_cached_user_language(callback.from_user.id, new_lang)

    user_dto = await UserRepository.get_by_tgid(callback.from_user.id, session)
    if user_dto:
        user_dto.language = new_lang
        await UserRepository.update(user_dto, session)
    else:
        new_user = UserDTO(
            telegram_id=callback.from_user.id,
            telegram_username=callback.from_user.username,
            language=new_lang,
            can_receive_messages=True
        )
        await UserRepository.create(new_user, session)
    await session_commit(session)
    Localizator.clear_cache()

    success_messages = {
        Language.VI: "🇻🇳 Bạn đã chọn **Tiếng Việt**. Menu bên dưới đã được cập nhật!",
        Language.EN: "🇬🇧 You selected **English**. The menu below has been updated!",
        Language.HI: "🇮🇳 आपने **हिन्दी** चुनी है। नीचे दिया गया मेनू अपडेट कर दिया गया है!",
        Language.ZH: "🇨🇳 您已选择 **简体中文**。下方菜单已更新！",
        Language.FR: "🇫🇷 Vous avez sélectionné **Français**. Le menu ci-dessous a été mis à jour !",
        Language.DE: "🇩🇪 Sie haben **Deutsch** ausgewählt. Das Menü unten wurde aktualisiert!",
        Language.IT: "🇮🇹 Hai selezionato **Italiano**. Il menu sottostante è stato aggiornato!",
        Language.ES: "🇪🇸 Has seleccionado **Español**. ¡El menú inferior ha sido actualizado!"
    }
    msg_text = success_messages.get(new_lang, success_messages[Language.EN])
    new_start_markup = get_start_keyboard(new_lang, callback.from_user.id)

    await callback.answer(f"Language: {new_lang.get_display_name()}")
    try:
        await callback.message.edit_text(text=msg_text)
    except Exception:
        pass
    await callback.message.answer(text=msg_text, reply_markup=new_start_markup)


@main_router.message(F.text.in_(set(BUTTON_PRODUCTS.values())))
@main_router.message(Command("products"))
async def handle_products(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await state.clear()
    try:
        await all_types(callback=message, session=session, state=state, language=language)
    except Exception as e:
        logging.error(f"Error in handle_products: {e}", exc_info=True)
        from handlers.user.all_categories import execute_global_search
        await execute_global_search(message, "", session, language)


@main_router.message(F.text.in_(set(BUTTON_ORDERS.values())))
@main_router.message(Command("orders"))
async def handle_orders(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    caption, kb_builder = await UserService.get_purchase_history_buttons(
        message.from_user.id, None, state, session, language
    )
    await message.answer(caption, reply_markup=kb_builder.as_markup())


@main_router.message(F.text.in_(set(BUTTON_WALLET.values())))
@main_router.message(Command("wallet"))
async def handle_wallet(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await state.clear()
    try:
        stmt_u = select(User).where(User.telegram_id == message.from_user.id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        balance = 0.0
        top_up = 0.0
        consume = 0.0
        if user:
            top_up = float(user.top_up_amount or 0.0)
            consume = float(user.consume_records or 0.0)
            balance = round(max(0.0, top_up - consume), 2)

        user_name = f"@{message.from_user.username}" if message.from_user.username else (message.from_user.full_name or "Khách")

        wallet_texts = {
            Language.VI: {
                "title": (
                    "💳 <b>VÍ & TÀI KHOẢN CỦA BẠN</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Tài khoản:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Số dư khả dụng:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Đã nạp:</b> {top_up:.2f}$ | 📤 <b>Đã tiêu:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Khuyên dùng <b>Binance Pay</b>: Miễn phí 100%, nạp tự động nhận ngay sau 1-5 giây.</i>\n"
                    "👇 <b>Bấm nút bên dưới để nạp tiền tự động:</b>"
                ),
                "btn_bank": "🏦 Chuyển khoản Ngân hàng (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Phí - Nhận 1s)",
                "btn_onchain": "🌐 Nạp On-chain (BSC, TRX, TON...)",
                "btn_history": "📜 Lịch sử mua hàng"
            },
            Language.EN: {
                "title": (
                    "💳 <b>YOUR WALLET & ACCOUNT</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Account:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Available Balance:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Deposited:</b> {top_up:.2f}$ | 📤 <b>Spent:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Recommended: <b>Binance Pay</b> (0% fee, instant credit in 1-5s).</i>\n"
                    "👇 <b>Tap a button below to deposit:</b>"
                ),
                "btn_bank": "🏦 Vietnam Bank Transfer (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Fee - Instant 1s)",
                "btn_onchain": "🌐 Other Wallets / Exchanges (On-chain)",
                "btn_history": "📜 Purchase History"
            },
            Language.HI: {
                "title": (
                    "💳 <b>आपका वॉलेट और खाता</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>खाता:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>उपलब्ध शेष राशि:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>जमा:</b> {top_up:.2f}$ | 📤 <b>खर्च:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>सुझाव: <b>Binance Pay</b> (0% शुल्क, 1-5 सेकंड)।</i>\n"
                    "👇 <b>जमा करने के लिए नीचे दिए गए बटन पर टैप करें:</b>"
                ),
                "btn_bank": "🏦 वियतनाम बैंक (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% शुल्क - 1s)",
                "btn_onchain": "🌐 अन्य वॉलेट (On-chain)",
                "btn_history": "📜 खरीद इतिहास"
            },
            Language.ZH: {
                "title": (
                    "💳 <b>您的钱包与账户</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>账户：</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>可用余额：</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>总充值：</b> {top_up:.2f}$ | 📤 <b>已消费：</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>推荐使用 <b>Binance Pay</b>：0 手续费，1-5 秒自动秒到账。</i>\n"
                    "👇 <b>点击下方按钮进行自动充值：</b>"
                ),
                "btn_bank": "🏦 越南银行转账 (VietQR / BIDV)",
                "btn_binance": "🟡 币安支付 Binance Pay (0费率 - 秒到)",
                "btn_onchain": "🌐 链上充值 (BSC, TRX, TON...)",
                "btn_history": "📜 购买历史"
            },
            Language.FR: {
                "title": (
                    "💳 <b>VOTRE PORTEFEUILLE & COMPTE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Compte :</b> {user_name} (ID : <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Solde disponible :</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Déposé :</b> {top_up:.2f}$ | 📤 <b>Dépensé :</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Recommandé : <b>Binance Pay</b> (0% frais, instantané 1-5s).</i>\n"
                    "👇 <b>Appuyez ci-dessous pour recharger :</b>"
                ),
                "btn_bank": "🏦 Virement Vietnam (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Frais - Instant 1s)",
                "btn_onchain": "🌐 Autres portefeuilles (On-chain)",
                "btn_history": "📜 Historique d'achats"
            },
            Language.DE: {
                "title": (
                    "💳 <b>IHRE GELDBÖRSE & KONTO</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Konto:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Verfügbares Guthaben:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Eingezahlt:</b> {top_up:.2f}$ | 📤 <b>Ausgegeben:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Empfohlen: <b>Binance Pay</b> (0% Gebühr, sofort 1-5s).</i>\n"
                    "👇 <b>Klicken Sie unten zum Aufladen:</b>"
                ),
                "btn_bank": "🏦 Banküberweisung Vietnam (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Gebühr - Sofort 1s)",
                "btn_onchain": "🌐 Andere Wallets (On-chain)",
                "btn_history": "📜 Bestellhistorie"
            },
            Language.IT: {
                "title": (
                    "💳 <b>IL TUO PORTAFOGLIO & ACCOUNT</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Account:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Saldo disponibile:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Depositato:</b> {top_up:.2f}$ | 📤 <b>Speso:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Consigliato: <b>Binance Pay</b> (0% commissioni, 1-5s).</i>\n"
                    "👇 <b>Tocca un pulsante sotto per ricaricare:</b>"
                ),
                "btn_bank": "🏦 Bonifico Vietnam (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Commissioni - 1s)",
                "btn_onchain": "🌐 Altri portafogli (On-chain)",
                "btn_history": "📜 Storico acquisti"
            },
            Language.ES: {
                "title": (
                    "💳 <b>TU BILLETERA Y CUENTA</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 <b>Cuenta:</b> {user_name} (ID: <code>{message.from_user.id}</code>)\n"
                    f"💰 <b>Saldo disponible:</b> <b>{balance}$</b> (USDT)\n"
                    f"📥 <b>Depositado:</b> {top_up:.2f}$ | 📤 <b>Gastado:</b> {consume:.2f}$\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "⚡ <i>Recomendado: <b>Binance Pay</b> (0% comisión, 1-5s).</i>\n"
                    "👇 <b>Toca un botón abajo para recargar:</b>"
                ),
                "btn_bank": "🏦 Transferencia Vietnam (VietQR / BIDV)",
                "btn_binance": "🟡 Binance Pay (0% Comisión - Instant 1s)",
                "btn_onchain": "🌐 Otras billeteras (On-chain)",
                "btn_history": "📜 Historial de compras"
            }
        }
        cfg = wallet_texts.get(language, wallet_texts[Language.EN])
        text = cfg["title"]
        btn_bank = cfg["btn_bank"]
        btn_binance = cfg["btn_binance"]
        btn_onchain = cfg["btn_onchain"]
        btn_history = cfg["btn_history"]
        kb = InlineKeyboardBuilder()
        kb.button(text=btn_bank, callback_data="dep_method:bank")
        kb.button(text=btn_binance, callback_data="dep_method:binance")
        kb.button(text=btn_onchain, callback_data="dep_method:onchain")
        kb.button(text=btn_history, callback_data=MyProfileCallback.create(level=3))
        kb.adjust(1)
        await message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error in handle_wallet: {e}", exc_info=True)
        from services.deposit_flow import DepositFlowService
        text_method, kb_method = DepositFlowService.get_method_selection_keyboard(language)
        await message.answer(
            "💳 <b>VÍ & TÀI KHOẢN</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "Vui lòng chọn phương thức nạp tiền bên dưới:",
            reply_markup=kb_method.as_markup(),
            parse_mode="HTML"
        )


@main_router.message(F.text.in_(set(BUTTON_LANGUAGE.values())))
@main_router.message(Command("language"))
@main_router.message(Command("lang"))
async def handle_change_language(message: Message, session: AsyncSession, language: Language):
    lang_markup = get_language_inline_keyboard()
    text = {
        Language.VI: "🌐 **Chọn ngôn ngữ của bạn:**\nVui lòng chọn một trong các ngôn ngữ dưới đây để đổi giao diện bot:",
        Language.EN: "🌐 **Select your language:**\nPlease choose one of the languages below to switch bot interface:",
        Language.HI: "🌐 **अपनी भाषा चुनें:**\nकृपया बॉट इंटरफ़ेस बदलने के लिए नीचे दी गई भाषाओं में से एक चुनें:",
        Language.ZH: "🌐 **选择您的语言：**\n请在下方选择一种语言以切换机器人界面：",
        Language.FR: "🌐 **Choisissez votre langue :**\nVeuillez choisir l'une des langues ci-dessous pour changer l'interface du bot :",
        Language.DE: "🌐 **Wählen Sie Ihre Sprache:**\nBitte wählen Sie eine der folgenden Sprachen, um die Bot-Oberfläche zu ändern:",
        Language.IT: "🌐 **Seleziona la tua lingua:**\nScegli una delle seguenti lingue per cambiare l'interfaccia del bot:",
        Language.ES: "🌐 **Selecciona tu idioma:**\nPor favor, elige uno de los siguientes idiomas para cambiar la interfaz del bot:"
    }.get(language, "🌐 **Select your language:**")
    await message.answer(text=text, reply_markup=lang_markup)


@main_router.message(F.text.in_(set(BUTTON_WARRANTY.values())))
@main_router.message(Command("warranty"))
@main_router.message(Command("policy"))
@main_router.message(Command("dieukhoan"))
@main_router.message(Command("baohanh"))
@main_router.message(Command("terms"))
@main_router.callback_query(F.data == "view_full_policy")
async def handle_full_policy(event: Message | CallbackQuery, language: Language = Language.VI):
    from services.policy_defaults import get_default_policy, split_message_text

    is_cb = isinstance(event, CallbackQuery)
    if is_cb:
        await event.answer()
        target_msg = event.message
    else:
        target_msg = event

    policy_text = getattr(config, "WARRANTY_LEGAL_POLICY", "") or ""
    if not policy_text:
        policy_text = get_default_policy(language)

    kb_builder = InlineKeyboardBuilder()
    admin_btn_text = {
        Language.VI: "💬 Nhắn tin Admin (@truongdvfb)",
        Language.EN: "💬 Message Admin (@truongdvfb)",
        Language.HI: "💬 व्यवस्थापक को संदेश भेजें (@truongdvfb)",
        Language.ZH: "💬 联系管理员 (@truongdvfb)",
        Language.FR: "💬 Contacter l'administrateur (@truongdvfb)",
        Language.DE: "💬 Admin kontaktieren (@truongdvfb)",
        Language.IT: "💬 Contatta l'amministratore (@truongdvfb)",
        Language.ES: "💬 Contactar al Administrador (@truongdvfb)",
    }.get(language, "💬 Message Admin (@truongdvfb)")

    back_btn_text = {
        Language.VI: "⬅️ Quay lại Hỗ trợ",
        Language.EN: "⬅️ Back to Support",
        Language.HI: "⬅️ वापस सहायता",
        Language.ZH: "⬅️ 返回客服中心",
        Language.FR: "⬅️ Retour au Support",
        Language.DE: "⬅️ Zurück zum Support",
        Language.IT: "⬅️ Torna all'assistenza",
        Language.ES: "⬅️ Volver al Soporte",
    }.get(language, "⬅️ Back to Support")

    kb_builder.button(text=admin_btn_text, url=config.SUPPORT_LINK)
    kb_builder.button(text=back_btn_text, callback_data="back_to_support_menu")
    kb_builder.adjust(1)

    chunks = split_message_text(policy_text, max_length=3800)

    if is_cb and len(chunks) == 1:
        try:
            await target_msg.edit_text(chunks[0], reply_markup=kb_builder.as_markup(), parse_mode="HTML")
            return
        except Exception:
            pass

    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            await target_msg.answer(chunk, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
        else:
            await target_msg.answer(chunk, parse_mode="HTML")


@main_router.message(F.text.in_(set(BUTTON_SUPPORT.values())))
@main_router.message(F.text.in_(set(BUTTON_WARRANTY.values())))
@main_router.message(F.text.in_({"💬 Hỗ trợ & Bảo hành", "🛡️ Bảo hành", "🛡️ Điều khoản", "Điều khoản", "Bảo hành", "Chính sách", "Terms", "Policy", "Warranty"}))
@main_router.message(Command("support"))
@main_router.message(Command("warranty"))
@main_router.message(Command("policy"))
@main_router.message(Command("dieukhoan"))
@main_router.message(Command("baohanh"))
@main_router.message(Command("terms"))
@main_router.message(Command("api"))
@main_router.message(Command("help"))
@main_router.message(Command("contact"))
@main_router.message(F.text.lower().in_({"điều khoản", "dieukhoan", "dieu khoan", "bảo hành", "baohanh", "chính sách", "chinhsach", "terms", "policy", "warranty", "help", "support"}))
@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.HELP)))
@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.FAQ)))
@main_router.callback_query(F.data == "back_to_support_menu")
async def handle_unified_support(event: Message | CallbackQuery, language: Language = Language.VI):
    from services.policy_defaults import get_default_summary

    is_cb = isinstance(event, CallbackQuery)
    if is_cb:
        await event.answer()
        target_msg = event.message
    else:
        target_msg = event

    kb_builder = InlineKeyboardBuilder()

    policy_btn_text = {
        Language.VI: "🛡️ Xem Điều khoản & Bảo hành (Toàn văn)",
        Language.EN: "🛡️ Full Warranty & Legal Policy",
        Language.HI: "🛡️ पूर्ण वारंटी और कानूनी नीति",
        Language.ZH: "🛡️ 查看完整质保与法律条款",
        Language.FR: "🛡️ Voir Politique de Garantie Complète",
        Language.DE: "🛡️ Vollständige Garantiebestimmungen",
        Language.IT: "🛡️ Termini di Garanzia Completi",
        Language.ES: "🛡️ Ver Política de Garantía Completa",
    }.get(language, "🛡️ Full Warranty & Legal Policy")

    admin_btn_text = {
        Language.VI: "💬 Nhắn tin Admin (@truongdvfb)",
        Language.EN: "💬 Message Admin (@truongdvfb)",
        Language.HI: "💬 व्यवस्थापक को संदेश भेजें (@truongdvfb)",
        Language.ZH: "💬 联系管理员 (@truongdvfb)",
        Language.FR: "💬 Contacter l'administrateur (@truongdvfb)",
        Language.DE: "💬 Admin kontaktieren (@truongdvfb)",
        Language.IT: "💬 Contatta l'amministratore (@truongdvfb)",
        Language.ES: "💬 Contactar al Administrador (@truongdvfb)",
    }.get(language, "💬 Message Admin (@truongdvfb)")

    kb_builder.button(text=policy_btn_text, callback_data="view_full_policy")
    kb_builder.button(text=admin_btn_text, url=config.SUPPORT_LINK)
    kb_builder.adjust(1)

    summary_text = getattr(config, "WARRANTY_SHORT_SUMMARY", "") or ""
    if not summary_text:
        summary_text = get_default_summary(language)

    if language == Language.VI:
        support_info = (
            f"💬 <b>TRUNG TÂM HỖ TRỢ & LIÊN HỆ ADMIN</b>\n"
            f"👤 <b>Admin:</b> @truongdvfb\n\n"
            f"{summary_text}\n\n"
            f"💳 <b>Hỗ trợ Ví & Nạp tiền:</b>\n"
            f"• Hỗ trợ nạp tiền tự động qua <b>Binance Pay (0% phí - Nhận 1s)</b> và <b>USDT Blockchain</b>.\n"
            f"• Nạp tự động chuyển khoản ngân hàng Việt Nam (VietQR 24/7).\n\n"
            f"🔑 <b>Kết nối API & Mua sỉ:</b>\n"
            f"• Cấp API Key, tài liệu kết nối cho tool tự động reg/nuôi clone và đại lý mua sỉ.\n"
            f"• Chiết khấu ưu đãi cho khách mua số lượng lớn.\n\n"
            f"👉 <i>Bấm nút bên dưới để xem toàn văn chính sách hoặc nhắn tin trực tiếp cho Admin:</i>"
        )
    else:
        support_info = (
            f"💬 <b>SUPPORT CENTER & CONTACT ADMIN</b>\n"
            f"👤 <b>Admin:</b> @truongdvfb\n\n"
            f"{summary_text}\n\n"
            f"💳 <b>Wallet & Deposit Support:</b>\n"
            f"• Automatic deposit available via <b>Binance Pay (0% Fee - 1s)</b> and <b>USDT</b>.\n\n"
            f"🔑 <b>API Integration & Bulk Orders:</b>\n"
            f"• REST API available for automation tools and wholesale partners.\n\n"
            f"👉 <i>Click below to read full warranty policy or message Admin:</i>"
        )

    if is_cb:
        try:
            await target_msg.edit_text(support_info, reply_markup=kb_builder.as_markup(), parse_mode="HTML")
            return
        except Exception:
            pass

    await target_msg.answer(support_info, reply_markup=kb_builder.as_markup(), parse_mode="HTML")


@main_router.message(F.text.in_(set(BUTTON_TOP_UP.values())))
@main_router.message(Command("deposit"))
@main_router.message(Command("nap"))
@main_router.message(Command("topup"))
async def handle_deposit_button(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    from services.deposit_flow import DepositFlowService
    await state.clear()
    text, kb = DepositFlowService.get_method_selection_keyboard(language)
    await message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")

@main_router.message(F.text.in_(set(BUTTON_ADMIN.values())))
async def handle_admin(message: Message, state: FSMContext, language: Language):
    if message.from_user.id in config.ADMIN_ID_LIST:
        await admin(message=message, state=state, language=language)


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
    await message.answer("⚠️ <b>Đã có lỗi xảy ra!</b> Vui lòng thử lại sau giây lát hoặc liên hệ Admin để được hỗ trợ.")
    traceback_str = traceback.format_exc()
    admin_notification = (
        f"Critical error caused by {event.exception}\n\n"
        f"Stack trace:\n{traceback_str}"
    )
    if len(admin_notification) > 4096:
        byte_array = bytearray(admin_notification, 'utf-8')
        admin_notification = BufferedInputFile(byte_array, "exception.txt")
    await NotificationService.send_to_admins(admin_notification, None)


throttling_middleware = ThrottlingMiddleware(redis, limit=0.15)
users_routers = Router()
users_routers.include_routers(
    all_categories_router,
    my_profile_router,
    cart_router,
    review_management_router,
    deposit_router,
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


@main_router.message(F.text, StateFilter(None))
async def fallback_any_text(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    current_state = await state.get_state()
    if current_state is not None:
        return
    text = (message.text or "").strip()
    if not text:
        return

    telegram_id = message.from_user.id
    try:
        from models.user import UserDTO
        from services.user import UserService
        await UserService.create_if_not_exist(UserDTO(
            telegram_username=message.from_user.username,
            telegram_id=telegram_id,
            language=language
        ), None, session)
        from utils.custom_filters import cache_user_exists
        from middleware.language import set_cached_user_language
        cache_user_exists(telegram_id)
        set_cached_user_language(telegram_id, language)
    except Exception as e:
        logging.debug(f"User registration in fallback: {e}")

    menu_keywords = {
        "menu", "shop", "home", "main", "start", "bot",
        "trang chủ", "trang chu", "bắt đầu", "bat dau", "mở menu", "mo menu",
        "hi", "hello", "xin chào", "xin chao", "alo", "helo",
        "trở về", "tro ve", "quay lại", "quay lai", "help",
        "hỗ trợ", "ho tro"
    }
    if text.lower() in menu_keywords:
        await start(message, session, language, None)
        return

    num_clean = text.replace(",", ".").replace("$", "").replace("USDT", "").replace("usdt", "").strip()
    try:
        val = float(num_clean)
        if val > 0:
            from services.deposit_flow import DepositFlowService
            text_method, kb_method = DepositFlowService.get_method_selection_keyboard(language)
            await message.answer(
                f"💡 Bạn vừa nhập số tiền <b>{val:g}</b>.\n"
                "Vui lòng chọn hình thức nạp tiền bên dưới để tạo hoá đơn:",
                reply_markup=kb_method.as_markup(),
                parse_mode="HTML"
            )
            return
    except ValueError:
        pass

    # Nếu người dùng gõ từ khoá tìm kiếm (như clone, via, fb, facebook...), tự động tìm kiếm ngay!
    if not text.startswith("/"):
        from handlers.user.all_categories import execute_global_search
        await execute_global_search(message, text, session, language)
        return

    await start(message, session, language, None)


if __name__ == '__main__':
    if config.MULTIBOT:
        main_multibot(main_router)
    else:
        dp.include_router(main_router)
        main()
