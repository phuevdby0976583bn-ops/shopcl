import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
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
        return await target.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
    else:
        callback = target
        if callback.message.caption:
            try:
                await callback.message.delete()
            except Exception:
                pass
            return await callback.message.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
        else:
            try:
                return await callback.message.edit_text(text=text_content, reply_markup=reply_markup, parse_mode='HTML')
            except Exception:
                return await callback.message.answer(text=text_content, reply_markup=reply_markup, parse_mode='HTML')


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
    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    msg, kb_builder = await SubcategoryService.get_instant_buy_confirmation(callback_data, user, session, language)
    await _send_or_edit_text(callback, msg, kb_builder.as_markup())


async def execute_instant_buy(**kwargs):
    callback: CallbackQuery = kwargs.get('callback')
    callback_data: AllCategoriesCallback = kwargs.get('callback_data')
    session: AsyncSession = kwargs.get('session')
    language: Language = kwargs.get('language')

    if not callback_data.confirmation:
        return await show_subcategories_in_category(**kwargs)

    user = await UserRepository.get_by_tgid(callback.from_user.id, session)
    if not user:
        return await callback.answer('Vui lòng gõ /start để khởi tạo tài khoản!', show_alert=True)

    item = await ItemRepository.get_single(
        callback_data.item_type, callback_data.category_id, callback_data.subcategory_id, session
    )
    if not item:
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text='📁 Xem sản phẩm khác', callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL))
        return await _send_or_edit_text(callback, '❌ <b>Sản phẩm này không còn tồn tại hoặc đã bị xóa.</b>', kb_builder.as_markup())

    qty = callback_data.quantity or 1
    total_price = item.price * qty
    user_balance = max(0.0, (user.top_up_amount or 0.0) - (user.consume_records or 0.0))
    sym = _sym()

    # Kiểm tra số dư ví
    if user_balance < total_price:
        missing = total_price - user_balance
        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(text=f'🟡 Nạp Binance Pay (0% Phí - Nhận ngay 1s)', callback_data='binance_pay:view')
        kb_builder.button(text='💳 Cổng Nạp On-chain Crypto', callback_data='deposit:start')
        kb_builder.button(
            text='⬅️ Chọn lại số lượng',
            callback_data=AllCategoriesCallback.create(
                level=3,
                item_type=callback_data.item_type,
                category_id=callback_data.category_id,
                subcategory_id=callback_data.subcategory_id
            )
        )
        kb_builder.adjust(1, 1, 1)
        insufficient_msg = (
            f'❌ <b>Số dư ví không đủ để thanh toán!</b>\n\n'
            f'💰 <b>Cần thanh toán:</b> <code>{total_price:.2f} {sym}</code>\n'
            f'💳 <b>Số dư hiện tại:</b> <code>{user_balance:.2f} {sym}</code>\n'
            f'⚠️ <b>Còn thiếu:</b> <code>{missing:.2f} {sym}</code>\n\n'
            f'👉 Vui lòng nạp thêm tiền vào tài khoản để nhận clone ngay lập tức!'
        )
        return await _send_or_edit_text(callback, insufficient_msg, kb_builder.as_markup())

    # Lấy thông tin Category & Subcategory
    category = await CategoryRepository.get_by_id(callback_data.category_id, session)
    subcategory = await SubcategoryRepository.get_by_id(callback_data.subcategory_id, session)

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
            await callback.answer('⚡ Đang check Live tài khoản Facebook qua Graph API...', show_alert=False)
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
            subcat_name = subcategory.name if subcategory else 'Facebook Clone'
            msg = (
                f'❌ <b>Kho không đủ tài khoản LIVE!</b>\n\n'
                f'Sản phẩm: <b>{subcat_name}</b>\n'
                f'Số lượng bạn đặt: <b>{qty}</b> tài khoản\n'
                f'Số tài khoản LIVE thực tế còn lại: <b>{len(live_items)}</b>\n\n'
                f'<i>⚡ Bot đã tự động check Live qua Facebook Graph API trước khi giao để đảm bảo bạn luôn nhận được nick LIVE 100%. Các tài khoản DIE đã được tự động loại bỏ. Số dư của bạn chưa bị trừ! Vui lòng đặt mua với số lượng phù hợp.</i>'
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
    remaining_balance = max(0.0, (user.top_up_amount or 0.0) - (user.consume_records or 0.0))

    formatted_items = []
    for idx, it in enumerate(purchased_items, start=1):
        uid = extract_uid(it.private_data)
        if uid:
            formatted_items.append(f'📦 Clone #{idx} [UID: <code>{uid}</code> | LIVE ✅]\n<code>{it.private_data}</code>')
        else:
            formatted_items.append(f'📦 Tài khoản #{idx}\n<code>{it.private_data}</code>')

    items_block = '\n\n'.join(formatted_items)

    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=f'📦 Xem đơn hàng #{buy_dto.id}',
        callback_data=MyProfileCallback.create(level=4, buy_id=buy_dto.id)
    )
    kb_builder.button(
        text='🛒 Mua tiếp tài khoản khác',
        callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    )
    kb_builder.button(
        text=f'💬 Hỗ trợ Admin (@truongdvfb)',
        url=config.SUPPORT_LINK
    )
    kb_builder.adjust(1)

    cat_name = category.name if category else 'Facebook'
    subcat_name = subcategory.name if subcategory else 'Clone'

    success_header = (
        f'🎉 <b>MUA HÀNG THÀNH CÔNG!</b>\n\n'
        f'🧾 <b>Mã đơn hàng:</b> <code>#{buy_dto.id}</code>\n'
        f'📁 <b>Danh mục:</b> <code>{cat_name}</code>\n'
        f'📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n'
        f'🔢 <b>Số lượng:</b> <code>{len(purchased_items)}</code> nick\n'
        f'💰 <b>Tổng thanh toán:</b> <code>{total_price:.2f} {sym}</code> (Đã trừ ví)\n'
        f'💳 <b>Số dư ví còn lại:</b> <code>{remaining_balance:.2f} {sym}</code>\n\n'
        f'━━━━━━━━━━━━━━━━━━━\n'
        f'📦 <b>DANH SÁCH TÀI KHOẢN CỦA BẠN:</b>\n'
    )

    full_text = success_header + items_block + f'\n━━━━━━━━━━━━━━━━━━━\n🛡️ <b>Bảo hành:</b> 24h lỗi 1 đổi 1. Hỗ trợ Admin: @truongdvfb'

    if len(purchased_items) < 3 and len(full_text) <= 3800:
        await _send_or_edit_text(callback, full_text, kb_builder.as_markup())
    else:
        file_content = '\n'.join(it.private_data for it in purchased_items if it.private_data)
        file_doc = BufferedInputFile(file_content.encode('utf-8'), filename=f'DonHang_{buy_dto.id}_{len(purchased_items)}acc.txt')

        preview_items = '\n\n'.join(formatted_items[:3])
        if len(purchased_items) > 3:
            preview_items += f'\n\n<i>... và còn {len(purchased_items) - 3} tài khoản nữa trong file đính kèm bên dưới!</i>'

        short_caption = (
            success_header + preview_items +
            f'\n━━━━━━━━━━━━━━━━━━━\n'
            f'📄 <i>Toàn bộ {len(purchased_items)} tài khoản đã được lưu trong file .txt đính kèm bên dưới để bạn tiện nhập vào tool (FPlus, MaxCare...).</i>\n'
            f'🛡️ <b>Bảo hành:</b> 24h lỗi 1 đổi 1. Hỗ trợ Admin: @truongdvfb'
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_document(
            document=file_doc,
            caption=short_caption,
            reply_markup=kb_builder.as_markup(),
            parse_mode='HTML'
        )


@all_categories_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_items))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    await state.update_data(filter=message.html_text)
    state_data = await state.get_data()
    entity_type = EntityType(state_data['entity_type'])
    if entity_type == EntityType.CATEGORY:
        media, kb_builder = await CategoryService.get_buttons(None, state, session, language)
    else:
        media, kb_builder = await SubcategoryService.get_buttons(None, state, session, language)
    caption = getattr(media, 'caption', '') or '...'
    await _send_or_edit_text(message, caption, kb_builder.as_markup())


@all_categories_router.callback_query(AllCategoriesCallback.filter(), IsUserExistFilter())
async def navigate_categories(callback: CallbackQuery,
                              callback_data: AllCategoriesCallback,
                              session: AsyncSession,
                              state: FSMContext,
                              language: Language):
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
