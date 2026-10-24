import io
import random
import logging
import qrcode
from PIL import Image, ImageDraw
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models.binance_pay import BinancePayOrder
from models.user import User

logger = logging.getLogger(__name__)

USDT_VND_RATE = 26185

NETWORK_DISPLAY_NAMES = {
    "BSC": "BSC - BNB Smart Chain (BEP20)",
    "OPBNB": "OPBNB - opBNB",
    "TRX": "TRX - Tron (TRC20)",
    "TON": "TON - The Open Network",
    "CELO": "CELO",
    "ETH": "ETH - Ethereum (ERC20)",
}


class DepositFlowService:
    @staticmethod
    def generate_binance_qr(binance_uid: str, amount: float) -> BufferedInputFile:
        """Sinh ma QR co logo Binance o giua giong y het hinh anh minh hoa cua ban."""
        qr = qrcode.QRCode(box_size=10, border=3)
        qr.add_data(f"binance://pay?receiver={binance_uid}&amount={amount:.4f}")
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        w, h = img.size

        # Ve khung vuong bo goc mau vang o giua
        box_size = int(w * 0.22)
        x0 = (w - box_size) // 2
        y0 = (h - box_size) // 2
        x1 = x0 + box_size
        y1 = y0 + box_size

        draw = ImageDraw.Draw(img)
        pad = 6
        draw.rounded_rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], radius=14, fill="white")
        draw.rounded_rectangle([x0, y0, x1, y1], radius=10, fill="#F0B90B")

        # Ve bieu tuong kim cuong Binance o giua
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        r = box_size // 3
        draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill="black")
        r_inner = r // 2
        draw.polygon([(cx, cy - r_inner), (cx + r_inner, cy), (cx, cy + r_inner), (cx - r_inner, cy)], fill="#F0B90B")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(file=buffer.getvalue(), filename="binance_pay_qr.png")

    @staticmethod
    def generate_clean_qr(data: str) -> BufferedInputFile:
        """Sinh ma QR sach cho dia chi vi on-chain."""
        qr = qrcode.QRCode(box_size=10, border=3)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(file=buffer.getvalue(), filename="crypto_address_qr.png")

    @staticmethod
    def get_method_selection_keyboard() -> tuple[str, InlineKeyboardBuilder]:
        text = "Bạn muốn nạp tiền bằng cách nào?"
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Binance Pay (miễn phí)", callback_data="dep_method:binance")
        kb.button(text="🔄 Ví / sàn khác", callback_data="dep_method:onchain")
        kb.adjust(1)
        return text, kb

    @staticmethod
    def get_network_selection_keyboard() -> tuple[str, InlineKeyboardBuilder]:
        text = "Chọn mạng chuyển:"
        kb = InlineKeyboardBuilder()
        kb.button(text="BSC - BNB Smart Chain (BEP20)", callback_data="dep_net:BSC")
        kb.button(text="OPBNB - opBNB", callback_data="dep_net:OPBNB")
        kb.button(text="TRX - Tron (TRC20)", callback_data="dep_net:TRX")
        kb.button(text="TON - The Open Network", callback_data="dep_net:TON")
        kb.button(text="CELO", callback_data="dep_net:CELO")
        kb.button(text="ETH - Ethereum (ERC20)", callback_data="dep_net:ETH")
        kb.button(text="‹ Quay lại", callback_data="dep_back:methods")
        kb.adjust(1)
        return text, kb

    @staticmethod
    def get_wallet_address_for_network(network_code: str) -> str:
        """Lay dia chi vi phu hop cho tung mang luoi blockchain."""
        evm_address = getattr(config, "BNB_FORWARDING_ADDRESS", "") or getattr(config, "ETH_FORWARDING_ADDRESS", "") or ""
        sol_address = getattr(config, "SOL_FORWARDING_ADDRESS", "") or ""

        fallback_evm = "0x117a8781fdd17c14733034c8d16058dd730b3772"
        fallback_trx = "TPyVzXU2j8K6uGf6BvWwP8uC7vM7yN9kL2"
        fallback_ton = "EQBvW8m53GQv-S2Yj6ffTWPjYzLzP8xK6vM7yN9kL2uC7vM"

        if network_code in ("BSC", "OPBNB", "CELO", "ETH"):
            return evm_address if evm_address else fallback_evm
        elif network_code == "TRX":
            return fallback_trx
        elif network_code == "TON":
            return fallback_ton
        return evm_address if evm_address else fallback_evm

    @staticmethod
    async def create_binance_invoice(telegram_id: int, base_amount: float, session: AsyncSession):
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            raise ValueError("Không tìm thấy thông tin người dùng!")

        binance_uid = getattr(config, "BINANCE_UID", "805398854") or "805398854"

        # Sinh so duoi le ngau nhien (VD: 0.0050 hoac 0.0012)
        random_sub = random.randint(10, 99) / 10000.0
        exact_amount = round(base_amount + random_sub, 4)
        decimal_suffix = f"{random_sub:.4f}"

        rate = USDT_VND_RATE
        vnd_amount = int(round(exact_amount * rate))

        # Luu order vao DB
        order = BinancePayOrder(
            user_id=user.id,
            telegram_id=telegram_id,
            memo=f"NAP {telegram_id}",
            amount=exact_amount,
            status="PENDING"
        )
        session.add(order)
        await session.commit()
        await session.refresh(order)

        qr_file = DepositFlowService.generate_binance_qr(binance_uid, exact_amount)

        caption = (
            f"🧾 <b>Hoá đơn nạp USDT</b>\n\n"
            f"Binance Pay ID: <code>{binance_uid}</code>\n"
            f"Số tiền chuyển: <code>{exact_amount:.4f}</code> USDT\n"
            f"Tiền nạp quy đổi: {vnd_amount:,}đ\n"
            f"Tổng dự kiến nhận: {vnd_amount:,}đ (tỷ giá {rate:,}đ/USDT)\n"
            f"Hết hạn: 60 phút\n\n"
            f"⚠️ Chuyển ĐÚNG <code>{exact_amount:.4f}</code> USDT qua Binance Pay tới ID trên. "
            f"Hệ thống tự cộng tiền trong 1-2 phút.\n"
            f"Con số lẻ {decimal_suffix} không phải là phí, bạn vẫn nhận được đủ số tiền đã chuyển."
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Sao chép Pay ID", callback_data=f"dep_cp:id:{binance_uid}")
        kb.button(text="📋 Sao chép số tiền", callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text="❌ Huỷ hoá đơn", callback_data=f"dep_cancel:{order.id}")
        kb.adjust(2, 1)

        return qr_file, caption, kb

    @staticmethod
    async def create_onchain_invoice(telegram_id: int, network_code: str, base_amount: float, session: AsyncSession):
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            raise ValueError("Không tìm thấy thông tin người dùng!")

        network_name = NETWORK_DISPLAY_NAMES.get(network_code, network_code)
        wallet_address = DepositFlowService.get_wallet_address_for_network(network_code)

        random_sub = random.randint(10, 99) / 10000.0
        exact_amount = round(base_amount + random_sub, 4)
        decimal_suffix = f"{random_sub:.4f}"

        rate = USDT_VND_RATE
        vnd_amount = int(round(exact_amount * rate))

        qr_file = DepositFlowService.generate_clean_qr(wallet_address)

        caption = (
            f"🧾 <b>Hoá đơn nạp USDT</b>\n\n"
            f"Mạng: {network_name}\n"
            f"Địa chỉ ví: <code>{wallet_address}</code>\n"
            f"Số tiền chuyển: <code>{exact_amount:.4f}</code> USDT\n"
            f"Tiền nạp quy đổi: {vnd_amount:,}đ\n"
            f"Tổng dự kiến nhận: {vnd_amount:,}đ (tỷ giá {rate:,}đ/USDT)\n"
            f"Hết hạn: 60 phút\n\n"
            f"⚠️ Chuyển ĐÚNG <code>{exact_amount:.4f}</code> USDT (chưa bao gồm phí chuyển của sàn) "
            f"qua mạng {network_name}. Gửi sai mạng hoặc sai coin sẽ MẤT TIỀN!\n"
            f"Con số lẻ {decimal_suffix} không phải là phí, bạn vẫn nhận được đủ số tiền đã chuyển."
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="📋 Sao chép địa chỉ ví", callback_data=f"dep_cp:addr:{wallet_address}")
        kb.button(text="📋 Sao chép số tiền", callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text="❌ Huỷ hoá đơn", callback_data="dep_cancel:onchain")
        kb.adjust(2, 1)

        return qr_file, caption, kb
