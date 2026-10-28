# -*- coding: utf-8 -*-
"""
fb_reg_worker.py - Real Facebook Web Registration Flow (m.facebook.com)
Extracted and integrated from real request flow.
Supports multi-threading, proxy, phone number & email registration, and 2FA.
"""

import json
import time
import random
import re
import os
import sys
import uuid
import threading
from typing import Optional, Dict, Any, List
from faker import Faker

from ui.colors import GREEN, RED, WHITE, YELLOW, ORANGE, CYAN, RESET, BOLD
from core.number_manager import remove_number, get_next_number, load_numbers
from core.proxy_manager import format_proxy_for_requests
from core.session_builder import create_http_session, build_request_context, setup_session_cookies, get_random_device_profile
from core.password_manager import generate_random_password
# top-level get_email_provider
from core.path_manager import get_output_filepaths
from ui.counter import RegistrationCounter

fake = Faker()
output_lock = threading.Lock()


# Save successful account credentials across all configured output paths (thread-safe)
def _save_success_output(record_line):
    with output_lock:
        for filepath in get_output_filepaths():
            try:
                os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
                with open(filepath, "a", encoding="utf-8-sig") as f:
                    f.write(record_line.strip() + "\n")
            except Exception:
                pass


# Vietnamese Names Pool fallback
HO_LIST = [
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",
    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Đoàn", "Lâm", "Mai",
    "Trịnh", "Đào", "Cao", "Hà", "Lưu", "Lương", "Thái", "Châu", "Tạ", "Phùng"
]
TEN_DEM_NAM = ["Quốc", "Văn", "Minh", "Đức", "Hoàng", "Gia", "Hải", "Tuấn", "Thanh", "Hữu", "Xuân", "Thành", "Bảo", "Đình", "Công", "Trọng"]
TEN_NAM = ["Huy", "Nam", "Phong", "Dũng", "Khánh", "Việt", "Anh", "Long", "Đạt", "Sơn", "Tùng", "Bảo", "Phát", "Thịnh", "Khoa", "Hiếu"]
TEN_DEM_NU = ["Thị", "Ngọc", "Thu", "Thanh", "Phương", "Kim", "Quỳnh", "Ánh", "Mỹ", "Mai", "Hồng", "Tuyết", "Bích", "Như"]
TEN_NU = ["Trang", "Linh", "Hương", "Lan", "Huyền", "Nhi", "Vy", "Thảo", "Hà", "Trâm", "Ngân", "Hoa", "Tuyết", "Mai", "Quỳnh"]


# Generate an identity with name, birthday, gender and password
def generate_identity(password_config=None, locale="vi_VN", name_type=None, custom_file="names.txt", mix_file_names=False):
    from core.name_manager import NameManager

    gender_val = 2 if random.random() < 0.50 else 1
    sex_value = str(gender_val)

    chosen_type = name_type
    if not chosen_type:
        loc = (locale or "").lower()
        if "vi" in loc:
            chosen_type = "vietnamese"
        elif "th" in loc:
            chosen_type = "thai"
        elif "zh" in loc or "cn" in loc:
            chosen_type = "chinese"
        elif "ko" in loc or "kr" in loc:
            chosen_type = "korean"
        elif "ja" in loc or "jp" in loc:
            chosen_type = "japanese"
        elif "hi" in loc or "in" in loc:
            chosen_type = "indian"
        elif "en" in loc or "us" in loc:
            chosen_type = "western"
        else:
            chosen_type = "vietnamese"

    gen_name = NameManager.generate_name(
        name_type=chosen_type,
        gender_val=gender_val,
        custom_file=custom_file,
        mix_file_names=mix_file_names,
    )

    current_year = 2026
    b_year = current_year - random.randint(20, 35)
    b_month = random.randint(1, 12)
    max_d = 28 if b_month == 2 else (30 if b_month in (4, 6, 9, 11) else 31)
    b_day = random.randint(1, max_d)

    # Determine password based on configuration
    if isinstance(password_config, dict) and password_config.get("type") == "fixed" and password_config.get("value"):
        password = password_config["value"]
    elif isinstance(password_config, str) and password_config:
        password = password_config
    else:
        password = generate_random_password()

    return {
        "first_name": gen_name.first_name,
        "last_name": gen_name.last_name,
        "full_name": gen_name.full_name,
        "sex_value": sex_value,
        "b_day": str(b_day),
        "b_month": str(b_month),
        "b_year": str(b_year),
        "password": password,
        "name_tag": gen_name.display_tag,
    }


# Extract first regex capture group from text, returns None if not found
def _search(pattern, text):
    if isinstance(pattern, list):
        for p in pattern:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None
    m = re.search(pattern, text)
    return m.group(1) if m else None


# Core worker - handles the full registration flow for a single phone number or email
def create_worker(wid, phone_number, proxy_data, config, counter):
    device_type = config.get("device_type", "mr_sxr")
    browser_type = config.get("browser_type", "Default")
    server = config.get("server", "m.facebook.com")
    password_config = config.get("password_config", None)

    proxy_dict = format_proxy_for_requests(proxy_data)
    locale = proxy_data.get("locale", "vi_VN") if isinstance(proxy_data, dict) else config.get("locale", "vi_VN")

    # If no phone number provided, fetch temporary email
    target_identity = phone_number
    active_mailbox = None
    email_provider = None

    if not target_identity or "@" in target_identity:
        try:
            # top-level get_email_provider
            prov_name = config.get("email_service", "mailtm")
            api_key = config.get("dongvanfb_api_key") or config.get("email_api_key")
            if "metaking" in str(prov_name).lower():
                api_key = config.get("metaking_api_key") or api_key
                srv_type = "phone" if "phone" in str(prov_name).lower() else config.get("metaking_service_type", "email")
                sid = 67 if srv_type == "phone" else 1
                email_provider = get_email_provider(
                    prov_name,
                    api_key=api_key,
                    service_type=srv_type,
                    server=config.get("metaking_server", 1),
                    domain=config.get("metaking_domain", "gmail.com"),
                    service_id=sid,
                    country_id=config.get("metaking_country_id", 154),
                    price=config.get("metaking_price", "low"),
                )
            else:
                email_provider = get_email_provider(prov_name, api_key=api_key, selected_domains=config.get("selected_custom_domains"))
            if not target_identity:
                try:
                    active_mailbox = email_provider.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None, worker_id=wid)
                except TypeError:
                    active_mailbox = email_provider.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None)
                if active_mailbox:
                    target_identity = active_mailbox.email
                    counter.update("info", number=str(wid), message=f"Đã tạo email ({prov_name}): {target_identity}", color=CYAN)
        except Exception:
            pass

    if not target_identity:
        counter.update("error", number=str(wid), message="No phone number or email available", color=RED)
        return {"success": False, "error": "Missing contact target"}

    try:
        profile = get_random_device_profile(device_type)
        session = create_http_session(device_type, proxy_dict, profile=profile)

        ctx = build_request_context(device_type, browser_type, locale, profile=profile)
        base_headers = ctx["base_headers"]

        # Step 1: GET registration page and extract hidden tokens (using clean browser UA to avoid 302 redirect)
        ua_browser = getattr(profile, "web_user_agent", "") or profile.user_agent
        get_headers = dict(base_headers)
        get_headers["user-agent"] = ua_browser
        resp_get_1 = session.get(f'https://{server}/reg?soft=hjk', headers=get_headers, timeout=20)
        setup_session_cookies(session, device_type, profile=profile)
        response_1 = getattr(resp_get_1, "text", "") or ""

        # Robust extraction for modern Facebook web registration
        lsd = _search([r'name="lsd" value="([^"]+)"', r'"LSD",\[\],\{"token":"([^"]+)"\}', r'"lsd"[:\s]+"([^"]+)"'], response_1)
        jazoest = _search([r'name="jazoest" value="([^"]+)"', r'"jazoest"[:\s]+"([^"]+)"'], response_1)
        if not jazoest and lsd:
            jazoest = f"2{sum(ord(c) for c in lsd)}"
        
        ccp = _search([r'name="ccp" value="([^"]+)"', r'"ccp"[:\s]+"([^"]+)"'], response_1) or "2"
        reg_instance = _search([r'name="reg_instance" value="([^"]+)"', r'"reg_instance"[:\s]+"([^"]+)"'], response_1)
        reg_impression_id = _search([r'name="reg_impression_id" value="([^"]+)"', r'"impressionId"[:\s]+"([^"]+)"'], response_1)
        ns_value = _search([r'name="ns" value="([^"]+)"', r'"ns"[:\s]+"([^"]+)"'], response_1) or "0"
        logger_id = _search([r'name="logger_id" value="([^"]+)"', r'"lid"[:\s]+"([^"]+)"'], response_1)
        encrypted_token = _search([r'"encrypted"\s*:\s*"([^"]+)"', r'"encrypted_token"[:\s]+"([^"]+)"'], response_1) or ""
        fb_dtsg = _search([r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', r'name="fb_dtsg" value="([^"]+)"', r'"fb_dtsg"[:\s]+"([^"]+)"'], response_1) or ""
        privacy_token = _search([r'privacy_mutation_token=([^&"\'\s]+)', r'"privacy_mutation_token"[:\s]+"([^"]+)"'], response_1) or ""

        # Legacy handshake fallback if modern view is redirected to /ig/login_via/app/
        is_android_or_sxr = getattr(profile, "os_name", "") == "Android" or any(k in str(device_type).lower() for k in ("android", "mr_sxr", "katana", "fb4a", "fb_app"))
        if not (reg_instance and privacy_token):
            if is_android_or_sxr:
                try:
                    for alt_url in [f'https://{server}/r.php?soft=hjk', f'https://mbasic.facebook.com/reg?soft=hjk']:
                        alt_resp = session.get(alt_url, headers=get_headers, timeout=15)
                        alt_txt = getattr(alt_resp, "text", "") or ""
                        lsd_alt = _search([r'name="lsd" value="([^"]+)"', r'"LSD",\[\],\{"token":"([^"]+)"\}', r'"lsd"[:\s]+"([^"]+)"'], alt_txt)
                        reg_inst_alt = _search([r'name="reg_instance" value="([^"]+)"', r'"reg_instance"[:\s]+"([^"]+)"'], alt_txt)
                        priv_alt = _search([r'privacy_mutation_token=([^&"\'\s]+)', r'"privacy_mutation_token"[:\s]+"([^"]+)"'], alt_txt)
                        if reg_inst_alt and priv_alt:
                            response_1 = alt_txt
                            lsd = lsd_alt or lsd
                            reg_instance = reg_inst_alt
                            privacy_token = priv_alt
                            ccp = _search([r'name="ccp" value="([^"]+)"', r'"ccp"[:\s]+"([^"]+)"'], alt_txt) or ccp
                            reg_impression_id = _search([r'name="reg_impression_id" value="([^"]+)"', r'"impressionId"[:\s]+"([^"]+)"'], alt_txt) or reg_impression_id
                            ns_value = _search([r'name="ns" value="([^"]+)"', r'"ns"[:\s]+"([^"]+)"'], alt_txt) or ns_value
                            logger_id = _search([r'name="logger_id" value="([^"]+)"', r'"lid"[:\s]+"([^"]+)"'], alt_txt) or logger_id
                            encrypted_token = _search([r'"encrypted"\s*:\s*"([^"]+)"', r'"encrypted_token"[:\s]+"([^"]+)"'], alt_txt) or encrypted_token
                            fb_dtsg = _search([r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', r'name="fb_dtsg" value="([^"]+)"', r'"fb_dtsg"[:\s]+"([^"]+)"'], alt_txt) or fb_dtsg
                            break
                except Exception:
                    pass
            else:
                try:
                    from core.session_builder import build_dynamic_kaios_profile
                    leg_p = build_dynamic_kaios_profile()
                    leg_c = build_request_context("kaios", profile=leg_p)
                    leg_resp = session.get(f'https://{server}/reg?soft=hjk', headers=leg_c["base_headers"], timeout=15)
                    leg_txt = getattr(leg_resp, "text", "") or ""
                    lsd_leg = _search([r'name="lsd" value="([^"]+)"', r'"LSD",\[\],\{"token":"([^"]+)"\}', r'"lsd"[:\s]+"([^"]+)"'], leg_txt)
                    reg_inst_leg = _search([r'name="reg_instance" value="([^"]+)"', r'"reg_instance"[:\s]+"([^"]+)"'], leg_txt)
                    priv_leg = _search([r'privacy_mutation_token=([^&"\'\s]+)', r'"privacy_mutation_token"[:\s]+"([^"]+)"'], leg_txt)
                    if reg_inst_leg and priv_leg:
                        response_1 = leg_txt
                        lsd = lsd_leg or lsd
                        reg_instance = reg_inst_leg
                        privacy_token = priv_leg
                        ccp = _search([r'name="ccp" value="([^"]+)"', r'"ccp"[:\s]+"([^"]+)"'], leg_txt) or ccp
                        reg_impression_id = _search([r'name="reg_impression_id" value="([^"]+)"', r'"impressionId"[:\s]+"([^"]+)"'], leg_txt) or reg_impression_id
                        ns_value = _search([r'name="ns" value="([^"]+)"', r'"ns"[:\s]+"([^"]+)"'], leg_txt) or ns_value
                        logger_id = _search([r'name="logger_id" value="([^"]+)"', r'"lid"[:\s]+"([^"]+)"'], leg_txt) or logger_id
                        encrypted_token = _search([r'"encrypted"\s*:\s*"([^"]+)"', r'"encrypted_token"[:\s]+"([^"]+)"'], leg_txt) or encrypted_token
                        fb_dtsg = _search([r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', r'name="fb_dtsg" value="([^"]+)"', r'"fb_dtsg"[:\s]+"([^"]+)"'], leg_txt) or fb_dtsg
                        base_headers["user-agent"] = leg_p.user_agent
                        base_headers.pop("sec-ch-ua", None)
                        base_headers.pop("sec-ch-ua-mobile", None)
                        base_headers.pop("sec-ch-ua-platform", None)
                except Exception:
                    pass

        if not reg_instance:
            reg_instance = str(uuid.uuid4())
        if not reg_impression_id:
            reg_impression_id = str(uuid.uuid4())
        if not logger_id:
            logger_id = str(uuid.uuid4())

        required = [lsd]
        if not all(required):
            counter.update("error", number=target_identity, message="Failed to Parse Tokens (Missing LSD)", color=ORANGE)
            return {"success": False, "error": "Failed to Parse LSD"}

        privacy_token = privacy_token.replace('%3D', '=')

        n_type = config.get("name_type") if isinstance(config, dict) else None
        c_file = config.get("custom_name_file", "names.txt") if isinstance(config, dict) else "names.txt"
        m_names = config.get("mix_file_names", False) if isinstance(config, dict) else False
        identity = generate_identity(password_config, locale, name_type=n_type, custom_file=c_file, mix_file_names=m_names)

        # Step 2: POST registration with extracted tokens and generated identity
        post_headers = dict(base_headers)
        post_headers.update({
            'user-agent': profile.user_agent,
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': f'https://{server}',
            'referer': f'https://{server}/reg?soft=hjk',
            'x-fb-lsd': lsd,
            'x-requested-with': 'XMLHttpRequest',
            'x-response-format': 'JSONStream',
            'x-asbd-id': '129477',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        })
        if getattr(profile, "model", None) and "kaios" not in str(profile.user_agent).lower():
            post_headers["sec-ch-ua-model"] = getattr(profile, "sec_ch_ua_model", f'"{profile.model}"') or f'"{profile.model}"'
        if getattr(profile, "os_version", None) and "kaios" not in str(profile.user_agent).lower():
            os_v = profile.os_version.split(".")[0] if "." in str(profile.os_version) else profile.os_version
            post_headers["sec-ch-ua-platform-version"] = getattr(profile, "sec_ch_ua_platform_version", f'"{os_v}.0.0"') or f'"{os_v}.0.0"'
        post_headers.pop('upgrade-insecure-requests', None)
        post_headers.pop('sec-fetch-user', None)

        params = {
            'privacy_mutation_token': privacy_token,
            'multi_step_form': '1',
            'skip_suma': '0',
            'shouldForceMTouch': '1',
        }

        raw_target_id = str(target_identity).strip()
        if "@" not in raw_target_id:
            if raw_target_id.startswith("+0"):
                clean_target_id = raw_target_id[1:]
            elif raw_target_id.startswith("+"):
                clean_target_id = raw_target_id
            elif raw_target_id.startswith("0"):
                clean_target_id = raw_target_id
            else:
                clean_target_id = f"+{raw_target_id}" if len(raw_target_id) >= 8 else raw_target_id
        else:
            clean_target_id = raw_target_id

        from core.email_service import get_random_comet_telemetry
        _telemetry = get_random_comet_telemetry()
        data = {
            'ccp': ccp,
            'reg_instance': reg_instance,
            'submission_request': 'true',
            'helper': '',
            'reg_impression_id': reg_impression_id,
            'ns': ns_value,
            'zero_header_af_client': '',
            'app_id': '',
            'logger_id': logger_id,
            'field_names[0]': 'firstname',
            'firstname': identity["first_name"],
            'lastname': identity["last_name"],
            'field_names[1]': 'birthday_wrapper',
            'birthday_day': identity["b_day"],
            'birthday_month': identity["b_month"],
            'birthday_year': identity["b_year"],
            'age_step_input': '',
            'did_use_age': 'false',
            'field_names[2]': 'reg_email__',
            'reg_email__': clean_target_id,
            'field_names[3]': 'sex',
            'sex': identity["sex_value"],
            'preferred_pronoun': '',
            'custom_gender': '',
            'field_names[4]': 'reg_passwd__',
            'name_suggest_elig': 'false',
            'was_shown_name_suggestions': 'false',
            'did_use_suggested_name': 'false',
            'use_custom_gender': 'false',
            'guid': '',
            'pre_form_step': '',
            'encpass': f'#PWD_BROWSER:0:{int(time.time())}:{identity["password"]}',
            'fb_dtsg': fb_dtsg,
            'jazoest': jazoest,
            'lsd': lsd,
            '__dyn': _telemetry.get('__dyn', '1Z3pawlEnwm8_Bg9ppoW5UdE4a2i5U4e0C86u7E39x60zU3ex608ewk9E4W0pKq0FE6S0x81vohw73wGwcq1GwqU2YwbK0oi0zE1jU1soG0hi0Lo6-0Co1kU1UU3jwGwbu'),
            '__csr': _telemetry.get('__csr', ''),
            '__hsdp': _telemetry.get('__hsdp', ''),
            '__hblp': _telemetry.get('__hblp', ''),
            '__sjsp': _telemetry.get('__sjsp', ''),
            '__req': _telemetry.get('__req', random.choice(['1', '2', '3', 'a', 'b', 'c', 'r', 'm'])),
            '__fmt': '1',
            '__a': encrypted_token,
            '__user': '0',
        }

        response_2 = session.post(f'https://{server}/reg/submit/', params=params, headers=post_headers, data=data, timeout=25)

        cookies = response_2.cookies.get_dict()
        response_text = response_2.text
        name = f"{identity['first_name']} {identity['last_name']}"

        # Step 3: Đợi OTP và gửi xác minh email thật lên Facebook
        ok_confirm = False
        confirm_text = ""
        if active_mailbox and email_provider:
            counter.update("info", number=target_identity, message=f"Đang chờ mã OTP gửi về {target_identity}...", color=CYAN)
            otp_timeout = int(config.get("otp_timeout", 20))
            otp_res = email_provider.wait_for_otp(active_mailbox, timeout_seconds=otp_timeout, proxy=proxy_dict.get("http") if proxy_dict else None)
            is_otp_ok = getattr(otp_res, "success", False)
            otp_code = getattr(otp_res, "otp_code", "") or ""
            conf_link = getattr(otp_res, "confirmation_link", None)
            res_meta = getattr(otp_res, "metadata", None)
            if not conf_link and res_meta and isinstance(res_meta, dict):
                conf_link = res_meta.get("confirmation_link")

            if is_otp_ok and (otp_code or conf_link):
                counter.update("success", number=target_identity, message=f"Bắt được mã OTP: {otp_code}! Đang gửi xác minh Facebook...", color=GREEN)
                from core.email_service import submit_facebook_web_email_otp
                cur_uid = cookies.get("c_user", "")
                ok_confirm, confirm_text = submit_facebook_web_email_otp(
                    session=session,
                    server=server,
                    otp_code=otp_code,
                    headers=post_headers,
                    confirmation_link=conf_link,
                    email=target_identity,
                    fb_dtsg=fb_dtsg,
                    lsd=lsd,
                    uid=cur_uid,
                )
                cookies = session.cookies.get_dict() if hasattr(session, "cookies") and hasattr(session.cookies, "get_dict") else getattr(session, "cookies", cookies)
                if ok_confirm:
                    if "@" in str(target_identity):
                        from core.email_service import remove_hotmail
                        remove_hotmail(str(target_identity))
                    counter.update("success", number=target_identity, message="Xác thực OTP Email thành công! Đã xóa khỏi danh sách hotmail.", color=GREEN)
            else:
                otp_err = getattr(otp_res, "error", None) or "Hết thời gian chờ"
                counter.update("error", number=target_identity, message=f"Hết thời gian chờ OTP ({otp_err})", color=ORANGE)

        # Multi-email retry loop for worker.py if confirmation is stuck
        retry_on_nvr = bool(config.get("retry_on_nvr_with_new_mail", True)) if isinstance(config, dict) else True
        max_email_retries = int(config.get("max_otp_email_retries", 5)) if isinstance(config, dict) else 5
        retry_use_free = bool(config.get("retry_use_free_mail", False)) if isinstance(config, dict) else False
        free_prov_name = str(config.get("fallback_email_service", "tempmail_plus")).lower().strip() if isinstance(config, dict) else "tempmail_plus"

        if not ok_confirm and cookies and any(k in cookies for k in ("c_user", "xs")) and retry_on_nvr and max_email_retries > 0:
            from core.registration_service import bind_facebook_session_email
            # top-level get_email_provider
            counter.update("info", number=target_identity, message="Đang đổi email mới để tiếp tục xác minh...", color=CYAN)
            for retry_idx in range(1, max_email_retries + 1):
                if ok_confirm:
                    break
                target_service = str(config.get("retry_email_service") or config.get("email_service") or "10minutemail").lower().strip()
                cur_prov = get_email_provider(target_service)
                new_box = None
                try:
                    try:
                        new_box = cur_prov.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None, worker_id=wid)
                    except TypeError:
                        new_box = cur_prov.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None)
                except Exception:
                    pass
                if not new_box:
                    cur_prov = email_provider
                    try:
                        try:
                            new_box = cur_prov.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None, worker_id=wid)
                        except TypeError:
                            new_box = cur_prov.create_mailbox(proxy=proxy_dict.get("http") if proxy_dict else None)
                    except Exception:
                        pass
                if not new_box or not getattr(new_box, "email", None):
                    continue

                new_em = new_box.email
                w_uid = cookies.get("c_user") if isinstance(cookies, dict) else None
                bind_ok = bind_facebook_session_email(
                    client=session,
                    server=server,
                    new_email=new_em,
                    base_headers=post_headers,
                    fb_dtsg=fb_dtsg,
                    jazoest=jazoest,
                    reg_instance=reg_instance,
                    timeout=10,
                    uid=w_uid,
                )
                if not bind_ok:
                    continue

                target_identity = new_em
                active_mailbox = new_box
                email_provider = cur_prov

                counter.update("info", number=target_identity, message=f"[Thử {retry_idx}/{max_email_retries}] Chờ OTP gửi về {target_identity}...", color=CYAN)
                otp_res = email_provider.wait_for_otp(active_mailbox, timeout_seconds=otp_timeout, proxy=proxy_dict.get("http") if proxy_dict else None)
                if not getattr(otp_res, "success", False):
                    try:
                        session.get(f"https://{server}/confirmemail.php?resend=1", headers=post_headers, timeout=8)
                        time.sleep(2.0)
                        otp_res = email_provider.wait_for_otp(active_mailbox, timeout_seconds=min(15, otp_timeout), proxy=proxy_dict.get("http") if proxy_dict else None)
                    except Exception:
                        pass
                if getattr(otp_res, "success", False) and getattr(otp_res, "otp_code", None):
                    otp_code = otp_res.otp_code
                    ok_confirm, confirm_text = submit_facebook_web_email_otp(
                        session=session,
                        server=server,
                        otp_code=otp_code,
                        headers=post_headers,
                        email=target_identity,
                        fb_dtsg=fb_dtsg,
                        lsd=lsd,
                        uid=cookies.get("c_user", ""),
                    )
                    if ok_confirm:
                        from core.facebook_checker import check_registration_account_live
                        c_st, c_msg = check_registration_account_live(session, server=server, uid=cookies.get("c_user", ""))
                        if c_st == 'die':
                            ok_confirm = False
                            break
                        else:
                            ok_confirm = True
                            counter.update('success', number=target_identity, message=f'Xác thực OTP Email mới {target_identity} thành công! Tài khoản LIVE!', color=GREEN)
                            break

        # Check for auth cookies and verified OTP (Strict VR OTP)
        if cookies and any(k in cookies for k in ("c_user", "xs")):
            if not ok_confirm:
                if active_mailbox and email_provider and hasattr(email_provider, "release_account"):
                    email_provider.release_account(active_mailbox.email)
                uid = cookies.get("c_user", "")
                counter.update(
                    "failed", number=target_identity,
                    message=f"Bỏ qua UID {uid} do chưa xác minh OTP thành công (VR OTP bắt buộc)!",
                    color=YELLOW,
                )
                return {"success": False, "error": "Chưa hoàn tất VR OTP"}
            uid = cookies.get("c_user", "")
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            counter.update(
                "success", number=target_identity,
                message=f" Name : {name} | Birthday : {identity['b_day']}/{identity['b_month']}/{identity['b_year']} \n [SxR-NV] {uid} | {identity['password']} | {cookie_str}",
                color=GREEN,
            )
            if "@" in str(target_identity):
                from core.email_service import remove_hotmail
                remove_hotmail(str(target_identity))
            else:
                remove_number(target_identity)

            # Auto 2FA TOTP activation if configured (THẬT trên Facebook)
            totp_secret = ""
            if config.get("enable_2fa", True):
                try:
                    from core.two_factor_service import enable_facebook_2fa
                    ok_2fa, sec_2fa, otp_2fa, msg_2fa = enable_facebook_2fa(
                        client=client,
                        uid=uid,
                        password=identity.get("password", ""),
                        server=server,
                        fb_dtsg=None,
                        lsd=None,
                    )
                    if ok_2fa and sec_2fa:
                        totp_secret = sec_2fa
                        logger.info(f"[W{worker_id}] Kích hoạt 2FA TOTP THẬT thành công! Secret: {sec_2fa} (OTP: {otp_2fa})")
                    else:
                        logger.warning(f"[W{worker_id}] Không kích hoạt được 2FA thật ({msg_2fa}). Lưu tài khoản không 2FA.")
                except Exception as e:
                    logger.warning(f"[W{worker_id}] Lỗi kích hoạt 2FA: {e}")

            # Save successful account credentials to output files
            mail_rest = ""
            if active_mailbox:
                m_meta = getattr(active_mailbox, "metadata", {}) or {}
                m_raw = m_meta.get("raw_line") or ""
                if m_raw and "|" in m_raw:
                    mail_rest = m_raw.split("|", 1)[1]
                else:
                    m_parts = []
                    if getattr(active_mailbox, "password", ""):
                        m_parts.append(str(active_mailbox.password))
                    for k in ("refresh_token", "client_id", "rec_email", "rec_pwd"):
                        v = m_meta.get(k)
                        if v:
                            m_parts.append(str(v))
                    mail_rest = "|".join(m_parts)

            save_format = config.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
            if save_format == "UID|PASS|2FA|COOKIE|TOKEN|EMAIL":
                record_line = f"{uid}|{identity['password']}|{totp_secret}|{cookie_str}||{target_identity}"
                if mail_rest:
                    record_line = f"{record_line}|{mail_rest}"
            else:
                record_line = f"{uid}|{identity['password']}|{cookie_str}"
                if mail_rest:
                    record_line = f"{record_line}|{target_identity}|{mail_rest}"

            _save_success_output(record_line)
            return {"success": True, "uid": uid, "password": identity["password"], "cookies": cookies, "cookie": cookie_str, "2fa": totp_secret}

        else:
            # Parse error response for debugging
            debug_msg = "Unknown Error"
            try:
                err_data = json.loads(response_text.split("for (;;);")[1]) if "for (;;);" in response_text else json.loads(response_text)
                debug_msg = str(err_data)[:150]
            except Exception:
                debug_msg = response_text.replace('\n', ' ')[:300]

            counter.update(
                "failed", number=target_identity,
                message=f"Failed | Debug: {debug_msg}...",
                color=YELLOW,
            )
            return {"success": False, "debug": debug_msg, "response": response_text}

    except Exception as e:
        if active_mailbox and email_provider and hasattr(email_provider, "release_account"):
            try:
                email_provider.release_account(active_mailbox.email)
            except Exception:
                pass
        err = str(e)
        if "proxy" in err.lower():
            counter.update("error", number=target_identity, message="Proxy Error", color=RED)
        elif "timeout" in err.lower() or "timed out" in err.lower():
            counter.update("error", number=target_identity, message="Timeout", color=RED)
        else:
            counter.update("error", number=target_identity, message=err[:50], color=RED)
        return {"success": False, "error": err}


def main():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    else:
        config = {
            "threads": 4,
            "max_accounts": 20,
            "enable_2fa": True,
            "email_service": "mailtm",
            "server": "m.facebook.com",
            "output_file": "accounts.txt",
        }

    threads_count = int(config.get("threads", 4))
    max_acc = int(config.get("max_accounts", 20))
    counter = RegistrationCounter()
    proxy_list = config.get("proxy_list", [])

    print(f"[*] Starting FB Web Registration Worker Pool")
    print(f"[*] Threads: {threads_count} | Target: {max_acc} accounts")
    print(f"[*] Server: {config.get('server', 'm.facebook.com')}\n" + "-" * 60)

    target_type = config.get("target_type", "email")
    if target_type == "phone":
        phone_file = config.get("phone_file", "numbers.txt")
        load_numbers(phone_file)

    stop_event = threading.Event()

    def worker_loop(wid):
        while not stop_event.is_set():
            if counter.success_count >= max_acc:
                stop_event.set()
                break
            
            p_data = random.choice(proxy_list) if proxy_list else None
            p_num = None
            if target_type == "phone":
                p_num = get_next_number()
                if not p_num:
                    print(f"[-] [W{wid}] Out of phone numbers in numbers.txt.")
                    break

            create_worker(wid, p_num, p_data, config, counter)
            time.sleep(random.uniform(0.5, 1.5))

    threads = []
    for wid in range(1, threads_count + 1):
        t = threading.Thread(target=worker_loop, args=(wid,), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(0.3)

    try:
        while not stop_event.is_set() and any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[-] Stopped by user.")
        stop_event.set()

    stats = counter.get_stats()
    print("\n" + "=" * 60)
    print(f"[+] Done: Success: {stats['success']} | Failed: {stats['failed']} | Error: {stats['error']}")

if __name__ == "__main__":
    main()
