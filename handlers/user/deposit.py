import config
from models.bank_order import BankDepositOrder
from services.bank_deposit import BankDepositService
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
from services.deposit_bonus import DepositBonusService

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
    try:
        await callback.answer()
    except Exception:
        pass
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
    try:
        await callback.answer()
    except Exception:
        pass
    await state.set_state(UserStates.binance_pay_amount)
    bonus_text = DepositBonusService.get_bonus_display_text(language)
    if language == Language.VI:
        msg = (
            "🟡 <b>NẠP TIỀN QUA BINANCE PAY (0% PHÍ)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 <b>Vui lòng nhập số USDT bạn muốn nạp:</b>\n"
            "<i>(Ví dụ: <code>1</code>, <code>5</code>, <code>10.5</code> - Tối thiểu 1 USDT)</i>"
        )
        if bonus_text:
            msg += f"\n\n{bonus_text}"
        btn_cancel = "‹ Huỷ / Quay lại"
    else:
        msg = (
            "🟡 <b>TOP UP VIA BINANCE PAY (0% FEE)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 <b>Please enter the USDT amount to deposit:</b>\n"
            "<i>(e.g., <code>1</code>, <code>5</code>, <code>10.5</code> - Minimum 1 USDT)</i>"
        )
        if bonus_text:
            msg += f"\n\n{bonus_text}"
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


@deposit_router.callback_query(F.data == "dep_cancel_prompt")
async def cancel_deposit_prompt(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    await state.clear()
    msg = "❌ <b>Đã huỷ thao tác nạp tiền.</b>" if language == Language.VI else "❌ <b>Deposit operation cancelled.</b>"
    try:
        await callback.message.edit_text(text=msg, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text=msg, parse_mode="HTML")
    await callback.answer()


@deposit_router.message(StateFilter(UserStates.binance_pay_amount))
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
        qr_file, caption, kb, order = await DepositFlowService.create_binance_invoice(
            telegram_id=message.from_user.id,
            base_amount=amount,
            session=session,
            language=language
        )
        try:
            sent_msg = await message.answer_photo(
                photo=qr_file,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as pe:
            logger.warning(f"Failed to send Binance QR photo, falling back to text: {pe}")
            sent_msg = await message.answer(
                text=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        # Luu message_id va chat_id de background worker tu dong cap nhat khi co giao dich
        try:
            order.chat_id = sent_msg.chat.id
            order.message_id = sent_msg.message_id
            await session.commit()
        except Exception as e_save:
            logger.warning(f"Could not save chat_id/message_id to BinancePayOrder: {e_save}")
            try:
                await session.rollback()
            except Exception:
                pass
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
            if callback.message.photo:
                await callback.message.edit_caption(caption=success_text, reply_markup=None, parse_mode="HTML")
            else:
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
    try:
        await callback.answer()
    except Exception:
        pass
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

    base_prompt = "Nhập số USDT muốn nạp (tối thiểu 1):" if language == Language.VI else "Enter USDT amount to deposit (min 1):"
    bonus_text = DepositBonusService.get_bonus_display_text(language)
    msg = f"{base_prompt}\n\n{bonus_text}".strip() if bonus_text else base_prompt
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
        qr_file, caption, kb = await DepositFlowService.create_onchain_invoice(
            telegram_id=message.from_user.id,
            network_code=net_code,
            base_amount=amount,
            session=session,
            language=language
        )
        try:
            await message.answer_photo(
                photo=qr_file,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as pe:
            logger.warning(f"Failed to answer onchain photo: {pe}")
            await message.answer(
                text=caption,
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

    cancel_text = "❌ <b>Hoá đơn nạp tiền đã được huỷ.</b>"
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=cancel_text, reply_markup=None, parse_mode="HTML")
        else:
            await callback.message.edit_text(text=cancel_text, parse_mode="HTML")
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text=cancel_text, parse_mode="HTML")
    await callback.answer("Đã huỷ hoá đơn thành công!")


@deposit_router.callback_query(F.data == "dep_method:bank")
async def prompt_bank_amount(callback: CallbackQuery, state: FSMContext, language: Language = Language.VI):
    try:
        await callback.answer()
    except Exception:
        pass
    await state.set_state(UserStates.bank_deposit_amount)
    rate = float(getattr(config, "BANK_EXCHANGE_RATE", 26000) or 26000)
    stk = getattr(config, "BANK_ACCOUNT_NUMBER", "8880117869")
    bonus_text = DepositBonusService.get_bonus_display_text(language)
    if language == Language.VI:
        msg = (
            f"🏦 <b>NẠP TIỀN QUA NGÂN HÀNG (VIETQR / BIDV)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ <b>Ngân hàng:</b> <b>BIDV</b>\n"
            f"💳 <b>Số tài khoản (STK):</b> <code>{stk}</code>\n"
            f"💱 <b>Tỷ giá:</b> <b>1$ = {rate:,.0f} đ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 <b>Vui lòng nhập số tiền bạn muốn nạp:</b>\n"
            f"• Nhập theo USD (ví dụ: <code>1</code>, <code>2</code>, <code>5</code>, <code>10</code>$)\n"
            f"• Hoặc nhập theo VNĐ (ví dụ: <code>26000</code>, <code>50000</code>, <code>100k</code>)\n"
            f"<i>(Hạn mức tối thiểu: <b>1$ (~{rate:,.0f}đ)</b>)</i>"
        )
        if bonus_text:
            msg += f"\n\n{bonus_text}"
        btn_cancel = "‹ Huỷ / Quay lại"
    else:
        msg = (
            f"🏦 <b>VIETNAM BANK TRANSFER (VIETQR / BIDV)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛️ <b>Bank:</b> <b>BIDV</b>\n"
            f"💳 <b>Account:</b> <code>{stk}</code>\n"
            f"💱 <b>Rate:</b> <b>$1 = {rate:,.0f} VND</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 <b>Please enter the amount you want to deposit:</b>\n"
            f"• In USD (e.g., <code>1</code>, <code>5</code>, <code>10</code>$)\n"
            f"• Or in VND (e.g., <code>50000</code>, <code>100000</code>)\n"
            f"<i>(Minimum: <b>$1 (~{rate:,.0f} VND)</b>)</i>"
        )
        if bonus_text:
            msg += f"\n\n{bonus_text}"
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


@deposit_router.message(StateFilter(UserStates.bank_deposit_amount))
async def receive_bank_amount(message: Message, state: FSMContext, session: AsyncSession, language: Language = Language.VI):
    raw_text = (message.text or "").strip()
    if raw_text.startswith("/") or any(k in raw_text for k in ["Sản phẩm", "Đơn hàng", "Ví", "Hỗ trợ"]):
        await state.clear()
        return

    rate = float(getattr(config, "BANK_EXCHANGE_RATE", 26000) or 26000)
    cleaned = raw_text.lower().replace("$", "").replace("vnd", "").replace("vnđ", "").replace("đ", "").replace(",", "").replace(".", "").strip()

    if cleaned.endswith("k"):
        try:
            val_vnd = float(cleaned[:-1]) * 1000
            amount_usd = round(val_vnd / rate, 2)
        except ValueError:
            await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ:")
            return
    else:
        raw_num = raw_text.replace(",", ".").replace("$", "").replace("VND", "").replace("vnd", "").strip()
        try:
            val = float(raw_num)
            if val >= 1000:
                amount_usd = round(val / rate, 2)
            else:
                amount_usd = round(val, 2)
        except ValueError:
            await message.answer("⚠️ Vui lòng nhập số tiền hợp lệ (ví dụ: <code>2</code> hoặc <code>50000</code>):", parse_mode="HTML")
            return

    if amount_usd < 0.5:
        await message.answer(f"⚠️ Số tiền nạp tối thiểu là 1$ (~{rate:,.0f} đ). Vui lòng nhập lại:")
        return

    try:
        qr_file, caption, kb, order = await BankDepositService.create_bank_invoice(
            telegram_id=message.from_user.id,
            base_amount_usd=amount_usd,
            session=session,
            language=language
        )
        try:
            sent = await message.answer_photo(
                photo=qr_file,
                caption=caption,
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        except Exception as pe:
            logger.warning(f"Failed to send VietQR photo, falling back to text: {pe}")
            sent = await message.answer(
                text=caption,
                parse_mode="HTML",
                reply_markup=kb.as_markup()
            )
        try:
            order.chat_id = sent.chat.id
            order.message_id = sent.message_id
            await session.commit()
        except Exception as e_save:
            logger.warning(f"Could not save chat_id/message_id to BankDepositOrder: {e_save}")
            try:
                await session.rollback()
            except Exception:
                pass
        await state.clear()
    except Exception as e:
        logger.error(f"Error creating Bank invoice: {e}", exc_info=True)
        await message.answer(f"❌ Có lỗi khi tạo hoá đơn nạp ngân hàng: {e}")


@deposit_router.callback_query(F.data.startswith("bank_cp:"))
async def handle_bank_copy_buttons(callback: CallbackQuery):
    parts = callback.data.split(":", 2)
    cp_type = parts[1]
    val = parts[2] if len(parts) > 2 else ""

    if cp_type == "stk":
        await callback.answer(f"Đã sao chép STK BIDV: {val}", show_alert=False)
        await callback.message.answer(f"💳 STK BIDV: <code>{val}</code>", parse_mode="HTML")
    elif cp_type == "amt":
        try:
            amt_fmt = f"{int(val):,} đ"
        except Exception:
            amt_fmt = val
        await callback.answer(f"Đã sao chép số tiền: {amt_fmt}", show_alert=False)
        await callback.message.answer(f"💵 Số tiền cần chuyển: <code>{val}</code>", parse_mode="HTML")
    elif cp_type == "memo":
        await callback.answer(f"Đã sao chép nội dung: {val}", show_alert=False)
        await callback.message.answer(f"📝 Nội dung chuyển khoản: <code>{val}</code>", parse_mode="HTML")


@deposit_router.callback_query(F.data.startswith("bank_chk:"))
async def handle_bank_check_invoice(callback: CallbackQuery, session: AsyncSession, language: Language = Language.VI):
    parts = callback.data.split(":", 1)
    if len(parts) < 2 or not parts[1].isdigit():
        await callback.answer("Hoá đơn không hợp lệ!")
        return

    order_id = int(parts[1])
    checking_toast = "🔍 Đang kiểm tra giao dịch với ngân hàng BIDV..." if language == Language.VI else "🔍 Checking bank transfer with BIDV..."
    await callback.answer(checking_toast)

    is_paid, order = await BankDepositService.check_order_status(order_id, session, callback.bot)

    if is_paid and order:
        user_dto = await session.execute(select(User).where(User.id == order.user_id))
        user = user_dto.scalar_one_or_none()
        bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2) if user else order.amount_usd
        bonus_amt, bonus_pct = DepositBonusService.calculate_bonus(order.amount_usd)
        bonus_line = f"🎁 Thưởng nạp (+{bonus_pct:g}%): <b>+{bonus_amt:.2f}$</b>\n" if bonus_amt > 0 else ""
        if language == Language.VI:
            success_msg = (
                f"🎉 <b>NẠP TIỀN NGÂN HÀNG THÀNH CÔNG!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Đã nhận: <b>+{order.amount_vnd:,.0f} đ</b> (~ <b>+{order.amount_usd}$ USDT</b>)\n"
                f"{bonus_line}"
                f"💳 Số dư khả dụng hiện tại: <b>{bal}$</b>\n"
                f"🆔 Mã GD ThueApi: <code>{order.transaction_id or 'Auto'}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🦐 Cảm ơn bạn! Hãy bấm nút bên dưới để chọn mua tài khoản ngay nhé!"
            )
        else:
            success_msg = (
                f"🎉 <b>DEPOSIT SUCCESSFUL!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Credited: <b>+{order.amount_vnd:,.0f} VND</b> (~ <b>+${order.amount_usd}</b>)\n"
                f"💳 Current Balance: <b>${bal}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Thank you for your purchase!"
            )
        from callbacks import AllCategoriesCallback
        from enums.item_type import ItemType
        kb_shop = InlineKeyboardBuilder()
        btn_txt = "\U0001f6d2 Ch\u1ecdn Mua S\u1ea3n Ph\u1ea9m" if language == Language.VI else "\U0001f6d2 Shop Products Now"
        kb_shop.button(text=btn_txt, callback_data=AllCategoriesCallback.create(level=1, item_type=ItemType.DIGITAL))
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(success_msg, reply_markup=kb_shop.as_markup(), parse_mode="HTML")
    else:
        if language == Language.VI:
            toast = (
                "⏳ Chưa phát hiện giao dịch chuyển khoản mới!\n\n"
                "Nếu bạn vừa chuyển trên App ngân hàng, vui lòng đợi 15-30 giây để hệ thống ngân hàng đồng bộ rồi bấm kiểm tra lại nhé.\n\n"
                f"⚠️ Lưu ý: BẮT BUỘC phải điền đúng nội dung chuyển khoản: NAP {callback.from_user.id}"
            )
        else:
            toast = (
                "⏳ No transfer detected yet!\n\n"
                "If you just transferred, please wait 15-30 seconds and check again.\n\n"
                f"⚠️ Note: You MUST enter the exact remark: NAP {callback.from_user.id}"
            )
        await callback.answer(toast, show_alert=True)


@deposit_router.callback_query(F.data.startswith("bank_cancel:"))
async def handle_bank_cancel_invoice(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.clear()
    parts = callback.data.split(":", 1)
    if len(parts) > 1 and parts[1].isdigit():
        order_id = int(parts[1])
        stmt = update(BankDepositOrder).where(
            BankDepositOrder.id == order_id,
            BankDepositOrder.status == "PENDING"
        ).values(status="CANCELLED")
        await session.execute(stmt)
        await session.commit()

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("❌ <b>Hoá đơn nạp tiền ngân hàng đã được huỷ.</b>", parse_mode="HTML")
    await callback.answer("Đã huỷ hoá đơn thành công!")
