from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from callbacks import CartCallback, AllCategoriesCallback
from enums.item_type import ItemType
from enums.keyboard_button import KeyboardButton as KB
from enums.language import Language
from utils.custom_filters import IsUserExistFilter

cart_router = Router()


@cart_router.message(F.text.in_(KB.get_localized_set(KB.CART)), IsUserExistFilter())
@cart_router.message(F.text == '/cart', IsUserExistFilter())
async def cart_text_message(message: Message, session: AsyncSession, state: FSMContext, language: Language):
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text='🛒 Xem danh mục sản phẩm',
        callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    )
    kb_builder.adjust(1)
    btn_text = "🛒 Xem danh mục sản phẩm" if language == Language.VI else "🛒 Browse Products"
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=btn_text,
        callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    )
    kb_builder.adjust(1)
    if language == Language.VI:
        msg = (
            '⚡ <b>Hệ thống áp dụng cơ chế MUA NGAY (Trừ tiền trực tiếp)!</b>\n\n'
            '👉 Bạn không cần thêm vào giỏ hàng rườm rà. Chỉ cần chọn loại tài khoản và số lượng cần mua, tiền sẽ được trừ trực tiếp từ số dư ví và nick LIVE 100% sẽ được giao ngay lập tức!\n\n'
            '👇 Bấm nút bên dưới để chọn sản phẩm:'
        )
    else:
        msg = (
            '⚡ <b>INSTANT PURCHASE ENABLED (Direct Balance Deduction)!</b>\n\n'
            '👉 No tedious cart management needed. Simply select your desired account type and quantity, your wallet balance will be debited and 100% LIVE accounts delivered immediately!\n\n'
            '👇 Tap the button below to browse products:'
        )
    await message.answer(msg, reply_markup=kb_builder.as_markup(), parse_mode='HTML')


@cart_router.callback_query(CartCallback.filter(), IsUserExistFilter())
async def navigate_cart_process(callback: CallbackQuery,
                                callback_data: CartCallback,
                                session: AsyncSession | Session,
                                state: FSMContext,
                                language: Language):
    try:
        await callback.answer()
    except Exception:
        pass
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text='🛒 Xem danh mục sản phẩm',
        callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    )
    kb_builder.adjust(1)
    btn_text = "🛒 Xem danh mục sản phẩm" if language == Language.VI else "🛒 Browse Products"
    kb_builder = InlineKeyboardBuilder()
    kb_builder.button(
        text=btn_text,
        callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL)
    )
    kb_builder.adjust(1)
    if language == Language.VI:
        text = (
            '⚡ <b>Hệ thống áp dụng cơ chế MUA NGAY (Trừ tiền trực tiếp)!</b>\n\n'
            '👉 Bấm nút bên dưới để chọn loại tài khoản và mua ngay:'
        )
    else:
        text = (
            '⚡ <b>INSTANT PURCHASE ENABLED!</b>\n\n'
            '👉 Tap the button below to browse account types and buy now:'
        )
    if callback.message.caption:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=text, reply_markup=kb_builder.as_markup(), parse_mode='HTML')
    else:
        try:
            await callback.message.edit_text(text=text, reply_markup=kb_builder.as_markup(), parse_mode='HTML')
        except Exception:
            await callback.message.answer(text=text, reply_markup=kb_builder.as_markup(), parse_mode='HTML')
