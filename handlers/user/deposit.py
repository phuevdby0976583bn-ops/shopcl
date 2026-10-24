import logging
from aiogram import Router, F
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from handlers.user.constants import UserStates
from models.binance_pay import BinancePayOrder
from services.deposit_flow import DepositFlowService

logger = logging.getLogger(__name__)

deposit_router = Router()

TOP_UP_COMMANDS = {
    "💰 nạp tiền", "nạp tiền", "nap tien", "/deposit", "/nap", "/topup",
    "💳 ví", "ví", "vi"
}


@deposit_router.message(F.text.lower().in_(TOP_UP_COMMANDS))
async def cmd_start_deposit(message: Message, state: FSMContext):
    await state.clear()
    text, kb = DepositFlowService.get_method_selection_keyboard()
    await message.answer(text=text, reply_markup=kb.as_markup())


@deposit_router.callback_query(F.data.in_({"deposit:start", "binance_pay:view", "dep_back:methods"}))
async def callback_start_deposit(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = DepositFlowService.get_method_selection_keyboard()
    if callback.message.caption:
        await callback.message.delete()
        await callback.message.answer(text=text, reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(text=text, reply_markup=kb.as_markup())
    await callback.answer()


@deposit_router.callback_query(F.data == "dep_method:binance")
async def choose_binance_pay(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.binance_pay_amount)
    msg = "Nhập số USDT muốn nạp (tối thiểu 1):"
    if callback.message.caption:
        await callback.message.delete()
        await callback.message.answer(text=msg)
    else:
        await callback.message.edit_text(text=msg)
    await callback.answer()


@deposit_router.message(StateFilter(UserStates.binance_pay_amount))
async def receive_binance_amount(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip().replace(",", ".")
    try:
        amount = float(text_val)
        if amount < 1:
            await message.answer("⚠️ Số tiền nạp tối thiểu là 1 USDT. Vui lòng nhập lại:")
            return
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (ví dụ: <code>5</code> hoặc <code>10.5</code>):", parse_mode="HTML")
        return

    try:
        qr_file, caption, kb = await DepositFlowService.create_binance_invoice(
            telegram_id=message.from_user.id,
            base_amount=amount,
            session=session
        )
        await message.answer_photo(
            photo=qr_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating Binance invoice: {e}")
        await message.answer(f"❌ Có lỗi khi tạo hoá đơn Binance Pay: {e}")


@deposit_router.callback_query(F.data == "dep_method:onchain")
async def choose_onchain(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = DepositFlowService.get_network_selection_keyboard()
    if callback.message.caption:
        await callback.message.delete()
        await callback.message.answer(text=text, reply_markup=kb.as_markup())
    else:
        await callback.message.edit_text(text=text, reply_markup=kb.as_markup())
    await callback.answer()


@deposit_router.callback_query(F.data.startswith("dep_net:"))
async def choose_network(callback: CallbackQuery, state: FSMContext):
    net_code = callback.data.split(":", 1)[1]
    await state.update_data(deposit_network=net_code)
    await state.set_state(UserStates.onchain_amount)

    msg = "Nhập số USDT muốn nạp (tối thiểu 1):"
    if callback.message.caption:
        await callback.message.delete()
        await callback.message.answer(text=msg)
    else:
        await callback.message.edit_text(text=msg)
    await callback.answer()


@deposit_router.message(StateFilter(UserStates.onchain_amount))
async def receive_onchain_amount(message: Message, state: FSMContext, session: AsyncSession):
    text_val = message.text.strip().replace(",", ".")
    try:
        amount = float(text_val)
        if amount < 1:
            await message.answer("⚠️ Số tiền nạp tối thiểu là 1 USDT. Vui lòng nhập lại:")
            return
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (ví dụ: <code>1</code> hoặc <code>50</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    net_code = data.get("deposit_network", "BSC")

    try:
        qr_file, caption, kb = await DepositFlowService.create_onchain_invoice(
            telegram_id=message.from_user.id,
            network_code=net_code,
            base_amount=amount,
            session=session
        )
        await message.answer_photo(
            photo=qr_file,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating On-chain invoice: {e}")
        await message.answer(f"❌ Có lỗi khi tạo hoá đơn: {e}")


@deposit_router.callback_query(F.data.startswith("dep_cp:"))
async def handle_copy_buttons(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    cp_type = parts[1]
    val = parts[2] if len(parts) > 2 else ""

    if cp_type == "id":
        await callback.answer(f"Đã sao chép Pay ID: {val}", show_alert=False)
        await callback.message.answer(f"🆔 Pay ID: <code>{val}</code>", parse_mode="HTML")
    elif cp_type == "addr":
        await callback.answer("Đã sao chép địa chỉ ví!", show_alert=False)
        await callback.message.answer(f"📫 Địa chỉ ví: <code>{val}</code>", parse_mode="HTML")
    elif cp_type == "amt":
        await callback.answer(f"Đã sao chép số tiền: {val}", show_alert=False)
        await callback.message.answer(f"💵 Số tiền cần chuyển: <code>{val}</code>", parse_mode="HTML")


@deposit_router.callback_query(F.data.startswith("dep_cancel"))
async def handle_cancel_invoice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    parts = callback.data.split(":", 1)
    if len(parts) > 1 and parts[1].isdigit():
        order_id = int(parts[1])
        stmt = update(BinancePayOrder).where(BinancePayOrder.id == order_id).values(status="CANCELLED")
        await session.execute(stmt)
        await session.commit()

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("❌ <b>Hoá đơn nạp tiền đã được huỷ.</b>", parse_mode="HTML")
    await callback.answer("Đã huỷ hoá đơn thành công!")
