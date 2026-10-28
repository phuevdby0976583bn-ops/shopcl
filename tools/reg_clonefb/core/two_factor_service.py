# -*- coding: utf-8 -*-
import re
import json
import time
import logging
from typing import Dict, Any, Optional, Tuple, Callable
import pyotp

logger = logging.getLogger(__name__)

DESKTOP_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
)


def _extract_token(pattern: str, text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(pattern, text)
    return m.group(1) if m else None


def _calc_jazoest(token: str) -> str:
    if not token:
        return "2957"
    return f"2{sum(ord(c) for c in token)}"


def _clean_secret_key(raw_secret: str) -> str:
    """Loai bo khoang trang va chuan hoa Base32 RFC 3548."""
    if not raw_secret:
        return ""
    clean = re.sub(r'[^A-Za-z2-7]', '', raw_secret).upper()
    return clean


def _is_valid_base32_secret(raw_secret: str) -> bool:
    """Kiem tra xem chuoi co phai la Base32 TOTP Secret Key hop le (RFC 3548 / RFC 6238)."""
    if not raw_secret:
        return False
    clean = _clean_secret_key(raw_secret)
    if len(clean) < 16 or len(clean) > 64:
        return False
    # Valid Base32 unpadded lengths mod 8 cannot have remainder 1, 3, 6
    if len(clean) % 8 in (1, 3, 6):
        return False
    try:
        import base64
        missing_padding = (8 - len(clean) % 8) % 8
        padded = clean + ("=" * missing_padding)
        decoded = base64.b32decode(padded, casefold=True)
        return len(decoded) >= 10
    except Exception:
        return False


def _extract_secret_from_payload(payload_text: str) -> Optional[str]:
    """Tim Secret Key Base32 that tu phan hoi JSON, GraphQL hoac HTML cua Facebook."""
    if not payload_text:
        return None

    import urllib.parse
    texts_to_check = [payload_text]
    try:
        unq = urllib.parse.unquote(payload_text)
        if unq != payload_text:
            texts_to_check.append(unq)
    except Exception:
        pass

    for txt in texts_to_check:
        # 1. URI otpauth: otpauth://totp/...secret=XXXX
        for m_uri in re.finditer(r"otpauth://totp/[^\s?&\"\x27]+\?(?:[^\s?&\"\x27]+&)*secret=([A-Za-z0-9]+)", txt, re.I):
            cand = _clean_secret_key(m_uri.group(1))
            if _is_valid_base32_secret(cand):
                return cand

        # 2. Cac truong JSON / GraphQL / HTML (TUYET DOI khong dung bare 'key' vi trung voi React JSON key)
        patterns = [
            r'"(?:secret_key|totp_secret|manual_entry_key|qr_secret|setup_token|two_factor_secret_key)":\s*"([^"]+)"',
            r'"(?:secret_key|totp_secret|manual_entry_key|qr_secret|setup_token|two_factor_secret_key)":\s*"([^"]+)"',
            r'"secret":\s*"([A-Za-z2-7\s]{16,64})"',
            r'"secret":\s*"([A-Za-z2-7\s]{16,64})"',
            r'name="(?:secret_key|secret)"\s+value="([^"]+)"',
            r'data-secret="([^"]+)"',
            r'<code[^>]*>([A-Za-z2-7\s]{16,64})</code>',
            r'<strong[^>]*>([A-Za-z2-7\s]{16,64})</strong>',
            r'class="[^"]*(?:secret|totp)[^"]*"[^>]*>([A-Za-z2-7\s]{16,64})<',
            r'(?:khóa bí mật|mã bí mật|secret key|manual key)[:\s]+([A-Za-z2-7\s]{16,64})',
        ]
        for pat in patterns:
            for m in re.finditer(pat, txt, re.I):
                candidate = _clean_secret_key(m.group(1))
                if _is_valid_base32_secret(candidate):
                    return candidate

    return None


def _is_fb_verify_success(resp_status: int, resp_text: str, resp_url: str = "") -> Tuple[bool, str]:
    """
    Tham dinh nghiem ngat ket qua xac nhan OTP 2FA tu Facebook.
    Tuyet doi khong doan mo - phai co tin hieu thanh cong thuc te tu Meta (KO BIA).
    """
    if resp_status not in (200, 302):
        return False, f"HTTP status khong hop le ({resp_status})"

    text_lower = (resp_text or "").lower()
    url_lower = (resp_url or "").lower()

    # 1. Chuyen huong Checkpoint thuc te (URL bi redirect toi 282 / block)
    if any(bad in url_lower for bad in ("/checkpoint/block/", "checkpoint/disabled", "help/103873106370583")):
        return False, f"Bi chuyen huong Checkpoint 282 ({resp_url})"

    # 2. Chuyen huong hoan tat 2FA
    if any(k in url_lower for k in ("recovery_codes", "/security/2fac/", "two_factor")):
        return True, "Chuyen huong thanh cong sang trang hoan tat 2FA"

    # 3. Kiem tra JSON Payload thuc te tu Facebook AJAX
    clean_json = resp_text.split("for (;;);")[1] if "for (;;);" in resp_text else resp_text
    try:
        data = json.loads(clean_json.strip())
        if isinstance(data, dict):
            if data.get("error") or data.get("error_summary") or data.get("error_description"):
                err_msg = data.get("error_description") or data.get("error_summary") or data.get("error")
                return False, f"Facebook bao loi: {err_msg}"
            payload = data.get("payload")
            if isinstance(payload, dict):
                if payload.get("success") is True or payload.get("is_valid") is True or payload.get("two_factor_auth_enabled") is True or payload.get("recovery_codes"):
                    return True, "Facebook xac nhan 2FA thanh cong (payload.success)"
                for act in payload.get("actions", []):
                    if isinstance(act, dict) and act.get("cmd") == "redirect":
                        uri = act.get("uri", "").lower()
                        if "checkpoint" not in uri or "two_factor" in uri or "2fac" in uri:
                            return True, f"Facebook chuyen huong hoan tat: {uri}"
    except Exception:
        pass

    # 4. Tin hieu thanh cong chuoi van ban
    success_indicators = [
        '"success":true',
        '"is_valid":true',
        '"is_successful":true',
        '"two_factor_auth_enabled":true',
        '"recovery_codes"',
        '"backup_codes"',
        'recovery_codes',
        'backup_codes',
        '/security/2fac/setup/recovery_codes/',
    ]
    for si in success_indicators:
        if si in text_lower:
            if not any(e in text_lower for e in ("error_summary", "error_description", "mã không hợp lệ", "invalid verification code")):
                return True, f"Facebook xac nhan thanh cong ({si})"

    # 5. Loi xac thuc ro rang
    explicit_errors = [
        "error_summary",
        "error_description",
        "mã không hợp lệ",
        "mã bạn đã nhập không khớp",
        "invalid verification code",
        "action_blocked",
        "bạn tạm thời bị chặn",
        "security_check",
    ]
    for ee in explicit_errors:
        if ee in text_lower:
            return False, f"Facebook bao loi: {ee}"

    if '"payload":' in text_lower and '"error":' not in text_lower and '"error_summary"' not in text_lower:
        if any(k in text_lower for k in ("actions", "next", "recovery_codes", "two_factor")):
            return True, "Payload phan hoi hop le khong chua loi"

    return False, "Khong tim thay bang chung xac nhan thanh cong tu Facebook"


def enable_facebook_2fa(
    client: Any,
    uid: str,
    password: str = "",
    cookies: Optional[Dict[str, str]] = None,
    server: str = "www.facebook.com",
    fb_dtsg: Optional[str] = None,
    lsd: Optional[str] = None,
    logger_instance: Optional[logging.Logger] = None,
    emit: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    timeout: int = 25,
) -> Tuple[bool, str, str, str]:
    """
    Kich hoat 2FA TOTP (Authenticator App) THAT 100% tren tai khoan Facebook LIVE.
    Tuan thu tuyet doi: Chi xac nhan thanh cong khi Facebook thuc su cap Secret va chap nhan ma TOTP (KO BIA).

    Returns:
        (success: bool, secret_key: str, current_otp: str, message: str)
    """
    log = logger_instance or logger
    _emit = emit or (lambda event, data: None)

    # Dong bo cookie hien tai
    cur_cookies: Dict[str, str] = {}
    if hasattr(client, "get_cookies"):
        try:
            cur_cookies = client.get_cookies() or {}
        except Exception:
            pass
    elif hasattr(client, "cookies"):
        try:
            cur_cookies = client.cookies.get_dict() if hasattr(client.cookies, "get_dict") else dict(client.cookies)
        except Exception:
            pass

    if cookies:
        cur_cookies.update(cookies)
        if hasattr(client, "set_cookie"):
            for ck, cv in cookies.items():
                try:
                    client.set_cookie(ck, cv, domain=".facebook.com")
                except Exception:
                    pass

    cur_uid = uid or cur_cookies.get("c_user", "")
    _emit("info", {"message": f"[2FA] Bắt đầu kích hoạt 2FA TOTP THẬT cho UID: {cur_uid}..."})
    log.info(f"[2FA] Bat dau kich hoat 2FA TOTP that cho UID: {cur_uid}")

    if not cur_cookies or not any(k in cur_cookies for k in ("c_user", "xs")):
        msg = "Thiếu cookies đăng nhập hợp lệ (c_user/xs) để bật 2FA"
        _emit("warning", {"message": f"[2FA] {msg}"})
        return False, "", "", msg

    raw_ua = getattr(client, "user_agent", "")
    active_ua = raw_ua if isinstance(raw_ua, str) and raw_ua else MOBILE_UA
    active_lang = "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7"
    if hasattr(client, "headers") and isinstance(client.headers, dict):
        active_ua = client.headers.get("user-agent") or client.headers.get("User-Agent") or active_ua
        active_lang = client.headers.get("accept-language") or client.headers.get("Accept-Language") or active_lang

    desktop_headers = {
        "User-Agent": active_ua if active_ua else DESKTOP_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": active_lang,
        "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    mobile_headers = {
        "User-Agent": active_ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": active_lang,
        "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
    }

    from core.email_service import is_chromium_ua, clean_client_hints
    if not is_chromium_ua(active_ua):
        clean_client_hints(mobile_headers, active_ua)
        clean_client_hints(desktop_headers, active_ua)

    # =========================================================================
    # BUOC 1: LAY TOKEN BAO MAT PHIEN DANG NHAP THAT (fb_dtsg, jazoest, lsd)
    # =========================================================================
    _emit("step", {"step": "2fa_1", "name": "Thu thập token bảo mật Facebook phiên đăng nhập...", "target": cur_uid})
    cur_fb_dtsg = fb_dtsg or ""
    cur_lsd = lsd or ""
    reauth_done = False

    # 1.1 Uu tien trich xuat qua extract_facebook_comet_tokens tu core.email_service neu chua co
    if not cur_fb_dtsg or not cur_lsd:
        try:
            from core.email_service import extract_facebook_comet_tokens
            c_toks = extract_facebook_comet_tokens(client, server="www.facebook.com", timeout=timeout)
            if c_toks.get("dtsg") and not cur_fb_dtsg:
                cur_fb_dtsg = c_toks["dtsg"]
            if c_toks.get("lsd") and not cur_lsd:
                cur_lsd = c_toks["lsd"]
        except Exception as ex_tok:
            log.debug(f"[2FA] extract_facebook_comet_tokens fallback: {ex_tok}")

    # 1.2 Tham do trang 2FA thuc te cua phien dang nhap
    probe_targets = [
        "https://www.facebook.com/security/2fac/setup/intro/",
        f"https://{server}/security/2fac/setup/intro/",
        "https://m.facebook.com/security/2fac/setup/intro/",
        "https://mbasic.facebook.com/security/2fac/setup/intro/",
        "https://www.facebook.com/",
        f"https://{server}/",
        "https://accountscenter.facebook.com/password_and_security/two_factor",
    ]

    for probe_url in probe_targets:
        if cur_fb_dtsg and cur_lsd:
            break
        try:
            hdrs_to_use = desktop_headers if ("www." in probe_url or "accountscenter." in probe_url) else mobile_headers
            r_probe = client.get(probe_url, headers=hdrs_to_use, timeout=timeout)
            p_text = getattr(r_probe, "text", "")
            p_url = getattr(r_probe, "url", "")

            if not cur_fb_dtsg:
                cur_fb_dtsg = (
                    _extract_token(r'"tokenName":"fb_dtsg","token":"([^"]+)"', p_text)
                    or _extract_token(r'"dtsg":\{"token":"([^"]+)"', p_text)
                    or _extract_token(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"\}', p_text)
                    or _extract_token(r'"DTSGInitData",\[\],\{"token":"([^"]+)"\}', p_text)
                    or _extract_token(r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', p_text)
                    or _extract_token(r'name="fb_dtsg"\s+value="([^"]+)"', p_text)
                    or _extract_token(r'value="([^"]+)"\s+name="fb_dtsg"', p_text)
                    or _extract_token(r'"async_get_token":"([^"]+)"', p_text)
                    or _extract_token(r'"token":"([A-Za-z0-9_-]{20,})"', p_text)
                    or ""
                )

            if not cur_lsd:
                cur_lsd = (
                    _extract_token(r'"LSD",\[\],\{"token":"([^"]+)"\}', p_text)
                    or _extract_token(r'name="lsd"\s+value="([^"]+)"', p_text)
                    or _extract_token(r'"token":"([A-Za-z0-9_-]{10,20})"', p_text)
                    or ""
                )

            # Xu ly Re-authentication neu Facebook yeu cau xac nhan lai mat khau
            if password and not reauth_done and ("reauth" in p_url or "/login/reauth.php" in p_text or "SecuredActionReauthDialog" in p_text or "XSecuredAction" in p_text):
                reauth_done = True
                _emit("info", {"message": "[2FA] Facebook yêu cầu xác nhận mật khẩu (Reauth). Đang gửi mật khẩu..."})
                log.info("[2FA] Phat hien yeu cau Reauth mat khau, dang xac nhan...")
                reauth_jaz = _calc_jazoest(cur_fb_dtsg) if cur_fb_dtsg else "2957"
                reauth_payload = {
                    "pass": password,
                    "password": password,
                    "fb_dtsg": cur_fb_dtsg,
                    "jazoest": reauth_jaz,
                    "save": "1",
                    "next": probe_url,
                }
                reauth_hdrs = dict(hdrs_to_use)
                reauth_hdrs["Content-Type"] = "application/x-www-form-urlencoded"
                reauth_url = "https://www.facebook.com/login/reauth.php" if "www." in probe_url else f"https://{server}/login/reauth.php"
                r_re = client.post(reauth_url, data=reauth_payload, headers=reauth_hdrs, timeout=timeout)
                re_text = getattr(r_re, "text", "")
                fresh_dtsg = _extract_token(r'name="fb_dtsg"\s+value="([^"]+)"', re_text) or _extract_token(r'"token":"([^"]+)"', re_text)
                if fresh_dtsg:
                    cur_fb_dtsg = fresh_dtsg
        except Exception as e:
            log.debug(f"[2FA] Loi probe token tai {probe_url}: {e}")

    # Neu van chua co fb_dtsg tu probe, dung fb_dtsg duoc truyen vao neu co
    if not cur_fb_dtsg and fb_dtsg:
        cur_fb_dtsg = fb_dtsg
    if not cur_lsd and lsd:
        cur_lsd = lsd

    cur_jazoest = _calc_jazoest(cur_fb_dtsg)

    # =========================================================================
    # BUOC 2: YEU CAU MAY CHU FACEBOOK SINH SECRET KEY TOTP THAT (DA KENH)
    # =========================================================================
    _emit("step", {"step": "2fa_2", "name": "Gửi yêu cầu Facebook sinh mã bí mật TOTP...", "target": cur_uid})
    log.info("[2FA] Dang yeu cau may chu Facebook tao 2FA Secret Key...")

    found_secret: Optional[str] = None
    gen_resp_text = ""

    # Kenh 1: Desktop Web AJAX Endpoint (Uu tien so 1: www.facebook.com on dinh nhat cho 2FA)
    try:
        d_gen_headers = {
            "User-Agent": active_ua if active_ua else DESKTOP_UA,
            "Accept": "*/*",
            "Accept-Language": active_lang,
            "Origin": "https://www.facebook.com",
            "Referer": "https://www.facebook.com/security/2fac/setup/intro/",
            "X-Requested-With": "XMLHttpRequest",
            "X-ASBD-ID": "359341",
            "Content-Type": "application/x-www-form-urlencoded",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not A(Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
        }
        r_d_gen = client.post(
            "https://www.facebook.com/security/2fac/setup/qrcode/generate/",
            data={"__a": "1", "fb_dtsg": cur_fb_dtsg, "jazoest": cur_jazoest, "lsd": cur_lsd},
            headers=d_gen_headers,
            timeout=timeout,
        )
        d_resp_text = getattr(r_d_gen, "text", "")
        gen_resp_text = d_resp_text
        found_secret = _extract_secret_from_payload(d_resp_text)
        if found_secret:
            log.info(f"[2FA] Bat thanh cong Secret Key tu Kenh 1 (Desktop AJAX): {found_secret[:6]}...")
    except Exception as e:
        log.debug(f"[2FA] Kenh 1 Desktop loi: {e}")

    # Kenh 2: Mobile Web AJAX Endpoint
    if not found_secret:
        try:
            target_host = server if "m." in server else "m.facebook.com"
            m_gen_headers = {
                "User-Agent": active_ua,
                "Accept": "*/*",
                "Accept-Language": active_lang,
                "Origin": f"https://{target_host}",
                "Referer": f"https://{target_host}/security/2fac/setup/intro/",
                "X-Requested-With": "XMLHttpRequest",
                "X-ASBD-ID": "129477",
                "Content-Type": "application/x-www-form-urlencoded",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"Android"',
            }
            r_m_gen = client.post(
                f"https://{target_host}/security/2fac/setup/qrcode/generate/",
                data={"__a": "1", "fb_dtsg": cur_fb_dtsg, "jazoest": cur_jazoest, "lsd": cur_lsd},
                headers=m_gen_headers,
                timeout=timeout,
            )
            m_resp_text = getattr(r_m_gen, "text", "")
            if not gen_resp_text:
                gen_resp_text = m_resp_text
            found_secret = _extract_secret_from_payload(m_resp_text)
            if found_secret:
                log.info(f"[2FA] Bat thanh cong Secret Key tu Kenh 2 (Mobile AJAX): {found_secret[:6]}...")
        except Exception as e:
            log.debug(f"[2FA] Kenh 2 Mobile loi: {e}")

    # Kenh 3: GET truc tiep trang setup de boc tach ma nhung
    if not found_secret:
        for s_url, s_hdrs in [
            ("https://www.facebook.com/security/2fac/setup/intro/", desktop_headers),
            ("https://www.facebook.com/security/2fac/setup/", desktop_headers),
            (f"https://{server}/security/2fac/setup/intro/", mobile_headers),
            (f"https://{server}/security/2fac/setup/", mobile_headers),
            ("https://mbasic.facebook.com/security/2fac/setup/intro/", mobile_headers),
        ]:
            if found_secret:
                break
            try:
                r_s = client.get(s_url, headers=s_hdrs, timeout=timeout)
                s_txt = getattr(r_s, "text", "")
                found_secret = _extract_secret_from_payload(s_txt)
                if found_secret:
                    log.info(f"[2FA] Bat thanh cong Secret Key tu Kenh 3 (GET {s_url}): {found_secret[:6]}...")
            except Exception as e:
                log.debug(f"[2FA] Kenh 3 loi tai {s_url}: {e}")

    # Kenh 4: Meta Accounts Center GraphQL Mutation
    if not found_secret:
        gql_doc_ids = ["6724398117621429", "7183204781711200", "6649231845151528"]
        for doc_id in gql_doc_ids:
            if found_secret:
                break
            try:
                gql_headers = {
                    "User-Agent": active_ua or DESKTOP_UA,
                    "Accept-Language": active_lang,
                    "Origin": "https://accountscenter.facebook.com",
                    "Referer": "https://accountscenter.facebook.com/password_and_security/two_factor",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-ASBD-ID": "359341",
                    "X-FB-Friendly-Name": "FXAccountsCenterTwoFactorGenerateSecretKeyMutation",
                }
                gql_payload = {
                    "fb_dtsg": cur_fb_dtsg,
                    "jazoest": cur_jazoest,
                    "variables": json.dumps({"input": {"account_id": cur_uid, "client_mutation_id": "1"}}),
                    "doc_id": doc_id,
                }
                r_gql = client.post("https://www.facebook.com/api/graphql/", data=gql_payload, headers=gql_headers, timeout=timeout)
                found_secret = _extract_secret_from_payload(getattr(r_gql, "text", ""))
                if found_secret:
                    log.info(f"[2FA] Bat thanh cong Secret Key tu Kenh 4 (GraphQL doc_id {doc_id}): {found_secret[:6]}...")
            except Exception as e:
                log.debug(f"[2FA] Kenh 4 doc_id {doc_id} loi: {e}")

    # Tham dinh Secret Key: KHONG DUOC BIA! Neu Facebook khong cap -> bao that bai
    if not found_secret or len(found_secret) < 16:
        err_hint = "Facebook không cấp Secret Key"
        if "checkpoint" in gen_resp_text.lower():
            err_hint = "Tài khoản dính checkpoint khi mở trang 2FA"
        elif "error" in gen_resp_text.lower():
            err_hint = "Facebook từ chối tạo mã (giới hạn tần suất hoặc kiểm duyệt IP)"
        msg = f"Không lấy được Secret Key thật từ Facebook ({err_hint})"
        _emit("warning", {"message": f"[2FA] {msg}"})
        log.warning(f"[2FA] {msg}")
        return False, "", "", msg

    _emit("info", {"message": f"[2FA] Đã nhận Secret Key THẬT từ Facebook: {found_secret}"})
    log.info(f"[2FA] Nhan thanh cong Secret Key THAT: {found_secret}")

    # =========================================================================
    # BUOC 3: TINH TOAN MA TOTP 6 CHU SO THOI GIAN THUC (RFC 6238)
    # =========================================================================
    missing_pad = (8 - len(found_secret) % 8) % 8
    padded_secret = found_secret + ("=" * missing_pad)
    try:
        totp = pyotp.TOTP(padded_secret)
        current_otp = totp.now()
    except Exception as e:
        log.warning(f"[2FA] Khong the sinh ma OTP tu Secret ({e})")
        return False, "", "", f"Loi sinh ma OTP tu Secret Key: {e}"
    _emit("step", {"step": "2fa_3", "name": f"Tính mã xác thực ({current_otp}) từ Secret Facebook...", "target": cur_uid})
    log.info(f"[2FA] Sinh ma TOTP xac thuc: {current_otp}")

    time.sleep(0.8)

    # =========================================================================
    # BUOC 4: GUI MA TOTP XAC NHAN LEN FACEBOOK DE KICH HOAT THAT (KO BIA)
    # =========================================================================
    _emit("step", {"step": "2fa_4", "name": f"Gửi mã OTP '{current_otp}' xác nhận kích hoạt 2FA với Facebook...", "target": cur_uid})
    log.info(f"[2FA] Dang gui ma OTP '{current_otp}' xac nhan len Facebook...")

    verify_success = False
    verify_msg = ""

    confirm_endpoints = [
        "https://www.facebook.com/security/2fac/setup/qrcode/verify/",
        "https://www.facebook.com/security/2fac/setup/totp/confirm/",
        "https://www.facebook.com/security/2fac/setup/confirm/",
        f"https://{server}/security/2fac/setup/qrcode/verify/",
        f"https://{server}/security/2fac/setup/totp/confirm/",
        f"https://{server}/security/2fac/setup/confirm/",
        "https://m.facebook.com/security/2fac/setup/qrcode/verify/",
        "https://m.facebook.com/security/2fac/setup/totp/confirm/",
        "https://mbasic.facebook.com/security/2fac/setup/totp/confirm/",
        "https://mbasic.facebook.com/security/2fac/setup/confirm/",
    ]

    # Ho tro bu sai lech dong ho (clock drift): Thu ma hien tai, ma -30s, ma +30s
    codes_to_try = [current_otp]
    try:
        now_ts = time.time()
        prev_code = totp.at(now_ts - 30)
        next_code = totp.at(now_ts + 30)
        if prev_code != current_otp:
            codes_to_try.append(prev_code)
        if next_code != current_otp:
            codes_to_try.append(next_code)
    except Exception:
        pass

    for attempt_code in codes_to_try:
        if verify_success:
            break
        for c_url in confirm_endpoints:
            if verify_success:
                break
            try:
                is_desktop_ep = "www." in c_url
                origin_domain = "https://www.facebook.com" if is_desktop_ep else f"https://{server}"
                c_headers = {
                    "User-Agent": active_ua or DESKTOP_UA,
                    "Accept": "*/*",
                    "Accept-Language": active_lang,
                    "Origin": origin_domain,
                    "Referer": f"{origin_domain}/security/2fac/setup/intro/",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-ASBD-ID": "359341" if is_desktop_ep else "129477",
                    "Content-Type": "application/x-www-form-urlencoded",
                }
                if is_desktop_ep:
                    c_headers["sec-ch-ua"] = '"Chromium";v="124", "Google Chrome";v="124", "Not A(Brand";v="99"'
                    c_headers["sec-ch-ua-mobile"] = "?0"
                    c_headers["sec-ch-ua-platform"] = '"Windows"'
                else:
                    c_headers["sec-ch-ua-mobile"] = "?1"
                    c_headers["sec-ch-ua-platform"] = '"Android"'

                c_data = {
                    "__a": "1",
                    "fb_dtsg": cur_fb_dtsg,
                    "jazoest": cur_jazoest,
                    "code": attempt_code,
                    "secret": found_secret,
                    "secret_key": found_secret,
                }
                if cur_lsd:
                    c_data["lsd"] = cur_lsd
                r_conf = client.post(c_url, data=c_data, headers=c_headers, timeout=timeout)
                c_text = getattr(r_conf, "text", "")
                c_status = getattr(r_conf, "status_code", 200)
                c_final_url = getattr(r_conf, "url", "")

                ok_sig, sig_msg = _is_fb_verify_success(c_status, c_text, c_final_url)
                if ok_sig:
                    verify_success = True
                    verify_msg = f"Thành công qua {c_url} ({sig_msg})"
                    log.info(f"[2FA] {verify_msg}")
                    break
                else:
                    verify_msg = sig_msg
            except Exception as e:
                log.debug(f"[2FA] Xac thuc tai {c_url} gap loi: {e}")

    # Kenh GraphQL Accounts Center Mutation neu REST endpoints chua confirm
    if not verify_success:
        try:
            ver_gql_payload = {
                "fb_dtsg": cur_fb_dtsg,
                "jazoest": cur_jazoest,
                "variables": json.dumps({
                    "input": {
                        "account_id": cur_uid,
                        "verification_code": current_otp,
                        "client_mutation_id": "2"
                    }
                }),
                "doc_id": "6724398117621430",
            }
            ver_headers = {
                "User-Agent": active_ua or DESKTOP_UA,
                "Accept-Language": active_lang,
                "Origin": "https://accountscenter.facebook.com",
                "Referer": "https://accountscenter.facebook.com/password_and_security/two_factor",
                "Content-Type": "application/x-www-form-urlencoded",
                "X-ASBD-ID": "359341",
            }
            r_ver_gql = client.post("https://www.facebook.com/api/graphql/", data=ver_gql_payload, headers=ver_headers, timeout=timeout)
            v_text = getattr(r_ver_gql, "text", "")
            v_status = getattr(r_ver_gql, "status_code", 200)
            ok_gql, gql_msg = _is_fb_verify_success(v_status, v_text)
            if ok_gql:
                verify_success = True
                verify_msg = f"Thành công qua GraphQL Accounts Center ({gql_msg})"
            else:
                verify_msg = gql_msg
        except Exception as e:
            log.debug(f"[2FA] Kenh GraphQL verify loi: {e}")

    # =========================================================================
    # BUOC 5: KIEM DINH CUOI CUNG VA KET QUA THUC TE (TUYET DOI KO BIA)
    # =========================================================================
    if not verify_success:
        # NEU FACEBOOK KHONG XAC NHAN -> BAO THAT BAI, KHONG TRA KEY GIA!
        fail_msg = f"Facebook từ chối xác thực mã OTP 2FA ({verify_msg})"
        _emit("warning", {"message": f"[2FA] {fail_msg}"})
        log.warning(f"[2FA] {fail_msg}")
        return False, "", "", fail_msg

    final_msg = f"KÍCH HOẠT 2FA TOTP THẬT THÀNH CÔNG! Secret: {found_secret}"
    _emit("info", {"message": f"[2FA] {final_msg}"})
    log.info(f"[2FA] Hoan tat: {final_msg}")
    return True, found_secret, current_otp, final_msg
