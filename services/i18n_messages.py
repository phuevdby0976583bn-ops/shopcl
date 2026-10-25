from enums.language import Language


def get_wallet_text(language: Language, user_name: str, telegram_id: int, balance: float, top_up: float, consume: float) -> tuple[str, dict]:
    match language:
        case Language.VI:
            text = (
                "👤 <b>VÍ & TÀI KHOẢN CỦA BẠN</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Tài khoản:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"💵 <b>Số dư khả dụng:</b> <b>{balance}$</b> (USDT)\n"
                f"📈 <b>Đã nạp:</b> {top_up:.2f}$ | 📉 <b>Đã tiêu:</b> {consume:.2f}$\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <i>Khuyên dùng <b>Binance Pay</b> hoặc <b>VietQR BIDV</b>: Nạp tự động nhận ngay sau vài giây.</i>\n"
                "👇 <b>Bấm nút bên dưới để nạp tiền tự động:</b>"
            )
            buttons = {
                "bank": "🏦 Chuyển khoản Ngân hàng (VietQR / BIDV)",
                "binance": "⚡ Binance Pay (0% Phí - Nhận 1s)",
                "onchain": "🌐 Nạp On-chain (BSC, TRX, TON...)",
                "history": "📦 Lịch sử mua hàng"
            }
        case Language.ZH:
            text = (
                "👤 <b>我的钱包与账户</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>账户:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"💵 <b>可用余额:</b> <b>${balance}</b> (USDT)\n"
                f"📈 <b>总充值:</b> ${top_up:.2f} | 📉 <b>总消费:</b> ${consume:.2f}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <i>推荐使用 <b>币安支付 (Binance Pay)</b>：0手续费，1-5秒自动到账。</i>\n"
                "👇 <b>请点击下方按钮进行自动充值:</b>"
            )
            buttons = {
                "bank": "🏦 越南银行卡 (VietQR / BIDV)",
                "binance": "⚡ 币安支付 Binance Pay (0手续费 - 秒到)",
                "onchain": "🌐 链上充值 (BSC, TRX, TON...)",
                "history": "📦 购买记录"
            }
        case _:
            text = (
                "👤 <b>YOUR WALLET & ACCOUNT</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🆔 <b>Account:</b> {user_name} (ID: <code>{telegram_id}</code>)\n"
                f"💵 <b>Available Balance:</b> <b>${balance}</b> (USDT)\n"
                f"📈 <b>Deposited:</b> ${top_up:.2f} | 📉 <b>Spent:</b> ${consume:.2f}\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "💡 <i>Recommended: <b>Binance Pay</b> (0% fee, instant credit in 1-5s).</i>\n"
                "👇 <b>Tap a button below to deposit automatically:</b>"
            )
            buttons = {
                "bank": "🏦 Vietnam Bank Transfer (VietQR / BIDV)",
                "binance": "⚡ Binance Pay (0% Fee - Instant 1s)",
                "onchain": "🌐 On-chain Deposit (BSC, TRX, TON...)",
                "history": "📦 Purchase History"
            }
    return text, buttons


def get_deposit_method_selection(language: Language) -> tuple[str, dict]:
    match language:
        case Language.VI:
            text = (
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
                "👇 <i>Vui lòng bấm chọn hình thức nạp bên dưới:</i>"
            )
            buttons = {
                "binance": "⚡ Binance Pay (0% Phí - Nhận ngay 1s)",
                "bank": "🏦 Ngân hàng VN (VietQR / BIDV)",
                "onchain": "🌐 Nạp Crypto On-chain"
            }
        case Language.ZH:
            text = (
                "💰 <b>请选择充值方式</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "1️⃣ <b>币安支付 (推荐 - 0手续费):</b>\n"
                "• 扫码或通过币安 Pay ID / UID 转账。\n"
                "• 系统1-5秒内自动查账并充值。\n\n"
                "2️⃣ <b>越南银行转账 (VietQR / BIDV):</b>\n"
                "• 扫码转账，全自动按汇率入账。\n\n"
                "3️⃣ <b>链上虚拟币充值:</b>\n"
                "• 支持 USDT, LTC, SOL, TRX 等。\n\n"
                "👇 <i>请在下方选择充值方式:</i>"
            )
            buttons = {
                "binance": "⚡ 币安支付 (0手续费 - 秒到)",
                "bank": "🏦 越南银行 (VietQR / BIDV)",
                "onchain": "🌐 链上虚拟币"
            }
        case _:
            text = (
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
                "👇 <i>Please select a deposit method below:</i>"
            )
            buttons = {
                "binance": "⚡ Binance Pay (0% Fee - Instant 1s)",
                "bank": "🏦 Vietnam Bank (VietQR / BIDV)",
                "onchain": "🌐 On-chain Crypto"
            }
    return text, buttons


def get_out_of_stock_text(language: Language, cat_name: str, subcat_name: str) -> str:
    match language:
        case Language.VI:
            return (
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Mặt hàng:</b> <code>{subcat_name}</code>\n\n"
                "⚠️ <b>Hiện tại mặt hàng này đang tạm hết hàng!</b>\n"
                "Vui lòng quay lại sau ít phút hoặc chọn mặt hàng khác."
            )
        case Language.ZH:
            return (
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>商品:</b> <code>{subcat_name}</code>\n\n"
                "⚠️ <b>该商品暂时缺货！</b>\n"
                "请稍后再来或选择其他商品。"
            )
        case _:
            return (
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Item:</b> <code>{subcat_name}</code>\n\n"
                "⚠️ <b>This item is currently out of stock!</b>\n"
                "Please check back in a few minutes or choose another item."
            )


def get_select_quantity_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, sym: str, desc: str, available_qty: int) -> str:
    match language:
        case Language.VI:
            return (
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Tài khoản:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>Giá bán:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"📝 <b>Mô tả:</b> <i>{desc}</i>\n"
                f"📊 <b>Còn trong kho:</b> <code>{available_qty}</code> nick\n\n"
                "🔢 <b>Vui lòng chọn số lượng cần mua bên dưới:</b>"
            )
        case Language.ZH:
            return (
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>账号:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>单价:</b> <code>{unit_price:.2f} {sym}</code> / 个\n"
                f"📝 <b>描述:</b> <i>{desc}</i>\n"
                f"📊 <b>当前库存:</b> <code>{available_qty}</code> 个\n\n"
                "🔢 <b>请在下方选择购买数量:</b>"
            )
        case _:
            return (
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"📝 <b>Description:</b> <i>{desc}</i>\n"
                f"📊 <b>In stock:</b> <code>{available_qty}</code> pcs\n\n"
                "🔢 <b>Please select quantity to buy below:</b>"
            )


def get_instant_buy_confirm_text(language: Language, cat_name: str, subcat_name: str, unit_price: float, qty: int, total_price: float, sym: str, balance: float, is_enough: bool, missing: float) -> tuple[str, dict]:
    match language:
        case Language.VI:
            status_text = (
                "✅ <b>Số dư ví đủ thanh toán. Bấm 'MUA NGAY' bên dưới để nhận tài khoản tức thì!</b>"
                if is_enough
                else f"⚠️ <b>Số dư ví không đủ! Còn thiếu: <code>{missing:.2f} {sym}</code>. Vui lòng nạp tiền vào ví trước khi mua.</b>"
            )
            msg = (
                "🛒 <b>XÁC NHẬN MUA TÀI KHOẢN (TRỪ TIỀN TRỰC TIẾP)</b>\n\n"
                f"📁 <b>Danh mục:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Loại tài khoản:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>Đơn giá:</b> <code>{unit_price:.2f} {sym}</code> / nick\n"
                f"🔢 <b>Số lượng mua:</b> <code>{qty}</code> nick\n"
                f"💰 <b>TỔNG THANH TOÁN:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Số dư ví hiện tại:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Lưu ý: Hệ thống tự động Check Live UID Facebook qua Graph API ngay khi giao hàng, cam kết 100% clone Live!</i>"
            )
            labels = {
                "buy": f"🚀 MUA NGAY ({total_price:.2f} {sym})",
                "back_qty": "🔢 Chọn lại số lượng",
                "cancel": "❌ Hủy bỏ",
                "binance": "⚡ Nạp Binance Pay (0% Phí - Nhận ngay 1s)",
                "bank": "🏦 Nạp Ngân Hàng (VietQR / BIDV)",
                "crypto": "🌐 Nạp On-chain Crypto"
            }
        case Language.ZH:
            status_text = (
                "✅ <b>钱包余额充足，点击下方'立即购买'即可秒发卡！</b>"
                if is_enough
                else f"⚠️ <b>余额不足！还缺: <code>{missing:.2f} {sym}</code>，请先充值后再购买。</b>"
            )
            msg = (
                "🛒 <b>确认购买账号 (余额直接扣款)</b>\n\n"
                f"📁 <b>分类:</b> <code>{cat_name}</code>\n"
                f"📦 <b>商品:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>单价:</b> <code>{unit_price:.2f} {sym}</code> / 个\n"
                f"🔢 <b>数量:</b> <code>{qty}</code> 个\n"
                f"💰 <b>总需支付:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>当前钱包余额:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>注意: 发货前系统将自动通过 Facebook Graph API 实时检测 Live，承诺 100% Live！</i>"
            )
            labels = {
                "buy": f"🚀 立即购买 ({total_price:.2f} {sym})",
                "back_qty": "🔢 重选数量",
                "cancel": "❌ 取消",
                "binance": "⚡ 币安支付 (0手续费)",
                "bank": "🏦 越南银行卡 (VietQR)",
                "crypto": "🌐 链上充值 (On-chain)"
            }
        case _:
            status_text = (
                "✅ <b>Sufficient balance. Click 'BUY NOW' below to receive accounts immediately!</b>"
                if is_enough
                else f"⚠️ <b>Insufficient balance! Missing: <code>{missing:.2f} {sym}</code>. Please top up your wallet.</b>"
            )
            msg = (
                "🛒 <b>INSTANT PURCHASE CONFIRMATION</b>\n\n"
                f"📁 <b>Category:</b> <code>{cat_name}</code>\n"
                f"📦 <b>Account:</b> <code>{subcat_name}</code>\n"
                f"💵 <b>Unit Price:</b> <code>{unit_price:.2f} {sym}</code> / acc\n"
                f"🔢 <b>Quantity:</b> <code>{qty}</code> pcs\n"
                f"💰 <b>TOTAL AMOUNT:</b> <code>{total_price:.2f} {sym}</code>\n\n"
                f"💳 <b>Wallet Balance:</b> <code>{balance:.2f} {sym}</code>\n"
                f"{status_text}\n\n"
                "⚡ <i>Note: Live Facebook UIDs are automatically verified via Graph API upon delivery!</i>"
            )
            labels = {
                "buy": f"🚀 BUY NOW ({total_price:.2f} {sym})",
                "back_qty": "🔢 Change quantity",
                "cancel": "❌ Cancel",
                "binance": "⚡ Deposit Binance Pay (0% Fee)",
                "bank": "🏦 Deposit Vietnam Bank (VietQR)",
                "crypto": "🌐 Deposit On-chain Crypto"
            }
    return msg, labels
