from sqladmin import BaseView, expose
from fastapi import Request
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token
import config


class WarrantyPolicyAdminView(BaseView):
    name = "🛡️ Chính sách & Bảo hành"
    icon = "fa-solid fa-shield-halved"

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

    @expose("/policy", methods=["GET"])
    async def policy_page(self, request: Request):
        try:
            token = request.session.get("token")
        except Exception:
            token = None

        if not token or not decode_token(token):
            return RedirectResponse(url="/admin/login", status_code=302)

        from db import get_db_session
        from services.settings import SettingsService
        from services.policy_defaults import DEFAULT_WARRANTY_LEGAL_POLICY, DEFAULT_WARRANTY_SHORT_SUMMARY

        async with get_db_session() as session:
            cur_settings = await SettingsService.get_all_settings(session)

        current_policy = cur_settings.get("WARRANTY_LEGAL_POLICY") or DEFAULT_WARRANTY_LEGAL_POLICY
        current_summary = cur_settings.get("WARRANTY_SHORT_SUMMARY") or DEFAULT_WARRANTY_SHORT_SUMMARY

        api_key = config.SQLADMIN_RAW_PASSWORD or "MatKhauAdminCuaBan123"
        admin_token = token or ""
        api_settings_save = "/api/settings/save"

        html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛡️ Quản Lý Chính Sách Bảo Hành & Điều Khoản Pháp Lý - Bubba Gump</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{
            background-color: #0f172a;
            color: #f1f5f9;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            min-height: 100vh;
        }}
        .card {{
            border-radius: 14px;
            border: 1px solid #334155;
            background-color: #1e293b;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            margin-bottom: 24px;
        }}
        .card-header {{
            background-color: #1e293b;
            border-bottom: 1px solid #334155;
            padding: 16px 20px;
        }}
        .nav-pills .nav-link {{
            color: #94a3b8;
            font-weight: 600;
            border-radius: 10px;
            padding: 10px 20px;
            margin-right: 10px;
            border: 1px solid transparent;
            transition: all 0.2s ease-in-out;
        }}
        .nav-pills .nav-link:hover {{
            color: #e2e8f0;
            background-color: #334155;
        }}
        .nav-pills .nav-link.active {{
            background-color: #0284c7;
            color: #ffffff;
            border-color: #38bdf8;
            box-shadow: 0 4px 14px rgba(2, 132, 199, 0.4);
        }}
        .editor-textarea {{
            background-color: #090d16;
            color: #38bdf8;
            font-family: "Fira Code", Consolas, "Courier New", monospace;
            font-size: 13.5px;
            line-height: 1.6;
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 16px;
            resize: vertical;
        }}
        .editor-textarea:focus {{
            background-color: #090d16;
            color: #7dd3fc;
            border-color: #38bdf8;
            box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25);
        }}
        .badge-law {{
            background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%);
            color: #fff;
            font-size: 0.82rem;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 600;
        }}
        .badge-sync {{
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #fff;
            font-size: 0.82rem;
            padding: 6px 12px;
            border-radius: 8px;
            font-weight: 600;
        }}
        /* Telegram Phone Mockup */
        .tg-mockup {{
            max-width: 480px;
            margin: 0 auto;
            background: #17212b;
            border-radius: 24px;
            border: 8px solid #0e1621;
            box-shadow: 0 20px 40px rgba(0,0,0,0.6);
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
            transition: background 0.15s;
        }}
        .tg-button:hover {{
            background: #346392;
        }}
    </style>
</head>
<body class="p-3 p-md-4">
    <div class="container-fluid" style="max-width: 1440px;">
        <!-- Header -->
        <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
            <div>
                <h3 class="fw-bold mb-1 text-white">
                    <i class="fa-solid fa-shield-halved text-info me-2"></i>Chính Sách Bảo Hành & Điều Khoản Pháp Lý
                </h3>
                <p class="text-secondary mb-0">
                    Bảo vệ pháp lý cho Shop theo <b>Luật An ninh mạng 2018</b> & <b>Nghị định 15/2020/NĐ-CP</b> khi bán Clone FB, AI, CapCut Pro, VPN...
                </p>
            </div>
            <div class="mt-2 mt-md-0 d-flex gap-2">
                <a href="/admin" class="btn btn-outline-light">
                    <i class="fa-solid fa-arrow-left me-1"></i> Quay lại Dashboard
                </a>
            </div>
        </div>

        <!-- Banner Huong Dan & Luat Phap -->
        <div class="alert bg-dark text-light border-secondary p-3 mb-4 rounded-3 shadow-sm">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge-law"><i class="fa-solid fa-scale-balanced me-1"></i> LUẬT AN NINH MẠNG VN</span>
                    <span class="badge-sync"><i class="fa-solid fa-bolt me-1"></i> TỰ ĐỘNG ĐỒNG BỘ TELEGRAM</span>
                </div>
                <div class="small text-info">
                    <i class="fa-solid fa-circle-check me-1"></i> Miễn trừ 100% trách nhiệm liên đới trước pháp luật khi người mua vi phạm
                </div>
            </div>
            <hr class="my-2 border-secondary">
            <div class="row g-2 small text-light mt-1">
                <div class="col-md-3">
                    <i class="fa-solid fa-check text-success me-1"></i> <b>Facebook Clone/Via:</b> 24h 1 đổi 1 (Check Live UID tự động).
                </div>
                <div class="col-md-3">
                    <i class="fa-solid fa-check text-success me-1"></i> <b>Tài khoản AI (ChatGPT/Claude):</b> Bảo hành hết thời hạn gói cam kết.
                </div>
                <div class="col-md-3">
                    <i class="fa-solid fa-check text-success me-1"></i> <b>CapCut Pro:</b> 1 đổi 1 nếu văng Pro (giới hạn 1-2 thiết bị).
                </div>
                <div class="col-md-3">
                    <i class="fa-solid fa-check text-success me-1"></i> <b>VPN:</b> Bảo hành bản quyền kết nối, cấm DDoS/hack.
                </div>
            </div>
        </div>

        <!-- Nav tabs -->
        <ul class="nav nav-pills mb-4" id="policyTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="tab-full-btn" data-bs-toggle="pill" data-bs-target="#tab-full" type="button" role="tab">
                    <i class="fa-solid fa-file-contract me-2"></i>1. Toàn Văn Chính Sách & Điều Khoản (Gõ /policy)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-summary-btn" data-bs-toggle="pill" data-bs-target="#tab-summary" type="button" role="tab">
                    <i class="fa-solid fa-list-check me-2"></i>2. Bản Tóm Tắt Nhanh (Gõ /support & Sau khi Mua)
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="tab-preview-btn" data-bs-toggle="pill" data-bs-target="#tab-preview" type="button" role="tab">
                    <i class="fa-brands fa-telegram text-info me-2"></i>3. Mô Phỏng Hiển Thị Telegram (Live Preview)
                </button>
            </li>
        </ul>

        <!-- Tab Content -->
        <div class="tab-content" id="policyTabsContent">
            <!-- TAB 1: TOAN VAN CHINH SACH -->
            <div class="tab-pane fade show active" id="tab-full" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-8">
                        <div class="card h-100">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-white">
                                    <i class="fa-solid fa-pen-to-square text-info me-2"></i>Soạn Thảo Toàn Văn Chính Sách
                                </h5>
                                <div class="small text-secondary" id="charCountFull">
                                    Độ dài: <span class="fw-bold text-info" id="charNum">0</span> ký tự | <span class="fw-bold text-success" id="wordNum">0</span> từ
                                </div>
                            </div>
                            <div class="card-body">
                                <!-- Quick Snippet Toolbar -->
                                <div class="mb-3 d-flex flex-wrap gap-2 align-items-center">
                                    <span class="small text-secondary me-1"><i class="fa-solid fa-wand-magic-sparkles me-1"></i>Chèn mẫu nhanh:</span>
                                    <button type="button" class="btn btn-sm btn-outline-info" onclick="insertClause('fb')">
                                        <i class="fa-brands fa-facebook me-1"></i> + Mẫu Facebook
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="insertClause('ai')">
                                        <i class="fa-solid fa-robot me-1"></i> + Mẫu AI (ChatGPT)
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-warning" onclick="insertClause('capcut')">
                                        <i class="fa-solid fa-video me-1"></i> + Mẫu CapCut Pro
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-success" onclick="insertClause('vpn')">
                                        <i class="fa-solid fa-shield-halved me-1"></i> + Mẫu VPN
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="insertClause('disclaimer')">
                                        <i class="fa-solid fa-scale-balanced me-1"></i> + Mẫu Miễn Trừ Pháp Lý
                                    </button>
                                </div>

                                <textarea class="form-control editor-textarea w-100" id="policyContentInput" rows="18" placeholder="Nhập toàn văn chính sách bảo hành..."></textarea>

                                <div id="saveResultFull" class="mt-3" style="display: none;"></div>

                                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 pt-3 border-top border-secondary">
                                    <div class="d-flex gap-2">
                                        <button type="button" class="btn btn-outline-warning" onclick="resetToDefaultPolicy()">
                                            <i class="fa-solid fa-rotate-left me-1"></i> Khôi Phục Mẫu Chuẩn Pháp Luật
                                        </button>
                                        <button type="button" class="btn btn-outline-info" onclick="switchToPreview()">
                                            <i class="fa-solid fa-eye me-1"></i> Xem Trước Trên Telegram
                                        </button>
                                    </div>
                                    <button type="button" class="btn btn-primary px-4 fw-bold shadow" onclick="savePolicyFull()">
                                        <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Toàn Văn Vào Supabase
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right Column: Huong dan & Dieu khoan mau -->
                    <div class="col-lg-4">
                        <div class="card h-100">
                            <div class="card-header">
                                <h5 class="card-title mb-0 fw-bold text-white">
                                    <i class="fa-solid fa-gavel text-warning me-2"></i>Quy Chuẩn Pháp Lý Việt Nam
                                </h5>
                            </div>
                            <div class="card-body small text-secondary">
                                <div class="mb-3">
                                    <h6 class="text-info fw-bold mb-1"><i class="fa-solid fa-circle-info me-1"></i> 1. Mục Đích Hợp Pháp</h6>
                                    <p class="mb-0">Quy định mọi tài khoản chỉ bán cho mục đích nghiên cứu, học tập, QA testing, marketing sạch tuân thủ pháp luật Việt Nam.</p>
                                </div>
                                <div class="mb-3">
                                    <h6 class="text-danger fw-bold mb-1"><i class="fa-solid fa-ban me-1"></i> 2. Các Hành Vi Bị Cấm</h6>
                                    <p class="mb-0">Cấm triệt để: Chống phá Nhà nước, lừa đảo, chiếm đoạt tài sản, tin giả, văn hóa phẩm đồi trụy, cờ bạc, tấn công mạng DDoS.</p>
                                </div>
                                <div class="mb-3">
                                    <h6 class="text-warning fw-bold mb-1"><i class="fa-solid fa-shield-cat me-1"></i> 3. Miễn Trừ Trách Nhiệm</h6>
                                    <p class="mb-0">Bên mua chịu 100% trách nhiệm trước pháp luật. Shop là đơn vị trung gian kỹ thuật số, miễn trừ mọi trách nhiệm pháp lý liên đới.</p>
                                </div>
                                <div class="mb-3">
                                    <h6 class="text-success fw-bold mb-1"><i class="fa-solid fa-clock-rotate-left me-1"></i> 4. Thời Gian Bảo Hành</h6>
                                    <p class="mb-0">Facebook Clone: 1 đổi 1 trong 24 giờ cho lỗi đăng nhập đầu (Hệ thống có auto-check UID live trước khi giao).</p>
                                </div>
                                <div class="p-3 bg-dark rounded border border-secondary mt-3">
                                    <span class="text-white fw-bold d-block mb-1"><i class="fa-solid fa-headset text-info me-1"></i> Thông tin hỗ trợ:</span>
                                    <span>Telegram Admin: <b class="text-info">@truongdvfb</b></span><br>
                                    <span>Thời gian phản hồi: <b>15 - 30 phút</b></span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 2: TOM TAT NHANH -->
            <div class="tab-pane fade" id="tab-summary" role="tabpanel">
                <div class="row g-4">
                    <div class="col-lg-8">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="card-title mb-0 fw-bold text-white">
                                    <i class="fa-solid fa-bolt text-warning me-2"></i>Soạn Thảo Bản Tóm Tắt Nhanh
                                </h5>
                                <div class="small text-secondary" id="charCountSummary">
                                    Độ dài: <span class="fw-bold text-warning" id="charNumSum">0</span> ký tự
                                </div>
                            </div>
                            <div class="card-body">
                                <div class="alert alert-info py-2 small mb-3">
                                    <i class="fa-solid fa-lightbulb me-1"></i> <b>Nội dung tóm tắt này hiển thị ở đâu?</b><br>
                                    • Khi khách hàng bấm <code>💬 Hỗ trợ & Bảo hành</code> trên menu Telegram.<br>
                                    • Gửi kèm ở cuối tin nhắn xác nhận đơn hàng thành công sau khi khách mua tài khoản.
                                </div>

                                <textarea class="form-control editor-textarea w-100" id="summaryContentInput" rows="12" placeholder="Nhập bản tóm tắt nhanh..."></textarea>

                                <div id="saveResultSummary" class="mt-3" style="display: none;"></div>

                                <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 pt-3 border-top border-secondary">
                                    <button type="button" class="btn btn-outline-warning" onclick="resetToDefaultSummary()">
                                        <i class="fa-solid fa-rotate-left me-1"></i> Khôi Phục Tóm Tắt Mặc Định
                                    </button>
                                    <button type="button" class="btn btn-warning text-dark px-4 fw-bold shadow" onclick="saveSummary()">
                                        <i class="fa-solid fa-floppy-disk me-1"></i> Lưu Bản Tóm Tắt Vào Supabase
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-lg-4">
                        <div class="card">
                            <div class="card-header">
                                <h5 class="card-title mb-0 fw-bold text-white">
                                    <i class="fa-solid fa-circle-question text-info me-2"></i>Gợi Ý Nội Dung Tóm Tắt
                                </h5>
                            </div>
                            <div class="card-body small text-secondary">
                                <p>Bản tóm tắt nên ngắn gọn (khoảng 500 - 800 ký tự) để khách dễ đọc lướt qua trên điện thoại:</p>
                                <ul class="ps-3 mb-0">
                                    <li class="mb-2">Khẳng định tuân thủ Luật An ninh mạng Việt Nam.</li>
                                    <li class="mb-2">Bảo hành 1 đổi 1 trong 24h đối với lỗi đăng nhập đầu.</li>
                                    <li class="mb-2">Từ chối bảo hành nếu đã đổi pass thành công hoặc dính IP bẩn.</li>
                                    <li class="mb-2">Khách hàng chịu 100% trách nhiệm trước pháp luật.</li>
                                    <li>Liên hệ Admin @truongdvfb kèm Order ID.</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- TAB 3: TELEGRAM PREVIEW -->
            <div class="tab-pane fade" id="tab-preview" role="tabpanel">
                <div class="row">
                    <div class="col-12 text-center mb-3">
                        <p class="text-secondary small">
                            <i class="fa-solid fa-mobile-screen me-1"></i> Giao diện mô phỏng chuẩn kích thước màn hình ứng dụng Telegram trên smartphone:
                        </p>
                    </div>
                    <div class="col-12">
                        <div class="tg-mockup">
                            <div class="tg-header">
                                <div class="tg-avatar">🍤</div>
                                <div>
                                    <div class="text-white fw-bold d-flex align-items-center">
                                        Bubba Gump Shop Bot <i class="fa-solid fa-circle-check text-info ms-1 small"></i>
                                    </div>
                                    <div class="text-secondary small" style="font-size: 11px;">bot • online</div>
                                </div>
                            </div>
                            <div class="tg-body" id="tgPreviewBody">
                                <div class="tg-bubble" id="tgBubbleContent">
                                    <!-- Rendered dynamically -->
                                </div>
                                <div class="mt-2">
                                    <div class="tg-button" onclick="alert('Demo: Mở link Admin Telegram: @truongdvfb')">
                                        💬 Nhắn tin Admin (@truongdvfb)
                                    </div>
                                    <div class="tg-button" onclick="alert('Demo: Xem Điều khoản & Bảo hành')">
                                        🛡️ Xem Điều khoản & Bảo hành
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
        const defaultPolicy = {json.dumps(DEFAULT_WARRANTY_LEGAL_POLICY)};
        const defaultSummary = {json.dumps(DEFAULT_WARRANTY_SHORT_SUMMARY)};
        const initialPolicy = {json.dumps(current_policy)};
        const initialSummary = {json.dumps(current_summary)};

        const policyTextarea = document.getElementById('policyContentInput');
        const summaryTextarea = document.getElementById('summaryContentInput');

        policyTextarea.value = initialPolicy;
        summaryTextarea.value = initialSummary;

        function updateCounts() {{
            const val = policyTextarea.value;
            document.getElementById('charNum').innerText = val.length.toLocaleString();
            const words = val.trim() ? val.trim().split(/\s+/).length : 0;
            document.getElementById('wordNum').innerText = words.toLocaleString();

            const sumVal = summaryTextarea.value;
            document.getElementById('charNumSum').innerText = sumVal.length.toLocaleString();

            updateTelegramPreview();
        }}

        function updateTelegramPreview() {{
            const raw = policyTextarea.value || defaultPolicy;
            // Clean/render simple HTML
            document.getElementById('tgBubbleContent').innerHTML = raw;
        }}

        policyTextarea.addEventListener('input', updateCounts);
        summaryTextarea.addEventListener('input', updateCounts);
        updateCounts();

        function switchToPreview() {{
            const triggerEl = document.getElementById('tab-preview-btn');
            bootstrap.Tab.getInstance(triggerEl) ? bootstrap.Tab.getInstance(triggerEl).show() : new bootstrap.Tab(triggerEl).show();
        }}

        function insertClause(type) {{
            let snippet = "";
            if (type === 'fb') {{
                snippet = "\n• <b>Tài khoản Facebook:</b> 1 đổi 1 trong 24h nếu sai pass, sai 2FA, die trước khi mua (Auto-check live UID). Từ chối nếu đã login thành công, IP bẩn hoặc vi phạm ToS Meta.\n";
            }} else if (type === 'ai') {{
                snippet = "\n• <b>Tài khoản AI (ChatGPT/Claude/Midjourney):</b> Bảo hành tụt gói Pro trong suốt thời hạn cam kết. Không bảo hành nếu share account công khai hoặc vi phạm ToS OpenAI.\n";
            }} else if (type === 'capcut') {{
                snippet = "\n• <b>Tài khoản CapCut Pro:</b> Bảo hành đúng thời hạn gói đã mua (1 đổi 1 nếu văng Pro). Từ chối nếu đăng nhập quá 2 thiết bị.\n";
            }} else if (type === 'vpn') {{
                snippet = "\n• <b>Tài khoản VPN:</b> Bảo hành kết nối và bản quyền suốt gói. Từ chối nếu dùng VPN để hack, DDoS, tấn công mạng.\n";
            }} else if (type === 'disclaimer') {{
                snippet = "\n⚖️ <b>TUYÊN BỐ MIỄN TRỪ TRÁCH NHIỆM:</b> Bên mua chịu 100% trách nhiệm trước pháp luật Việt Nam (Luật An ninh mạng & NĐ 15/2020/NĐ-CP). Shop là đơn vị trung gian kỹ thuật và hoàn toàn miễn trừ mọi trách nhiệm liên đới.\n";
            }}
            const curPos = policyTextarea.selectionStart;
            const text = policyTextarea.value;
            policyTextarea.value = text.slice(0, curPos) + snippet + text.slice(curPos);
            updateCounts();
            policyTextarea.focus();
        }}

        function resetToDefaultPolicy() {{
            if (confirm("Bạn có chắc chắn muốn khôi phục Toàn văn Chính sách về mẫu chuẩn Pháp Luật Việt Nam mặc định?")) {{
                policyTextarea.value = defaultPolicy;
                updateCounts();
            }}
        }}

        function resetToDefaultSummary() {{
            if (confirm("Bạn có chắc chắn muốn khôi phục Bản Tóm Tắt về mẫu mặc định?")) {{
                summaryTextarea.value = defaultSummary;
                updateCounts();
            }}
        }}

        async function savePolicyPayload(payload, resultDivId) {{
            const resDiv = document.getElementById(resultDivId);
            resDiv.style.display = 'block';
            resDiv.innerHTML = '<span class="text-info"><i class="fa-solid fa-spinner fa-spin me-1"></i> Đang lưu chính sách vào Supabase Database...</span>';

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
                    resDiv.innerHTML = '<div class="alert alert-success py-2 mb-0"><i class="fa-solid fa-circle-check me-1"></i> <b>Lưu thành công!</b> Đã đồng bộ tức thì vào Supabase Postgres & Bot Telegram.</div>';
                    setTimeout(() => {{ resDiv.style.display = 'none'; }}, 4000);
                }} else {{
                    const errDetail = data.detail || data.message || ('Lỗi máy chủ: ' + res.status);
                    resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi lưu: ' + errDetail + '</div>';
                }}
            }} catch (err) {{
                resDiv.innerHTML = '<div class="alert alert-danger py-2 mb-0"><i class="fa-solid fa-circle-exclamation me-1"></i> Lỗi kết nối: ' + err.message + '</div>';
            }}
        }}

        function savePolicyFull() {{
            const val = policyTextarea.value.trim();
            if (!val) {{
                alert("Vui lòng không để trống nội dung chính sách!");
                return;
            }}
            savePolicyPayload({{ 'WARRANTY_LEGAL_POLICY': val }}, 'saveResultFull');
        }}

        function saveSummary() {{
            const val = summaryTextarea.value.trim();
            if (!val) {{
                alert("Vui lòng không để trống nội dung tóm tắt!");
                return;
            }}
            savePolicyPayload({{ 'WARRANTY_SHORT_SUMMARY': val }}, 'saveResultSummary');
        }}
    </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)
