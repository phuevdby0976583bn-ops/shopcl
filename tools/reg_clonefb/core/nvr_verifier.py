# -*- coding: utf-8 -*-
"""
core.nvr_verifier
Smart account parser and NVR (No-Verify) account verification engine.
Converts unverified Facebook accounts into verified (VR OTP) live accounts.
"""

import os
import time
import re
import json
import logging
import random
from typing import Dict, List, Optional, Tuple, Any, Union, Callable

from core.models import RegistrationInput, RegistrationResult
from core.http_client import HttpClient
from core.session_builder import get_random_device_profile, setup_session_cookies, build_request_context
from core.registration_service import _sync_response_cookies, parse_maturation_delay_seconds
from core.email_service import (
    BaseEmailProvider,
    get_email_provider,
    EmailAccount,
    submit_facebook_web_email_otp,
    remove_hotmail,
)
import core.facebook_checker as fb_checker
from core.facebook_checker import check_facebook_uid_live, check_facebook_account_live_status, check_registration_account_live

logger = logging.getLogger(__name__)


class SmartAccountParser:
    # Hỗ trợ tương thích ngược alias
    # parse_account_line sẽ được gán sau định nghĩa parse_line
    """
    Trình phân tích & nhận diện tài khoản Facebook thông minh:
    Tự động bóc tách các định dạng hỗn hợp:
    - UID|PASS
    - UID|PASS|2FA
    - UID|PASS|COOKIE
    - UID|PASS|2FA|COOKIE
    - UID|PASS|2FA|COOKIE|TOKEN
    - UID|PASS|COOKIE|TOKEN
    - UID|PASS|2FA|COOKIE|TOKEN|EMAIL
    - COOKIE_ONLY (chứa c_user và xs)
    """

    @classmethod
    @classmethod
    def parse_account_line(cls, line: str):
        return cls.parse_line(line)

    @classmethod
    def parse_line(cls, line: str) -> Optional[Dict[str, Any]]:
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#"):
            return None

        # Trường hợp 1: Toàn bộ dòng là Cookie thuần
        if ("c_user=" in line or "xs=" in line) and "|" not in line and "\t" not in line:
            uid_m = re.search(r"c_user=(\d+)", line)
            uid = uid_m.group(1) if uid_m else ""
            return {
                "uid": uid,
                "password": "",
                "two_factor_secret": "",
                "cookie": line,
                "token": "",
                "email": "",
                "email_password": "",
                "email_raw": "",
                "email_rest": "",
                "refresh_token": "",
                "client_id": "",
                "raw_line": line,
                "detected_format": "COOKIE_ONLY",
            }

        # Tách theo delimiter phổ biến: |, tab, hoặc khoảng trắng nếu định dạng cột
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 1 and "\t" in line:
            parts = [p.strip() for p in line.split("\t")]
        elif len(parts) == 1 and ":" in line and "@" not in line:
            parts = [p.strip() for p in line.split(":")]

        uid = ""
        pwd = ""
        twofa = ""
        cookie = ""
        token = ""
        email = ""
        email_pass = ""
        email_raw = ""
        email_rest = ""
        refresh_token = ""
        client_id = ""

        # Tìm vị trí Email nếu có (loại trừ proxy URL có user:pass@host)
        email_idx = -1
        for idx, p in enumerate(parts):
            if "@" in p and "." in p and " " not in p:
                if p.startswith(("http://", "https://", "socks5://", "socks4://", "socks5h://")) or "://" in p:
                    continue
                if re.search(r"@\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$", p):
                    continue
                email_idx = idx
                break

        if email_idx != -1:
            email = parts[email_idx]
            email_parts = parts[email_idx:]
            email_raw = "|".join(email_parts)
            if len(email_parts) > 1:
                email_pass = email_parts[1]
                email_rest = "|".join(email_parts[1:])
            for ep in email_parts[1:]:
                if ep.startswith("M.C") or len(ep) > 80:
                    refresh_token = ep
                elif re.fullmatch(r"[0-9a-fA-F-]{36}", ep):
                    client_id = ep
            fb_parts = parts[:email_idx]
        else:
            fb_parts = parts

        part_roles = {}
        # 1. Nhận diện Cookie theo vị trí thực tế
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and ("c_user=" in p or "datr=" in p or "xs=" in p or "sb=" in p) and len(p) > 20:
                cookie = p
                part_roles[idx] = "COOKIE"
                break

        # 2. Nhận diện Token theo vị trí thực tế
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and (p.startswith("EAAB") or p.startswith("EAA")) and len(p) > 25:
                token = p
                part_roles[idx] = "TOKEN"
                break

        # 3. Nhận diện 2FA Secret
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and re.fullmatch(r"[A-Za-z2-7\s]{16,36}", p) and not p.isdigit() and len(p.replace(" ", "")) in (16, 26, 32):
                twofa = p.replace(" ", "").upper()
                part_roles[idx] = "2FA"
                break

        # 4. Nhận diện UID (Bỏ qua số 0 hoặc chuỗi rác)
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and p.isdigit() and len(p) >= 8 and p != "0":
                uid = p
                part_roles[idx] = "UID"
                break

        # Nếu chưa có UID hợp lệ nhưng có Cookie: lấy từ c_user
        if (not uid or uid == "0") and cookie:
            uid_m = re.search(r"c_user=(\d+)", cookie)
            if uid_m and uid_m.group(1) != "0" and len(uid_m.group(1)) >= 8:
                uid = uid_m.group(1)
        if uid == "0":
            uid = ""

        # Nếu không có UID, không có Cookie, không có Email: Bỏ qua dòng rác
        if not uid and not cookie and not email:
            return None

        # 5. Nhận diện Proxy (nếu có trong dòng fb_parts)
        proxy = ""
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and p:
                p_clean = p.strip()
                if (
                    p_clean.startswith(("http://", "https://", "socks5://", "socks4://"))
                    or re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5}", p_clean)
                    or (re.match(r"^[a-zA-Z0-9.-]+:\d{2,5}", p_clean) and "." in p_clean.split(":")[0])
                ):
                    proxy = p_clean
                    part_roles[idx] = "PROXY"
                    break

        # 6. Phần tử còn lại trong fb_parts là Mật khẩu (PASS)
        for idx, p in enumerate(fb_parts):
            if idx not in part_roles and p:
                pwd = p
                part_roles[idx] = "PASS"
                break

        # Xác định chuỗi định dạng theo ĐÚNG thứ tự xuất hiện trong dòng gốc
        ordered_roles = [part_roles[i] for i in range(len(fb_parts)) if i in part_roles]
        if email_idx != -1:
            ordered_roles.append("EMAIL")

        detected_fmt = "|".join(ordered_roles) if ordered_roles else "UNKNOWN"

        return {
            "uid": uid,
            "password": pwd,
            "two_factor_secret": twofa,
            "cookie": cookie,
            "token": token,
            "email": email,
            "email_password": email_pass,
            "email_raw": email_raw,
            "email_rest": email_rest,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "proxy": proxy,
            "raw_line": line,
            "detected_format": detected_fmt,
        }

    @classmethod
    def parse_accounts(cls, text_or_lines: Union[str, List[str]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Nhập & phân tích hàng loạt dòng tài khoản.
        Trả về (danh_sách_acc_hợp_lệ, bảng_thống_kê_định_dạng).
        """
        if isinstance(text_or_lines, str):
            lines = [l.strip() for l in text_or_lines.splitlines() if l.strip()]
        else:
            lines = [str(l).strip() for l in text_or_lines if str(l).strip()]

        accounts: List[Dict[str, Any]] = []
        fmt_stats: Dict[str, int] = {}

        for l in lines:
            parsed = cls.parse_line(l)
            if parsed and (parsed.get("uid") or parsed.get("cookie") or parsed.get("password") or parsed.get("email")):
                accounts.append(parsed)
                fmt = parsed.get("detected_format", "OTHER")
                fmt_stats[fmt] = fmt_stats.get(fmt, 0) + 1

        return accounts, fmt_stats


def verify_single_nvr_account(
    account_data: Dict[str, Any],
    email_provider: BaseEmailProvider,
    task_input: RegistrationInput,
    emit_callback: Optional[Callable[[str, dict], None]] = None,
) -> RegistrationResult:
    """
    Xác minh một tài khoản NVR:
    1. Khởi tạo phiên qua Cookie (hoặc đăng nhập bằng UID/Pass).
    2. Gắn Email mới từ dịch vụ mail đã chọn qua /setemail/ (hoặc dùng mail có sẵn).
    3. Chờ mã OTP từ Email và xác nhận với Facebook.
    4. Đợi 10 giây để Facebook ổn định & kiểm định Live UID thực tế qua Graph API.
    5. Cập nhật kết quả LIVE hoặc Checkpoint 282.
    """
    start_time = time.time()
    wid = task_input.extra.get("worker_id", 1)

    uid = str(account_data.get("uid", "")).strip()

    def emit(event: str, payload: dict):
        if emit_callback:
            if "worker_id" not in payload:
                payload["worker_id"] = wid
            if "uid" not in payload and uid:
                payload["uid"] = uid
            if "email" not in payload and "new_email" in locals() and new_email:
                payload["email"] = new_email
            if "proxy" not in payload and getattr(task_input, "proxy", None):
                px = task_input.proxy
                payload["proxy"] = getattr(px, "real_ip", None) or (f"{px.host}:{px.port}" if hasattr(px, "host") and getattr(px, "port", None) else str(px))
            emit_callback(event, payload)
    pwd = str(account_data.get("password", "")).strip() or str(task_input.password or "").strip()
    if not pwd:
        from core.password_manager import PasswordManager
        pwd = PasswordManager.generate()
    cookie_str = str(account_data.get("cookie", "")).strip()
    twofa_secret = str(account_data.get("two_factor_secret", "")).strip()
    token_val = str(account_data.get("token", "") or "").strip()
    from core.registration_service import resolve_facebook_server
    server, _ = resolve_facebook_server(
        task_input.server,
        server_pool=task_input.extra.get("server_pool"),
        random_subset=task_input.extra.get("random_subset", False),
        random_server=task_input.extra.get("random_server", False),
    )
    target_label = uid or account_data.get("email") or "Acc NVR"

    emit("step", {"step": 1, "name": f"Khởi tạo phiên duyệt cho tài khoản {target_label}...", "target": target_label})

    # 1. Khởi tạo HttpClient với Device Profile Katana & Proxy
    profile = get_random_device_profile(task_input.device_type or "Android")
    if cookie_str:
        m_wd = re.search(r'wd=(\d+)x(\d+)', cookie_str)
        if m_wd:
            w_val, h_val = int(m_wd.group(1)), int(m_wd.group(2))
            profile.viewport_width = w_val
            profile.viewport_height = h_val
            profile.screen_width = w_val
            profile.screen_height = h_val
        m_dpr = re.search(r'(?:dpr|m_pixel_ratio)=([0-9.]+)', cookie_str)
        if m_dpr:
            try:
                profile.pixel_ratio = float(m_dpr.group(1))
            except Exception:
                pass
    client = HttpClient(
        proxy=task_input.proxy,
        timeout=15,
        impersonate=getattr(profile, "impersonate", "chrome124"),
        profile=profile,
    )
    try:
        setup_session_cookies(client, task_input.device_type or "Android", profile=profile)
        ctx = build_request_context(task_input.device_type or "Android", profile=profile)
        base_headers = ctx["base_headers"]
        client.update_headers(base_headers)

        # 2. Đồng bộ Cookie đã nhập vào Client
        if cookie_str:
            client.update_headers({"Cookie": cookie_str})
            for part in cookie_str.split(";"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k:
                        client.set_cookie(k, v, domain=".facebook.com")
                        client.set_cookie(k, v, domain=f".{server}")
                        client.set_cookie(k, v, domain=server)
            ck_dict = client.get_cookies()
            if not uid and "c_user" in ck_dict:
                uid = ck_dict["c_user"]

        # 3. Kiểm tra tính hợp lệ của phiên đăng nhập
        emit("step", {"step": 2, "name": f"Kiểm tra phiên đăng nhập UID {uid}...", "target": target_label})
        session_ok = False
        cur_cookies = client.get_cookies()
        if cur_cookies and any(k in cur_cookies for k in ("c_user", "xs")):
            try:
                r_check = client.get(f"https://{server}/confirmemail.php", timeout=10)
                if r_check.status_code in (200, 302):
                    session_ok = True
            except Exception:
                session_ok = True  # Giữ cookie hiện có

        # Nếu cookie không có hoặc không hợp lệ, thử đăng nhập bằng UID + Pass
        if not session_ok and uid and pwd:
            emit("info", {"message": "Cookie chưa có hoặc hết hạn. Đang tiến hành đăng nhập bằng UID/Mật khẩu..."})
            try:
                login_url = f"https://{server}/login/device-based/regular/login/"
                login_headers = dict(base_headers)
                login_headers["referer"] = f"https://{server}/login.php"
                r_lpage = client.get(f"https://{server}/login.php", timeout=10)
                lsd_val = re.search(r'name="lsd" value="([^"]+)"', r_lpage.text)
                jazoest_val = re.search(r'name="jazoest" value="([^"]+)"', r_lpage.text)

                login_data = {
                    "lsd": lsd_val.group(1) if lsd_val else "",
                    "jazoest": jazoest_val.group(1) if jazoest_val else "",
                    "email": uid,
                    "pass": pwd,
                    "login": "1",
                }
                r_login = client.post(login_url, data=login_data, headers=login_headers, timeout=12)
                cur_cookies = client.get_cookies()
                if any(k in cur_cookies for k in ("c_user", "xs")):
                    session_ok = True
                    emit("info", {"message": "Đăng nhập thành công! Đã lấy được Cookie phiên mới."})
            except Exception as e:
                logger.debug(f"Login error: {e}")

        # 3.5. Kiểm tra thời gian chờ ngấu của nick (nếu bật chế độ Chờ ngấu)
        if task_input.extra.get("enable_account_maturation", False):
            raw_mat = task_input.extra.get("account_maturation_delay", "60-120s (Ngẫu nhiên)")
            mat_s = parse_maturation_delay_seconds(raw_mat, default=90.0)
            created_at = float(account_data.get("created_at") or 0.0)
            now_t = time.time()
            if created_at > 0:
                elapsed_created = now_t - created_at
                wait_rem = max(0.0, mat_s - elapsed_created)
                msg_rem = f"Nick UID {uid} mới tạo cách đây {int(elapsed_created)}s ➔ Đợi ngấu thêm {int(wait_rem)}s"
            else:
                wait_rem = mat_s
                msg_rem = f"Đợi ngấu {int(wait_rem)}s"

            if wait_rem > 1.0:
                emit("info", {"message": f"⏳ [Chờ ngấu] {msg_rem} để Meta kích hoạt session ổn định trước khi nhận OTP (Chống 282)...", "uid": uid})
                emit("step", {"step": 2, "name": f"Chờ ngấu tài khoản ({int(wait_rem)}s)...", "uid": uid})
                t_end = time.time() + wait_rem
                stop_evt = task_input.extra.get("stop_event")
                while time.time() < t_end:
                    if stop_evt and stop_evt.is_set():
                        break
                    time.sleep(min(1.0, t_end - time.time()))

        # 4. Xác định hòm thư email để nhận OTP
        active_provider = email_provider
        use_existing_acc_email = (
            bool(account_data.get("is_registered_email"))
            or task_input.extra.get("email_service") in ("account_email", None, "")
            or getattr(email_provider, "provider_name", "") == "account_email"
        ) and bool(account_data.get("email"))

        mailbox: Optional[EmailAccount] = None
        if use_existing_acc_email:
            if account_data.get("mailbox"):
                mailbox = account_data["mailbox"]
                acc_email = mailbox.email
            else:
                acc_email = account_data["email"]
            mailbox = EmailAccount(
                email=acc_email,
                provider="hotmail_custom" if ("hotmail" in acc_email or "outlook" in acc_email) else "custom",
                password=account_data.get("email_password", ""),
                metadata={
                    "email": acc_email,
                    "password": account_data.get("email_password", ""),
                    "refresh_token": account_data.get("refresh_token", ""),
                    "client_id": account_data.get("client_id", ""),
                    "raw_line": account_data.get("email_raw", ""),
                }
            )
            new_email = acc_email
            emit("info", {"message": f"Sử dụng Email đi kèm trong tài khoản: {new_email}"})
        else:
            emit("step", {"step": 3, "name": "Lấy hòm thư mới từ dịch vụ mail đã chọn để gắn vào acc...", "target": target_label})
            try:
                domain_target = task_input.extra.get("metaking_domain") or task_input.extra.get("domain")
                wid = task_input.extra.get("worker_id", 1)
                try:
                    mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target, worker_id=wid)
                except TypeError:
                    mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target)
            except TypeError:
                wid = task_input.extra.get("worker_id", 1)
                mailbox = email_provider.create_mailbox(proxy=task_input.proxy, worker_id=wid)
            except Exception as e:
                elapsed = time.time() - start_time
                err_m = f"Lỗi lấy email xác minh: {e}"
                retry_on_nvr_chk = bool(task_input.extra.get("retry_on_nvr_with_new_mail", True))
                max_retries_chk = int(task_input.extra.get("max_otp_email_retries", 15))
                if retry_on_nvr_chk and max_retries_chk > 0:
                    emit("warning", {"message": f"{err_m} -> Tự động chuyển sang các lần thử tiếp theo ({max_retries_chk} lần)..."})
                    mailbox = None
                else:
                    emit("warning", {"message": f"{err_m} -> Tài khoản vẫn ở trạng thái NVR (Không DIE)."})
                    res = RegistrationResult(
                        success=False,
                        status="unverified",
                        uid=uid,
                        identifier=target_label,
                        password=pwd,
                        error_message=err_m,
                        elapsed_seconds=elapsed,
                        metadata={"unverified": True, "nvr": True, "not_die": True},
                    )
                    emit("unverified", {"result": res, "message": f"{err_m} (Tài khoản vẫn NVR - Không DIE)"})
                    return res

            if not mailbox or not getattr(mailbox, "email", None):
                is_strict_laoia = "laoia" in str(getattr(active_provider, "fixed_domain", "")).lower() or "laoia" in str(task_input.extra.get("email_service", "")).lower()
                if not is_strict_laoia:
                    try:
                        from core.email_service import TempMailPlusProvider
                        fallback_prov = TempMailPlusProvider()
                        mailbox = fallback_prov.create_mailbox(proxy=task_input.proxy)
                        if mailbox and getattr(mailbox, "email", None):
                            active_provider = fallback_prov
                            new_email = mailbox.email
                            emit("info", {"message": f"⚡ [Cứu Nguy Tự Động] Hòm thư chính nghẽn ➔ Cấp hòm thư dự phòng: {mailbox.email}"})
                    except Exception:
                        pass

            if not mailbox or not getattr(mailbox, "email", None):
                elapsed = time.time() - start_time
                err_m = "Không thể cấp phát hòm thư mới từ dịch vụ mail đã chọn (Hết kho hoặc lỗi kết nối)"
                retry_on_nvr_chk = bool(task_input.extra.get("retry_on_nvr_with_new_mail", True))
                max_retries_chk = int(task_input.extra.get("max_otp_email_retries", 15))
                if retry_on_nvr_chk and max_retries_chk > 0:
                    emit("warning", {"message": f"{err_m} -> Tự động chuyển sang các lần thử tiếp theo ({max_retries_chk} lần)..."})
                    new_email = ""
                else:
                    emit("warning", {"message": f"{err_m} -> Tài khoản vẫn ở trạng thái NVR (Không DIE)."})
                    res = RegistrationResult(
                        success=False,
                        status="unverified",
                        uid=uid,
                        identifier=target_label,
                        password=pwd,
                        error_message=err_m,
                        elapsed_seconds=elapsed,
                        metadata={"unverified": True, "nvr": True, "not_die": True},
                    )
                    emit("unverified", {"result": res, "message": f"{err_m} (Tài khoản vẫn NVR - Không DIE)"})
                    return res
            else:
                new_email = mailbox.email
                emit("info", {"message": f"Đã nhận hòm thư mới: {new_email}. Đang gắn vào Facebook qua GraphQL Relay (useCAAFBConfirmationAddContactPointMutation)..."})

        # Xử lý thông tin Email Raw để lưu đầy đủ mọi thành phần như đã nhập
        mail_pass = getattr(mailbox, "password", "") or ""
        mail_meta = getattr(mailbox, "metadata", {}) or {}
        mail_raw = mail_meta.get("raw_line") or ""
        mail_rest = ""
        if mail_raw and "|" in mail_raw:
            mail_rest = mail_raw.split("|", 1)[1]
        elif mail_pass:
            mail_rest = mail_pass
        if not mail_raw and mail_rest:
            mail_raw = f"{new_email}|{mail_rest}" 

        # 5. Gắn Email mới qua /changeemail/ và /setemail/ (nếu chưa gắn)
        fb_dtsg = ""
        jazoest = ""
        reg_instance = ""
        old_email = ""
        try:
            ch_headers = dict(base_headers)
            ch_headers["cookie"] = client.get_cookie_string()
            if not use_existing_acc_email and new_email:
                emit("step", {"step": 4, "name": f"Gắn Email {new_email} vào Facebook (GraphQL Relay Mutation)...", "target": target_label})
                ok_add = False
                try:
                    from core.email_service import add_contact_point_via_graphql
                    ok_add, add_msg = add_contact_point_via_graphql(
                        session=client,
                        email=new_email,
                        uid=uid,
                        server=server,
                        headers=ch_headers,
                        timeout=12.0
                    )
                    if ok_add:
                        emit("info", {"message": f"Facebook đã tiếp nhận Email {new_email} qua GraphQL Relay! Đang chờ máy chủ Meta phát mã OTP..."})
                except Exception as ex_gql_add:
                    logger.debug(f"GraphQL add contact point error in NVR verifier: {ex_gql_add}")
                if not ok_add:
                    r_ch = client.get(f"https://{server}/changeemail/", headers=ch_headers, timeout=10)
                    _sync_response_cookies(client, r_ch)
                    p_ch = r_ch.text
                    m_dtsg = re.search(r'name="fb_dtsg" value="([^"]+)"', p_ch) or re.search(r'"token":"([^"]+)"', p_ch)
                    if m_dtsg: fb_dtsg = m_dtsg.group(1)
                    m_jaz = re.search(r'name="jazoest" value="([^"]+)"', p_ch)
                    if m_jaz: jazoest = m_jaz.group(1)
                    m_old = re.search(r'name="old_email" value="([^"]+)"', p_ch)
                    if m_old: old_email = m_old.group(1)
                    m_inst = re.search(r'name="reg_instance" value="([^"]+)"', p_ch)
                    if m_inst: reg_instance = m_inst.group(1)

                    if not fb_dtsg:
                        for cf_probe_ep in [f"https://{server}/confirmphone.php", f"https://{server}/confirmemail.php"]:
                            try:
                                r_cf = client.get(cf_probe_ep, headers=ch_headers, timeout=10, allow_redirects=True)
                                p_cf = getattr(r_cf, "text", "") or ""
                                m_dtsg = (
                                    re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"\}', p_cf)
                                    or re.search(r'(NAf[A-Za-z0-9_\-]+:\d+:\d+)', p_cf)
                                    or re.search(r'name="fb_dtsg" value="([^"]+)"', p_cf)
                                    or re.search(r'"token":"([^"]+)"', p_cf)
                                )
                                if m_dtsg: fb_dtsg = m_dtsg.group(1)
                                m_jaz = re.search(r'name="jazoest" value="([^"]+)"', p_cf)
                                if m_jaz: jazoest = m_jaz.group(1)
                                if fb_dtsg:
                                    break
                            except Exception:
                                pass

                    if not jazoest and fb_dtsg:
                        jazoest = f"2{sum(ord(c) for c in fb_dtsg)}"

                    set_headers = dict(ch_headers)
                    set_headers.update({
                        "origin": f"https://{server}",
                        "referer": f"https://{server}/changeemail/",
                        "content-type": "application/x-www-form-urlencoded",
                    })
                    set_payload = {
                        "fb_dtsg": fb_dtsg,
                        "jazoest": jazoest or "25688",
                        "next": "",
                        "old_email": old_email,
                        "reg_instance": reg_instance,
                        "new": new_email,
                        "submit": "Thêm",
                    }
                    r_set = client.post(f"https://{server}/setemail/", data=set_payload, headers=set_headers, timeout=12)
                    _sync_response_cookies(client, r_set)
                    try:
                        # Kích hoạt trang xác nhận từ Facebook và chờ máy chủ Meta phát mã OTP đầu tiên
                        r_cf_trigger = client.get(f"https://{server}/confirmemail.php", headers=ch_headers, timeout=8)
                        _sync_response_cookies(client, r_cf_trigger)
                        emit("info", {"message": f"Facebook đã tiếp nhận Email {new_email}! Đang chờ máy chủ Meta phát mã OTP..."})
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Change email error: {e}")

        active_provider = email_provider
        if use_existing_acc_email and ("hotmail" in new_email or "outlook" in new_email):
            from core.email_service import DongVanHotmailProvider
            active_provider = DongVanHotmailProvider()

        retry_on_nvr = bool(task_input.extra.get("retry_on_nvr_with_new_mail", True))
        max_email_retries = min(int(task_input.extra.get("max_otp_email_retries", 3)), 3)
        retry_use_free = bool(task_input.extra.get("retry_use_free_mail", False))
        retry_email_srv = str(task_input.extra.get("retry_email_service", "as_setting")).lower().strip()
        free_prov_name = str(task_input.extra.get("fallback_email_service", "tempmail_plus")).lower().strip()
        otp_timeout = int(task_input.extra.get("otp_timeout", 20))

        ok_confirm = False
        confirm_msg = ""
        token_val = account_data.get("token", "") or ""

        # 6. Chờ mã OTP từ hòm thư ban đầu (nếu có hòm thư)
        if mailbox and new_email:
            emit("step", {"step": 5, "name": f"Chờ mã OTP Facebook gửi về {new_email}...", "target": target_label})
            otp_res = active_provider.wait_for_otp(
                account=mailbox,
                timeout_seconds=otp_timeout,
                proxy=task_input.proxy
            )

            # Nếu nhịp đầu chưa có OTP: thử resend 1 nhịp phụ
            if not getattr(otp_res, "success", False) and not getattr(otp_res, "otp_code", None):
                try:
                    resend_hdrs = dict(base_headers)
                    resend_hdrs["referer"] = f"https://{server}/confirmemail.php"
                    client.get(f"https://{server}/confirmemail.php?resend=1", headers=resend_hdrs, timeout=8)
                    time.sleep(2.0)
                    otp_res2 = active_provider.wait_for_otp(
                        account=mailbox,
                        timeout_seconds=min(15, otp_timeout),
                        proxy=task_input.proxy
                    )
                    if getattr(otp_res2, "success", False):
                        otp_res = otp_res2
                except Exception:
                    pass

            otp_code = getattr(otp_res, "otp_code", None)
            conf_link = getattr(otp_res, "confirmation_link", None)

            if otp_code or conf_link:
                # 7. Gửi mã OTP xác nhận với Facebook
                emit("step", {"step": 6, "name": f"Gửi mã OTP '{otp_code}' xác nhận lên Facebook...", "target": target_label})
                ok_confirm, confirm_msg = submit_facebook_web_email_otp(
                    session=client,
                    server=server,
                    otp_code=otp_code or "",
                    headers=base_headers,
                    confirmation_link=conf_link,
                    email=new_email,
                    fb_dtsg=fb_dtsg,
                    uid=uid,
                    enable_otp_pacing=task_input.extra.get("enable_otp_pacing", True),
                    pacing_min=float(task_input.extra.get("otp_pacing_min", 2.0)),
                    pacing_max=float(task_input.extra.get("otp_pacing_max", 3.5)),
                    proxy_ip=task_input.extra.get("proxy_ip"),
                    emit_callback=emit,
                )
                if ok_confirm:
                    time.sleep(random.uniform(2.5, 3.8))
                    # Ưu tiên kiểm định bằng session hiện tại (giữ nguyên kết nối TLS, cookie và header thiết bị):
                    chk_st, chk_msg = "unknown", ""
                    if client:
                        try:
                            c_st, c_msg = check_registration_account_live(client=client, server=server, uid=uid, proxy=task_input.proxy, timeout=8)
                            if c_st in ("live", "die", "nvr"):
                                chk_st = "die_282" if c_st == "die" else c_st
                                chk_msg = c_msg
                        except Exception:
                            pass
                    if chk_st == "unknown":
                        chk_st, chk_msg = fb_checker.check_facebook_account_live_status(
                            cookie_str=client.get_cookie_string(),
                            uid=uid,
                            password=pwd,
                            proxy=task_input.proxy,
                            timeout=8,
                        )
                    if chk_st == "live":
                        ok_confirm = True
                        emit("verified", {"message": f"🟢 Xác thực OTP '{otp_code}' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({chk_msg})", "email": new_email})
                    elif chk_st == "die_282":
                        emit("error", {"message": f"❌ Tài khoản UID {uid} bị Checkpoint 282 thực tế ({chk_msg})"})
                        elapsed = time.time() - start_time
                        result = RegistrationResult(
                            success=False,
                            status="checkpoint",
                            uid=uid,
                            identifier=new_email,
                            password=pwd,
                            error_message=f"Dính Checkpoint 282 ({chk_msg})",
                            elapsed_seconds=elapsed,
                            cookies=client.get_cookies(),
                            cookie_string=client.get_cookie_string(),
                            metadata={"checkpoint": True, "live_check": chk_msg, "email": new_email},
                        )
                        emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({chk_msg})"})
                        return result
                    elif chk_st == "nvr":
                        if ok_confirm:
                            try:
                                d_hdrs = dict(base_headers or {})
                                d_hdrs['referer'] = f'https://{server}/confirmemail.php'
                                client.get(f'https://{server}/home.php', headers=d_hdrs, timeout=6, allow_redirects=True)
                            except Exception:
                                pass
                            chk_st = "live"
                            chk_msg = "Đã giải phóng onboarding sang LIVE"
                            emit("verified", {"message": f"🟢 Xác thực OTP '{otp_code}' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({chk_msg})", "email": new_email})
                        else:
                            ok_confirm = False
                            confirm_msg = f'Tài khoản chưa thoát form xác minh OTP ({chk_msg})'
                            emit('warning', {'message': f'Tài khoản chưa thoát form xác minh OTP sau lần đầu ({chk_msg}) -> Cần đổi email xác minh lại ({max_email_retries} lần thử)...'})
                            try:
                                if hasattr(active_provider, 'release_account'):
                                    active_provider.release_account(new_email)
                                elif hasattr(email_provider, 'release_account'):
                                    email_provider.release_account(new_email)
                            except Exception:
                                pass
                    else:
                        if ok_confirm:
                            confirm_msg = 'Xác thực OTP thành công! Tài khoản LIVE!'
                            emit('verified', {'message': f'🟢 Xác thực OTP \'{otp_code}\' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({chk_msg})', 'email': new_email})
                        else:
                            ok_confirm = False
                            confirm_msg = f'Tài khoản chưa thoát form xác minh OTP ({chk_msg})'
                            emit('warning', {'message': f'Tài khoản chưa thoát form xác minh OTP sau lần đầu ({chk_msg}) -> Cần đổi email xác minh lại ({max_email_retries} lần thử)...'})
                            try:
                                if hasattr(active_provider, 'release_account'):
                                    active_provider.release_account(new_email)
                                elif hasattr(email_provider, 'release_account'):
                                    email_provider.release_account(new_email)
                            except Exception:
                                pass
                else:
                    c_low = str(confirm_msg).lower()
                    is_confirm_c = any(k in c_low for k in ("confirmemail", "confirmphone", "chờ xác minh", "cho xac minh", "nvr", "không die", "khong die"))
                    if is_confirm_c:
                        is_die_c = any(bad in c_low for bad in ("tài khoản của bạn đã bị tạm ngưng", "chúng tôi đã tạm ngưng", "your account has been suspended", "we suspended your account", "tài khoản của bạn đã bị vô hiệu hóa", "your account has been disabled", "180 ngày", "180 days", "selfie"))
                    else:
                        is_die_c = any(bad in c_low for bad in ("1501092823525282", "checkpoint 282", "checkpoint_282", "die 282", "/checkpoint/block", "/checkpoint/disabled", "/checkpoint/suspended", "help/103873106370583", "đình chỉ", "tạm ngưng", "vô hiệu hóa", "suspended", "disabled", "kháng nghị", "180 ngày", "180 days", "selfie"))
                    is_not_die = (not is_die_c) and any(k in c_low for k in ("không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh", "form xác minh", "chưa thoát", "confirmemail"))
                    if is_die_c:
                        emit("error", {"message": f"❌ Tài khoản UID {uid} bị Checkpoint 282 / Đình chỉ ({confirm_msg})"})
                        elapsed = time.time() - start_time
                        result = RegistrationResult(
                            success=False,
                            status="checkpoint",
                            uid=uid,
                            identifier=new_email,
                            password=pwd,
                            error_message=f"Dính Checkpoint 282 ({confirm_msg})",
                            elapsed_seconds=elapsed,
                            cookies=client.get_cookies(),
                            cookie_string=client.get_cookie_string(),
                            metadata={"checkpoint": True, "live_check": confirm_msg, "email": new_email},
                        )
                        try:
                            with open("accounts_die.txt", "a", encoding="utf-8-sig") as f_die:
                                f_die.write(f"{uid}|{pwd}|{new_email}|Checkpoint 282 ({confirm_msg})\n")
                        except Exception:
                            pass
                        emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({confirm_msg})"})
                        return result
                    emit("warning", {"message": f"Xác nhận OTP thất bại: {confirm_msg}"})
                    try:
                        if hasattr(active_provider, "release_account"): 
                            active_provider.release_account(new_email)
                        elif hasattr(email_provider, "release_account"): 
                            email_provider.release_account(new_email)
                    except Exception:
                        pass
            else:
                err_m = f"Hết thời gian chờ mã OTP từ {new_email}"
                confirm_msg = err_m
                try:
                    if hasattr(active_provider, "release_account"): 
                        active_provider.release_account(new_email)
                    elif hasattr(email_provider, "release_account"): 
                        email_provider.release_account(new_email)
                except Exception:
                    pass

                if retry_on_nvr and max_email_retries > 0:
                    emit("warning", {"message": f"{err_m} -> Bắt đầu đổi email mới để xác minh lại ({max_email_retries} lần thử)..."})
                else:
                    elapsed = time.time() - start_time
                    emit("warning", {"message": f"{err_m} -> Tài khoản vẫn ở trạng thái NVR (Tuyệt đối không DIE)."})
                    res = RegistrationResult(
                        success=False,
                        status="unverified",
                        uid=uid,
                        identifier=new_email,
                        email=new_email,
                        password=pwd,
                        token=token_val,
                        email_password=mail_pass,
                        email_raw=mail_raw,
                        email_rest=mail_rest,
                        error_message=err_m,
                        elapsed_seconds=elapsed,
                        cookies=client.get_cookies(),
                        cookie_string=client.get_cookie_string(),
                        metadata={"unverified": True, "nvr": True, "not_die": True, "email": new_email},
                    )
                    emit("unverified", {"result": res, "message": f"Tài khoản UID {uid} chưa nhận được OTP (Vẫn NVR - Không DIE)"})
                    return res
        else:
            if retry_on_nvr and max_email_retries > 0:
                emit("warning", {"message": f"Chưa có email xác minh ban đầu -> Bắt đầu cấp phát mail mới để xác minh ({max_email_retries} lần thử)..."})
            else:
                elapsed = time.time() - start_time
                err_m = "Không có email xác minh ban đầu"
                emit("warning", {"message": f"{err_m} -> Tài khoản vẫn ở trạng thái NVR (Không DIE)."})
                res = RegistrationResult(
                    success=False,
                    status="unverified",
                    uid=uid,
                    identifier=target_label,
                    password=pwd,
                    error_message=err_m,
                    elapsed_seconds=elapsed,
                    metadata={"unverified": True, "nvr": True, "not_die": True},
                )
                emit("unverified", {"result": res, "message": f"{err_m} (Tài khoản vẫn NVR - Không DIE)"})
                return res

        # Chu trình thử đổi email khác nếu chưa xác minh thành công
        if not ok_confirm and retry_on_nvr and max_email_retries > 0:
            from core.registration_service import bind_facebook_session_email

            def _resolve_nvr_retry_provider(attempt_idx: int):
                eff_mtk_key = task_input.extra.get("metaking_api_key") or ""
                extra_kwargs = {
                    "domain": task_input.extra.get("metaking_domain") or task_input.extra.get("domain") or "hotmail.com",
                    "server": task_input.extra.get("metaking_server", 1),
                    "service_type": task_input.extra.get("metaking_service_type", "email"),
                    "country_id": task_input.extra.get("metaking_country_id", 154),
                    "price": task_input.extra.get("metaking_price", "low"),
                    "selected_domains": task_input.extra.get("selected_domains") or task_input.extra.get("selected_custom_domains"),
                }
                if retry_email_srv in ("clean_trio", "trio", "clean_suite") or any(k in str(retry_email_srv).lower() for k in ("clean_trio", "clean_suite", "trio")):
                    p = get_email_provider("clean_trio", **extra_kwargs)
                    return p, "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus"
                elif retry_email_srv in ("hotmailtrusted_domain",):
                    p = get_email_provider("clean_trio", selected_domains=["hotmailtrusted.com"])
                    return p, "Mail Ảo Riêng: @hotmailtrusted.com"
                elif retry_email_srv in ("mailtoplus_domain",):
                    p = get_email_provider("clean_trio", selected_domains=["mailto.plus"])
                    return p, "Mail Ảo Riêng: @mailto.plus"
                elif retry_email_srv in ("smail1s_domain",) or "smail1s_domain" in str(retry_email_srv).lower():
                    p = get_email_provider("smail1s_domain", **extra_kwargs)
                    return p, "Mail Ảo Riêng: @smail1s.com"
                elif retry_email_srv in ("laoia_domain",) or "laoia_domain" in str(retry_email_srv).lower():
                    p = get_email_provider("laoia_domain", **extra_kwargs)
                    return p, "Mail Ảo Riêng: @laoia.com"
                elif retry_email_srv in ("smailwork_domain",) or "smailwork_domain" in str(retry_email_srv).lower():
                    p = get_email_provider("smailwork_domain", **extra_kwargs)
                    return p, "Mail Ảo Riêng: @smailwork.com (pqudx6448)"
                elif retry_email_srv in ("as_setting", "setting", "") and not retry_use_free:
                    p = email_provider
                    if not p:
                        main_srv = task_input.extra.get("email_service", "custom_hotmail")
                        p = get_email_provider(main_srv, api_key=eff_mtk_key, **extra_kwargs)
                    lbl = getattr(p, "provider_name", "Cấu hình chính (Setting)")
                    return p, f"Cấu hình chính ({lbl})"
                elif retry_email_srv in ("all_free", "all_free_mail", "tat_ca_mail_free") or any(k in str(retry_email_srv).lower() for k in ("all_free", "tat_ca", "tất cả")):
                    p = get_email_provider("all_free")
                    return p, "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)"
                elif retry_email_srv in ("auto_rotator", "smart_rotator") or any(k in str(retry_email_srv).lower() for k in ("auto_rotator", "xoay", "mọi nguồn", "moi nguon")):
                    p = get_email_provider("auto_rotator")
                    return p, "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)"
                elif retry_use_free and retry_email_srv in ("as_setting", "setting", ""):
                    p = get_email_provider("auto_rotator")
                    return p, "Mail Ảo Free (Random Toàn Bộ Nguồn)"
                else:
                    p = get_email_provider(retry_email_srv, api_key=eff_mtk_key, **extra_kwargs)
                    lbl = getattr(p, "provider_name", retry_email_srv)
                    if not p:
                        p = email_provider or get_email_provider("auto_rotator")
                    return p, lbl

            tried_emails = set([new_email] if new_email else [])
            wid_val = task_input.extra.get("worker_id", 1)

            for retry_idx in range(1, max_email_retries + 1):
                if ok_confirm:
                    break
                try:
                    pre_chk_st, pre_chk_msg = check_registration_account_live(
                        client=client,
                        server=server,
                        uid=uid,
                        proxy=task_input.proxy
                    )
                except Exception as e:
                    logger.debug(f"check_registration_account_live retry error: {e}")
                    pre_chk_st, pre_chk_msg = "unknown", str(e)
                if pre_chk_st == "die":
                    confirm_msg = f"Tài khoản bị DIE ({pre_chk_msg})"
                    emit("error", {"message": f"❌ [Lần {retry_idx}/{max_email_retries}] Tài khoản UID {uid} đã bị DIE ({pre_chk_msg}) -> Dừng xác minh lại ngay!"})
                    break
                elif pre_chk_st == "live":
                    ok_confirm = True
                    emit("verified", {"message": f"🟢 [Lần {retry_idx}/{max_email_retries}] Tài khoản UID {uid} đã thoát form xác minh thành công và LIVE ({pre_chk_msg})!", "email": new_email})
                    break
                elif pre_chk_st == "session_expired":
                    emit("warning", {"message": f"⚠️ [Lần {retry_idx}/{max_email_retries}] Phiên tạm hết hạn ({pre_chk_msg}) -> Tiếp tục thử làm mới và gắn email mới..."})

                if retry_idx > 1:
                    # Giãn cách 3.0s - 4.5s giữa các lần đổi email để Facebook không đánh cờ spam/takeover
                    cooldown_sec = random.uniform(3.0, 4.5)
                    time.sleep(cooldown_sec)
                    try:
                        warm_hdrs = dict(base_headers)
                        warm_hdrs["referer"] = f"https://{server}/confirmemail.php"
                        client.get(f"https://{server}/confirmemail.php", headers=warm_hdrs, timeout=8)
                    except Exception:
                        pass

                cur_prov, prov_label = _resolve_nvr_retry_provider(retry_idx)
                emit("step", {"step": 4, "name": f"Đổi email mới xác minh lại [Lần {retry_idx}/{max_email_retries}]...", "target": target_label})

                new_box = None
                domain_target = task_input.extra.get("metaking_domain") or task_input.extra.get("domain")
                for alloc_try in range(3):
                    try:
                        if domain_target:
                            new_box = cur_prov.create_mailbox(proxy=task_input.proxy, domain=domain_target, worker_id=wid_val)
                        else:
                            new_box = cur_prov.create_mailbox(proxy=task_input.proxy, worker_id=wid_val)
                    except TypeError:
                        try:
                            new_box = cur_prov.create_mailbox(proxy=task_input.proxy, domain=domain_target)
                        except TypeError:
                            try:
                                new_box = cur_prov.create_mailbox(proxy=task_input.proxy, worker_id=wid_val)
                            except TypeError:
                                try:
                                    new_box = cur_prov.create_mailbox(proxy=task_input.proxy)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                    if new_box and getattr(new_box, "email", None) and new_box.email not in tried_emails:
                        break

                if not new_box or not getattr(new_box, "email", None) or new_box.email in tried_emails:
                    is_rot_retry = (
                        retry_email_srv in ("all_free", "all_free_mail", "tat_ca_mail_free", "auto_rotator", "smart_rotator")
                        or any(k in str(retry_email_srv).lower() for k in ("all_free", "tat_ca", "tất cả", "auto_rotator", "xoay"))
                    )
                    if is_rot_retry:
                        cur_prov = get_email_provider("auto_rotator")
                        prov_label = "Mail Ảo Free (Random Toàn Bộ Nguồn)"
                        try:
                            new_box = cur_prov.create_mailbox(proxy=task_input.proxy, worker_id=wid_val)
                        except Exception:
                            pass

                if not new_box or not getattr(new_box, "email", None):
                    is_strict_laoia = "laoia" in str(getattr(cur_prov, "fixed_domain", "")).lower() or "laoia" in str(retry_email_srv).lower()
                    if not is_strict_laoia:
                        try:
                            from core.email_service import TempMailPlusProvider
                            fallback_prov = TempMailPlusProvider()
                            new_box = fallback_prov.create_mailbox(proxy=task_input.proxy)
                            if new_box and getattr(new_box, "email", None):
                                cur_prov = fallback_prov
                                prov_label = "TempMail.Plus (Đa đuôi sạch tức thì)"
                        except Exception:
                            pass

                if not new_box or not getattr(new_box, "email", None):
                    emit("warning", {"message": f"[Lần {retry_idx}/{max_email_retries}] Không thể tạo hòm thư mới ({prov_label}). Tiếp tục lần thử sau..."})
                    continue

                new_email = new_box.email
                tried_emails.add(new_email)
                mail_pass = getattr(new_box, "password", "") or ""
                mail_raw = getattr(new_box, "raw_account", "") or f"{new_email}|{mail_pass}"
                mail_rest = getattr(new_box, "raw_account", "") or f"{new_email}|{mail_pass}"

                emit("info", {"message": f"[Lần {retry_idx}/{max_email_retries}] Đã nhận hòm thư: {new_email} ({prov_label}). Đang gắn vào Facebook qua GraphQL Relay..."})

                # Meta tu dong thay the contactpoint khi OTP moi thanh cong; khong gui mutation go contactpoint cu truoc de chong Checkpoint 282 (ATO defense)

                bind_ok = bind_facebook_session_email(
                    client=client,
                    server=server,
                    new_email=new_email,
                    base_headers=base_headers,
                    fb_dtsg=fb_dtsg,
                    jazoest=jazoest,
                    reg_instance=reg_instance,
                    timeout=10,
                    uid=uid,
                )
                if not bind_ok:
                    emit("warning", {"message": f"[Lần {retry_idx}/{max_email_retries}] Gắn {new_email} vào Facebook thất bại. Thử hòm thư khác..."})
                    try:
                        if hasattr(cur_prov, "release_account"): 
                            cur_prov.release_account(new_email)
                    except Exception:
                        pass
                    continue

                emit("step", {"step": 5, "name": f"Chờ mã OTP Facebook gửi về {new_email} [Lần {retry_idx}/{max_email_retries}]...", "target": target_label})
                otp_res = cur_prov.wait_for_otp(account=new_box, timeout_seconds=otp_timeout, proxy=task_input.proxy)
                if not getattr(otp_res, "success", False) and not getattr(otp_res, "otp_code", None):
                    try:
                        client.get(f"https://{server}/confirmemail.php?resend=1", headers=base_headers, timeout=8)
                        time.sleep(2.0)
                        otp_res2 = cur_prov.wait_for_otp(account=new_box, timeout_seconds=min(15, otp_timeout), proxy=task_input.proxy)
                        if getattr(otp_res2, "success", False):
                            otp_res = otp_res2
                    except Exception:
                        pass

                if getattr(otp_res, "success", False) and getattr(otp_res, "otp_code", None):
                    otp_code = otp_res.otp_code
                    emit("info", {"message": f"[Lần {retry_idx}/{max_email_retries}] Bắt được mã OTP: {otp_code}"})
                    emit("step", {"step": 6, "name": f"Gửi mã OTP '{otp_code}' xác nhận lên Facebook...", "target": target_label})
                    ok_confirm, confirm_msg = submit_facebook_web_email_otp(
                        session=client,
                        server=server,
                        otp_code=otp_code,
                        headers=base_headers,
                        email=new_email,
                        fb_dtsg=fb_dtsg,
                        uid=uid,
                        enable_otp_pacing=task_input.extra.get("enable_otp_pacing", True),
                        pacing_min=float(task_input.extra.get("otp_pacing_min", 2.0)),
                        pacing_max=float(task_input.extra.get("otp_pacing_max", 3.5)),
                        proxy_ip=task_input.extra.get("proxy_ip"),
                    emit_callback=emit,
                    )
                    if ok_confirm:
                        time.sleep(random.uniform(1.8, 2.8))
                        chk_st, chk_msg = fb_checker.check_facebook_account_live_status(
                            cookie_str=client.get_cookie_string(),
                            uid=uid,
                            password=pwd,
                            proxy=task_input.proxy,
                            timeout=8,
                        )
                        if chk_st == "unknown" and client:
                            try:
                                c_st, c_msg = check_registration_account_live(client=client, server=server, uid=uid, proxy=task_input.proxy, timeout=8)
                                if c_st in ("live", "die", "nvr"):
                                    chk_st = "die_282" if c_st == "die" else c_st
                                    chk_msg = c_msg
                            except Exception:
                                pass
                        if chk_st == "live":
                            ok_confirm = True
                            emit("verified", {"message": f"🟢 [Lần {retry_idx}/{max_email_retries}] Xác thực OTP '{otp_code}' với email mới {new_email} thành công! Tài khoản LIVE!", "email": new_email})
                            break
                        elif chk_st == "die_282":
                            emit("error", {"message": f"❌ Tài khoản UID {uid} bị Checkpoint 282 thực tế ({chk_msg})"})
                            elapsed = time.time() - start_time
                            result = RegistrationResult(
                                success=False,
                                status="checkpoint",
                                uid=uid,
                                identifier=new_email,
                                password=pwd,
                                error_message=f"Dính Checkpoint 282 ({chk_msg})",
                                elapsed_seconds=elapsed,
                                cookies=client.get_cookies(),
                                cookie_string=client.get_cookie_string(),
                                metadata={"checkpoint": True, "live_check": chk_msg, "email": new_email},
                            )
                            emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({chk_msg})"})
                            return result
                        elif chk_st == "nvr":
                            if ok_confirm:
                                try:
                                    d_hdrs = dict(base_headers or {})
                                    d_hdrs['referer'] = f'https://{server}/confirmemail.php'
                                    client.get(f'https://{server}/home.php', headers=d_hdrs, timeout=6, allow_redirects=True)
                                except Exception:
                                    pass
                                ok_confirm = True
                                confirm_msg = 'Xác thực OTP thành công! Tài khoản LIVE!'
                                emit('verified', {'message': f"🟢 [Lần {retry_idx}/{max_email_retries}] Xác thực OTP '{otp_code}' với email mới {new_email} thành công! Tài khoản LIVE!", 'email': new_email})
                                break
                            else:
                                ok_confirm = False
                                confirm_msg = f'Tài khoản chưa thoát trang xác minh OTP ({chk_msg})'
                                emit('warning', {'message': f'[Lần {retry_idx}/{max_email_retries}] ⚠️ Mã OTP đã gửi nhưng tài khoản vẫn còn ở form xác minh ({chk_msg}). Đổi sang email khác thử lại...'})
                                try:
                                    if hasattr(cur_prov, 'release_account'):
                                        cur_prov.release_account(new_email)
                                except Exception:
                                    pass
                        else:
                            time.sleep(1.5)
                            try:
                                re_chk_st, re_chk_msg = check_registration_account_live(
                                    client=client,
                                    server=server,
                                    uid=uid,
                                    proxy=task_input.proxy
                                )
                            except Exception as e:
                                logger.debug(f"check_registration_account_live post-check error: {e}")
                                re_chk_st, re_chk_msg = "unknown", str(e)
                            if re_chk_st == "live":
                                ok_confirm = True
                                confirm_msg = 'Xác thực OTP thành công! Tài khoản LIVE!'
                                emit('verified', {'message': f"🟢 [Lần {retry_idx}/{max_email_retries}] Xác thực OTP '{otp_code}' với email mới {new_email} thành công! Tài khoản LIVE! ({re_chk_msg})", 'email': new_email})
                                break
                            elif re_chk_st == "die":
                                ok_confirm = False
                                confirm_msg = f"Tài khoản bị DIE ({re_chk_msg})"
                                result = RegistrationResult(
                                    success=False,
                                    status="failed",
                                    uid=uid,
                                    identifier=target,
                                    password=pwd,
                                    error_message=f"Dính Checkpoint 282 ({re_chk_msg})",
                                    elapsed_seconds=round(time.time() - start_time, 2),
                                    cookies=client.get_cookies(),
                                    cookie_string=client.get_cookie_string(),
                                    metadata={"checkpoint": True, "live_check": re_chk_msg, "email": new_email},
                                )
                                emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({re_chk_msg})"})
                                return result
                            else:
                                ok_confirm = False
                                confirm_msg = f"Chưa xác thực được Live qua probe ({re_chk_msg})"
                                emit('warning', {'message': f"[Lần {retry_idx}/{max_email_retries}] ⚠️ Chưa xác nhận được trạng thái Live sau OTP ({re_chk_msg}). Đổi sang email khác thử lại..."})
                                try:
                                    if hasattr(cur_prov, 'release_account'):
                                        cur_prov.release_account(new_email)
                                except Exception:
                                    pass
                    else:
                        c_low = str(confirm_msg).lower()
                        is_confirm_c = any(k in c_low for k in ("confirmemail", "confirmphone", "chờ xác minh", "cho xac minh", "nvr", "không die", "khong die"))
                    if is_confirm_c:
                        is_die_c = any(bad in c_low for bad in ("tài khoản của bạn đã bị tạm ngưng", "chúng tôi đã tạm ngưng", "your account has been suspended", "we suspended your account", "tài khoản của bạn đã bị vô hiệu hóa", "your account has been disabled", "180 ngày", "180 days", "selfie"))
                    else:
                        is_die_c = any(bad in c_low for bad in ("1501092823525282", "checkpoint 282", "checkpoint_282", "die 282", "/checkpoint/block", "/checkpoint/disabled", "/checkpoint/suspended", "help/103873106370583", "đình chỉ", "tạm ngưng", "vô hiệu hóa", "suspended", "disabled", "kháng nghị", "180 ngày", "180 days", "selfie"))
                        is_not_die = (not is_die_c) and any(k in c_low for k in ("không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh", "form xác minh", "chưa thoát", "confirmemail"))
                        if is_die_c:
                            confirm_msg = f"Tài khoản bị DIE ({confirm_msg})"
                            emit("error", {"message": f"❌ [Lần {retry_idx}/{max_email_retries}] Tài khoản UID {uid} bị Checkpoint 282 / Đình chỉ ({confirm_msg})"})
                            elapsed = round(time.time() - start_time, 2)
                            result = RegistrationResult(
                                success=False,
                                status="checkpoint",
                                uid=uid,
                                identifier=target,
                                password=pwd,
                                error_message=f"Dính Checkpoint 282 ({confirm_msg})",
                                elapsed_seconds=elapsed,
                                cookies=client.get_cookies(),
                                cookie_string=client.get_cookie_string(),
                                metadata={"checkpoint": True, "live_check": confirm_msg, "email": new_email},
                            )
                            try:
                                with open("accounts_die.txt", "a", encoding="utf-8-sig") as f_die:
                                    f_die.write(f"{uid}|{pwd}|{new_email}|Checkpoint 282 ({confirm_msg})\n")
                            except Exception:
                                pass
                            emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({confirm_msg})"})
                            return result
                        confirm_msg = f"Gửi OTP thất bại ({confirm_msg})"
                        emit("warning", {"message": f"[Lần {retry_idx}/{max_email_retries}] ⚠️ Mã OTP đã gửi nhưng Facebook chưa chấp nhận ({confirm_msg}). Đổi sang email khác thử lại..."})
                        try:
                            if hasattr(cur_prov, "release_account"): 
                                cur_prov.release_account(new_email)
                        except Exception:
                            pass
                else:
                    otp_err = getattr(otp_res, "error", None) or f"Timeout {otp_timeout}s"
                    emit("warning", {"message": f"[Lần {retry_idx}/{max_email_retries}] Không nhận được OTP từ hòm thư {new_email} ({otp_err})"})
                    try:
                        if hasattr(cur_prov, "release_account"): 
                            cur_prov.release_account(new_email)
                    except Exception:
                        pass
        if not ok_confirm:
            elapsed = time.time() - start_time
            err_m = f"Xác nhận OTP với Facebook thất bại: {confirm_msg}"
            try:
                if hasattr(email_provider, "release_account"):
                    email_provider.release_account(new_email)
            except Exception:
                pass

            # Kiểm tra chéo với Graph API công khai: Nếu UID vẫn LIVE công khai, tài khoản KHÔNG THỂ NÀO DIE!
            is_graph_live = False
            g_network_err = False
            if uid:
                try:
                    g_ok, g_m = fb_checker.check_facebook_uid_live(uid, proxy=task_input.proxy, timeout=5)
                    is_graph_live = g_ok
                    if "lỗi mạng" in g_m.lower():
                        g_network_err = True
                except Exception:
                    g_network_err = True

            c_low = str(confirm_msg).lower()
            is_real_cp_text = any(bad in c_low for bad in (
                "1501092823525282", "checkpoint 282", "checkpoint_282", "die 282",
                "checkpoint/block", "checkpoint/disabled", "checkpoint/suspended",
                "tạm ngưng", "vô hiệu hóa", "suspended", "disabled", "180 ngày", "selfie", "ufac",
                "1357053", "kháng nghị", "help/103873106370583"
            ))
            is_not_die = (not is_real_cp_text) and any(k in c_low for k in ("không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh", "form xác minh", "chưa thoát", "confirmemail"))
            is_checkpoint = bool(is_real_cp_text)
            if is_checkpoint:
                emit("error", {"message": f"🔴 Tài khoản UID {uid} bị Checkpoint 282: {confirm_msg}"})
                res = RegistrationResult(
                    success=False,
                    status="checkpoint",
                    uid=uid,
                    identifier=new_email,
                    email=new_email,
                    password=pwd,
                    token=token_val,
                    email_password=mail_pass,
                    email_raw=mail_raw,
                    email_rest=mail_rest,
                    error_message=err_m,
                    elapsed_seconds=elapsed,
                    cookies=client.get_cookies(),
                    cookie_string=client.get_cookie_string(),
                    metadata={"checkpoint": True, "error": confirm_msg, "email": new_email},
                )
                try:
                    with open("accounts_die.txt", "a", encoding="utf-8-sig") as f_die:
                        f_die.write(f"{uid}|{pwd}|{new_email}|Checkpoint 282 ({confirm_msg})\n")
                except Exception:
                    pass
                emit("failed", {"result": res, "message": f"Tài khoản UID {uid} bị Checkpoint 282"})
                return res
            emit("warning", {"message": f"{err_m} -> Tài khoản vẫn ở trạng thái NVR (Tuyệt đối không DIE)."})
            res = RegistrationResult(
                success=False,
                status="unverified",
                uid=uid,
                identifier=new_email,
                email=new_email,
                password=pwd,
                token=token_val,
                email_password=mail_pass,
                email_raw=mail_raw,
                email_rest=mail_rest,
                error_message=err_m,
                elapsed_seconds=elapsed,
                cookies=client.get_cookies(),
                cookie_string=cookie_str or client.get_cookie_string(),
                metadata={"unverified": True, "nvr": True, "not_die": True, "email": new_email},
            )
            emit("unverified", {"result": res, "message": f"Tài khoản UID {uid} chưa xác minh xong OTP (Vẫn NVR - Không DIE)"})
            return res

        emit("info", {"message": "✅ Facebook đã nhận mã OTP! Bắt đầu kiểm định ổn định 10 giây..."})

        try:
            home_hdrs = dict(base_headers)
            home_hdrs["referer"] = f"https://{server}/confirmemail.php"
            time.sleep(random.uniform(1.2, 2.0))
            r_hm = client.get(f"https://{server}/", headers=home_hdrs, timeout=8)
            _sync_response_cookies(client, r_hm)
        except Exception:
            pass

        # Cập nhật cookies phiên mới & bảo toàn c_user/xs nếu cookie mới bị thiếu
        fresh_cookies = client.get_cookies()
        fresh_cookie_str = client.get_cookie_string()
        if cookie_str and ("c_user=" not in fresh_cookie_str or "xs=" not in fresh_cookie_str):
            for part in cookie_str.split(";"):
                if "=" in part:
                    k, v = part.strip().split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k and k not in fresh_cookies:
                        fresh_cookies[k] = v
                        client.set_cookie(k, v, domain=".facebook.com")
            fresh_cookie_str = client.get_cookie_string()

        # Trích xuất Token thụ động nếu caller yêu cầu (KHÔNG gửi active probe tới /composer/ocelot gây checkpoint 282)
        token_val = account_data.get("token", "")
        if task_input.extra.get("extract_token", False):
            try:
                src_text = locals().get("confirm_text", "") or ""
                if src_text:
                    m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)
                    if m_eaab:
                        token_val = m_eaab.group(1)
            except Exception:
                pass
    
        # 7.5 Onboarding nhẹ nhàng giải phóng hộp thoại chào mừng đầu tiên (?dismiss=1)
        try:
            onb_hdrs = dict(base_headers)
            onb_hdrs["referer"] = f"https://{server}/confirmemail.php"
            client.get(f"https://{server}/home.php", headers=onb_hdrs, timeout=6, allow_redirects=True)
        except Exception:
            pass

        # 8. Đợi 10 giây để Facebook xét duyệt & kiểm định Live UID thực tế qua Graph API
        live_delay = float(task_input.extra.get("live_check_delay", 10.0))
        if live_delay > 0:
            emit("step", {"step": 7, "name": f"Đợi {int(live_delay)}s để Facebook xét duyệt phiên & kiểm định Live UID ({uid})...", "target": target_label})
            elapsed_wait = 0.0
            step_wait = min(2.0, live_delay)
            while elapsed_wait < live_delay:
                remain_s = max(0, int(live_delay - elapsed_wait))
                emit("info", {"message": f"⏳ Đang đợi Facebook hoàn tất xét duyệt phiên nick... (còn {remain_s}s)"})
                time.sleep(step_wait)
                elapsed_wait += step_wait

        live_status, live_msg = fb_checker.check_facebook_account_live_status(
            cookie_str=fresh_cookie_str,
            uid=uid,
            password=pwd,
            proxy=task_input.proxy,
            timeout=10,
        )
        elapsed = time.time() - start_time

        # Xử lý thông tin Email Raw để lưu đầy đủ mọi thành phần như đã nhập
        mail_pass = getattr(mailbox, "password", "") or ""
        mail_meta = getattr(mailbox, "metadata", {}) or {}
        mail_raw = mail_meta.get("raw_line") or ""
        mail_rest = ""
        if mail_raw and "|" in mail_raw:
            mail_rest = mail_raw.split("|", 1)[1]
        elif mail_pass:
            mail_rest = mail_pass
        if not mail_raw and mail_rest:
            mail_raw = f"{new_email}|{mail_rest}"

        # Trường hợp 1: Checkpoint 282 / Khóa thực tế (DIE thật)
        if live_status == "die_282":
            emit("error", {"message": f"❌ Tài khoản UID {uid} bị Checkpoint 282 thực tế ({live_msg})"})
            result = RegistrationResult(
                success=False,
                status="checkpoint",
                uid=uid,
                identifier=new_email,
                password=pwd,
                error_message=f"Dính Checkpoint 282 ({live_msg})",
                elapsed_seconds=elapsed,
                cookies=fresh_cookies,
                cookie_string=fresh_cookie_str,
                metadata={"checkpoint": True, "live_check": live_msg, "email": new_email},
            )
            try:
                with open("accounts_die.txt", "a", encoding="utf-8-sig") as f_die:
                    f_die.write(f"{uid}|{pwd}|{new_email}|Checkpoint 282 ({live_msg})\n")
            except Exception:
                pass
            emit("failed", {"result": result, "message": f"Tài khoản UID {uid} bị Checkpoint 282 ({live_msg})"})
            return result

        # Trường hợp 2: Tài khoản vẫn ở trạng thái NVR (Chưa thoát xác minh OTP - Tuyệt đối không báo Live ảo và không báo DIE!)
        if live_status != "live":
            emit("warning", {"message": f"⚠️ Tài khoản UID {uid} vẫn ở màn hình NVR ({live_msg}) -> Lưu dạng NVR (Chờ xác minh - Tuyệt đối không DIE)."})
            result = RegistrationResult(
                success=False,
                status="unverified",
                uid=uid,
                identifier=new_email,
                email=new_email,
                password=pwd,
                token=token_val,
                two_factor_secret=twofa_secret,
                cookies=fresh_cookies,
                cookie_string=fresh_cookie_str,
                email_password=mail_pass,
                email_raw=mail_raw,
                email_rest=mail_rest,
                error_message=f"Chưa hoàn tất OTP (Vẫn NVR - Không DIE): {live_msg}",
                elapsed_seconds=elapsed,
                metadata={"unverified": True, "nvr": True, "not_die": True, "email": new_email, "otp_code": otp_code, "live_check": live_msg},
            )
            try:
                with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f_un:
                    f_un.write(f"{uid}|{pwd}|{fresh_cookie_str}|{new_email}|NVR\n")
            except Exception:
                pass
            emit("unverified", {"result": result, "message": f"Tài khoản UID {uid} vẫn ở trạng thái NVR (Không DIE)"})
            return result

        # Thành công Live thực tế
        emit("info", {"message": f"🟢 ĐÃ XÁC NHẬN LIVE THỰC TẾ! {live_msg} (UID {uid})"})
        # Trụ cột 5 & Giữ nick: Làm ấm phiên sau xác minh (Session Warmup)
        if task_input.extra.get("session_warmup", True):
            try:
                emit("step", {"name": f"Làm ấm phiên sau xác minh (Home Feed) cho UID {uid}...", "target": uid})
                warmup_headers = dict(base_headers)
                warmup_headers["referer"] = f"https://{server}/"
                client.get(f"https://{server}/", headers=warmup_headers, timeout=10)
                time.sleep(random.uniform(2.0, 3.5))
            except Exception:
                pass

        # Kích hoạt 2FA TOTP THẬT cho tài khoản LIVE (KO BỊA)
        if not twofa_secret and task_input.extra.get('enable_2fa', True):
            try:
                if task_input.extra.get("behavioral_delays", True):
                    time.sleep(random.uniform(1.8, 3.2))
                emit('step', {'name': f'[2FA] Đang tự động kích hoạt 2FA TOTP THẬT cho UID {uid}...', 'target': uid})
                from core.two_factor_service import enable_facebook_2fa
                ok_2fa, sec_2fa, otp_2fa, msg_2fa = enable_facebook_2fa(
                    client=client,
                    uid=uid,
                    password=pwd,
                    server='www.facebook.com',
                    emit=emit,
                )
                if ok_2fa and sec_2fa:
                    twofa_secret = sec_2fa
                    emit('info', {'message': f'[2FA] KÍCH HOẠT 2FA TOTP THẬT THÀNH CÔNG! Secret: {sec_2fa} (OTP hiện tại: {otp_2fa})'})
                else:
                    emit('warning', {'message': f'[2FA] Không kích hoạt được 2FA thật trên Facebook ({msg_2fa}). Lưu tài khoản Live không 2FA (KO BỊA 2FA).'})
            except Exception as e:
                emit('warning', {'message': f'[2FA] Lỗi kích hoạt 2FA: {e}'})

        result = RegistrationResult(
            success=True,
            status="live",
            uid=uid,
            identifier=new_email,
            email=new_email,
            password=pwd,
            token=token_val,
            two_factor_secret=twofa_secret,
            cookies=fresh_cookies,
            cookie_string=fresh_cookie_str,
            email_password=mail_pass,
            email_raw=mail_raw,
            email_rest=mail_rest,
            elapsed_seconds=elapsed,
            metadata={
                "live_verified": True,
                "vr_verified": True,
                "live_check": live_msg,
                "verified_nvr": True,
                "otp_code": otp_code,
                "reg_mode": task_input.extra.get("reg_mode", "verify_nvr"),
                "verify_mode": task_input.extra.get("legacy_verify_mode", "email"),
            },
        )

        # Xóa hotmail đã dùng khỏi kho nếu dùng hotmail
        remove_hotmail(new_email)

        skip_file_save = task_input.extra.get("skip_auto_file_save", False)
        if not skip_file_save:
            save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
            if twofa_secret and "2FA" not in str(save_fmt).upper():
                if "PASS|" in str(save_fmt).upper():
                    save_fmt = str(save_fmt).replace("PASS|", "PASS|2FA|")
                elif "PASSWORD|" in str(save_fmt).upper():
                    save_fmt = str(save_fmt).replace("PASSWORD|", "PASSWORD|2FA|")
                else:
                    save_fmt = f"{save_fmt}|2FA"
            record_line = result.format_line(save_fmt)
            uid_val = str(result.uid or "").strip()

            # Write to accounts_live.txt with deduplication
            try:
                already_in_live = False
                if os.path.exists("accounts_live.txt") and uid_val and uid_val != "N/A":
                    with open("accounts_live.txt", "r", encoding="utf-8-sig", errors="ignore") as f_r:
                        already_in_live = any(
                            l.strip().startswith(uid_val + "|") or f"c_user={uid_val}" in l for l in f_r
                        )
                if not already_in_live:
                    with open("accounts_live.txt", "a", encoding="utf-8-sig") as f_out:
                        f_out.write(record_line + "\n")
            except Exception:
                pass

            # Write or update accounts.txt (replace NVR record with verified LIVE record)
            try:
                if os.path.exists("accounts.txt") and uid_val and uid_val != "N/A":
                    with open("accounts.txt", "r", encoding="utf-8-sig", errors="ignore") as f_acc:
                        acc_lines = f_acc.readlines()
                    updated = False
                    new_lines = []
                    for l in acc_lines:
                        l_clean = l.strip()
                        if l_clean and (l_clean.startswith(uid_val + "|") or f"c_user={uid_val}" in l_clean):
                            if not updated:
                                new_lines.append(record_line + "\n")
                                updated = True
                        else:
                            new_lines.append(l)
                    if not updated:
                        new_lines.append(record_line + "\n")
                    with open("accounts.txt", "w", encoding="utf-8-sig") as f_acc:
                        f_acc.writelines(new_lines)
                else:
                    with open("accounts.txt", "a", encoding="utf-8-sig") as f_acc:
                        f_acc.write(record_line + "\n")
            except Exception:
                pass

            # Remove from accounts_unverified.txt
            if uid_val and uid_val != "N/A" and os.path.exists("accounts_unverified.txt"):
                try:
                    with open("accounts_unverified.txt", "r", encoding="utf-8-sig", errors="ignore") as f_un:
                        un_lines = f_un.readlines()
                    filtered = [l for l in un_lines if not (l.strip().startswith(uid_val + "|") or f"c_user={uid_val}" in l)]
                    if len(filtered) < len(un_lines):
                        with open("accounts_unverified.txt", "w", encoding="utf-8-sig") as f_un:
                            f_un.writelines(filtered)
                except Exception:
                    pass

# Handled exclusively by GUI based on user checkbox (auto_ttc_pipeline)

        emit("success", {"result": result})
        return result
    finally:
        try:
            client.close()
        except Exception:
            pass
