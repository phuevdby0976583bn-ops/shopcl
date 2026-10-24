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

        captions = {
            Language.VI: (
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
            ),
            Language.EN: (
                f"🟡 <b>TOP UP VIA BINANCE PAY (0% FEE)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Transaction Fee:</b> <b>0 USDT (100% Free)</b>\n"
                f"⚡ <b>Processing Time:</b> Instant (1-5 seconds)\n"
                f"⚡ <b>Minimum Amount:</b> From <b>0.01 USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>STEP 1:</b> Open <b>Binance App</b> ➔ Tap the <b>Pay</b> icon\n\n"
                f"👉 <b>STEP 2:</b> Select <b>Send</b> to Binance UID:\n"
                f"🆔 <code>{binance_uid}</code> <i>(Tap to copy)</i>\n\n"
                f"👉 <b>STEP 3:</b> Enter the USDT amount to deposit.\n\n"
                f"👉 <b>STEP 4 (REQUIRED):</b>\n"
                f"In the <b>Remark / Note</b> field, you MUST enter:\n"
                f"📝 <code>{memo}</code> <i>(Tap to copy)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 After sending on Binance, click <b>[ 🔄 Check Transaction ]</b> below to credit balance immediately!</i>"
            ),
            Language.HI: (
                f"🟡 <b>BINANCE PAY द्वारा टॉप-अप (0% शुल्क)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>लेनदेन शुल्क:</b> <b>0 USDT (100% मुफ़्त)</b>\n"
                f"⚡ <b>प्रसंस्करण समय:</b> तुरंत (1-5 सेकंड)\n"
                f"⚡ <b>न्यूनतम राशि:</b> <b>0.01 USDT</b> से\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>चरण 1:</b> <b>Binance App</b> खोलें ➔ <b>Pay</b> आइकन पर टैप करें\n\n"
                f"👉 <b>चरण 2:</b> Binance UID पर <b>भेजें (Send)</b> चुनें:\n"
                f"🆔 <code>{binance_uid}</code> <i>(कॉपी करने के लिए टैप करें)</i>\n\n"
                f"👉 <b>चरण 3:</b> जमा करने के लिए USDT राशि दर्ज करें।\n\n"
                f"👉 <b>चरण 4 (अनिवार्य):</b>\n"
                f"<b>Remark / Note</b> फ़ील्ड में यह दर्ज करना अनिवार्य है:\n"
                f"📝 <code>{memo}</code> <i>(कॉपी करने के लिए टैप करें)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 ट्रांसफर पूरा होने के बाद, तुरंत बैलेंस पाने के लिए नीचे <b>[ 🔄 लेनदेन जांचें ]</b> बटन पर क्लिक करें!</i>"
            ),
            Language.ZH: (
                f"🟡 <b>通过币安支付 BINANCE PAY 充值（0% 手续费）</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>手续费：</b> <b>0 USDT（100% 免费）</b>\n"
                f"⚡ <b>到账时间：</b> 实时秒到（1-5 秒）\n"
                f"⚡ <b>充值门槛：</b> 仅需 <b>0.01 USDT</b> 起\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>步骤 1：</b> 打开 <b>Binance 币安 App</b> ➔ 点击 <b>Pay 支付</b> 图标\n\n"
                f"👉 <b>步骤 2：</b> 选择 <b>发送 (Send)</b> 至币安 UID：\n"
                f"🆔 <code>{binance_uid}</code> <i>（点击数字一键复制）</i>\n\n"
                f"👉 <b>步骤 3：</b> 输入您要充值的 USDT 金额。\n\n"
                f"👉 <b>步骤 4（必填）：</b>\n"
                f"在 <b>备注 / Remark / Note</b> 栏，务必准确填写：\n"
                f"📝 <code>{memo}</code> <i>（点击文字一键复制）</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 币安转账完成后，请点击下方 <b>[ 🔄 检查交易状态 ]</b> 按钮，系统将立即自动上分！</i>"
            ),
            Language.FR: (
                f"🟡 <b>RECHARGER VIA BINANCE PAY (0% DE FRAIS)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Frais :</b> <b>0 USDT (100% Gratuit)</b>\n"
                f"⚡ <b>Délai :</b> Réception instantanée (1-5 secondes)\n"
                f"⚡ <b>Montant minimum :</b> À partir de <b>0.01 USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>ÉTAPE 1 :</b> Ouvrez l'application <b>Binance</b> ➔ Appuyez sur l'icône <b>Pay</b>\n\n"
                f"👉 <b>ÉTAPE 2 :</b> Choisissez <b>Envoyer (Send)</b> vers le UID Binance :\n"
                f"🆔 <code>{binance_uid}</code> <i>(Appuyez pour copier)</i>\n\n"
                f"👉 <b>ÉTAPE 3 :</b> Entrez le montant d'USDT à déposer.\n\n"
                f"👉 <b>ÉTAPE 4 (OBLIGATOIRE) :</b>\n"
                f"Dans le champ <b>Remarque / Note</b>, vous DEVEZ indiquer :\n"
                f"📝 <code>{memo}</code> <i>(Appuyez pour copier)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 Après votre transfert sur Binance, cliquez ci-dessous sur <b>[ 🔄 Vérifier la transaction ]</b> pour créditer votre solde immédiatement !</i>"
            ),
            Language.DE: (
                f"🟡 <b>AUFLADEN ÜBER BINANCE PAY (0% GEBÜHR)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Transaktionsgebühr:</b> <b>0 USDT (100% Kostenlos)</b>\n"
                f"⚡ <b>Bearbeitungszeit:</b> Sofort (1-5 Sekunden)\n"
                f"⚡ <b>Mindestbetrag:</b> Ab <b>0.01 USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>SCHRITT 1:</b> Öffnen Sie die <b>Binance App</b> ➔ Tippen Sie auf das <b>Pay</b>-Symbol\n\n"
                f"👉 <b>SCHRITT 2:</b> Wählen Sie <b>Senden (Send)</b> an die Binance-UID:\n"
                f"🆔 <code>{binance_uid}</code> <i>(Zum Kopieren tippen)</i>\n\n"
                f"👉 <b>SCHRITT 3:</b> Geben Sie den gewünschten USDT-Betrag ein.\n\n"
                f"👉 <b>SCHRITT 4 (ERFORDERLICH):</b>\n"
                f"Im Feld <b>Hinweis / Remark / Note</b> MÜSSEN Sie angeben:\n"
                f"📝 <code>{memo}</code> <i>(Zum Kopieren tippen)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 Nach der Überweisung auf Binance klicken Sie unten auf <b>[ 🔄 Transaktion prüfen ]</b>, um Ihr Guthaben sofort gutzuschreiben!</i>"
            ),
            Language.IT: (
                f"🟡 <b>RICARICA TRAMITE BINANCE PAY (0% COMMISSIONI)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Commissioni:</b> <b>0 USDT (100% Gratuito)</b>\n"
                f"⚡ <b>Tempo di accredito:</b> Immediato (1-5 secondi)\n"
                f"⚡ <b>Importo minimo:</b> A partire da <b>0.01 USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>PASSO 1:</b> Apri l'app <b>Binance</b> ➔ Tocca l'icona <b>Pay</b>\n\n"
                f"👉 <b>PASSO 2:</b> Seleziona <b>Invia (Send)</b> all'UID Binance :\n"
                f"🆔 <code>{binance_uid}</code> <i>(Tocca per copiare)</i>\n\n"
                f"👉 <b>PASSO 3:</b> Inserisci l'importo di USDT da ricaricare.\n\n"
                f"👉 <b>PASSO 4 (OBBLIGATORIO):</b>\n"
                f"Nel campo <b>Nota / Remark</b>, DEVI inserire :\n"
                f"📝 <code>{memo}</code> <i>(Tocca per copiare)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 Dopo il trasferimento su Binance, tocca il pulsante <b>[ 🔄 Controlla transazione ]</b> in basso per accreditare subito il saldo!</i>"
            ),
            Language.ES: (
                f"🟡 <b>RECARGAR MEDIANTE BINANCE PAY (0% COMISIÓN)</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Comisión:</b> <b>0 USDT (100% Gratis)</b>\n"
                f"⚡ <b>Tiempo de procesamiento:</b> Instantáneo (1-5 segundos)\n"
                f"⚡ <b>Monto mínimo:</b> Desde <b>0.01 USDT</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👉 <b>PASO 1:</b> Abre la app <b>Binance</b> ➔ Toca el icono de <b>Pay</b>\n\n"
                f"👉 <b>PASO 2:</b> Selecciona <b>Enviar (Send)</b> al UID de Binance:\n"
                f"🆔 <code>{binance_uid}</code> <i>(Toca para copiar)</i>\n\n"
                f"👉 <b>PASO 3:</b> Ingresa la cantidad de USDT que deseas recargar.\n\n"
                f"👉 <b>PASO 4 (OBLIGATORIO):</b>\n"
                f"En el campo <b>Nota / Remark</b>, DEBES ingresar obligatoriamente:\n"
                f"📝 <code>{memo}</code> <i>(Toca para copiar)</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<i>💡 Tras completar el envío en Binance, haz clic abajo en <b>[ 🔄 Verificar transacción ]</b> para acreditar tu saldo de inmediato.</i>"
            ),
        }
        caption = captions.get(language, captions[Language.EN])

        check_labels = {
            Language.VI: "🔄 Kiểm tra giao dịch (Check)",
            Language.EN: "🔄 Check Transaction",
            Language.HI: "🔄 लेनदेन की जाँच करें",
            Language.ZH: "🔄 检查交易状态",
            Language.FR: "🔄 Vérifier la transaction",
            Language.DE: "🔄 Transaktion prüfen",
            Language.IT: "🔄 Controlla transazione",
            Language.ES: "🔄 Verificar transacción",
        }
        back_labels = {
            Language.VI: "🔙 Quay lại Ví",
            Language.EN: "🔙 Back to Wallet",
            Language.HI: "🔙 वॉलेट पर वापस",
            Language.ZH: "🔙 返回钱包",
            Language.FR: "🔙 Retour au portefeuille",
            Language.DE: "🔙 Zurück zur Geldbörse",
            Language.IT: "🔙 Torna al portafoglio",
            Language.ES: "🔙 Volver a la billetera",
        }

        kb_builder = InlineKeyboardBuilder()
        kb_builder.button(
            text=check_labels.get(language, check_labels[Language.EN]),
            callback_data="binance_pay:check"
        )
        kb_builder.button(
            text=back_labels.get(language, back_labels[Language.EN]),
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
