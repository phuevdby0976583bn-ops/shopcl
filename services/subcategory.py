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
from services.i18n_messages import get_out_of_stock_text, get_select_quantity_text, get_instant_buy_confirm_text, get_all_qty_label
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
        from models.item import Item
        from sqlalchemy import select, func
        sold_map = {}
        if sub_ids:
            stmt_sold = (
                select(Item.subcategory_id, func.count(Item.id))
                .where(Item.subcategory_id.in_(sub_ids), Item.is_sold == True)
                .group_by(Item.subcategory_id)
            )
            sold_res = await session.execute(stmt_sold)
            sold_map = {row[0]: int(row[1]) for row in sold_res.all()}
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
                sold_quantity=sold_map.get(item.subcategory_id, 0),
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
            out_of_stock_caption = get_out_of_stock_text(language, category_dto.name, subcategory_dto.name)
            kb_builder.row(callback_data.get_back_button(language, lvl=2))
            media = MediaService.convert_to_media(subcategory_dto.media_id, out_of_stock_caption)
            return media, kb_builder

        sym = _sym()
        if callback_data.item_type:
            item_type = callback_data.item_type.get_localized(language)
        else:
            item_type = get_text(language, BotEntity.COMMON, 'all')

        desc = getattr(item_dto, 'description', '') or getattr(subcategory_dto, 'description', '') or ''
        caption = get_select_quantity_text(language, category_dto.name, subcategory_dto.name, item_dto.price, sym, desc, available_qty)

        if available_qty <= 10:
            options = list(range(1, available_qty + 1))
        else:
            candidates = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
            options = [c for c in candidates if c <= available_qty]
            if available_qty not in options and available_qty <= 500:
                options.append(available_qty)

        for qty in options:
            btn_text = get_all_qty_label(language, qty) if (qty == available_qty and qty > 10) else str(qty)
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

        message_text, labels = get_instant_buy_confirm_text(
            language=language,
            cat_name=category.name if category else "",
            subcat_name=subcategory.name if subcategory else "",
            unit_price=unit_price,
            qty=qty,
            total_price=total_price,
            sym=sym,
            balance=user_balance,
            is_enough=is_enough,
            missing=missing
        )

        kb_builder = InlineKeyboardBuilder()
        if is_enough:
            kb_builder.button(
                text=labels["buy"],
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
                text=labels["back_qty"],
                callback_data=AllCategoriesCallback.create(
                    level=3,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id
                )
            )
            kb_builder.button(
                text=labels["cancel"],
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id
                )
            )
            kb_builder.adjust(1, 2)
        else:
            kb_builder.button(text=labels["binance"], callback_data='binance_pay:view')
            kb_builder.button(text=labels["bank"], callback_data='dep_method:bank')
            kb_builder.button(text=labels["crypto"], callback_data='deposit:start')
            kb_builder.button(
                text=labels["back_qty"],
                callback_data=AllCategoriesCallback.create(
                    level=3,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id,
                    subcategory_id=callback_data.subcategory_id
                )
            )
            kb_builder.button(
                text=labels["cancel"],
                callback_data=AllCategoriesCallback.create(
                    level=2,
                    item_type=callback_data.item_type,
                    category_id=callback_data.category_id
                )
            )
            kb_builder.adjust(1, 1, 1, 2)

        return message_text, kb_builder

    @staticmethod
    async def get_add_to_cart_buttons(callback_data: AllCategoriesCallback,
                                      session: AsyncSession | Session,
                                      language: Language) -> tuple[str, InlineKeyboardBuilder]:
        return await SubcategoryService.get_instant_buy_confirmation(callback_data, None, session, language)
