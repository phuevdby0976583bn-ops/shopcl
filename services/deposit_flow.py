import random
import logging
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from enums.language import Language
from models.binance_pay import BinancePayOrder
from models.user import User

logger = logging.getLogger(__name__)

USDT_VND_RATE = 26307

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
    def get_method_selection_keyboard(language: Language = Language.VI) -> tuple[str, InlineKeyboardBuilder]:
        if language == Language.VI:
            text = (
                "💰 <b>BẠN MUỐN NẠP TIỀN BẰNG CÁCH NÀO?</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ <b>Khuyên dùng:</b> Binance Pay (0% phí chuyển, nạp tự động nhận ngay sau 1-5 giây).\n"
                "👇 <i>Vui lòng chọn hình thức bên dưới:</i>"
            )
            btn_binance = "🟡 Binance Pay (0% phí - Nhận ngay 1s)"
            btn_onchain = "🌐 Ví / Sàn khác (On-chain BSC, TRX, TON...)"
        else:
            text = (
                "💰 <b>CHOOSE YOUR DEPOSIT METHOD</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "⚡ <b>Recommended:</b> Binance Pay (0% fee, instant credit in 1-5 seconds).\n"
                "👇 <i>Please choose an option below:</i>"
            )
            btn_binance = "🟡 Binance Pay (0% Fee - Instant 1s)"
            btn_onchain = "🌐 Other Wallets / Exchanges (On-chain)"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_binance, callback_data="dep_method:binance")
        kb.button(text=btn_onchain, callback_data="dep_method:onchain")
        kb.adjust(1)
        return text, kb

    @staticmethod
    def get_network_selection_keyboard(language: Language = Language.VI) -> tuple[str, InlineKeyboardBuilder]:
        text = (
            "🌐 <b>CHỌN MẠNG CHUYỂN USDT:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Vui lòng chọn mạng blockchain tương ứng với ví/sàn của bạn:</i>"
            if language == Language.VI else
            "🌐 <b>SELECT USDT NETWORK:</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "<i>Please select the corresponding blockchain network:</i>"
        )
        kb = InlineKeyboardBuilder()
        kb.button(text="BSC - BNB Smart Chain (BEP20)", callback_data="dep_net:BSC")
        kb.button(text="OPBNB - opBNB", callback_data="dep_net:OPBNB")
        kb.button(text="TRX - Tron (TRC20)", callback_data="dep_net:TRX")
        kb.button(text="TON - The Open Network", callback_data="dep_net:TON")
        kb.button(text="CELO", callback_data="dep_net:CELO")
        kb.button(text="ETH - Ethereum (ERC20)", callback_data="dep_net:ETH")
        back_text = "‹ Quay lại" if language == Language.VI else "‹ Back"
        kb.button(text=back_text, callback_data="dep_back:methods")
        kb.adjust(1)
        return text, kb

    @staticmethod
    def get_wallet_address_for_network(network_code: str) -> str:
        evm_address = getattr(config, "BNB_FORWARDING_ADDRESS", "") or getattr(config, "ETH_FORWARDING_ADDRESS", "") or ""
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
    async def create_binance_invoice(telegram_id: int, base_amount: float, session: AsyncSession, language: Language = Language.VI):
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            raise ValueError("Không tìm thấy thông tin người dùng trong hệ thống!")

        binance_uid = (
            getattr(config, "BINANCE_UID", "805398854")
            or getattr(config, "BINANCE_PAY_UID", "805398854")
            or "805398854"
        )

        # Tranh trung lap so duoi le voi cac hoa don PENDING hien tai
        stmt_pending = select(BinancePayOrder.amount).where(BinancePayOrder.status == "PENDING")
        existing_amounts = set(round(float(a), 4) for a in (await session.execute(stmt_pending)).scalars() if a)

        exact_amount = None
        random_sub = None
        for _ in range(100):
            cand_sub = random.randint(11, 99) / 10000.0
            cand_amt = round(base_amount + cand_sub, 4)
            if cand_amt not in existing_amounts:
                exact_amount = cand_amt
                random_sub = cand_sub
                break

        if exact_amount is None:
            random_sub = random.randint(100, 999) / 10000.0
            exact_amount = round(base_amount + random_sub, 4)

        decimal_suffix = f"{random_sub:.4f}"
        rate = getattr(config, "USDT_VND_RATE", USDT_VND_RATE) or USDT_VND_RATE
        vnd_amount = int(round(exact_amount * rate))

        # Luu don hang vao DB
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

        if language == Language.VI:
            text = (
                f"🧾 <b>HOÁ ĐƠN NẠP TIỀN (BINANCE PAY)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Binance Pay ID:</b> <code>{binance_uid}</code>\n"
                f"💰 <b>Số tiền cần chuyển:</b> <code>{exact_amount:.4f}</code> USDT\n"
                f"💵 <b>Quy đổi:</b> {vnd_amount:,}đ (tỷ giá {rate:,}đ/$)\n"
                f"⏳ <b>Hạn thanh toán:</b> 60 phút\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>HƯỚNG DẪN CHUYỂN TIỀN:</b>\n"
                f"1️⃣ Mở app <b>Binance</b> ➔ Chọn mục <b>Pay</b>\n"
                f"2️⃣ Chọn <b>Gửi (Send)</b> tới Binance Pay ID: <code>{binance_uid}</code>\n"
                f"3️⃣ Nhập <b>CHÍNH XÁC</b> số tiền: <code>{exact_amount:.4f}</code> USDT\n"
                f"4️⃣ Xác nhận chuyển ➔ <b>Hệ thống tự động cộng tiền trong 1-5 giây!</b>\n\n"
                f"💡 <i>Con số lẻ {decimal_suffix} giúp hệ thống tự động nhận diện giao dịch của bạn, bạn vẫn nhận đủ 100% số tiền đã chuyển.</i>"
            )
            btn_cp_id = "📋 Sao chép Pay ID"
            btn_cp_amt = "📋 Sao chép số tiền"
            btn_check = "🔄 Kiểm tra giao dịch"
            btn_cancel = "❌ Huỷ hoá đơn"
        else:
            text = (
                f"🧾 <b>USDT INVOICE (BINANCE PAY)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Binance Pay ID:</b> <code>{binance_uid}</code>\n"
                f"💰 <b>Transfer Amount:</b> <code>{exact_amount:.4f}</code> USDT\n"
                f"💵 <b>Approx. VND:</b> {vnd_amount:,}đ (rate {rate:,}đ/$)\n"
                f"⏳ <b>Expires in:</b> 60 minutes\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>TRANSFER INSTRUCTIONS:</b>\n"
                f"1️⃣ Open <b>Binance App</b> ➔ Tap <b>Pay</b>\n"
                f"2️⃣ Choose <b>Send</b> to Binance Pay ID: <code>{binance_uid}</code>\n"
                f"3️⃣ Enter <b>EXACTLY</b> the amount: <code>{exact_amount:.4f}</code> USDT\n"
                f"4️⃣ Confirm transfer ➔ <b>Your balance will be credited automatically in 1-5s!</b>\n\n"
                f"💡 <i>The decimal suffix {decimal_suffix} helps identify your payment automatically; you receive 100% of the funds.</i>"
            )
            btn_cp_id = "📋 Copy Pay ID"
            btn_cp_amt = "📋 Copy Amount"
            btn_check = "🔄 Check Transaction"
            btn_cancel = "❌ Cancel Invoice"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_cp_id, callback_data=f"dep_cp:id:{binance_uid}")
        kb.button(text=btn_cp_amt, callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text=btn_check, callback_data=f"dep_chk:{order.id}")
        kb.button(text=btn_cancel, callback_data=f"dep_cancel:{order.id}")
        kb.adjust(2, 1, 1)

        return text, kb, order

    @staticmethod
    async def create_onchain_invoice(telegram_id: int, network_code: str, base_amount: float, session: AsyncSession, language: Language = Language.VI):
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            raise ValueError("Không tìm thấy thông tin người dùng trong hệ thống!")

        network_name = NETWORK_DISPLAY_NAMES.get(network_code, network_code)
        wallet_address = DepositFlowService.get_wallet_address_for_network(network_code)

        random_sub = random.randint(10, 99) / 10000.0
        exact_amount = round(base_amount + random_sub, 4)
        decimal_suffix = f"{random_sub:.4f}"

        rate = getattr(config, "USDT_VND_RATE", USDT_VND_RATE) or USDT_VND_RATE
        vnd_amount = int(round(exact_amount * rate))

        if language == Language.VI:
            text = (
                f"🧾 <b>HOÁ ĐƠN NẠP TIỀN (ON-CHAIN)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>Mạng:</b> <b>{network_name}</b>\n"
                f"📫 <b>Địa chỉ ví:</b> <code>{wallet_address}</code>\n"
                f"💰 <b>Số tiền cần chuyển:</b> <code>{exact_amount:.4f}</code> USDT\n"
                f"💵 <b>Quy đổi:</b> {vnd_amount:,}đ (tỷ giá {rate:,}đ/$)\n"
                f"⏳ <b>Hạn thanh toán:</b> 60 phút\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>LƯU Ý QUAN TRỌNG:</b>\n"
                f"• Chuyển ĐÚNG <code>{exact_amount:.4f}</code> USDT (chưa bao gồm phí rút của sàn/ví) qua mạng <b>{network_name}</b>.\n"
                f"• Gửi sai mạng hoặc sai loại coin sẽ bị mất tiền vĩnh viễn!\n"
                f"• Con số lẻ {decimal_suffix} không phải là phí, bạn vẫn nhận đủ số tiền đã chuyển."
            )
            btn_cp_addr = "📋 Sao chép địa chỉ ví"
            btn_cp_amt = "📋 Sao chép số tiền"
            btn_cancel = "❌ Huỷ hoá đơn"
        else:
            text = (
                f"🧾 <b>USDT INVOICE (ON-CHAIN)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>Network:</b> <b>{network_name}</b>\n"
                f"📫 <b>Wallet Address:</b> <code>{wallet_address}</code>\n"
                f"💰 <b>Transfer Amount:</b> <code>{exact_amount:.4f}</code> USDT\n"
                f"💵 <b>Approx. VND:</b> {vnd_amount:,}đ (rate {rate:,}đ/$)\n"
                f"⏳ <b>Expires in:</b> 60 minutes\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ <b>IMPORTANT NOTE:</b>\n"
                f"• Send EXACTLY <code>{exact_amount:.4f}</code> USDT on {network_name}.\n"
                f"• Sending to the wrong network will result in permanent loss!\n"
                f"• The decimal suffix {decimal_suffix} is not a fee; you receive 100% of your funds."
            )
            btn_cp_addr = "📋 Copy Address"
            btn_cp_amt = "📋 Copy Amount"
            btn_cancel = "❌ Cancel Invoice"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_cp_addr, callback_data=f"dep_cp:addr:{wallet_address}")
        kb.button(text=btn_cp_amt, callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text=btn_cancel, callback_data="dep_cancel:onchain")
        kb.adjust(2, 1)

        return text, kb
