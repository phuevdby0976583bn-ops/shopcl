# -*- coding: utf-8 -*-
"""
core.ios_bloks_engine
Native iOS GraphQL Bloks CAA Registration Engine extracted from regfb.py.
Preserves 100% of core Bloks/CAA/Pando/Tigon technology from regfb.py:
- Device profiling: UUIDv4, sid, nid, cloud_trust_token, machine_id, aac.
- Official Tigon/Liger + Pando headers + iOS OAuth bearer.
- Dynamic iOS Safari / FBAN / FBIOS User-Agent.
- 7 Bloks registration stages:
  1. com.bloks.www.bloks.caa.reg.name.async
  2. com.bloks.www.bloks.caa.reg.birthday.async
  3. com.bloks.www.bloks.caa.reg.gender.async
  4. com.bloks.www.bloks.caa.reg.async.contactpoint_phone.async OR contactpoint_email.async
  5. com.bloks.www.bloks.caa.reg.password.async
  6. com.bloks.www.bloks.caa.reg.create.account.async -> Extracts UID and iOS access token (EAAAAY...)
  7. com.bloks.www.bloks.caa.reg.confirmation.async -> Submits OTP code
- Token extraction: Android Token EAAAAU & session cookies via https://b-graph.facebook.com/auth/login.
- Integrated with tool settings:
  * Bait phone (mồi SĐT ảo) matching proxy country code.
  * Bait gmail (mồi Gmail ảo).
  * Direct email (không mồi).
  * Proxy from settings (ProxyItem, string, dict). Fails safe to protect real IP.
  * OTP verification via tool settings (Mail ảo, Hotmail, Metaking, 1smail, Otptrust...).
"""

import sys
import os
import time
import re
import json
import uuid
import random
import datetime
import html as _html
import logging
from typing import Optional, Dict, Any, Tuple, Union, Callable

import requests
import urllib3

from core.models import RegistrationInput, RegistrationResult, ProxyItem
from core.email_service import (
    get_email_provider,
    EmailAccount,
    OTPVerificationResult,
    add_facebook_confirmation_contactpoint,
    submit_facebook_web_email_otp,
    generate_bait_gmail_identifier,
)
from core.facebook_checker import check_registration_account_live, check_facebook_uid_live, extract_facebook_uid, check_facebook_account_live_status
from core.geo_manager import GeoTelephonyResolver, normalize_country_code
from core.registration_service import _format_e164_phone, generate_mno_carrier_phone, bind_facebook_session_email

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger("ios_bloks_engine")

URL_10MIN_ADDRESS = 'https://10minutemail.net/address.api.php'
URL_10MIN_MAIL = 'https://10minutemail.net/mail.api.php'
HEADERS_10MIN = {
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'x-requested-with': 'XMLHttpRequest',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'referer': 'https://10minutemail.net/m/?lang=vi'
}

def get_10min_email(proxies: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    """Khởi tạo hòm thư 10MinuteMail chuẩn 100% từ regfb.py."""
    session = requests.Session()
    params = {'new': '1', '_': int(time.time() * 1000)}
    # Thử qua proxy trước (nếu có), fallback sang direct nếu proxy chậm/lỗi
    proxy_attempts = [proxies, None] if proxies else [None]
    for cur_p in proxy_attempts:
        try:
            r = session.get(URL_10MIN_ADDRESS, headers=HEADERS_10MIN, params=params, proxies=cur_p, timeout=10)
            if r.status_code == 200:
                data = r.json()
                email = data.get('mail_get_mail')
                if email:
                    return {'email': email.strip(), 'session': session, 'type': '10min'}
        except Exception as e:
            logger.debug(f"Lỗi tạo 10MinuteMail (proxy={bool(cur_p)}): {e}")
    return None

def get_10min_otp(session: requests.Session, timeout_sec: int = 90, proxies: Optional[dict] = None) -> Optional[str]:
    """Lắng nghe và tự động trích xuất OTP từ hòm thư 10MinuteMail chuẩn 100% từ regfb.py."""
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            params = {'_': int(time.time() * 1000)}
            r = None
            try:
                r = session.get(URL_10MIN_ADDRESS, headers=HEADERS_10MIN, params=params, timeout=8)
            except Exception:
                if proxies:
                    try:
                        r = session.get(URL_10MIN_ADDRESS, headers=HEADERS_10MIN, params=params, proxies=proxies, timeout=8)
                    except Exception:
                        pass

            if r and r.status_code == 200:
                data = r.json()
                mail_list = data.get('mail_list', [])
                for item in mail_list:
                    mail_id = item.get('mail_id', '')
                    if mail_id == 'welcome':
                        continue
                    subject = item.get('subject', '')
                    match = re.search(r'\b(\d{5,8})\b', subject)
                    if match:
                        return match.group(1)
                    try:
                        r_content = None
                        try:
                            r_content = session.get(URL_10MIN_MAIL, headers=HEADERS_10MIN, params={'mailid': mail_id, '_': int(time.time() * 1000)}, timeout=8)
                        except Exception:
                            if proxies:
                                try:
                                    r_content = session.get(URL_10MIN_MAIL, headers=HEADERS_10MIN, params={'mailid': mail_id, '_': int(time.time() * 1000)}, proxies=proxies, timeout=8)
                                except Exception:
                                    pass

                        if r_content and r_content.status_code == 200:
                            content_data = r_content.json()
                            body = content_data.get('plain') or content_data.get('html') or ''
                            c_match = re.search(r'FB-(\d{5,8})', body, re.I) or re.search(r'\b(\d{5,6})\b', body)
                            if c_match:
                                return c_match.group(1)
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(2)
    return None

GLOBAL_DEVICE_ID = '60DC365D-F964-4224-BD99-71D7259558E6'
GLOBAL_FAMILY_DEVICE_ID = '8f81379b-d587-4465-ae08-ae549d9f8c8f'
GLOBAL_MACHINE_ID = 'YAvmaQtOfBJFJBcqpXveKZ9g'
GLOBAL_WATERFALL_ID = 'bac03ebd268241e99fa00151141b4230'
GLOBAL_CLOUD_TRUST_TOKEN = '8252B111-5428-483D-8996-28A96D07DD579D2668CF-88D0-453D-B871-5D954FD059E0'
GLOBAL_AAC = '{"aac_init_timestamp":1790210000,"aacjid":"Q7jiDQG-coQCrATZCPNA3ZW5srq2bf7HKXXr1FTlIBj-8wGzkK7mS5RN335_vg7MGFEzbXAPA5OBfxIX9kb7KID-ab4UcCOR9pGwBv_qb1pzYxhJ8Mze8tUKwTbOiHYoqhHSoqEtg75jlBVgP2yPEBlA_HpO0Ue_jsKGIiow2G9YdKNZ06lZS_uO5muUQTfADV1JAtXRb5f8GsT7KRayoC2BF8rKLLEmOMhGxZsrqvEfjCwScdLKpwi4BFCTnpJU"}'
CLEAN_PWD_WILDE = '#PWD_WILDE:2:1790210764:AR2ZjAAC2MkJio6zDXsAAW0dJPNJHlKk74FY8Wqljgr0+FFsWpPMI5rl/c6g/CEREiay7H9sBgavn21al+bLYm2rm0VLviqXG//qccfdU29wLCsoriGK6+j1DZzg5WkWBiXuxh6SdfKiatFmExBd/8Voetimbx75uNnzzqJMaBl5QxdJCTEUkqyTel4MXhkPmI2cHLRtj/AtXj0H9JUhz1OslFs77aaI3XwDJ2er6L2viVmcASk15G5plYeRHVTiYoCINEJ5qwbQf5WbZUDsTSGGk2nyvIw5yCAB0nA7vhybwaLgR9OkINI+wPHrUtbWR1WFeYJ5UPjrHIqKUaTvmiiaqWT9kApVkrzzuABAjHRR2Qd39Xy2E2wxR9pSAgx656YrA5iAVOUa'

VIETNAMESE_FIRST_NAMES = [
    'Quang', 'Huy', 'Anh', 'Minh', 'Tuan', 'Dung', 'Nam', 'Thang', 'Duc', 'Hoang',
    'Long', 'Khoa', 'Phong', 'Thanh', 'Hieu', 'Linh', 'Trang', 'Huong', 'Ha', 'Phuong',
    'Mai', 'Ngoc', 'Lan', 'Vy', 'Yen'
]
VIETNAMESE_LAST_NAMES = [
    'Nguyen', 'Tran', 'Le', 'Pham', 'Hoang', 'Huynh', 'Phan', 'Vu', 'Vo', 'Dang',
    'Bui', 'Do', 'Ho', 'Ngo', 'Duong', 'Ly'
]

IOS_GRAPHQL_URL = 'https://graph.facebook.com/graphql'
IOS_USER_AGENT = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/21E219 [FBAN/FBIOS;FBAV/520.0.0.38.101;FBBV/756351453;FBDV/iPhone13,4;FBMD/iPhone;FBSN/iOS;FBSV/17.4;FBSS/3;FBID/phone;FBLC/vi_VN;FBOP/5;FBRV/0]'
IOS_APP_AUTH_HEADER = 'OAuth 6628568379|c1e620fa708a1d5696fb991c1bde5662'
BLOKS_VERSIONING_ID = '9f6640a4dfe5a7dbef8a547602beb113245c252866cda233a02a797683c2b120'
CLIENT_DOC_ID = '375801096012207349486705547963'

def generate_device_profile() -> Dict[str, str]:
    """Sinh định danh thiết bị iOS ảo ngẫu nhiên như trong regfb.py."""
    return {
        'device_id': str(uuid.uuid4()).upper(),
        'family_device_id': str(uuid.uuid4()),
        'waterfall_id': uuid.uuid4().hex,
        'flow_id': str(uuid.uuid4()),
        'cloud_token': '{}{}'.format(str(uuid.uuid4()).upper(), str(uuid.uuid4()).upper()[:16]),
        'sid': uuid.uuid4().hex,
        'nid': '{}{}'.format(uuid.uuid4().hex[:32], ',Wifi'),
    }

def create_nested_variables(app_id: str, client_inputs: dict, server_inputs: dict, dev: Optional[dict] = None) -> str:
    """Tạo biến mã hóa JSON lồng chuẩn Bloks/CAA của Facebook Mobile."""
    d = dev or {'device_id': GLOBAL_DEVICE_ID, 'waterfall_id': GLOBAL_WATERFALL_ID, 'cloud_token': GLOBAL_CLOUD_TRUST_TOKEN}
    client_inputs['machine_id'] = GLOBAL_MACHINE_ID
    client_inputs['aac'] = GLOBAL_AAC
    client_inputs['cloud_trust_token'] = d.get('cloud_token', GLOBAL_CLOUD_TRUST_TOKEN)
    server_inputs['machine_id'] = GLOBAL_MACHINE_ID
    server_inputs['device_id'] = d.get('device_id', GLOBAL_DEVICE_ID)
    server_inputs['waterfall_id'] = d.get('waterfall_id', GLOBAL_WATERFALL_ID)
    server_inputs['cloud_trust_token'] = d.get('cloud_token', GLOBAL_CLOUD_TRUST_TOKEN)
    inner_payload = {'client_input_params': client_inputs, 'server_params': server_inputs}
    middle_payload = {
        'params': json.dumps(inner_payload),
        'bloks_versioning_id': BLOKS_VERSIONING_ID,
        'app_id': app_id,
    }
    variables = {
        'generic_attachment_tall_cover_image_width': 1164,
        'generic_attachment_small_cover_image_height': 120,
        'params': middle_payload,
        'formatType': 'concise',
        'include_workplace_fields': 'false',
        'device': 'iphone',
        'generic_attachment_tall_cover_image_height': 612,
        'generic_attachment_tall_cover_image_width_no_scale': 388,
        'nt_context': {
            'bloks_version': BLOKS_VERSIONING_ID,
            'styles_id': 'a8f4a1c2a3aae6ce1e5ac6aee64fbb75',
            'pixel_ratio': 3,
            'theme_params': [{'design_system_name': 'FDS', 'value': ['BLUEPRINT_TEST_ROUNDED_CORNERS_NO_GUTTERS', 'DEFAULT']}],
        },
        'scale': 3,
        'should_include_delegate_page': True,
        'generic_attachment_small_cover_image_width': 120,
        'voiceover_enabled': 'false',
    }
    return json.dumps(variables)

def extract_reg_context(response_text: str, fallback_context: str) -> str:
    """Trích xuất reg_context (AX...) luân chuyển giữa các bước Bloks."""
    if not response_text:
        return fallback_context
    m = re.search(r'logged_out[^\w]*(AX[a-zA-Z0-9_\-\|]+?)(?:\\\\\\\\\\"|"|\')', response_text)
    if m:
        return m.group(1)
    m2 = re.search(r'reg_context\\"[^\w]*(AX[a-zA-Z0-9_\-\|]+?)(?:\\\\\\\\\\"|"|\')', response_text)
    if m2:
        return m2.group(1)
    matches = re.findall(r'(AX[a-zA-Z0-9_\-\|]{100,})', response_text)
    if matches:
        return max(matches, key=len)
    return fallback_context

def extract_session_cookies(session: requests.Session, extra_text: str = '') -> str:
    """Trích xuất toàn bộ cookies từ Session và JSON response payload chuẩn định dạng Facebook."""
    cookies = []
    try:
        for c in session.cookies:
            if c.name and c.value:
                cookies.append(f"{c.name}={c.value}")
    except Exception:
        pass
    if extra_text:
        matches = re.findall(r'"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]+)"', extra_text)
        for n, v in matches:
            cookies.append(f"{n}={v}")
        matches_rev = re.findall(r'"value"\s*:\s*"([^"]+)"\s*,\s*"name"\s*:\s*"([^"]+)"', extra_text)
        for v, n in matches_rev:
            cookies.append(f"{n}={v}")
    seen = {}
    for item in cookies:
        if '=' in item:
            k, v = item.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k and v:
                seen[k] = v
    if not seen:
        return ''
    prios = ['c_user', 'xs', 'fr', 'datr', 'sb', 'locale', 'm_pixel_ratio', 'dpr', 'wd', 'ps_l', 'ps_n']
    ordered = []
    for pk in prios:
        if pk in seen:
            ordered.append(f"{pk}={seen.pop(pk)}")
    for k, v in seen.items():
        ordered.append(f"{k}={v}")
    return '; '.join(ordered) + ';'

def get_token_eaaau_and_cookie(
    uid: str,
    password: str,
    email: Optional[str] = None,
    proxies: Optional[dict] = None,
    timeout: int = 15
) -> Tuple[Optional[str], str]:
    """
    Trích xuất token Android EAAAU và cookies phiên chuẩn đầy đủ (c_user, xs, fr, datr, sb)
    qua login Katana với chữ ký động MD5 (chuẩn 100% Meta FB4A).
    Thử đăng nhập bằng email trước, nếu không thành công fallback sang uid.
    """
    import hashlib
    url = 'https://b-graph.facebook.com/auth/login'
    secret = '62f8ce9f74b12f84c123cc23437a4a32'
    headers = {
        'user-agent': 'Dalvik/2.1.0 (Linux; U; Android 7.1.2; G011A Build/N2G48H) [FBAN/FB4A;FBAV/417.0.0.33.65;FBPN/com.facebook.katana;FBLC/en_US;FBBV/480086274;FBCR/Sprint;FBMF/google;FBBD/google;FBDV/G011A;FBSV/7.1.2;FBCA/x86:armeabi-v7a;FBDM/{density=1.5,width=720,height=1280};FB_FW/1;FBRV/0;]',
        'content-type': 'application/x-www-form-urlencoded',
    }

    login_candidates = []
    if uid and str(uid).strip():
        login_candidates.append(str(uid).strip())
    if email and str(email).strip() and str(email).strip() != str(uid):
        login_candidates.append(str(email).strip())

    proxy_options = [proxies]

    for login_id in login_candidates:
        timestamp = int(time.time())
        encrypted_password = f'#PWD_FB4A:0:{timestamp}:{password}'
        device_id = str(uuid.uuid4())
        ad_id = str(uuid.uuid4())

        base_data = {
            'adid': ad_id,
            'format': 'json',
            'device_id': device_id,
            'email': login_id,
            'openid_flow': 'android_login',
            'password': encrypted_password,
            'generate_analytics_claim': '1',
            'cpl': 'true',
            'family_device_id': device_id,
            'credentials_type': 'password',
            'generate_session_cookies': '1',
            'error_detail_type': 'button_with_disabled',
            'source': 'register_api',
            'locale': 'en_US',
            'client_country_code': 'US',
            'api_key': '882a8490361da98702bf97a021ddc14d',
            'access_token': '350685531728|62f8ce9f74b12f84c123cc23437a4a32',
        }
        sorted_items = sorted(base_data.items(), key=lambda x: x[0])
        sig_raw = ''.join(f'{k}={v}' for k, v in sorted_items) + secret
        base_data['sig'] = hashlib.md5(sig_raw.encode('utf-8')).hexdigest()

        for cur_proxy in proxy_options:
            try:
                r = requests.post(url, headers=headers, data=base_data, proxies=cur_proxy, timeout=timeout)
                rs = r.text or ''
                token_match = re.search(r'"access_token"\s*:\s*"(EAAAAU[^"]+)"', rs)
                token = token_match.group(1) if token_match else None
                c_dict = {}
                try:
                    js_auth = r.json()
                    if isinstance(js_auth, dict):
                        if not token and js_auth.get("access_token"):
                            token = str(js_auth.get("access_token"))
                        if "session_cookies" in js_auth and isinstance(js_auth["session_cookies"], list):
                            for sc in js_auth["session_cookies"]:
                                if isinstance(sc, dict) and sc.get("name") and sc.get("value"):
                                    c_dict[str(sc["name"])] = str(sc["value"])
                except Exception:
                    pass

                cookie_matches = re.findall(r'"name"\s*:\s*"([^"]+)"\s*,\s*"value"\s*:\s*"([^"]+)"', rs)
                if cookie_matches:
                    for n, v in cookie_matches:
                        if n not in c_dict:
                            c_dict[n] = v

                if c_dict:
                    if str(uid) and 'c_user' not in c_dict and 'xs' in c_dict:
                        c_dict['c_user'] = str(uid)
                    prios = ['c_user', 'xs', 'fr', 'datr', 'sb']
                    ordered = []
                    for pk in prios:
                        if pk in c_dict:
                            ordered.append(f'{pk}={c_dict.pop(pk)}')
                    for k, v in c_dict.items():
                        ordered.append(f'{k}={v}')
                    cookie_str = '; '.join(ordered) + ';'
                    return token, cookie_str
            except Exception:
                continue

    # 2. Fallback sang mbasic web login n?u Katana ch?a tr? v? full cookie (c_user/xs)
    try:
        m_s = requests.Session()
        if proxies:
            m_s.proxies.update(proxies)
        m_hdrs = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'accept-language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        r_init = m_s.get('https://mbasic.facebook.com/login.php', headers=m_hdrs, timeout=timeout)
        dtsg_m = re.search(r'name="fb_dtsg" value="([^"]+)"', r_init.text)
        jaz_m = re.search(r'name="jazoest" value="([^"]+)"', r_init.text)
        login_data = {
            'email': uid or email or '',
            'pass': password,
                    }
        if dtsg_m: login_data['fb_dtsg'] = dtsg_m.group(1)
        if jaz_m: login_data['jazoest'] = jaz_m.group(1)
        r_log = m_s.post('https://mbasic.facebook.com/login/device-based/regular/login/', data=login_data, headers=m_hdrs, timeout=timeout)
        mb_cookies = m_s.cookies.get_dict()
        if 'c_user' in mb_cookies or 'xs' in mb_cookies:
            if str(uid) and 'c_user' not in mb_cookies:
                mb_cookies['c_user'] = str(uid)
            prios = ['c_user', 'xs', 'fr', 'datr', 'sb']
            ordered = []
            for pk in prios:
                if pk in mb_cookies:
                    ordered.append(f'{pk}={mb_cookies.pop(pk)}')
            for k, v in mb_cookies.items():
                ordered.append(f'{k}={v}')
            cookie_str = '; '.join(ordered) + ';'
            return None, cookie_str
    except Exception as e_mb:
        logger.debug(f"mbasic fallback login exception: {e_mb}")

    return None, ''

def check_live_die(
    uid: str,
    proxies: Optional[dict] = None,
    token: Optional[str] = None,
    cookie_str: Optional[str] = None,
    fallback_name: Optional[str] = None
) -> Tuple[bool, Optional[str], str]:
    """
    Kiểm tra trạng thái Live / Die / Chưa xác minh (NVR) chuẩn xác 100%:
    - LIVE: Graph API /me trả về 200 HOẶC Cookie phiên vào được Home/Feed/mbasic bình thường.
    - DIE: Bị Checkpoint 282 / 1501092823525282 / UFAC / Khóa tài khoản / Hết phiên đăng nhập.
    - NVR: Đang ở màn hình xác minh OTP / Flow 828281030927956 / Dạng checkpoint khác (Chờ OTP).
    """
    if not uid or not str(uid).isdigit():
        return False, None, "die"

    real_name = fallback_name or "Facebook User"
    proxy_url = None
    if proxies and isinstance(proxies, dict):
        proxy_url = proxies.get("http") or proxies.get("https")

    # 1. Thẩm định trực tiếp qua Cookie phiên bằng check_facebook_account_live_status (ƯU TIÊN HÀNG ĐẦU)
    if cookie_str and ("c_user=" in cookie_str or "xs=" in cookie_str):
        try:
            from core.facebook_checker import check_facebook_account_live_status
            ck_st, ck_msg = check_facebook_account_live_status(
                cookie_str=cookie_str,
                uid=str(uid),
                proxy=proxy_url,
                timeout=6
            )
            if ck_st == "live":
                return True, real_name, "live"
            elif ck_st in ("die_282", "die", "session_expired"):
                return False, None, "die"
            elif ck_st == "nvr":
                return False, real_name, "nvr"
        except Exception:
            pass

    # 2. Thẩm định qua Token Graph API (nếu có access_token) kết hợp kiểm tra checkpoint
    if token and str(token).startswith("EAAAA"):
        try:
            r_me = requests.get(
                f"https://graph.facebook.com/me?access_token={token}&fields=id,name",
                proxies=proxies,
                timeout=6
            )
            if r_me.status_code == 200:
                data_me = r_me.json()
                if str(data_me.get("id")) == str(uid):
                    real_name = data_me.get("name") or real_name
                    try:
                        r_pic = requests.get(f"https://graph.facebook.com/{uid}/picture?redirect=false", proxies=proxies, timeout=5)
                        if r_pic.status_code == 200:
                            p_url = r_pic.json().get("data", {}).get("url", "")
                            if "static.xx" in p_url or "rsrc.php" in p_url:
                                return False, real_name, "nvr"
                    except Exception:
                        pass
                    return True, real_name, "live"
            elif r_me.status_code in (400, 401):
                err_text = r_me.text.lower()
                try:
                    js_err = r_me.json().get("error", {})
                    subcode = js_err.get("error_subcode")
                    code = js_err.get("code")
                    msg = str(js_err.get("message", "")).lower()
                    err_data_str = js_err.get("error_data", "")
                    flow_id = ""
                    if err_data_str:
                        import json as _j
                        err_data_obj = _j.loads(err_data_str) if isinstance(err_data_str, str) else err_data_str
                        flow_id = str(err_data_obj.get("checkpoint_flow_id", ""))

                    if flow_id == "1501092823525282" or any(k in err_text for k in ("checkpoint/block", "checkpoint/disabled", "checkpoint/suspended", "help/103873106370583", "suspended", "vô hiệu hóa", "180 days", "180 ngày", "1357053")):
                        return False, None, "die"
                    elif flow_id == "828281030927956" or subcode in (490, 491, 459, 405) or code in (459, 405) or "(#459)" in err_text or "checkpointed" in msg:
                        return False, real_name, "nvr"
                except Exception:
                    pass
        except Exception:
            pass

    # 3. Thẩm định qua UID tồn tại công khai
    try:
        from core.facebook_checker import check_facebook_uid_live
        w_live, w_msg = check_facebook_uid_live(str(uid), proxy=proxy_url, timeout=5)
        if not w_live and not any(k in (w_msg or "").lower() for k in ("silhouette", "placeholder")):
            return False, None, "die"
    except Exception:
        pass

    return False, real_name, "nvr"

def parse_proxy_to_dict(proxy_input: Any) -> Optional[Dict[str, str]]:
    """Chuyển đổi ProxyItem, string, hoặc dict sang dict requests {'http': ..., 'https': ...}."""
    if not proxy_input:
        return None
    if isinstance(proxy_input, dict):
        if "http" in proxy_input or "https" in proxy_input:
            return proxy_input
        host = proxy_input.get("host")
        port = proxy_input.get("port")
        if host and port:
            proto = proxy_input.get("protocol", "http")
            u = proxy_input.get("username")
            p = proxy_input.get("password")
            url = f"{proto}://{u}:{p}@{host}:{port}" if (u and p) else f"{proto}://{host}:{port}"
            return {"http": url, "https": url}
    if hasattr(proxy_input, "to_requests_dict"):
        try:
            return proxy_input.to_requests_dict()
        except Exception:
            pass
    if hasattr(proxy_input, "as_url"):
        try:
            u = proxy_input.as_url()
            return {"http": u, "https": u}
        except Exception:
            pass
    p = str(proxy_input or "").strip()
    if not p or p.lower() in ("direct", "none", "127.0.0.1"):
        return None
    scheme = 'http'
    if p.startswith('socks5://'):
        scheme = 'socks5'
        p = p[len('socks5://'):]
    elif p.startswith('http://'):
        scheme = 'http'
        p = p[len('http://'):]
    elif p.startswith('https://'):
        scheme = 'http'
        p = p[len('https://'):]
    if '@' in p:
        p_url = f'{scheme}://{p}'
        return {'http': p_url, 'https': p_url}
    parts = p.split(':')
    if len(parts) == 2:
        p_url = f'{scheme}://{parts[0]}:{parts[1]}'
        return {'http': p_url, 'https': p_url}
    elif len(parts) == 4:
        if parts[1].isdigit() and not parts[3].isdigit():
            ip, port, user, pwd = parts[0], parts[1], parts[2], parts[3]
        elif parts[3].isdigit() and not parts[1].isdigit():
            user, pwd, ip, port = parts[0], parts[1], parts[2], parts[3]
        else:
            ip, port, user, pwd = parts[0], parts[1], parts[2], parts[3]
        p_url = f'{scheme}://{user}:{pwd}@{ip}:{port}'
        return {'http': p_url, 'https': p_url}
    p_url = f'{scheme}://{p}'
    return {'http': p_url, 'https': p_url}

def run_ios_bloks_registration(
    task_input: RegistrationInput,
    emit_func: Optional[Callable[[str, dict], None]] = None,
    parent_service: Optional[Any] = None
) -> RegistrationResult:
    """
    Chạy luồng đăng ký tài khoản Facebook qua iOS Bloks Native CAA (theo regfb.py).
    Tích hợp hoàn hảo:
    - Mồi SĐT ảo / Gmail ảo / Đăng ký trực tiếp.
    - Proxy từ setting với cơ chế fail-safe hủy lượt an toàn (không lộ IP thật).
    - Xác minh OTP Email qua cấu hình setting (Metaking, Hotmail, Mail ảo, v.v.).
    - Kiểm tra Live/Die & trích xuất Tokens, Cookies chuẩn.
    """
    start_time = time.time()
    emit = emit_func or (lambda evt, data: None)
    wid = task_input.extra.get("worker_id", 1)

    # 1. Khởi tạo thiết bị iOS
    dev = generate_device_profile()
    emit("info", {"message": f"[Luồng {wid}] 🍏 Khởi động iOS Bloks Engine (Device ID: {dev['device_id'][:8]}...)"})

    # 2. Xử lý Proxy theo setting
    session = requests.Session()
    session.headers.update({'Accept-Encoding': 'gzip, deflate'})
    proxies = parse_proxy_to_dict(task_input.proxy)
    assigned_ip = task_input.extra.get("proxy_ip") or "Direct"

    if proxies:
        try:
            r_chk = session.get('https://graph.facebook.com', proxies=proxies, timeout=10)
            emit("info", {"message": f"[Luồng {wid}] [Proxy Live] Đang chạy qua Proxy: {task_input.proxy}"})
            session.proxies.update(proxies)
        except Exception as p_e:
            err_msg = f"Proxy Error: Request timed out after (20.0, 28.0)s: Failed to establish a new connection ({p_e})"
            emit("error", {"message": f"[Luồng {wid}] ❌ Lỗi Proxy ({p_e}). Hủy lượt an toàn để bảo vệ IP máy thật!"})
            return RegistrationResult(
                success=False,
                status="error",
                error_message=err_msg,
                elapsed_seconds=round(time.time() - start_time, 2),
                metadata={"proxy_error": True, "die": False, "reg_mode": "ios_bloks"}
            )
    else:
        emit("info", {"message": f"[Luồng {wid}] [*] Đang chạy trực tiếp (Không dùng Proxy)."})

    # 3. Chuẩn bị thông tin cá nhân & Giới tính
    first_name = (task_input.first_name or "").strip()
    last_name = (task_input.last_name or "").strip()
    if not first_name:
        first_name = random.choice(VIETNAMESE_FIRST_NAMES)
    if not last_name:
        last_name = random.choice(VIETNAMESE_LAST_NAMES)
    full_name = f"{last_name} {first_name}"

    gender_val = task_input.gender
    if gender_val in (1, "1", "female", "nu", "Nữ"):
        gender = 1
    elif gender_val in (2, "2", "male", "nam", "Nam"):
        gender = 2
    else:
        gender = random.choice([1, 2])

    password_to_save = task_input.password or task_input.extra.get("default_password") or "Facebook@2026"
    password_to_send = f"#PWD_FB4A:0:{int(time.time())}:{password_to_save}"

    # ??c c?u h?nh fallback t? config.json n?u task_input.extra thi?u th?ng tin
    cfg_data = {}
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r", encoding="utf-8") as f_cfg:
                cfg_data = json.load(f_cfg)
        except Exception:
            cfg_data = {}

    # 4. X?c ??nh Contact Point theo setting (M?i Gmail, M?i S?T, ho?c Email tr?c ti?p)
    raw_bm = task_input.extra.get("bait_mode")
    if raw_bm:
        bait_mode = str(raw_bm).lower().strip()
    elif task_input.extra.get("use_bait_gmail"):
        bait_mode = "gmail"
    elif task_input.extra.get("use_bait_phone") or task_input.extra.get("auto_gen_phone"):
        bait_mode = "phone"
    else:
        bait_mode = "none"

    if bait_mode not in ("phone", "gmail", "none"):
        bait_mode = "none"

    prov_name = task_input.extra.get("email_service") or cfg_data.get("email_service", "clean_trio")
    metaking_api_key = (
        task_input.extra.get("metaking_api_key")
        or cfg_data.get("metaking_api_key")
        or task_input.extra.get("email_api_key")
        or ""
    )
    api_key = (
        task_input.extra.get("dongvanfb_api_key")
        or cfg_data.get("dongvanfb_api_key")
        or metaking_api_key
        or task_input.extra.get("email_api_key")
        or ""
    )
    custom_doms = (
        task_input.extra.get("selected_domains")
        or task_input.extra.get("selected_custom_domains")
        or cfg_data.get("selected_domains")
    )
    allow_free_fallback = bool(
        task_input.extra.get("retry_use_free_mail", cfg_data.get("retry_use_free_mail", False))
    )

    email_prov = None

    def _allocate_mailbox(svc_name: str, allow_free_fallback: bool = allow_free_fallback):
        svc_low = str(svc_name or "").lower()
        # 1. N?u l? d?ch v? mail ?o 10MinuteMail / laoia.com:
        if any(k in svc_low for k in ["10min", "laoia", "mail ảo riêng", "@laoia.com", "laoia_domain", "mail_ao"]):
            try:
                m_10m = get_10min_email(proxies=proxies)
                if m_10m and m_10m.get("email"):
                    return m_10m, None, m_10m["email"]
            except Exception as e_10m:
                logger.warning(f"Error get_10min_email: {e_10m}")

        # 2. D?ch v? Email c? c?u h?nh (Metaking, Hotmail, Dongvanfb, Clean Trio, Auto Rotator...)
        try:
            nonlocal email_prov
            if "metaking" in svc_low:
                mk_key = task_input.extra.get("metaking_api_key") or cfg_data.get("metaking_api_key") or metaking_api_key
                mk_domain = "hotmail.com" if "hotmail" in svc_low else ("gmail.com" if "gmail" in svc_low else ("outlook.com" if "outlook" in svc_low else ("icloud.com" if "icloud" in svc_low else task_input.extra.get("metaking_domain", cfg_data.get("metaking_domain", "hotmail.com")))))
                email_prov = get_email_provider(
                    svc_name,
                    api_key=mk_key,
                    service_type=task_input.extra.get("metaking_service_type", cfg_data.get("metaking_service_type", "email")),
                    server=task_input.extra.get("metaking_server", cfg_data.get("metaking_server", 1)),
                    domain=mk_domain,
                    service_id=task_input.extra.get("metaking_service_id", cfg_data.get("metaking_service_id", 1)),
                    country_id=task_input.extra.get("metaking_country_id", cfg_data.get("metaking_country_id", 154)),
                    price=task_input.extra.get("metaking_price", cfg_data.get("metaking_price", "low")),
                )
            elif not email_prov or svc_name != prov_name:
                email_prov = get_email_provider(svc_name, api_key=api_key, selected_domains=custom_doms)

            dom_t = "hotmail.com" if "hotmail" in svc_low else ("gmail.com" if "gmail" in svc_low else task_input.extra.get("domain", cfg_data.get("domain")))
            mb = None
            try:
                mb = email_prov.create_mailbox(proxy=task_input.proxy, domain=dom_t, worker_id=wid)
            except TypeError:
                mb = email_prov.create_mailbox(proxy=task_input.proxy, domain=dom_t)

            if mb and getattr(mb, "email", None):
                return None, mb, mb.email
        except Exception as e_al:
            logger.warning(f"Error allocating mailbox for {svc_name}: {e_al}")

        # 3. Fallback an to?n sang 10MinuteMail (laoia.com) CH? KHI ng??i d?ng cho ph?p free fallback
        if allow_free_fallback:
            try:
                emit("warning", {"message": f"[Luồng {wid}] ⚠️ Dịch vụ {svc_name} chưa cấp được hòm thư ➔ Tự động fallback sang Mail ảo (10minutemail / laoia.com)..."})
                m_fb = get_10min_email(proxies=proxies)
                if m_fb and m_fb.get("email"):
                    return m_fb, None, m_fb["email"]
            except Exception as e_fb:
                logger.warning(f"Error in free mailbox fallback: {e_fb}")

        return None, None, None

    # Thi?t l?p Contact Point kh?i t?o theo ch? ?? m?i
    mail_10min_obj = None
    active_mailbox = None
    contact_point = ""
    is_phone = False

    if bait_mode == "gmail":
        is_phone = False
        contact_point = generate_bait_gmail_identifier(first_name=first_name, last_name=last_name)
        emit("info", {"message": f"[Luồng {wid}] [Mồi Gmail] Đã sinh Gmail ảo mồi: {contact_point}"})
        emit("step", {"step": 1, "name": f"Đăng ký bằng Mồi Gmail {contact_point}", "target": contact_point, "worker_id": wid})

    elif bait_mode == "phone":
        is_phone = True
        target_host = ""
        if task_input.proxy:
            p_str = task_input.proxy.as_url() if hasattr(task_input.proxy, "as_url") else str(task_input.proxy)
            if "://" in p_str:
                p_str = p_str.split("://", 1)[1]
            if "@" in p_str:
                p_str = p_str.split("@", 1)[1]
            target_host = p_str.split(":", 1)[0].strip()

        geo_prof = None
        c_code = "VN"
        if target_host and target_host not in ("127.0.0.1", "0.0.0.0", "direct", "none", ""):
            try:
                geo_prof = GeoTelephonyResolver.resolve_ip(target_host, proxy=task_input.proxy)
                if geo_prof and geo_prof.country_code:
                    c_code = normalize_country_code(geo_prof.country_code)
            except Exception:
                c_code = "VN"

        raw_phone = generate_mno_carrier_phone(geo_profile=geo_prof, country_code=c_code, ip=target_host, force_vn=False, force_fresh=True, e164=True)
        contact_point = raw_phone
        emit("info", {"message": f"[Luồng {wid}] [Mồi SĐT] Đã sinh SĐT mồi [{c_code}]: {contact_point}"})
        emit("step", {"step": 1, "name": f"Đăng ký bằng Mồi SĐT {contact_point}", "target": contact_point, "worker_id": wid})

    else:
        # bait_mode == "none": C?p h?m th? th?t ngay tr??c B??c 4 theo chu?n regfb.py
        is_phone = False
        emit("info", {"message": f"[Luồng {wid}] [*] Đang cấp phát hòm thư email ({prov_name}) cho Bước 4 theo chuẩn regfb.py..."})
        mail_10min_obj, active_mailbox, contact_point = _allocate_mailbox(prov_name, allow_free_fallback=allow_free_fallback)
        if not contact_point:
            err_msg = f"Không thể cấp phát hòm thư thật từ '{prov_name}' (Vui lòng kiểm tra API key, số dư hoặc mạng)"
            emit("error", {"message": f"[Luồng {wid}] ❌ {err_msg}. Dừng luồng an toàn!"})
            return RegistrationResult(
                success=False,
                status="failed",
                identifier="",
                error_message=err_msg,
                elapsed_seconds=round(time.time() - start_time, 2),
                metadata={"step": 4, "die": False, "reg_mode": "ios_bloks"}
            )
        emit("info", {"message": f"[Luồng {wid}] [Direct Mail] Đã cấp email đăng ký: {contact_point}"})
        emit("step", {"step": 1, "name": f"Đăng ký bằng Email {contact_point}", "target": contact_point, "worker_id": wid})
    # 5. Cấu hình Headers Tigon/Liger + Pando cho luồng iOS Bloks
    url = IOS_GRAPHQL_URL
    headers = {
        'x-fb-request-analytics-tags': '{"network_tags":{"product":"6628568379","purpose":"fetch","request_category":"graphql","retry_attempt":"0"}}',
        'priority': 'u=1',
        'x-tigon-is-retry': 'False',
        'x-graphql-request-purpose': 'fetch',
        'content-type': 'application/x-www-form-urlencoded',
        'x-fb-tasos-experimental': '1',
        'x-graphql-client-library': 'pando',
        'x-fb-appnetsession-sid': dev['sid'],
        'x-fb-integrity-machine-id': GLOBAL_MACHINE_ID,
        'user-agent': IOS_USER_AGENT,
        'x-fb-connection-type': 'wifi',
        'x-fb-appnetsession-nid': dev['nid'],
        'x-fb-sim-hni': '45204',
        'authorization': IOS_APP_AUTH_HEADER,
        'x-meta-zca': '{"e": {"c":7}}',
        'x-fb-congestion-signal': '0',
        'accept-encoding': 'gzip, deflate',
        'x-fb-http-engine': 'Tigon/Liger',
        'x-fb-client-ip': 'True',
        'x-fb-server-cluster': 'True'
    }

    flow_info_str = '{"flow_name":"new_to_family_fb_default","flow_type":"ntf"}'
    reg_info_dict = {
        'first_name': None, 'last_name': None, 'full_name': None, 'contactpoint': None,
        'ar_contactpoint': None, 'attempted_empty_last_name': False, 'contactpoint_type': None,
        'is_using_unified_cp': None, 'unified_cp_screen_variant': None, 'is_cp_auto_confirmed': False,
        'is_cp_auto_confirmable': False, 'is_cp_claimed': False, 'confirmation_code': None,
        'birthday': None, 'birthday_derived_from_age': None, 'age_range': None, 'did_use_age': False,
        'os_shared_age_range': None, 'gender': None, 'use_custom_gender': False, 'custom_gender': None,
        'encrypted_password': None, 'username': None, 'username_prefill': None, 'accounts_list_client': [],
        'fb_conf_source': None, 'device_id': dev['device_id'], 'ig4a_qe_device_id': None,
        'family_device_id': dev['family_device_id'], 'fdid_available_on_start': None,
        'fdid_rid_available_on_start': None, 'asdid_available_on_start': None, 'user_id': None,
        'safetynet_token': None, 'skip_slow_rel_check': False, 'safetynet_response': None,
        'machine_id': GLOBAL_MACHINE_ID, 'profile_photo': None, 'profile_photo_id': None,
        'profile_photo_upload_id': None, 'avatar': None, 'email_oauth_token_no_contact_perm': None,
        'email_oauth_token': None, 'email_oauth_tokens': [], 'sign_in_with_google_email': None,
        'should_skip_two_step_conf': None, 'openid_tokens_for_testing': None, 'encrypted_msisdn': None,
        'encrypted_msisdn_for_safetynet': None, 'cached_headers_safetynet_info': None,
        'should_skip_headers_safetynet': None, 'headers_last_infra_flow_id': None,
        'headers_last_infra_flow_id_safetynet': None, 'headers_flow_id': None,
        'was_headers_prefill_available': None, 'sso_enabled': None, 'existing_accounts': None,
        'used_ig_birthday': None, 'create_new_to_app_account': None, 'skip_session_info': None,
        'ck_error': None, 'ck_id': None, 'ck_nonce': None, 'should_save_password': True,
        'fb_access_token': None, 'is_msplit_reg': None, 'is_spectra_reg': None,
        'dema_account_consent_given': None, 'spectra_entry_source': None, 'spectra_reg_token': None,
        'spectra_reg_guardian_id': None, 'spectra_reg_guardian_logged_in_context': None,
        'spectra_requester_user_id': None, 'user_id_of_msplit_creator': None,
        'msplit_creator_nonce': None, 'dma_data_combination_consent_given': None, 'xapp_accounts': None,
        'fb_device_id': None, 'fb_machine_id': None, 'ig_device_id': None, 'ig_machine_id': None,
        'should_skip_nta_upsell': None, 'big_blue_token': None,
        'caa_reg_flow_source': 'aymh_multi_profiles_native_integration_point',
        'ig_authorization_token': None, 'full_sheet_flow': False, 'crypted_user_id': None,
        'is_ca_late_teen': None, 'is_early_teen': None, 'is_caa_perf_enabled': True, 'is_preform': True,
        'should_show_rel_error': False, 'ignore_suma_check': False, 'dismissed_login_upsell_with_cna': False,
        'ignore_existing_login': False, 'ignore_existing_login_from_suma': False,
        'ignore_existing_login_after_errors': False, 'suggested_first_name': None,
        'suggested_last_name': None, 'suggested_full_name': None, 'frl_authorization_token': None,
        'post_form_errors': None, 'skip_step_without_errors': False,
        'existing_account_exact_match_checked': True, 'existing_account_fuzzy_match_checked': False,
        'email_oauth_exists': False, 'confirmation_code_send_error': None,
        'consent_jurisdiction_at_gate': None, 'consent_jurisdiction_at_inflow': None,
        'pc_enforcement_outcome': None, 'pc_inflow_decision': None, 'is_too_young': False,
        'source_account_type': None, 'whatsapp_installed_on_client': True, 'confirmation_medium': None,
        'source_credentials_type': None, 'source_cuid': None, 'source_account_reg_info': None,
        'soap_creation_source': None, 'source_account_type_to_reg_info': None,
        'registration_flow_id': dev['flow_id'], 'should_skip_youth_tos': True,
        'is_youth_regulation_flow_complete': False, 'is_on_cold_start': False, 'email_prefilled': False,
        'cp_confirmed_by_auto_conf': False, 'in_sowa_experiment': False,
        'youth_regulation_config': {
            'isEnabled': True, 'consentJurisdiction': 'VN', 'shouldRaiseAgeGating': False,
            'ageOfConsent': None, 'ageOfParentalConsent': None, 'requiresAgeVerification': False,
            'requiresParentalConsent': False
        },
        'screen_visited': ['CAA_REG_WELCOME_SCREEN']
    }

    current_reg_context = 'AQV' + str(uuid.uuid4()).replace('-', '')[:32]

    # BƯỚC 1: GỬI HỌ TÊN (name.async)
    emit("step", {"step": 1, "name": f"Gửi form reg Họ Tên ({full_name})", "target": contact_point, "worker_id": wid})
    emit("info", {"message": f"[Luồng {wid}] [Bước 1] Gửi Họ Tên: {full_name}..."})
    client_inputs_1 = {
        'last_name': first_name, 'failed_fuzzy_names_match_count': 0, 'network_bssid': None,
        'first_name': last_name, 'is_from_device_emails': 0, 'block_store_machine_id': '',
        'device_emails': [], 'zero_balance_state': '', 'lois_settings': {'lois_token': ''},
        'device_phone_numbers': [], 'has_rejected_rel': 0, 'family_device_id': ''
    }
    server_inputs_1 = {
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'login_surface': 'aymh_one_tap', 'is_from_logged_out': 1,
        'INTERNAL__latency_qpl_instance_id': 175782787800007,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'reg_info': json.dumps(reg_info_dict), 'access_flow_version': 'pre_mt_behavior',
        'flow_info': flow_info_str, 'current_step': 1,
        'INTERNAL__latency_qpl_marker_id': 36707139,
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'event_request_id': str(uuid.uuid4()),
        'is_from_logged_in_switcher': 0, 'reg_context': current_reg_context,
        'is_platform_login': 0, 'family_device_id': None, 'login_entry_point': 'logged_out'
    }
    payload_step_1 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.name.async',
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.name.async', client_inputs_1, server_inputs_1, dev)
    }

    try:
        h1 = headers.copy()
        h1['x-fb-friendly-name'] = payload_step_1['fb_api_req_friendly_name']
        resp1 = session.post(url, headers=h1, data=payload_step_1, proxies=proxies, timeout=15)
        current_reg_context = extract_reg_context(resp1.text, current_reg_context)
    except Exception as e:
        logger.warning(f"Error in Step 1: {e}")

    time.sleep(random.uniform(0.6, 1.2))

    # BƯỚC 2: GỬI NGÀY SINH (birthday.async)
    b_y = random.randint(1994, 2005)
    b_m = random.randint(1, 12)
    b_d = random.randint(1, 28)
    birthday_str = f'{b_d:02d}-{b_m:02d}-{b_y:04d}'
    b_ts = int(datetime.datetime(b_y, b_m, b_d).timestamp())

    emit("step", {"step": 2, "name": f"Gửi form reg Ngày sinh ({birthday_str})", "target": contact_point, "worker_id": wid})
    emit("info", {"message": f"[Luồng {wid}] [Bước 2] Gửi Ngày sinh: {birthday_str}..."})
    reg_info_dict['first_name'] = last_name
    reg_info_dict['last_name'] = first_name
    reg_info_dict['full_name'] = full_name
    reg_info_dict['screen_visited'] = ['CAA_REG_WELCOME_SCREEN', 'bloks.caa.reg.birthday']

    client_inputs_2 = {
        'should_skip_youth_tos': 0, 'block_store_machine_id': '', 'zero_balance_state': '',
        'accounts_list': [], 'birthday_or_current_date_string': birthday_str,
        'network_bssid': None, 'birthday_timestamp': b_ts,
        'lois_settings': {'lois_token': ''}, 'os_age_range': '',
        'client_timezone': 'Asia/Ho_Chi_Minh', 'is_youth_regulation_flow_complete': 0
    }
    server_inputs_2 = {
        'is_from_logged_out': 1, 'access_flow_version': 'pre_mt_behavior',
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'reg_context': current_reg_context, 'family_device_id': None,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'INTERNAL__latency_qpl_instance_id': 175872741300230,
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'login_surface': 'aymh_one_tap',
        'flow_info': flow_info_str, 'reg_info': json.dumps(reg_info_dict),
        'login_entry_point': 'logged_out', 'is_from_logged_in_switcher': 0,
        'is_platform_login': 0, 'current_step': 2, 'INTERNAL__latency_qpl_marker_id': 36707139
    }
    payload_step_2 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.birthday.async',
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.birthday.async', client_inputs_2, server_inputs_2, dev)
    }

    try:
        h2 = headers.copy()
        h2['x-fb-friendly-name'] = payload_step_2['fb_api_req_friendly_name']
        resp2 = session.post(url, headers=h2, data=payload_step_2, proxies=proxies, timeout=15)
        current_reg_context = extract_reg_context(resp2.text, current_reg_context)
    except Exception as e:
        logger.warning(f"Error in Step 2: {e}")

    time.sleep(random.uniform(0.6, 1.2))

    # BƯỚC 3: GỬI GIỚI TÍNH (gender.async)
    gender_txt = "Nữ" if gender == 1 else "Nam"
    emit("step", {"step": 3, "name": f"Gửi form reg Giới tính ({gender_txt})", "target": contact_point, "worker_id": wid})
    emit("info", {"message": f"[Luồng {wid}] [Bước 3] Gửi Giới tính: {gender_txt}..."})
    reg_info_dict['birthday'] = birthday_str
    reg_info_dict['age_range'] = 'o18'
    reg_info_dict['gender'] = gender

    client_inputs_3 = {
        'device_emails': [], 'gender': gender, 'network_bssid': None,
        'lois_settings': {'lois_token': ''}, 'device_phone_numbers': [],
        'zero_balance_state': '', 'block_store_machine_id': '', 'pronoun': 0, 'custom_gender': ''
    }
    server_inputs_3 = {
        'is_from_logged_out': 1, 'access_flow_version': 'pre_mt_behavior',
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'reg_context': current_reg_context, 'family_device_id': None,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'INTERNAL__latency_qpl_instance_id': 176167360100158,
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'login_surface': 'aymh_one_tap',
        'flow_info': flow_info_str, 'reg_info': json.dumps(reg_info_dict),
        'login_entry_point': 'logged_out', 'is_from_logged_in_switcher': 0,
        'is_platform_login': 0, 'current_step': 3, 'INTERNAL__latency_qpl_marker_id': 36707139
    }
    payload_step_3 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.gender.async',
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.gender.async', client_inputs_3, server_inputs_3, dev)
    }

    try:
        h3 = headers.copy()
        h3['x-fb-friendly-name'] = payload_step_3['fb_api_req_friendly_name']
        resp3 = session.post(url, headers=h3, data=payload_step_3, proxies=proxies, timeout=15)
        current_reg_context = extract_reg_context(resp3.text, current_reg_context)
    except Exception as e:
        logger.warning(f"Error in Step 3: {e}")

    time.sleep(random.uniform(0.6, 1.2))

    # BƯỚC 4: GỬI THÔNG TIN LIÊN HỆ (contactpoint_phone.async HOẶC contactpoint_email.async)
    if bait_mode == "gmail":
        step4_label = f"Mồi Gmail {contact_point}"
    elif bait_mode == "phone":
        step4_label = f"Mồi SĐT {contact_point}"
    else:
        step4_label = f"Đăng ký Email {contact_point}"
    emit("step", {"step": 4, "name": step4_label, "target": contact_point, "worker_id": wid})
    if is_phone:
        emit("info", {"message": f"[Luồng {wid}] [Bước 4] Gửi Số điện thoại: {contact_point} (Mã vùng {parsed_country})..."})
        reg_info_dict['contactpoint'] = contact_point
        reg_info_dict['contactpoint_type'] = 'phone_number'
        reg_info_dict['screen_visited'] = ['CAA_REG_WELCOME_SCREEN', 'bloks.caa.reg.birthday', 'CAA_REG_CONTACT_POINT_PHONE']
        client_inputs_4 = {
            'family_device_id': '', 'seen_login_upsell': 0, 'block_store_machine_id': '',
            'confirmed_cp_and_code': {}, 'zero_balance_state': '',
            'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'accounts_list': [],
            'fb_ig_device_id': [], 'network_bssid': None, 'lois_settings': {'lois_token': ''},
            'has_rejected_rel': 0, 'msg_previous_cp': '', 'phone': contact_point,
            'country_code': parsed_country
        }
        friendly_name_4 = 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.async.contactpoint_phone.async'
        var_query_4 = 'com.bloks.www.bloks.caa.reg.async.contactpoint_phone.async'
        step4_text_input_id = 'vzj9pz:113'
    else:
        emit("info", {"message": f"[Luồng {wid}] [Bước 4] Gửi Email: {contact_point}..."})
        reg_info_dict['contactpoint'] = contact_point
        reg_info_dict['contactpoint_type'] = 'email'
        reg_info_dict['screen_visited'] = ['CAA_REG_WELCOME_SCREEN', 'bloks.caa.reg.birthday', 'CAA_REG_CONTACT_POINT_PHONE', 'CAA_REG_CONTACT_POINT_EMAIL']
        client_inputs_4 = {
            'switch_cp_have_seen_suma': 0, 'family_device_id': '', 'seen_login_upsell': 0,
            'block_store_machine_id': '', 'confirmed_cp_and_code': {}, 'zero_balance_state': '',
            'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'accounts_list': [],
            'fb_ig_device_id': [], 'network_bssid': None, 'email_prefilled': 0,
            'lois_settings': {'lois_token': ''}, 'has_rejected_rel': 0, 'msg_previous_cp': '',
            'is_from_device_emails': 0, 'email': contact_point, 'switch_cp_first_time_loading': 1
        }
        friendly_name_4 = 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.async.contactpoint_email.async'
        var_query_4 = 'com.bloks.www.bloks.caa.reg.async.contactpoint_email.async'
        step4_text_input_id = 't7ud3m:28'

    server_inputs_4 = {
        'INTERNAL__latency_qpl_marker_id': 36707139, 'event_request_id': str(uuid.uuid4()),
        'login_surface': 'aymh_one_tap', 'cp_source': 0, 'is_from_logged_in_switcher': 0,
        'is_platform_login': 0, 'access_flow_version': 'pre_mt_behavior',
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'flow_info': flow_info_str,
        'INTERNAL__latency_qpl_instance_id': 176669307400128, 'cp_funnel': 0,
        'login_entry_point': 'logged_out', 'is_from_logged_out': 1,
        'text_input_id': step4_text_input_id,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'reg_info': json.dumps(reg_info_dict), 'current_step': 4,
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'family_device_id': None
    }
    payload_step_4 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': friendly_name_4,
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables(var_query_4, client_inputs_4, server_inputs_4, dev)
    }

    try:
        h4 = headers.copy()
        h4['x-fb-friendly-name'] = payload_step_4['fb_api_req_friendly_name']
        resp4 = session.post(url, headers=h4, data=payload_step_4, proxies=proxies, timeout=15)
        if 'errors' in resp4.text and '"data":{"fb_bloks_action":null}' in resp4.text:
            err_msg = "Facebook từ chối Email tại Bước 4"
            try:
                e_data = resp4.json().get('errors', [{}])[0]
                err_msg = f"{e_data.get('summary', 'Lỗi')}: {e_data.get('description', e_data.get('message', ''))}"
            except Exception:
                pass
            emit("error", {"message": f"[Luồng {wid}] ❌ Bước 4 thất bại: {err_msg}"})
            return RegistrationResult(
                success=False,
                status="failed",
                identifier=contact_point,
                error_message=err_msg,
                elapsed_seconds=round(time.time() - start_time, 2),
                metadata={"step": 4, "die": False, "reg_mode": "ios_bloks"}
            )

        current_reg_context = extract_reg_context(resp4.text, current_reg_context)
    except Exception as e:
        emit("error", {"message": f"[Luồng {wid}] Lỗi Bước 4: {e}"})
        return RegistrationResult(
            success=False,
            status="error",
            identifier=contact_point,
            error_message=str(e),
            elapsed_seconds=round(time.time() - start_time, 2),
            metadata={"step": 4, "die": False, "reg_mode": "ios_bloks"}
        )

    time.sleep(random.uniform(0.8, 1.5))

    # BƯỚC 5: GỬI MẬT KHẨU (password.async)
    emit("step", {"step": 5, "name": "Gửi form reg Mật khẩu", "target": contact_point, "worker_id": wid})
    emit("info", {"message": f"[Luồng {wid}] [Bước 5] Gửi Mật khẩu..."})
    reg_info_dict['encrypted_password'] = password_to_send
    if is_phone:
        reg_info_dict['screen_visited'] = ['CAA_REG_WELCOME_SCREEN', 'bloks.caa.reg.birthday', 'CAA_REG_CONTACT_POINT_PHONE', 'CAA_REG_PASSWORD']
    else:
        reg_info_dict['screen_visited'] = ['CAA_REG_WELCOME_SCREEN', 'bloks.caa.reg.birthday', 'CAA_REG_CONTACT_POINT_PHONE', 'CAA_REG_CONTACT_POINT_EMAIL', 'CAA_REG_PASSWORD']

    client_inputs_5 = {
        'block_store_machine_id': '', 'zero_balance_state': '',
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'email_oauth_token_map': {},
        'fb_ig_device_id': [], 'network_bssid': None, 'encrypted_password': password_to_send,
        'client_known_key_hash': '', 'whatsapp_installed_on_client': 1,
        'encrypted_msisdn_for_safetynet': '', 'lois_settings': {'lois_token': ''},
        'safetynet_token': '', 'caa_play_integrity_attestation_result': '',
        'has_rejected_rel': 0, 'safetynet_response': '', 'spi_action': 1,
        'headers_last_infra_flow_id_safetynet': ''
    }
    server_inputs_5 = {
        'INTERNAL__latency_qpl_marker_id': 36707139, 'event_request_id': str(uuid.uuid4()),
        'login_surface': 'aymh_one_tap', 'is_from_logged_in_switcher': 0,
        'is_platform_login': 0, 'access_flow_version': 'pre_mt_behavior',
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'flow_info': flow_info_str,
        'INTERNAL__latency_qpl_instance_id': 176773764300378,
        'login_entry_point': 'logged_out', 'is_from_logged_out': 1,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'reg_context': current_reg_context, 'reg_info': json.dumps(reg_info_dict),
        'current_step': 5, 'flow_modifier': flow_info_str,
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'family_device_id': None
    }
    payload_step_5 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.password.async',
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.password.async', client_inputs_5, server_inputs_5, dev)
    }

    try:
        h5 = headers.copy()
        h5['x-fb-friendly-name'] = payload_step_5['fb_api_req_friendly_name']
        resp5 = session.post(url, headers=h5, data=payload_step_5, proxies=proxies, timeout=15)
        if 'errors' in resp5.text and '"data":{"fb_bloks_action":null}' in resp5.text:
            err_msg = "Facebook từ chối Mật khẩu tại Bước 5"
            try:
                e_data = resp5.json().get('errors', [{}])[0]
                err_msg = f"{e_data.get('summary', 'Lỗi')}: {e_data.get('description', e_data.get('message', ''))}"
            except Exception:
                pass
            emit("warning", {"message": f"[Luồng {wid}] ⚠️ Bước 5 bị từ chối: {err_msg}"})
            return RegistrationResult(
                success=False,
                status="failed",
                identifier=contact_point,
                error_message=err_msg,
                elapsed_seconds=round(time.time() - start_time, 2),
                metadata={"step": 5, "die": False, "reg_mode": "ios_bloks"}
            )
        current_reg_context = extract_reg_context(resp5.text, current_reg_context)
    except Exception as e:
        emit("error", {"message": f"[Luồng {wid}] Lỗi Bước 5: {e}"})
        return RegistrationResult(
            success=False,
            status="error",
            identifier=contact_point,
            error_message=str(e),
            elapsed_seconds=round(time.time() - start_time, 2),
            metadata={"step": 5, "die": False, "reg_mode": "ios_bloks"}
        )

    time.sleep(round(random.uniform(2.5, 4.0), 1))

    # BƯỚC 6: YÊU CẦU TẠO TÀI KHOẢN (create.account.async)
    emit("step", {"step": 6, "name": "Đang tạo UID...", "target": contact_point, "worker_id": wid})
    emit("info", {"message": f"[Luồng {wid}] [Bước 6] Gửi yêu cầu khởi tạo tài khoản hệ thống..."})
    client_inputs_6 = {
        'ig_partially_created_account_user_id': 0, 'block_store_machine_id': '',
        'ck_id': '', 'zero_balance_state': '', 'ck_nonce': '',
        'ig_partially_created_account_nonce': '', 'encrypted_msisdn': '',
        'failed_birthday_year_count': '', 'ck_error': '', 'network_bssid': None,
        'no_contact_perm_email_oauth_token': '', 'lois_settings': {'lois_token': ''},
        'reached_from_tos_screen': 1, 'ig_partially_created_account_nonce_expiry': 0,
        'headers_last_infra_flow_id': ''
    }
    server_inputs_6 = {
        'INTERNAL__latency_qpl_marker_id': 36707139, 'event_request_id': str(uuid.uuid4()),
        'login_surface': 'aymh_one_tap', 'is_from_logged_in_switcher': 0,
        'is_platform_login': 0, 'access_flow_version': 'pre_mt_behavior',
        'cloud_trust_token': GLOBAL_CLOUD_TRUST_TOKEN, 'flow_info': flow_info_str,
        'INTERNAL__latency_qpl_instance_id': 176973951800024,
        'login_entry_point': 'logged_out', 'is_from_logged_out': 1,
        'layered_homepage_experiment_group': 'not_in_experiment',
        'reg_context': current_reg_context, 'reg_info': json.dumps(reg_info_dict),
        'current_step': 8, 'bloks_controller_source': 'bk_caa_reg_icon_text_list_tos_screen',
        'offline_experiment_group': 'caa_launch_fbios_combined_60_percent',
        'family_device_id': None
    }
    payload_step_6 = {
        'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
        'locale': 'vi_VN', 'purpose': 'fetch',
        'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.create.account.async',
        'client_doc_id': CLIENT_DOC_ID,
        'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.create.account.async', client_inputs_6, server_inputs_6, dev)
    }

    uid = None
    access_token = None
    try:
        h6 = headers.copy()
        h6['x-fb-friendly-name'] = payload_step_6['fb_api_req_friendly_name']
        from core.registration_service import ProxySubmitRateLimiter
        p_slot_key = task_input.extra.get("proxy_ip", "") or (proxies.get("http") if isinstance(proxies, dict) else str(task_input.proxy or ""))
        ip_bloks_lock = ProxySubmitRateLimiter.get_ip_lock(p_slot_key)
        with ip_bloks_lock:
            ProxySubmitRateLimiter.wait_turn(p_slot_key, min_interval=random.uniform(2.8, 4.0))
            try:
                resp6 = session.post(url, headers=h6, data=payload_step_6, proxies=proxies, timeout=20)
            finally:
                ProxySubmitRateLimiter.record_submit_finish(p_slot_key)
        
        uid_match = re.search(r'["\'](?:uid|user_id|actor_id|created_userid)["\']\s*:\s*["\']?(\d{10,20})["\']?', resp6.text)
        if uid_match:
            uid = uid_match.group(1)
        else:
            backup_match = re.search(r'(1000\d{11}|615\d{11,12})', resp6.text)
            if backup_match:
                uid = backup_match.group(1)
        if not uid and session.cookies.get('c_user'):
            uid = session.cookies.get('c_user')

        token_match = re.search(r'(EAAAA[a-zA-Z0-9]+)', resp6.text)
        if token_match:
            access_token = token_match.group(1)

    except Exception as e:
        emit("error", {"message": f"[Luồng {wid}] Lỗi Bước 6: {e}"})
        return RegistrationResult(
            success=False,
            status="error",
            identifier=contact_point,
            error_message=str(e),
            elapsed_seconds=round(time.time() - start_time, 2),
            metadata={"step": 6, "die": False, "reg_mode": "ios_bloks"}
        )

    if not uid:
        fb_err_detail = ""
        try:
            r_json = resp6.json()
            if "errors" in r_json and r_json["errors"]:
                e0 = r_json["errors"][0]
                fb_err_detail = f"{e0.get('summary', '')}: {e0.get('description', e0.get('message', ''))}".strip(": ")
        except Exception:
            pass

        try:
            with open("fb_checkpoint_log.json", "w", encoding="utf-8") as f_log:
                f_log.write(resp6.text)
        except Exception:
            pass

        is_cp = any(bad in resp6.text.lower() for bad in ("checkpoint", "vô hiệu hóa", "tạm ngưng", "vi phạm", "suspended", "180 ngày"))
        is_integrity = any(bad in resp6.text.lower() for bad in ("integrity_block", "không thể tạo tài khoản", "kh\u00f4ng th\u1ec3 t\u1ea1o t\u00e0i kho\u1ea3n"))
        if fb_err_detail:
            err_msg = f"{fb_err_detail} (Facebook từ chối tại Bước 6)"
        elif is_integrity:
            err_msg = "Không thể tạo tài khoản (Integrity Block - Facebook hạn chế IP này, cần xoay IP mới)"
        else:
            err_msg = "Không trích xuất được UID (Facebook chặn màn hình hoặc yêu cầu Captcha/Integrity)"
        status_code = "die" if is_cp else "failed"
        emit("error", {"message": f"[Luồng {wid}] ❌ Tạo tài khoản thất bại: {err_msg}"})
        return RegistrationResult(
            success=False,
            status=status_code,
            identifier=contact_point,
            error_message=err_msg,
            elapsed_seconds=round(time.time() - start_time, 2),
            metadata={"step": 6, "die": is_cp, "reg_mode": "ios_bloks"}
        )

    emit("success", {"message": f"[Luồng {wid}] 🎉 TẠO TÀI KHOẢN THÀNH CÔNG! UID: {uid} | Tên: {full_name}", "uid": uid})
    emit("step", {"step": 6, "name": f"Đã sinh UID {uid}", "target": contact_point, "uid": uid, "worker_id": wid})

    # 1. Trích xuất cookies phiên khởi tạo trực tiếp từ Session iOS và response Step 6 (chuẩn 100% regfb.py)
    init_final_cookie = extract_session_cookies(session, extra_text=resp6.text if 'resp6' in locals() and resp6 else '')
    if uid and not session.cookies.get("c_user"):
        try:
            session.cookies.set("c_user", str(uid), domain=".facebook.com")
        except Exception:
            pass

    # KHÔNG gọi Katana Android Auth và KHÔNG kiểm tra Graph API /me tại thời điểm này
    # (tài khoản vừa tạo đang chờ mã OTP Bước 7, Graph API luôn trả về subcode 490 / Checkpoint Flow 828281030927956 xác nhận email - hoàn toàn bình thường).
    # Chuyển ngay sang Bước 7 để xác nhận mã OTP theo chuẩn regfb.py!
    
    # BƯỚC 7: XÁC NHẬN MÃ OTP VÀ KIỂM ĐỊNH LIVE/DIE (CHUẨN 100% REGFB.PY + MULTI-RETRY)
    raw_to = task_input.extra.get("otp_timeout") or cfg_data.get("otp_timeout")
    otp_timeout = max(int(raw_to), 15) if (raw_to and int(raw_to) > 0) else 35

    max_retries = int(task_input.extra.get("max_otp_email_retries") or cfg_data.get("max_otp_email_retries", 3) or 3)
    max_retries = max(1, min(max_retries, 5))

    target_verification_email = contact_point
    otp_code = None
    confirmed_success = False
    is_live = False
    real_name = full_name
    status_probe = "nvr"
    resp7_text = ""

    for attempt in range(1, max_retries + 1):
        if confirmed_success:
            break

        # Nếu đang ở chế độ mồi (Gmail hoặc SĐT) HOẶC là lượt thử lại (attempt > 1) HOẶC chưa có mailbox thật:
        # Cần cấp phát một email thật mới và gắn vào phiên Facebook qua bind_facebook_session_email
        need_bind = (bait_mode in ("gmail", "phone")) or (attempt > 1) or (not active_mailbox and not mail_10min_obj)
        if need_bind:
            emit("info", {"message": f"[Luồng {wid}] [Lần {attempt}/{max_retries}] Đang cấp phát hòm thư email ({prov_name}) để gắn vào UID {uid}..."})
            new_10m, new_mb, new_email = _allocate_mailbox(prov_name, allow_free_fallback=allow_free_fallback)
            if not new_email:
                emit("warning", {"message": f"[Luồng {wid}] ⚠️ [Lần {attempt}/{max_retries}] Không thể cấp hòm thư mới từ '{prov_name}'. Bỏ qua lượt này."})
                continue
            mail_10min_obj = new_10m
            active_mailbox = new_mb
            target_verification_email = new_email

            emit("step", {"step": 7, "name": f"Gắn email {new_email} [Lần {attempt}/{max_retries}]", "target": new_email, "uid": str(uid), "worker_id": wid})
            emit("info", {"message": f"[Luồng {wid}] [Gắn Email] Cấp hòm thư {new_email}. Đang gắn vào Facebook qua GraphQL..."})

            bind_ok = bind_facebook_session_email(
                client=session,
                server="www.facebook.com",
                new_email=new_email,
                timeout=12,
                uid=str(uid)
            )
            if not bind_ok:
                emit("warning", {"message": f"[Luồng {wid}] ⚠️ [Lần {attempt}/{max_retries}] Gắn email {new_email} chưa hoàn tất. Vẫn thử lắng nghe OTP..."})
            else:
                emit("info", {"message": f"[Luồng {wid}] [Gắn Email] Gắn {new_email} thành công! Đang đợi mã OTP..."})

        emit("step", {"step": 8, "name": f"Đang chờ mã OTP từ {target_verification_email}... [Lần {attempt}/{max_retries}]", "target": target_verification_email, "uid": str(uid), "worker_id": wid})
        emit("info", {"message": f"[Luồng {wid}] [*] [Lần {attempt}/{max_retries}] Đang đợi mã OTP từ hòm thư {target_verification_email} (Tối đa {otp_timeout}s)..."})

        # Lắng nghe OTP trực tiếp từ hòm thư:
        otp_code = None
        if mail_10min_obj and mail_10min_obj.get("session"):
            try:
                otp_code = get_10min_otp(mail_10min_obj["session"], timeout_sec=otp_timeout, proxies=proxies)
                if otp_code:
                    emit("info", {"message": f"[Luồng {wid}] 📥 [Lần {attempt}/{max_retries}] Đã bắt được mã OTP từ 10MinuteMail: {otp_code}"})
            except Exception as e_10m:
                logger.warning(f"Error polling 10min OTP: {e_10m}")

        if not otp_code and active_mailbox and email_prov:
            try:
                otp_res = email_prov.wait_for_otp(active_mailbox, timeout_seconds=otp_timeout, proxy=task_input.proxy)
                if otp_res and otp_res.otp_code:
                    otp_code = str(otp_res.otp_code).strip()
                    emit("info", {"message": f"[Luồng {wid}] 📥 [Lần {attempt}/{max_retries}] Đã bắt được mã OTP: {otp_code}"})
            except Exception as e_otp:
                logger.warning(f"Error polling OTP: {e_otp}")

        if otp_code:
            # Gửi xác nhận OTP
            emit("step", {"step": 9, "name": f"Gửi mã OTP '{otp_code}' [Lần {attempt}/{max_retries}]", "target": target_verification_email, "uid": str(uid), "worker_id": wid})
            emit("info", {"message": f"[Luồng {wid}] [Bước 7] Xác nhận mã OTP ({otp_code}) cho {target_verification_email}..."})

            # K?nh 1: Bloks CAA Confirmation Async (chu?n regfb.py d?ng 1151-1170)
            reg_info_dict['user_id'] = str(uid)
            reg_info_dict['contactpoint'] = target_verification_email
            reg_info_dict['contactpoint_type'] = 'email'
            reg_info_dict['confirmation_code'] = otp_code

            client_inputs_7 = {
                'confirmed_cp_and_code': {}, 'lois_settings': {'lois_token': ''},
                'network_bssid': None, 'cloud_trust_token': None, 'code': otp_code,
                'family_device_id': '', 'block_store_machine_id': '', 'fb_ig_device_id': []
            }
            server_inputs_7 = {
                'is_from_logged_out': 0, 'offline_experiment_group': None,
                'family_device_id': None, 'layered_homepage_experiment_group': None,
                'wa_timer_id': 'wa_retriever', 'INTERNAL__latency_qpl_instance_id': int(time.time() * 1000),
                'event_request_id': str(uuid.uuid4()), 'login_surface': 'unknown',
                'sms_retriever_started_prior_step': 0, 'flow_info': flow_info_str,
                'reg_info': json.dumps(reg_info_dict), 'text_input_id': 'yqncc:57',
                'is_platform_login': 0, 'current_step': 10, 'is_from_logged_in_switcher': 0,
                'INTERNAL__latency_qpl_marker_id': 36707139, 'access_flow_version': 'pre_mt_behavior'
            }
            payload_step_7 = {
                'method': 'post', 'pretty': 'false', 'format': 'json', 'server_timestamps': 'true',
                'locale': 'vi_VN', 'purpose': 'fetch',
                'fb_api_req_friendly_name': 'FBBloksActionRootQuery-com.bloks.www.bloks.caa.reg.confirmation.async',
                'client_doc_id': CLIENT_DOC_ID,
                'variables': create_nested_variables('com.bloks.www.bloks.caa.reg.confirmation.async', client_inputs_7, server_inputs_7, dev)
            }
            h7 = headers.copy()
            h7['x-fb-friendly-name'] = payload_step_7['fb_api_req_friendly_name']
            if access_token:
                h7['authorization'] = f'OAuth {access_token}'

            try:
                resp7 = session.post(url, headers=h7, data=payload_step_7, proxies=proxies, timeout=15)
                resp7_text = resp7.text
                is_conf_bloks = bool(
                    ('CAA_REG_CONFIRMATION:is_confirmed' in resp7.text and 'true' in resp7.text.lower())
                    or re.search(r"""['"]?is_confirmed['"]?\s*:\s*true""", resp7.text, re.I)
                    or '"status":"CONFIRMED"' in resp7.text.upper()
                    or '"status":"SUCCESS"' in resp7.text.upper()
                )
                if is_conf_bloks:
                    confirmed_success = True
                    emit("info", {"message": f"[Luồng {wid}] 🟢 Đã gửi xác nhận mã OTP qua Bloks Native thành công!"})
            except Exception as e_s7:
                logger.warning(f"Error in Step 7 Bloks confirmation: {e_s7}")

            # K?nh 2: N?u Bloks ch?a x?c nh?n th?nh c?ng, fallback sang Web GraphQL Relay (RelayModern)
            if not confirmed_success:
                try:
                    emit("info", {"message": f"[Luồng {wid}] [*] Thử xác nhận OTP '{otp_code}' qua Web GraphQL Relay..."})
                    ok_web, msg_web = submit_facebook_web_email_otp(
                        session=session,
                        server="www.facebook.com",
                        otp_code=otp_code,
                        email=target_verification_email,
                        uid=str(uid),
                        timeout=12
                    )
                    if ok_web:
                        confirmed_success = True
                        emit("info", {"message": f"[Luồng {wid}] 🟢 Xác nhận mã OTP thành công qua Web Relay ({msg_web})!"})
                    else:
                        emit("warning", {"message": f"[Luồng {wid}] ⚠️ Web Relay phản hồi: {msg_web}"})
                except Exception as e_w:
                    logger.debug(f"Web relay confirmation exception: {e_w}")

            if confirmed_success:
                break
        else:
            emit("warning", {"message": f"[Luồng {wid}] ⏱️ [Lần {attempt}/{max_retries}] Hết thời gian chờ {otp_timeout}s không nhận được OTP từ {target_verification_email}."})
            if active_mailbox and email_prov and hasattr(email_prov, "cancel_mailbox"):
                try:
                    email_prov.cancel_mailbox(active_mailbox)
                except Exception:
                    pass

    # Ngâm tài khoản 5s để Meta đồng bộ xác nhận trước khi kiểm định (chuẩn regfb.py dòng 1172)
    if confirmed_success:
        emit("step", {"step": 10, "name": "Kiểm định LIVE / DIE...", "target": target_verification_email, "uid": str(uid), "worker_id": wid})
        emit("info", {"message": f"[Luồng {wid}] [*] Đang ngâm tài khoản 5s để Meta đồng bộ xác nhận trước khi kiểm định (regfb.py)..."})
        time.sleep(5)

    # 1. Trích xuất cookies phiên từ iOS session
    sess_cookie = extract_session_cookies(session, extra_text=(resp7_text or (resp6.text if 'resp6' in locals() and resp6 else '')))
    token_eaaau = None
    cookie_android = ""

    # 2. Katana Android Auth để lấy full cookies (c_user, xs, fr, datr, sb) và EAAAU token
    try:
        t_k, c_k = get_token_eaaau_and_cookie(
            uid=str(uid),
            password=password_to_save,
            email=target_verification_email or contact_point,
            proxies=proxies,
            timeout=12
        )
        if c_k and "xs=" in c_k:
            cookie_android = c_k
        if t_k:
            token_eaaau = t_k
    except Exception as e_k:
        logger.debug(f"Katana live extraction error: {e_k}")

    final_cookie = cookie_android or sess_cookie or ""
    final_token = access_token or token_eaaau or ""

    if str(uid) and final_cookie and "c_user=" not in final_cookie:
        final_cookie = f"c_user={uid}; " + final_cookie

    # 3. Kiểm định Live/Die chuẩn xác với full cookie_str (LUÔN CHẠY để thẩm định đúng die / nvr / live)
    is_live, real_name, status_probe = check_live_die(
        uid=str(uid),
        proxies=proxies,
        token=final_token,
        cookie_str=final_cookie,
        fallback_name=full_name
    )
    if not confirmed_success and status_probe == "live":
        status_probe = "nvr"

    has_valid_cookie = bool(final_cookie and "c_user=" in final_cookie and "xs=" in final_cookie and "xs=deleted" not in final_cookie)

    mail_meta = getattr(active_mailbox, "metadata", {}) or {}
    mail_raw = mail_meta.get("raw_line") or getattr(active_mailbox, "raw_account", "") or ""
    if not mail_raw and mail_10min_obj:
        mail_raw = mail_10min_obj.get("email", "")
    mail_rest = mail_raw.split("|", 1)[1] if (mail_raw and "|" in mail_raw) else mail_raw
    elapsed_total = round(time.time() - start_time, 2)

    # ĐIỀU KIỆN KẾT LUẬN CHUẨN XÁC 100%:
    if (is_live or status_probe == "live") and has_valid_cookie and confirmed_success:
        res = RegistrationResult(
            success=True,
            status="live",
            identifier=target_verification_email or contact_point,
            uid=str(uid),
            password=password_to_save,
            token=final_token,
            cookie_string=final_cookie,
            email=target_verification_email or contact_point,
            email_password=getattr(active_mailbox, "password", ""),
            email_raw=mail_raw,
            email_rest=mail_rest,
            name=real_name or full_name,
            birthday=birthday_str,
            gender=str(gender),
            elapsed_seconds=elapsed_total,
            metadata={
                "reg_mode": "ios_bloks",
                "live_verified": True,
                "token_ios": access_token,
                "token_android": token_eaaau,
                "device_id": dev["device_id"],
                "otp_confirmed": True,
            }
        )
        emit("success", {"result": res, "message": f"[iOS Bloks] 🎉 REG THÀNH CÔNG! UID {uid} | Tên: {real_name or full_name}"})
        return res

    elif status_probe == "die":
        res = RegistrationResult(
            success=False,
            status="die",
            identifier=target_verification_email or contact_point,
            uid=str(uid),
            password=password_to_save,
            token=final_token,
            cookie_string=final_cookie,
            email=target_verification_email or contact_point,
            email_password=getattr(active_mailbox, "password", ""),
            email_raw=mail_raw,
            email_rest=mail_rest,
            name=full_name,
            birthday=birthday_str,
            gender=str(gender),
            error_message="Tài khoản bị Checkpoint 282 sau khi kiểm định",
            elapsed_seconds=elapsed_total,
            metadata={
                "reg_mode": "ios_bloks",
                "die": True,
                "checkpoint": True,
                "checkpoint_282": True,
                "device_id": dev["device_id"],
            }
        )
        emit("error", {"result": res, "message": f"[iOS Bloks] ❌ UID {uid} bị Checkpoint 282 (DIE) sau khi kiểm định"})
        return res

    else:
        # NVR (Ch?a x?c minh): L?u phi?n NVR an to?n, TUY?T ??I kh?ng ??nh d?u DIE
        unver_reason = f"Đã gửi mã OTP ({otp_code}) nhưng cần duyệt thêm (Lưu NVR)" if otp_code else f"Chưa hoàn tất xác minh OTP qua {max_retries} lượt thử (Lưu NVR)"
        res = RegistrationResult(
            success=False,
            status="unverified",
            identifier=target_verification_email or contact_point,
            uid=str(uid),
            password=password_to_save,
            token=final_token,
            cookie_string=final_cookie,
            email=target_verification_email or contact_point,
            email_password=getattr(active_mailbox, "password", ""),
            email_raw=mail_raw,
            email_rest=mail_rest,
            name=full_name,
            birthday=birthday_str,
            gender=str(gender),
            error_message=unver_reason,
            elapsed_seconds=elapsed_total,
            metadata={
                "reg_mode": "ios_bloks",
                "unverified": True,
                "nvr": True,
                "token_ios": access_token,
                "device_id": dev["device_id"],
                "otp_confirmed": confirmed_success,
            }
        )
        emit("unverified", {"result": res, "message": f"[iOS Bloks] ⏳ UID {uid} chưa hoàn tất xác minh -> Lưu phiên NVR"})
        return res
