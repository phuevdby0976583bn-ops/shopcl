import config
from fastapi import Request
from sqladmin import BaseView, expose
from starlette.responses import HTMLResponse, RedirectResponse
from utils.utils import decode_token


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

        from admin_settings_view import render_unified_settings_page
        return await render_unified_settings_page(request, default_active_tab="policy")
