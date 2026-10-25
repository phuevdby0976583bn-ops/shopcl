import html as html_lib
import json
import os
from fastapi import Request
from sqladmin import BaseView, expose
from starlette.responses import HTMLResponse, RedirectResponse

import config
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

        from db import get_db_session
        from services.policy_defaults import (
            DEFAULT_WARRANTY_LEGAL_POLICY,
            DEFAULT_WARRANTY_SHORT_SUMMARY,
        )
        from services.settings import SettingsService

        async with get_db_session() as session:
            cur_settings = await SettingsService.get_all_settings(session)

        current_policy = cur_settings.get("WARRANTY_LEGAL_POLICY") or DEFAULT_WARRANTY_LEGAL_POLICY
        current_summary = cur_settings.get("WARRANTY_SHORT_SUMMARY") or DEFAULT_WARRANTY_SHORT_SUMMARY

        api_key = getattr(config, "SQLADMIN_RAW_PASSWORD", "MatKhauAdminCuaBan123") or "MatKhauAdminCuaBan123"
        admin_token = token or ""
        api_settings_save = "/api/settings/save"

        template_path = os.path.join(os.path.dirname(__file__), "templates", "admin_policy.html")
        with open(template_path, "r", encoding="utf-8") as f:
            template_content = f.read()

        html_content = (
            template_content
            .replace("{{ DEFAULT_POLICY_JSON }}", json.dumps(DEFAULT_WARRANTY_LEGAL_POLICY))
            .replace("{{ DEFAULT_SUMMARY_JSON }}", json.dumps(DEFAULT_WARRANTY_SHORT_SUMMARY))
            .replace("{{ INITIAL_POLICY_JSON }}", json.dumps(current_policy))
            .replace("{{ INITIAL_SUMMARY_JSON }}", json.dumps(current_summary))
            .replace("{{ POLICY_ESCAPED }}", html_lib.escape(current_policy))
            .replace("{{ SUMMARY_ESCAPED }}", html_lib.escape(current_summary))
            .replace("{{ API_SETTINGS_SAVE }}", api_settings_save)
            .replace("{{ API_KEY }}", api_key)
            .replace("{{ ADMIN_TOKEN }}", admin_token)
        )

        return HTMLResponse(content=html_content)
