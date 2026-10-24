from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from callbacks import AllCategoriesCallback
from enums.entity_type import EntityType
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from handlers.common.common import enable_search
from handlers.user.constants import UserStates
from services.cart import CartService
from services.category import CategoryService
from services.item import ItemService
from services.notification import NotificationService
from services.subcategory import SubcategoryService
from utils.custom_filters import IsUserExistFilter

all_categories_router = Router()


async def _send_or_edit_text(target: Message | CallbackQuery, text: str, reply_markup=None):
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


@all_categories_router.message(F.text.in_(KB.get_localized_set(KB.ALL_CATEGORIES)), IsUserExistFilter())
async def all_categories_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    await all_types(callback=message, session=session, state=state, language=language)


async def all_types(**kwargs):
    message: CallbackQuery | Message = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    media, kb_builder = await ItemService.get_all_types(callback_data, session, language)
    caption = getattr(media, "caption", "") or "📦 Chọn danh mục sản phẩm:"
    await _send_or_edit_text(message, caption, kb_builder.as_markup())


async def all_categories(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.CATEGORY,
                                                {"item_type": item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await CategoryService.get_buttons(callback_data, state, session, language)
    caption = getattr(media, "caption", "") or "📦 Danh mục:"
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def show_subcategories_in_category(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    state: FSMContext = kwargs.get("state")
    language: Language = kwargs.get("language")
    state_data = await state.get_data()
    if callback_data.is_filter_enabled and state_data.get('filter') is not None:
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)
    elif callback_data.is_filter_enabled:
        item_type_value = callback_data.item_type.value if callback_data.item_type else None
        media, kb_builder = await enable_search(callback_data,
                                                EntityType.SUBCATEGORY,
                                                {"category_id": callback_data.category_id,
                                                 "item_type": item_type_value},
                                                state,
                                                UserStates.filter_items,
                                                language)
    else:
        await state.update_data(filter=None)
        await state.set_state()
        media, kb_builder = await SubcategoryService.get_buttons(callback_data, state, session, language)
    caption = getattr(media, "caption", "") or "📦 Danh mục con:"
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def select_quantity(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    media, kb_builder = await SubcategoryService.get_select_quantity_buttons(callback_data, session, language)
    caption = getattr(media, "caption", "") or "Chọn số lượng:"
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


async def add_to_cart_confirmation(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    msg, kb_builder = await SubcategoryService.get_add_to_cart_buttons(callback_data, session, language)
    await _send_or_edit_text(callback, msg or "Xác nhận thêm vào giỏ hàng:", kb_builder.as_markup())


async def add_to_cart(**kwargs):
    callback: CallbackQuery = kwargs.get("callback")
    callback_data: AllCategoriesCallback = kwargs.get("callback_data")
    session: AsyncSession = kwargs.get("session")
    language: Language = kwargs.get("language")
    media, kb_builder = await CartService.add_to_cart(callback, callback_data, session, language)
    caption = getattr(media, "caption", "") or "Đã thêm vào giỏ hàng!"
    await _send_or_edit_text(callback, caption, kb_builder.as_markup())


@all_categories_router.message(IsUserExistFilter(), F.text, StateFilter(UserStates.filter_items))
async def receive_filter_message(message: Message, state: FSMContext, session: AsyncSession, language: Language):
    await state.update_data(filter=message.html_text)
    state_data = await state.get_data()
    entity_type = EntityType(state_data['entity_type'])
    if entity_type == EntityType.CATEGORY:
        media, kb_builder = await CategoryService.get_buttons(None, state, session, language)
    else:
        media, kb_builder = await SubcategoryService.get_buttons(None, state, session, language)
    caption = getattr(media, "caption", "") or "..."
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
        4: add_to_cart_confirmation,
        5: add_to_cart
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
