# -*- coding: utf-8 -*-
from enums.language import Language


def get_wallet_text(language: Language, user_name: str, telegram_id: int, balance: float, top_up: float, consume: float) -> tuple[str, dict]:
    wallet_data = {
        Language.VI: (
            "👤 <b>VÍ & TÀI KHOẢN CỦA BẠN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Tài khoản:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>Số dư khả dụng:</b> <b>{balance}$</b> (USDT)\n"
            f"📈 <b>Đã nạp:</b> {top_up:.2f}$ | 📉 <b>Đã tiêu:</b> {consume:.2f}$\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Khuyên dùng <b>Binance Pay</b> hoặc <b>VietQR BIDV</b>: Nạp tự động nhận ngay sau vài giây.</i>\n"
            "👇 <b>Bấm nút bên dưới để nạp tiền tự động:</b>",
            {"bank": "🏦 Chuyển khoản Ngân hàng (VietQR / BIDV)", "binance": "⚡ Binance Pay (0% Phí - Nhận 1s)", "onchain": "🌐 Nạp On-chain (BSC, TRX, TON...)", "history": "📦 Lịch sử mua hàng"}
        ),
        Language.ZH: (
            "👤 <b>我的钱包与账户</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>账户:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>可用余额:</b> <b></b> (USDT)\n"
            f"📈 <b>总充值:</b>  | 📉 <b>总消费:</b> \n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>推荐使用 <b>币安支付 (Binance Pay)</b>：0手续费，1-5秒自动到账。</i>\n"
            "👇 <b>请点击下方按钮进行自动充值:</b>",
            {"bank": "🏦 越南银行卡 (VietQR / BIDV)", "binance": "⚡ 币安支付 Binance Pay (0手续费 - 秒到)", "onchain": "🌐 链上充值 (BSC, TRX, TON...)", "history": "📦 购买记录"}
        ),
        Language.HI: (
            "👤 <b>आपका वॉलेट और खाता</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>खाता:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>उपलब्ध शेष:</b> <b></b> (USDT)\n"
            f"📈 <b>कुल जमा:</b>  | 📉 <b>खर्च:</b> \n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>सुझाव: <b>Binance Pay</b> (0% शुल्क, 1-5 सेकंड में तत्काल जमा)।</i>\n"
            "👇 <b>स्वचालित रूप से जमा करने के लिए नीचे क्लिक करें:</b>",
            {"bank": "🏦 वियतनाम बैंक (VietQR / BIDV)", "binance": "⚡ Binance Pay (0% शुल्क - तुरंत 1s)", "onchain": "🌐 ऑन-चेन जमा (BSC, TRX, TON...)", "history": "📦 खरीद इतिहास"}
        ),
        Language.FR: (
            "👤 <b>VOTRE PORTEFEUILLE & COMPTE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Compte :</b> {user_name} (ID : <code>{telegram_id}</code>)\n"
            f"💵 <b>Solde disponible :</b> <b>{balance}$</b> (USDT)\n"
            f"📈 <b>Déposé :</b> {top_up:.2f}$ | 📉 <b>Dépensé :</b> {consume:.2f}$\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Recommandé : <b>Binance Pay</b> (0 % de frais, crédit instantané en 1-5s).</i>\n"
            "👇 <b>Appuyez sur un bouton ci-dessous pour déposer :</b>",
            {"bank": "🏦 Virement bancaire Vietnam (VietQR / BIDV)", "binance": "⚡ Binance Pay (0 % Frais - Immédiat 1s)", "onchain": "🌐 Dépôt On-chain (BSC, TRX, TON...)", "history": "📦 Historique des achats"}
        ),
        Language.DE: (
            "👤 <b>IHR WALLET & KONTO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Konto:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>Verfügbares Guthaben:</b> <b>{balance}$</b> (USDT)\n"
            f"📈 <b>Eingezahlt:</b> {top_up:.2f}$ | 📉 <b>Ausgegeben:</b> {consume:.2f}$\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Empfohlen: <b>Binance Pay</b> (0 % Gebühr, Gutschrift in 1-5 Sek.).</i>\n"
            "👇 <b>Tippen Sie unten, um automatisch aufzuladen:</b>",
            {"bank": "🏦 Vietnam Banküberweisung (VietQR / BIDV)", "binance": "⚡ Binance Pay (0 % Gebühr - Sofort 1s)", "onchain": "🌐 On-chain Einzahlung (BSC, TRX, TON...)", "history": "📦 Kaufhistorie"}
        ),
        Language.IT: (
            "👤 <b>IL TUO PORTAFOGLIO & ACCOUNT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Account:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>Saldo disponibile:</b> <b>{balance}$</b> (USDT)\n"
            f"📈 <b>Depositato:</b> {top_up:.2f}$ | 📉 <b>Speso:</b> {consume:.2f}$\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Consigliato: <b>Binance Pay</b> (0% commissioni, accredito in 1-5s).</i>\n"
            "👇 <b>Tocca un pulsante in basso per ricaricare:</b>",
            {"bank": "🏦 Bonifico bancario Vietnam (VietQR / BIDV)", "binance": "⚡ Binance Pay (0% Comm. - Immediato 1s)", "onchain": "🌐 Deposito On-chain (BSC, TRX, TON...)", "history": "📦 Storico acquisti"}
        ),
        Language.ES: (
            "👤 <b>TU BILLETERA & CUENTA</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔 <b>Cuenta:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
            f"💵 <b>Saldo disponible:</b> <b></b> (USDT)\n"
            f"📈 <b>Depositado:</b>  | 📉 <b>Gastado:</b> \n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>Recomendado: <b>Binance Pay</b> (0% comisión, acreditación en 1-5s).</i>\n"
            "👇 <b>Toca un botón abajo para depositar automáticamente:</b>",
            {"bank": "🏦 Transferencia bancaria Vietnam (VietQR / BIDV)", "binance": "⚡ Binance Pay (0% Comisión - Instantáneo 1s)", "onchain": "🌐 Depósito On-chain (BSC, TRX, TON...)", "history": "📦 Historial de compras"}
        ),
    }
    default_data = (
        "👤 <b>YOUR WALLET & ACCOUNT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 <b>Account:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
        f"💵 <b>Available Balance:</b> <b></b> (USDT)\n"
        f"📈 <b>Deposited:</b>  | 📉 <b>Spent:</b> \n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <i>Recommended: <b>Binance Pay</b> (0% fee, instant credit in 1-5s).</i>\n"
        "👇 <b>Tap a button below to deposit automatically:</b>",
        {"bank": "🏦 Vietnam Bank Transfer (VietQR / BIDV)", "binance": "⚡ Binance Pay (0% Fee - Instant 1s)", "onchain": "🌐 On-chain Deposit (BSC, TRX, TON...)", "history": "📦 Purchase History"}
    )
    return wallet_data.get(language, default_data)


def get_deposit_method_selection(language: Language) -> tuple[str, dict]:
    data = {
        Language.VI: (
            "💰 <b>BẠN MUỐN NẠP TIỀN BẰNG CÁCH NÀO?</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (Khuyên dùng - 0% Phí):</b>\n"
            "• Quét mã hoặc gửi qua Pay ID / UID Binance.\n"
            "• Hệ thống tự quét giao dịch và cộng tiền ngay trong 1 - 5 giây.\n\n"
            "2️⃣ <b>Chuyển khoản Ngân hàng (VietQR / BIDV):</b>\n"
            "• Quét mã VietQR đúng số tiền và nội dung chuyển khoản.\n"
            "• Tự động cộng tiền theo tỷ giá thị trường.\n\n"
            "3️⃣ <b>Nạp On-chain Crypto:</b>\n"
            "• Nhận USDT, LTC, SOL, TRX...\n\n"
            "👇 <i>Vui lòng bấm chọn hình thức nạp bên dưới:</i>",
            {"binance": "⚡ Binance Pay (0% Phí - Nhận ngay 1s)", "bank": "🏦 Ngân hàng VN (VietQR / BIDV)", "onchain": "🌐 Nạp Crypto On-chain"}
        ),
        Language.ZH: (
            "💰 <b>请选择充值方式</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>币安支付 (推荐 - 0手续费):</b>\n"
            "• 扫码或通过币安 Pay ID / UID 转账。\n"
            "• 系统1-5秒内自动查账并充值。\n\n"
            "2️⃣ <b>越南银行转账 (VietQR / BIDV):</b>\n"
            "• 扫码转账，全自动按汇率入账。\n\n"
            "3️⃣ <b>链上虚拟币充值:</b>\n"
            "• 支持 USDT, LTC, SOL, TRX 等。\n\n"
            "👇 <i>请在下方选择充值方式:</i>",
            {"binance": "⚡ 币安支付 (0手续费 - 秒到)", "bank": "🏦 越南银行 (VietQR / BIDV)", "onchain": "🌐 链上虚拟币"}
        ),
        Language.HI: (
            "💰 <b>जमा करने का तरीका चुनें</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (सुझाव - 0% शुल्क):</b>\n"
            "• QR स्कैन करें या Binance Pay ID / UID पर ट्रांसफर करें।\n"
            "• 1-5 सेकंड में स्वचालित जमा।\n\n"
            "2️⃣ <b>वियतनाम बैंक ट्रांसफर (VietQR / BIDV):</b>\n"
            "• सटीक राशि और विवरण के साथ QR कोड स्कैन करें।\n\n"
            "3️⃣ <b>ऑन-चेन क्रिप्टो:</b>\n"
            "• USDT, LTC, SOL, TRX समर्थित।\n\n"
            "👇 <i>कृपया नीचे जमा विधि चुनें:</i>",
            {"binance": "⚡ Binance Pay (0% शुल्क - तुरंत 1s)", "bank": "🏦 वियतनाम बैंक (VietQR / BIDV)", "onchain": "🌐 ऑन-चेन क्रिप्टो"}
        ),
        Language.FR: (
            "💰 <b>CHOISISSEZ VOTRE MÉTHODE DE DÉPÔT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (Recommandé - 0% Frais) :</b>\n"
            "• Scannez le QR ou transférez vers Binance Pay ID / UID.\n"
            "• Crédité automatiquement en 1-5 secondes.\n\n"
            "2️⃣ <b>Virement bancaire Vietnam (VietQR / BIDV) :</b>\n"
            "• Scannez le QR avec le montant et le motif exacts.\n\n"
            "3️⃣ <b>Crypto On-chain :</b>\n"
            "• Supporte USDT, LTC, SOL, TRX, etc.\n\n"
            "👇 <i>Veuillez sélectionner une méthode ci-dessous :</i>",
            {"binance": "⚡ Binance Pay (0% Frais - Instant 1s)", "bank": "🏦 Banque Vietnam (VietQR / BIDV)", "onchain": "🌐 Crypto On-chain"}
        ),
        Language.DE: (
            "💰 <b>WÄHLEN SIE IHRE EINZAHLUNGSMETHODE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (Empfohlen - 0% Gebühr):</b>\n"
            "• QR scannen oder an Binance Pay ID / UID überweisen.\n"
            "• Automatische Gutschrift in 1-5 Sekunden.\n\n"
            "2️⃣ <b>Vietnam Banküberweisung (VietQR / BIDV):</b>\n"
            "• QR-Code mit exaktem Betrag und Verwendungszweck scannen.\n\n"
            "3️⃣ <b>On-Chain Krypto:</b>\n"
            "• Unterstützt USDT, LTC, SOL, TRX usw.\n\n"
            "👇 <i>Bitte wählen Sie unten eine Methode:</i>",
            {"binance": "⚡ Binance Pay (0% Gebühr - Sofort 1s)", "bank": "🏦 Vietnam Bank (VietQR / BIDV)", "onchain": "🌐 On-chain Krypto"}
        ),
        Language.IT: (
            "💰 <b>SCEGLI IL METODO DI DEPOSITO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (Consigliato - 0% Commissioni):</b>\n"
            "• Scansiona il QR o trasferisci su Binance Pay ID / UID.\n"
            "• Accredito automatico in 1-5 secondi.\n\n"
            "2️⃣ <b>Bonifico Vietnam (VietQR / BIDV):</b>\n"
            "• Scansiona il QR con importo e causale corretti.\n\n"
            "3️⃣ <b>Crypto On-chain:</b>\n"
            "• Supporta USDT, LTC, SOL, TRX e altri.\n\n"
            "👇 <i>Seleziona un metodo di deposito in basso:</i>",
            {"binance": "⚡ Binance Pay (0% Comm. - Immediato 1s)", "bank": "🏦 Banca Vietnam (VietQR / BIDV)", "onchain": "🌐 Crypto On-chain"}
        ),
        Language.ES: (
            "💰 <b>ELIGE TU MÉTODO DE DEPÓSITO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ <b>Binance Pay (Recomendado - 0% Comisión):</b>\n"
            "• Escanea el QR o transfiere a Binance Pay ID / UID.\n"
            "• Acreditación automática en 1-5 segundos.\n\n"
            "2️⃣ <b>Transferencia Vietnam (VietQR / BIDV):</b>\n"
            "• Escanea el QR con el monto y concepto exactos.\n\n"
            "3️⃣ <b>Cripto On-chain:</b>\n"
            "• Soporta USDT, LTC, SOL, TRX y más.\n\n"
            "👇 <i>Por favor selecciona un método abajo:</i>",
            {"binance": "⚡ Binance Pay (0% Comisión - Instantáneo 1s)", "bank": "🏦 Banco Vietnam (VietQR / BIDV)", "onchain": "🌐 Cripto On-chain"}
        ),
    }
    default_data = (
        "💰 <b>CHOOSE YOUR DEPOSIT METHOD</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ <b>Binance Pay (Recommended - 0% Fee):</b>\n"
        "• Scan QR code or transfer to Binance Pay ID / UID.\n"
        "• Auto-credited in 1 - 5 seconds.\n\n"
        "2️⃣ <b>Vietnam Bank Transfer (VietQR / BIDV):</b>\n"
        "• Scan QR with exact amount and transfer description.\n"
        "• Auto-credited instantly.\n\n"
        "3️⃣ <b>On-chain Crypto:</b>\n"
        "• Supports USDT, LTC, SOL, TRX and more.\n\n"
        "👇 <i>Please select a deposit method below:</i>",
        {"binance": "⚡ Binance Pay (0% Fee - Instant 1s)", "bank": "🏦 Vietnam Bank (VietQR / BIDV)", "onchain": "🌐 On-chain Crypto"}
    )
    return data.get(language, default_data)


def get_out_of_stock_text(language: Language, cat_name: str, subcat_name: str) -> str:
    match language:
        case Language.VI:
            return (
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>Tạm thời hết hàng!</b>\n"
                "Kho hiện tại đã bán hết loại tài khoản này. Vui lòng chọn loại tài khoản khác hoặc liên hệ Admin @truongdvfb để được hỗ trợ nhập thêm hàng."
            )
        case Language.ZH:
            return (
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>商品:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>暂时缺货！</b>\n"
                "当前分类已售罄，请稍后再试或选择其他商品，或联系客服 @truongdvfb 补货。"
            )
        case Language.HI:
            return (
                f"📁 <b>श्रेणी:</b> <code>{cat_name}</code>\n"
                f"📦 <b>उत्पाद:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>स्टॉक समाप्त!</b>\n"
                "यह उत्पाद वर्तमान में स्टॉक में नहीं है। कृपया दूसरा उत्पाद चुनें या एडमिन @truongdvfb से संपर्क करें।"
            )
        case Language.FR:
            return (
                f"📁 <b>Catégorie :</b> <code>{cat_name}</code>\n"
                f"📦 <b>Produit :</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>Rupture de stock !</b>\n"
                "Ce produit est actuellement épuisé. Veuillez choisir un autre produit ou contacter l'administrateur @truongdvfb."
            )
        case Language.DE:
            return (
                f"📁 <b>Kategorie:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Produkt:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>Zurzeit nicht auf Lager!</b>\n"
                "Dieses Produkt ist derzeit ausverkauft. Bitte wählen Sie ein anderes Produkt oder kontaktieren Sie @truongdvfb."
            )
        case Language.IT:
            return (
                f"📁 <b>Categoria:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Prodotto:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>Attualmente esaurito!</b>\n"
                "Questo articolo è temporaneamente esaurito. Scegli un altro prodotto o contatta l'amministratore @truongdvfb."
            )
        case Language.ES:
            return (
                f"📁 <b>Categoría:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Producto:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>¡Agotado temporalmente!</b>\n"
                "Este producto está agotado actualmente. Por favor elige otro producto o contacta al administrador @truongdvfb."
            )
        case _:
            return (
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n\n"
                "❌ <b>Out of stock!</b>\n"
                "This account type is currently out of stock. Please select another product or contact Admin @truongdvfb."
            )


def get_select_quantity_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, sym: str, desc: str, available_qty: int) -> str:
    desc_str = f"📝 <b>Mô tả:</b> <i>{desc}</i>\n" if desc else ""
    match language:
        case Language.VI:
            return (
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Giá bán:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"{desc_str}"
                f"🔢 <b>Số lượng có sẵn:</b> <code>{available_qty}</code> cái\n\n"
                "🔢 <b>Vui lòng chọn số lượng cần mua bên dưới:</b>"
            )
        case Language.ZH:
            desc_zh = f"📝 <b>描述:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>账号:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>单价:</b> <code>{unit_price:.2f} {sym}</code> / 个\n"
                f"{desc_zh}"
                f"🔢 <b>当前库存:</b> <code>{available_qty}</code> 个\n\n"
                "🔢 <b>请在下方选择购买数量:</b>"
            )
        case Language.HI:
            desc_hi = f"📝 <b>विवरण:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>श्रेणी:</b> <code>{cat_name}</code>\n"
                f"📦 <b>खाता:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>मूल्य:</b> <code>{unit_price:.2f} {sym}</code> / खाता\n"
                f"{desc_hi}"
                f"🔢 <b>स्टॉक में उपलब्ध:</b> <code>{available_qty}</code>\n\n"
                "🔢 <b>कृपया नीचे से खरीदने की मात्रा चुनें:</b>"
            )
        case Language.FR:
            desc_fr = f"📝 <b>Description :</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>Catégorie :</b> <code>{cat_name}</code>\n"
                f"📦 <b>Compte :</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Prix :</b> <code>{unit_price:.2f} {sym}</code> / compte\n"
                f"{desc_fr}"
                f"🔢 <b>En stock :</b> <code>{available_qty}</code> pcs\n\n"
                "🔢 <b>Veuillez choisir la quantité à acheter ci-dessous :</b>"
            )
        case Language.DE:
            desc_de = f"📝 <b>Beschreibung:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>Kategorie:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Konto:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Preis:</b> <code>{unit_price:.2f} {sym}</code> / Stk.\n"
                f"{desc_de}"
                f"🔢 <b>Auf Lager:</b> <code>{available_qty}</code> Stück\n\n"
                "🔢 <b>Bitte wählen Sie die gewünschte Kaufmenge:</b>"
            )
        case Language.IT:
            desc_it = f"📝 <b>Descrizione:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>Categoria:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Prezzo:</b> <code>{unit_price:.2f} {sym}</code> / account\n"
                f"{desc_it}"
                f"🔢 <b>Disponibili:</b> <code>{available_qty}</code> pz\n\n"
                "🔢 <b>Seleziona la quantità da acquistare in basso:</b>"
            )
        case Language.ES:
            desc_es = f"📝 <b>Descripción:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>Categoría:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Cuenta:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Precio:</b> <code>{unit_price:.2f} {sym}</code> / cuenta\n"
                f"{desc_es}"
                f"🔢 <b>En stock:</b> <code>{available_qty}</code> uds\n\n"
                "🔢 <b>Por favor selecciona la cantidad a comprar abajo:</b>"
            )
        case _:
            desc_en = f"📝 <b>Description:</b> <i>{desc}</i>\n" if desc else ""
            return (
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"{desc_en}"
                f"🔢 <b>In stock:</b> <code>{available_qty}</code> pcs\n\n"
                "🔢 <b>Please select quantity to buy below:</b>"
            )


def get_all_qty_label(language: Language, qty: int) -> str:
    match language:
        case Language.VI:
            return f"Tất cả ({qty})"
        case Language.ZH:
            return f"全部 ({qty})"
        case Language.HI:
            return f"सभी ({qty})"
        case Language.FR:
            return f"Tous ({qty})"
        case Language.DE:
            return f"Alle ({qty})"
        case Language.IT:
            return f"Tutti ({qty})"
        case Language.ES:
            return f"Todos ({qty})"
        case _:
            return f"All ({qty})"


def get_instant_buy_confirm_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, qty: int, total_price: float, sym: str, balance: float, is_enough: bool, missing: float) -> tuple[str, dict]:
    match language:
        case Language.VI:
            status_text = (
                "✅ <b>Số dư ví đủ thanh toán. Bấm 'MUA NGAY' bên dưới để nhận tài khoản tức thì!</b>"
                if is_enough
                else f"⚠️ <b>Số dư ví không đủ! Còn thiếu: <code>{missing:.2f} {sym}</code>. Vui lòng nạp tiền vào ví trước khi mua.</b>"
            )
            msg = (
                "⚡ <b>XÁC NHẬN MUA TÀI KHOẢN (TRỪ TIỀN TRỰC TIẾP)</b>\n\n"
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Đơn giá:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"🔢 <b>Số lượng mua:</b> <code>{qty}</code> nick\n"
                f"💰 <b>TỔNG THANH TOÁN:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Số dư ví hiện tại:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Lưu ý: Hệ thống tự động Check Live UID Facebook qua Graph API ngay khi giao hàng, cam kết 100% clone Live!</i>"
            )
            labels = {
                "buy": f"⚡ MUA NGAY ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Chọn lại số lượng",
                "cancel": "❌ Hủy bỏ",
                "binance": "🟡 Nạp Binance Pay (0% Phí - Nhận ngay 1s)",
                "bank": "🏦 Nạp Ngân Hàng (VietQR / BIDV)",
                "crypto": "💳 Cổng Nạp On-chain Crypto"
            }
        case Language.ZH:
            status_text = (
                "✅ <b>钱包余额充足，点击下方'立即购买'即可秒发卡！</b>"
                if is_enough
                else f"⚠️ <b>余额不足！还缺: <code>{missing:.2f} {sym}</code>，请先充值后再购买。</b>"
            )
            msg = (
                "⚡ <b>确认购买账号 (余额直接扣款)</b>\n\n"
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>商品:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>单价:</b> <code>{unit_price:.2f} {sym}</code> / 个\n"
                f"🔢 <b>数量:</b> <code>{qty}</code> 个\n"
                f"💰 <b>总需支付:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>当前钱包余额:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>注意: 发货前系统自动通过 Facebook Graph API 实时检测 Live，承诺 100% Live！</i>"
            )
            labels = {
                "buy": f"⚡ 立即购买 ({total_price:.2f} {sym})",
                "back_qty": "⬅️ 重选数量",
                "cancel": "❌ 取消",
                "binance": "🟡 币安支付 (0手续费 - 秒到)",
                "bank": "🏦 越南银行卡 (VietQR / BIDV)",
                "crypto": "💳 链上虚拟币 (On-chain)"
            }
        case Language.HI:
            status_text = (
                "✅ <b>पर्याप्त शेष राशि। तुरंत खाता प्राप्त करने के लिए नीचे 'अभी खरीदें' पर क्लिक करें!</b>"
                if is_enough
                else f"⚠️ <b>अपर्याप्त शेष राशि! कमी: <code>{missing:.2f} {sym}</code>। कृपया पहले वॉलेट में जमा करें।</b>"
            )
            msg = (
                "⚡ <b>त्वरित खरीद पुष्टि</b>\n\n"
                f"📁 <b>श्रेणी:</b> <code>{cat_name}</code>\n"
                f"📦 <b>खाता:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>इकाई मूल्य:</b> <code>{unit_price:.2f} {sym}</code> / खाता\n"
                f"🔢 <b>मात्रा:</b> <code>{qty}</code>\n"
                f"💰 <b>कुल भुगतान:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>वॉलेट शेष:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>नोट: डिलीवरी से पहले Graph API द्वारा Facebook UIDs की 100% लाइव जांच की जाती है!</i>"
            )
            labels = {
                "buy": f"⚡ अभी खरीदें ({total_price:.2f} {sym})",
                "back_qty": "⬅️ मात्रा बदलें",
                "cancel": "❌ रद्द करें",
                "binance": "🟡 Binance Pay (0% शुल्क)",
                "bank": "🏦 वियतनाम बैंक (VietQR / BIDV)",
                "crypto": "💳 ऑन-चेन क्रिप्टो"
            }
        case Language.FR:
            status_text = (
                "✅ <b>Solde suffisant. Cliquez sur 'ACHETER' ci-dessous pour recevoir vos comptes !</b>"
                if is_enough
                else f"⚠️ <b>Solde insuffisant ! Manquant : <code>{missing:.2f} {sym}</code>. Veuillez recharger votre portefeuille.</b>"
            )
            msg = (
                "⚡ <b>CONFIRMATION D'ACHAT IMMÉDIAT</b>\n\n"
                f"📁 <b>Catégorie :</b> <code>{cat_name}</code>\n"
                f"📦 <b>Compte :</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Prix unitaire :</b> <code>{unit_price:.2f} {sym}</code> / compte\n"
                f"🔢 <b>Quantité :</b> <code>{qty}</code> pcs\n"
                f"💰 <b>TOTAL À PAYER :</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Solde du portefeuille :</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Remarque : Vérification Live automatique via Graph API Facebook avant livraison !</i>"
            )
            labels = {
                "buy": f"⚡ ACHETER ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Changer la quantité",
                "cancel": "❌ Annuler",
                "binance": "🟡 Binance Pay (0% Frais)",
                "bank": "🏦 Banque Vietnam (VietQR / BIDV)",
                "crypto": "💳 Dépôt Crypto On-chain"
            }
        case Language.DE:
            status_text = (
                "✅ <b>Ausreichendes Guthaben. Klicken Sie unten auf 'JETZT KAUFEN' für sofortige Lieferung!</b>"
                if is_enough
                else f"⚠️ <b>Nicht genügend Guthaben! Fehlend: <code>{missing:.2f} {sym}</code>. Bitte laden Sie Ihr Wallet auf.</b>"
            )
            msg = (
                "⚡ <b>SOFORTKAUF-BESTÄTIGUNG</b>\n\n"
                f"📁 <b>Kategorie:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Konto:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Stückpreis:</b> <code>{unit_price:.2f} {sym}</code> / Stk.\n"
                f"🔢 <b>Menge:</b> <code>{qty}</code> Stk.\n"
                f"💰 <b>GESAMTSUMME:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Wallet-Guthaben:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Hinweis: Facebook-UIDs werden bei Lieferung automatisch über die Graph-API live geprüft!</i>"
            )
            labels = {
                "buy": f"⚡ JETZT KAUFEN ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Menge ändern",
                "cancel": "❌ Abbrechen",
                "binance": "🟡 Binance Pay (0% Gebühr)",
                "bank": "🏦 Vietnam Bank (VietQR / BIDV)",
                "crypto": "💳 On-chain Krypto"
            }
        case Language.IT:
            status_text = (
                "✅ <b>Saldo sufficiente. Clicca 'ACQUISTA ORA' in basso per ricevere gli account!</b>"
                if is_enough
                else f"⚠️ <b>Saldo insufficiente! Mancante: <code>{missing:.2f} {sym}</code>. Ricarica il portafoglio.</b>"
            )
            msg = (
                "⚡ <b>CONFERMA ACQUISTO IMMEDIATO</b>\n\n"
                f"📁 <b>Categoria:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Prezzo unitario:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"🔢 <b>Quantità:</b> <code>{qty}</code> pz\n"
                f"💰 <b>TOTALE:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Saldo portafoglio:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Nota: Verifica Live automatica tramite Facebook Graph API alla consegna!</i>"
            )
            labels = {
                "buy": f"⚡ ACQUISTA ORA ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Cambia quantità",
                "cancel": "❌ Annulla",
                "binance": "🟡 Binance Pay (0% Comm.)",
                "bank": "🏦 Banca Vietnam (VietQR / BIDV)",
                "crypto": "💳 Crypto On-chain"
            }
        case Language.ES:
            status_text = (
                "✅ <b>Saldo suficiente. ¡Haz clic en 'COMPRAR AHORA' abajo para recibir tus cuentas!</b>"
                if is_enough
                else f"⚠️ <b>¡Saldo insuficiente! Faltan: <code>{missing:.2f} {sym}</code>. Por favor recarga tu billetera.</b>"
            )
            msg = (
                "⚡ <b>CONFIRMACIÓN DE COMPRA INMEDIATA</b>\n\n"
                f"📁 <b>Categoría:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Cuenta:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Precio unitario:</b> <code>{unit_price:.2f} {sym}</code> / cuenta\n"
                f"🔢 <b>Cantidad:</b> <code>{qty}</code> uds\n"
                f"💰 <b>TOTAL:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Saldo billetera:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Nota: ¡Los UIDs de Facebook se verifican automáticamente en vivo vía Graph API!</i>"
            )
            labels = {
                "buy": f"⚡ COMPRAR AHORA ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Cambiar cantidad",
                "cancel": "❌ Cancelar",
                "binance": "🟡 Binance Pay (0% Comisión)",
                "bank": "🏦 Banco Vietnam (VietQR / BIDV)",
                "crypto": "💳 Cripto On-chain"
            }
        case _:
            status_text = (
                "✅ <b>Sufficient balance. Click 'BUY NOW' below to receive accounts immediately!</b>"
                if is_enough
                else f"⚠️ <b>Insufficient balance! Missing: <code>{missing:.2f} {sym}</code>. Please top up your wallet.</b>"
            )
            msg = (
                "⚡ <b>INSTANT PURCHASE CONFIRMATION</b>\n\n"
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💸 <b>Unit Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"🔢 <b>Quantity:</b> <code>{qty}</code> pcs\n"
                f"💰 <b>TOTAL AMOUNT:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Wallet Balance:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Note: Live Facebook UIDs are automatically verified via Graph API upon delivery!</i>"
            )
            labels = {
                "buy": f"⚡ BUY NOW ({total_price:.2f} {sym})",
                "back_qty": "⬅️ Change quantity",
                "cancel": "❌ Cancel",
                "binance": "🟡 Deposit Binance Pay (0% Fee)",
                "bank": "🏦 Vietnam Bank (VietQR / BIDV)",
                "crypto": "💳 Deposit On-chain Crypto"
            }
    return msg, labels


def get_search_prompt_caption(language: Language) -> str:
    match language:
        case Language.VI:
            return (
                "🔎 <b>TÌM KIẾM THEO TÊN SẢN PHẨM / DANH MỤC</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Vui lòng nhập tên bạn muốn tìm kiếm vào ô chat bên dưới:</b>\n"
                "<i>(Ví dụ: <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.ZH:
            return (
                "🔎 <b>按商品/分类名称搜索</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>请在下方聊天框中输入您要搜索的关键词：</b>\n"
                "<i>(例如: <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.HI:
            return (
                "🔎 <b>उत्पाद / श्रेणी के नाम से खोजें</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>कृपया नीचे चैट बॉक्स में खोज कीवर्ड दर्ज करें:</b>\n"
                "<i>(उदाहरण: <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.FR:
            return (
                "🔎 <b>RECHERCHE PAR PRODUIT / CATÉGORIE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Veuillez saisir le mot-clé recherché ci-dessous :</b>\n"
                "<i>(Exemple : <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.DE:
            return (
                "🔎 <b>SUCHE NACH PRODUKT / KATEGORIE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Bitte geben Sie unten den Suchbegriff ein:</b>\n"
                "<i>(z. B. <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.IT:
            return (
                "🔎 <b>CERCA PRODOTTI / CATEGORIE</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Inserisci la parola chiave da cercare qui sotto:</b>\n"
                "<i>(es. <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case Language.ES:
            return (
                "🔎 <b>BUSCAR PRODUCTOS / CATEGORÍAS</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Por favor escribe la palabra clave que deseas buscar abajo:</b>\n"
                "<i>(Ejemplo: <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )
        case _:
            return (
                "🔎 <b>SEARCH PRODUCTS / CATEGORIES</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "👉 <b>Please enter the keyword you want to search below:</b>\n"
                "<i>(e.g., <code>clone</code>, <code>facebook</code>, <code>via</code>...)</i>"
            )


def get_search_results_text(language: Language, query: str, found: bool) -> tuple[str, str]:
    btn_all = {
        Language.VI: "📦 Xem tất cả sản phẩm",
        Language.ZH: "📦 查看所有商品",
        Language.HI: "📦 सभी उत्पाद देखें",
        Language.FR: "📦 Voir tous les produits",
        Language.DE: "📦 Alle Produkte anzeigen",
        Language.IT: "📦 Mostra tutti i prodotti",
        Language.ES: "📦 Ver todos los productos"
    }.get(language, "📦 All Products")

    if found:
        match language:
            case Language.VI:
                msg = f'🔎 <b>KẾT QUẢ TÌM KIẾM CHO:</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Vui lòng chọn sản phẩm bạn muốn mua bên dưới:</i>'
            case Language.ZH:
                msg = f'🔎 <b>"{query}" 的搜索结果：</b>\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>请在下方选择您想购买的商品：</i>'
            case Language.HI:
                msg = f'🔎 <b>"{query}" के खोज परिणाम:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>कृपया नीचे से वह उत्पाद चुनें जिसे आप खरीदना चाहते हैं:</i>'
            case Language.FR:
                msg = f'🔎 <b>RÉSULTATS DE RECHERCHE POUR :</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Veuillez choisir un produit ci-dessous :</i>'
            case Language.DE:
                msg = f'🔎 <b>SUCHERGEBNISSE FÜR:</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Bitte wählen Sie unten ein Produkt aus:</i>'
            case Language.IT:
                msg = f'🔎 <b>RISULTATI DI RICERCA PER:</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Seleziona un prodotto qui sotto:</i>'
            case Language.ES:
                msg = f'🔎 <b>RESULTADOS DE BÚSQUEDA PARA:</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Por favor selecciona un producto abajo:</i>'
            case _:
                msg = f'🔎 <b>SEARCH RESULTS FOR:</b> "<code>{query}</code>"\n━━━━━━━━━━━━━━━━━━━━━━\n👇 <i>Please choose a product below:</i>'
    else:
        match language:
            case Language.VI:
                msg = f'🔎 Không tìm thấy sản phẩm nào phù hợp với từ khoá "<b>{query}</b>".\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Bạn có thể bấm <b>{btn_all}</b> để xem toàn bộ danh mục tài khoản:'
            case Language.ZH:
                msg = f'🔎 没有找到与 "<b>{query}</b>" 匹配的商品。\n━━━━━━━━━━━━━━━━━━━━━━\n👇 您可以点击下方按钮查看所有商品：'
            case Language.HI:
                msg = f'🔎 "<b>{query}</b>" से मेल खाता कोई उत्पाद नहीं मिला।\n━━━━━━━━━━━━━━━━━━━━━━\n👇 सभी उपलब्ध उत्पाद देखने के लिए नीचे क्लिक करें:'
            case Language.FR:
                msg = f'🔎 Aucun produit ne correspond au mot-clé "<b>{query}</b>".\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Cliquez ci-dessous pour voir tous les produits disponibles :'
            case Language.DE:
                msg = f'🔎 Keine Produkte für "<b>{query}</b>" gefunden.\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Klicken Sie unten, um alle verfügbaren Produkte anzuzeigen:'
            case Language.IT:
                msg = f'🔎 Nessun prodotto trovato per "<b>{query}</b>".\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Clicca qui sotto per vedere tutti i prodotti disponibili:'
            case Language.ES:
                msg = f'🔎 No se encontraron productos que coincidan con "<b>{query}</b>".\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Haz clic abajo para ver todos los productos disponibles:'
            case _:
                msg = f'🔎 No products found matching "<b>{query}</b>".\n━━━━━━━━━━━━━━━━━━━━━━\n👇 Click below to view all available products:'

    return msg, btn_all
