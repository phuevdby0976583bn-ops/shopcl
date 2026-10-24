import io
import time
import hmac
import hashlib
import urllib.parse
import re
import logging
from datetime import datetime, timezone
import aiohttp
import qrcode
from aiogram.types import InputMediaPhoto, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import MyProfileCallback
from enums.cryptocurrency import Cryptocurrency
from enums.language import Language
from models.binance_pay import BinancePayOrder
from models.deposit import Deposit
from models.user import User
from services.notification import NotificationService

logger = logging.getLogger(__name__)


class BinancePayService:
    @staticmethod
    def generate_qr_code(binance_uid: str, memo: str) -> BufferedInputFile:
        # Tao ma QR chua thong tin chuyen khoan Binance Pay
        qr = qrcode.QRCode(box_size=8, border=2)
        # Deep link format hoac noi dung ID
        qr_data = f"binance://pay?receiver={binance_uid}&memo={memo}"
        qr.add_data(qr_data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(file=buffer.getvalue(), filename=f"binance_pay_{memo}.png")

    @staticmethod
    async def get_or_create_order(telegram_id: int, session: AsyncSession) -> BinancePayOrder:
        # Tim user trong database
        stmt_user = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_user)).scalar_one_or_none()
        if not user:
            raise ValueError(f"Khong tim thay nguoi dung Telegram ID: {telegram_id}")

        memo = f"NAP {telegram_id}"

        # Kiem tra order pending gan nhat
        stmt_order = select(BinancePayOrder).where(
            BinancePayOrder.telegram_id == telegram_id,
            BinancePayOrder.status == "PENDING"
        ).order_by(BinancePayOrder.id.desc())
        order = (await session.execute(stmt_order)).scalar_one_or_none()

        if not order:
            order = BinancePayOrder(
                user_id=user.id,
                telegram_id=telegram_id,
                memo=memo,
                status="PENDING"
            )
            session.add(order)
            await session.commit()
            await session.refresh(order)

        return order

    @staticmethod
    async def build_payment_screen(telegram_id: int, session: AsyncSession, language: Language) -> tuple[InputMediaPhoto, InlineKeyboardBuilder]:
        order = await BinancePayService.get_or_create_order(telegram_id, session)
        binance_uid = config.BINANCE_UID or "805398854"
        memo = order.memo

        qr_file = BinancePayService.generate_qr_code(binance_uid, memo)

        caption = (
            f"🟡 <b>NẠP TIỀN QUA BINANCE PAY (0% PHÍ)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ <b>Phí giao dịch:</b> <b>0 đ / 0 USDT (Miễn phí 100%)</b>\n"
            f"⚡ <b>Thời gian:</b> Nhận ngay lập tức (1-5 giây)\n"
            f"⚡ <b>Hạn mức:</b> Từ <b>0.01 USDT</b> (không giới hạn tối thiểu)\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👉 <b>BƯỚC 1:</b> Mở app <b>Binance</b> ➔ Chọn biểu tượng <b>Pay</b> (ở góc trên hoặc mục Thêm)\n\n"
            f"👉 <b>BƯỚC 2:</b> Chọn <b>Gửi tiền (Send)</b> tới Binance UID:\n"
            f"🆔 <code>{binance_uid}</code> <i>(Chạm vào số để sao chép)</i>\n\n"
            f"👉 <b>BƯỚC 3:</b> Nhập số lượng USDT muốn nạp.\n\n"
            f"👉 <b>BƯỚC 4 (BẮT BUỘC):</b>\n"
            f"Tại mục <b>Ghi chú / Remark / Note</b>, bạn BẮT BUỘC nhập:\n"
            f"📝 <code>{memo}</code> <i>(Chạm vào chữ để sao chép)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<i>💡 Sau khi hoàn tất chuyển trên Binance, bấm nút <b>[ 🔄 Kiểm tra giao dịch ]</b> bên dưới để bot cộng tiền ngay lập tức!</i>"
        )

        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text="🔄 Kiểm tra giao dịch (Check)",
            callback_data="binance_pay:check"
        )
        kb_builder.button(
            text="🔙 Quay lại Ví",
            callback_data=MyProfileCallback.create(level=0)
        )
        kb_builder.adjust(1)

        media = InputMediaPhoto(media=qr_file, caption=caption, parse_mode="HTML")
        return media, kb_builder

    @staticmethod
    async def fetch_binance_pay_transactions() -> list[dict]:
        api_key = config.BINANCE_API_KEY
        api_secret = config.BINANCE_API_SECRET
        if not api_key or not api_secret:
            logger.info("Chua cau hinh BINANCE_API_KEY hoac BINANCE_API_SECRET")
            return []

        timestamp = int(time.time() * 1000)
        # Lay cac giao dich trong 48 gio gan nhat
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
            logger.error(f"Loi ket noi Binance Pay API: {e}")
            return []

    @staticmethod
    async def process_and_credit_transactions(bot, session: AsyncSession, target_telegram_id: int = None) -> list[dict]:
        tx_list = await BinancePayService.fetch_binance_pay_transactions()
        if not tx_list:
            return []

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

            # Kiem tra xem giao dich nay da duoc cong tien chua
            stmt_check = select(BinancePayOrder).where(
                BinancePayOrder.transaction_id == tx_id,
                BinancePayOrder.status == "COMPLETED"
            )
            existing = (await session.execute(stmt_check)).scalar_one_or_none()
            if existing:
                continue

            # Trich xuat Telegram ID tu note (Vi du: "NAP 12345678" hoac "12345678")
            matched_tg_id = None
            match = re.search(r'(\d{6,15})', note)
            if match:
                matched_tg_id = int(match.group(1))

            if target_telegram_id and matched_tg_id != target_telegram_id:
                continue

            if not matched_tg_id:
                continue

            # Tim user trong database
            stmt_u = select(User).where(User.telegram_id == matched_tg_id)
            user = (await session.execute(stmt_u)).scalar_one_or_none()
            if not user:
                continue

            # Cap nhat so du nguoi dung
            user.top_up_amount = round(float(user.top_up_amount or 0.0) + amount, 2)

            # Cap nhat hoac tao BinancePayOrder
            stmt_order = select(BinancePayOrder).where(
                BinancePayOrder.telegram_id == matched_tg_id,
                BinancePayOrder.status == "PENDING"
            ).order_by(BinancePayOrder.id.desc())
            order = (await session.execute(stmt_order)).scalar_one_or_none()

            if not order:
                order = BinancePayOrder(
                    user_id=user.id,
                    telegram_id=matched_tg_id,
                    memo=f"NAP {matched_tg_id}",
                    amount=amount,
                    transaction_id=tx_id,
                    status="COMPLETED"
                )
                session.add(order)
            else:
                order.status = "COMPLETED"
                order.amount = amount
                order.transaction_id = tx_id

            # Ghi nhan vao bang deposits
            deposit = Deposit(
                user_id=user.id,
                network=Cryptocurrency.USDT_BEP20,
                amount=int(amount * (10 ** 18)),
                fiat_amount=amount,
                deposit_datetime=datetime.now(timezone.utc)
            )
            session.add(deposit)

            await session.commit()

            # Thong bao ting ting cho khach hang
            try:
                new_bal = round(user.top_up_amount - (user.consume_records or 0.0), 2)
                user_msg = (
                    f"🎉 <b>TING TING! NẠP TIỀN THÀNH CÔNG</b> 🎉\n\n"
                    f"✅ Đã nạp thành công: <b>+{amount} USDT</b> qua <b>Binance Pay (0% phí)</b>!\n"
                    f"💳 Số dư khả dụng hiện tại: <b>{new_bal}$</b>\n"
                    f"🆔 Mã GD Binance: <code>{tx_id}</code>\n\n"
                    f"Cảm ơn bạn đã ủng hộ shop! Hãy bấm <b>🛒 Sản phẩm</b> để mua tài khoản ngay nhé! 🦐"
                )
                await bot.send_message(chat_id=matched_tg_id, text=user_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Khong the gui tin nhan thong bao nap Binance Pay cho {matched_tg_id}: {e}")

            # Thong bao cho Admin
            try:
                admin_msg = (
                    f"💰 <b>[BINANCE PAY] CÓ GIAO DỊCH MỚI!</b>\n\n"
                    f"👤 Khách hàng: @{user.telegram_username or 'Unknown'} (ID: <code>{matched_tg_id}</code>)\n"
                    f"💵 Số tiền nạp: <b>+{amount} USDT</b>\n"
                    f"📝 Ghi chú Memo: <code>{note}</code>\n"
                    f"🆔 Transaction ID: <code>{tx_id}</code>"
                )
                for admin_id in config.ADMIN_ID_LIST:
                    try:
                        await bot.send_message(chat_id=admin_id, text=admin_msg, parse_mode="HTML")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Khong the gui tin nhan bao admin Binance Pay: {e}")

            credited.append({
                "telegram_id": matched_tg_id,
                "amount": amount,
                "transaction_id": tx_id
            })

        return credited
