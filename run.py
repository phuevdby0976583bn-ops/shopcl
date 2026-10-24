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
    Language.VI: "💬 Hỗ trợ & Bảo hành",
    Language.EN: "💬 Support & Warranty",
    Language.HI: "💬 समर्थन और वारंटी",
    Language.ZH: "💬 客服与售后",
    Language.FR: "💬 Support & Garantie",
    Language.DE: "💬 Support & Garantie",
    Language.IT: "💬 Supporto e Garanzia",
    Language.ES: "💬 Soporte y Garantía",
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
    support_btn = types.KeyboardButton(text=BUTTON_SUPPORT.get(language, "💬 Support & Warranty"))

    lang_btn = types.KeyboardButton(text=BUTTON_LANGUAGE.get(language, "🌐 Language"))

    keyboard = [
        [prod_btn, orders_btn],
        [wallet_btn, support_btn],
        [lang_btn]
    ]
    if telegram_id in config.ADMIN_ID_LIST:
        admin_btn = types.KeyboardButton(text=BUTTON_ADMIN.get(language, "⚙️ Admin Menu"))
        keyboard.append([admin_btn])

    return types.ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)


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
    lang_code = callback.data.split(":")[1]
    new_lang = Language.from_locale(lang_code)

    user_dto = await UserRepository.get_by_tgid(callback.from_user.id, session)
    if user_dto:
        user_dto.language = new_lang
        await UserRepository.update(user_dto, session)
        await session_commit(session)
        from middleware.language import set_cached_user_language
        set_cached_user_language(callback.from_user.id, new_lang)

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


from services.binance_pay import BinancePayService


@main_router.callback_query(F.data == "binance_pay:view")
async def show_binance_pay_screen(callback: CallbackQuery, session: AsyncSession, language: Language):
    media, kb_builder = await BinancePayService.build_payment_screen(callback.from_user.id, session, language)
    try:
        await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())
    except Exception:
        await callback.message.delete()
        await callback.message.answer_photo(photo=media.media, caption=media.caption, reply_markup=kb_builder.as_markup(), parse_mode="HTML")


@main_router.callback_query(F.data == "binance_pay:check")
async def check_binance_pay_payment(callback: CallbackQuery, session: AsyncSession, language: Language):
    checking_toast = {
        Language.VI: "🔍 Đang kiểm tra giao dịch trên Binance...",
        Language.EN: "🔍 Checking transaction on Binance...",
        Language.HI: "🔍 Binance पर लेनदेन की जाँच की जा रही है...",
        Language.ZH: "🔍 正在查询币安交易状态...",
        Language.FR: "🔍 Vérification de la transaction sur Binance...",
        Language.DE: "🔍 Transaktion auf Binance wird überprüft...",
        Language.IT: "🔍 Verifica transazione su Binance in corso...",
        Language.ES: "🔍 Verificando transacción en Binance..."
    }.get(language, "🔍 Checking transaction on Binance...")
    await callback.answer(checking_toast)

    credited = await BinancePayService.process_and_credit_transactions(bot, session, callback.from_user.id)
    if credited:
        total_credited = sum(item["amount"] for item in credited)
        success_toast = {
            Language.VI: f"🎉 Đã nhận và cộng thành công +{total_credited} USDT vào tài khoản!",
            Language.EN: f"🎉 Successfully credited +{total_credited} USDT to your balance!",
            Language.HI: f"🎉 सफलतापूर्वक आपके खाते में +{total_credited} USDT जोड़ दिए गए!",
            Language.ZH: f"🎉 成功到账 +{total_credited} USDT 至您的账户！",
            Language.FR: f"🎉 +{total_credited} USDT crédités avec succès sur votre compte !",
            Language.DE: f"🎉 +{total_credited} USDT erfolgreich Ihrem Guthaben gutgeschrieben!",
            Language.IT: f"🎉 Accreditati con successo +{total_credited} USDT sul tuo conto!",
            Language.ES: f"🎉 ¡Se han acreditado con éxito +{total_credited} USDT en su saldo!"
        }.get(language, f"🎉 Successfully credited +{total_credited} USDT!")
        await callback.answer(success_toast, show_alert=True)
        from handlers.user.my_profile import my_profile
        await my_profile(callback=callback, session=session, state=None, language=language)
    else:
        no_tx_alert = {
            Language.VI: """⏳ Chưa phát hiện giao dịch mới!

Nếu bạn vừa chuyển trên App Binance, vui lòng đợi 5-15 giây rồi bấm lại nút này.

⚠️ Lưu ý: BẮT BUỘC phải điền đúng mã Ghi chú (Memo) khi chuyển tiền!""",
            Language.EN: """⏳ No new transaction detected!

If you just sent on Binance App, please wait 5-15 seconds and try again.

⚠️ Note: You MUST enter the correct Remark/Memo when transferring!""",
            Language.HI: """⏳ कोई नया लेनदेन नहीं मिला!

यदि आपने अभी भेजा है, तो कृपया 5-15 सेकंड प्रतीक्षा करें और पुनः प्रयास करें।""",
            Language.ZH: """⏳ 暂未检测到新交易！

如果您刚刚完成转账，请等待5-15秒后重试。

⚠️ 注意：转账时请务必填写正确的备注 Memo！""",
            Language.FR: """⏳ Aucune nouvelle transaction détectée !

Si vous venez d'effectuer le transfert, veuillez patienter 5 à 15 secondes puis réessayer.

⚠️ Remarque : Vous DEVEZ indiquer le Memo correct lors du virement !""",
            Language.DE: """⏳ Keine neue Transaktion erkannt!

Wenn Sie gerade überwiesen haben, warten Sie bitte 5-15 Sekunden und versuchen Sie es erneut.

⚠️ Hinweis: Sie MÜSSEN den richtigen Hinweis (Memo) angeben!""",
            Language.IT: """⏳ Nessuna nuova transazione rilevata!

Se hai appena trasferito, attendi 5-15 secondi e riprova.

⚠️ Nota: DEVI inserire il Remark/Memo corretto durante il trasferimento!""",
            Language.ES: """⏳ ¡No se ha detectado ninguna transacción nueva!

Si acabas de enviar en Binance, espera entre 5 y 15 segundos e intenta de nuevo.

⚠️ Nota: ¡DEBES ingresar el Remark/Memo correcto al transferir!"""
        }.get(language, "⏳ No new transaction detected!")
        await callback.answer(no_tx_alert, show_alert=True)


@main_router.message(F.text.in_(set(BUTTON_PRODUCTS.values())))
@main_router.message(Command("products"))
async def handle_products(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await all_types(callback=message, session=session, state=state, language=language)


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
    await my_profile(message=message, session=session, state=state, language=language)


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


@main_router.message(F.text.in_(set(BUTTON_SUPPORT.values()) | set(BUTTON_WARRANTY.values())))
@main_router.message(Command("support"))
@main_router.message(Command("warranty"))
@main_router.message(Command("api"))
@main_router.message(Command("help"))
@main_router.message(Command("contact"))
@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.HELP)))
@main_router.message(F.text.in_(KeyboardButton.get_localized_set(KeyboardButton.FAQ)))
async def handle_unified_support(message: Message, language: Language):
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

    kb_builder.button(text=admin_btn_text, url=config.SUPPORT_LINK)

    support_info = {
        Language.VI: (
            "💬 **TRUNG TÂM HỖ TRỢ & LIÊN HỆ ADMIN**\n"
            "👤 **Admin:** @truongdvfb\n\n"
            "🛡️ **1. Chính sách bảo hành & Đổi trả:**\n"
            "• Bảo hành 1 đổi 1 trong vòng 24 giờ kể từ lúc nhận hàng nếu tài khoản lỗi do hệ thống.\n"
            "• Vui lòng giữ nguyên định dạng ban đầu khi nhận đơn.\n"
            "• Gửi kèm **Mã đơn hàng (Order ID)** khi nhắn tin để được hỗ trợ nhanh nhất.\n\n"
            "💳 **2. Hỗ trợ Ví & Nạp tiền:**\n"
            "• Hỗ trợ nạp tiền tự động qua **Binance Pay (0% phí)** và **USDT Blockchain**.\n"
            "• Nếu cần kiểm tra giao dịch nạp, vui lòng gửi mã Memo hoặc TxID cho Admin.\n\n"
            "🔑 **3. Kết nối API & Mua sỉ:**\n"
            "• Cấp API Key, tài liệu kết nối cho tool tự động reg/nuôi clone và đại lý mua sỉ.\n"
            "• Chiết khấu ưu đãi cho khách mua số lượng lớn.\n\n"
            "👉 **Bấm nút bên dưới để nhắn tin trực tiếp cho Admin:**"
        ),
        Language.EN: (
            "💬 **SUPPORT CENTER & CONTACT ADMIN**\n"
            "👤 **Admin:** @truongdvfb\n\n"
            "🛡️ **1. Warranty & Replacement Policy:**\n"
            "• 1-to-1 replacement within 24 hours of delivery if there is any system error.\n"
            "• Please keep the original format delivered.\n"
            "• Send your **Order ID** for the fastest resolution.\n\n"
            "💳 **2. Wallet & Deposit Support:**\n"
            "• Automatic deposit available via **Binance Pay (0% Fee)** and **USDT Blockchain**.\n"
            "• For deposit verification, send your Memo or TxID to Admin.\n\n"
            "🔑 **3. API Integration & Bulk Orders:**\n"
            "• API Key and REST documentation provided for automation tools and wholesale partners.\n"
            "• Special discounts for high-volume orders.\n\n"
            "👉 **Click the button below to message Admin directly:**"
        ),
        Language.HI: (
            "💬 **सहायता केंद्र और व्यवस्यापक संपर्क**\n"
            "👤 **व्यवस्यापक:** @truongdvfb\n\n"
            "🛡️ **1. वारंटी और प्रतिस्थापन:**\n"
            "• सिस्टम त्रुटि के मामले में 24 घंटे के भीतर **1-टू-1 वारंटी**।\n"
            "• कृपया सहायता के लिए अपना **ऑर्डर आईडी (Order ID)** भेजें।\n\n"
            "💳 **2. वॉलेट और जमा समर्\u0925न:**\n"
            "• **Binance Pay (0% शुल्क)** और **USDT** द्वारा स्वचालित जमा।\n\n"
            "🔑 **3. एपीआई और थोक खरीद:**\n"
            "• टूल और थोक विक्रेताओं के लिए एपीआई कुंजी उपलब्ध है।\n\n"
            "👉 **व्यवस्यापक से संपर्क करने के लिए नीचे दिए गए बटन पर क्लिक करें:**"
        ),
        Language.ZH: (
            "💬 **客服支持与售后中心**\n"
            "👤 **管理员:** @truongdvfb\n\n"
            "🛡️ **1. 售后保修政策:**\n"
            "• 购买后24小时内如遇系统问题，**1对1换新**。\n"
            "• 请保留发货时的原始格式，并提供 **订单号 (Order ID)**。\n\n"
            "💳 **2. 充值与钱包支持:**\n"
            "• 支持 **Binance Pay（0% 手续费）** 及 **USDT** 自动充值。\n"
            "• 充值遇阻请发送 Memo 备注或 TxID 给管理员。\n\n"
            "🔑 **3. API 接口与批量采购:**\n"
            "• 为代理、养号/注册工具提供 REST API 接口及技术文档。\n"
            "• 大额批发享专属折扣优惠。\n\n"
            "👉 **点击下方按钮直接联系管理员:**"
        ),
        Language.FR: (
            "💬 **CENTRE DE SUPPORT & GARANTIE**\n"
            "👤 **Administrateur :** @truongdvfb\n\n"
            "🛡️ **1. Politique de garantie :**\n"
            "• Remplacement **1 pour 1** sous 24h en cas d'erreur système ou problème initial.\n"
            "• Veuillez conserver le format d'origine livré et fournir votre **Numéro de commande (Order ID)**.\n\n"
            "💳 **2. Support portefeuille & recharge :**\n"
            "• Recharge automatique via **Binance Pay (0% de frais)** et **USDT**.\n"
            "• En cas de problème de dépôt, envoyez la note Memo ou le TxID à l'administrateur.\n\n"
            "🔑 **3. API & Achats en gros :**\n"
            "• Clé API REST disponible pour outils et revendeurs avec documentation technique.\n"
            "• Tarifs préférentiels pour les gros volumes.\n\n"
            "👉 **Cliquez sur le bouton ci-dessous pour contacter l'administrateur :**"
        ),
        Language.DE: (
            "💬 **KUNDENSERVICE & GARANTIEZENTRUM**\n"
            "👤 **Administrator:** @truongdvfb\n\n"
            "🛡️ **1. Garantiebestimmungen:**\n"
            "• **1:1-Ersatz** innerhalb von 24 Stunden bei Systemfehlern oder Erstproblemen.\n"
            "• Bitte Originalformat beibehalten und Ihre **Bestellnummer (Order ID)** bereithalten.\n\n"
            "💳 **2. Guthaben & Aufladung:**\n"
            "• Automatische Aufladung über **Binance Pay (0% Gebühr)** und **USDT**.\n"
            "• Bei Verzögerungen Memo-Code oder TxID an den Administrator senden.\n\n"
            "🔑 **3. API & Großeinkauf:**\n"
            "• REST-API-Schlüssel für Tools und Wiederverkäufer verfügbar.\n"
            "• Attraktive Rabatte bei Großbestellungen.\n\n"
            "👉 **Klicken Sie unten, um den Administrator direkt zu kontaktieren:**"
        ),
        Language.IT: (
            "💬 **CENTRO ASSISTENZA & GARANZIA**\n"
            "👤 **Amministratore:** @truongdvfb\n\n"
            "🛡️ **1. Politica di garanzia:**\n"
            "• Sostituzione **1 a 1** entro 24 ore in caso di errori di sistema o difetti iniziali.\n"
            "• Conservare il formato originale e fornire il proprio **ID Ordine (Order ID)**.\n\n"
            "💳 **2. Supporto portafoglio & ricariche:**\n"
            "• Ricarica automatica tramite **Binance Pay (0% commissioni)** e **USDT**.\n"
            "• In caso di necessità, inviare il Memo o TxID all'amministratore.\n\n"
            "🔑 **3. API & Acquisti all'ingrosso:**\n"
            "• Chiavi API REST disponibili per tool e rivenditori con documentazione completa.\n"
            "• Sconti dedicati per ordini all'ingrosso.\n\n"
            "👉 **Clicca sul pulsante qui sotto per contattare l'amministratore:**"
        ),
        Language.ES: (
            "💬 **CENTRO DE SOPORTE & GARANTÍA**\n"
            "👤 **Administrador:** @truongdvfb\n\n"
            "🛡️ **1. Política de garantía:**\n"
            "• Reemplazo **1 a 1** dentro de las 24 horas por fallas del sistema o problemas iniciales.\n"
            "• Conserve el formato de entrega original y proporcione su **ID de Pedido (Order ID)**.\n\n"
            "💳 **2. Soporte de billetera y depósitos:**\n"
            "• Depósito automático a través de **Binance Pay (0% comisión)** y **USDT**.\n"
            "• Si tiene algún problema, envíe el Memo o TxID al administrador.\n\n"
            "🔑 **3. API y compras al por mayor:**\n"
            "• Claves API REST disponibles para herramientas y distribuidores con documentación técnica.\n"
            "• Descuentos exclusivos para compras al por mayor.\n\n"
            "👉 **Haz clic en el botón de abajo para contactar al administrador:**"
        )
    }.get(language, "💬 **SUPPORT CENTER & CONTACT ADMIN**")

    await message.answer(support_info, reply_markup=kb_builder.as_markup())


@main_router.message(F.text.in_(set(BUTTON_TOP_UP.values())))
@main_router.message(Command("deposit"))
@main_router.message(Command("nap"))
@main_router.message(Command("topup"))
async def handle_deposit_button(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    from callbacks import MyProfileCallback
    from services.user import UserService
    cb_data = MyProfileCallback.create(level=1)
    msg_text, kb_builder = await UserService.get_top_up_buttons(cb_data, language)
    await message.answer(msg_text, reply_markup=kb_builder.as_markup())

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
