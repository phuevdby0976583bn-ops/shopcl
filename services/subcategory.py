from typing import Any
from aiogram.fsm.context import FSMContext
from aiogram.types import InputMediaVideo, InputMediaAnimation, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import config
from callbacks import AllCategoriesCallback
from enums.bot_entity import BotEntity
from enums.entity_type import EntityType
from enums.language import Language
from enums.sort_property import SortProperty
from handlers.common.common import add_pagination_buttons, add_sorting_buttons, get_filters_settings, add_search_button
from repositories.category import CategoryRepository
from repositories.item import ItemRepository
from repositories.subcategory import SubcategoryRepository
from services.media import MediaService
from utils.utils import get_text
from services.i18n_messages import get_out_of_stock_text, get_select_quantity_text, get_instant_buy_confirm_text
from utils.utils import get_bot_photo_id


def _sym() -> str:
    return 'USDT' if getattr(config, 'ONLY_USDT_MODE', False) else config.CURRENCY.get_localized_symbol()


class SubcategoryService:

    @staticmethod
    async def get_buttons(callback_data: AllCategoriesCallback | None,
                          state: FSMContext,
                          session: AsyncSession,
                          language: Language) -> tuple[InputMediaPhoto |
                                                       InputMediaAnimation |
                                                       InputMediaVideo, InlineKeyboardBuilder]:
        state_data = await state.get_data()
        callback_data = callback_data or AllCategoriesCallback.create(2, **(state_data.get('entity_id_dict') or {}))
        sort_pairs, filters = await get_filters_settings(state, callback_data)
        kb_builder = InlineKeyboardBuilder()
        items = await SubcategoryRepository.get_paginated_by_category_id(sort_pairs, filters,
                                                                         callback_data.item_type,
                                                                         callback_data.category_id,
                                                                         callback_data.page, session)
        sub_ids = [item.subcategory_id for item in items]
        qty_map = await ItemRepository.get_available_qty_map(sub_ids, session)
        for item in items:
            if item.subcategory_id in qty_map:
                available_qty = qty_map[item.subcategory_id]
            else:
                available_qty = await ItemRepository.get_available_qty(item_type=item.item_type,
                                                                       category_id=item.category_id,
                                                                       subcategory_id=item.subcategory_id,
                                                                       session=session)
            kb_builder.button(text=get_text(language, BotEntity.USER, 'subcategory_button').format(
                subcategory_name=item.subcategory_name,
                subcategory_price=item.price,
                available_quantity=available_qty,
                currency_sym=_sym()),
                callback_data=AllCategoriesCallback.create(
                    level=callback_data.level + 1,
                    item_type=item.item_type,
                    category_id=item.category_id,
                    subcategory_id=item.subcategory_id
                )
            )
        kb_builder.adjust(1)
        kb_builder = await add_search_button(kb_builder, EntityType.SUBCATEGORY, callback_data, filters, language)
        kb_builder = await add_sorting_buttons(kb_builder, [SortProperty.NAME, SortProperty.PRICE],
                                               callback_data, sort_pairs, language)
        kb_builder = await add_pagination_buttons(kb_builder, callback_data,
                                                  SubcategoryRepository.get_maximum_page(callback_data.category_id,
                                                                                         filters, session),
                                                  callback_data.get_back_button(language), language)
        caption = get_text(language, BotEntity.USER, 'pick_subcategory')
        if callback_data.item_type:
            item_type = callback_data.item_type.get_localized(language)
        else:
            item_type = get_text(language, BotEntity.COMMON, 'all')
        if callback_data.category_id:
            try:
                category_dto = await CategoryRepository.get_by_id(callback_data.category_id, session)
            except Exception:
                category_dto = None
            if category_dto:
                caption = caption.format(
                    category_name=category_dto.name,
                    item_type=item_type
                )
                media = MediaService.convert_to_media(category_dto.media_id, caption)
            else:
                caption = caption.format(
                    category_name=get_text(language, BotEntity.COMMON, 'all'),
                    item_type=item_type
                )
                media = InputMediaPhoto(media=get_bot_photo_id(), caption=caption)
        else:
            caption = caption.format(
                category_name=get_text(language, BotEntity.COMMON, 'all'),
                item_type=item_type
            )
            media = InputMediaPhoto(media=get_bot_photo_id(), caption=caption)
        return media, kb_builder

    @staticmethod
    async def get_select_quantity_buttons(callback_data: AllCategoriesCallback,
                                          session: AsyncSession,
                                          language: Language) -> tuple[InputMediaPhoto |
                                                                       InputMediaAnimation |
                                                                       InputMediaVideo, InlineKeyboardBuilder]:
        if not getattr(callback_data, "category_id", None) and getattr(callback_data, "subcategory_id", None):
            from models.item import Item
            from sqlalchemy import select
            stmt_item = select(Item.category_id).where(Item.subcategory_id == callback_data.subcategory_id).limit(1)
            found_cat_id = (await session.execute(stmt_item)).scalar_one_or_none()
            callback_data.category_id = found_cat_id or 1

        item_dto = await ItemRepository.get_single(callback_data.item_type, callback_data.category_id,
                                                   callback_data.subcategory_id, session)
        subcategory_dto = await SubcategoryRepository.get_by_id(callback_data.subcategory_id, session)
        category_dto = await CategoryRepository.get_by_id(callback_data.category_id, session)
        if not category_dto:
            from models.category import CategoryDTO
            category_dto = CategoryDTO(id=1, name="Sản phẩm")
        available_qty = await ItemRepository.get_available_qty(item_type=callback_data.item_type,
                                                               category_id=callback_data.category_id,
                                                               subcategory_id=callback_data.subcategory_id,
                                                               session=session)
        kb_builder = InlineKeyboardBuilder()

        if available_qty <= 0:
            if language == Language.VI:
                out_of_stock_caption = (
                    f'📁 <b>Danh mục:</b> <code>{category_dto.name}</code>\n'
                    f'📦 <b>Loại tài khoản:</b> <code>{subcategory_dto.name}</code>\n\n'
                    f'❌ <b>Tạm thời hết hàng!</b>\n'
                    f'Kho hiện tại đã bán hết loại tài khoản này. Vui lòng chọn loại tài khoản khác hoặc liên hệ Admin @truongdvfb để được hỗ trợ nhập thêm hàng.'
                )
            else:
                out_of_stock_caption = (
                    f'📁 <b>Category:</b> <code>{category_dto.name}</code>\n'
                    f'📦 <b>Account:</b> <code>{subcategory_dto.name}</code>\n\n'
                    f'❌ <b>Out of stock!</b>\n'
                    f'This account type is currently out of stock. Please select another product or contact Admin @truongdvfb.'
                )
            kb_builder.row(callback_data.get_back_button(language, lvl=2))
            media = MediaService.convert_to_media(subcategory_dto.media_id, out_of_stock_caption)
            return media, kb_builder

        sym = _sym()
        if callback_data.item_type:
            item_type = callback_data.item_type.get_localized(language)
        else:
            item_type = get_text(language, BotEntity.COMMON, 'all')

        if language == Language.VI:
            caption = (
                f'📁 <b>Danh mục:</b> <code>{category_dto.name}</code>\n'
                f'📦 <b>Loại tài khoản:</b> <code>{subcategory_dto.name}</code>\n'
                f'💸 <b>Giá bán:</b> <code>{item_dto.price:.2f} {sym}</code> / nick\n'
                f'✍️ <b>Mô tả:</b> <i>{item_dto.description}</i>\n'
                f'🔢 <b>Số lượng có sẵn:</b> <code>{available_qty}</code> cái\n\n'
                f'🔢 <b>Vui lòng chọn số lượng cần mua:</b>'
            )
        else:
            caption = (
                f'📁 <b>Category:</b> <code>{category_dto.name}</code>\n'
                f'📦 <b>Account:</b> <code>{subcategory_dto.name}</code>\n'
                f'💸 <b>Price:</b> <code>{item_dto.price:.2f} {sym}</code> / acc\n'
                f'✍️ <b>Description:</b> <i>{item_dto.description}</i>\n'
                f'🔢 <b>In stock:</b> <code>{available_qty}</code> pcs\n\n'
                f'🔢 <b>Select quantity to buy:</b>'
            )

        if available_qty <= 10:
            options = list(range(1, available_qty + 1))
        else:
            candidates = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
            options = [c for c in candidates if c <= available_qty]
            if available_qty not in options and available_qty <= 500:
                options.append(available_qty)

        for qty in options:
            btn_text = f'Tất cả ({qty})' if (qty == available_qty and qty > 10 and language == Language.VI) else (f'All ({qty})' if (qty == available_qty and qty > 10) else str(qty))
            kb_builder.button(text=btn_text, callback_data=AllCategoriesCallback.create(
                level=callback_data.level + 1,
                item_type=item_dto.item_type,
                category_id=item_dto.category_id,
                subcategory_id=item_dto.subcategory_id,
                quantity=qty
            ))
        kb_builder.adjust(3)
        kb_builder.row(callback_data.get_back_button(language, lvl=2))
        media = MediaService.convert_to_media(subcategory_dto.media_id, caption)
        return media, kb_builder

    @staticmethod
    async def get_instant_buy_confirmation(callback_data: AllCategoriesCallback,
                                           user: Any,
                                           session: AsyncSession | Session,
                                           language: Language) -> tuple[str, InlineKeyboardBuilder]:
        item = await ItemRepository.get_single(callback_data.item_type, callback_data.category_id,
                                               callback_data.subcategory_id, session)
        category = await CategoryRepository.get_by_id(callback_data.category_id, session)
        subcategory = await SubcategoryRepository.get_by_id(callback_data.subcategory_id, session)
        qty = callback_data.quantity or 1
        unit_price = (getattr(subcategory, 'price', None) or (getattr(item, 'price', 0.0) if item else 0.0)) or 0.0
        total_price = unit_price * qty
        sym = _sym()

        user_balance = max(0.0, (getattr(user, 'top_up_amount', 0.0) or 0.0) - (getattr(user, 'consume_records', 0.0) or 0.0))
        is_enough = user_balance >= total_price
        missing = max(0.0, total_price - user_balance)

        if language == Language.VI:
            status_text = (
                f'✅ <b>Số dư ví đủ thanh toán. Bấm \'MUA NGAY\' bên dưới để nhận tài khoản tức thì!</b>'
                if is_enough
                else f'⚠️ <b>Số dư ví không đủ! Còn thiếu: <code>{missing:.2f} {sym}</code>. Vui lòng nạp tiền vào ví trước khi mua.</b>'
            )
            message_text = (
                f'⚡ <b>XÁC NHẬN MUA TÀI KHOẢN (TRỪ TIỀN TRỰC TIẾP)</b>\n\n'
                f'📁 <b>Danh mục:</b> <code>{category.name}</code>\n'
                f'📦 <b>Loại tài khoản:</b> <code>{subcategory.name}</code>\n'
                f'💸 <b>Đơn giá:</b> <code>{unit_price:.2f} {sym}</code> / nick\n'
                f'🔢 <b>Số lượng mua:</b> <code>{qty}</code> nick\n'
                f'💰 <b>TỔNG THANH TOÁN:</b> <code>{total_price:.2f} {sym}</code>\n\n'
                f'💳 <b>Số dư ví hiện tại:</b> <code>{user_balance:.2f} {sym}</code>\n'
                f'{status_text}\n\n'
                f'⚡ <i>Lưu ý: Hệ thống tự động Check Live UID Facebook qua Graph API ngay khi giao hàng, cam kết 100% clone Live!</i>'
            )
        else:
            status_text = (
                f'✅ <b>Sufficient balance. Click \'BUY NOW\' below to receive accounts immediately!</b>'
                if is_enough
                else f'⚠️ <b>Insufficient balance! Missing: <code>{missing:.2f} {sym}</code>. Please top up your wallet.</b>'
            )
            message_text = (
                f'⚡ <b>INSTANT PURCHASE CONFIRMATION</b>\n\n'
                f'📁 <b>Category:</b> <code>{category.name}</code>\n'
                f'📦 <b>Account:</b> <code>{subcategory.name}</code>\n'
                f'💸 <b>Unit Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n'
                f'🔢 <b>Quantity:</b> <code>{qty}</code> pcs\n'
                f'💰 <b>TOTAL AMOUNT:</b> <code>{total_price:.2f} {sym}</code>\n\n'
                f'💳 <b>Wallet Balance:</b> <code>{user_balance:.2f} {sym}</code>\n'
                f'{status_text}\n\n'
                f'⚡ <i>Note: Live Facebook UIDs are automatically verified via Graph API upon delivery!</i>'
            )

        kb_builder = InlineKeyboardBuilder()
        if is_enough:
            confirm_label = f'⚡ MUA NGAY ({total_price:.2f} {sym})' if language == Language.VI else f'⚡ BUY NOW ({total_price:.2f} {sym})'
            back_qty_label = '⬅️ Chọn lại số lượng' if language == Language.VI else '⬅️ Change quantity'
            cancel_label = '❌ Hủy bỏ' if language == Language.VI else '❌ Cancel'

            kb_builder.button(
                text=confirm_label,
                callback_data=AllCategoriesCallback.create(
                    level=5,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id,
                    quantity=qty,
                    confirmation=True
                )
            )
            kb_builder.button(
                text=back_qty_label,
                callback_data=AllCategoriesCallback.create(
                    level=3,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id
                )
            )
            kb_builder.button(
                text=cancel_label,
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id
                )
            )
            kb_builder.adjust(1, 2)
        else:
            binance_label = f'🟡 Nạp Binance Pay (0% Phí - Nhận ngay 1s)' if language == Language.VI else f'🟡 Deposit Binance Pay (0% Fee)'
            crypto_label = '💳 Cổng Nạp On-chain Crypto' if language == Language.VI else '💳 Deposit On-chain Crypto'
            back_qty_label = '⬅️ Chọn lại số lượng' if language == Language.VI else '⬅️ Change quantity'
            cancel_label = '❌ Hủy bỏ' if language == Language.VI else '❌ Cancel'

            kb_builder.button(text=binance_label, callback_data='binance_pay:view')
            kb_builder.button(text=crypto_label, callback_data='deposit:start')
            kb_builder.button(
                text=back_qty_label,
                callback_data=AllCategoriesCallback.create(
                    level=3,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id
                )
            )
            kb_builder.button(
                text=cancel_label,
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id
                )
            )
            kb_builder.adjust(1, 1, 2)

        return message_text, kb_builder

    @staticmethod
    async def get_add_to_cart_buttons(callback_data: AllCategoriesCallback,
                                      session: AsyncSession | Session,
                                      language: Language) -> tuple[str, InlineKeyboardBuilder]:
        return await SubcategoryService.get_instant_buy_confirmation(callback_data, None, session, language)
