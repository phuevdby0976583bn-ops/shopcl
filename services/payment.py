import io
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import qrcode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InputMediaPhoto, BufferedInputFile, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

import config
from callbacks import MyProfileCallback
from crypto_api.CryptoApiWrapper import CryptoApiWrapper
from db import session_commit
from enums.bot_entity import BotEntity
from enums.cryptocurrency import Cryptocurrency
from enums.language import Language
from enums.payment import PaymentType
from handlers.user.constants import UserStates
from models.payment import ProcessingPaymentDTO
from repositories.payment import PaymentRepository
from repositories.user import UserRepository
from utils.utils import get_text, get_bot_photo_id
from services.deposit_bonus import DepositBonusService


class PaymentService:
    AMOUNT_RE = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d{1,2})?$")

    @staticmethod
    def __create_qr_code(payment_dto: ProcessingPaymentDTO) -> BufferedInputFile:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=3
        )
        qr.add_data(payment_dto.address)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return BufferedInputFile(
            file=buffer.getvalue(),
            filename=f"{payment_dto.address[:10]}.png"
        )

    @staticmethod
    async def __create_invoice(payment_dto: ProcessingPaymentDTO) -> ProcessingPaymentDTO:
        return await CryptoApiWrapper.create_invoice(payment_dto)

    @staticmethod
    def __request_fiat_amount(kb_builder: InlineKeyboardBuilder, language: Language, error_text: str | None = None):
        kb_builder.button(
            text=get_text(language, BotEntity.COMMON, "back_button"),
            callback_data=MyProfileCallback.create(level=1)
        )
        bot_photo_id = get_bot_photo_id()
        min_deposit = float(getattr(config, "MIN_DEPOSIT_USDT", 1.0) or 1.0)
        base_prompt = f"Nhập số USDT muốn nạp (tối thiểu {min_deposit:g}):" if language == Language.VI else f"Enter USDT amount to deposit (min {min_deposit:g}):"
        bonus_text = DepositBonusService.get_bonus_display_text(language)
        request_caption = f"{base_prompt}\n\n{bonus_text}".strip() if bonus_text else base_prompt
        caption = request_caption if error_text is None else f"{error_text}\n\n{request_caption}"
        return InputMediaPhoto(media=bot_photo_id, caption=caption), kb_builder

    @staticmethod
    def _parse_fiat_amount(raw_amount: str | None) -> Decimal | None:
        if raw_amount is None:
            return None
        normalized_amount = raw_amount.strip()
        if not PaymentService.AMOUNT_RE.fullmatch(normalized_amount):
            return None
        try:
            parsed_amount = Decimal(normalized_amount)
        except InvalidOperation:
            return None
        min_deposit = Decimal(str(getattr(config, "MIN_DEPOSIT_USDT", 1.0) or 1.0))
        if parsed_amount < min_deposit or parsed_amount >= Decimal("1000000"):
            return None
        return parsed_amount

    @staticmethod
    async def create(callback: CallbackQuery | Message,
                     callback_data: MyProfileCallback | None,
                     state: FSMContext,
                     session: AsyncSession,
                     language: Language) -> tuple[InputMediaPhoto | str, InlineKeyboardBuilder]:
        from services.settings import SettingsService
        await SettingsService.load_settings_into_config(session)

        user = await UserRepository.get_by_tgid(callback.from_user.id, session)
        unexpired_payments_count = await PaymentRepository.get_unexpired_unpaid_payments(user.id, session)
        state_data = await state.get_data()
        current_state = await state.get_state()
        kb_builder = InlineKeyboardBuilder()

        if callback_data is None:
            stored_cryptocurrency = state_data.get('cryptocurrency')
            if stored_cryptocurrency is None:
                await state.set_state(UserStates.top_up_amount)
                return PaymentService.__request_fiat_amount(
                    kb_builder,
                    language,
                    get_text(language, BotEntity.USER, "top_up_balance_invalid_fiat_amount").format(
                        currency_text=config.CURRENCY.get_localized_text()
                    )
                )
            cryptocurrency = Cryptocurrency(stored_cryptocurrency)
        else:
            cryptocurrency = callback_data.cryptocurrency

        if unexpired_payments_count >= 15:
            kb_builder.row(callback_data.get_back_button(language))
            return get_text(language, BotEntity.USER, "too_many_payment_request"), kb_builder

        elif cryptocurrency in Cryptocurrency.get_stablecoins() and current_state is None:
            await state.set_state(UserStates.top_up_amount)
            await state.update_data(cryptocurrency=cryptocurrency.value)
            return PaymentService.__request_fiat_amount(kb_builder, language)

        elif cryptocurrency in Cryptocurrency.get_stablecoins() and current_state == UserStates.top_up_amount:
            message: Message = callback
            fiat_amount = PaymentService._parse_fiat_amount(message.text or message.html_text)
            if fiat_amount is None:
                return PaymentService.__request_fiat_amount(
                    kb_builder,
                    language,
                    get_text(language, BotEntity.USER, "top_up_balance_invalid_fiat_amount").format(
                        currency_text=config.CURRENCY.get_localized_text()
                    )
                )

            await state.set_state()
            payment_dto = ProcessingPaymentDTO(
                paymentType=PaymentType.PAYMENT,
                fiatCurrency=config.CURRENCY,
                cryptoCurrency=cryptocurrency,
                fiatAmount=float(fiat_amount)
            )

            loading_msg = await message.answer("⏳ Đang tạo hoá đơn thanh toán qua KryptoExpress...")
            try:
                payment_dto = await PaymentService.__create_invoice(payment_dto)
            finally:
                try:
                    await loading_msg.delete()
                except Exception:
                    pass

            msg_id = getattr(message, "message_id", 0)
            await PaymentRepository.create(payment_dto.id, user.id, msg_id, session)
            await session_commit(session)

            rate = getattr(config, "USDT_VND_RATE", 26307) or 26307
            vnd_amount = int(round(payment_dto.fiatAmount * rate))
            network_name = payment_dto.cryptoCurrency.name.replace("_", " ")

            if language == Language.VI:
                caption = (
                    f"🧾 <b>Hoá đơn nạp {payment_dto.cryptoCurrency.name.split('_')[0]}</b>\n\n"
                    f"Mạng: {network_name}\n"
                    f"Địa chỉ ví: <code>{payment_dto.address}</code>\n"
                    f"Số tiền chuyển: <code>{payment_dto.cryptoAmount}</code> {payment_dto.cryptoCurrency.name.split('_')[0]}\n"
                    f"Tiền nạp quy đổi: {vnd_amount:,}đ\n"
                    f"Tổng dự kiến nhận: {vnd_amount:,}đ (tỷ giá {rate:,}đ/USDT)\n"
                    f"Hết hạn: 60 phút\n\n"
                    f"⚠️ Chuyển ĐÚNG <code>{payment_dto.cryptoAmount}</code> (chưa bao gồm phí chuyển của sàn) qua mạng {network_name}. Gửi sai mạng hoặc sai coin sẽ MẤT TIỀN!\n"
                )
                btn_cp_addr = "📋 Sao chép địa chỉ ví"
                btn_cp_amt = "📋 Sao chép số tiền"
                btn_cancel = "❌ Huỷ hoá đơn"
            else:
                caption = (
                    f"🧾 <b>Invoice {payment_dto.cryptoCurrency.name.split('_')[0]}</b>\n\n"
                    f"Network: {network_name}\n"
                    f"Wallet Address: <code>{payment_dto.address}</code>\n"
                    f"Transfer Amount: <code>{payment_dto.cryptoAmount}</code> {payment_dto.cryptoCurrency.name.split('_')[0]}\n"
                    f"Approx. VND: {vnd_amount:,}đ (rate {rate:,}đ/USDT)\n"
                    f"Expires in: 60 minutes\n\n"
                    f"⚠️ Send EXACTLY <code>{payment_dto.cryptoAmount}</code> on {network_name}."
                )
                btn_cp_addr = "📋 Copy Address"
                btn_cp_amt = "📋 Copy Amount"
                btn_cancel = "❌ Cancel Invoice"

            kb_builder.button(text=btn_cp_addr, callback_data=f"dep_cp:addr:{payment_dto.address}")
            kb_builder.button(text=btn_cp_amt, callback_data=f"dep_cp:amt:{payment_dto.cryptoAmount}")
            kb_builder.button(text=btn_cancel, callback_data="dep_cancel:krypto")
            kb_builder.adjust(2, 1)

            qr_code_file = PaymentService.__create_qr_code(payment_dto)
            return InputMediaPhoto(media=qr_code_file, caption=caption), kb_builder

        else:
            payment_dto = ProcessingPaymentDTO(
                paymentType=PaymentType.DEPOSIT,
                fiatCurrency=config.CURRENCY,
                cryptoCurrency=cryptocurrency
            )
            payment_dto = await PaymentService.__create_invoice(payment_dto)
            msg_id = getattr(callback.message, "message_id", 0) if hasattr(callback, "message") else getattr(callback, "message_id", 0)
            await PaymentRepository.create(payment_dto.id, user.id, msg_id, session)
            await session_commit(session)

            if language == Language.VI:
                caption = (
                    f"🧾 <b>Hoá đơn nạp {payment_dto.cryptoCurrency.name}</b>\n\n"
                    f"Coin: <b>{payment_dto.cryptoCurrency.name}</b>\n"
                    f"Địa chỉ ví: <code>{payment_dto.address}</code>\n"
                    f"Hạn thanh toán: 60 phút\n\n"
                    f"⚠️ Vui lòng gửi {payment_dto.cryptoCurrency.name} vào đúng địa chỉ ví trên.\n"
                    f"Sau khi mạng blockchain xác nhận giao dịch, hệ thống KryptoExpress sẽ tự động cộng tiền vào tài khoản của bạn."
                )
                btn_cp_addr = "📋 Sao chép địa chỉ ví"
                btn_cancel = "❌ Huỷ hoá đơn"
            else:
                caption = (
                    f"🧾 <b>Deposit Invoice ({payment_dto.cryptoCurrency.name})</b>\n\n"
                    f"Coin: <b>{payment_dto.cryptoCurrency.name}</b>\n"
                    f"Deposit Address: <code>{payment_dto.address}</code>\n"
                    f"Expires in: 60 minutes\n\n"
                    f"⚠️ Please transfer {payment_dto.cryptoCurrency.name} to the address above. Balance will be credited automatically once confirmed."
                )
                btn_cp_addr = "📋 Copy Address"
                btn_cancel = "❌ Cancel Invoice"

            kb_builder.button(text=btn_cp_addr, callback_data=f"dep_cp:addr:{payment_dto.address}")
            kb_builder.button(text=btn_cancel, callback_data="dep_cancel:krypto")
            kb_builder.adjust(1, 1)

            qr_code_file = PaymentService.__create_qr_code(payment_dto)
            return InputMediaPhoto(media=qr_code_file, caption=caption), kb_builder
