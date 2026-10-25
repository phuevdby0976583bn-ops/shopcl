import html as html_lib
import json
import os
from fastapi import Request
from sqladmin import BaseView, expose
from starlette.responses import HTMLResponse, RedirectResponse

import config
from utils.utils import decode_token
from services.policy_defaults import (
    DEFAULT_WARRANTY_LEGAL_POLICY,
    DEFAULT_WARRANTY_SHORT_SUMMARY,
)


async def render_unified_settings_page(request: Request, default_active_tab: str = 'binance') -> HTMLResponse:

        # 1. Bắt buộc kiểm tra đăng nhập Admin
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        webhook_host = config.WEBHOOK_HOST or "https://shopcl.onrender.com"
        webhook_host = (config.WEBHOOK_HOST or "https://shopcl.onrender.com").rstrip("/")
        api_binance_check = "/api/binancepay/check-now"
        api_settings_save = "/api/settings/save"
        api_fb_check_uid = "/api/facebook/check-uid"
        api_fb_scan_stock = "/api/facebook/scan-stock"
        api_fb_clean_die = "/api/facebook/clean-die"
        api_fb_clean_dups = "/api/facebook/clean-duplicates"
        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"
        admin_token = token or ""

        from db import get_db_session
        from services.settings import SettingsService

        async with get_db_session() as session:
            cur_settings = await SettingsService.get_all_settings(session)

        binance_uid = cur_settings.get("BINANCE_UID") or "805398854"
        binance_api_key = cur_settings.get("BINANCE_API_KEY") or ""
        binance_api_secret = cur_settings.get("BINANCE_API_SECRET") or ""

        krypto_api_key = cur_settings.get("KRYPTO_EXPRESS_API_KEY") or ""
        krypto_api_secret = cur_settings.get("KRYPTO_EXPRESS_API_SECRET") or ""
        krypto_api_url = cur_settings.get("KRYPTO_EXPRESS_API_URL") or "https://kryptoexpress.pro/api"

        bank_token = cur_settings.get("BANK_BIDV_TOKEN") or ""
        bank_acc_num = cur_settings.get("BANK_ACCOUNT_NUMBER") or "8880117869"
        bank_acc_name = cur_settings.get("BANK_ACCOUNT_NAME") or "NGUYEN XUAN TRUONG"
        bank_code = cur_settings.get("BANK_CODE") or "BIDV"
        bank_rate = cur_settings.get("BANK_EXCHANGE_RATE", 26000)
        bank_auto_check = cur_settings.get("BANK_AUTO_CHECK", True)
        bank_auto_attr = "checked" if bank_auto_check else ""
        is_bank_ready = bool(bank_token)
        bank_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_bank_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa điền Token ThueApi.pro</span>'
        api_bank_check = "/api/bank/check-now"

        fwd_mode = cur_settings.get("CRYPTO_FORWARDING_MODE", False)
        only_usdt = cur_settings.get("ONLY_USDT_MODE", False)
        bnb_fwd = cur_settings.get("BNB_FORWARDING_ADDRESS") or ""
        sol_fwd = cur_settings.get("SOL_FORWARDING_ADDRESS") or ""
        eth_fwd = cur_settings.get("ETH_FORWARDING_ADDRESS") or ""
        btc_fwd = cur_settings.get("BTC_FORWARDING_ADDRESS") or ""
        ltc_fwd = cur_settings.get("LTC_FORWARDING_ADDRESS") or ""
        doge_fwd = cur_settings.get("DOGE_FORWARDING_ADDRESS") or ""

        only_usdt_checked_attr = "checked" if only_usdt else ""

        fb_filter_dups = cur_settings.get("FB_FILTER_DUPLICATE_UIDS", True)
        fb_filter_dups_attr = "checked" if fb_filter_dups else ""
        fb_check_upload = cur_settings.get("FB_AUTO_CHECK_ON_UPLOAD", True)
        fb_delete_upload = cur_settings.get("FB_AUTO_DELETE_DIE_ON_UPLOAD", True)
        fb_check_delivery = cur_settings.get("FB_CHECK_LIVE_BEFORE_DELIVERY", True)
        fb_delete_delivery = cur_settings.get("FB_AUTO_DELETE_DIE_ON_DELIVERY", True)
        fb_keywords = cur_settings.get("FB_CATEGORY_KEYWORDS", "facebook, fb, clone, via, bm")

        fb_check_up_attr = "checked" if fb_check_upload else ""
        fb_del_up_attr = "checked" if fb_delete_upload else ""
        fb_check_deliv_attr = "checked" if fb_check_delivery else ""
        fb_del_deliv_attr = "checked" if fb_delete_delivery else ""
        fb_cron_interval = cur_settings.get("FB_CRON_CHECK_INTERVAL_MINUTES", 30)
        fb_cron_notify = cur_settings.get("FB_CRON_NOTIFY_ADMIN", True)
        fb_cron_notify_attr = "checked" if fb_cron_notify else ""
        cron_webhook_url = f"{webhook_host}/api/cron/check-live?token={api_key}&delete_die=true"

        is_binance_ready = bool(binance_api_key and binance_api_secret)
        binance_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang hoạt động tự động</span>' if is_binance_ready else '<span class="badge bg-warning text-dark"><i class="fa-solid fa-triangle-exclamation me-1"></i> Chưa cấu hình API Key & Secret</span>'

        fwd_checked_attr = "checked" if fwd_mode else ""

        deposit_bonus_enabled = cur_settings.get("DEPOSIT_BONUS_ENABLED", False)
        deposit_bonus_enabled_attr = "checked" if deposit_bonus_enabled else ""
        deposit_bonus_tiers = cur_settings.get("DEPOSIT_BONUS_TIERS") or "100:2,200:5,300:6,500:7,1000:8"
        bonus_badge = '<span class="badge bg-success"><i class="fa-solid fa-circle-check me-1"></i> Đang BẬT khuyến mãi</span>' if deposit_bonus_enabled else '<span class="badge bg-secondary"><i class="fa-solid fa-power-off me-1"></i> Đang TẮT</span>'

        min_deposit_usdt = float(cur_settings.get("MIN_DEPOSIT_USDT") or getattr(config, "MIN_DEPOSIT_USDT", 1.0) or 1.0)
        try:
            bank_rate_val = float(bank_rate)
        except Exception:
            bank_rate_val = 26000.0

        min_deposit_vnd_setting = cur_settings.get("MIN_DEPOSIT_VND") or getattr(config, "MIN_DEPOSIT_VND", None)
        if min_deposit_vnd_setting is not None:
            try:
                min_deposit_vnd = float(min_deposit_vnd_setting)
            except Exception:
                min_deposit_vnd = min_deposit_usdt * bank_rate_val
        else:
            min_deposit_vnd = min_deposit_usdt * bank_rate_val

        from enums.language import Language
        from services.deposit_bonus import DepositBonusService
        preview_text = DepositBonusService.get_bonus_display_text(Language.VI)
        if not preview_text:
            preview_bonus_html = f"Nhập số USDT muốn nạp (tối thiểu {min_deposit_usdt:g}):\n(Khuyến mãi đang TẮT - Bot chỉ hiện khung nhập tiền sạch, không có chữ thưởng)"
        else:
            preview_bonus_html = f"Nhập số USDT muốn nạp (tối thiểu {min_deposit_usdt:g}):\n\n{preview_text}"

        
        current_policy = cur_settings.get("WARRANTY_LEGAL_POLICY") or DEFAULT_WARRANTY_LEGAL_POLICY
        current_summary = cur_settings.get("WARRANTY_SHORT_SUMMARY") or DEFAULT_WARRANTY_SHORT_SUMMARY
        policy_escaped = html_lib.escape(current_policy)
        summary_escaped = html_lib.escape(current_summary)
        default_policy_json = json.dumps(DEFAULT_WARRANTY_LEGAL_POLICY)
        default_summary_json = json.dumps(DEFAULT_WARRANTY_SHORT_SUMMARY)
        initial_policy_json = json.dumps(current_policy)
        initial_summary_json = json.dumps(current_summary)

        is_policy_active = (default_active_tab == "policy")
        binance_nav_cls = "nav-link" if is_policy_active else "nav-link active"
        binance_pane_cls = "tab-pane fade" if is_policy_active else "tab-pane fade show active"
        policy_nav_cls = "nav-link active" if is_policy_active else "nav-link"
        policy_pane_cls = "tab-pane fade show active" if is_policy_active else "tab-pane fade"

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cấu Hình Cổng Nạp USDT & Binance Pay - Bubba Gump</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #1e293b; }}
        .card {{ border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; background: #fff; }}
        .card-header {{ background-color: #ffffff; border-bottom: 1px solid #f1f5f9; font-weight: 600; padding: 14px 20px; }}
        .nav-pills .nav-link {{ color: #475569; font-weight: 500; border-radius: 8px; padding: 10px 16px; margin-right: 8px; transition: all 0.2s; }}
        .nav-pills .nav-link.active {{ background-color: #0d6efd; color: #fff; box-shadow: 0 4px 12px rgba(13,110,253,0.25); }}
        .step-badge {{ display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 50%; background: #0d6efd; color: #fff; font-weight: bold; font-size: 0.85rem; margin-right: 8px; }}
        .step-badge.success {{ background: #10b981; }}
        .step-badge.warning {{ background: #f59e0b; }}
    
        .editor-textarea {{
            background-color: #ffffff;
            color: #0f172a;
            font-family: "Fira Code", Consolas, "Courier New", monospace;
            font-size: 13.5px;
            line-height: 1.6;
            border: 1px solid #cbd5e1;
            border-radius: 10px;
            padding: 16px;
            resize: vertical;
        }}
        .editor-textarea:focus {{
            background-color: #ffffff;
            color: #0f172a;
            border-color: #0d6efd;
            box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.15);
        }}
        .tg-mockup {{
            max-width: 480px;
            margin: 0 auto;
            background: #17212b;
            border-radius: 24px;
            border: 8px solid #0e1621;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .tg-header {{
            background: #242f3d;
            padding: 12px 16px;
            display: flex;
            align-items: center;
            border-bottom: 1px solid #10161f;
        }}
        .tg-avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: #0284c7;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            margin-right: 12px;
        }}
        .tg-body {{
            background: #0e1621;
            padding: 16px;
            min-height: 420px;
            max-height: 550px;
            overflow-y: auto;
        }}
        .tg-bubble {{
            background: #182533;
            color: #f5f5f5;
            padding: 14px 16px;
            border-radius: 12px 12px 12px 2px;
            font-size: 13.5px;
            line-height: 1.5;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .tg-bubble b {{ color: #ffffff; font-weight: 700; }}
        .tg-bubble i {{ color: #94a3b8; font-style: italic; }}
        .tg-button {{
            background: #2b5278;
            color: #ffffff;
            border-radius: 8px;
            padding: 8px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: 600;
            margin-top: 6px;
            cursor: pointer;
        }}

    
        /* An tab ngoai sidebar Chinh sach & Bao hanh */
        .navbar-nav a.nav-link[href*="/policy"], .navbar-nav .nav-item:has(a[href*="/policy"]), .navbar-nav a.nav-link:has(.fa-shield-halved), .navbar-nav .nav-item:has(.fa-shield-halved) {{ display: none !important; }}
    </style>
</head>
<body class="p-3 p-md-4">
    <!-- Safe JSON Payloads for Policy & Settings -->
    <script type="application/json" id="data-default-policy">{default_policy_json}</script>
    <script type="application/json" id="data-default-summary">{default_summary_json}</script>
    <script type="application/json" id="data-initial-policy">{initial_policy_json}</script>
    <script type="application/json" id="data-initial-summary">{initial_summary_json}</script>
    <div class="container-fluid" style="max-width: 1400px;">
        <!-- Header -->
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom">
            <div>
                <h3 class="fw-bold mb-1 text-dark"><i class="fa-solid fa-coins text-warning me-2"></i>Cấu Hình Cổng Nạp Tiền Trực Tiếp</h3>
                <p class="text-muted mb-0">Cấu hình trực tiếp tại đây để lưu vào Database Supabase mà <b>KHÔNG CẦN</b> phải vào Render chỉnh biến môi trường!</p>
            </div>
            <div class="mt-2 mt-md-0">
                <a href="/admin" class="btn btn-outline-secondary"><i class="fa-solid fa-arrow-left me-1"></i> Quay lại Dashboard</a>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <ul class="nav nav-pills mb-4" id="pills-tab" role="tablist">
            <li class="nav-item">
                <button class="{binance_nav_cls}" id="tab-binance-nav" data-bs-toggle="pill" data-bs-target="#tab-binance">
                    <i class="fa-brands fa-bitcoin text-warning me-1"></i> 1. Cổng Nạp Binance Pay (0% Phí - Quét Mã App & API)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-usdt">
                    <i class="fa-solid fa-wallet text-success me-1"></i> 2. Cổng Nạp USDT Tự Động (KryptoExpress) & Rút Ví
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-bank">
                    <i class="fa-solid fa-building-columns text-info me-1"></i> 3. Cổng Nạp Ngân Hàng BIDV (ThueApi.pro & VietQR)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-facebook">
                    <i class="fa-brands fa-facebook text-primary me-1"></i> 4. Cấu Hình Clone Facebook (Check Live & Tự Động Xóa DIE)
                </button>
            </li>
            <li class="nav-item">
                <button class="nav-link" data-bs-toggle="pill" data-bs-target="#tab-bonus">
                    <i class="fa-solid fa-gift text-danger me-1"></i> 5. Khuyến Mãi Nạp Tiền (Deposit Bonus)
                </button>
            </li>
                    <li class="nav-item">
                <button class="{policy_nav_cls}" id="tab-policy-nav" data-bs-toggle="pill" data-bs-target="#tab-policy" type="button" role="tab">
                    <i class="fa-solid fa-shield-halved text-primary me-1"></i> 6. Chính Sách & Bảo Hành (Pháp Lý & Telegram)
                </button>
            </li>
        </ul>

        <div class="tab-content" id="pills-tabContent">
            <!-- TAB 1: BINANCE PAY -->
            <div class="{binance_pane_cls}" id="tab-binance">
                <div class="row g-4">
                    <!-- Cột 1: Form lưu trực tiếp -->
                    <div class="col-lg-6">
                        <div class="card border-warning h-100 shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-brands fa-bitcoin text-warning me-2"></i>Cấu Hình Binance Pay & Open API</h5>
                                {binance_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-success py-2 small mb-3">
                                    <i class="fa-solid fa-bolt me-1"></i> <b>Nạp 0% Phí - Nhận 1s:</b> Khách chuyển tiền nội bộ Binance vào UID của bạn, Bot tự đọc lịch sử qua API và tự động cộng số dư ngay lập tức!
                                </div>

                                <form id="binanceForm" onsubmit="event.preventDefault(); saveBinanceSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Binance UID Cá Nhân Của Bạn (Pay ID):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-id-badge text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace fw-bold" id="binance_uid" value="{binance_uid}" placeholder="VD: 805398854" required>
                                        </div>
                                        <div class="form-text small">UID hiển thị trên app Binance của bạn để khách chuyển USDT vào.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Binance API Key (Chỉ đọc - Read-only):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key"></i></span>
                                            <input type="password" class="form-control font-monospace" id="binance_api_key" value="{binance_api_key}" placeholder="Dán Binance API Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('binance_api_key', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Binance Secret Key:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-lock"></i></span>
                                            <input type="password" class="form-control font-monospace" id="binance_api_secret" value="{binance_api_secret}" placeholder="Dán Binance Secret Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('binance_api_secret', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">4. Số Tiền Nạp Tối Thiểu (USDT):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-coins text-warning"></i></span>
                                            <input type="number" class="form-control font-monospace fw-bold text-dark" id="binance_min_deposit" value="{min_deposit_usdt:g}" step="0.1" min="0.01" placeholder="VD: 1.0" oninput="syncMinDepositInputs(this.value)">
                                            <span class="input-group-text bg-light fw-bold">USDT</span>
                                        </div>
                                        <div class="form-text small">Hạn mức nạp tối thiểu toàn hệ thống (áp dụng cho cả Binance Pay, Ngân hàng và On-chain). Mặc định: 1.0 USDT.</div>
                                    </div>

                                    <div id="binanceSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="d-flex flex-wrap gap-2 pt-2 border-top">
                                        <button type="submit" class="btn btn-warning fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Binance Ngay
                                        </button>
                                        <button type="button" class="btn btn-outline-secondary" onclick="syncBinancePay()">
                                            <i class="fa-solid fa-rotate me-1"></i> Quét Giao Dịch Ngay
                                        </button>
                                    </div>
                                </form>
                                <div id="syncResult" class="mt-3 p-2 bg-light rounded small" style="display:none;"></div>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Hướng dẫn lấy key -->
                    <div class="col-lg-6">
                        <div class="card h-100 shadow-sm">
                            <div class="card-header py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-shield-halved text-success me-2"></i>Hướng Dẫn Lấy API Key Binance (An Toàn 100%)</h5>
                            </div>
                            <div class="card-body">
                                <p class="text-muted small">Bạn chỉ cần cấp quyền <b>Chỉ Đọc (Read-only)</b> để bot kiểm tra giao dịch nạp. Bot tuyệt đối không thể rút tiền hay giao dịch spot, tiền trong ví an toàn tuyệt đối.</p>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge">1</span>
                                    <div>
                                        <b>Mở Quản lý API trên Binance:</b>
                                        <div class="small text-muted">Mở Binance trên web ➔ Bấm Avatar góc trên ➔ Chọn <b>Account</b> ➔ <b>API Management</b>. Hoặc truy cập: <a href="https://www.binance.com/en/my/settings/api-management" target="_blank" class="text-decoration-none">binance.com/en/my/settings/api-management</a></div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge">2</span>
                                    <div>
                                        <b>Tạo API Key:</b>
                                        <div class="small text-muted">Bấm <b>Create API</b> ➔ Chọn loại <b>System generated (HMAC)</b> ➔ Đặt tên ví dụ: <code>ShopBotTelegram</code> ➔ Xác thực OTP.</div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start mb-3">
                                    <span class="step-badge warning">3</span>
                                    <div>
                                        <b>Cài đặt Quyền (API Restrictions):</b>
                                        <div class="small text-muted"><span class="badge bg-success">Chỉ tích: Enable Reading</span>. <span class="badge bg-danger">KHÔNG TÍCH</span> <i>Enable Withdrawals</i> hay <i>Enable Spot Trading</i>.</div>
                                    </div>
                                </div>
                                <div class="d-flex align-items-start">
                                    <span class="step-badge success">4</span>
                                    <div>
                                        <b>Dán vào Form & Bấm Lưu:</b>
                                        <div class="small text-muted">Copy <b>API Key</b> và <b>Secret Key</b> dán sang form bên trái rồi bấm nút <b>Lưu Cấu Hình Binance Ngay</b>. Cài đặt được lưu vào Supabase và kích hoạt ngay tức thì!</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: KRYPTOEXPRESS & AUTO FORWARDING -->
            <div class="tab-pane fade" id="tab-usdt">
                <div class="row g-4">
                    <!-- Cột 1: Cấu hình KryptoExpress -->
                    <div class="col-lg-6">
                        <div class="card border-success h-100 shadow-sm">
                            <div class="card-header bg-success bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-wallet text-success me-2"></i>Cấu Hình Cổng Nạp USDT (KryptoExpress)</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    Cổng nạp USDT on-chain qua mạng BEP20, Solana, TRC20, Polygon... Tự động tạo ví riêng kèm mã QR cho từng đơn nạp.
                                </div>

                                <form id="kryptoForm" onsubmit="event.preventDefault(); saveKryptoSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. KryptoExpress API Key:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key"></i></span>
                                            <input type="password" class="form-control font-monospace" id="krypto_api_key" value="{krypto_api_key}" placeholder="Dán KryptoExpress API Key vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('krypto_api_key', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. KryptoExpress API Secret:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-lock"></i></span>
                                            <input type="password" class="form-control font-monospace" id="krypto_api_secret" value="{krypto_api_secret}" placeholder="Dán KryptoExpress API Secret vào đây">
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('krypto_api_secret', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. API Base URL:</label>
                                        <input type="text" class="form-control font-monospace small" id="krypto_api_url" value="{krypto_api_url}" required>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">4. Số Tiền Nạp Tối Thiểu (USDT):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-coins text-success"></i></span>
                                            <input type="number" class="form-control font-monospace fw-bold text-dark" id="krypto_min_deposit" value="{min_deposit_usdt:g}" step="0.1" min="0.01" placeholder="VD: 1.0" oninput="syncMinDepositInputs(this.value)">
                                            <span class="input-group-text bg-light fw-bold">USDT</span>
                                        </div>
                                        <div class="form-text small">Hạn mức nạp tối thiểu cho khách khi nạp tiền On-chain.</div>
                                    </div>

                                    <div class="mb-3 p-2 bg-light rounded small">
                                        <b>Webhook URL dán vào KryptoExpress:</b>
                                        <div class="input-group input-group-sm mt-1">
                                            <input type="text" class="form-control font-monospace" value="{webhook_host}/cryptoprocessing/event" readonly id="kryptoWebhook">
                                            <button class="btn btn-outline-secondary" type="button" onclick="navigator.clipboard.writeText(document.getElementById('kryptoWebhook').value); alert('Đã sao chép Webhook URL!');"><i class="fa-regular fa-copy"></i> Copy</button>
                                        </div>
                                    </div>

                                    <div id="kryptoSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-success fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình KryptoExpress
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Cấu hình tự động bắn tiền về ví sàn Binance (Auto-Forwarding) -->
                    <div class="col-lg-6">
                        <div class="card border-primary h-100 shadow-sm">
                            <div class="card-header bg-primary bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-arrow-right-arrow-left text-primary me-2"></i>Tự Động Bắn Tiền Về Ví Sàn Binance (Auto-Forwarding)</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-primary py-2 small mb-3">
                                    Khi khách nạp tiền thành công, cổng thanh toán có thể tự động bắn thẳng số USDT đó về địa chỉ ví Binance của bạn mà không cần bạn phải thao tác rút tay!
                                </div>

                                <form id="forwardingForm" onsubmit="event.preventDefault(); saveForwardingSettings();">
                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-info">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="only_usdt_mode" {only_usdt_checked_attr}>
                                        <label class="form-check-label fw-bold text-primary" for="only_usdt_mode">⚡ Chế độ Nạp Gọn: Chỉ hiện Binance Pay & USDT trên Bot</label>
                                        <div class="small text-muted ms-4">Ẩn bớt các coin phí cao (BTC, ETH, LTC, DOGE...) để khách không nạp nhầm. Khi bật, bot chỉ hiện Binance Pay (0% phí) và các mạng USDT (BEP20, SOL).</div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="crypto_forwarding_mode" {fwd_checked_attr}>
                                        <label class="form-check-label fw-bold text-success" for="crypto_forwarding_mode">🔁 Bật tự động chuyển tiếp tiền về ví cá nhân (Auto-Forwarding)</label>
                                        <div class="small text-muted ms-4">Khi khách nạp coin nào, KryptoExpress sẽ tự động chuyển thẳng coin đó về đúng địa chỉ ví tương ứng bên dưới.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Địa chỉ ví USDT / BNB (Mạng BNB Smart Chain - BEP20 - Rẻ nhất):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-ethereum text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="bnb_forwarding_address" value="{bnb_fwd}" placeholder="0x... (Lấy trong mục Nạp USDT mạng BEP20 của Binance)">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Địa chỉ ví USDT / SOL (Mạng Solana - SOL):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-sun text-info"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="sol_forwarding_address" value="{sol_fwd}" placeholder="Địa chỉ ví SOL trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Địa chỉ ví USDT / ETH / USDC (Mạng ERC-20 - Ethereum):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-ethereum text-primary"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="eth_forwarding_address" value="{eth_fwd}" placeholder="0x... (Địa chỉ ví ERC20 trên Binance)">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">4. Địa chỉ ví Bitcoin (BTC):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-brands fa-bitcoin text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="btc_forwarding_address" value="{btc_fwd}" placeholder="Địa chỉ ví BTC trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">5. Địa chỉ ví Litecoin (LTC):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-coins text-secondary"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="ltc_forwarding_address" value="{ltc_fwd}" placeholder="Địa chỉ ví LTC trên Binance">
                                        </div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">6. Địa chỉ ví Dogecoin (DOGE):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-dog text-warning"></i></span>
                                            <input type="text" class="form-control font-monospace small" id="doge_forwarding_address" value="{doge_fwd}" placeholder="Địa chỉ ví DOGE trên Binance">
                                        </div>
                                    </div>

                                    <div id="fwdSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-primary fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Ví Chuyển Tiếp
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

<!-- TAB: NGÂN HÀNG VIỆT NAM (BIDV / THUEAPI.PRO) -->
            <div class="tab-pane fade" id="tab-bank">
                <div class="row g-4">
                    <!-- Cột 1: Form cấu hình BIDV & ThueApi.pro -->
                    <div class="col-lg-6">
                        <div class="card border-info h-100 shadow-sm">
                            <div class="card-header bg-info bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-building-columns text-info me-2"></i>Cấu Hình Ngân Hàng BIDV (ThueApi.pro)</h5>
                                {bank_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-bolt me-1"></i> <b>Tự động 100%:</b> Khách nạp qua mã VietQR, tiền vào tài khoản BIDV của bạn, hệ thống gọi API <b>ThueApi.pro</b> đọc lịch sử giao dịch và tự động cộng tiền USD vào số dư bot sau 10-30 giây!
                                </div>

                                <form id="bankForm" onsubmit="event.preventDefault(); saveBankSettings();">
                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">1. Token BIDV (Lấy từ ThueApi.pro):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-key text-info"></i></span>
                                            <input type="password" class="form-control font-monospace" id="bank_token" value="{bank_token}" placeholder="Dán token BIDV từ thueapi.pro vào đây" required>
                                            <button class="btn btn-outline-secondary" type="button" onclick="togglePass('bank_token', this)"><i class="fa-solid fa-eye"></i></button>
                                        </div>
                                        <div class="form-text small">Lấy trong mục API V2 tại <code>thueapi.pro/historyapibidvv2/:tokenbidv</code></div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">2. Số Tài Khoản Nhận Tiền (STK):</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-credit-card text-success"></i></span>
                                            <input type="text" class="form-control font-monospace fw-bold" id="bank_account_number" value="{bank_acc_num}" placeholder="VD: 8880117869" required>
                                        </div>
                                        <div class="form-text small">Số tài khoản BIDV của bạn để khách chuyển tiền tới.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">3. Tên Chủ Tài Khoản:</label>
                                        <div class="input-group">
                                            <span class="input-group-text"><i class="fa-solid fa-user text-primary"></i></span>
                                            <input type="text" class="form-control" id="bank_account_name" value="{bank_acc_name}" placeholder="VD: NGUYEN VAN A">
                                        </div>
                                        <div class="form-text small">Tên in trên tài khoản ngân hàng (viết hoa không dấu).</div>
                                    </div>

                                    <div class="row g-2 mb-3">
                                        <div class="col-sm-6">
                                            <label class="form-label fw-bold small text-muted">4. Mã Ngân Hàng:</label>
                                            <input type="text" class="form-control font-monospace fw-bold" id="bank_code" value="{bank_code}" placeholder="BIDV" readonly>
                                        </div>
                                        <div class="col-sm-6">
                                            <label class="form-label fw-bold small text-muted">5. Tỷ Giá Quy Đổi (VNĐ / 1$):</label>
                                            <div class="input-group">
                                                <input type="number" class="form-control font-monospace fw-bold text-success" id="bank_exchange_rate" value="{bank_rate}" step="100" min="1000" oninput="syncMinDepositInputs(document.getElementById('bank_min_deposit').value)">
                                                <span class="input-group-text small">đ / 1$</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div class="mb-3 p-3 bg-light rounded border">
                                        <div class="row g-3">
                                            <div class="col-md-6">
                                                <label class="form-label fw-bold text-success mb-1">
                                                    <i class="fa-solid fa-money-bill-wave me-1"></i> 6. Hạn Mức Nạp Tối Thiểu (VNĐ):
                                                </label>
                                                <div class="input-group">
                                                    <input type="number" class="form-control font-monospace fw-bold text-success border-success" id="bank_min_deposit_vnd" value="{min_deposit_vnd:.0f}" step="1000" min="1000" placeholder="VD: 20000" oninput="onMinVndChange(this.value)">
                                                    <span class="input-group-text fw-bold bg-success text-white">VNĐ</span>
                                                </div>
                                                <div class="form-text small">Khách nạp qua BIDV / VietQR tối thiểu số tiền VNĐ này (VD: 10000, 20000, 50000 đ).</div>
                                            </div>
                                            <div class="col-md-6">
                                                <label class="form-label fw-bold text-primary mb-1">
                                                    <i class="fa-solid fa-coins me-1"></i> Quy Đổi Ra USDT ($):
                                                </label>
                                                <div class="input-group">
                                                    <input type="number" class="form-control font-monospace fw-bold text-primary border-primary" id="bank_min_deposit" value="{min_deposit_usdt:g}" step="0.01" min="0.01" placeholder="VD: 1.0" oninput="onMinUsdtChange(this.value)">
                                                    <span class="input-group-text fw-bold bg-primary text-white">USDT / $</span>
                                                </div>
                                                <div class="form-text small">Tự động quy đổi theo tỷ giá (<span id="bank_min_vnd_preview">{min_deposit_vnd:,.0f}</span> đ).</div>
                                            </div>
                                        </div>
                                    </div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-info">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="bank_auto_check" {bank_auto_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="bank_auto_check">
                                            <i class="fa-solid fa-robot text-info me-1"></i> Tự Động Quét & Cộng Tiền Ngân Hàng (24/7)
                                        </label>
                                        <div class="small text-muted ms-4">Bot sẽ tự động quét API ThueApi.pro mỗi 15 giây. Khi khách chuyển đúng nội dung <code>NAP &lt;id&gt;</code>, số dư sẽ được cộng ngay lập tức!</div>
                                    </div>

                                    <div id="bankSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top d-flex gap-2">
                                        <button type="button" class="btn btn-info text-white fw-bold px-4" onclick="saveBankSettings()">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Ngân Hàng
                                        </button>
                                        <button type="button" class="btn btn-outline-info fw-bold" onclick="checkBankTransactionsNow()">
                                            <i class="fa-solid fa-rotate me-1"></i> Quét Giao Dịch Ngay
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Hướng dẫn lấy token từ ThueApi.pro -->
                    <div class="col-lg-6">
                        <div class="card bg-light border-0 shadow-sm h-100">
                            <div class="card-body">
                                <h5 class="fw-bold text-dark mb-3"><i class="fa-solid fa-book-open-reader text-info me-2"></i>Hướng Dẫn Tích Hợp ThueApi.pro (3 Bước)</h5>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">1</div>
                                    <div>
                                        <div class="fw-bold">Đăng ký & Thêm tài khoản BIDV trên ThueApi.pro:</div>
                                        <div class="small text-muted">Truy cập <a href="https://thueapi.pro" target="_blank" class="fw-bold text-info">https://thueapi.pro</a> ➔ Cổng thanh toán ➔ Thêm tài khoản ngân hàng BIDV của bạn (STK <code>8880117869</code>).</div>
                                    </div>
                                </div>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">2</div>
                                    <div>
                                        <div class="fw-bold">Lấy Token BIDV:</div>
                                        <div class="small text-muted">Vào menu <b>Nhà phát triển</b> ➔ Chọn <b>API V2</b> ➔ Chọn tab <b>BIDV</b> ➔ Copy đoạn token trong đường dẫn <code>https://thueapi.pro/historyapibidvv2/<b>:tokenbidv</b></code>.</div>
                                    </div>
                                </div>

                                <div class="step-item d-flex mb-3">
                                    <div class="step-num me-3 bg-info text-white rounded-circle d-flex align-items-center justify-content-center fw-bold" style="width: 32px; height: 32px; min-width: 32px;">3</div>
                                    <div>
                                        <div class="fw-bold">Dán Token & Lưu Cấu Hình:</div>
                                        <div class="small text-muted">Dán token vào ô <b>Token BIDV</b> bên trái và bấm <b>Lưu Cấu Hình Ngân Hàng</b>. Hệ thống sẽ lưu vào Supabase và bắt đầu tự động quét giao dịch 24/7!</div>
                                    </div>
                                </div>

                                <div class="alert alert-success mt-4 small">
                                    <div class="fw-bold mb-1"><i class="fa-solid fa-qrcode me-1"></i> Cơ chế tạo mã VietQR tự động:</div>
                                    Khi khách nạp qua bot, bot tự sinh mã VietQR chuẩn Napas quốc gia có sẵn STK <b>8880117869</b>, số tiền chính xác và cú pháp <code>NAP &lt;telegram_id&gt;</code>. Khách chỉ cần mở app ngân hàng quét là tự điền đúng mọi thông tin!
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: FACEBOOK CLONE SETTINGS & AUTO CHECK LIVE -->
            <div class="tab-pane fade" id="tab-facebook">
                <div class="row g-4">
                    <!-- Cột 1: Cấu hình Bật/Tắt Check Live & Xóa DIE -->
                    <div class="col-lg-6">
                        <div class="card border-primary h-100 shadow-sm">
                            <div class="card-header bg-primary bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-brands fa-facebook text-primary me-2"></i>Cấu Hình Tự Động Check Live & Xóa Nick DIE</h5>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-circle-check me-1"></i> Tự động kiểm tra trực tiếp qua <b>Facebook Graph API</b> (tốc độ cao, không cần cookie, không sợ bị khóa).
                                </div>

                                <form id="facebookForm" onsubmit="event.preventDefault(); saveFacebookSettings();">
                                    <h6 class="fw-bold text-primary border-bottom pb-1 mb-3">1. Khi Nạp / Đăng Hàng Vào Kho:</h6>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border border-warning">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_filter_duplicate_uids" {fb_filter_dups_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="fb_filter_duplicate_uids">
                                            <i class="fa-solid fa-clone text-warning me-1"></i> Tự động LỌC & CHẶN TRÙNG UID Facebook khi nạp
                                        </label>
                                        <div class="small text-muted ms-4">Nếu UID đã có trong kho hàng (hoặc lặp lại trong danh sách nạp), hệ thống sẽ tự động loại bỏ để <b>không bao giờ bán trùng nick</b> cho khách.</div>
                                    </div>
                                    
                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_check_on_upload" {fb_check_up_attr}>
                                        <label class="form-check-label fw-bold" for="fb_auto_check_on_upload">Tự động check LIVE UID khi nạp hàng</label>
                                        <div class="small text-muted ms-4">Khi nạp clone qua Web, API, Bot hoặc File TXT, hệ thống sẽ tự động quét trạng thái từng UID.</div>
                                    </div>

                                    <div class="form-check form-switch mb-4 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_delete_die_on_upload" {fb_del_up_attr}>
                                        <label class="form-check-label fw-bold text-danger" for="fb_auto_delete_die_on_upload">Tự động XÓA / LOẠI BỎ tài khoản DIE khi nạp</label>
                                        <div class="small text-muted ms-4">Nếu bật, các nick DIE sẽ bị lọc bỏ ngay lập tức, chỉ những nick <b>LIVE 100%</b> mới được đưa vào kho.</div>
                                    </div>

                                    <h6 class="fw-bold text-success border-bottom pb-1 mb-3">2. Khi Khách Mua Hàng (Giao Cho Khách):</h6>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_check_live_before_delivery" {fb_check_deliv_attr}>
                                        <label class="form-check-label fw-bold" for="fb_check_live_before_delivery">Check LIVE UID trước khi giao hàng cho khách</label>
                                        <div class="small text-muted ms-4">Khi khách thanh toán, Bot sẽ quét lại ngay tại thời điểm giao để đảm bảo khách không bao giờ nhận phải acc DIE.</div>
                                    </div>

                                    <div class="form-check form-switch mb-4 p-2 bg-light rounded">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_auto_delete_die_on_delivery" {fb_del_deliv_attr}>
                                        <label class="form-check-label fw-bold text-danger" for="fb_auto_delete_die_on_delivery">Tự động xóa nick DIE và lấy nick LIVE khác bù vào</label>
                                        <div class="small text-muted ms-4">Nếu acc trong kho bị die sau thời gian lưu trữ, bot sẽ xóa nick die đó và tự động bốc nick LIVE khác giao cho khách.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Từ khóa nhận diện danh mục Facebook (phân cách bằng dấu phẩy):</label>
                                        <input type="text" class="form-control font-monospace small" id="fb_category_keywords" value="{fb_keywords}" placeholder="facebook, fb, clone, via, bm">
                                        <div class="form-text small">Các danh mục chứa từ khóa này sẽ tự động được áp dụng cơ chế lọc Facebook clone.</div>
                                    </div>

                                    <h6 class="fw-bold text-info border-bottom pb-1 mb-3 mt-4"><i class="fa-solid fa-clock-rotate-left me-1"></i> 3. Cron Tự Động Quét Kho Theo Chu Kỳ (Sau mỗi XX phút):</h6>

                                    <div class="mb-3 p-2 bg-light rounded border">
                                        <label class="form-label fw-bold small text-dark mb-1">Chu kỳ tự động check LIVE kho (phút):</label>
                                        <div class="input-group" style="max-width: 250px;">
                                            <input type="number" class="form-control fw-bold" id="fb_cron_check_interval_minutes" value="{fb_cron_interval}" min="0" max="1440">
                                            <span class="input-group-text">phút</span>
                                        </div>
                                        <div class="form-text small">Đặt <b>30</b> = Quét 30 phút/lần. Đặt <b>60</b> = Quét 1 tiếng/lần. Đặt <b>0</b> = Tắt cron tự động.</div>
                                    </div>

                                    <div class="form-check form-switch mb-3 p-2 bg-light rounded border">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="fb_cron_notify_admin" {fb_cron_notify_attr}>
                                        <label class="form-check-label fw-bold" for="fb_cron_notify_admin">Gửi thông báo báo cáo về Telegram Admin khi quét</label>
                                    </div>

                                    <div class="mb-3 p-3 bg-light rounded border">
                                        <label class="form-label fw-bold small text-dark mb-1"><i class="fa-solid fa-link me-1"></i> Link Webhook Cron Cho Dịch Vụ Ngoài (Cron-job.org / Vercel / UptimeRobot):</label>
                                        <div class="input-group">
                                            <input type="text" class="form-control font-monospace small" id="cronWebhookUrl" value="{cron_webhook_url}" readonly>
                                            <button class="btn btn-outline-primary" type="button" onclick="navigator.clipboard.writeText(document.getElementById('cronWebhookUrl').value); alert('Đã sao chép link Cron!')">
                                                <i class="fa-solid fa-copy me-1"></i> Sao chép
                                            </button>
                                        </div>
                                        <div class="form-text small">Dán URL này vào <b>Cron-job.org</b> hoặc <b>EasyCron</b> để kích hoạt quét kho từ bên ngoài theo đúng số phút bạn muốn!</div>
                                    </div>

                                    <div id="fbSaveResult" class="mb-3" style="display:none;"></div>

                                    <div class="pt-2 border-top">
                                        <button type="submit" class="btn btn-primary fw-bold px-4">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Facebook Ngay
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <!-- Cột 2: Công cụ kiểm tra UID & Quản trị kho trực tiếp -->
                    <div class="col-lg-6">
                        <!-- Widget 1: Kiểm tra nhanh 1 UID -->
                        <div class="card shadow-sm mb-4">
                            <div class="card-header py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-magnifying-glass text-info me-2"></i>Kiểm Tra Nhanh 1 Tài Khoản Facebook</h5>
                            </div>
                            <div class="card-body">
                                <div class="mb-3">
                                    <label class="form-label small text-muted fw-bold">Nhập UID hoặc chuỗi Clone (UID|Pass|2FA...):</label>
                                    <div class="input-group">
                                        <input type="text" class="form-control font-monospace" id="quickUidInput" placeholder="VD: 100088912345678|Password|2FA...">
                                        <button class="btn btn-info text-white fw-bold" type="button" onclick="checkSingleUid()">
                                            <i class="fa-solid fa-circle-play me-1"></i> Kiểm Tra
                                        </button>
                                    </div>
                                </div>
                                <div id="quickUidResult" style="display:none;" class="p-3 bg-light rounded border"></div>
                            </div>
                        </div>

                        <!-- Widget 2: Quét & Dọn Dẹp Kho Hàng Facebook -->
                        <div class="card border-danger shadow-sm">
                            <div class="card-header bg-danger bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-broom text-danger me-2"></i>Quét & Xóa Sạch Nick DIE Trong Kho</h5>
                            </div>
                            <div class="card-body">
                                <p class="small text-muted">Quét toàn bộ tài khoản clone Facebook đang tồn trong database để kiểm tra trạng thái sống/chết và dọn sạch nick DIE để đảm bảo uy tín shop.</p>
                                
                                <div class="d-flex flex-wrap gap-2 mb-3">
                                    <button class="btn btn-outline-primary fw-bold" type="button" onclick="scanFbStock()">
                                        <i class="fa-solid fa-magnifying-glass-chart me-1"></i> Quét Toàn Kho (Xem Trạng Thái)
                                    </button>
                                    <button class="btn btn-warning fw-bold text-dark" type="button" onclick="cleanFbDuplicateStock()">
                                        <i class="fa-solid fa-clone me-1"></i> Quét & XÓA Nick Trùng UID
                                    </button>
                                    <button class="btn btn-danger fw-bold" type="button" onclick="cleanFbDieStock()">
                                        <i class="fa-solid fa-trash-can me-1"></i> Quét & XÓA Nick DIE
                                    </button>
                                </div>

                                <div id="stockScanResult" style="display:none;" class="p-3 bg-light rounded border"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 5: KHUYẾN MÃI NẠP TIỀN (DEPOSIT BONUS) -->
            <div class="tab-pane fade" id="tab-bonus">
                <div class="row g-4">
                    <div class="col-lg-7">
                        <div class="card border-danger h-100 shadow-sm">
                            <div class="card-header bg-danger bg-opacity-10 py-3 d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-dark">
                                    <i class="fa-solid fa-gift text-danger me-2"></i>Cấu Hình Khuyến Mãi Nạp Tiền (Deposit Bonus)
                                </h5>
                                {bonus_badge}
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-circle-info me-1"></i>
                                    <b>Cơ chế hoạt động:</b><br>
                                    • Khi <b>TẮT</b>: Bot sẽ hoàn toàn ẩn thông tin thưởng nạp, chỉ hiển thị form nhập số tiền nạp bình thường và không cộng thêm tiền thưởng.<br>
                                    • Khi <b>BẬT</b>: Bot sẽ hiển thị danh sách thưởng nạp theo các mốc cấu hình bên dưới. Khi khách nạp tiền (qua Binance Pay, BIDV Bank hoặc On-chain), hệ thống sẽ <b>tự động tính % và cộng thêm tiền thưởng vào tài khoản khách</b>, đồng thời báo rõ trong thông báo Ting Ting.
                                </div>

                                <form id="bonusForm" onsubmit="event.preventDefault(); saveBonusSettings();">
                                    <div class="form-check form-switch mb-3 p-3 bg-light rounded border border-danger">
                                        <input class="form-check-input ms-0 me-2" type="checkbox" role="switch" id="deposit_bonus_enabled" {deposit_bonus_enabled_attr}>
                                        <label class="form-check-label fw-bold text-dark" for="deposit_bonus_enabled">
                                            <i class="fa-solid fa-power-off text-danger me-1"></i> Bật / Tắt Chương Trình Thưởng Nạp
                                        </label>
                                        <div class="small text-muted ms-4">Bật công tắc này nếu bạn muốn chạy chương trình khuyến mãi nạp tiền cho khách hàng.</div>
                                    </div>

                                    <div class="mb-3">
                                        <label class="form-label fw-bold small text-muted">Các Mốc Thưởng Nạp (Mức USDT : % Thưởng):</label>
                                        <input type="text" class="form-control font-monospace fw-bold" id="deposit_bonus_tiers" value="{deposit_bonus_tiers}" placeholder="100:2,200:5,300:6,500:7,1000:8">
                                        <div class="form-text small">
                                            Định dạng: <code>SốTiền:PhầnTrăm</code> phân cách bởi dấu phẩy <code>,</code> hoặc xuống dòng.<br>
                                            <i>Ví dụ: <code>100:2, 200:5, 300:6, 500:7, 1000:8</code> có nghĩa là:<br>
                                            • Nạp từ 100 USDT trở lên: thưởng +2%<br>
                                            • Nạp từ 200 USDT trở lên: thưởng +5%<br>
                                            • Nạp từ 300 USDT trở lên: thưởng +6%<br>
                                            • Nạp từ 500 USDT trở lên: thưởng +7%<br>
                                            • Nạp từ 1.000 USDT trở lên: thưởng +8%</i>
                                        </div>
                                    </div>

                                    <div class="d-grid mt-4">
                                        <button type="submit" class="btn btn-danger py-2 fw-bold">
                                            <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Cấu Hình Khuyến Mãi
                                        </button>
                                    </div>
                                    <div id="bonusSaveResult" class="mt-3" style="display:none;"></div>
                                </form>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-5">
                        <div class="card border-info shadow-sm mb-4">
                            <div class="card-header bg-info bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-eye me-2 text-info"></i>Xem Trước Hiển Thị Trên Bot</h5>
                            </div>
                            <div class="card-body">
                                <p class="small text-muted mb-2">Giao diện khách nhìn thấy trên Telegram khi bấm Nạp tiền:</p>
                                <div class="p-3 rounded bg-dark text-light font-monospace small" style="white-space: pre-wrap;">{preview_bonus_html}</div>
                            </div>
                        </div>

                        <div class="card border-warning shadow-sm">
                            <div class="card-header bg-warning bg-opacity-10 py-3">
                                <h5 class="card-title mb-0 fw-bold text-dark"><i class="fa-solid fa-lightbulb me-2 text-warning"></i>Gợi Ý Cấu Hình</h5>
                            </div>
                            <div class="card-body small text-muted">
                                <p class="mb-2"><b>Mẫu 1 (Khuyến mãi nhẹ):</b><br>
                                <code>50:1, 100:2, 500:5</code></p>
                                <p class="mb-2"><b>Mẫu 2 (Kích thích nạp số lượng lớn):</b><br>
                                <code>100:2, 200:5, 300:6, 500:7, 1000:8</code></p>
                                <p class="mb-0"><b>Mẫu 3 (Thưởng nạp lễ/tết):</b><br>
                                <code>10:5, 50:10, 100:15</code></p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 6: CHÍNH SÁCH BẢO HÀNH & PHÁP LÝ -->
            <div class="{policy_pane_cls}" id="tab-policy" role="tabpanel">
        <ul class="nav nav-pills mb-4" id="policyTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-easy-btn" data-bs-toggle="pill" data-bs-target="#tab-easy" type="button" role="tab">
                    <i class="fa-solid fa-wand-magic-sparkles me-2"></i>1. Nhập Nhanh Theo Mục (Dễ dùng nhất)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-full-btn" data-bs-toggle="pill" data-bs-target="#tab-full" type="button" role="tab">
                    <i class="fa-solid fa-file-contract me-2"></i>2. Soạn Thảo Toàn Văn (Gõ /policy)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-summary-btn" data-bs-toggle="pill" data-bs-target="#tab-summary" type="button" role="tab">
                    <i class="fa-solid fa-list-check me-2"></i>3. Bản Tóm Tắt Nhanh (Gõ /support & Sau khi Mua)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-preview-btn" data-bs-toggle="pill" data-bs-target="#tab-preview" type="button" role="tab">
                    <i class="fa-brands fa-telegram text-info me-2"></i>4. Mô Phỏng Telegram (Live Preview)
                </button>
            </li>
        </ul>

        <div class="tab-content" id="policyTabsContent">
            <!-- TAB 1: NHAP NHANH THEO MUC (CUC KY DE DUNG) -->
            <div class="tab-pane fade show active" id="tab-easy" role="tabpanel">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0 fw-bold">
                            <i class="fa-solid fa-sliders text-warning me-2"></i>Cài Đặt Điều Khoản Theo Từng Mặt Hàng (Ai Cũng Chỉnh Sửa Được)
                        </h5>
                        <span class="badge bg-primary">Không cần gõ thẻ HTML</span>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-info py-2 small mb-4">
                            <i class="fa-solid fa-circle-info me-1"></i> <b>Hướng dẫn:</b> Bạn chỉ cần thay đổi số giờ hoặc ghi chú ngắn gọn bên dưới. Bấm nút <b>"✨ Tự Động Ghép & Lưu Vào Supabase"</b> ở cuối trang, hệ thống sẽ tự động ghép thành văn bản pháp lý chuyên nghiệp và gửi lên Bot Telegram!
                        </div>

                        <div class="row g-4">
                            <!-- 1. Facebook -->
                            <div class="col-md-6">
                                <div class="p-3 rounded border border-primary-subtle shadow-sm bg-light bg-opacity-25 h-100">
                                    <h6 class="fw-bold text-primary mb-3">
                                        <i class="fa-brands fa-facebook me-2"></i>1. Tài Khoản Facebook (Clone, Via, BM)
                                    </h6>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary fw-bold">Thời gian bảo hành (1 đổi 1):</label>
                                        <div class="input-group">
                                            <input type="text" class="form-control form-control fw-bold" id="form_fb_hours" value="24 giờ">
                                            <span class="input-group-text bg-secondary text-dark border">tính từ lúc mua</span>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary fw-bold">Điều kiện được bảo hành:</label>
                                        <textarea class="form-control form-control small" id="form_fb_warranty" rows="2">Sai mật khẩu ban đầu, sai mã 2FA, checkpoint/die TRƯỚC thời điểm mua (Hệ thống có Auto-check Live UID trước khi giao hàng).</textarea>
                                    </div>
                                    <div class="mb-0">
                                        <label class="form-label small text-secondary fw-bold">Từ chối bảo hành khi:</label>
                                        <textarea class="form-control form-control small" id="form_fb_refuse" rows="2">Đã login thành công; checkpoint do IP bẩn / proxy bẩn / thiết bị spam; spam vi phạm chính sách Meta; tự ý đổi mail/pass làm checkpoint; quá hạn bảo hành.</textarea>
                                    </div>
                                </div>
                            </div>

                            <!-- 2. AI -->
                            <div class="col-md-6">
                                <div class="p-3 rounded border border-info-subtle shadow-sm bg-light bg-opacity-25 h-100">
                                    <h6 class="fw-bold text-info mb-3">
                                        <i class="fa-solid fa-robot me-2"></i>2. Tài Khoản AI (ChatGPT Plus/Team, Claude Pro, Midjourney)
                                    </h6>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary fw-bold">Chính sách bảo hành gói Pro/Plus:</label>
                                        <textarea class="form-control form-control small" id="form_ai_warranty" rows="2">1 đổi 1 hoặc hoàn tiền/gia hạn lại gói nếu mất quyền lợi Pro/Plus trong suốt thời hạn cam kết.</textarea>
                                    </div>
                                    <div class="mb-0">
                                        <label class="form-label small text-secondary fw-bold">Từ chối bảo hành khi:</label>
                                        <textarea class="form-control form-control small" id="form_ai_refuse" rows="3">Dùng chung tài khoản cho nhiều người (share public), spam prompt vi phạm ToS của OpenAI/Anthropic dẫn đến tài khoản bị cấm.</textarea>
                                    </div>
                                </div>
                            </div>

                            <!-- 3. CapCut Pro -->
                            <div class="col-md-6">
                                <div class="p-3 rounded border border-warning-subtle shadow-sm bg-light bg-opacity-25 h-100">
                                    <h6 class="fw-bold text-warning mb-3">
                                        <i class="fa-solid fa-video me-2"></i>3. Tài Khoản CapCut Pro
                                    </h6>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary fw-bold">Chính sách bảo hành:</label>
                                        <textarea class="form-control form-control small" id="form_capcut_warranty" rows="2">Bảo hành toàn bộ thời hạn gói mua (1 tháng, 6 tháng, 1 năm). 1 đổi 1 nếu văng Pro hoặc lỗi kỹ thuật từ hệ thống.</textarea>
                                    </div>
                                    <div class="mb-0">
                                        <label class="form-label small text-secondary fw-bold">Quy định số lượng thiết bị:</label>
                                        <input type="text" class="form-control form-control small" id="form_capcut_devices" value="Tối đa 1-2 thiết bị theo quy định, nghiêm cấm share bên thứ ba">
                                    </div>
                                </div>
                            </div>

                            <!-- 4. VPN -->
                            <div class="col-md-6">
                                <div class="p-3 rounded border border-success-subtle shadow-sm bg-light bg-opacity-25 h-100">
                                    <h6 class="fw-bold text-success mb-3">
                                        <i class="fa-solid fa-shield-halved me-2"></i>4. Tài Khoản VPN (NordVPN, ExpressVPN, Surfshark...)
                                    </h6>
                                    <div class="mb-3">
                                        <label class="form-label small text-secondary fw-bold">Chính sách bảo hành:</label>
                                        <textarea class="form-control form-control small" id="form_vpn_warranty" rows="2">1 đổi 1 suốt thời hạn gói nếu tài khoản mất quyền truy cập hoặc bị thu hồi bản quyền.</textarea>
                                    </div>
                                    <div class="mb-0">
                                        <label class="form-label small text-secondary fw-bold">Nghiêm cấm hành vi:</label>
                                        <input type="text" class="form-control form-control small" id="form_vpn_refuse" value="Cấm dùng VPN để tấn công mạng, DDoS, hack, torrent vi phạm bản quyền">
                                    </div>
                                </div>
                            </div>

                            <!-- 5. Phap ly & Admin -->
                            <div class="col-12">
                                <div class="p-3 rounded border border-danger-subtle shadow-sm bg-light bg-opacity-25">
                                    <h6 class="fw-bold text-danger mb-3">
                                        <i class="fa-solid fa-scale-balanced me-2"></i>5. Căn Cứ Pháp Lý Việt Nam & Kênh Hỗ Trợ
                                    </h6>
                                    <div class="row g-3">
                                        <div class="col-md-6">
                                            <label class="form-label small text-secondary fw-bold">Tuyên bố miễn trừ trách nhiệm (Luật An ninh mạng):</label>
                                            <textarea class="form-control form-control small" id="form_disclaimer" rows="2">Bên mua chịu 100% trách nhiệm trước pháp luật Việt Nam. Shop là đơn vị trung gian kỹ thuật số và hoàn toàn miễn trừ mọi trách nhiệm pháp lý liên đới.</textarea>
                                        </div>
                                        <div class="col-md-6">
                                            <label class="form-label small text-secondary fw-bold">Telegram Admin hỗ trợ:</label>
                                            <div class="input-group mb-2">
                                                <span class="input-group-text bg-secondary text-dark border"><i class="fa-brands fa-telegram"></i></span>
                                                <input type="text" class="form-control form-control fw-bold text-info" id="form_admin_handle" value="@truongdvfb">
                                            </div>
                                            <small class="text-secondary">Thời gian xử lý bảo hành: <b>15 - 30 phút</b></small>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div id="saveResultEasy" class="mt-4" style="display: none;"></div>

                        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 pt-3 border-top border">
                            <button type="button" class="btn btn-outline-warning" onclick="resetEasyFormToDefaults()">
                                <i class="fa-solid fa-rotate-left me-1"></i> Điền Lại Giá Trị Mặc Định
                            </button>
                            <button type="button" class="btn btn-success btn-lg px-4 fw-bold shadow" onclick="generateAndSaveFromEasyForm()">
                                <i class="fa-solid fa-wand-magic-sparkles me-2"></i>✨ Tự Động Ghép & Lưu Vào Supabase
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            <!-- TAB 2: SOAN THAO TOAN VAN -->
            <div class="tab-pane fade" id="tab-full" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-8">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold">
                                    <i class="fa-solid fa-pen-to-square text-info me-2"></i>Soạn Thảo Toàn Văn Chính Sách
                                </h5>
                                <div class="small text-secondary" id="charCountFull">
                                    Độ dài: <span class="fw-bold text-info" id="charNum">0</span> ký tự | <span class="fw-bold text-success" id="wordNum">0</span> từ
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="mb-3 d-flex flex-wrap gap-2 align-items-center">
                                    <span class="small text-secondary me-1"><i class="fa-solid fa-wand-magic-sparkles me-1"></i>Chèn nhanh:</span>
                                    <button type="button" class="btn btn-sm btn-outline-info" onclick="insertClause('fb')">
                                        <i class="fa-brands fa-facebook me-1"></i> + Mục Facebook
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="insertClause('ai')">
                                        <i class="fa-solid fa-robot me-1"></i> + Mục AI (ChatGPT)
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-warning" onclick="insertClause('capcut')">
                                        <i class="fa-solid fa-video me-1"></i> + Mục CapCut
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-success" onclick="insertClause('vpn')">
                                        <i class="fa-solid fa-shield-halved me-1"></i> + Mục VPN
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="insertClause('disclaimer')">
                                        <i class="fa-solid fa-scale-balanced me-1"></i> + Miễn Trừ Pháp Lý
                                    </button>
                                </div>

                                <textarea class="form-control editor-textarea w-100" id="policyContentInput" rows="18">{policy_escaped}</textarea>

                                <div id="saveResultFull" class="mt-3" style="display: none;"></div>

                                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 pt-3 border-top border">
                                    <div class="d-flex gap-2">
                                        <button type="button" class="btn btn-outline-warning" onclick="resetToDefaultPolicy()">
                                            <i class="fa-solid fa-rotate-left me-1"></i> Khôi Phục Mẫu Chuẩn
                                        </button>
                                        <button type="button" class="btn btn-outline-info" onclick="switchToPreview()">
                                            <i class="fa-solid fa-eye me-1"></i> Xem Trên Telegram
                                        </button>
                                    </div>
                                    <button type="button" class="btn btn-primary px-4 fw-bold" onclick="savePolicyFull()">
                                        <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Toàn Văn Vào Supabase
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-4">
                        <div class="card h-100">
                            <div class="card-header">
                                <h6 class="card-title mb-0 fw-bold">
                                    <i class="fa-solid fa-book-bookmark text-warning me-2"></i>Cẩm Nang Điều Khoản Pháp Lý
                                </h6>
                            </div>
                            <div class="card-body small text-secondary">
                                <div class="mb-3">
                                    <h6 class="text-info fw-bold mb-1"><i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> Tại sao cần Điều khoản?</h6>
                                    <p class="mb-0">Việt Nam có <b>Luật An ninh mạng 2018</b> và <b>Nghị định 15/2020/NĐ-CP</b>. Khi bạn bán clone FB hoặc account số, nếu không ghi rõ tuyên bố miễn trừ và mục đích sử dụng hợp pháp, shop có thể bị quy kết liên đới nếu người mua dùng account đi lừa đảo, chống phá hoặc vi phạm pháp luật.</p>
                                </div>
                                <hr class="border">
                                <div class="mb-3">
                                    <h6 class="text-success fw-bold mb-1"><i class="fa-solid fa-shield-heart me-1"></i> Thẻ HTML hỗ trợ bởi Telegram:</h6>
                                    <ul class="ps-3 mb-0">
                                        <li><code>&lt;b&gt;in đậm&lt;/b&gt;</code></li>
                                        <li><code>&lt;i&gt;in nghiêng&lt;/i&gt;</code></li>
                                        <li><code>&lt;u&gt;gạch chân&lt;/u&gt;</code></li>
                                        <li><code>&lt;s&gt;gạch ngang&lt;/s&gt;</code></li>
                                        <li><code>&lt;code&gt;mã lệnh / copy nhanh&lt;/code&gt;</code></li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: BAN TOM TAT NHANH -->
            <div class="tab-pane fade" id="tab-summary" role="tabpanel">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0 fw-bold">
                            <i class="fa-solid fa-list-check text-success me-2"></i>Bản Tóm Tắt Nhanh (Gõ /support & Gửi Kèm Khi Mua Hàng)
                        </h5>
                        <div class="small text-secondary" id="charCountSum">
                            Độ dài: <span class="fw-bold text-info" id="charNumSum">0</span> ký tự
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="alert alert-secondary py-2 small mb-3">
                            <i class="fa-solid fa-circle-info me-1"></i> Bản tóm tắt này sẽ tự động hiển thị khi khách bấm lệnh <b>/support</b> hoặc được đính kèm vào hóa đơn ngay sau khi khách mua hàng thành công.
                        </div>

                        <textarea class="form-control editor-textarea w-100" id="summaryContentInput" rows="12">{summary_escaped}</textarea>

                        <div id="saveResultSummary" class="mt-3" style="display: none;"></div>

                        <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 pt-3 border-top border">
                            <button type="button" class="btn btn-outline-warning" onclick="resetToDefaultSummary()">
                                <i class="fa-solid fa-rotate-left me-1"></i> Khôi Phục Mẫu Tóm Tắt Mặc Định
                            </button>
                            <button type="button" class="btn btn-success px-4 fw-bold" onclick="saveSummary()">
                                <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Bản Tóm Tắt Vào Supabase
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 4: MO PHONG TELEGRAM -->
            <div class="tab-pane fade" id="tab-preview" role="tabpanel">
                <div class="row justify-content-center">
                    <div class="col-lg-6">
                        <div class="card">
                            <div class="card-header text-center">
                                <h6 class="card-title mb-0 fw-bold">
                                    <i class="fa-brands fa-telegram text-info me-2"></i>Mô Phỏng Trực Tiếp Giao Diện Telegram Của Khách Hàng
                                </h6>
                            </div>
                            <div class="card-body p-3">
                                <div class="tg-mockup">
                                    <div class="tg-header">
                                        <div class="tg-avatar">🤖</div>
                                        <div>
                                            <div class="fw-bold text-dark" style="font-size: 15px;">Shop Clone FB & TK Số</div>
                                            <div class="text-secondary" style="font-size: 12px;">bot • @shopcl_bot</div>
                                        </div>
                                    </div>
                                    <div class="tg-body">
                                        <div class="tg-bubble" id="tgBubbleContent">
                                            <!-- Preview rendered live -->
                                        </div>
                                        <div class="tg-button mt-3">
                                            <i class="fa-solid fa-arrow-left me-1"></i> Quay lại Menu Chính
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function togglePass(id, btn) {{
            const input = document.getElementById(id);
            if (!input) return;
            const icon = btn ? btn.querySelector('i') : null;
            if (input.type === 'password') {{
                input.type = 'text';
                if (icon) icon.className = 'fa-solid fa-eye-slash';
            }} else {{
                input.type = 'password';
                if (icon) icon.className = 'fa-solid fa-eye';
            }}
        }}

        function togglePasswordVisibility(id, btn) {{
            togglePass(id, btn);
        }}

        function showToast(msg, type) {{
            let container = document.getElementById('toastContainer');
            if (!container) {{
                container = document.createElement('div');
                container.id = 'toastContainer';
                container.style = 'position: fixed; top: 20px; right: 20px; z-index: 99999;';
                document.body.appendChild(container);
            }}
            const id = 'toast_' + Date.now();
            const bgClass = type === 'success' ? 'bg-success' : (type === 'danger' ? 'bg-danger' : (type === 'warning' ? 'bg-warning text-dark' : 'bg-info text-dark'));
            const toastHtml = `
                <div id="${{id}}" class="toast align-items-center text-white ${{bgClass}} border-0 show shadow mb-2" role="alert" style="min-width: 280px;">
                    <div class="d-flex">
                        <div class="toast-body fw-bold">${{msg}}</div>
                        <button type="button" class="btn-close btn-close-white me-2 m-auto" onclick="document.getElementById('${{id}}').remove()"></button>
                    </div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', toastHtml);
            setTimeout(() => {{
                const el = document.getElementById(id);
                if (el) el.remove();
            }}, 4000);
        }}

        async function saveSettingsPayload(payload, resultDivId) {{
            const resDiv = document.getElementById(resultDivId);
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang lưu cài đặt vào Database Supabase...</span>';

            try {{
                const res = await fetch("{api_settings_save}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }},
                    body: JSON.stringify({{ settings: payload }})
                }});
                const data = await res.json();
                if (res.ok) {{
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>Lưu thành công!</b> ' + (data.message || 'Cấu hình đã được lưu vĩnh viễn vào Supabase và kích hoạt ngay lập tức.') + '</div>';
                    setTimeout(() => {{ location.reload(); }}, 1500);
                }} else {{
                    const errDetail = data.detail || data.message || ('Không thể lưu cài đặt (Mã lỗi: ' + res.status + ')');
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi: ' + errDetail + '</div>';
                }}
            }} catch (err) {{
                resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi kết nối: ' + err.message + '</div>';
            }}
        }}

        function saveFacebookSettings() {{
            const payload = {{
                'FB_FILTER_DUPLICATE_UIDS': document.getElementById('fb_filter_duplicate_uids').checked ? 'true' : 'false',
                'FB_AUTO_CHECK_ON_UPLOAD': document.getElementById('fb_auto_check_on_upload').checked ? 'true' : 'false',
                'FB_AUTO_DELETE_DIE_ON_UPLOAD': document.getElementById('fb_auto_delete_die_on_upload').checked ? 'true' : 'false',
                'FB_CHECK_LIVE_BEFORE_DELIVERY': document.getElementById('fb_check_live_before_delivery').checked ? 'true' : 'false',
                'FB_AUTO_DELETE_DIE_ON_DELIVERY': document.getElementById('fb_auto_delete_die_on_delivery').checked ? 'true' : 'false',
                'FB_CATEGORY_KEYWORDS': document.getElementById('fb_category_keywords').value.trim(),
                'FB_CRON_CHECK_INTERVAL_MINUTES': document.getElementById('fb_cron_check_interval_minutes').value.trim() || '30',
                'FB_CRON_NOTIFY_ADMIN': document.getElementById('fb_cron_notify_admin').checked ? 'true' : 'false'
            }};
            saveSettingsPayload(payload, 'fbSaveResult');
        }}

        async function checkSingleUid() {{
            const val = document.getElementById('quickUidInput').value.trim();
            const resDiv = document.getElementById('quickUidResult');
            if (!val) {{ alert('Vui lòng nhập UID!'); return; }}
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kiểm tra Facebook Graph API...</span>';

            try {{
                const res = await fetch("{api_fb_check_uid}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }},
                    body: JSON.stringify({{ data: val }})
                }});
                const data = await res.json();
                if (data.results && data.results.length > 0) {{
                    const r = data.results[0];
                    if (r.status === 'LIVE') {{
                        resDiv.innerHTML = '<div class="text-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> UID ' + r.uid + ' -> LIVE (Hoạt động tốt)</div>';
                    }} else {{
                        resDiv.innerHTML = '<div class="text-danger fw-bold"><i class="fa-solid fa-circle-xmark me-1"></i> UID ' + r.uid + ' -> DIE (Bị khóa / Checkpoint)</div>';
                    }}
                }} else {{
                    resDiv.innerHTML = '<div class="text-warning">Không tìm thấy UID hợp lệ trong chuỗi.</div>';
                }}
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

        async function scanFbStock() {{
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét toàn bộ kho clone...</span>';
            try {{
                const res = await fetch("{api_fb_scan_stock}", {{
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                resDiv.innerHTML = '<div class="alert alert-info py-2 mb-0"><b>Kết quả:</b> Quét ' + data.total_scanned + ' clone | Live: <span class="text-success fw-bold">' + data.live_count + '</span> | Die: <span class="text-danger fw-bold">' + data.die_count + '</span></div>';
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

                async function cleanFbDuplicateStock() {{
            if (!confirm('Bạn có chắc chắn muốn quét và XÓA các nick bị TRÙNG UID trong kho hàng không? (Hệ thống sẽ giữ lại 1 nick duy nhất)')) return;
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-warning"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét và lọc nick trùng UID trong kho...</span>';
            try {{
                const res = await fetch("{api_fb_clean_dups}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                if (res.ok) {{
                    const delCount = data.deleted_duplicates || 0;
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><b>Hoàn tất:</b> Đã quét ' + data.total_scanned + ' clone. Độc nhất: ' + data.unique_uids + ' UID | Đã xóa: <span class="text-danger fw-bold">' + delCount + '</span> nick bị trùng UID khỏi kho!</div>';
                }} else {{
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0">Lỗi: ' + (data.detail || JSON.stringify(data)) + '</div>';
                }}
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

        async function cleanFbDieStock() {{
            if (!confirm('Bạn có chắc chắn muốn quét và XÓA TOÀN BỘ clone DIE khỏi kho không?')) return;
            const resDiv = document.getElementById('stockScanResult');
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-danger"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang quét và xóa nick DIE khỏi kho...</span>';
            try {{
                const res = await fetch("{api_fb_clean_die}", {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><b>Hoàn tất:</b> Đã quét ' + data.total_scanned + ' clone. Live: ' + data.live_count + ' | Đã xóa: <span class="text-danger fw-bold">' + data.deleted_count + '</span> nick DIE khỏi kho!</div>';
            }} catch(e) {{
                resDiv.innerHTML = '<div class="text-danger">Lỗi: ' + e.message + '</div>';
            }}
        }}

function onMinVndChange(val) {{
            const vnd = parseFloat(val) || 0;
            const rateEl = document.getElementById('bank_exchange_rate');
            const rate = rateEl ? (parseFloat(rateEl.value) || 26000) : 26000;
            const usdt = rate > 0 ? (vnd / rate).toFixed(2) : '1.0';
            const el1 = document.getElementById('binance_min_deposit');
            const el2 = document.getElementById('krypto_min_deposit');
            const el3 = document.getElementById('bank_min_deposit');
            const vndEl = document.getElementById('bank_min_vnd_preview');
            if (el3) el3.value = usdt;
            if (el1) el1.value = usdt;
            if (el2) el2.value = usdt;
            if (vndEl) vndEl.innerText = Math.round(vnd).toLocaleString();
        }}

        function onMinUsdtChange(val) {{
            syncMinDepositInputs(val);
        }}

        function saveBankSettings() {{
            const minUsdtEl = document.getElementById('bank_min_deposit');
            const minVndEl = document.getElementById('bank_min_deposit_vnd');
            const rateEl = document.getElementById('bank_exchange_rate');
            const rateVal = rateEl ? (parseFloat(rateEl.value) || 26000) : 26000;

            let minVndVal = minVndEl ? (parseFloat(minVndEl.value) || 0) : 0;
            let minUsdtVal = minUsdtEl ? (parseFloat(minUsdtEl.value) || 0) : 0;

            if (minVndVal <= 0 && minUsdtVal > 0) {{
                minVndVal = Math.round(minUsdtVal * rateVal);
            }} else if (minUsdtVal <= 0 && minVndVal > 0) {{
                minUsdtVal = parseFloat((minVndVal / rateVal).toFixed(2));
            }}

            const payload = {{
                'BANK_BIDV_TOKEN': document.getElementById('bank_token').value.trim(),
                'BANK_ACCOUNT_NUMBER': document.getElementById('bank_account_number').value.trim(),
                'BANK_ACCOUNT_NAME': document.getElementById('bank_account_name').value.trim(),
                'BANK_CODE': document.getElementById('bank_code').value.trim(),
                'BANK_EXCHANGE_RATE': rateVal,
                'BANK_AUTO_CHECK': document.getElementById('bank_auto_check').checked,
                'MIN_DEPOSIT_USDT': minUsdtVal,
                'MIN_DEPOSIT_VND': minVndVal
            }};
            saveSettingsPayload(payload, 'bankSaveResult');
        }}

        async function checkBankTransactionsNow() {{
            const resBox = document.getElementById('bankSaveResult');
            if (resBox) {{
                resBox.style.display = 'block';
                resBox.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kết nối ThueApi.pro để quét giao dịch ngân hàng BIDV...</span>';
            }}
            showToast('Đang kết nối ThueApi.pro quét giao dịch...', 'info');

            try {{
                const res = await fetch('/api/bank/check-now', {{
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-KEY': '{api_key}',
                        'Authorization': 'Bearer {admin_token}'
                    }}
                }});
                const data = await res.json();
                if (res.ok && data.status === 'success') {{
                    if (data.credited_count > 0) {{
                        const msg = 'Thành công! Đã phát hiện và cộng tiền cho ' + data.credited_count + ' giao dịch mới!';
                        if (resBox) resBox.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>' + msg + '</b></div>';
                        showToast(msg, 'success');
                    }} else {{
                        const msg = 'Kết nối ThueApi.pro thành công! Hiện chưa có giao dịch chuyển khoản mới.';
                        if (resBox) resBox.innerHTML = '<div class="alert alert-info py-2 mb-0"><i class="fa-solid fa-check me-1"></i> ' + msg + '</div>';
                        showToast(msg, 'info');
                    }}
                }} else {{
                    const errMsg = data.detail || data.message || 'Không thể quét giao dịch';
                    if (resBox) resBox.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-triangle-exclamation me-1"></i> <b>Lỗi:</b> ' + errMsg + '</div>';
                    showToast('Lỗi: ' + errMsg, 'danger');
                }}
            }} catch (err) {{
                if (resBox) resBox.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-triangle-exclamation me-1"></i> <b>Lỗi kết nối:</b> ' + err.message + '</div>';
                showToast('Lỗi mạng: ' + err.message, 'danger');
            }}
        }}

        function syncMinDepositInputs(val) {{
            const el1 = document.getElementById('binance_min_deposit');
            const el2 = document.getElementById('krypto_min_deposit');
            const el3 = document.getElementById('bank_min_deposit');
            const elVnd = document.getElementById('bank_min_deposit_vnd');
            if (el1 && el1.value !== val) el1.value = val;
            if (el2 && el2.value !== val) el2.value = val;
            if (el3 && el3.value !== val) el3.value = val;
            const rateEl = document.getElementById('bank_exchange_rate');
            const vndEl = document.getElementById('bank_min_vnd_preview');
            const rate = rateEl ? (parseFloat(rateEl.value) || 26000) : 26000;
            const num = parseFloat(val) || 1;
            if (vndEl) {{
                vndEl.innerText = Math.round(num * rate).toLocaleString();
            }}
            if (elVnd && elVnd.value !== Math.round(num * rate).toString()) {{
                elVnd.value = Math.round(num * rate);
            }}
        }}

        function saveBinanceSettings() {{
            const minEl = document.getElementById('binance_min_deposit');
            const minVal = minEl ? (parseFloat(minEl.value) || 1.0) : 1.0;
            const payload = {{
                'BINANCE_UID': document.getElementById('binance_uid').value.trim(),
                'BINANCE_API_KEY': document.getElementById('binance_api_key').value.trim(),
                'BINANCE_API_SECRET': document.getElementById('binance_api_secret').value.trim(),
                'MIN_DEPOSIT_USDT': minVal
            }};
            saveSettingsPayload(payload, 'binanceSaveResult');
        }}

        function saveKryptoSettings() {{
            const minEl = document.getElementById('krypto_min_deposit');
            const minVal = minEl ? (parseFloat(minEl.value) || 1.0) : 1.0;
            const payload = {{
                'KRYPTO_EXPRESS_API_KEY': document.getElementById('krypto_api_key').value.trim(),
                'KRYPTO_EXPRESS_API_SECRET': document.getElementById('krypto_api_secret').value.trim(),
                'KRYPTO_EXPRESS_API_URL': document.getElementById('krypto_api_url').value.trim(),
                'MIN_DEPOSIT_USDT': minVal
            }};
            saveSettingsPayload(payload, 'kryptoSaveResult');
        }}

        function saveBonusSettings() {{
            const payload = {{
                'DEPOSIT_BONUS_ENABLED': document.getElementById('deposit_bonus_enabled').checked ? 'true' : 'false',
                'DEPOSIT_BONUS_TIERS': document.getElementById('deposit_bonus_tiers').value.trim()
            }};
            saveSettingsPayload(payload, 'bonusSaveResult');
        }}

        function saveForwardingSettings() {{
            const payload = {{
                'CRYPTO_FORWARDING_MODE': document.getElementById('crypto_forwarding_mode').checked ? 'true' : 'false',
                'ONLY_USDT_MODE': document.getElementById('only_usdt_mode').checked ? 'true' : 'false',
                'BNB_FORWARDING_ADDRESS': document.getElementById('bnb_forwarding_address').value.trim(),
                'SOL_FORWARDING_ADDRESS': document.getElementById('sol_forwarding_address').value.trim(),
                'ETH_FORWARDING_ADDRESS': document.getElementById('eth_forwarding_address').value.trim(),
                'BTC_FORWARDING_ADDRESS': document.getElementById('btc_forwarding_address').value.trim(),
                'LTC_FORWARDING_ADDRESS': document.getElementById('ltc_forwarding_address').value.trim(),
                'DOGE_FORWARDING_ADDRESS': document.getElementById('doge_forwarding_address').value.trim()
            }};
            saveSettingsPayload(payload, 'fwdSaveResult');
        }}

        async function syncBinancePay() {{
            const resBox = document.getElementById("syncResult");
            resBox.style.display = "block";
            resBox.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang kết nối Binance API...</span>';

            try {{
                const res = await fetch("{api_binance_check}", {{
                    method: "POST",
                    credentials: 'same-origin',
                    headers: {{
                        'X-API-KEY': "{api_key}",
                        'Authorization': "Bearer {admin_token}"
                    }}
                }});
                const data = await res.json();
                if (res.ok) {{
                    if (data.credited_count > 0) {{
                        resBox.innerHTML = '<span class="text-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> Đã tìm thấy và cộng tiền cho ' + data.credited_count + ' giao dịch!</span>';
                    }} else {{
                        resBox.innerHTML = '<span class="text-muted"><i class="fa-solid fa-check me-1"></i> Quét hoàn tất: Không có giao dịch mới cần xử lý.</span>';
                    }}
                }} else {{
                    resBox.innerHTML = '<span class="text-danger"><i class="fa-solid fa-triangle-exclamation me-1"></i> ' + (data.detail || "Chưa cấu hình API Key trên Render") + '</span>';
                }}
            }} catch (err) {{
                resBox.innerHTML = '<span class="text-danger">Lỗi kết nối: ' + err.message + '</span>';
            }}
        }}
            const defaultPolicy = JSON.parse(document.getElementById('data-default-policy').textContent);
        const defaultSummary = JSON.parse(document.getElementById('data-default-summary').textContent);
        const initialPolicy = JSON.parse(document.getElementById('data-initial-policy').textContent);
        const initialSummary = JSON.parse(document.getElementById('data-initial-summary').textContent);

        const policyTextarea = document.getElementById('policyContentInput');
        const summaryTextarea = document.getElementById('summaryContentInput');

        if (!policyTextarea.value.trim()) {{
            policyTextarea.value = initialPolicy || defaultPolicy;
        }}
        if (!summaryTextarea.value.trim()) {{
            summaryTextarea.value = initialSummary || defaultSummary;
        }}

        function updateCounts() {{
            const val = policyTextarea.value || '';
            const charEl = document.getElementById('charNum');
            const wordEl = document.getElementById('wordNum');
            if (charEl) charEl.innerText = val.length.toLocaleString();
            if (wordEl) {{
                const words = val.trim() ? val.trim().split(/\\s+/).length : 0;
                wordEl.innerText = words.toLocaleString();
            }}

            const sumVal = summaryTextarea.value || '';
            const charSumEl = document.getElementById('charNumSum');
            if (charSumEl) charSumEl.innerText = sumVal.length.toLocaleString();

            updateTelegramPreview();
        }}

        function updateTelegramPreview() {{
            const raw = policyTextarea.value || defaultPolicy;
            const bubble = document.getElementById('tgBubbleContent');
            if (bubble) bubble.innerHTML = raw;
        }}

        policyTextarea.addEventListener('input', updateCounts);
        summaryTextarea.addEventListener('input', updateCounts);
        updateCounts();

        function switchToPreview() {{
            const triggerEl = document.getElementById('tab-preview-btn');
            if (triggerEl) {{
                const tab = bootstrap.Tab.getInstance(triggerEl) || new bootstrap.Tab(triggerEl);
                tab.show();
            }}
        }}

        function insertClause(type) {{
            let snippet = '';
            if (type === 'fb') {{
                snippet = '\\n• <b>Tài khoản Facebook:</b> 1 đổi 1 trong 24h nếu sai pass, sai 2FA, die trước khi mua (Auto-check live UID). Từ chối nếu đã login thành công, IP bẩn hoặc vi phạm ToS Meta.\\n';
            }} else if (type === 'ai') {{
                snippet = '\\n• <b>Tài khoản AI (ChatGPT/Claude/Midjourney):</b> Bảo hành tụt gói Pro trong suốt thời hạn cam kết. Không bảo hành nếu share account công khai hoặc vi phạm ToS OpenAI.\\n';
            }} else if (type === 'capcut') {{
                snippet = '\\n• <b>Tài khoản CapCut Pro:</b> Bảo hành đúng thời hạn gói đã mua (1 đổi 1 nếu văng Pro). Từ chối nếu đăng nhập quá 2 thiết bị.\\n';
            }} else if (type === 'vpn') {{
                snippet = '\\n• <b>Tài khoản VPN:</b> Bảo hành kết nối và bản quyền suốt gói. Từ chối nếu dùng VPN để hack, DDoS, tấn công mạng.\\n';
            }} else if (type === 'disclaimer') {{
                snippet = '\\n⚖️ <b>TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM:</b> Bên mua chịu 100% trách nhiệm trước pháp luật Việt Nam (Luật An ninh mạng & NĐ 15/2020/NĐ-CP). Shop là đơn vị trung gian kỹ thuật và hoàn toàn miễn trừ mọi trách nhiệm liên đới.\\n';
            }}
            const curPos = policyTextarea.selectionStart || 0;
            const text = policyTextarea.value;
            policyTextarea.value = text.slice(0, curPos) + snippet + text.slice(curPos);
            updateCounts();
            policyTextarea.focus();
        }}

        function resetToDefaultPolicy() {{
            if (confirm('Khôi phục toàn văn chính sách về mẫu chuẩn mặc định?')) {{
                policyTextarea.value = defaultPolicy;
                updateCounts();
            }}
        }}

        function resetToDefaultSummary() {{
            if (confirm('Khôi phục bản tóm tắt về mẫu mặc định?')) {{
                summaryTextarea.value = defaultSummary;
                updateCounts();
            }}
        }}

        function resetEasyFormToDefaults() {{
            document.getElementById('form_fb_hours').value = '24 giờ';
            document.getElementById('form_fb_warranty').value = 'Sai mật khẩu ban đầu, sai mã 2FA, checkpoint/die TRƯỚC thời điểm mua (Hệ thống có Auto-check Live UID trước khi giao hàng).';
            document.getElementById('form_fb_refuse').value = 'Đã login thành công; checkpoint do IP bẩn / proxy bẩn / thiết bị spam; spam vi phạm chính sách Meta; tự ý đổi mail/pass làm checkpoint; quá hạn bảo hành.';
            document.getElementById('form_ai_warranty').value = '1 đổi 1 hoặc hoàn tiền/gia hạn lại gói nếu mất quyền lợi Pro/Plus trong suốt thời hạn cam kết.';
            document.getElementById('form_ai_refuse').value = 'Dùng chung tài khoản cho nhiều người (share public), spam prompt vi phạm ToS của OpenAI/Anthropic dẫn đến tài khoản bị cấm.';
            document.getElementById('form_capcut_warranty').value = 'Bảo hành toàn bộ thời hạn gói mua (1 tháng, 6 tháng, 1 năm). 1 đổi 1 nếu văng Pro hoặc lỗi kỹ thuật từ hệ thống.';
            document.getElementById('form_capcut_devices').value = 'Tối đa 1-2 thiết bị theo quy định, nghiêm cấm share bên thứ ba';
            document.getElementById('form_vpn_warranty').value = '1 đổi 1 suốt thời hạn gói nếu tài khoản mất quyền truy cập hoặc bị thu hồi bản quyền.';
            document.getElementById('form_vpn_refuse').value = 'Cấm dùng VPN để tấn công mạng, DDoS, hack, torrent vi phạm bản quyền';
            document.getElementById('form_disclaimer').value = 'Bên mua chịu 100% trách nhiệm trước pháp luật Việt Nam. Shop là đơn vị trung gian kỹ thuật số và hoàn toàn miễn trừ mọi trách nhiệm pháp lý liên đới.';
            document.getElementById('form_admin_handle').value = '@truongdvfb';
            alert('Đã đưa các ô về giá trị chuẩn mặc định!');
        }}

        function generateAndSaveFromEasyForm() {{
            const fbH = document.getElementById('form_fb_hours').value.trim();
            const fbW = document.getElementById('form_fb_warranty').value.trim();
            const fbR = document.getElementById('form_fb_refuse').value.trim();
            const aiW = document.getElementById('form_ai_warranty').value.trim();
            const aiR = document.getElementById('form_ai_refuse').value.trim();
            const ccW = document.getElementById('form_capcut_warranty').value.trim();
            const ccD = document.getElementById('form_capcut_devices').value.trim();
            const vpnW = document.getElementById('form_vpn_warranty').value.trim();
            const vpnR = document.getElementById('form_vpn_refuse').value.trim();
            const discl = document.getElementById('form_disclaimer').value.trim();
            const adm = document.getElementById('form_admin_handle').value.trim() || '@truongdvfb';

            const assembledFull = [
                '🛡️ <b>CHÍNH SÁCH BẢO HÀNH & TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM PHÁP LÝ</b>',
                '<i>(Căn cứ Luật An ninh mạng số 24/2018/QH14 & Nghị định 15/2020/NĐ-CP)</i>',
                '━━━━━━━━━━━━━━━━━━━━━━━━━',
                '',
                '<b>I. MỤC ĐÍCH CUNG CẤP & SỬ DỤNG HỢP PHÁP</b>',
                '1. Mọi tài khoản số do hệ thống cung cấp (Facebook Clone/Via/BM, AI: ChatGPT/Claude, CapCut Pro, VPN...) được cung cấp <b>ĐỘC QUYỀN</b> cho học tập, nghiên cứu công nghệ, QA testing, marketing sạch tuân thủ pháp luật Việt Nam.',
                '2. Khách hàng cam kết tuân thủ nghiêm ngặt mọi quy định pháp luật nước CHXHCN Việt Nam và ToS nền tảng gốc.',
                '',
                '<b>II. CÁC HÀNH VI BỊ NGHIÊM CẤM TUYỆT ĐỐI (PHÁP LUẬT VN)</b>',
                '❌ Chống phá Nhà nước, kích động gây rối an ninh trật tự.',
                '❌ Lừa đảo chiếm đoạt tài sản, giả mạo danh tính, rửa tiền.',
                '❌ Phát tán tin giả, văn hóa phẩm đồi trụy, xuyên tạc vu khống.',
                '❌ Cờ bạc, cá độ, giao dịch tài chính phi pháp.',
                '❌ Tấn công mạng DDoS, phát tán mã độc, virus.',
                '',
                '<b>III. TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM</b>',
                '⚖️ <b>Trách nhiệm độc lập:</b> BÊN MUA CHỊU HOÀN TOÀN TRÁCH NHIỆM 100% TRƯỚC PHÁP LUẬT VIỆT NAM về mọi hoạt động sử dụng tài khoản.',
                '⚖️ <b>Miễn trừ:</b> ' + discl,
                '',
                '<b>IV. CHÍNH SÁCH BẢO HÀNH THEO SẢN PHẨM</b>',
                '<b>1. Tài khoản Facebook (Clone, Via, BM):</b>',
                '• <b>Bảo hành 1 đổi 1 trong ' + fbH + ':</b> ' + fbW,
                '• <b>Từ chối bảo hành:</b> ' + fbR,
                '',
                '<b>2. Tài khoản AI (ChatGPT Plus/Team, Claude Pro, Midjourney...):</b>',
                '• <b>Bảo hành:</b> ' + aiW,
                '• <b>Từ chối:</b> ' + aiR,
                '',
                '<b>3. Tài khoản CapCut Pro:</b>',
                '• <b>Bảo hành:</b> ' + ccW,
                '• <b>Quy định thiết bị:</b> ' + ccD,
                '',
                '<b>4. Tài khoản VPN (NordVPN, ExpressVPN...):</b>',
                '• <b>Bảo hành:</b> ' + vpnW,
                '• <b>Từ chối:</b> ' + vpnR,
                '',
                '<b>V. QUY TRÌNH TIẾP NHẬN BẢO HÀNH</b>',
                '1. Chụp ảnh/video rõ ràng chứng minh lỗi.',
                '2. Gửi kèm <b>Mã đơn hàng (Order ID)</b> và định dạng tài khoản lỗi.',
                '3. Nhắn tin Admin Telegram: <b>' + adm + '</b> (Xử lý trong 15 - 30 phút).',
                '━━━━━━━━━━━━━━━━━━━━━━━━━',
                '<i>⚠️ Mua hàng đồng nghĩa với việc bạn đồng ý với toàn bộ điều khoản trên.</i>'
            ].join('\\n');

            const assembledSummary = [
                '🛡️ <b>CHÍNH SÁCH BẢO HÀNH & MIỄN TRỪ TRÁCH NHIỆM</b>',
                '━━━━━━━━━━━━━━━━━━━━━━━━━',
                '⚖️ <b>Tuân thủ Pháp luật VN:</b> Tài khoản chỉ phục vụ học tập, nghiên cứu & marketing hợp pháp (Luật An ninh mạng 2018). Người mua tự chịu 100% trách nhiệm trước pháp luật, Shop miễn trừ mọi trách nhiệm liên đới.',
                '',
                '🛡️ <b>Bảo hành 1 đổi 1 (' + fbH + '):</b>',
                '• <b>Facebook:</b> Lỗi sai pass, sai 2FA, die trước khi mua (Auto-check live). Không bảo hành nếu đã login hoặc IP bẩn.',
                '• <b>AI, CapCut & VPN:</b> ' + aiW,
                '',
                '👤 <b>Admin hỗ trợ:</b> ' + adm + ' (Kèm mã Order ID)',
                '📜 Gõ /policy để đọc toàn văn chính sách.'
            ].join('\\n');

            policyTextarea.value = assembledFull;
            summaryTextarea.value = assembledSummary;
            updateCounts();

            savePolicyPayload({{
                'WARRANTY_LEGAL_POLICY': assembledFull,
                'WARRANTY_SHORT_SUMMARY': assembledSummary
            }}, 'saveResultEasy');
        }}

        async function savePolicyPayload(payload, resultDivId) {{
            return saveSettingsPayload(payload, resultDivId);
        }}

        function savePolicyFull() {{
            const val = policyTextarea.value.trim();
            if (!val) {{
                alert('Vui lòng không để trống nội dung chính sách!');
                return;
            }}
            savePolicyPayload({{ 'WARRANTY_LEGAL_POLICY': val }}, 'saveResultFull');
        }}

        function saveSummary() {{
            const val = summaryTextarea.value.trim();
            if (!val) {{
                alert('Vui lòng không để trống nội dung tóm tắt!');
                return;
            }}
            savePolicyPayload({{ 'WARRANTY_SHORT_SUMMARY': val }}, 'saveResultSummary');
        }}

        // Live update & URL hash sync for all 6 tabs
        document.addEventListener('DOMContentLoaded', function() {{
            if (typeof updateCounts === 'function') updateCounts();
            const hash = window.location.hash;
            if (hash) {{
                const triggerEl = document.querySelector('#pills-tab button[data-bs-target="' + hash + '"]');
                if (triggerEl) {{
                    bootstrap.Tab.getOrCreateInstance(triggerEl).show();
                }}
            }}
            const tabButtons = document.querySelectorAll('#pills-tab button[data-bs-toggle="pill"]');
            tabButtons.forEach(btn => {{
                btn.addEventListener('shown.bs.tab', function(e) {{
                    const target = e.target.getAttribute('data-bs-target');
                    if (target) {{
                        history.replaceState(null, null, target);
                    }}
                }});
            }});
        }});

    </script>
</body>
</html>"""
        return HTMLResponse(content=html_content)


class PaymentApiConfigView(BaseView):
    name = "Cài đặt & Clone FB"
    icon = "fa-solid fa-sliders"

    def is_accessible(self, request: Request) -> bool:
        try:
            token = request.session.get("token")
            return bool(token and decode_token(token))
        except Exception:
            return False

    def is_visible(self, request: Request) -> bool:
        try:
            token = request.session.get("token")
            return bool(token and decode_token(token))
        except Exception:
            return False

    @expose("/settings", methods=["GET"])
    async def settings_page(self, request: Request):
        try:
            tab = request.query_params.get("tab", "binance")
        except Exception:
            tab = "binance"
        return await render_unified_settings_page(request, default_active_tab=tab or "binance")

    @expose("/policy", methods=["GET"])
    async def policy_page(self, request: Request):
        return await render_unified_settings_page(request, default_active_tab="policy")
