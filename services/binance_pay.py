import io
import time
import hmac
import hashlib
import urllib.parse
import re
import logging
from datetime import datetime, timezone, timedelta
import aiohttp
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import config
from enums.cryptocurrency import Cryptocurrency
from enums.language import Language
from models.binance_pay import BinancePayOrder
from models.deposit import Deposit
from models.user import User
from services.deposit_bonus import DepositBonusService

logger = logging.getLogger(__name__)


class BinancePayService:
    @staticmethod
    async def fetch_binance_pay_transactions() -> list[dict]:
        api_key = getattr(config, "BINANCE_API_KEY", "") or ""
        api_secret = getattr(config, "BINANCE_API_SECRET", "") or ""
        if not api_key or not api_secret:
            return []

        timestamp = int(time.time() * 1000)
        start_time = timestamp - (48 * 3600 * 1000)
        params = {
            "timestamp": timestamp,
            "recvWindow": 60000,
            "startTimestamp": start_time,
            "limit": 100
        }

        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        url = f"https://api.binance.com/sapi/v1/pay/transactions?{query_string}&signature={signature}"
        headers = {
            "X-MBX-APIKEY": api_key
        }

        try:
            async with aiohttp.ClientSession() as http_session:
                async with http_session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("code") == "000000" and "data" in data:
                            return data["data"]
                        else:
                            logger.warning(f"Binance Pay API error response: {data}")
                            return []
                    else:
                        text = await resp.text()
                        logger.warning(f"Binance Pay HTTP {resp.status}: {text}")
                        return []
        except Exception as e:
            logger.warning(f"Lỗi kết nối Binance Pay API: {e}")
            return []

    @staticmethod
    async def process_and_credit_transactions(bot, session: AsyncSession, target_order_id: int = None, target_telegram_id: int = None) -> list[dict]:
        tx_list = await BinancePayService.fetch_binance_pay_transactions()
        if not tx_list:
            return []

        stmt_pending = select(BinancePayOrder).where(BinancePayOrder.status == "PENDING")
        if target_order_id:
            stmt_pending = stmt_pending.where(BinancePayOrder.id == target_order_id)
        elif target_telegram_id:
            stmt_pending = stmt_pending.where(BinancePayOrder.telegram_id == target_telegram_id)

        pending_orders = list((await session.execute(stmt_pending)).scalars().all())
        credited = []

        for tx in tx_list:
            tx_id = str(tx.get("transactionId") or tx.get("orderId") or "").strip()
            if not tx_id:
                continue

            currency = str(tx.get("currency", "")).upper()
            if currency not in ("USDT", "BUSD"):
                continue

            try:
                amount = float(tx.get("amount", 0.0))
            except Exception:
                continue

            if amount <= 0:
                continue

            note = str(tx.get("note", "") or "").strip()

            stmt_check = select(BinancePayOrder).where(
                BinancePayOrder.transaction_id == tx_id,
                BinancePayOrder.status == "COMPLETED"
            )
            existing = (await session.execute(stmt_check)).scalar_one_or_none()
            if existing:
                continue

            matched_order = None

            # Quy tac 1: Khop so tien le 4 chu so thap phan (MetakingBot auto matching)
            for p_order in pending_orders:
                if p_order.status == "PENDING" and abs(round(p_order.amount, 4) - round(amount, 4)) < 0.0001:
                    matched_order = p_order
                    break

            # Quy tac 2: Khop theo note / memo neu co
            if not matched_order and note:
                for p_order in pending_orders:
                    if p_order.status == "PENDING":
                        if p_order.memo.lower() in note.lower() or str(p_order.telegram_id) in note or str(p_order.id) in note:
                            matched_order = p_order
                            break

            if matched_order:
                matched_order.status = "COMPLETED"
                matched_order.transaction_id = tx_id
                matched_order.amount = amount

                stmt_u = select(User).where(User.id == matched_order.user_id)
                user = (await session.execute(stmt_u)).scalar_one_or_none()
                if user:
                    bonus_amt, bonus_pct = DepositBonusService.calculate_bonus(amount)
                    total_credit = round(amount + bonus_amt, 2)
                    user.top_up_amount = round(float(user.top_up_amount or 0.0) + total_credit, 2)
                    deposit = Deposit(
                        user_id=user.id,
                        network=Cryptocurrency.USDT_BEP20,
                        amount=int(total_credit * (10 ** 18)),
                        fiat_amount=total_credit,
                        deposit_datetime=datetime.now(timezone.utc)
                    )
                    session.add(deposit)
                    await session.commit()

                    new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)

                    # Gui thong bao Ting Ting vao chat cho khach hang
                    try:
                        bonus_line = f"🎁 Thưởng nạp (+{bonus_pct:g}%): <b>+{bonus_amt:.2f}$</b>\n" if bonus_amt > 0 else ""
                        user_msg = (
                            f"🎉 <b>TING TING! NẠP TIỀN THÀNH CÔNG</b> 🎉\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"✅ Đã nạp thành công: <b>+{amount:.4f} USDT</b> qua <b>Binance Pay (0% phí)</b>!\n"
                            f"{bonus_line}"
                            f"💳 Số dư khả dụng hiện tại: <b>{new_bal}$</b>\n"
                            f"🆔 Mã GD Binance: <code>{tx_id}</code>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"Cảm ơn bạn đã ủng hộ shop! Hãy bấm <b>🛒 Sản phẩm</b> để mua nick ngay nhé! 🚀"
                        )
                        await bot.send_message(chat_id=matched_order.telegram_id, text=user_msg, parse_mode="HTML")
                    except Exception as e:
                        logger.warning(f"Failed to send customer notification: {e}")

                    # Tu dong cap nhat noi dung tin nhan hoa don thanh Cong tien thanh cong
                    if matched_order.chat_id and matched_order.message_id:
                        try:
                            bonus_inv_line = f"🎁 <b>Thưởng nạp (+{bonus_pct:g}%):</b> <b>+{bonus_amt:.2f}$</b>\n" if bonus_amt > 0 else ""
                            success_text = (
                                f"✅ <b>ĐÃ THANH TOÁN THÀNH CÔNG!</b>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🧾 <b>Hoá đơn:</b> #{matched_order.id}\n"
                                f"💰 <b>Đã nạp:</b> <b>+{amount:.4f} USDT</b>\n"
                                f"{bonus_inv_line}"
                                f"💳 <b>Số dư hiện tại:</b> <b>{new_bal}$</b>\n"
                                f"🆔 <b>Mã GD Binance:</b> <code>{tx_id}</code>\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"🎉 Cảm ơn bạn! Hãy bấm <b>🛒 Sản phẩm</b> để mua nick ngay! 🚀"
                            )
                            try:
                                await bot.edit_message_caption(
                                    chat_id=matched_order.chat_id,
                                    message_id=matched_order.message_id,
                                    caption=success_text,
                                    reply_markup=None,
                                    parse_mode="HTML"
                                )
                            except Exception:
                                await bot.edit_message_text(
                                    chat_id=matched_order.chat_id,
                                    message_id=matched_order.message_id,
                                    text=success_text,
                                    reply_markup=None,
                                    parse_mode="HTML"
                                )
                        except Exception as e:
                            logger.debug(f"Could not edit invoice message: {e}")

                    # Bao ve Telegram cho Admin
                    try:
                        admin_msg = (
                            f"💰 <b>[BINANCE PAY] CÓ GIAO DỊCH MỚI!</b>\n\n"
                            f"👤 Khách: @{user.telegram_username or 'Unknown'} (ID: <code>{matched_order.telegram_id}</code>)\n"
                            f"💵 Số tiền nạp: <b>+{amount:.4f} USDT</b>\n"
                            f"🧾 Hoá đơn: #{matched_order.id}\n"
                            f"🆔 Mã GD: <code>{tx_id}</code>"
                        )
                        for admin_id in getattr(config, "ADMIN_ID_LIST", []):
                            try:
                                await bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(f"Failed to notify admin: {e}")

                    credited.append({
                        "order_id": matched_order.id,
                        "telegram_id": matched_order.telegram_id,
                        "amount": amount,
                        "transaction_id": tx_id
                    })
                    pending_orders = [p for p in pending_orders if p.id != matched_order.id]

            # Quy tac 3: Khach hang khong tao hoa don nhung chuyen tien co Memo chua Telegram ID
            elif note:
                match = re.search(r'(\d{6,15})', note)
                if match:
                    matched_tg_id = int(match.group(1))
                    stmt_u = select(User).where(User.telegram_id == matched_tg_id)
                    user = (await session.execute(stmt_u)).scalar_one_or_none()
                    if user:
                        bonus_amt, bonus_pct = DepositBonusService.calculate_bonus(amount)
                        total_credit = round(amount + bonus_amt, 2)
                        user.top_up_amount = round(float(user.top_up_amount or 0.0) + total_credit, 2)
                        new_order = BinancePayOrder(
                            user_id=user.id,
                            telegram_id=matched_tg_id,
                            memo=f"NAP {matched_tg_id}",
                            amount=amount,
                            transaction_id=tx_id,
                            status="COMPLETED"
                        )
                        session.add(new_order)
                        deposit = Deposit(
                            user_id=user.id,
                            network=Cryptocurrency.USDT_BEP20,
                            amount=int(total_credit * (10 ** 18)),
                            fiat_amount=total_credit,
                            deposit_datetime=datetime.now(timezone.utc)
                        )
                        session.add(deposit)
                        await session.commit()
                        new_bal = round((user.top_up_amount or 0.0) - (user.consume_records or 0.0), 2)
                        try:
                            bonus_line = f"🎁 Thưởng nạp (+{bonus_pct:g}%): <b>+{bonus_amt:.2f}$</b>\n" if bonus_amt > 0 else ""
                            user_msg = (
                                f"🎉 <b>TING TING! NẠP TIỀN THÀNH CÔNG</b> 🎉\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                                f"✅ Đã nhận: <b>+{amount:.4f} USDT</b> qua <b>Binance Pay</b>!\n"
                                f"{bonus_line}"
                                f"💳 Số dư hiện tại: <b>{new_bal}$</b>\n"
                                f"🆔 Mã GD: <code>{tx_id}</code>"
                            )
                            await bot.send_message(chat_id=matched_tg_id, text=user_msg, parse_mode="HTML")
                        except Exception:
                            pass
                        credited.append({
                            "telegram_id": matched_tg_id,
                            "amount": amount,
                            "transaction_id": tx_id
                        })

        # Tu dong danh dau EXPIRED cac hoa don qua 90 phut khong thanh toan
        try:
            expire_cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)
            stmt_exp = update(BinancePayOrder).where(
                BinancePayOrder.status == "PENDING",
                BinancePayOrder.created_at < expire_cutoff
            ).values(status="EXPIRED")
            await session.execute(stmt_exp)
            await session.commit()
        except Exception:
            pass

        return credited

    @staticmethod
    async def check_order_status(order_id: int, session: AsyncSession, bot) -> tuple[bool, BinancePayOrder | None]:
        stmt = select(BinancePayOrder).where(BinancePayOrder.id == order_id)
        order = (await session.execute(stmt)).scalar_one_or_none()
        if not order:
            return False, None

        if order.status == "COMPLETED":
            return True, order

        # Quet ngay Binance de kiem tra giao dich
        await BinancePayService.process_and_credit_transactions(
            bot=bot,
            session=session,
            target_order_id=order_id
        )
        await session.refresh(order)
        if order.status == "COMPLETED":
            return True, order

        return False, order
