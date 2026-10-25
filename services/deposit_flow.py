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
    def generate_binance_qr(binance_uid: str, amount: float) -> BufferedInputFile:
        """Sinh ma QR co logo Binance o giua theo mau MetakingBot."""
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=3
        )
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
        return BufferedInputFile(file=buffer.getvalue(), filename=f"binance_pay_{amount:.4f}.png")

    @staticmethod
    def generate_clean_qr(data: str) -> BufferedInputFile:
        """Sinh ma QR sach cho dia chi vi on-chain giong MetakingBot."""
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(file=buffer.getvalue(), filename="onchain_address_qr.png")

    @staticmethod
    def get_method_selection_keyboard(language: Language = Language.VI) -> tuple[str, InlineKeyboardBuilder]:
        methods_dict = {
            Language.VI: {
                "text": (
                    "💰 <b>BẠN MUỐN NẠP TIỀN BẰNG CÁCH NÀO?</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Ngân Hàng Việt Nam:</b> Quét mã VietQR chuyển khoản BIDV, tự động cộng tiền 10s.\n"
                    "⚡ <b>Binance Pay:</b> 0% phí chuyển, nạp tự động nhận ngay sau 1-5 giây.\n"
                    "🌐 <b>On-chain:</b> Nạp qua USDT các mạng BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Vui lòng chọn hình thức bên dưới:</i>"
                ),
                "bank": "🏦 Chuyển khoản Ngân hàng (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% phí - Nhận ngay 1s)",
                "onchain": "🌐 Ví / Sàn khác (On-chain BSC, TRX, TON...)"
            },
            Language.EN: {
                "text": (
                    "💰 <b>CHOOSE YOUR DEPOSIT METHOD</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Vietnam Bank:</b> VietQR instant transfer (BIDV), auto-credit in 10s.\n"
                    "⚡ <b>Binance Pay:</b> 0% fee, instant credit in 1-5 seconds.\n"
                    "🌐 <b>On-chain:</b> Deposit USDT via BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Please choose an option below:</i>"
                ),
                "bank": "🏦 Vietnam Bank Transfer (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% Fee - Instant 1s)",
                "onchain": "🌐 Other Wallets / Exchanges (On-chain)"
            },
            Language.HI: {
                "text": (
                    "💰 <b>जमा विधि चुनें</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>वियतनाम बैंक:</b> VietQR त्वरित स्थानांतरण (BIDV), 10 सेकंड में स्वतः जमा।\n"
                    "⚡ <b>Binance Pay:</b> 0% शुल्क, 1-5 सेकंड में त्वरित जमा।\n"
                    "🌐 <b>On-chain:</b> BSC, Solana, Tron, ERC20 के माध्यम से USDT जमा करें।\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>कृपया नीचे दिए गए विकल्पों में से चुनें:</i>"
                ),
                "bank": "🏦 वियतनाम बैंक (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% शुल्क - 1s)",
                "onchain": "🌐 अन्य वॉलेट / एक्सचेंज (On-chain)"
            },
            Language.ZH: {
                "text": (
                    "💰 <b>请选择充值方式</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>越南银行：</b> VietQR 扫码转账 (BIDV)，10秒自动到账。\n"
                    "⚡ <b>币安支付 (Binance Pay)：</b> 0 手续费，1-5秒全自动秒到。\n"
                    "🌐 <b>链上充值 (On-chain)：</b> 支持 BSC、Tron、Solana 等多链。\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>请在下方选择充值通道：</i>"
                ),
                "bank": "🏦 越南银行转账 (VietQR / BIDV)",
                "binance": "🟡 币安支付 Binance Pay (0费率 - 秒到)",
                "onchain": "🌐 链上充值 (On-chain BSC, TRX, TON...)"
            },
            Language.FR: {
                "text": (
                    "💰 <b>CHOISISSEZ VOTRE MODE DE DÉPÔT</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Banque Vietnam :</b> Virement VietQR (BIDV), crédit auto en 10s.\n"
                    "⚡ <b>Binance Pay :</b> 0% frais, crédit instantané en 1-5 secondes.\n"
                    "🌐 <b>On-chain :</b> USDT via BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Veuillez choisir une option ci-dessous :</i>"
                ),
                "bank": "🏦 Virement bancaire Vietnam (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% Frais - Instant 1s)",
                "onchain": "🌐 Autres portefeuilles (On-chain)"
            },
            Language.DE: {
                "text": (
                    "💰 <b>WÄHLEN SIE IHRE EINZAHLUNGSMETHODE</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Vietnam Bank:</b> VietQR Überweisung (BIDV), automatische Gutschrift in 10s.\n"
                    "⚡ <b>Binance Pay:</b> 0% Gebühr, Sofortgutschrift in 1-5 Sekunden.\n"
                    "🌐 <b>On-chain:</b> USDT über BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Bitte wählen Sie unten eine Option:</i>"
                ),
                "bank": "🏦 Banküberweisung Vietnam (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% Gebühr - Sofort 1s)",
                "onchain": "🌐 Andere Wallets (On-chain)"
            },
            Language.IT: {
                "text": (
                    "💰 <b>SCEGLI IL TUO METODO DI DEPOSITO</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Banca Vietnam:</b> Bonifico VietQR (BIDV), accredito auto in 10s.\n"
                    "⚡ <b>Binance Pay:</b> 0% commissioni, accredito istantaneo in 1-5 secondi.\n"
                    "🌐 <b>On-chain:</b> Deposita USDT via BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Scegli un'opzione qui sotto:</i>"
                ),
                "bank": "🏦 Bonifico bancario Vietnam (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% Commissioni - Immediato 1s)",
                "onchain": "🌐 Altri portafogli (On-chain)"
            },
            Language.ES: {
                "text": (
                    "💰 <b>ELIGE TU MÉTODO DE DEPÓSITO</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🏦 <b>Banco Vietnam:</b> Transferencia VietQR (BIDV), acreditación auto en 10s.\n"
                    "⚡ <b>Binance Pay:</b> 0% comisión, acreditación instantánea en 1-5 segundos.\n"
                    "🌐 <b>On-chain:</b> Depósito USDT vía BSC, Solana, Tron, ERC20.\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "👇 <i>Por favor, selecciona una opción:</i>"
                ),
                "bank": "🏦 Transferencia bancaria Vietnam (VietQR / BIDV)",
                "binance": "🟡 Binance Pay (0% Comisión - Instant 1s)",
                "onchain": "🌐 Otras billeteras (On-chain)"
            }
        }
        cfg = methods_dict.get(language, methods_dict[Language.EN])
        text = cfg["text"]
        btn_bank = cfg["bank"]
        btn_binance = cfg["binance"]
        btn_onchain = cfg["onchain"]

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_bank, callback_data="dep_method:bank")
        kb.button(text=btn_binance, callback_data="dep_method:binance")
        kb.button(text=btn_onchain, callback_data="dep_method:onchain")
        kb.adjust(1)
        return text, kb

    @staticmethod
    def get_network_selection_keyboard(language: Language = Language.VI) -> tuple[str, InlineKeyboardBuilder]:
        prompts = {
            Language.VI: ("🌐 <b>CHỌN MẠNG CHUYỂN USDT:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Vui lòng chọn mạng blockchain tương ứng với ví/sàn của bạn:</i>", "‹ Quay lại"),
            Language.EN: ("🌐 <b>SELECT USDT NETWORK:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Please select the corresponding blockchain network:</i>", "‹ Back"),
            Language.HI: ("🌐 <b>USDT नेटवर्क चुनें:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>कृपया संगत ब्लॉकचेन नेटवर्क चुनें:</i>", "‹ वापस"),
            Language.ZH: ("🌐 <b>选择 USDT 充值网络：</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>请选择与您的钱包或交易所对应的网络：</i>", "‹ 返回"),
            Language.FR: ("🌐 <b>SÉLECTIONNEZ LE RÉSEAU USDT :</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Veuillez sélectionner le réseau blockchain correspondant :</i>", "‹ Retour"),
            Language.DE: ("🌐 <b>USDT-NETZWERK WÄHLEN:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Bitte wählen Sie das entsprechende Blockchain-Netzwerk:</i>", "‹ Zurück"),
            Language.IT: ("🌐 <b>SELEZIONA RETE USDT:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Seleziona la rete blockchain corrispondente:</i>", "‹ Indietro"),
            Language.ES: ("🌐 <b>SELECCIONA RED USDT:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n<i>Selecciona la red blockchain correspondiente:</i>", "‹ Volver")
        }
        text, back_text = prompts.get(language, prompts[Language.EN])
        kb = InlineKeyboardBuilder()
        kb.button(text="BSC - BNB Smart Chain (BEP20)", callback_data="dep_net:BSC")
        kb.button(text="OPBNB - opBNB", callback_data="dep_net:OPBNB")
        kb.button(text="TRX - Tron (TRC20)", callback_data="dep_net:TRX")
        kb.button(text="TON - The Open Network", callback_data="dep_net:TON")
        kb.button(text="CELO", callback_data="dep_net:CELO")
        kb.button(text="ETH - Ethereum (ERC20)", callback_data="dep_net:ETH")
        
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
            from models.user import UserDTO
            from services.user import UserService
            await UserService.create_if_not_exist(UserDTO(telegram_id=telegram_id), session)
            user = (await session.execute(stmt_u)).scalar_one_or_none()

        binance_uid = (
            getattr(config, "BINANCE_UID", "805398854")
            or getattr(config, "BINANCE_PAY_UID", "805398854")
            or "805398854"
        )

        # Tránh trùng lặp số đuôi lẻ với các hoá đơn PENDING hiện tại
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

        # Lưu đơn hàng vào DB
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

        if language == Language.VI:
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
            btn_cp_id = "📋 Sao chép Pay ID"
            btn_cp_amt = "📋 Sao chép số tiền"
            btn_cancel = "❌ Huỷ hoá đơn"
            btn_check = "🔄 Kiểm tra giao dịch"
        else:
            caption = (
                f"🧾 <b>USDT Invoice</b>\n\n"
                f"Binance Pay ID: <code>{binance_uid}</code>\n"
                f"Transfer amount: <code>{exact_amount:.4f}</code> USDT\n"
                f"Approx. VND: {vnd_amount:,}đ\n"
                f"Expected received: {vnd_amount:,}đ (rate {rate:,}đ/USDT)\n"
                f"Expires: 60 minutes\n\n"
                f"⚠️ Transfer EXACTLY <code>{exact_amount:.4f}</code> USDT via Binance Pay to the ID above. "
                f"System will auto-credit in 1-2 minutes.\n"
                f"The decimal {decimal_suffix} is not a fee, you still receive the full amount."
            )
            btn_cp_id = "📋 Copy Pay ID"
            btn_cp_amt = "📋 Copy Amount"
            btn_cancel = "❌ Cancel Invoice"
            btn_check = "🔄 Check Transaction"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_cp_id, callback_data=f"dep_cp:id:{binance_uid}")
        kb.button(text=btn_cp_amt, callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text=btn_cancel, callback_data=f"dep_cancel:{order.id}")
        kb.button(text=btn_check, callback_data=f"dep_chk:{order.id}")
        kb.adjust(2, 2)

        return qr_file, caption, kb, order

    @staticmethod
    async def create_onchain_invoice(telegram_id: int, network_code: str, base_amount: float, session: AsyncSession, language: Language = Language.VI):
        stmt_u = select(User).where(User.telegram_id == telegram_id)
        user = (await session.execute(stmt_u)).scalar_one_or_none()
        if not user:
            from models.user import UserDTO
            from services.user import UserService
            await UserService.create_if_not_exist(UserDTO(telegram_id=telegram_id), session)
            user = (await session.execute(stmt_u)).scalar_one_or_none()

        network_name = NETWORK_DISPLAY_NAMES.get(network_code, network_code)
        wallet_address = DepositFlowService.get_wallet_address_for_network(network_code)

        random_sub = random.randint(10, 99) / 10000.0
        exact_amount = round(base_amount + random_sub, 4)
        decimal_suffix = f"{random_sub:.4f}"

        rate = getattr(config, "USDT_VND_RATE", USDT_VND_RATE) or USDT_VND_RATE
        vnd_amount = int(round(exact_amount * rate))

        qr_file = DepositFlowService.generate_clean_qr(wallet_address)

        if language == Language.VI:
            caption = (
                f"🧾 <b>Hoá đơn nạp USDT</b>\n\n"
                f"Mạng: {network_name}\n"
                f"Địa chỉ ví: <code>{wallet_address}</code>\n"
                f"Số tiền chuyển: <code>{exact_amount:.4f}</code> USDT\n"
                f"Tiền nạp quy đổi: {vnd_amount:,}đ\n"
                f"Tổng dự kiến nhận: {vnd_amount:,}đ (tỷ giá {rate:,}đ/USDT)\n"
                f"Hết hạn: 60 phút\n\n"
                f"⚠️ Chuyển ĐÚNG <code>{exact_amount:.4f}</code> USDT (chưa bao gồm phí chuyển của sàn) qua mạng {network_name}. Gửi sai mạng hoặc sai coin sẽ MẤT TIỀN!\n"
                f"Con số lẻ {decimal_suffix} không phải là phí, bạn vẫn nhận được đủ số tiền đã chuyển."
            )
            btn_cp_addr = "📋 Sao chép địa chỉ ví"
            btn_cp_amt = "📋 Sao chép số tiền"
            btn_cancel = "❌ Huỷ hoá đơn"
        else:
            caption = (
                f"🧾 <b>USDT Invoice</b>\n\n"
                f"Network: {network_name}\n"
                f"Wallet Address: <code>{wallet_address}</code>\n"
                f"Transfer Amount: <code>{exact_amount:.4f}</code> USDT\n"
                f"Approx. VND: {vnd_amount:,}đ (rate {rate:,}đ/USDT)\n"
                f"Expires in: 60 minutes\n\n"
                f"⚠️ Send EXACTLY <code>{exact_amount:.4f}</code> USDT on {network_name}.\n"
                f"The decimal suffix {decimal_suffix} is not a fee; you receive 100% of your funds."
            )
            btn_cp_addr = "📋 Copy Address"
            btn_cp_amt = "📋 Copy Amount"
            btn_cancel = "❌ Cancel Invoice"

        kb = InlineKeyboardBuilder()
        kb.button(text=btn_cp_addr, callback_data=f"dep_cp:addr:{wallet_address}")
        kb.button(text=btn_cp_amt, callback_data=f"dep_cp:amt:{exact_amount:.4f}")
        kb.button(text=btn_cancel, callback_data="dep_cancel:onchain")
        kb.adjust(2, 1)

        return qr_file, caption, kb
