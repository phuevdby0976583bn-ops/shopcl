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
    response, kb_builder = await PaymentService.create(callback, callback_data, state, session, language)
    if isinstance(response, str):
        await callback.message.edit_caption(caption=response, reply_markup=kb_builder.as_markup())
    else:
        await callback.message.edit_media(media=response, reply_markup=kb_builder.as_markup())


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
    media, kb_builder = await PaymentService.create(message,
                                                    None,
                                                    state,
                                                    session,
                                                    language)
    state_data = await state.get_data()
    if state_data.get("chat_id") and state_data.get("msg_id"):
        await message.bot.edit_message_media(chat_id=state_data.get("chat_id"),
                                             message_id=state_data.get("msg_id"),
                                             media=media,
                                             reply_markup=kb_builder.as_markup())
    else:
        await NotificationService.answer_media(message, media, kb_builder.as_markup())


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


@my_profile_router.callback_query(F.data == "binance_pay:view", IsUserExistFilter())
async def binance_pay_view_handler(callback: CallbackQuery, session: AsyncSession, language: Language):
    from services.binance_pay import BinancePayService
    media, kb_builder = await BinancePayService.build_payment_screen(callback.from_user.id, session, language)
    await callback.message.edit_media(media=media, reply_markup=kb_builder.as_markup())


@my_profile_router.callback_query(F.data == "binance_pay:check", IsUserExistFilter())
async def binance_pay_check_handler(callback: CallbackQuery, session: AsyncSession, language: Language):
    from services.binance_pay import BinancePayService
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

    credited = await BinancePayService.process_and_credit_transactions(
        bot=callback.bot,
        session=session,
        target_telegram_id=callback.from_user.id
    )
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
        await my_profile(callback=callback, session=session, language=language)
    else:
        no_tx_alert = {
            Language.VI: (
                f"⏳ Chưa thấy giao dịch mới trên Binance!\n\n"
                f"Nếu bạn vừa chuyển, vui lòng đợi 10-20 giây rồi bấm kiểm tra lại nhé.\n"
                f"⚠️ Lưu ý: Bắt buộc phải có nội dung Note: NAP {callback.from_user.id}"
            ),
            Language.EN: (
                f"⏳ No new transaction detected on Binance!\n\n"
                f"If you just transferred, please wait 10-20 seconds and check again.\n"
                f"⚠️ Note: You MUST enter Note: NAP {callback.from_user.id}"
            ),
            Language.HI: (
                f"⏳ Binance पर कोई नया लेनदेन नहीं मिला!\n\n"
                f"यदि आपने अभी ट्रांसफर किया है, तो कृपया 10-20 सेकंड प्रतीक्षा करें और पुनः प्रयास करें।\n"
                f"⚠️ नोट: आपको Note: NAP {callback.from_user.id} दर्ज करना आवश्यक है"
            ),
            Language.ZH: (
                f"⏳ 暂未在币安上检测到新交易！\n\n"
                f"如果您刚刚完成转账，请等待 10-20 秒后重新点击检查。\n"
                f"⚠️ 注意：转账时必须填写备注 Note: NAP {callback.from_user.id}"
            ),
            Language.FR: (
                f"⏳ Aucune nouvelle transaction détectée sur Binance !\n\n"
                f"Si vous venez d'effectuer le transfert, veuillez patienter 10-20 secondes puis réessayer.\n"
                f"⚠️ Remarque : Vous DEVEZ indiquer dans la Note : NAP {callback.from_user.id}"
            ),
            Language.DE: (
                f"⏳ Keine neue Transaktion auf Binance erkannt!\n\n"
                f"Wenn Sie gerade überwiesen haben, warten Sie bitte 10-20 Sekunden und prüfen Sie erneut.\n"
                f"⚠️ Hinweis: Sie MÜSSEN als Notiz angeben: NAP {callback.from_user.id}"
            ),
            Language.IT: (
                f"⏳ Nessuna nuova transazione rilevata su Binance!\n\n"
                f"Se hai appena trasferito, attendi 10-20 secondi e ricontrolla.\n"
                f"⚠️ Nota: DEVI obbligatoriamente inserire nella Nota: NAP {callback.from_user.id}"
            ),
            Language.ES: (
                f"⏳ ¡No se ha detectado ninguna transacción nueva en Binance!\n\n"
                f"Si acabas de transferir, espera entre 10 y 20 segundos y vuelve a consultar.\n"
                f"⚠️ Nota: DEBES ingresar obligatoriamente en Nota: NAP {callback.from_user.id}"
            )
        }.get(language, f"⏳ No new transaction detected!\nNote: NAP {callback.from_user.id}")
        await callback.answer(no_tx_alert, show_alert=True)
