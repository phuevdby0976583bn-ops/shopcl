import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import AllCategoriesCallback, MyProfileCallback
from enums.entity_type import EntityType
from enums.item_type import ItemType
from enums.keyboard_button import KeyboardButton as KB
from enums.bot_entity import BotEntity
from enums.buy_status import BuyStatus
from enums.language import Language
from utils.utils import get_text
from handlers.common.common import enable_search
from handlers.user.constants import UserStates
from services.category import CategoryService
from services.notification import NotificationService
from services.subcategory import SubcategoryService
from repositories.item import ItemRepository
from repositories.user import UserRepository
from repositories.category import CategoryRepository
from repositories.subcategory import SubcategoryRepository
from repositories.buy import BuyRepository
from repositories.buyItem import BuyItemRepository
from models.buy import BuyDTO
from models.buyItem import BuyItemDTO
from db import session_commit
from services.facebook import (
    filter_live_facebook_items,
    is_facebook_clone,
    is_facebook_product,
    extract_uid
)
from utils.custom_filters import IsUserExistFilter
import config

logger = logging.getLogger(__name__)

all_categories_router = Router()


def _sym() -> str:
    return 'USDT' if getattr(config, 'ONLY_USDT_MODE', False) else config.CURRENCY.get_localized_symbol()


async def _send_or_edit_text(target: Message | CallbackQuery, text: str, reply_markup=None):
    text_content = text or '...'
    if isinstance(target, Message):
        try:
            return await target.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
        except Exception:
            return await target.answer(text=text_content, reply_markup=reply_markup)
    else:
        callback = target
        if callback.message.caption:
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                return await callback.message.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
            except Exception:
                return await callback.message.answer(text=text_content, reply_markup=reply_markup)
        else:
            try:
                return await callback.message.edit_text(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
            except Exception:
                try:
                    return await callback.message.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
                except Exception:
                    return await callback.message.answer(text=text_content, reply_markup=reply_markup)


@all_categories_router.message(F.text.in_(KB.get_localized_set(KB.ALL_CATEGORIES)), IsUserExistFilter())
async def all_categories_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    callback_data = AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    await all_categories(callback=message, callback_data=callback_data, session=session, state=state, language=language)


async def all_types(**kwargs):
    kwargs['callback_data'] = AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    await all_categories(**kwargs)


async def all_categories(**kwargs):
    callback: CallbackQuery | Message = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    state: FSMContext = kwargs.get('state')
    language: Language = kwargs.get('language')

    if callback_data is None:
        callback_data = AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)

    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.CATEGORY,
                                                {'item_type': item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)

    caption = getattr(media, 'caption', None) or get_text(language, BotEntity.USER, 'pick_category')
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def show_subcategories_in_category(**kwargs):
    callback: CallbackQuery = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    state: FSMContext = kwargs.get('state')
    language: Language = kwargs.get('language')
    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.SUBCATEGORY,
                                                {'category_id': callback_data.category_id,
                                                 'item_type': item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)

    caption = getattr(media, 'caption', None) or get_text(language, BotEntity.USER, 'subcategories')
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def select_quantity(**kwargs):
    callback: CallbackQuery = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    language: Language = kwargs.get('language')
    media, kb_builder = await SubcategoryService.get_select_quantity_buttons(callback_data, session, language)
    caption = getattr(media, 'caption', None) or get_text(language, BotEntity.USER, 'select_quantity')
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def instant_buy_confirmation(**kwargs):
    callback: CallbackQuery = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    language: Language = kwargs.get('language')
    user = await UserRepository.get_by_tgid(callback.from_user.id, session, for_update=True)
    msg, kb_builder = await SubcategoryService.get_instant_buy_confirmation(callback_data, user, session, language)
    await _send_or_edit_text(callback, msg, kb_builder.as_markup())


async def execute_instant_buy(**kwargs):
    callback: CallbackQuery = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    language: Language = kwargs.get('language')

    if not callback_data.confirmation:
        return await show_subcategories_in_category(**kwargs)

    try:
        user = await UserRepository.get_by_tgid(callback.from_user.id, session, for_update=True)
        if not user:
            return await callback.answer('Vui lòng gõ /start để khởi tạo tài khoản!', show_alert=True)

        category = await CategoryRepository.get_by_id(callback_data.category_id, session)
        subcategory = await SubcategoryRepository.get_by_id(callback_data.subcategory_id, session)
        item = await ItemRepository.get_single(
            callback_data.item_type, callback_data.category_id, callback_data.subcategory_id, session
        )

        unit_price = (getattr(subcategory, 'price', None) or (getattr(item, 'price', 0.0) if item else 0.0)) or 0.0
        if not item and not (subcategory and getattr(subcategory, 'price', None)):
            kb_builder = InlineKeyboardBuilder()
            btn_other = {
                Language.VI: "📁 Xem sản phẩm khác",
                Language.ZH: "📁 查看其他商品",
                Language.HI: "📁 अन्य उत्पाद देखें",
                Language.FR: "📁 Voir d'autres produits",
                Language.DE: "📁 Andere Produkte ansehen",
                Language.IT: "📁 Vedi altri prodotti",
                Language.ES: "📁 Ver otros productos"
            }.get(language, "📁 View Other Products")
            kb_builder.button(text=btn_other, callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL))
            out_msg = {
                Language.VI: "❌ <b>Sản phẩm này tạm thời hết hàng hoặc không tồn tại.</b>",
                Language.ZH: "❌ <b>该商品暂时缺货或不存在。</b>",
                Language.HI: "❌ <b>यह उत्पाद वर्तमान में स्टॉक में नहीं है या मौजूद नहीं है।</b>",
                Language.FR: "❌ <b>Ce produit est actuellement en rupture de stock ou n'existe pas.</b>",
                Language.DE: "❌ <b>Dieses Produkt ist derzeit nicht vorrätig oder existiert nicht.</b>",
                Language.IT: "❌ <b>Questo prodotto è temporaneamente esaurito o non esiste.</b>",
                Language.ES: "❌ <b>Este producto está agotado temporalmente o no existe.</b>"
            }.get(language, "❌ <b>This product is currently out of stock or does not exist.</b>")
            return await _send_or_edit_text(callback, out_msg, kb_builder.as_markup())

        qty = callback_data.quantity or 1
        total_price = unit_price * qty
        user_balance = max(0.0, (getattr(user, 'top_up_amount', 0.0) or 0.0) - (getattr(user, 'consume_records', 0.0) or 0.0))
        sym = _sym()

        # Kiểm tra số dư ví
        if user_balance < total_price:
            missing = total_price - user_balance
            kb_builder = InlineKeyboardBuilder()
            btn_bin = {
                Language.VI: "⚡ Nạp Binance Pay (0% Phí - Tự Động)",
                Language.ZH: "⚡ 币安支付 (0手续费 - 秒到)",
                Language.HI: "⚡ Binance Pay (0% शुल्क)",
                Language.FR: "⚡ Binance Pay (0% Frais)",
                Language.DE: "⚡ Binance Pay (0% Gebühr)",
                Language.IT: "⚡ Binance Pay (0% Commissioni)",
                Language.ES: "⚡ Binance Pay (0% Comisión)"
            }.get(language, "⚡ Binance Pay (0% Fee - Instant)")
            btn_bank = {
                Language.VI: "🏦 Nạp Ngân Hàng (VietQR / BIDV)",
                Language.ZH: "🏦 越南银行卡 (VietQR / BIDV)",
                Language.HI: "🏦 वियतनाम बैंक (VietQR / BIDV)",
                Language.FR: "🏦 Banque Vietnam (VietQR / BIDV)",
                Language.DE: "🏦 Vietnam Bank (VietQR / BIDV)",
                Language.IT: "🏦 Banca Vietnam (VietQR / BIDV)",
                Language.ES: "🏦 Banco Vietnam (VietQR / BIDV)"
            }.get(language, "🏦 Vietnam Bank (VietQR / BIDV)")
            btn_on = {
                Language.VI: "💳 Nạp On-chain Crypto (USDT)",
                Language.ZH: "💳 链上充值 (USDT)",
                Language.HI: "💳 ऑन-चेन क्रिप्टो (USDT)",
                Language.FR: "💳 Dépôt Crypto On-chain (USDT)",
                Language.DE: "💳 On-chain Krypto (USDT)",
                Language.IT: "💳 Deposito On-chain (USDT)",
                Language.ES: "💳 Depósito On-chain (USDT)"
            }.get(language, "💳 Crypto Deposit (USDT)")
            btn_re = {
                Language.VI: "⬅️ Chọn lại số lượng",
                Language.ZH: "⬅️ 重选数量",
                Language.HI: "⬅️ मात्रा बदलें",
                Language.FR: "⬅️ Changer la quantité",
                Language.DE: "⬅️ Menge ändern",
                Language.IT: "⬅️ Cambia quantità",
                Language.ES: "⬅️ Cambiar cantidad"
            }.get(language, "⬅️ Change Quantity")

            kb_builder.button(text=btn_bin, callback_data='binance_pay:view')
            kb_builder.button(text=btn_bank, callback_data='dep_method:bank')
            kb_builder.button(text=btn_on, callback_data='deposit:start')
            kb_builder.button(
                text=btn_re,
                callback_data=AllCategoriesCallback.create(
                    level=3,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id
                )
            )
            kb_builder.adjust(1, 1, 1, 1)

            insufficient_templates = {
                Language.VI: (
                    f'❌ <b>Số dư ví không đủ để thanh toán!</b>\n\n'
                    f'💰 <b>Cần thanh toán:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>Số dư hiện tại:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>Còn thiếu:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 Vui lòng nạp thêm tiền vào tài khoản để nhận clone ngay lập tức!'
                ),
                Language.ZH: (
                    f'❌ <b>钱包余额不足以完成支付！</b>\n\n'
                    f'💰 <b>需付金额:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>当前余额:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>还缺:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 请先充值后即可秒发卡！'
                ),
                Language.HI: (
                    f'❌ <b>भुगतान के लिए वॉलेट में अपर्याप्त शेष राशि!</b>\n\n'
                    f'💰 <b>आवश्यक राशि:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>वर्तमान शेष:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>कमी:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 तुरंत खाता प्राप्त करने के लिए कृपया वॉलेट टॉप अप करें!'
                ),
                Language.FR: (
                    f'❌ <b>Solde insuffisant pour effectuer le paiement !</b>\n\n'
                    f'💰 <b>Montant requis :</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>Solde actuel :</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>Manquant :</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 Veuillez recharger votre portefeuille pour recevoir vos comptes immédiatement !'
                ),
                Language.DE: (
                    f'❌ <b>Nicht genügend Guthaben für diese Zahlung!</b>\n\n'
                    f'💰 <b>Erforderlich:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>Aktuelles Guthaben:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>Fehlend:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 Bitte laden Sie Ihr Wallet auf, um Ihre Konten sofort zu erhalten!'
                ),
                Language.IT: (
                    f'❌ <b>Saldo insufficiente per completare il pagamento!</b>\n\n'
                    f'💰 <b>Importo richiesto:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>Saldo attuale:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>Mancante:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 Ricarica il portafoglio per ricevere gli account immediatamente!'
                ),
                Language.ES: (
                    f'❌ <b>¡Saldo insuficiente para realizar el pago!</b>\n\n'
                    f'💰 <b>Monto requerido:</b> <code>{total_price:.2f} {sym}</code>\n'
                    f'💳 <b>Saldo actual:</b> <code>{user_balance:.2f} {sym}</code>\n'
                    f'⚠️ <b>Faltan:</b> <code>{missing:.2f} {sym}</code>\n\n'
                    f'👉 ¡Por favor recarga tu billetera para recibir tus cuentas de inmediato!'
                ),
            }
            insufficient_msg = insufficient_templates.get(language, (
                f'❌ <b>Insufficient wallet balance!</b>\n\n'
                f'💰 <b>Amount needed:</b> <code>{total_price:.2f} {sym}</code>\n'
                f'💳 <b>Current balance:</b> <code>{user_balance:.2f} {sym}</code>\n'
                f'⚠️ <b>Missing:</b> <code>{missing:.2f} {sym}</code>\n\n'
                f'👉 Please top up your wallet to receive accounts immediately!'
            ))
            return await _send_or_edit_text(callback, insufficient_msg, kb_builder.as_markup())

        # Lấy danh sách ứng viên tài khoản trong kho
        candidates = await ItemRepository.get_unsold_candidates(
            callback_data.item_type,
            callback_data.category_id,
            callback_data.subcategory_id,
            limit=max(qty * 3, 50),
            session=session
        )

        is_fb = (
            is_facebook_product(category.name if category else '', subcategory.name if subcategory else '')
            or any(is_facebook_clone(c.private_data) for c in candidates)
        )

        check_live_delivery = getattr(config, 'FB_CHECK_LIVE_BEFORE_DELIVERY', True)
        auto_delete_delivery = getattr(config, 'FB_AUTO_DELETE_DIE_ON_DELIVERY', True)

        if is_fb and check_live_delivery:
            try:
                await callback.answer('⚡ Đang kiểm tra LIVE qua Facebook Graph API...', show_alert=False)
            except Exception:
                pass

            live_items, dead_items = await filter_live_facebook_items(candidates, required_qty=qty)
            if dead_items:
                if auto_delete_delivery:
                    await ItemRepository.delete_items_by_ids([d.id for d in dead_items], session)
                else:
                    await ItemRepository.mark_items_as_dead([d.id for d in dead_items], session)

            checked_ids = {it.id for it in live_items} | {it.id for it in dead_items}
            while len(live_items) < qty:
                more_candidates = await ItemRepository.get_unsold_candidates(
                    callback_data.item_type,
                    callback_data.category_id,
                    callback_data.subcategory_id,
                    limit=50,
                    session=session
                )
                untested = [c for c in more_candidates if c.id not in checked_ids]
                if not untested:
                    break
                for u in untested:
                    checked_ids.add(u.id)
                new_live, new_dead = await filter_live_facebook_items(
                    untested,
                    required_qty=(qty - len(live_items))
                )
                if new_dead:
                    if auto_delete_delivery:
                        await ItemRepository.delete_items_by_ids([d.id for d in new_dead], session)
                    else:
                        await ItemRepository.mark_items_as_dead([d.id for d in new_dead], session)
                live_items.extend(new_live)

            if len(live_items) < qty:
                await session_commit(session)
                kb_builder = InlineKeyboardBuilder()
                subcat_name = subcategory.name if subcategory else 'Facebook Clone'
                if len(live_items) > 0:
                    avail_price = unit_price * len(live_items)
                    kb_builder.button(
                        text=f'⚡ Mua ngay {len(live_items)} nick LIVE còn lại ({avail_price:.2f} {sym})',
                        callback_data=AllCategoriesCallback.create(
                            level=4,
                            item_type=callback_data.item_type,
                            category_id=callback_data.category_id,
                            subcategory_id=callback_data.subcategory_id,
                            quantity=len(live_items)
                        )
                    )
                kb_builder.button(
                    text='⬅️ Chọn lại số lượng',
                    callback_data=AllCategoriesCallback.create(
                        level=3,
                        item_type=callback_data.item_type,
                        category_id=callback_data.category_id,
                        subcategory_id=callback_data.subcategory_id
                    )
                )
                kb_builder.button(
                    text='📁 Xem sản phẩm khác',
                    callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
                )
                kb_builder.adjust(1)
                msg = (
                    f'⚠️ <b>Kho không đủ số lượng tài khoản LIVE theo yêu cầu!</b>\n\n'
                    f'📦 Sản phẩm: <b>{subcat_name}</b>\n'
                    f'🔢 Số lượng bạn đặt: <b>{qty}</b> tài khoản\n'
                    f'✅ Số tài khoản LIVE thực tế còn lại: <b>{len(live_items)}</b>\n\n'
                    f'<i>⚡ Bot đã tự động check Live qua Facebook Graph API trước khi giao để đảm bảo bạn luôn nhận được nick LIVE 100%. Các tài khoản DIE đã được loại bỏ. Số dư của bạn chưa bị trừ!</i>'
                )
                return await _send_or_edit_text(callback, msg, kb_builder.as_markup())

            purchased_items = live_items[:qty]
        else:
            purchased_items = await ItemRepository.get_purchased_items(
                callback_data.item_type,
                callback_data.category_id,
                callback_data.subcategory_id,
                qty,
                session
            )
            if len(purchased_items) < qty:
                kb_builder = InlineKeyboardBuilder()
                kb_builder.button(
                    text='⬅️ Chọn lại số lượng',
                    callback_data=AllCategoriesCallback.create(
                        level=3,
                        item_type=callback_data.item_type,
                        category_id=callback_data.category_id,
                        subcategory_id=callback_data.subcategory_id
                    )
                )
                kb_builder.button(
                    text='📁 Xem sản phẩm khác',
                    callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
                )
                kb_builder.adjust(1, 1)
                msg = f'❌ <b>Kho không đủ số lượng yêu cầu!</b>\nHiện chỉ còn {len(purchased_items)} tài khoản trong kho.'
                return await _send_or_edit_text(callback, msg, kb_builder.as_markup())

        # TRỪ TIỀN VÀ CẬP NHẬT TRẠNG THÁI
        user.consume_records = (user.consume_records or 0.0) + total_price
        await UserRepository.update(user, session)

        for it in purchased_items:
            it.is_sold = True
            it.is_new = False
        await ItemRepository.update(purchased_items, session)

        buy_dto = BuyDTO(
            buyer_id=user.id,
            total_price=total_price,
            discount=0.0,
            shipping_address=None,
            shipping_option_id=None,
            status=BuyStatus.COMPLETED
        )
        buy_dto = await BuyRepository.create(buy_dto, session)

        buy_item_dto = BuyItemDTO(
            buy_id=buy_dto.id,
            item_ids=[it.id for it in purchased_items]
        )
        await BuyItemRepository.create_single(buy_item_dto, session)

        await session_commit(session)

        try:
            await NotificationService.new_buy(buy_dto, user, session)
        except Exception as err:
            logger.error(f'Error notifying admin: {err}')

        # GIAO HÀNG TRỰC TIẾP CHO KHÁCH
        remaining_balance = max(0.0, (getattr(user, 'top_up_amount', 0.0) or 0.0) - (getattr(user, 'consume_records', 0.0) or 0.0))
        cat_name = category.name if category else 'Facebook'
        subcat_name = subcategory.name if subcategory else 'Clone'

        formatted_items = []
        for idx, it in enumerate(purchased_items, start=1):
            uid = extract_uid(it.private_data)
            if uid:
                formatted_items.append(f'📦 <b>Clone #{idx}</b> [UID: <code>{uid}</code> | LIVE ✅]\n<code>{it.private_data}</code>')
            else:
                formatted_items.append(f'📦 <b>Tài khoản #{idx}</b>\n<code>{it.private_data}</code>')

        items_block = '\n\n'.join(formatted_items)

        kb_builder = InlineKeyboardBuilder()
        btn_view_map = {
            Language.VI: f'📦 Xem đơn hàng #{buy_dto.id}',
            Language.ZH: f'📦 查看订单 #{buy_dto.id}',
            Language.HI: f'📦 ऑर्डर #{buy_dto.id} देखें',
            Language.FR: f'📦 Voir commande #{buy_dto.id}',
            Language.DE: f'📦 Bestellung #{buy_dto.id} ansehen',
            Language.IT: f'📦 Visualizza ordine #{buy_dto.id}',
            Language.ES: f'📦 Ver pedido #{buy_dto.id}'
        }
        btn_more_map = {
            Language.VI: '🛒 Mua tiếp tài khoản khác',
            Language.ZH: '🛒 继续购买其他商品',
            Language.HI: '🛒 और खाते खरीदें',
            Language.FR: '🛒 Acheter d\'autres comptes',
            Language.DE: '🛒 Weitere Konten kaufen',
            Language.IT: '🛒 Acquista altri account',
            Language.ES: '🛒 Comprar más cuentas'
        }
        btn_policy_map = {
            Language.VI: '🛡️ Chính sách bảo hành & Miễn trừ',
            Language.ZH: '🛡️ 售后保障与条款',
            Language.HI: '🛡️ वारंटी नीति और नियम',
            Language.FR: '🛡️ Politique de garantie',
            Language.DE: '🛡️ Garantie & Richtlinien',
            Language.IT: '🛡️ Politica di garanzia',
            Language.ES: '🛡️ Política de garantía'
        }
        btn_supp_map = {
            Language.VI: '💬 Hỗ trợ Admin (@truongdvfb)',
            Language.ZH: '💬 客服支持 (@truongdvfb)',
            Language.HI: '💬 एडमिन सपोर्ट (@truongdvfb)',
            Language.FR: '💬 Support Admin (@truongdvfb)',
            Language.DE: '💬 Admin-Support (@truongdvfb)',
            Language.IT: '💬 Supporto Admin (@truongdvfb)',
            Language.ES: '💬 Soporte Admin (@truongdvfb)'
        }
        btn_view = btn_view_map.get(language, f'📦 View Order #{buy_dto.id}')
        btn_more = btn_more_map.get(language, '🛒 Buy More Accounts')
        btn_policy = btn_policy_map.get(language, '🛡️ Warranty Policy & Legal')
        btn_supp = btn_supp_map.get(language, '💬 Admin Support (@truongdvfb)')

        headers = {
            Language.VI: (
                f'🎉 <b>MUA HÀNG THÀNH CÔNG!</b>\n\n'
                f'🧾 <b>Mã đơn hàng:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>Danh mục:</b> <code>{cat_name}</code>\n'
                f'📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>Số lượng:</b> <code>{len(purchased_items)}</code> nick\n'
                f'💰 <b>Tổng thanh toán:</b> <code>{total_price:.2f} {sym}</code> (Đã trừ ví)\n'
                f'💳 <b>Số dư ví còn lại:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.ZH: (
                f'🎉 <b>购买成功！</b>\n\n'
                f'🧾 <b>订单编号:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>商品分类:</b> <code>{cat_name}</code>\n'
                f'📦 <b>账号类型:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>购买数量:</b> <code>{len(purchased_items)}</code> 个\n'
                f'💰 <b>实付金额:</b> <code>{total_price:.2f} {sym}</code> (已从余额扣除)\n'
                f'💳 <b>剩余钱包余额:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.HI: (
                f'🎉 <b>खरीद सफल!</b>\n\n'
                f'🧾 <b>ऑर्डर आईडी:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>श्रेणी:</b> <code>{cat_name}</code>\n'
                f'📦 <b>खाता प्रकार:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>मात्रा:</b> <code>{len(purchased_items)}</code>\n'
                f'💰 <b>कुल भुगतान:</b> <code>{total_price:.2f} {sym}</code> (वॉलेट से काटा गया)\n'
                f'💳 <b>शेष राशि:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.FR: (
                f'🎉 <b>ACHAT RÉUSSI !</b>\n\n'
                f'🧾 <b>ID commande :</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>Catégorie :</b> <code>{cat_name}</code>\n'
                f'📦 <b>Compte :</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>Quantité :</b> <code>{len(purchased_items)}</code> pcs\n'
                f'💰 <b>Total payé :</b> <code>{total_price:.2f} {sym}</code> (Déduit du solde)\n'
                f'💳 <b>Solde restant :</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.DE: (
                f'🎉 <b>KAUF ERFOLGREICH!</b>\n\n'
                f'🧾 <b>Bestell-ID:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>Kategorie:</b> <code>{cat_name}</code>\n'
                f'📦 <b>Konto:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>Menge:</b> <code>{len(purchased_items)}</code> Stk.\n'
                f'💰 <b>Bezahlt:</b> <code>{total_price:.2f} {sym}</code> (Vom Wallet abgebucht)\n'
                f'💳 <b>Restguthaben:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.IT: (
                f'🎉 <b>ACQUISTO COMPLETATO!</b>\n\n'
                f'🧾 <b>ID Ordine:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>Categoria:</b> <code>{cat_name}</code>\n'
                f'📦 <b>Account:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>Quantità:</b> <code>{len(purchased_items)}</code> pz\n'
                f'💰 <b>Totale pagato:</b> <code>{total_price:.2f} {sym}</code> (Scalato dal saldo)\n'
                f'💳 <b>Saldo residuo:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            ),
            Language.ES: (
                f'🎉 <b>¡COMPRA EXITOSA!</b>\n\n'
                f'🧾 <b>ID Pedido:</b> <code>#{buy_dto.id}</code>\n'
                f'📁 <b>Categoría:</b> <code>{cat_name}</code>\n'
                f'📦 <b>Cuenta:</b> <code>{subcat_name}</code>\n'
                f'🔢 <b>Cantidad:</b> <code>{len(purchased_items)}</code> uds\n'
                f'💰 <b>Total pagado:</b> <code>{total_price:.2f} {sym}</code> (Debitado de billetera)\n'
                f'💳 <b>Saldo restante:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
            )
        }
        success_header = headers.get(language, (
            f'🎉 <b>PURCHASE SUCCESSFUL!</b>\n\n'
            f'🧾 <b>Order ID:</b> <code>#{buy_dto.id}</code>\n'
            f'📁 <b>Category:</b> <code>{cat_name}</code>\n'
            f'📦 <b>Account:</b> <code>{subcat_name}</code>\n'
            f'🔢 <b>Quantity:</b> <code>{len(purchased_items)}</code> pcs\n'
            f'💰 <b>Total Paid:</b> <code>{total_price:.2f} {sym}</code> (Debited from wallet)\n'
            f'💳 <b>Remaining Balance:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
        ))

        acc_headers = {
            Language.VI: '📦 <b>DANH SÁCH TÀI KHOẢN CỦA BẠN:</b>',
            Language.ZH: '📦 <b>您的账号列表：</b>',
            Language.HI: '📦 <b>आपके खातों की सूची:</b>',
            Language.FR: '📦 <b>VOS COMPTES :</b>',
            Language.DE: '📦 <b>IHRE KONTEN:</b>',
            Language.IT: '📦 <b>I TUOI ACCOUNT:</b>',
            Language.ES: '📦 <b>TUS CUENTAS:</b>'
        }
        acc_hdr = acc_headers.get(language, '📦 <b>YOUR ACCOUNTS:</b>')

        policy_footers = {
            Language.VI: '🛡️ <b>Bảo hành:</b> 24h lỗi 1 đổi 1. Điều khoản: /policy. Hỗ trợ: @truongdvfb',
            Language.ZH: '🛡️ <b>售后保证:</b> 24小时内首登问题1换1。条款: /policy。客服: @truongdvfb',
            Language.HI: '🛡️ <b>वारंटी:</b> 24 घंटे में प्रतिस्थापन। नियम: /policy। सहायता: @truongdvfb',
            Language.FR: '🛡️ <b>Garantie :</b> Remplacement 1 pour 1 en 24h. Politique : /policy. Support : @truongdvfb',
            Language.DE: '🛡️ <b>Garantie:</b> 24h 1-zu-1 Ersatz. Richtlinien: /policy. Support: @truongdvfb',
            Language.IT: '🛡️ <b>Garanzia:</b> Sostituzione 1 a 1 entro 24h. Termini: /policy. Supporto: @truongdvfb',
            Language.ES: '🛡️ <b>Garantía:</b> Reemplazo 1 a 1 en 24h. Términos: /policy. Soporte: @truongdvfb'
        }
        policy_foot = policy_footers.get(language, '🛡️ <b>Warranty:</b> 24h 1-to-1 replacement. Policy: /policy. Support: @truongdvfb')

        full_text = (
            success_header +
            f'━━━━━━━━━━━━━━━━━━\n'
            f'{acc_hdr}\n'
            f'{items_block}\n'
            f'━━━━━━━━━━━━━━━━━━\n'
            f'{policy_foot}\n'
        )
        kb_builder.button(text=btn_view, callback_data=MyProfileCallback.create(level=4, buy_id=buy_dto.id))
        kb_builder.button(text=btn_more, callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL))
        kb_builder.button(text=btn_policy, callback_data='view_full_policy')
        kb_builder.button(text=btn_supp, url=getattr(config, "SUPPORT_LINK", "https://t.me/truongdvfb") or "https://t.me/truongdvfb")
        kb_builder.adjust(1)

        file_content = '\n'.join(it.private_data for it in purchased_items if it.private_data)
        file_doc = BufferedInputFile(
            file_content.encode('utf-8'),
            filename=f'DonHang_{buy_dto.id}_{len(purchased_items)}acc.txt'
        )

        if len(purchased_items) <= 2 and len(full_text) <= 3500:
            await _send_or_edit_text(callback, full_text, kb_builder.as_markup())
            try:
                await callback.message.answer_document(
                    document=file_doc,
                    caption=f'📄 <i>File .txt lưu {len(purchased_items)} tài khoản cho đơn hàng #{buy_dto.id}.</i>',
                    parse_mode='HTML'
                )
            except Exception as f_err:
                logger.warning(f'Could not send attached doc: {f_err}')
        else:
            doc_caption = (
                success_header +
                f'━━━━━━━━━━━━━━━━━━\n'
                f'📄 <i>Toàn bộ <b>{len(purchased_items)} tài khoản</b> đã được lưu trong file .txt đính kèm bên dưới để bạn tải về nhập trực tiếp vào tool (FPlus, MaxCare...).</i>\n\n'
                f'🛡️ <b>Bảo hành:</b> 24h lỗi 1 đổi 1. Điều khoản & Miễn trừ: /policy. Hỗ trợ Admin: @truongdvfb'
            )
            if len(doc_caption) > 1000:
                doc_caption = doc_caption[:990] + '...'
            try:
                await callback.message.delete()
            except Exception:
                pass

            try:
                await callback.message.answer_document(
                    document=file_doc,
                    caption=doc_caption,
                    reply_markup=kb_builder.as_markup(),
                    parse_mode='HTML'
                )
            except Exception as doc_err:
                logger.error(f'Error sending document: {doc_err}', exc_info=True)
                fallback_text = (
                    success_header +
                    f'━━━━━━━━━━━━━━━━━━\n'
                    f'<code>{file_content[:3000]}</code>\n'
                    f'━━━━━━━━━━━━━━━━━━\n'
                    f'🛡️ <b>Bảo hành:</b> 24h lỗi 1 đổi 1. Điều khoản & Miễn trừ: /policy. Hỗ trợ Admin: @truongdvfb'
                )
                await callback.message.answer(
                    text=fallback_text,
                    reply_markup=kb_builder.as_markup(),
                    parse_mode='HTML'
                )

    except Exception as exc:
        logger.error(f'Critical error in execute_instant_buy: {exc}', exc_info=True)
        try:
            await callback.answer(f'❌ Lỗi xử lý: {str(exc)[:100]}', show_alert=True)
        except Exception:
            pass
        try:
            await callback.message.answer(
                f'❌ <b>Có lỗi xảy ra khi xử lý đơn hàng!</b>\n\n'
                f'Chi tiết: <code>{str(exc)}</code>\n\n'
                f'Vui lòng liên hệ Admin <b>@truongdvfb</b> để được hỗ trợ kiểm tra tài khoản và hoàn tiền nếu có sự cố.',
                parse_mode='HTML'
            )
        except Exception:
            pass


def parse_entity_type(raw) -> EntityType:
    if isinstance(raw, EntityType):
        return raw
    if isinstance(raw, int):
        try:
            return EntityType(raw)
        except Exception:
            pass
    if isinstance(raw, str):
        if raw.isdigit():
            try:
                return EntityType(int(raw))
            except Exception:
                pass
        name = raw.upper()
        if hasattr(EntityType, name):
            return EntityType[name]
    return EntityType.CATEGORY


async def execute_global_search(target: Message | CallbackQuery, query: str, session: AsyncSession, language: Language = Language.VI):
    from sqlalchemy import select, func
    from aiogram.types import InlineKeyboardButton
    from models.category import Category
    from models.subcategory import Subcategory
    from models.item import Item

    clean_query = query.strip()
    stmt_cat = select(Category).where(Category.name.ilike(f"%{clean_query}%"))
    categories = (await session.execute(stmt_cat)).scalars().all()

    stmt_sub = select(Subcategory).where(Subcategory.name.ilike(f"%{clean_query}%"))
    subcategories = (await session.execute(stmt_sub)).scalars().all()

    kb_builder = InlineKeyboardBuilder()

    if subcategories or categories:
        for sub in subcategories[:10]:
            stmt_cat_id = select(Item.category_id).where(Item.subcategory_id == sub.id).limit(1)
            cat_id = (await session.execute(stmt_cat_id)).scalar_one_or_none() or 1

            stmt_cnt = select(func.count(Item.id)).where(Item.subcategory_id == sub.id, Item.is_sold == False)
            avail_cnt = (await session.execute(stmt_cnt)).scalar() or 0

            btn_text = f"🛒 {sub.name} - ${sub.price or 0.02:g} ({avail_cnt} nick)"
            cb = AllCategoriesCallback.create(level=3, category_id=cat_id, subcategory_id=sub.id, item_type=ItemType.DIGITAL)
            kb_builder.button(text=btn_text, callback_data=cb.pack())

        for cat in categories[:4]:
            cb = AllCategoriesCallback.create(level=2, category_id=cat.id, item_type=ItemType.DIGITAL)
            kb_builder.button(text=f"📁 {cat.name}", callback_data=cb.pack())

        kb_builder.adjust(1)
        from services.i18n_messages import get_search_results_text
        msg_text, btn_all = get_search_results_text(language, clean_query, found=True)
        cb_all = AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
        kb_builder.row(InlineKeyboardButton(text=btn_all, callback_data=cb_all.pack()))
    else:
        from services.i18n_messages import get_search_results_text
        msg_text, btn_all = get_search_results_text(language, clean_query, found=False)
        cb_all = AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
        kb_builder.button(text=btn_all, callback_data=cb_all.pack())
        kb_builder.adjust(1)

    await _send_or_edit_text(target, msg_text, kb_builder.as_markup())


@all_categories_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_items))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    filter_val = (message.text or "").strip()
    if filter_val.startswith("/") or any(k in filter_val for k in ["Sản phẩm", "Đơn hàng", "Ví", "Hỗ trợ", "Products", "Orders", "Wallet"]):
        await state.clear()
        return

    await state.clear()
    await execute_global_search(message, filter_val, session, language)


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(callback: CallbackQuery,
                              callback_data: AllCategoriesCallback,
                              session: AsyncSession,
                              state: FSMContext,
                              language: Language):
    try:
        await callback.answer()
    except Exception:
        pass

    current_level = callback_data.level

    levels = {
        0: all_types,
        1: all_categories,
        2: show_subcategories_in_category,
        3: select_quantity,
        4: instant_buy_confirmation,
        5: execute_instant_buy
    }

    current_level_function = levels.get(current_level, all_categories)

    kwargs = {
        'callback': callback,
        'session': session,
        'callback_data': callback_data,
        'state': state,
        'language': language
    }

    await current_level_function(**kwargs)
