import io
import re
import random
import logging
from datetime import datetime, timezone, timedelta
import aiohttp
import qrcode
from PIL import Image, ImageDraw, ImageFont
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

import config
from enums.cryptocurrency import Cryptocurrency
from enums.language import Language
from models.bank_order import BankDepositOrder
from models.deposit import Deposit
from models.user import User

logger = logging.getLogger(__name__)

# BIN mã ngân hàng chuẩn Napas VietQR
BANK_BINS = {
    "BIDV": "970418",
    "MBBANK": "970422",
    "MB": "970422",
    "VIETCOMBANK": "970436",
    "VCB": "970436",
    "VIETINBANK": "970415",
    "CTG": "970415",
    "ACB": "970416",
    "TECHCOMBANK": "970407",
    "TCB": "970407",
    "VPBANK": "970432",
    "TPBANK": "970423",
}


def crc16_ccitt(data: bytes) -> str:
    crc = 0xFFFF
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def build_vietqr_emvco_payload(bin_code: str, account_no: str, amount_vnd: int, memo: str) -> str:
    """Sinh chuỗi mã QR chuẩn Napas VietQR EMVCo quốc gia."""
    s00 = "000201"
    s01 = "010212"
    guid = "0010A000000727"
    acc = f"00{len(bin_code):02d}{bin_code}01{len(account_no):02d}{account_no}"
    tag38_sub = f"{guid}01{len(acc):02d}{acc}0208QRIBFTTA"
    s38 = f"38{len(tag38_sub):02d}{tag38_sub}"
    s53 = "5303704"
    amt_str = str(int(amount_vnd))
    s54 = f"54{len(amt_str):02d}{amt_str}"
    s58 = "5802VN"
    tag62_sub = f"08{len(memo):02d}{memo}"
    s62 = f"62{len(tag62_sub):02d}{tag62_sub}"
    raw = s00 + s01 + s38 + s53 + s54 + s58 + s62 + "6304"
    crc = crc16_ccitt(raw.encode("ascii"))
    return raw + crc


class BankDepositService:
    @staticmethod
    def generate_vietqr_image(bin_code: str, account_no: str, amount_vnd: int, memo: str, bank_code: str = "BIDV") -> BufferedInputFile:
        """Sinh mã QR VietQR chuẩn, vẽ logo ngân hàng BIDV màu xanh ngọc ở giữa."""
        payload = build_vietqr_emvco_payload(bin_code, account_no, amount_vnd, memo)

        qr = qrcode.QRCode(box_size=10, border=3)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#002D56", back_color="white").convert("RGB")
        w, h = img.size

        # Vẽ khung logo BIDV ở giữa
        box_size = int(w * 0.22)
        x0 = (w - box_size) // 2
        y0 = (h - box_size) // 2
        x1 = x0 + box_size
        y1 = y0 + box_size

        draw = ImageDraw.Draw(img)
        pad = 6
        draw.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], radius=14, fill="white")
        # Màu xanh BIDV chuẩn (#006666 / #002D56)
        draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill="#006666")

        # Vẽ chữ BIDV màu trắng / vàng
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        r = box_size // 3
        draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill="#DAA520")
        r_inner = r // 2
        draw.polygon([(cx, cy - r_inner), (cx + r_inner, cy), (cx, cy + r_inner), (cx - r_inner, cy)], fill="#006666")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(file=buffer.getvalue(), filename=f"vietqr_{memo.replace(' ', '_')}.png")

    @staticmethod
    async def create_bank_invoice(telegram_id: int, base_amount_usd: float, session: AsyncSession, language: Language = Language.VI) -> tuple[BufferedInputFile, str, InlineKeyboardBuilder, BankDepositOrder]:
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            raise ValueError("Không tìm thấy thông tin người dùng trong hệ thống!")

        account_number = getattr(config, "BANK_ACCOUNT_NUMBER", "8880117869") or "8880117869"
        account_name = getattr(config, "BANK_ACCOUNT_NAME", "") or ""
        bank_code = (getattr(config, "BANK_CODE", "BIDV") or "BIDV").upper()
        bin_code = BANK_BINS.get(bank_code, "970418")
        rate = float(getattr(config, "BANK_EXCHANGE_RATE", 26000) or 26000)

        # Tính toán số tiền VNĐ tương ứng
        exact_vnd = int(round(base_amount_usd * rate))
        # Làm tròn theo nghìn đồng nếu > 10.000đ
        if exact_vnd >= 10000:
            exact_vnd = int(round(exact_vnd / 1000.0) * 1000)

        memo = f"NAP {telegram_id}"

        # Lưu đơn nạp vào DB
        order = BankDepositOrder(
            user_id=user.id,
            telegram_id=telegram_id,
            bank_code=bank_code,
            account_number=account_number,
            account_name=account_name,
            amount_vnd=float(exact_vnd),
            amount_usd=round(base_amount_usd, 2),
            memo=memo,
            status="PENDING"
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)

        qr_file = BankDepositService.generate_vietqr_image(bin_code, account_number, exact_vnd, memo, bank_code)

        acc_name_display = f"👤 <b>Chủ TK:</b> <b>{account_name}</b>\n" if account_name else ""

        if language == Language.VI:
            text = (
                f"🏦 <b>HOÁ ĐƠN NẠP TIỀN NGÂN HÀNG (VIETQR)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏛️ <b>Ngân hàng:</b> <b>{bank_code} (BIDV)</b>\n"
                f"💳 <b>Số tài khoản (STK):</b> <code>{account_number}</code>\n"
                f"{acc_name_display}"
                f"💵 <b>Số tiền cần chuyển:</b> <code>{exact_vnd:,}</code> đ (~<b>{base_amount_usd}$</b>)\n"
                f"📝 <b>Nội dung chuyển khoản (BẮT BUỘC):</b>\n"
                f"👉 <code>{memo}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <i>Hệ thống tự động cộng tiền trong 10-30 giây ngay sau khi nhận được tiền.</i>\n"
                f"⚠️ <b>LƯU Ý:</b> Bạn <b>BẮT BUỘC</b> điền đúng nội dung <code>{memo}</code> để được cộng tiền tự động!"
            )
            btn_cp_stk = "📋 Sao chép STK"
            btn_cp_amt = "📋 Sao chép số tiền"
            btn_cp_memo = "📋 Sao chép nội dung"
            btn_chk = "🔄 Tôi đã chuyển tiền (Kiểm tra)"
            btn_cancel = "❌ Huỷ hoá đơn"
        else:
            text = (
                f"🏦 <b>VIETNAM BANK DEPOSIT (VIETQR)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏛️ <b>Bank:</b> <b>{bank_code} (BIDV)</b>\n"
                f"💳 <b>Account Number:</b> <code>{account_number}</code>\n"
                f"{acc_name_display}"
                f"💵 <b>Transfer Amount:</b> <code>{exact_vnd:,}</code> VND (~<b>${base_amount_usd}</b>)\n"
                f"📝 <b>Transfer Content (REQUIRED):</b>\n"
                f"👉 <code>{memo}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <i>Instant auto-credit in 10-30s once transfer is completed.</i>\n"
                f"⚠️ <b>NOTE:</b> You MUST include the exact remark <code>{memo}</code>!"
            )
            btn_cp_stk = "📋 Copy Account No"
            btn_cp_amt = "📋 Copy Amount"
            btn_cp_memo = "📋 Copy Content"
            btn_chk = "🔄 I Have Paid (Check Now)"
            btn_cancel = "❌ Cancel Invoice"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_cp_stk, callback_data=f"bank_cp:stk:{account_number}")
        kb.button(text=btn_cp_amt, callback_data=f"bank_cp:amt:{exact_vnd}")
        kb.button(text=btn_cp_memo, callback_data=f"bank_cp:memo:{memo}")
        kb.button(text=btn_chk, callback_data=f"bank_chk:{order.id}")
        kb.button(text=btn_cancel, callback_data=f"bank_cancel:{order.id}")
        kb.adjust(2, 1, 1, 1)

        return qr_file, text, kb, order

    @staticmethod
    async def process_and_credit_transactions(bot, session: AsyncSession, target_telegram_id: int = None, target_order_id: int = None) -> list[dict]:
        """
        Quét giao dịch ngân hàng từ ThueApi.pro (endpoint: /historyapibidvv2/:token).
        Tự động phân tích nội dung NAP {telegram_id}, quy đổi tỷ giá và cộng tiền vào tài khoản.
        """
        token = getattr(config, "BANK_BIDV_TOKEN", "") or ""
        token = str(token).strip().strip('"').strip("'")
        if not token:
            logger.info("Chưa cấu hình BANK_BIDV_TOKEN, bỏ qua quét ngân hàng.")
            return []

        url = f"https://thueapi.pro/historyapibidvv2/{token}"
        logger.info(f"Đang kiểm tra giao dịch BIDV qua ThueApi.pro...")

        credited = []
        async with aiohttp.ClientSession() as http_sess:
            try:
                async with http_sess.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning(f"ThueApi.pro trả về status code {resp.status}")
                        return []
                    data = await resp.json()
            except Exception as e:
                logger.error(f"Lỗi kết nối ThueApi.pro: {e}")
                return []

        if not isinstance(data, dict) or data.get("status") != "success":
            logger.warning(f"ThueApi response không thành công: {data}")
            return []

        transactions = data.get("transactions", [])
        if not transactions:
            return []

        rate = float(getattr(config, "BANK_EXCHANGE_RATE", 26000) or 26000)

        for tx in transactions:
            tx_type = str(tx.get("type", "")).upper()
            if tx_type and tx_type != "IN":
                continue

            amount_vnd = float(tx.get("amount", 0) or 0)
            if amount_vnd <= 0:
                continue

            tx_id = str(tx.get("transactionID") or tx.get("id") or "").strip()
            if not tx_id:
                continue

            desc = str(tx.get("description", "") or "").strip()

            # Trích xuất ID từ nội dung chuyển khoản: NAP 123456789 hoặc NAP123456789
            m = re.search(r"NAP\s*(\d+)", desc, re.IGNORECASE)
            if not m:
                continue

            matched_num = int(m.group(1))

            # Kiểm tra xem mã giao dịch này đã được cộng tiền trong DB chưa
            stmt_exist = select(BankDepositOrder).where(BankDepositOrder.transaction_id == tx_id)
            exist_order = (await session.execute(stmt_exist)).scalar_one_or_none()
            if exist_order:
                continue

            # Tìm kiếm người dùng theo Telegram ID
            stmt_u = select(User).where(User.telegram_id == matched_num)
            user = (await session.execute(stmt_u)).scalar_one_or_none()
            matched_tg_id = matched_num

            if not user:
                # Nếu matched_num là order ID
                stmt_ord = select(BankDepositOrder).where(BankDepositOrder.id == matched_num)
                ord_obj = (await session.execute(stmt_ord)).scalar_one_or_none()
                if ord_obj:
                    matched_tg_id = ord_obj.telegram_id
                    stmt_u2 = select(User).where(User.id == ord_obj.user_id)
                    user = (await session.execute(stmt_u2)).scalar_one_or_none()

            if not user:
                continue

            if target_telegram_id and matched_tg_id != target_telegram_id:
                continue

            # Quy đổi VNĐ sang USD
            usd_amount = round(amount_vnd / rate, 2)
            if usd_amount <= 0:
                usd_amount = 0.01

            # Cộng số dư cho User
            user.top_up_amount = round(float(user.top_up_amount or 0.0) + usd_amount, 2)

            # Cập nhật hoặc tạo BankDepositOrder
            stmt_p = select(BankDepositOrder).where(
                BankDepositOrder.telegram_id == matched_tg_id,
                BankDepositOrder.status == "PENDING"
            ).order_by(BankDepositOrder.id.desc())
            pending_order = (await session.execute(stmt_p)).scalar_one_or_none()

            if pending_order:
                pending_order.status = "COMPLETED"
                pending_order.transaction_id = tx_id
                pending_order.amount_vnd = amount_vnd
                pending_order.amount_usd = usd_amount
                order_id = pending_order.id
            else:
                new_order = BankDepositOrder(
                    user_id=user.id,
                    telegram_id=matched_tg_id,
                    bank_code="BIDV",
                    account_number=getattr(config, "BANK_ACCOUNT_NUMBER", "8880117869"),
                    account_name=getattr(config, "BANK_ACCOUNT_NAME", ""),
                    amount_vnd=amount_vnd,
                    amount_usd=usd_amount,
                    memo=f"NAP {matched_tg_id}",
                    transaction_id=tx_id,
                    status="COMPLETED"
                )
                session.add(new_order)
                await session.flush()
                order_id = new_order.id

            # Lưu vào bảng Deposit để đồng bộ lịch sử nạp
            deposit = Deposit(
                user_id=user.id,
                network=Cryptocurrency.USDT_BEP20,
                amount=int(usd_amount * (10 ** 18)),
                fiat_amount=usd_amount,
                deposit_datetime=datetime.now(timezone.utc)
            )
            session.add(deposit)
            await session.commit()

            new_bal = round(user.top_up_amount - (user.consume_records or 0.0), 2)
            logger.info(f"Ting ting! Nạp thành công +{amount_vnd:,.0f}đ (+{usd_amount}$) cho Telegram ID {matched_tg_id}")

            # Gửi tin nhắn thông báo cho khách hàng
            try:
                user_msg = (
                    f"🎉 <b>TING TING! NẠP TIỀN THÀNH CÔNG</b> 🎉\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ <b>Đã nhận:</b> <b>+{amount_vnd:,.0f} đ</b> (~ <b>+{usd_amount}$ USDT</b>)\n"
                    f"🏛️ <b>Cổng nạp:</b> Ngân hàng BIDV (STK <code>{getattr(config, 'BANK_ACCOUNT_NUMBER', '8880117869')}</code>)\n"
                    f"💳 <b>Số dư ví khả dụng hiện tại:</b> <b>{new_bal}$</b>\n"
                    f"🆔 <b>Mã giao dịch:</b> <code>{tx_id}</code>\n"
                    f"📝 <b>Nội dung CK:</b> <code>{desc}</code>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🦐 Cảm ơn bạn đã ủng hộ shop! Hãy bấm <b>🛒 Sản phẩm</b> để mua tài khoản ngay nhé!"
                )
                await bot.send_message(chat_id=matched_tg_id, text=user_msg, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Lỗi gửi thông báo nạp ngân hàng cho {matched_tg_id}: {e}")

            # Gửi thông báo cho Admin
            try:
                admin_msg = (
                    f"💰 <b>[NGÂN HÀNG BIDV] CÓ GIAO DỊCH NẠP MỚI!</b>\n\n"
                    f"👤 Khách hàng: @{user.telegram_username or 'Unknown'} (ID: <code>{matched_tg_id}</code>)\n"
                    f"💵 Số tiền nhận: <b>+{amount_vnd:,.0f} đ</b> (~ <b>+{usd_amount}$</b>)\n"
                    f"🆔 Mã GD ThueApi: <code>{tx_id}</code>\n"
                    f"📝 Nội dung CK: <code>{desc}</code>"
                )
                for aid in getattr(config, "ADMIN_ID_LIST", []):
                    try:
                        await bot.send_message(chat_id=aid, text=admin_msg, parse_mode="HTML")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Lỗi gửi tin nhắn báo admin nạp ngân hàng: {e}")

            credited.append({
                "telegram_id": matched_tg_id,
                "amount_vnd": amount_vnd,
                "amount_usd": usd_amount,
                "transaction_id": tx_id
            })

        # Tự động đánh dấu hết hạn các hoá đơn ngân hàng quá 60 phút
        try:
            expire_cutoff = datetime.now(timezone.utc) - timedelta(minutes=60)
            stmt_exp = update(BankDepositOrder).where(
                BankDepositOrder.status == "PENDING",
                BankDepositOrder.created_at < expire_cutoff
            ).values(status="EXPIRED")
            await session.execute(stmt_exp)
            await session.commit()
        except Exception:
            pass

        return credited

    @staticmethod
    async def check_order_status(order_id: int, session: AsyncSession, bot) -> tuple[bool, BankDepositOrder | None]:
        stmt = select(BankDepositOrder).where(BankDepositOrder.id == order_id)
        order = (await session.execute(stmt)).scalar_one_or_none()
        if not order:
            return False, None

        if order.status == "COMPLETED":
            return True, order

        # Quét ngay ThueApi để kiểm tra giao dịch
        await BankDepositService.process_and_credit_transactions(
            bot=bot,
            session=session,
            target_order_id=order_id
        )
        await session.refresh(order)
        if order.status == "COMPLETED":
            return True, order

        return False, order