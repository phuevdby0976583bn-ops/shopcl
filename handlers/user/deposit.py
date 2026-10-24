import logging
from aiogram import Router, F
from aiogram.filters import StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from enums.language import Language
from handlers.user.constants import UserStates
from models.binance_pay import BinancePayOrder
from models.user import User
from services.binance_pay import BinancePayService
from services.deposit_flow import DepositFlowService

logger = logging.getLogger(__name__)

deposit_router = Router()

TOP_UP_COMMANDS = {
    "💰 nạp tiền", "nạp tiền", "nap tien", "/deposit", "/nap", "/topup",
    "💳 ví", "ví", "vi", "/wallet"
}


@deposit_router.message(F.text.lower().in_(TOP_UP_COMMANDS))
async def cmd_start_deposit(message: Message, state: FSMContext, language: Language = Language.VI):
    await state.clear()
    text, kb = DepositFlowService.get_method_selection_keyboard(language)
    await message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")


@deposit_router.callback_query(F.data.in_({"deposit:start", "dep_back:methods"}))
async def callback_start_deposit(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    await state.clear()
    text, kb = DepositFlowService.get_method_selection_keyboard(language)
    if callback.message.caption:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@deposit_router.callback_query(F.data.in_({"dep_method:binance", "binance_pay:view"}))
async def prompt_binance_pay_amount(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    await state.set_state(UserStates.binance_pay_amount)
    if language == Language.VI:
        msg = (
            "🟡 <b>NẠP TIỀN QUA BINANCE PAY (0% PHÍ)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 <b>Vui lòng nhập số USDT bạn muốn nạp:</b>\n"
            "<i>(Ví dụ: <code>1</code>, <code>5</code>, <code>10.5</code> - Tối thiểu 1 USDT)</i>"
        )
        btn_cancel = "‹ Huỷ / Quay lại"
    else:
        msg = (
            "🟡 <b>TOP UP VIA BINANCE PAY (0% FEE)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 <b>Please enter the USDT amount to deposit:</b>\n"
            "<i>(e.g., <code>1</code>, <code>5</code>, <code>10.5</code> - Minimum 1 USDT)</i>"
        )
        btn_cancel = "‹ Cancel / Back"

    kb = InlineKeyboardBuilder()
    kb.button(text=btn_cancel, callback_data="dep_cancel_prompt")

    if callback.message.caption:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@deposit_router.callback_query(F.data == "dep_cancel_prompt")
async def cancel_deposit_prompt(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    await state.clear()
    msg = "❌ <b>Đã huỷ thao tác nạp tiền.</b>" if language == Language.VI else "❌ <b>Deposit operation cancelled.</b>"
    try:
        await callback.message.edit_text(text=msg, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text=msg, parse_mode="HTML")
    await callback.answer()


@deposit_router.message(StateFilter(UserStates.binance_pay_amount, UserStates.top_up_amount))
async def receive_binance_amount(message: Message, state: FSMContext, session: AsyncSession, language: Language = Language.VI):
    raw_text = (message.text or "").strip()
    text_val = raw_text.replace(",", ".").replace("$", "").replace("USDT", "").replace("usdt", "").strip()

    # Neu nguoi dung bam nut menu chinh hoac gui command, huy state va khong bao loi
    if raw_text.startswith("/") or any(k in raw_text for k in ["Sản phẩm", "Đơn hàng", "Ví", "Hỗ trợ", "Products", "Orders", "Wallet"]):
        await state.clear()
        return

    try:
        amount = float(text_val)
        if amount < 1:
            kb = InlineKeyboardBuilder()
            kb.button(text="‹ Huỷ", callback_data="dep_cancel_prompt")
            await message.answer(
                "⚠️ <b>Số tiền nạp tối thiểu là 1 USDT.</b>\nVui lòng nhập lại số tiền (ví dụ: <code>1</code> hoặc <code>5</code>):",
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
            return
    except ValueError:
        kb = InlineKeyboardBuilder()
        kb.button(text="‹ Huỷ", callback_data="dep_cancel_prompt")
        await message.answer(
            "⚠️ <b>Vui lòng nhập số tiền hợp lệ!</b>\nVí dụ: <code>1</code> hoặc <code>5.5</code>:",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        return

    try:
        text, kb, order = await DepositFlowService.create_binance_invoice(
            telegram_id=message.from_user.id,
            base_amount=amount,
            session=session,
            language=language
        )
        sent_msg = await message.answer(
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
        # Luu message_id va chat_id de background worker tu dong cap nhat khi co giao dich
        order.chat_id = sent_msg.chat.id
        order.message_id = sent_msg.message_id
        await session.commit()
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating Binance invoice: {e}", exc_info=True)
        await message.answer(f"❌ Có lỗi khi tạo hoá đơn: {e}")


@deposit_router.callback_query(F.data.startswith("dep_chk:"))
async def handle_check_invoice(callback: CallbackQuery, session: AsyncSession, language: Language = Language.VI):
    parts = callback.data.split(":", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await callback.answer("Không tìm thấy mã hoá đơn!", show_alert=True)
        return

    order_id = int(parts[1])
    await callback.answer("🔍 Đang kiểm tra giao dịch trên Binance...", show_alert=False)

    is_paid, order = await BinancePayService.check_order_status(
        order_id=order_id,
        session=session,
        bot=callback.bot
    )

    if is_paid and order:
        stmt_u = select(User).where(User.id == order.user_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        new_bal = 0.0
        if user:
            new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)

        success_text = (
            f"✅ <b>ĐÃ THANH TOÁN THÀNH CÔNG!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧾 <b>Hoá đơn:</b> #{order.id}\n"
            f"💰 <b>Đã nạp:</b> <b>+{order.amount:.4f} USDT</b>\n"
            f"💳 <b>Số dư khả dụng hiện tại:</b> <b>{new_bal}$</b>\n"
            f"🆔 <b>Mã GD Binance:</b> <code>{order.transaction_id or ''}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 Cảm ơn bạn! Hãy bấm <b>🛒 Sản phẩm</b> để mua nick ngay nhé! 🚀"
        )
        try:
            await callback.message.edit_text(text=success_text, reply_markup=None, parse_mode="HTML")
        except Exception:
            pass
        await callback.answer(f"🎉 Nạp tiền thành công! Đã cộng +{order.amount:.4f} USDT.", show_alert=True)
    else:
        amt_str = f"{order.amount:.4f}" if order else ""
        await callback.answer(
            f"⏳ Chưa nhận được giao dịch {amt_str} USDT.\n"
            "Vui lòng đảm bảo bạn đã chuyển đúng số tiền qua Binance Pay rồi kiểm tra lại (hoặc chờ hệ thống tự động cộng sau 1-2 phút).",
            show_alert=True
        )


@deposit_router.callback_query(F.data == "binance_pay:check")
async def handle_legacy_check(callback: CallbackQuery, session: AsyncSession):
    await callback.answer("🔍 Đang kiểm tra giao dịch trên Binance...", show_alert=False)
    credited = await BinancePayService.process_and_credit_transactions(
        bot=callback.bot,
        session=session,
        target_telegram_id=callback.from_user.id
    )
    if credited:
        total = sum(c.get("amount", 0.0) for c in credited)
        await callback.answer(f"🎉 Đã cộng +{total:.4f} USDT vào tài khoản!", show_alert=True)
    else:
        await callback.answer("⏳ Chưa nhận được giao dịch mới từ bạn trên Binance. Vui lòng kiểm tra lại sau ít giây.", show_alert=True)


@deposit_router.callback_query(F.data == "dep_method:onchain")
async def choose_onchain(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    await state.clear()
    text, kb = DepositFlowService.get_network_selection_keyboard(language)
    if callback.message.caption:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@deposit_router.callback_query(F.data.startswith("dep_net:"))
async def choose_network(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    net_code = callback.data.split(":", 1)[1]
    await state.update_data(deposit_network=net_code)
    await state.set_state(UserStates.onchain_amount)

    msg = (
        f"🌐 <b>Mạng đã chọn:</b> <code>{net_code}</code>\n\n"
        "👉 <b>Nhập số USDT bạn muốn nạp</b> (tối thiểu <code>1</code> USDT):"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="‹ Huỷ / Quay lại", callback_data="dep_cancel_prompt")

    if callback.message.caption:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        try:
            await callback.message.edit_text(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text=msg, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@deposit_router.message(StateFilter(UserStates.onchain_amount))
async def receive_onchain_amount(message: Message, state: FSMContext, session: AsyncSession, language: Language = Language.VI):
    raw_text = (message.text or "").strip()
    text_val = raw_text.replace(",", ".").replace("$", "").replace("USDT", "").replace("usdt", "").strip()

    if raw_text.startswith("/") or any(k in raw_text for k in ["Sản phẩm", "Đơn hàng", "Ví", "Hỗ trợ"]):
        await state.clear()
        return

    try:
        amount = float(text_val)
        if amount < 1:
            await message.answer("⚠️ Số tiền nạp tối thiểu là 1 USDT. Vui lòng nhập lại:")
            return
    except ValueError:
        await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (ví dụ: <code>10</code> hoặc <code>50</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    net_code = data.get("deposit_network", "BSC")

    try:
        text, kb = await DepositFlowService.create_onchain_invoice(
            telegram_id=message.from_user.id,
            network_code=net_code,
            base_amount=amount,
            session=session,
            language=language
        )
        await message.answer(
            text=text,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
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
        stmt = update(BinancePayOrder).where(
            BinancePayOrder.id == order_id,
            BinancePayOrder.status == "PENDING"
        ).values(status="CANCELLED")
        await session.execute(stmt)
        await session.commit()

    try:
        await callback.message.edit_text("❌ <b>Hoá đơn nạp tiền đã được huỷ.</b>", parse_mode="HTML")
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("❌ <b>Hoá đơn nạp tiền đã được huỷ.</b>", parse_mode="HTML")
    await callback.answer("Đã huỷ hoá đơn thành công!")
