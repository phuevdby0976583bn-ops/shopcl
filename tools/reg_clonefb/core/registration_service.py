# -*- coding: utf-8 -*-
"""
core.registration_service
Domain service for Facebook Web/Mobile Registration flow.
Completely separated from UI, CLI prints, and global counters.
Supports:
1. Mode vr: Strict VR OTP verification flow.
"""

import sys
import os
import time
import re
import json
import random
import logging
import threading
import unicodedata
import uuid
import html
from datetime import datetime
from typing import Optional, Dict, Any, Callable, Tuple, Union

from faker import Faker

def _is_test_env() -> bool:
    if "pytest" in sys.modules or "unittest" in sys.modules:
        return True
    return any("test" in str(arg).lower() or "pytest" in str(arg).lower() for arg in sys.argv)

def _safe_sleep(seconds: float) -> None:
    if _is_test_env():
        return
    if seconds > 0:
        time.sleep(seconds)

import core.facebook_checker as fb_checker
from core.facebook_checker import check_registration_account_live, check_facebook_account_live_status, check_facebook_uid_live, extract_facebook_uid
from core.geo_manager import GeoTelephonyResolver, GeoTelephonyProfile, normalize_country_code, WORLD_CALLING_CODES
from core.models import RegistrationInput, RegistrationResult, ProxyItem
import core.email_service as email_service
from core.email_service import get_email_provider, submit_facebook_web_email_otp, generate_bait_gmail_identifier, is_chromium_ua, clean_client_hints
from core.http_client import HttpClient, ProxyConnectionError, RequestTimeoutError, HttpClientError
from core.two_factor_service import enable_facebook_2fa
from core.proxy_manager import FreeProxyManager


def parse_maturation_delay_seconds(delay_val: Any, default: float = 90.0) -> float:
    """Chuyển đổi chuỗi cấu hình thời gian ngấu (giây, phút, hoặc khoảng ngẫu nhiên) sang float giây."""
    if delay_val is None:
        return default
    if isinstance(delay_val, (int, float)):
        return max(5.0, float(delay_val))
    s = str(delay_val).strip().lower()
    m_range = re.search(r'(\d+)\s*[-~–]\s*(\d+)', s)
    if m_range:
        low = float(m_range.group(1))
        high = float(m_range.group(2))
        return random.uniform(min(low, high), max(low, high))
    m_min = re.search(r'([\d.]+)\s*(?:phút|min|m\b)', s)
    if m_min:
        try:
            return float(m_min.group(1)) * 60.0
        except Exception:
            pass
    m_sec = re.search(r'([\d.]+)', s)
    if m_sec:
        try:
            return max(5.0, float(m_sec.group(1)))
        except Exception:
            pass
    return default


class ProxySubmitRateLimiter:
    """
    Điều tiết tần suất submit /reg/submit/ theo từng IP Proxy riêng biệt.
    Sử dụng Non-blocking Timestamp Scheduling kết hợp Per-IP Lock:
    giãn cách nhịp gửi an toàn mà không bị nghẽn các IP khác nhau.
    """
    _master_lock = threading.Lock()
    _ip_locks: Dict[str, threading.Lock] = {}
    _next_allowed_time: Dict[str, float] = {}
    _last_submit_finish_time: Dict[str, float] = {}

    @classmethod
    def get_ip_lock(cls, proxy_key: str) -> threading.Lock:
        clean_key = str(proxy_key or "").strip().lower()
        if not clean_key or clean_key in ("direct", "none", "127.0.0.1", "0.0.0.0", ""):
            clean_key = "direct"
        with cls._master_lock:
            if clean_key not in cls._ip_locks:
                cls._ip_locks[clean_key] = threading.Lock()
            return cls._ip_locks[clean_key]

    @classmethod
    def wait_turn(cls, proxy_key: str, min_interval: float = 0.25, max_wait: float = 2.0) -> None:
        clean_key = str(proxy_key or "").strip().lower()
        if not clean_key or clean_key in ("direct", "none", "127.0.0.1", "0.0.0.0", ""):
            return

        with cls._master_lock:
            now = time.time()
            last_t = cls._next_allowed_time.get(clean_key, 0.0)
            base_time = max(now, last_t)
            stagger = random.uniform(min_interval * 0.8, min_interval * 1.2) if min_interval > 0 else random.uniform(0.35, 0.75)
            target_time = base_time + stagger
            wait_s = max(0.0, target_time - now)
            cls._next_allowed_time[clean_key] = target_time

        # Ngủ bên ngoài lock để các luồng khác không bị nghẽn
        if wait_s > 0:
            _safe_sleep(min(wait_s, max_wait))

    @classmethod
    def record_submit_finish(cls, proxy_key: str) -> None:
        clean_key = str(proxy_key or "").strip().lower()
        if not clean_key or clean_key in ("direct", "none", "127.0.0.1", "0.0.0.0", ""):
            return
        with cls._master_lock:
            cls._last_submit_finish_time[clean_key] = time.time()

def extract_facebook_suggested_name(text: str) -> Optional[Tuple[str, str, str]]:
    if not text:
        return None

    # 1. Tim trong HTML input radio/label hoac JSON payload
    radio_matches = re.findall(r'<input[^>]+value="([^"]+)"', text, re.I)
    for rm in radio_matches:
        cand = rm.strip()
        words = cand.split()
        if 2 <= len(words) <= 4 and not any(bad in cand.lower() for bad in ("none", "other", "custom", "chính sách", "không phải", "select", "chọn", "true", "false")):
            last_name = words[0]
            first_name = " ".join(words[1:])
            return cand, first_name, last_name

    # 2. Tim trong van ban (Did you mean: ... hoac Co phai y ban la: ...)
    m = re.search(r'(?:did you mean|có phải ý bạn là|ý bạn là)\s*:\s*(.*?)(?:none of these|không có tên nào|không phải tên nào|none_of_these|$|\.)', text, re.I | re.S)
    if m:
        raw_sug = m.group(1)
        # Tach theo xuong dong, bullet, gach ngang, pipe, HOAC 2 khoang trang tro len (\s{2,})
        chunks = re.split(r"[\r\n•–\-\|]|\s{2,}", raw_sug)
        for chunk in chunks:
            cand = " ".join(chunk.split())
            words = cand.split()
            if 2 <= len(words) <= 4 and not any(bad in cand.lower() for bad in ("none", "không phải", "select", "chọn", "did you", "có phải", "không có tên", "chính sách", "lưu ý", "tiêu đề", "ký hiệu")):
                last_name = words[0]
                first_name = " ".join(words[1:])
                return cand, first_name, last_name

    # 3. Tim truc tiep sau "Có phải ý bạn là: <Ten>"
    m_direct = re.search(r'(?:có phải ý bạn là|did you mean)[:\s]+([A-ZÀ-Ỹa-zà-ỹ\s]{3,30}?)(?:\s{2,}|không có tên|none of|$|\.)', text, re.I)
    if m_direct:
        cand = " ".join(m_direct.group(1).split())
        words = cand.split()
        if 2 <= len(words) <= 4 and not any(bad in cand.lower() for bad in ("none", "không phải", "select", "chọn", "did you", "có phải", "không có tên")):
            last_name = words[0]
            first_name = " ".join(words[1:])
            return cand, first_name, last_name

    return None

def _format_e164_phone(phone_str: str, geo_profile: Any = None) -> str:
    """Định dạng số điện thoại chuẩn quốc tế E.164 (+<calling_code><digits>) để tránh Facebook WAF Error 1351050."""
    clean_str = str(phone_str or "").strip()
    if "@" in clean_str or not clean_str:
        return clean_str
    clean_digits = re.sub(r"\D", "", clean_str)
    if not clean_digits:
        return clean_str

    calling_code = ""
    country_code = ""
    if geo_profile:
        if isinstance(geo_profile, str):
            # top-level GeoTelephonyResolver, normalize_country_code
            norm_c = normalize_country_code(geo_profile)
            if norm_c:
                try:
                    prof = GeoTelephonyResolver.get_profile_for_country(norm_c)
                    calling_code = (prof.phone_calling_code or "").strip().lstrip("+")
                    country_code = prof.country_code
                except Exception:
                    pass
        elif isinstance(geo_profile, dict):
            calling_code = str(geo_profile.get("phone_calling_code") or "").strip().lstrip("+")
            country_code = str(geo_profile.get("country_code") or "").strip().upper()
        else:
            calling_code = (getattr(geo_profile, "phone_calling_code", "") or "").strip().lstrip("+")
            country_code = (getattr(geo_profile, "country_code", "") or "").strip().upper()

    if not calling_code and country_code:
        try:
            # top-level GeoTelephonyResolver
            prof = GeoTelephonyResolver.get_profile_for_country(country_code)
            calling_code = (prof.phone_calling_code or "").strip().lstrip("+")
        except Exception:
            pass

    # Chuẩn hóa SĐT chuẩn quốc tế E.164 (+<calling_code><digits>)
    is_vn = (country_code == "VN") or (calling_code == "84") or (not country_code and not calling_code and clean_digits.startswith("0") and len(clean_digits) == 10)
    if clean_digits.startswith("8484"):
        clean_digits = clean_digits[2:]
        is_vn = True
    if clean_digits.startswith("84") and len(clean_digits) in (11, 12):
        is_vn = True

    if is_vn:
        national = clean_digits
        if national.startswith("84") and len(national) in (11, 12):
            national = national[2:]
        elif national.startswith("0"):
            national = national[1:]
        return f"+84{national}"

    if clean_str.startswith("+"):
        return f"+{clean_digits}"

    if not calling_code:
        if country_code:
            try:
                calling_code = WORLD_CALLING_CODES.get(country_code, "").lstrip("+")
            except Exception:
                pass
        if not calling_code:
            calling_code = "84" if (clean_digits.startswith("0") and len(clean_digits) == 10) else "1"

    if clean_digits.startswith(calling_code) and len(clean_digits) > len(calling_code) + 5:
        return f"+{clean_digits}"
    elif clean_digits.startswith("0"):
        return f"+{calling_code}{clean_digits[1:]}"
    else:
        return f"+{calling_code}{clean_digits}"




from core.session_builder import (

    build_request_context,

    setup_session_cookies,

    get_random_device_profile,

    build_dynamic_kaios_profile,

    DeviceProfile,

)

from modules.email_integrity_guard import (

    EmailIntegrityGuard,

    KNOWN_DISPOSABLE_DOMAINS,

    TRUSTED_PROVIDER_DOMAINS,

)

from modules.play_integrity_verifier import PlayIntegrityNonceManager, GooglePlayIntegrityVerifier

from modules.network_risk_profiler import NetworkRiskProfiler

from modules.behavioral_telemetry import SensorTelemetryEngine, TouchKinematicsEngine

from modules.velocity_graph_engine import (

    BatteryThermalEngine,

    ActivityLifecycleManager,

    BehaviorVelocityLimiter,

    DeviceGraphProfiler,

)

from modules.environment_detector import EnvironmentDetector, EmulatorDetector, RootIntegrityAuditor

from modules.hardware_gpu_audio_profiler import HardwareGpuAudioProfiler

from modules.hardware_keystore_drm import HardwareKeystoreDRMEngine, HardwareAttestationEngine, WidevineDRMProfiler

from modules.multi_sensor_fusion import MultiSensorFusionEngine

from modules.native_antirev_engine import NativeIntegrityAuditor, DirectSyscallEngine, AntiFridaAuditor

from modules.pow_challenge_engine import PoWChallengeEngine

from modules.transport_fingerprint import TransportFingerprintEngine, TlsFingerprintEngine, Http2FingerprintEngine

from integrity_engine import HumanBehaviorDynamics



logger = logging.getLogger(__name__)

_fake = Faker()





HO_VIET = [

    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",

    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Đoàn", "Lâm", "Mai",

    "Trịnh", "Đào", "Cao", "Hà", "Lưu", "Lương", "Thái", "Châu", "Tạ", "Phùng",

    "Tô", "Vương", "Tăng", "Quách", "Nhan", "La", "Kiều", "Triệu", "Hứa", "Nghiêm",

    "Thạch", "Trác", "Bạch", "Cung", "Khổng", "Cù", "Diệp", "Doãn", "Giang", "Hàn",

    "Khâu", "Khưu", "Kim", "Lục", "Mã", "Mạc", "Ninh", "Nông", "Ôn", "Phí",

    "Quản", "Sầm", "Sơn", "Tào", "Thân", "Thi", "Thang", "Tiêu", "Tôn", "Trang",

    "Uông", "Ứng", "Văn", "Vi", "Vĩnh", "Xa", "Xung", "Yên", "Ân", "Bửu",

    "Lạc", "Trịnh", "Âu", "Phù", "Cầm", "Sầm", "Bạc", "Đoan", "Giáp", "Hình"

]



HO_KEP = [

    "Nguyễn Hoàng", "Nguyễn Đình", "Nguyễn Văn", "Nguyễn Đức", "Trần Lê", "Trần Đăng",

    "Phạm Hoàng", "Vũ Đình", "Phan Huỳnh", "Đặng Trần", "Bùi Hoàng", "Lê Nguyễn"

]



DEM_NAM = [

    "Quốc", "Văn", "Minh", "Đức", "Hoàng", "Gia", "Hải", "Tuấn", "Thanh", "Hữu",

    "Xuân", "Thành", "Bảo", "Đình", "Công", "Trọng", "Duy", "Mạnh", "Phúc", "Tấn",

    "Nhật", "Khắc", "Chí", "Đăng", "Thái", "Bá", "Trung", "Vĩnh", "Ngọc", "Viết",

    "Tiến", "Bách", "Hiệp", "Quang", "Huy", "Hồng", "Nam", "Sơn", "Long", "Bình",

    "Vũ", "Thế", "Khánh", "Việt", "Trí", "Nguyên", "Vinh", "Khôi", "An", "Phú"

]



TEN_NAM = [

    "Huy", "Nam", "Phong", "Dũng", "Khánh", "Việt", "Anh", "Long", "Đạt", "Sơn",

    "Tùng", "Bảo", "Phát", "Thịnh", "Khoa", "Hiếu", "Cường", "Tài", "Vinh", "Quân",

    "Lâm", "Kiên", "Bình", "Hải", "Thắng", "Triết", "Hào", "Phú", "Nhân", "Nghĩa",

    "Tú", "Khôi", "Trí", "Sang", "Nguyên", "Phước", "Hoài", "Luân", "Đông", "Thuận",

    "An", "Bách", "Bảo", "Công", "Chiến", "Chính", "Duy", "Đăng", "Đức", "Hiệp",

    "Hùng", "Hưng", "Khang", "Kha", "Khải", "Minh", "Phi", "Phúc", "Quang", "Quyết",

    "Thành", "Thao", "Thế", "Thông", "Tiến", "Toàn", "Trọng", "Trung", "Trường", "Vũ"

]



DEM_NU = [

    "Thị", "Ngọc", "Thu", "Thanh", "Phương", "Kim", "Quỳnh", "Ánh", "Mỹ", "Mai",

    "Hồng", "Tuyết", "Bích", "Như", "Diễm", "Cẩm", "Yến", "Thảo", "Hương", "Hoài",

    "Khánh", "Minh", "Trúc", "Gia", "Tú", "Thùy", "Bảo", "Bội", "Cát", "Đan",

    "Hà", "Hải", "Hạnh", "Hiền", "Hoa", "Hoàng", "Huyền", "Lam", "Lan", "Lệ",

    "Linh", "Loan", "Ly", "Mộng", "Nga", "Ngân", "Nhã", "Oanh", "Phụng", "Quý"

]



TEN_NU = [

    "Trang", "Linh", "Hương", "Lan", "Huyền", "Nhi", "Vy", "Thảo", "Hà", "Trâm",

    "Ngân", "Hoa", "Tuyết", "Mai", "Quỳnh", "Anh", "Dung", "Oanh", "Diệp", "Chi",

    "Ly", "Thư", "Châu", "Hân", "Phương", "Uyên", "Hằng", "Vân", "Yến", "My",

    "Nhung", "Giang", "Thoa", "Tâm", "Loan", "Thắm", "Lê", "Liên", "Sen", "Bích",

    "Bình", "Cúc", "Đào", "Điệp", "Duyên", "Hạnh", "Hiền", "Huệ", "Khánh", "Kiều",

    "Lệ", "Liễu", "Lộc", "Minh", "Nga", "Ngọc", "Nguyệt", "Nhài", "Như", "Nương"

]



MNO_PREFIXES = {
    "viettel": ["098", "097", "096", "086", "039", "038", "037", "036", "035", "034", "033", "032"],
    "vinaphone": ["091", "094", "088", "081", "082", "083", "084", "085"],
    "mobifone": ["090", "093", "089", "070", "076", "077", "078", "079"],
    "vietnamobile": ["092", "056", "058"],
    "gmobile": ["099", "059"],
    "wintel": ["055"],
}

REG_ENTRYPOINTS = [

    "https://{server}/reg/",

    "https://{server}/reg/?soft=hjk",

    "https://{server}/reg/?cid=103",

    "https://{server}/reg/?locale={locale}",

    "https://{server}/reg/?entrypoint=app_registration",

    "https://{server}/r.php",

]



def generate_mno_carrier_phone(
    geo_profile: Optional[Any] = None,
    carrier: Optional[str] = None,
    country_code: Optional[str] = None,
    ip: Optional[str] = None,
    force_vn: bool = False,
    force_fresh: bool = False,
    e164: bool = False,
    **kwargs
) -> str:
    """
    Sinh SDT di dong hop le da dang quoc gia va nha mang (Viettel, Vina, Mobi, T-Mobile, AIS, Telkomsel...).
    Khop hoan toan voi IP cua proxy va chuan quoc te E.164 khi moi tao phien dang ky Facebook.
    """
    from core.geo_manager import generate_phone_suffix_from_ip, GeoTelephonyResolver, normalize_country_code

    if isinstance(geo_profile, str):
        country_code = geo_profile
        geo_profile = None

    c_code = normalize_country_code(country_code)
    target_ip = ip
    if geo_profile:
        if not c_code:
            g_c = getattr(geo_profile, "country_code", "") or (geo_profile.get("country_code") if isinstance(geo_profile, dict) else "")
            c_code = normalize_country_code(g_c)
        if not target_ip:
            g_ip = getattr(geo_profile, "ip", None) or (geo_profile.get("ip") if isinstance(geo_profile, dict) else None)
            if g_ip and str(g_ip).lower() not in ("127.0.0.1", "0.0.0.0", "direct", "none", ""):
                target_ip = str(g_ip)

    # Tự động tra cứu quốc gia chuẩn xác từ IP nếu chưa có country_code (Tránh ra số VN khi proxy là quốc tế)
    if not c_code and target_ip and str(target_ip).lower() not in ("127.0.0.1", "0.0.0.0", "direct", "none", ""):
        try:
            g_prof = GeoTelephonyResolver.resolve_ip(target_ip)
            if g_prof and g_prof.country_code:
                c_code = normalize_country_code(g_prof.country_code)
                if not geo_profile:
                    geo_profile = g_prof
        except Exception:
            pass

    # Khi IP Proxy la quoc te (!= VN), uu tien so dien thoai hop le cua chinh quoc gia do:
    if not force_vn and c_code and c_code != "VN":
        try:
            prof = geo_profile if (geo_profile and hasattr(geo_profile, "generate_phone") and getattr(geo_profile, "country_code", "") == c_code) else GeoTelephonyResolver.get_profile_for_country(c_code, ip=target_ip or "127.0.0.1")
            gen_p = prof.generate_phone(ip=target_ip, e164=e164)
            if gen_p and len(gen_p) >= 6:
                return gen_p
        except Exception:
            pass

    carrier_key = carrier.lower() if carrier and carrier.lower() in MNO_PREFIXES else None
    if not carrier_key and geo_profile and hasattr(geo_profile, "carrier_name"):
        c_name = str(geo_profile.carrier_name).lower()
        for k in MNO_PREFIXES:
            if k in c_name:
                carrier_key = k
                break
    if not carrier_key:
        carrier_key = random.choices(
            ["viettel", "vinaphone", "mobifone", "vietnamobile", "gmobile", "wintel"],
            weights=[0.45, 0.25, 0.20, 0.05, 0.03, 0.02]
        )[0]

    prefixes = MNO_PREFIXES.get(carrier_key, MNO_PREFIXES["viettel"])
    prefix = random.choice(prefixes)
    if force_fresh or not target_ip:
        first_sub = str(random.randint(2, 9))
        rest_sub = "".join(str(random.randint(0, 9)) for _ in range(6))
        suffix = f"{first_sub}{rest_sub}"
    else:
        suffix = generate_phone_suffix_from_ip(target_ip, length=7)
        if len(suffix) != 7 or not suffix.isdigit():
            suffix = f"{random.randint(2, 9)}{''.join(str(random.randint(0, 9)) for _ in range(6))}"
    phone_res = f"{prefix}{suffix}"
    if len(phone_res) != 10:
        phone_res = f"{prefix}{random.randint(2, 9)}{''.join(str(random.randint(0, 9)) for _ in range(6))}"
    if not c_code or c_code == "VN" or force_vn:
        return phone_res
    if e164:
        return f"+84{phone_res.lstrip('0')}"
    return phone_res


def get_random_typing_profile() -> dict:

    profiles = [

        {"type": "fast", "flight_mean_ms": 85.0, "jitter_ms": 20.0, "read_min": 1.4, "read_max": 2.5, "review_min": 1.0, "review_max": 1.8},

        {"type": "moderate", "flight_mean_ms": 145.0, "jitter_ms": 35.0, "read_min": 1.8, "read_max": 3.2, "review_min": 1.2, "review_max": 2.5},

        {"type": "careful", "flight_mean_ms": 205.0, "jitter_ms": 50.0, "read_min": 2.4, "read_max": 4.2, "review_min": 1.8, "review_max": 3.5},

    ]

    return random.choices(profiles, weights=[0.35, 0.50, 0.15])[0]



def _extract_regex(pattern: str, text: str) -> Optional[str]:
    """Extract first regex capture group safely."""
    if not text:
        return None
    try:
        m = re.search(pattern, text)
        return m.group(1) if m else None
    except Exception:
        return None


_search = _extract_regex

# Mapping 10 server domains from Mr-SxR (facebook-account-registration)
ALL_LEGACY_SERVER_DOMAINS = [
    "m.facebook.com",
    "mbasic.facebook.com",
    "touch.facebook.com",
    "free.facebook.com",
    "m.alpha.facebook.com",
    "m.beta.facebook.com",
    "x.facebook.com",
    "limited.facebook.com",
    "iphone.facebook.com",
    "d.facebook.com",
]

SERVER_MAP: Dict[str, str] = {
    "1": "m.facebook.com",
    "2": "mbasic.facebook.com",
    "3": "touch.facebook.com",
    "4": "free.facebook.com",
    "5": "m.alpha.facebook.com",
    "6": "m.beta.facebook.com",
    "7": "x.facebook.com",
    "8": "limited.facebook.com",
    "9": "iphone.facebook.com",
    "10": "d.facebook.com",
}

# Mapping 6 legacy device types (Android, KaiOS, WindowsPhone, BlackBerry, IphoneApp, AndroidApp)
LEGACY_DEVICE_TYPES: Dict[str, str] = {
    "1": "Android",
    "2": "KaiOS",
    "3": "WindowsPhone",
    "4": "BlackBerry",
    "5": "IphoneApp",
    "6": "AndroidApp",
}

output_lock = threading.Lock()


def resolve_facebook_server(
    server_raw: Optional[str] = None,
    server_pool: Optional[list] = None,
    random_subset: bool = False,
    random_server: bool = False,
) -> Tuple[str, str]:
    """
    Resolve server input to an authoritative Facebook mobile/web domain.
    Guaranteed to return a valid domain. Eliminates toxic zero-rating domains
    (free, x, d, limited) that cause WAF 1351050 and country-selector redirects.
    """
    server_str = str(server_raw or "m.facebook.com").strip()
    s_lower = server_str.lower()

    is_subset_mode = (
        bool(random_subset)
        or (s_lower in ("subset", "pool", "custom", "group"))
        or ("nhóm" in s_lower)
    )
    is_random_all = (
        (bool(random_server) or s_lower in ("random", "all", "rand", "random_all") or "tất cả" in s_lower)
        and not is_subset_mode
    )

    # Chỉ sử dụng các domain mobile web chuẩn Meta (Loại bỏ zero-rating gây lỗi Selecciona tu país và 1351050)
    reliable_servers = ["m.facebook.com", "mbasic.facebook.com", "touch.facebook.com"]

    if is_random_all:
        server = random.choice(reliable_servers)
        server_tag = f"{server} (🎲 Random server)"
        return server, server_tag

    if is_subset_mode:
        custom_pool = server_pool or []
        if isinstance(custom_pool, str):
            custom_pool = [s.strip() for s in re.split(r'[, ]+', custom_pool) if s.strip()]
        resolved_pool = []
        for s in custom_pool:
            dom = SERVER_MAP.get(str(s).strip(), str(s).strip())
            if dom in reliable_servers and dom not in resolved_pool:
                resolved_pool.append(dom)
        if not resolved_pool:
            resolved_pool = reliable_servers
        server = random.choice(resolved_pool)
        server_tag = f"{server} (🎲 Random nhóm {len(resolved_pool)} server)"
        return server, server_tag

    # Cố định 1 Server: Nhận diện chính xác domain chuẩn Meta
    matched = None
    for dom in reliable_servers:
        if dom in server_str:
            matched = dom
            break
    if not matched:
        clean_key = server_str.split("-")[0].strip().lstrip("0") if "-" in server_str else server_str.lstrip("0")
        raw_match = SERVER_MAP.get(clean_key) or SERVER_MAP.get(server_str)
        if raw_match in reliable_servers:
            matched = raw_match

    server = matched or "m.facebook.com"
    server_tag = server
    return server, server_tag


def _save_success_output(record_line: str) -> None:
    """Save successful account credentials across output paths (thread-safe)."""
    with output_lock:
        try:
            from core.path_manager import get_output_filepaths
            filepaths = get_output_filepaths()
        except Exception:
            filepaths = ["output/success.txt"]
        for filepath in filepaths:
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(record_line + "\n")
            except Exception:
                pass



def _sync_response_cookies(client: Any, response: Any) -> None:

    """Đảm bảo mọi cookie set-cookie từ CDN Facebook (datr, sb, fr, wd, ...) được lưu đồng bộ."""

    if not response or not hasattr(response, "headers") or not client:

        return

    try:

        set_cookies = []

        if hasattr(response.headers, "get_list"):

            set_cookies = response.headers.get_list("set-cookie") or response.headers.get_list("Set-Cookie")

        elif "set-cookie" in response.headers:

            val = response.headers.get("set-cookie")

            set_cookies = [val] if isinstance(val, str) else list(val)

        for sc in set_cookies:

            for part in sc.split(";"):

                part = part.strip()

                if "=" in part:

                    k, v = part.split("=", 1)

                    k_clean = k.strip()

                    if k_clean.lower() not in ("path", "domain", "expires", "max-age", "secure", "httponly", "samesite"):

                        client.set_cookie(k_clean, v.strip(), domain=".facebook.com")

                        break

    except Exception:

        pass







def trigger_facebook_confirmation_resend(
    client: Any,
    server: str = "m.facebook.com",
    target: str = "",
    base_headers: Optional[Dict[str, str]] = None,
    fb_dtsg: str = "",
    lsd: str = "",
    jazoest: str = "",
    cur_uid: str = "",
    timeout: int = 10,
) -> bool:
    """Kích hoạt phát lại mã OTP Facebook/Meta đa kênh."""
    success = False
    clean_target = str(target or "").strip()
    is_phone = bool(clean_target and "@" not in clean_target)
    endpoint_page = "confirmphone.php" if is_phone else "confirmemail.php"

    hdrs = dict(base_headers or {})
    hdrs["referer"] = f"https://{server}/{endpoint_page}"

    try:
        r_get = client.get(f"https://{server}/{endpoint_page}?resend=1", headers=hdrs, timeout=timeout)
        _sync_response_cookies(client, r_get)
        if r_get and getattr(r_get, "status_code", 0) in (200, 302):
            success = True
    except Exception as ex_g:
        logger.debug(f"[Resend OTP] GET error: {ex_g}")

    try:
        post_hdrs = dict(hdrs)
        post_hdrs["content-type"] = "application/x-www-form-urlencoded"
        post_hdrs["origin"] = f"https://{server}"
        eff_jaz = jazoest or (f"2{sum(ord(c) for c in fb_dtsg)}" if fb_dtsg else "2987")
        post_data = {
            "fb_dtsg": fb_dtsg or "",
            "jazoest": eff_jaz,
            "lsd": lsd or "",
            "resend": "1",
            "send_another_code": "1",
        }
        r_post = client.post(f"https://{server}/{endpoint_page}", data=post_data, headers=post_hdrs, timeout=timeout)
        _sync_response_cookies(client, r_post)
        if r_post and getattr(r_post, "status_code", 0) in (200, 302):
            success = True
    except Exception as ex_p:
        logger.debug(f"[Resend OTP] POST error: {ex_p}")

    # Resend code only without duplicate contactpoint addition

    return success


def bind_facebook_session_email(
    client: Any,
    server: str,
    new_email: str,
    base_headers: Optional[Dict[str, str]] = None,
    fb_dtsg: str = "",
    jazoest: str = "",
    reg_instance: str = "",
    timeout: int = 10,
    uid: Optional[str] = None,
) -> bool:
    """Gắn Email hoặc SĐT mới vào phiên Facebook (GraphQL + web fallback)."""
    clean_target = str(new_email or "").strip()
    if not clean_target:
        return False
    is_phone = bool("@" not in clean_target)

    try:
        from core.email_service import add_facebook_confirmation_contactpoint
        client_uid = uid or (client.get_cookies().get("c_user") if hasattr(client, "get_cookies") else None)
        if not client_uid and hasattr(client, "uid") and client.uid:
            client_uid = str(client.uid)
        ok, msg = add_facebook_confirmation_contactpoint(
            session=client,
            email=clean_target,
            server=server,
            headers=base_headers,
            uid=client_uid,
            fb_dtsg=fb_dtsg,
            timeout=timeout,
        )
        if ok:
            logger.info(f"bind_facebook_session_email: Gắn contact {clean_target} thành công qua GraphQL ({msg})")
            try:
                cf_hdrs = dict(base_headers or {})
                cf_hdrs["referer"] = f"https://{server}/confirmemail.php"
                cf_hdrs.pop("X-Requested-With", None)
                cf_hdrs.pop("x-requested-with", None)
                cf_hdrs["sec-fetch-dest"] = "document"
                cf_hdrs["sec-fetch-mode"] = "navigate"
                cf_hdrs["sec-fetch-site"] = "same-origin"
                cf_hdrs["sec-fetch-user"] = "?1"
                cf_hdrs["upgrade-insecure-requests"] = "1"
                r_bind_get = client.get(f"https://{server}/confirmemail.php", headers=cf_hdrs, timeout=timeout)
                _sync_response_cookies(client, r_bind_get)
            except Exception:
                pass
            return True
        else:
            logger.info(f"bind_facebook_session_email: GraphQL chưa nhận {clean_target} ({msg}), tiến hành web fallback...")
            is_explicit_die = any(bad in str(msg).lower() for bad in ("1501092823525282", "checkpoint/block", "checkpoint/disabled", "checkpoint/suspended", "help/103873106370583", "tài khoản của bạn đã bị tạm ngưng", "your account has been disabled"))
            if is_explicit_die:
                return False
    except Exception as ex_gql:
        logger.debug(f"bind_facebook_session_email GraphQL error: {ex_gql}")

    if not is_phone:
        try:
            ch_headers = dict(base_headers or {})
            if hasattr(client, "get_cookie_string"):
                ch_headers["cookie"] = client.get_cookie_string()
            r_ch = client.get(f"https://{server}/changeemail/", headers=ch_headers, timeout=timeout)
            p_ch = getattr(r_ch, "text", "") or ""
            m_dtsg = re.search(r'name="fb_dtsg" value="([^"]+)"', p_ch) or re.search(r'"token":"([^"]+)"', p_ch)
            ch_dtsg = m_dtsg.group(1) if m_dtsg else fb_dtsg
            m_jaz = re.search(r'name="jazoest" value="([^"]+)"', p_ch)
            ch_jaz = m_jaz.group(1) if m_jaz else jazoest
            m_old = re.search(r'name="old_email" value="([^"]+)"', p_ch)
            old_email = m_old.group(1) if m_old else ""
            m_inst = re.search(r'name="reg_instance" value="([^"]+)"', p_ch)
            inst_val = m_inst.group(1) if m_inst else reg_instance

            if not ch_dtsg:
                for probe_u in [f"https://{server}/confirmphone.php", f"https://{server}/confirmemail.php"]:
                    try:
                        r_cf = client.get(probe_u, headers=ch_headers, timeout=timeout, allow_redirects=True)
                        p_cf = getattr(r_cf, "text", "") or ""
                        m_dtsg2 = (
                            re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"\}', p_cf)
                            or re.search(r'(NAf[A-Za-z0-9_\-]+:\d+:\d+)', p_cf)
                            or re.search(r'name="fb_dtsg" value="([^"]+)"', p_cf)
                            or re.search(r'"token":"([^"]+)"', p_cf)
                        )
                        if m_dtsg2:
                            ch_dtsg = m_dtsg2.group(1)
                            break
                    except Exception:
                        pass

            set_headers = dict(ch_headers)
            set_headers.update({
                "origin": f"https://{server}",
                "referer": f"https://{server}/changeemail/",
                "content-type": "application/x-www-form-urlencoded",
            })
            set_payload = {
                "fb_dtsg": ch_dtsg,
                "jazoest": ch_jaz or (f"2{sum(ord(c) for c in ch_dtsg)}" if ch_dtsg else "2987"),
                "next": "",
                "old_email": old_email,
                "reg_instance": inst_val,
                "new": clean_target,
                "submit": "Thêm",
            }
            r_set = client.post(f"https://{server}/setemail/", data=set_payload, headers=set_headers, timeout=timeout)
            _sync_response_cookies(client, r_set)

            loc_val = str(getattr(r_set, "headers", {}).get("location") or getattr(r_set, "headers", {}).get("Location") or "").lower()
            text_val = str(getattr(r_set, "text", "")).lower() if isinstance(getattr(r_set, "text", ""), str) else ""

            is_set_ok = False
            if "confirmemail" in loc_val or clean_target.lower() in text_val or (r_set and r_set.status_code in (200, 302) and not text_val):
                is_set_ok = True
            else:
                try:
                    r_cf_check = client.get(f"https://{server}/confirmemail.php", headers=ch_headers, timeout=timeout)
                    _sync_response_cookies(client, r_cf_check)
                    cf_txt = getattr(r_cf_check, "text", "").lower()
                    if clean_target.lower() in cf_txt:
                        is_set_ok = True
                except Exception:
                    pass

            if is_set_ok:
                logger.info(f"bind_facebook_session_email: Đã fallback gắn email {clean_target} qua /setemail/!")
                return True
            else:
                logger.info(f"bind_facebook_session_email: Fallback /setemail/ chưa hoàn tất với {clean_target}.")
                return False
        except Exception as ex_web:
            logger.debug(f"bind_facebook_session_email fallback web error: {ex_web}")

    return False


bind_facebook_session_contactpoint = bind_facebook_session_email

SEED_PAGES_BY_COUNTRY = {

    "VN": ["vtv24", "thanhnien", "tuoitreonline", "vnexpress.net"],

    "US": ["cnn", "bbcnews", "nytimes", "natgeo"],

    "GB": ["bbcnews", "guardian", "telegraph"],

    "DE": ["spiegel", "zeitonline", "tagesschau"],

    "FR": ["lemonde.fr", "lefigaro", "france24"],

    "TH": ["thairath", "khaosod", "sanook"],

    "ID": ["detikcom", "kompascom", "tribunnews"],

    "PH": ["rappler", "abs-cbn", "gmanews"],

    "IN": ["ndtv", "timesofindia", "indiatoday"],

    "JP": ["nhk", "yomiuri.shimbun", "asahi.com"],

    "KR": ["chosun", "joongang", "donga"],

    "BR": ["g1", "uol", "folha"],

}

def _perform_anti_die_warmup(
    client: Any,
    server: str = "m.facebook.com",
    base_headers: Optional[Dict[str, str]] = None,
    geo_profile: Any = None,
    uid: str = "",
    emit: Optional[Callable[[str, dict], None]] = None,
) -> None:
    """
    BẢO VỆ CHỐNG DIE CHO TÀI KHOẢN MỚI TẠO (WARMUP PHIÊN TƯƠNG TÁC THẬT).
    Tương tác tự nhiên: Tải trang chủ Newsfeed và đọc báo địa phương theo quốc gia IP.
    Đồng bộ cookies mới nhất (datr, sb, wd, fr...) giúp tài khoản vượt qua kiểm duyệt anti-bot.
    """
    _emit = emit or (lambda evt, data: None)
    try:
        _emit("info", {"message": f"[🛡️ Anti-Die Warmup] Đang kích hoạt phiên tương tác thật cho UID {uid}...", "uid": uid})
        warmup_headers = dict(base_headers or {})
        warmup_headers["referer"] = f"https://{server}/confirmemail.php"

        # top-level is_chromium_ua
        cur_ua = warmup_headers.get("user-agent") or warmup_headers.get("User-Agent") or ""
        if not is_chromium_ua(cur_ua):
            clean_client_hints(warmup_headers, cur_ua)

        warmup_headers["sec-fetch-dest"] = "document"
        warmup_headers["sec-fetch-mode"] = "navigate"
        warmup_headers["sec-fetch-site"] = "same-origin"

        # 1. Truy cập nhẹ nhàng trang chủ Facebook (Home Feed / Splash) để đồng bộ session tự nhiên
        warmup_headers["sec-fetch-user"] = "?1"
        warmup_headers["upgrade-insecure-requests"] = "1"
        warmup_headers.pop("x-requested-with", None)
        warmup_headers.pop("X-Requested-With", None)

        r_home = client.get(f"https://{server}/home.php", headers=warmup_headers, timeout=6, allow_redirects=True)
        _sync_response_cookies(client, r_home)

        # 2. Tải asset tĩnh (favicon) tự nhiên như trình duyệt thật, xác thực CDN asset render
        try:
            fav_hdrs = dict(warmup_headers)
            fav_hdrs["accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
            fav_hdrs["sec-fetch-dest"] = "image"
            fav_hdrs["sec-fetch-mode"] = "no-cors"
            fav_hdrs["sec-fetch-site"] = "same-origin"
            fav_hdrs["referer"] = f"https://{server}/home.php"
            client.get(f"https://{server}/favicon.ico", headers=fav_hdrs, timeout=4)
        except Exception:
            pass

        _emit("info", {"message": f"[🛡️ Anti-Die Warmup] Hoàn tất kích hoạt phiên! Tài khoản UID {uid} đã được tương tác an toàn vào hệ thống."})
    except Exception as ex_wm:
        logger.debug(f"[Anti-Die Warmup Error] {ex_wm}")




class RegistrationService:

    """

    Clean Architecture service for web/mobile account registration.

    Input: RegistrationInput -> Output: RegistrationResult

    """



    def __init__(

        self,

        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,

        timeout: int = 30,

    ):

        self.event_callback = event_callback

        self.timeout = timeout



    def _emit_event(self, event_name: str, payload: Dict[str, Any]) -> None:
        if self.event_callback:
            try:
                self.event_callback(event_name, payload)
            except Exception as e:
                logger.debug(f"Event callback exception: {e}")

    def _emit(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Alias for _emit_event for compatibility with Mr-SxR create_task."""
        self._emit_event(event_name, payload)



    def generate_identity(

        self,

        password_seed: Optional[str] = None,

        locale: str = "vi_VN",

        name_type: Optional[str] = None,

        custom_file: str = "names.txt",

        mix_file_names: bool = False,

        geo_profile: Optional[Any] = None,

    ) -> Dict[str, Any]:

        """Sinh danh tính người dùng đa dạng tối đa hỗ trợ đa quốc gia và file tùy chỉnh."""

        from core.name_manager import NameManager



        gender_val = 2 if random.random() < 0.50 else 1

        sex_value = str(gender_val)



        chosen_type = name_type

        # Ưu tiên đồng bộ Họ Tên theo đúng Quốc gia & Nhà mạng của Proxy để tránh Checkpoint 282

        if geo_profile and getattr(geo_profile, "country_code", "").upper() == "VN" and chosen_type in ("global", "multinational"):

            chosen_type = "vietnamese"

        if chosen_type in (None, "", "auto_proxy") and geo_profile:

            c_code = getattr(geo_profile, "country_code", "").upper()

            country_map = {

                "VN": "vietnamese",

                "US": "western", "GB": "western", "CA": "western", "AU": "western", "DE": "western", "FR": "western",

                "TH": "thai", "CN": "chinese", "HK": "chinese", "TW": "chinese",

                "KR": "korean", "JP": "japanese", "IN": "indian", "ID": "indonesian",

                "PH": "filipino", "BR": "brazilian", "RU": "russian", "UA": "russian",

                "SA": "arabic", "AE": "arabic", "EG": "arabic",

            }

            chosen_type = country_map.get(c_code)

        if not chosen_type or chosen_type == "auto_proxy":

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



        # Phân tán ngày sinh tự nhiên: độ tuổi 20 đến 35 tuổi (1991 - 2006)

        current_year = 2026

        b_year = current_year - random.randint(20, 35)

        b_month = random.randint(1, 12)

        max_d = 28 if b_month == 2 else (30 if b_month in (4, 6, 9, 11) else 31)

        b_day = random.randint(1, max_d)



        from core.password_manager import generate_random_password

        if isinstance(password_seed, dict):
            if password_seed.get("type") == "fixed" and password_seed.get("value"):
                pwd = password_seed["value"]
            else:
                pwd = generate_random_password()
        elif isinstance(password_seed, str) and password_seed.strip():
            pwd = password_seed.strip()
        else:
            pwd = generate_random_password()



        from core.name_manager import NameManager
        full_n, first_n, last_n = NameManager.sanitize_facebook_name(gen_name.first_name, gen_name.last_name)

        return {
            "first_name": first_n,
            "last_name": last_n,
            "full_name": full_n,

            "sex_value": sex_value,

            "b_day": str(b_day),

            "b_month": str(b_month),

            "b_year": str(b_year),

            "password": pwd,

            "name_tag": gen_name.display_tag,

            "name_category": gen_name.category,

        }




    def register_legacy_nv(self, task_input: RegistrationInput) -> RegistrationResult:
        """
        Execute No-Verify (NV) registration flow using legacy Web/Mobile architecture from Mr-SxR.
        Uses classic device profiles (Android 4-8, KaiOS, Windows Phone, BlackBerry, iOS App)
        ?? ?p m?y ch? Facebook ph?c v? form HTML kinh ?i?n, tr?ch xu?t 10 security tokens v? thu nh?n session cookies (c_user, xs).
        """
        start_time = time.time()

        # Chuẩn hóa server domain nếu truyền vào dạng ID "1".."10" hoặc chế độ random / random subset
        server, server_tag = resolve_facebook_server(
            task_input.server,
            server_pool=task_input.extra.get("server_pool"),
            random_subset=task_input.extra.get("random_subset", False),
            random_server=task_input.extra.get("random_server", False),
        )

        # Chuẩn hóa device_type nếu truyền vào dạng ID "1".."6"
        dev_raw = str(task_input.device_type or "Android").strip()
        if dev_raw.lower() in ("mr_sxr", "android", "katana", "fb4a", "default", "none", ""):
            device_type = "Android"  # Khớp 100% Mr-SxR gốc: Android Browser (Chrome 32-48)
        elif dev_raw.lower() in ("random", "all"):
            device_type = random.choice(["Android", "AndroidApp", "IphoneApp"])
        else:
            device_type = LEGACY_DEVICE_TYPES.get(dev_raw, dev_raw)

        browser_type = task_input.browser_type or "Default"
        locale = task_input.locale or "en_US"
        wid = task_input.extra.get("worker_id", 1)

        def emit(event_name: str, payload: dict) -> None:
            if "worker_id" not in payload:
                payload["worker_id"] = wid
            self._emit_event(event_name, payload)

        # 1. Xác định chế độ xác minh Legacy: "none" | "setting" (email hoặc phone theo cấu hình)
        raw_leg_ver = str(task_input.extra.get("legacy_verify_mode", "none")).lower().strip()
        if raw_leg_ver in ("setting", "verify", "xm_setting", "true", "1"):
            # Tự động chọn Email hoặc SĐT dựa theo cấu hình hòm thư/SIM trong setting
            prov_name = str(task_input.extra.get("email_service", "")).lower()
            mtk_stype = str(task_input.extra.get("metaking_service_type", "")).lower()
            if prov_name == "metaking_phone" or mtk_stype == "phone" or "phone" in prov_name or "sdt" in prov_name:
                legacy_verify_mode = "phone"
            else:
                legacy_verify_mode = "email"
        elif raw_leg_ver in ("email", "mail", "email_vr", "vr_email"):
            legacy_verify_mode = "email"
        elif raw_leg_ver in ("phone", "sms", "sdt", "phone_vr", "vr_phone"):
            legacy_verify_mode = "phone"
        else:
            legacy_verify_mode = "none"

        # Đồng bộ hóa vị trí địa lý & MNO cho luồng
        # top-level GeoTelephonyResolver
        from core.proxy_manager import ProxyManager

        target_host = task_input.extra.get("proxy_ip", "") or ""
        if not target_host and task_input.proxy:
            try:
                p_parsed = ProxyManager.parse_proxy(task_input.proxy)
                if p_parsed:
                    target_host = p_parsed.real_ip or p_parsed.host
            except Exception:
                pass

        from core.geo_manager import normalize_country_code
        geo_profile = task_input.extra.get("geo_profile")
        raw_hint = task_input.extra.get("country_code") or task_input.extra.get("proxy_country")
        hint_c = normalize_country_code(raw_hint) if (raw_hint and str(raw_hint).lower() not in ("unknown", "none", "")) else None
        if not geo_profile and target_host and target_host not in ("Direct", "127.0.0.1", ""):
            try:
                geo_profile = GeoTelephonyResolver.resolve_ip(target_host, hint_country=hint_c, proxy=task_input.proxy)
            except Exception:
                pass
        elif not geo_profile and hint_c:
            try:
                geo_profile = GeoTelephonyResolver.get_profile_for_country(hint_c)
            except Exception:
                pass

        if not geo_profile:
            loc_country = "VN"
            if hint_c:
                loc_country = hint_c
            elif "_" in locale:
                loc_country = locale.split("_")[-1].upper()
            geo_profile = GeoTelephonyResolver.get_profile_for_country(loc_country)

        # 1. Generate identity sớm để mailbox và bait generator dùng tên thật người dùng
        fixed_pwd = task_input.password or task_input.extra.get("default_password") or task_input.extra.get("fixed_password")
        password_cfg = task_input.extra.get("password_config") or fixed_pwd
        identity = {
            "first_name": task_input.first_name or "",
            "last_name": task_input.last_name or "",
            "sex_value": str(task_input.gender or ""),
            "password": fixed_pwd or task_input.password or "",
        }
        if not (identity["first_name"] and identity["last_name"] and identity["password"]):
            n_type = task_input.extra.get("name_type")
            c_file = task_input.extra.get("custom_name_file", "names.txt")
            m_names = task_input.extra.get("mix_file_names", False)
            generated = self.generate_identity(
                password_seed=password_cfg,
                locale=locale,
                name_type=n_type,
                custom_file=c_file,
                mix_file_names=m_names,
                geo_profile=geo_profile,
            )
            for k, v in generated.items():
                if not identity.get(k):
                    identity[k] = v

        if not identity.get("b_day"):
            current_year = 2026
            b_yr = current_year - random.randint(20, 35)
            b_mo = random.randint(1, 12)
            max_d = 28 if b_mo == 2 else (30 if b_mo in (4, 6, 9, 11) else 31)
            identity["b_day"] = str(random.randint(1, max_d))
            identity["b_month"] = str(b_mo)
            identity["b_year"] = str(b_yr)

        if not identity.get("sex_value"):
            identity["sex_value"] = "2"

        full_name = f"{identity['first_name']} {identity['last_name']}".strip()
        from core.name_manager import NameManager
        full_name, identity["first_name"], identity["last_name"] = NameManager.sanitize_facebook_name(
            identity.get("first_name", ""),
            identity.get("last_name", "")
        )
        identity["full_name"] = full_name

        active_mailbox = None
        email_provider = None
        phone_provider = None
        real_email = ""
        mail_pass = ""
        mail_raw = ""
        mail_rest = ""
        target = ""
        submit_target = ""
        raw_bm = task_input.extra.get("bait_mode")
        if raw_bm:
            bait_mode = str(raw_bm).lower().strip()
        elif task_input.extra.get("use_bait_gmail"):
            bait_mode = "gmail"
        elif task_input.extra.get("use_bait_phone") is not None:
            bait_mode = "phone" if bool(task_input.extra.get("use_bait_phone")) else "none"
        elif task_input.extra.get("auto_gen_phone") is not None:
            bait_mode = "phone" if bool(task_input.extra.get("auto_gen_phone")) else "none"
        else:
            bait_mode = "none"
        if bait_mode not in ("phone", "gmail", "none"):
            bait_mode = "none"

        def _generate_bait_identifier(force_fresh: bool = False, force_mode: Optional[str] = None) -> str:
            bait_mode_cfg = str(force_mode or task_input.extra.get("bait_mode", "phone")).lower().strip()
            if bait_mode_cfg == "gmail":
                try:
                    # top-level generate_bait_gmail_identifier
                    fn = identity.get("first_name") or getattr(task_input, "first_name", None)
                    ln = identity.get("last_name") or getattr(task_input, "last_name", None)
                    return generate_bait_gmail_identifier(first_name=fn, last_name=ln)
                except Exception:
                    try:
                        from core.email_service import generate_bait_gmail_identifier
                        return generate_bait_gmail_identifier()
                    except Exception:
                        return f"user{random.randint(1992, 2005)}{random.randint(10, 99)}@gmail.com"
            c_code = getattr(geo_profile, "country_code", "") if geo_profile else ""
            if not c_code:
                c_code = task_input.extra.get("country_code") or task_input.extra.get("proxy_country") or ""
            if not c_code and target_host and target_host not in ("Direct", "127.0.0.1", ""):
                try:
                    g_res = GeoTelephonyResolver.resolve_ip(target_host, hint_country=hint_c, proxy=task_input.proxy)
                    c_code = getattr(g_res, "country_code", "VN")
                except Exception:
                    c_code = "VN"
            if not c_code:
                c_code = "VN"
            target_ip_val = None if force_fresh else target_host
            raw_phone = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=c_code, ip=target_ip_val, force_vn=False, force_fresh=force_fresh, e164=False)
            clean_digits = re.sub(r'[\s\-\(\)\+]', '', str(raw_phone).strip())
            if (c_code == "VN" or not c_code):
                if clean_digits.startswith("84") and len(clean_digits) in (11, 12):
                    clean_digits = f"0{clean_digits[2:]}"
                elif not clean_digits.startswith("0") and len(clean_digits) == 9:
                    clean_digits = f"0{clean_digits}"
            return clean_digits
        # Bộ cấp phát Mailbox an toàn theo đúng nhà cung cấp và tên miền người dùng yêu cầu 
        def _ensure_active_mailbox() -> Optional[Any]:
            nonlocal active_mailbox, email_provider, real_email, mail_pass, mail_raw, mail_rest
            if active_mailbox:
                return active_mailbox
            try:
                from core.email_service import get_email_provider
                prov_name = task_input.extra.get("email_service", "10minutemail")
                api_key = task_input.extra.get("dongvanfb_api_key") or task_input.extra.get("email_api_key")
                custom_doms = task_input.extra.get("selected_domains") or task_input.extra.get("selected_custom_domains")
                if "metaking" in str(prov_name).lower():
                    api_key = task_input.extra.get("metaking_api_key") or api_key
                    srv_type = task_input.extra.get("metaking_service_type", "email")
                    sid = 1
                    email_provider = get_email_provider(
                        prov_name,
                        api_key=api_key,
                        service_type=srv_type,
                        server=task_input.extra.get("metaking_server", 1),
                        domain=task_input.extra.get("metaking_domain", "hotmail.com"),
                        service_id=sid,
                        country_id=task_input.extra.get("metaking_country_id", 154),
                        price=task_input.extra.get("metaking_price", "low"),
                    )
                else:
                    email_provider = get_email_provider(prov_name, api_key=api_key, selected_domains=custom_doms)

                domain_target = task_input.extra.get("domain") or (task_input.extra.get("metaking_domain") if "metaking" in str(prov_name).lower() else None)
                if not domain_target:
                    custom_doms = task_input.extra.get("selected_domains") or task_input.extra.get("selected_custom_domains")
                    if custom_doms:
                        if isinstance(custom_doms, list) and len(custom_doms) == 1:
                            domain_target = custom_doms[0]
                        elif isinstance(custom_doms, list) and len(custom_doms) > 1:
                            domain_target = random.choice(custom_doms)
                        elif isinstance(custom_doms, str):
                            domain_target = custom_doms.split(",")[0].strip()
                    if not domain_target:
                        if "laoia_domain" in str(prov_name).lower():
                            domain_target = "laoia.com"
                        elif "smail1s_domain" in str(prov_name).lower():
                            domain_target = "smail1s.com"
                        elif "smailwork_domain" in str(prov_name).lower():
                            domain_target = "smailwork.com"

                for alloc_att in range(1, 4):
                    try:
                        active_mailbox = email_provider.create_mailbox(
                            proxy=task_input.proxy,
                            domain=domain_target,
                            worker_id=wid,
                            first_name=identity.get("first_name"),
                            last_name=identity.get("last_name"),
                            b_year=int(identity.get("b_year", 2000)),
                        )
                    except TypeError:
                        try:
                            active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target, worker_id=wid)
                        except TypeError:
                            try:
                                active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target)
                            except TypeError:
                                active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy)
                    if active_mailbox:
                        break
                    _safe_sleep(0.4 + (wid % 3) * 0.2)

                if active_mailbox:
                    real_email = active_mailbox.email
                    mail_pass = getattr(active_mailbox, "password", "") or ""
                    mail_meta = getattr(active_mailbox, "metadata", {}) or {}
                    mail_raw = mail_meta.get("raw_line") or getattr(active_mailbox, "raw_account", "") or ""
                    mail_rest = mail_raw.split("|", 1)[1] if (mail_raw and "|" in mail_raw) else mail_raw
                    return active_mailbox
            except Exception as e:
                logger.warning(f"[_ensure_active_mailbox] Lỗi khởi tạo hòm thư ({prov_name}): {e}")
            return None

        # Cấp phát thông tin định danh (Email / SĐT) tùy theo legacy_verify_mode
        if legacy_verify_mode == "email":
            raw_bm = task_input.extra.get("bait_mode")
            if raw_bm and str(raw_bm).lower().strip() == "gmail":
                bait_mode = "gmail"
            elif raw_bm and str(raw_bm).lower().strip() in ("none", "direct", "off", "no_bait", "email"):
                bait_mode = "none"
            elif task_input.extra.get("use_bait_phone") is False:
                bait_mode = "none"
            else:
                bait_mode = str(raw_bm).lower().strip() if raw_bm else "phone"

            if bait_mode in ("phone", "gmail"):
                # MỒI SĐT THEO IP (HOẶC GMAIL): Target đăng ký trên form Facebook chính là SĐT mồi
                submit_target = _generate_bait_identifier(force_mode=bait_mode)
                target = submit_target
                c_tag = f" [{geo_profile.phone_calling_code} {geo_profile.country_code}]" if (geo_profile and bait_mode == "phone") else ""
                b_title = "Mồi Gmail" if bait_mode == "gmail" else f"Mồi phone{c_tag}"
                emit("start", {"target": submit_target, "device_type": device_type, "server": server, "mode": "legacy_nv", "verify_mode": "email"})
                emit("info", {"message": f"[*] Khởi động Mr-SxR Legacy NV: {b_title} {submit_target} ➔ Xác minh Email theo cấu hình trên [{device_type}] -> {server_tag}"})
                if bait_mode == "phone" and geo_profile:
                    emit("info", {"message": f"[Mồi phiên] Đồng bộ đầu số SĐT mồi theo IP: {submit_target}{c_tag} (Quốc gia Proxy: {geo_profile.country_name})"})
            else:
                # Đăng ký trực tiếp bằng Email (không mồi SĐT)
                active_mailbox = _ensure_active_mailbox()
                if not active_mailbox:
                    elapsed = time.time() - start_time
                    err_msg = "Không thể cấp phát hòm thư 10MinuteMail  do mạng/proxy tạm thời nghẽn. Vui lòng thử lại!"
                    res = RegistrationResult(
                        success=False,
                        status="failed",
                        identifier="No-Mailbox",
                        error_message=err_msg,
                        elapsed_seconds=elapsed,
                    )
                    emit("error", {"message": err_msg})
                    emit("failed", {"result": res, "message": err_msg})
                    return res
                submit_target = real_email
                target = real_email
                emit("start", {"target": real_email, "device_type": device_type, "server": server, "mode": "legacy_nv", "verify_mode": "email"})
                emit("info", {"message": f"[*] Khởi động Mr-SxR Legacy NV: Đăng ký trực tiếp bằng Email {real_email}  trên [{device_type}] -> {server_tag}"})

        elif legacy_verify_mode == "phone":
            from core.email_service import MetakingEmailProvider
            metaking_key = (task_input.extra.get("metaking_api_key") or "").strip()
            if not metaking_key:
                try:
                    if os.path.exists("config.json"):
                        with open("config.json", "r", encoding="utf-8") as f_cfg:
                            cfg_d = json.load(f_cfg)
                            metaking_key = str(cfg_d.get("metaking_api_key", "")).strip()
                except Exception:
                    pass

            if metaking_key:
                try:
                    phone_provider = MetakingEmailProvider(
                        api_key=metaking_key,
                        service_type="phone",
                        service_id=67,
                        country_id=int(task_input.extra.get("metaking_country_id", 154)),
                    )
                    active_mailbox = phone_provider.create_mailbox(proxy=task_input.proxy)
                except Exception as ex_rent:
                    logger.warning(f"[Legacy VR Phone] Thuê SĐT Metaking lỗi: {ex_rent}")

            if active_mailbox and active_mailbox.email:
                target = str(active_mailbox.email).strip()
                email_provider = phone_provider
                submit_target = target
                emit("info", {"message": f"[Thuê SĐT Metaking] Đã thuê thành công SĐT {target} (ID: {active_mailbox.account_id}) để nhận OTP SMS."})
                emit("step", {"step": 1, "name": f"[Legacy VR SĐT] Nạp SĐT thuê {target}", "target": target})
            else:
                target = str(task_input.identifier or "").strip()
                if not target:
                    try:
                        from core.number_manager import get_next_number
                        target = get_next_number() or ""
                    except Exception:
                        target = ""
                if not target:
                    try:
                        target = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=getattr(geo_profile, "country_code", None), ip=target_host, e164=True)
                    except Exception:
                        target = "098" + str(random.randint(1000000, 9999999))
                submit_target = target
                email_provider = None
                emit("info", {"message": f"[Legacy VR SĐT] Sử dụng SĐT: {target}"})
                emit("step", {"step": 1, "name": f"[Legacy VR SĐT] Nạp SĐT {target}", "target": target})

            emit("start", {"target": target, "device_type": device_type, "server": server, "mode": "legacy_nv", "verify_mode": "phone"})
            emit("info", {"message": f"[*] Khởi động Mr-SxR Legacy NV + XÁC MINH SĐT trên [{device_type}] -> {server_tag} (Target: {target})"})

        else:
            # legacy_verify_mode == "none" (Bypass / NV nguyên bản)
            target = str(task_input.identifier or "").strip()
            if not target:
                try:
                    from core.number_manager import get_next_number
                    target = get_next_number() or ""
                except Exception:
                    target = ""
            if not target:
                bait_mode_cfg = str(task_input.extra.get("bait_mode", "phone")).lower().strip()
                if bait_mode_cfg == "gmail" or task_input.extra.get("use_bait_gmail"):
                    target = _generate_bait_identifier()
                else:
                    try:
                        target = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=getattr(geo_profile, "country_code", None), ip=target_host, e164=True)
                    except Exception:
                        target = "098" + str(random.randint(1000000, 9999999))
            submit_target = target
            email_provider = None
            active_mailbox = None

            emit("start", {"target": target, "device_type": device_type, "server": server, "mode": "legacy_nv", "verify_mode": "none"})
            emit("info", {"message": f"[*] Khởi động luồng Mr-SxR Legacy NV (Bypass - Không OTP) trên [{device_type}] -> {server_tag} (Target: {target})"})

        # 2. Identity đã được sinh từ trước để khớp hòm thư và mồi số

        client = None
        try:
            # 1. Sinh duy nhất 1 DeviceProfile chuẩn hóa theo thiết bị và liên kết vị trí địa lý của Proxy
            from core.session_builder import get_random_device_profile, setup_session_cookies, build_request_context
            profile = get_random_device_profile(device_type, geo_profile=geo_profile)

            from core.user_agent import (
                get_iphone_app_ua, get_android_app_ua, get_kaios_ua,
                get_windows_phone_ua, get_android_browser_ua, get_blackberry_ua
            )
            c_name = getattr(geo_profile, "carrier_name", None) if geo_profile else None
            loc_name = getattr(geo_profile, "locale", None) if geo_profile else None
            dev_name = str(device_type or "").lower()
            if "iphone" in dev_name or "ios" in dev_name:
                legacy_ua = get_iphone_app_ua(carrier=c_name, locale=loc_name)
                legacy_impersonate = "safari15_3"
            elif "androidapp" in dev_name or "katana" in dev_name or "fb4a" in dev_name:
                legacy_ua = get_android_app_ua(carrier=c_name, locale=loc_name)[0]
                legacy_impersonate = "chrome107"
            elif "android" in dev_name:
                legacy_ua = get_android_browser_ua()[0]
                legacy_impersonate = "chrome107"
            else:
                legacy_ua = get_android_browser_ua()[0]
                legacy_impersonate = "chrome107"

            base_type = device_type.split("_")[0] if "_" in device_type else device_type
            if base_type in ("IphoneApp", "iOS"):
                legacy_impersonate = "safari15_3"
            else:
                legacy_impersonate = "chrome107"
            profile.impersonate = legacy_impersonate
            profile.user_agent = legacy_ua

            client = HttpClient(
                impersonate=legacy_impersonate,
                device_type=device_type,
                proxy=task_input.proxy,
                timeout=self.timeout,
                profile=profile,
            )
            client.user_agent = legacy_ua
            setup_session_cookies(client, device_type=device_type, profile=profile)

            ctx = build_request_context(device_type, browser_type, locale, profile=profile, geo_profile=geo_profile)
            base_headers = ctx["base_headers"]

            emit("step", {"step": 1, "name": "fetch_reg_page", "target": submit_target or target, "server": server})

            # BƯỚC 1: GET /reg và trích xuất 10 security tokens bằng UA Mr-SxR cổ điển
            reg_get_ua = legacy_ua
            reg_get_headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "accept-language": base_headers.get("accept-language", f"{locale},en-US,en;q=0.9"),
                "upgrade-insecure-requests": "1",
                "user-agent": legacy_ua,
            }

            reg_urls = [
                f"https://{server}/reg?soft=hjk",
                f"https://{server}/reg",
            ]
            response_1 = ""
            candidate_lsd_html = ""
            for r_url in reg_urls:
                for get_attempt in range(2):
                    try:
                        resp_1 = client.get(r_url, headers=reg_get_headers, allow_redirects=True, timeout=max(22, int(self.timeout * 0.65)))
                        loc_cf = resp_1.headers.get("location") or ""
                        if isinstance(loc_cf, str) and loc_cf.startswith("fbredirect://"):
                            import urllib.parse
                            p_loc = urllib.parse.urlparse(loc_cf)
                            qs_loc = urllib.parse.parse_qs(p_loc.query)
                            target_uri = qs_loc.get("uri", [None])[0]
                            if target_uri:
                                wtsid = qs_loc.get("wtsid", [""])[0]
                                sep = "&" if "?" in target_uri else "?"
                                follow_url = f"{target_uri}{sep}wtsid={wtsid}&_rdr" if wtsid else target_uri
                                resp_1 = client.get(follow_url, headers=reg_get_headers, allow_redirects=True, timeout=max(22, int(self.timeout * 0.65)))
                        _sync_response_cookies(client, resp_1)
                        setup_session_cookies(client, device_type=device_type, profile=profile)
                        html_c = resp_1.text or ""
                        has_lsd = bool(_search(r'name="lsd" value="([^"]+)"', html_c) or _search(r'"lsd":\s*"([^"]+)"', html_c) or _search(r'\["LSD",\[\],\{"token":"([^"]+)"\}', html_c))
                        if has_lsd:
                            has_form = bool(_search(r'name="reg_instance" value="([^"]+)"', html_c) or _search(r'privacy_mutation_token=([^&]+)', html_c))
                            if has_form:
                                response_1 = html_c
                                import urllib.parse
                                actual_domain = urllib.parse.urlparse(r_url).netloc
                                if actual_domain and actual_domain != server:
                                    server = actual_domain
                                    server_tag = server
                                break
                            elif not candidate_lsd_html:
                                candidate_lsd_html = html_c
                    except (ProxyConnectionError, RequestTimeoutError) as p_err:
                        if get_attempt == 0:
                            if hasattr(client, "_reset_session_connections"):
                                client._reset_session_connections()
                            _safe_sleep(random.uniform(1.0, 1.8))
                            continue
                        elapsed = time.time() - start_time
                        res = RegistrationResult(
                            success=False,
                            status="error",
                            identifier=target,
                            error_message=f"Lỗi kết nối Proxy: {p_err}",
                            elapsed_seconds=elapsed,
                        )
                        emit("error", {"result": res, "message": f"Proxy Error: {p_err}"})
                        return res
                    except Exception:
                        break
                if response_1:
                    break

            # Nếu thiết bị hiện tại gặp 302 hoặc không trích xuất được LSD hoặc thiếu reg_instance, tự động fallback sang mobile web form
            if not response_1 or not _search(r'name="reg_instance" value="([^"]+)"', response_1):
                try:
                    fb_mob_headers = dict(reg_get_headers)
                    resp_fb = client.get(f"https://{server}/reg", headers=fb_mob_headers, allow_redirects=True, timeout=max(20, int(self.timeout * 0.6)))
                    _sync_response_cookies(client, resp_fb)
                    setup_session_cookies(client, device_type=device_type, profile=profile)
                    html_fb = resp_fb.text or ""
                    if _search(r'name="lsd" value="([^"]+)"', html_fb) or _search(r'"lsd":\s*"([^"]+)"', html_fb):
                        response_1 = html_fb
                except (ProxyConnectionError, RequestTimeoutError) as p_err:
                    elapsed = time.time() - start_time
                    res = RegistrationResult(
                        success=False,
                        status="error",
                        identifier=target,
                        error_message=f"Lỗi kết nối Proxy: {p_err}",
                        elapsed_seconds=elapsed,
                    )
                    emit("error", {"result": res, "message": f"Proxy Error: {p_err}"})
                    return res
                except Exception:
                    pass

            if not response_1 and candidate_lsd_html:
                response_1 = candidate_lsd_html

            ccp = _search(r'name="ccp" value="([^"]+)"', response_1) or "2"
            lsd = (
                _search(r'name="lsd" value="([^"]+)"', response_1)
                or _search(r'"lsd":\s*"([^"]+)"', response_1)
                or _search(r'\["LSD",\[\],\{"token":"([^"]+)"', response_1)
                or _search(r'"LSD",\[\],\{"token":"([^"]+)"', response_1)
                or _search(r'"token":"([^"]+)"', response_1)
            )
            jazoest = _search(r'name="jazoest" value="([^"]+)"', response_1) or (f"2{sum(ord(c) for c in lsd)}" if lsd else "")
            reg_instance = (
                _search(r'name="reg_instance" value="([^"]+)"', response_1)
                or _search(r'"reg_instance":\s*"([^"]+)"', response_1)
                or _search(r'\\?"reg_instance\\?":\s*\\?"([^\"]+)', response_1)
                or _search(r'([A-Za-z0-9_-]{20,30})"?\s+"?none"?\)\)\s+\(f4i\s+\(dkc[^\)]*reg_instance', response_1)
                or ""
            )
            reg_impression_id = (
                _search(r'name="reg_impression_id" value="([^"]+)"', response_1)
                or _search(r'"impressionId":\s*"([^"]+)"', response_1)
                or _search(r'"impression_id":\s*"([^"]+)"', response_1)
                or _search(r'\\?"impressionId\\?":\s*\\?"([^\"]+)', response_1)
                or _search(r'\\?"impression_id\\?":\s*\\?"([^\"]+)', response_1)
                or _search(r'([A-Za-z0-9_-]{20,30})"?\s+"?none"?\)\)\s+\(f4i\s+\(dkc[^\)]*reg_instance', response_1)
                or ""
            )
            ns_value = _search(r'name="ns" value="([^"]+)"', response_1) or "0"
            logger_id = (
                _search(r'name="logger_id" value="([^"]+)"', response_1)
                or _search(r'"logger_id":\s*"([^"]+)"', response_1)
                or _search(r'"lid":\s*"([^"]+)"', response_1)
                or _search(r'"lid"[:\s]+"([^"]+)"', response_1)
                or ""
            )
            encrypted_token = (
                _search(r'"encrypted"\s*:\s*"([^"]+)"', response_1)
                or _search(r'\\?"encrypted\\?"\s*:\s*\\?"([^\"]+)', response_1)
                or ""
            )
            fb_dtsg = (
                _search(r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', response_1)
                or _search(r'name="fb_dtsg" value="([^"]+)"', response_1)
                or _search(r'\["DTSGInitialData",\[\],\{"token":"([^"]+)"', response_1)
                or _search(r'\\?"token\\?":\s*\\?"(NAf[A-Za-z0-9_\-]+:\d+:\d+)', response_1)
                or ""
            )
            privacy_token = _search(r'privacy_mutation_token=([^&]+)', response_1) or ""
            if privacy_token:
                privacy_token = privacy_token.replace("%3D", "=")

            if not lsd:
                elapsed = time.time() - start_time
                res = RegistrationResult(
                    success=False,
                    status="error",
                    identifier=target,
                    error_message="Không trích xuất được LSD token từ Facebook",
                    elapsed_seconds=elapsed,
                )
                emit("error", {"result": res, "message": "Failed to parse LSD security token from /reg"})
                return res

            _safe_sleep(random.uniform(0.15, 0.35))
            emit("step", {"step": 2, "name": "submit_form", "target": submit_target or target, "server": server})

            # BƯỚC 2: POST /reg/submit/ (Khớp 100% Mr-SxR gốc)
            post_headers = dict(reg_get_headers)
            post_headers.update({
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded",
                "origin": f"https://{server}",
                "referer": f"https://{server}/reg?soft=hjk",
                "x-fb-lsd": lsd,
                "x-requested-with": "XMLHttpRequest",
                "x-response-format": "JSONStream",
            })
            post_headers.pop("upgrade-insecure-requests", None)
            post_headers.pop("sec-fetch-user", None)
            post_headers.pop("sec-fetch-dest", None)
            post_headers.pop("sec-fetch-mode", None)
            post_headers.pop("sec-fetch-site", None)
            post_headers.pop("x-asbd-id", None)
            post_headers.pop("priority", None)
            post_headers.pop("sec-ch-ua", None)
            post_headers.pop("sec-ch-ua-mobile", None)
            post_headers.pop("sec-ch-ua-platform", None)

            params = {
                "privacy_mutation_token": privacy_token,
                "multi_step_form": "1",
                "skip_suma": "0",
                "shouldForceMTouch": "1",
            }

            def _build_legacy_data(cand_target: str, attempt_idx: int = 0, current_html: str = "") -> dict:
                clean_target = str(cand_target).strip()
                if "@" not in clean_target:
                    clean_target = _format_e164_phone(clean_target, geo_profile=geo_profile)
                    if clean_target.startswith("+84"):
                        clean_target = f"0{clean_target[3:]}"
                    elif clean_target.startswith("+"):
                        clean_target = clean_target[1:]

                from core.email_service import get_random_comet_telemetry
                _telemetry = get_random_comet_telemetry()
                cur_encpass = f"#PWD_BROWSER:0:{int(time.time())}:{identity['password']}"
                try:
                    cur_ns = str(int(ns_value) + attempt_idx)
                except Exception:
                    cur_ns = str(attempt_idx)

                # Uu tien lay telemetry that duoc Meta render trong current_html hoac response_1
                src_html = current_html or response_1 or ""
                ext_dyn = _search(r'"__dyn"\s*:\s*"([^"]+)"', src_html) or _search(r'name="__dyn" value="([^"]+)"', src_html)
                ext_csr = _search(r'"__csr"\s*:\s*"([^"]+)"', src_html) or _search(r'name="__csr" value="([^"]+)"', src_html)
                ext_hsdp = _search(r'"__hsdp"\s*:\s*"([^"]+)"', src_html) or _search(r'name="__hsdp" value="([^"]+)"', src_html)
                ext_hblp = _search(r'"__hblp"\s*:\s*"([^"]+)"', src_html) or _search(r'name="__hblp" value="([^"]+)"', src_html)
                ext_sjsp = _search(r'"__sjsp"\s*:\s*"([^"]+)"', src_html) or _search(r'name="__sjsp" value="([^"]+)"', src_html)

                post_data = {
                    "ccp": ccp,
                    "reg_instance": reg_instance,
                    "submission_request": "true",
                    "helper": "",
                    "reg_impression_id": reg_impression_id,
                    "ns": cur_ns,
                    "zero_header_af_client": "",
                    "app_id": "",
                    "logger_id": logger_id,
                    "field_names[0]": "firstname",
                    "firstname": identity["first_name"],
                    "lastname": identity["last_name"],
                    "field_names[1]": "birthday_wrapper",
                    "birthday_day": identity.get("b_day", "15"),
                    "birthday_month": identity.get("b_month", "6"),
                    "birthday_year": identity.get("b_year", "1998"),
                    "age_step_input": "",
                    "did_use_age": "false",
                    "field_names[2]": "reg_email__",
                    "reg_email__": clean_target,
                    "field_names[3]": "sex",
                    "sex": identity["sex_value"],
                    "preferred_pronoun": "",
                    "custom_gender": "",
                    "field_names[4]": "reg_passwd__",
                    "name_suggest_elig": "true" if identity.get("did_use_suggested_name") == "true" else "false",
                    "was_shown_name_suggestions": "true" if identity.get("did_use_suggested_name") == "true" else "false",
                    "did_use_suggested_name": identity.get("did_use_suggested_name", "false"),
                    "use_custom_gender": "false",
                    "guid": "",
                    "pre_form_step": "",
                    "encpass": cur_encpass,
                    "fb_dtsg": fb_dtsg,
                    "jazoest": jazoest,
                    "lsd": lsd,
                    "__dyn": ext_dyn or "1Z3pawlEnwm8_Bg9ppoW5UdE4a2i5U4e0C86u7E39x60zU3ex608ewk9E4W0pKq0FE6S0x81vohw73wGwcq1GwqU2YwbK0oi0zE1jU1soG0hi0Lo6-0Co1kU1UU3jwGwbu",
                    "__csr": ext_csr or "",
                    "__hsdp": ext_hsdp or "",
                    "__hblp": ext_hblp or "",
                    "__sjsp": ext_sjsp or "",
                    "__req": "r",
                    "__fmt": "1",
                    "__a": encrypted_token,
                    "__user": "0",
                }
                # Khớp 100% Mr-SxR gốc: Không thêm các trường lạ (country_code, phone_country_code)
                return post_data

            raw_enable_retry = bool(task_input.extra.get("enable_bait_retry", True))
            raw_bait_retries = task_input.extra.get("bait_retries", 3)
            if not raw_enable_retry:
                max_retries = 0
            else:
                try:
                    max_retries = max(1, min(10, int(raw_bait_retries)))
                except Exception:
                    max_retries = 3

            candidate_targets = []
            clean_sub = str(submit_target).strip()
            if "@" not in clean_sub:
                clean_sub = _format_e164_phone(clean_sub, geo_profile=geo_profile)
                if clean_sub.startswith("+84"):
                    clean_sub = f"0{clean_sub[3:]}"
                elif clean_sub.startswith("+"):
                    clean_sub = clean_sub[1:]

            candidate_targets.append(clean_sub)
            if raw_enable_retry:
                # Cấp đủ số lượt mồi lại theo cài đặt: 1 lần tạo ban đầu + max_retries lượt mồi lại
                target_count = max_retries + 1
                gen_attempts = 0
                while len(candidate_targets) < target_count and gen_attempts < 40:
                    gen_attempts += 1
                    if bait_mode == "gmail" or (clean_sub and "@" in clean_sub and bait_mode != "phone"):
                        cand = generate_bait_gmail_identifier(first_name=identity.get("first_name"), last_name=identity.get("last_name"))
                    else:
                        c_code = getattr(geo_profile, "country_code", "VN") if geo_profile else "VN"
                        try:
                            raw_p = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=c_code, force_fresh=True, e164=False)
                            cand = _format_e164_phone(raw_p, geo_profile=geo_profile)
                        except Exception:
                            cand = _generate_bait_identifier(force_fresh=True, force_mode="phone")
                    cand_str = str(cand or "").strip()
                    if "@" not in cand_str:
                        cand_str = _format_e164_phone(cand_str, geo_profile=geo_profile)
                        if cand_str.startswith("+84"):
                            cand_str = f"0{cand_str[3:]}"
                        elif cand_str.startswith("+"):
                            cand_str = clean_digits = cand_str[1:]
                    if cand_str and cand_str not in candidate_targets:
                        candidate_targets.append(cand_str)
                    elif cand_str:
                        fake_suf = random.randint(1000, 9999)
                        if "@" in cand_str:
                            u_name, d_name = cand_str.split("@", 1)
                            candidate_targets.append(f"{u_name}{fake_suf}@{d_name}")
                        else:
                            candidate_targets.append(f"{cand_str[:-4]}{fake_suf}")
            elif legacy_verify_mode == "email" and real_email:
                if bait_mode == "none" and clean_sub != real_email and real_email not in candidate_targets:
                    candidate_targets.append(real_email)

            response_2 = None
            response_text = ""
            current_target = submit_target

            for cand_idx, cand_target in enumerate(candidate_targets):
                current_target = cand_target
                _redir_resp = None

                if cand_idx > 0:
                    if identity.get("did_use_suggested_name") == "true":
                        # Giữ nguyên tên đã được Meta gợi ý/chấp nhận
                        full_name = f"{identity['first_name']} {identity['last_name']}".strip()
                    else:
                        # ĐỔI THÔNG TIN MỚI CHO LƯỢT MỒI LẠI THEO YÊU CẦU:
                        n_type = task_input.extra.get("name_type")
                        c_file = task_input.extra.get("custom_name_file", "names.txt")
                        m_names = task_input.extra.get("mix_file_names", False)
                        new_gen = self.generate_identity(
                            password_seed=password_cfg,
                            locale=locale,
                            name_type=n_type,
                            custom_file=c_file,
                            mix_file_names=m_names,
                            geo_profile=geo_profile,
                        )
                        identity["first_name"] = new_gen.get("first_name", identity["first_name"])
                        identity["last_name"] = new_gen.get("last_name", identity["last_name"])
                        if not fixed_pwd:
                            identity["password"] = new_gen.get("password", identity["password"])

                        # Sinh ngày sinh mới
                        b_yr = 2026 - random.randint(20, 35)
                        b_mo = random.randint(1, 12)
                        max_d = 28 if b_mo == 2 else (30 if b_mo in (4, 6, 9, 11) else 31)
                        identity["b_day"] = str(random.randint(1, max_d))
                        identity["b_month"] = str(b_mo)
                        identity["b_year"] = str(b_yr)

                        full_name, identity["first_name"], identity["last_name"] = NameManager.sanitize_facebook_name(
                            identity.get("first_name", ""),
                            identity.get("last_name", "")
                        )
                        identity["full_name"] = full_name
                        identity["did_use_suggested_name"] = "false"

                    # Sinh target mới đúng 100% theo cài đặt cho lượt mồi lại
                    if bait_mode == "gmail" or (current_target and "@" in str(current_target) and bait_mode != "phone"):
                        current_target = generate_bait_gmail_identifier(first_name=identity.get("first_name"), last_name=identity.get("last_name"))
                    else:
                        c_code = getattr(geo_profile, "country_code", "VN") if geo_profile else "VN"
                        try:
                            raw_p = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=c_code, force_fresh=True, e164=False)
                            current_target = _format_e164_phone(raw_p, geo_profile=geo_profile)
                            if current_target.startswith("+84"):
                                current_target = f"0{current_target[3:]}"
                            elif current_target.startswith("+"):
                                current_target = current_target[1:]
                        except Exception:
                            current_target = cand_target

                    if not current_target:
                        current_target = cand_target
                    label_type = "SĐT mới" if "@" not in str(current_target) else "Gmail mới"
                    total_retries = max(1, len(candidate_targets) - 1)
                    emit("info", {"message": f"[Legacy NV Mồi Lại] Thử mồi lại lượt {cand_idx}/{total_retries} với thông tin mới (Tên: {full_name}, {label_type}: {current_target})..."})
                    # Giãn cách tự nhiên giữa các lần submit trên cùng IP để tránh Facebook WAF 1351050
                    _safe_sleep(random.uniform(0.8, 1.4))

                    r_html = ""
                    # Đặt lại cookies phiên sạch và refresh form trên Facebook (tránh mang trạng thái lỗi của lần trước)
                    try:
                        if hasattr(client, "clear_cookies"):
                            client.clear_cookies()
                        setup_session_cookies(client, device_type=device_type, profile=profile)

                        refresh_urls = [
                            f"https://{server}/reg?soft=hjk",
                            f"https://{server}/reg",
                            "https://mbasic.facebook.com/reg",
                        ]
                        for ref_u in refresh_urls:
                            r_refresh = client.get(ref_u, headers=reg_get_headers, allow_redirects=True, timeout=8)
                            _sync_response_cookies(client, r_refresh)
                            r_html = r_refresh.text or ""
                            new_inst = (
                                _search(r'name="reg_instance" value="([^"]+)"', r_html)
                                or _search(r'"reg_instance":\s*"([^"]+)"', r_html)
                            )
                            new_imp = (
                                _search(r'name="reg_impression_id" value="([^"]+)"', r_html)
                                or _search(r'"impressionId":\s*"([^"]+)"', r_html)
                                or _search(r'"impression_id":\s*"([^"]+)"', r_html)
                            )
                            new_lsd = (
                                _search(r'name="lsd" value="([^"]+)"', r_html)
                                or _search(r'"lsd":\s*"([^"]+)"', r_html)
                                or _search(r'\["LSD",\[\],\{"token":"([^"]+)"', r_html)
                            )
                            new_priv = _search(r'privacy_mutation_token=([^&]+)', r_html)
                            if new_inst:
                                reg_instance = new_inst
                            if new_imp:
                                reg_impression_id = new_imp
                            if new_lsd:
                                lsd = new_lsd
                                jazoest = f"2{sum(ord(c) for c in lsd)}"
                                post_headers["x-fb-lsd"] = lsd
                            if new_priv:
                                privacy_token = new_priv.replace("%3D", "=")
                                params["privacy_mutation_token"] = privacy_token
                            new_ns = _search(r'name="ns" value="([^"]+)"', r_html)
                            new_logger = _search(r'name="logger_id" value="([^"]+)"', r_html)
                            new_dtsg = _search(r'name="fb_dtsg" value="([^"]+)"', r_html) or _search(r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', r_html)
                            new_enc = _search(r'"encrypted"\s*:\s*"([^"]+)"', r_html) or _search(r'\\?"encrypted\\?"\s*:\s*\\?"([^\"]+)', r_html)
                            if new_ns:
                                ns_value = new_ns
                            if new_logger:
                                logger_id = new_logger
                            if new_dtsg:
                                fb_dtsg = new_dtsg
                            if new_enc:
                                encrypted_token = new_enc
                            if new_inst:
                                import urllib.parse
                                actual_ref_server = urllib.parse.urlparse(ref_u).netloc
                                if actual_ref_server and actual_ref_server != server:
                                    server = actual_ref_server
                                    post_headers["origin"] = f"https://{server}"
                                    post_headers["referer"] = f"https://{server}/reg?soft=hjk"
                                break
                    except Exception as ref_err:
                        logger.debug(f"[Legacy Mồi Lại] Refresh form session: {ref_err}")
                else:
                    # Mô phỏng thời gian người dùng thật điền form tự nhiên (Tránh WAF 1351050 do submit quá nhanh)
                    _safe_sleep(random.uniform(0.15, 0.35))
                data = _build_legacy_data(current_target, attempt_idx=cand_idx, current_html=locals().get("r_html", "") or response_1)

                # Thiết lập Cookie hiển thị di động tự nhiên khớp 100% repo Mr-SxR gốc
                try:
                    screen_res = random.choice(["320x480", "480x800", "540x960", "800x480", "854x480", "960x540", "720x1280", "1280x720", "1080x1920"])
                    client.set_cookie("m_pixel_ratio", "1", domain=f".{server}")
                    client.set_cookie("wd", screen_res, domain=f".{server}")
                except Exception:
                    pass

                # Giãn cách tần suất submit tự nhiên theo IP Proxy và đồng bộ khoá giữa các luồng dùng chung 1 IP
                proxy_slot_key = target_host or (task_input.proxy.real_ip if hasattr(task_input.proxy, "real_ip") and task_input.proxy.real_ip else str(task_input.proxy or ""))
                reg_ip_lock = ProxySubmitRateLimiter.get_ip_lock(proxy_slot_key)
                response_2 = None
                with reg_ip_lock:
                    ProxySubmitRateLimiter.wait_turn(proxy_slot_key, min_interval=random.uniform(1.2, 2.2), max_wait=6.0)
                    for post_attempt in range(2):
                        try:
                            response_2 = client.post(
                                f"https://{server}/reg/submit/",
                                params=params,
                                headers=post_headers,
                                data=data,
                                allow_redirects=False,
                                timeout=14,
                            )
                            if response_2 is not None:
                                break
                        except (ProxyConnectionError, RequestTimeoutError, HttpClientError) as p_err:
                            if post_attempt == 0:
                                if hasattr(client, "_reset_session_connections"):
                                    client._reset_session_connections()
                                _safe_sleep(random.uniform(0.5, 1.0))
                                continue
                            logger.warning(f"[Legacy Submit Error] Proxy error: {p_err}")
                            return RegistrationResult(
                                success=False,
                                status="failed",
                                error_message=f"Lỗi kết nối Proxy: {p_err}",
                                elapsed_seconds=round(time.time() - start_time, 2)
                            )
                    ProxySubmitRateLimiter.record_submit_finish(proxy_slot_key)

                if not response_2:
                    continue

                _sync_response_cookies(client, response_2)

                _raw_loc = response_2.headers.get("location") or response_2.headers.get("Location") or ""
                _is_cp_redirect = any(bad in _raw_loc.lower() for bad in ("checkpoint/block", "help/103873106370583"))
                is_302_success = (getattr(response_2, "status_code", 0) in (301, 302, 303)) and not _is_cp_redirect
                if getattr(response_2, "status_code", 0) in (301, 302, 303):
                    _loc = _raw_loc
                    if _loc:
                        _loc_uid = extract_facebook_uid(_loc, client.get_cookies(), client.get_cookie_string())
                        if _loc_uid and "c_user" not in client.get_cookies():
                            client.set_cookie("c_user", _loc_uid, domain=".facebook.com")
                        _redir_url = _loc if _loc.startswith("http") else f"https://{server}{_loc}"
                        _redir_hdrs = dict(reg_get_headers)
                        _redir_hdrs["referer"] = f"https://{server}/reg?soft=hjk"
                        _redir_hdrs["sec-fetch-dest"] = "document"
                        _redir_hdrs["sec-fetch-mode"] = "navigate"
                        _redir_hdrs["sec-fetch-site"] = "same-origin"
                        _redir_hdrs["sec-fetch-user"] = "?1"
                        _redir_hdrs["upgrade-insecure-requests"] = "1"
                        for _redir_att in range(2):
                            try:
                                _redir_resp = client.get(_redir_url, headers=_redir_hdrs, timeout=12, allow_redirects=True)
                                if _redir_resp is not None:
                                    _sync_response_cookies(client, _redir_resp)
                                    _final_u = getattr(_redir_resp, "url", "").lower()
                                    if any(bad in _final_u for bad in ("checkpoint/block", "help/103873106370583")):
                                        is_302_success = False
                                        _is_cp_redirect = True
                                    break
                            except Exception:
                                if hasattr(client, "_reset_session_connections"):
                                    client._reset_session_connections()
                                _safe_sleep(0.3)

                if _is_cp_redirect:
                    logger.warning(f"[Legacy Submit] Lượt mồi {cand_idx+1} bị Facebook chuyển hướng Checkpoint 282 ➔ Kích hoạt mồi lại...")
                    if cand_idx < len(candidate_targets) - 1:
                        continue

                cookies = client.get_cookies()
                response_text = getattr(response_2, "text", "") or ""
                if "_redir_resp" in locals() and _redir_resp and getattr(_redir_resp, "text", ""):
                    response_text = _redir_resp.text

                cand_uid = extract_facebook_uid(response_text, cookies, client.get_cookie_string())
                if cand_uid and "c_user" not in cookies:
                    cookies["c_user"] = cand_uid
                    client.set_cookie("c_user", cand_uid, domain=".facebook.com")

                should_probe = (
                    "c_user" not in cookies
                    and (
                        cookies.get("rs")
                        or is_302_success
                        or (
                            response_text
                            and any(k in response_text for k in ("confirmphone", "confirmemail", "checkpoint", "conf_code", "c_user"))
                        )
                    )
                )
                if should_probe:
                    probe_urls = [
                        f"https://{server}/confirmemail.php",
                        f"https://{server}/confirmphone.php"
                    ]
                    if "@" not in str(current_target):
                        probe_urls = [
                            f"https://{server}/confirmphone.php",
                            f"https://{server}/confirmemail.php"
                        ]
                    _p_hdrs = dict(reg_get_headers)
                    _p_hdrs["referer"] = f"https://{server}/reg?soft=hjk"
                    _p_hdrs["sec-fetch-dest"] = "document"
                    _p_hdrs["sec-fetch-mode"] = "navigate"
                    _p_hdrs["sec-fetch-site"] = "same-origin"
                    for probe_url in probe_urls:
                        try:
                            probe_resp = client.get(probe_url, headers=_p_hdrs, timeout=7, allow_redirects=True)
                            if probe_resp is not None:
                                _sync_response_cookies(client, probe_resp)
                                p_cookies = client.get_cookies()
                                p_uid = extract_facebook_uid(getattr(probe_resp, "text", ""), p_cookies, client.get_cookie_string())
                                if p_uid and "c_user" not in p_cookies:
                                    p_cookies["c_user"] = p_uid
                                    client.set_cookie("c_user", p_uid, domain=".facebook.com")
                                cookies = p_cookies
                                if cookies and any(k in cookies for k in ("c_user", "xs")):
                                    break
                        except Exception:
                            pass
                        if cookies and any(k in cookies for k in ("c_user", "xs")):
                            break

                # ĐẶC BIỆT QUAN TRỌNG: Nếu Facebook đã trả về 302 Redirect (Tạo nick thành công):
                # Tuyệt đối KHÔNG mồi lại vì tài khoản đã được Facebook tạo!
                if is_302_success:
                    if "c_user" not in cookies:
                        rescue_uid = extract_facebook_uid(cookie_str=client.get_cookie_string())
                        if rescue_uid:
                            cookies["c_user"] = rescue_uid
                            client.set_cookie("c_user", rescue_uid, domain=".facebook.com")
                    break

                if cookies and any(k in cookies for k in ("c_user", "xs")):
                    break

                decoded_resp_text = response_text
                try:
                    raw_j = response_text.split("for (;;);")[1] if "for (;;);" in response_text else response_text
                    parsed_j = json.loads(raw_j)
                    if isinstance(parsed_j, dict):
                        decoded_resp_text = json.dumps(parsed_j, ensure_ascii=False)
                except Exception:
                    pass

                clean_dec_text = re.sub(r'<[^>]+>', ' ', decoded_resp_text)
                resp_lower = (response_text + " " + clean_dec_text).lower()
                is_name_rejected = any(k in resp_lower for k in (
                    "chính sách tên", "tiêu đề", "ký hiệu", "tên thường dùng",
                    "tên bạn bè hay gọi", "title or symbol in your name", "name policy",
                    "names on facebook", "everyday name", "tên hoặc họ", "everyday life",
                    "friends call them", "we require everyone to use the name",
                    "did you mean", "có phải ý bạn là", "none of these", "không phải tên nào",
                    "vui lòng nhập tên", "tên không hợp lệ", "invalid name", "unusual name",
                    "use a real name", "character or symbol in your name", "suggested_name",
                    "tên thường dùng hàng ngày", "chúng tôi yêu cầu mọi người sử dụng tên"
                ))
                is_waf_1351050 = (
                    not is_name_rejected
                    and (
                        "1351050" in response_text
                        or "registration error" in resp_lower
                        or "error with your registration" in resp_lower
                        or "problem with your registration" in resp_lower
                        or "lỗi đăng ký" in resp_lower
                        or "lỗi đăng ký" in resp_lower
                        or "lỗi khi đăng ký" in resp_lower
                        or "erreur d’inscription" in resp_lower
                        or "erreur d'inscription" in resp_lower
                    )
                )
                if is_name_rejected:
                    sug_res = extract_facebook_suggested_name(clean_dec_text)
                    if sug_res:
                        sug_full, sug_first, sug_last = sug_res
                        identity["full_name"] = sug_full
                        identity["first_name"] = sug_first
                        identity["last_name"] = sug_last
                        identity["did_use_suggested_name"] = "true"
                        emit("info", {"message": f"[Legacy Cứu Tên] ⚡ Facebook gợi ý tên hợp lệ ➔ Tự động nhận tên Meta: {sug_full}..."})
                    else:
                        from core.name_manager import NameManager
                        safe_first = random.choice(NameManager.SAFE_FIRST_NAMES_MALE if identity.get("sex_value") == "2" else NameManager.SAFE_FIRST_NAMES_FEMALE)
                        safe_surname = random.choice(NameManager.SAFE_SURNAMES[:10])
                        full_name, identity["first_name"], identity["last_name"] = NameManager.sanitize_facebook_name(safe_first, safe_surname)
                        identity["full_name"] = full_name
                        identity["did_use_suggested_name"] = "true"
                        emit("info", {"message": f"[Legacy Cứu Tên] Facebook cảnh báo chính sách tên ➔ ⚡ Tự động đổi sang tên siêu sạch: {full_name}..."})

                    if cand_idx == len(candidate_targets) - 1 and raw_enable_retry:
                        candidate_targets.append(current_target)

                    next_idx = cand_idx + 1
                    if next_idx < len(candidate_targets):
                        if bait_mode == "gmail" or "@" in str(current_target):
                            candidate_targets[next_idx] = generate_bait_gmail_identifier(first_name=identity.get("first_name"), last_name=identity.get("last_name"))
                        else:
                            raw_p = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=getattr(geo_profile, "country_code", None), force_fresh=True)
                            candidate_targets[next_idx] = _format_e164_phone(raw_p, geo_profile=geo_profile).lstrip("+")
                    continue

                if is_waf_1351050:
                    identity["did_use_suggested_name"] = "false"
                    emit("warning", {
                        "message": "⚠️ Facebook từ chối biểu mẫu (Lỗi 1351050 - FB WAF chặn IP) ➔ IP đã bị chặn, dừng mồi lại để đổi IP mới!"
                    })
                    break

                is_fb_rejected = (
                    is_name_rejected
                    or "country_code_selector" in resp_lower
                    or "select your country" in resp_lower
                    or "vui lòng chọn quốc gia" in resp_lower
                    or "form_error" in resp_lower
                    or "error_summary" in resp_lower
                    or "errorsummary" in resp_lower
                    or "errordescription" in resp_lower
                    or ("error" in resp_lower and "registration" in resp_lower)
                    or not (cookies and any(k in cookies for k in ("c_user", "xs")))
                )
                if is_fb_rejected and cand_idx < len(candidate_targets) - 1:
                    total_retries = len(candidate_targets) - 1
                    attempt_cur = cand_idx + 1
                    retry_next = cand_idx + 1
                    fail_desc = "Facebook từ chối tên" if is_name_rejected else "Chưa nhận cookie phiên (c_user)"
                    emit("warning", {
                        "message": f"[Legacy NV Mồi Lại] ⚠️ Facebook từ chối ({fail_desc}) ở lượt {attempt_cur}/{len(candidate_targets)} ➔ Tự động mồi lại lượt {retry_next}/{total_retries} với thông tin mới..."
                    })
                    continue

            elapsed = time.time() - start_time

            # BƯỚC 3: Đánh giá kết quả auth cookies & Xác minh OTP nếu được yêu cầu
            if cookies and any(k in cookies for k in ("c_user", "xs")):
                uid = cookies.get("c_user", "")
                if not uid and hasattr(client, "get_cookie_string"):
                    try:
                        uid = extract_facebook_uid(response_text, cookies, client.get_cookie_string())
                    except Exception:
                        pass
                if not uid:
                    try:
                        r_cf_quick = client.get(f"https://{server}/confirmemail.php", timeout=8)
                        if r_cf_quick and getattr(r_cf_quick, "text", None):
                            uid = extract_facebook_uid(r_cf_quick.text, cookies, client.get_cookie_string())
                    except Exception:
                        pass
                if uid:
                    cookies["c_user"] = str(uid)
                    if hasattr(client, "set_cookie"):
                        try:
                            client.set_cookie("c_user", str(uid), domain=".facebook.com")
                        except Exception:
                            pass
                cookie_str = client.get_cookie_string()

                token_val = None
                if task_input.extra.get("extract_token") is True:
                    try:
                        src_text = locals().get("response_text", "") or locals().get("candidate_lsd_html", "") or ""
                        if src_text:
                            m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)
                            if m_eaab:
                                token_val = m_eaab.group(1)
                    except Exception:
                        pass

                # =============================================================
                # CHẾ ĐỘ A: legacy_verify_mode == "none" (Bypass / NV như hiện tại)
                # =============================================================
                if legacy_verify_mode == "none":
                    # Kiểm tra Checkpoint 282 ngay tại thời điểm hoàn tất submit/redirect
                    resp_check_str = str(locals().get("response_text", "")).lower()
                    is_immediate_cp = any(bad in resp_check_str for bad in (
                        "checkpoint/block", "help/103873106370583", "checkpoint/disabled",
                        "checkpoint/suspended", "tạm ngưng", "vô hiệu hóa", "suspended",
                        "1501092823525282", "kháng nghị"
                    ))

                    token_val = None
                    if task_input.extra.get("extract_token") is True:
                        try:
                            src_text = locals().get("response_text", "") or locals().get("candidate_lsd_html", "") or ""
                            if src_text:
                                m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)
                                if m_eaab:
                                    token_val = m_eaab.group(1)
                        except Exception:
                            pass

                    # BẢO VỆ PHIÊN NVR CHỐNG DIE:
                    # Với tài khoản đăng ký No-Verify bằng SĐT mồi (chưa xác minh OTP),
                    # TUYỆT ĐỐI KHÔNG gửi các request /home.php, /me, hoặc bật 2FA vì Meta sẽ phát hiện
                    # tài khoản chưa xác minh OTP nhảy cóc vào bảng tin -> lập tức kích hoạt Checkpoint 282!
                    # Giữ phiên an toàn nguyên vẹn trên màn hình confirm để lưu trữ vào accounts_unverified.txt!
                    if is_immediate_cp:
                        elapsed = round(time.time() - start_time, 2)
                        err_msg = "Tài khoản bị dính Checkpoint 282 ngay khi gửi biểu mẫu đăng ký"
                        res = RegistrationResult(
                            success=False,
                            status="die",
                            identifier=target,
                            phone=target if ("@" not in target) else None,
                            email=target if ("@" in target) else None,
                            uid=uid,
                            password=identity["password"],
                            token=token_val,
                            cookies=cookies,
                            cookie_string=cookie_str,
                            name=full_name,
                            error_message=err_msg,
                            elapsed_seconds=elapsed,
                            metadata={
                                "identity": identity,
                                "reg_mode": "legacy_nv",
                                "verify_mode": "none",
                                "device_type": device_type,
                                "server": server,
                                "checkpoint": True,
                                "die": True,
                            },
                        )
                        skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                        if not skip_file_save:
                            try:
                                die_file = task_input.extra.get("output_die_file", "accounts_die.txt")
                                with open(die_file, "a", encoding="utf-8-sig") as f_die:
                                    f_die.write(f"{uid or target}|{identity['password']}|{err_msg}|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            except Exception:
                                pass
                        emit("failed", {"result": res, "message": f"[Legacy NV] 🔴 UID {uid} bị Checkpoint 282 (DIE) ngay khi đăng ký"})
                        return res

                    # Trạng thái chuẩn xác khi chọn chế độ NV (Không OTP):
                    # Tài khoản tạo phiên thành công có UID & Cookie nhưng chưa xác minh OTP (vẫn ở form confirm)
                    # -> Phải phân loại là "unverified" (NVR / Chưa xác minh), LƯU VÀO accounts_unverified.txt, TUYỆT ĐỐI KHÔNG lưu accounts_live.txt!
                    elapsed = round(time.time() - start_time, 2)
                    eff_status = "unverified" if (uid and str(uid).isdigit() and len(str(uid)) >= 8) else "failed"
                    res = RegistrationResult(
                        success=False,
                        status=eff_status,
                        identifier=target,
                        phone=target if ("@" not in target) else None,
                        email=target if ("@" in target) else None,
                        uid=uid,
                        password=identity["password"],
                        token=token_val,
                        cookies=cookies,
                        cookie_string=cookie_str,
                        name=full_name,
                        birthday=f"{identity.get('b_day')}/{identity.get('b_month')}/{identity.get('b_year')}",
                        gender=identity["sex_value"],
                        elapsed_seconds=elapsed,
                        error_message="Chế độ Không OTP (Chưa xác minh / NVR - Còn sống, chưa thoát form xác minh OTP)",
                        metadata={
                            "identity": identity,
                            "reg_mode": "legacy_nv",
                            "verify_mode": "none",
                            "device_type": device_type,
                            "server": server,
                            "unverified": True,
                            "nvr": True,
                            "not_die": True,
                            "live_verified": False,
                        },
                    )

                    try:
                        from core.number_manager import remove_number
                        remove_number(target)
                    except Exception:
                        pass

                    skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                    if not skip_file_save:
                        try:
                            save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
                            record_line = res.format_line(save_fmt)
                            tag_suffix = "" if "|NVR" in record_line else "|NVR"
                            with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f_un:
                                f_un.write(record_line + tag_suffix + "\n")
                            with open("accounts.txt", "a", encoding="utf-8-sig") as f_all:
                                f_all.write(record_line + tag_suffix + "\n")
                        except Exception:
                            pass

                    emit("unverified", {"result": res, "message": f"[Legacy NV] 🟡 TẠO PHIÊN NVR THÀNH CÔNG: UID {uid} | Tên: {full_name} ➔ Đã lưu accounts_unverified.txt"})
                    return res
                elif legacy_verify_mode in ("email", "setting", "verify", "xm_setting", "true", "1"):
                    # 0. CHẾ ĐỘ CHỜ NGẤU TỰ ĐỘNG (SESSION MATURATION DELAY)
                    if task_input.extra.get("enable_account_maturation", False):
                        raw_mat = task_input.extra.get("account_maturation_delay", "60-120s (Ngẫu nhiên)")
                        mat_s = parse_maturation_delay_seconds(raw_mat, default=90.0)
                        emit("info", {
                            "message": f"⏳ [Chờ ngấu] Tạo phiên thành công UID {uid}. Đang chờ ngấu {int(mat_s)}s để phiên ổn định trên hệ thống Meta trước khi gắn mail (Chống Checkpoint 282)...",
                            "uid": uid
                        })
                        emit("step", {
                            "step": 4,
                            "name": f"Chờ ngấu tài khoản ({int(mat_s)}s)...",
                            "uid": uid,
                            "proxy": task_input.proxy
                        })
                        t_end = time.time() + mat_s
                        stop_evt = task_input.extra.get("stop_event")
                        while time.time() < t_end:
                            if stop_evt and stop_evt.is_set():
                                break
                            _safe_sleep(min(1.0, t_end - time.time()))
                    emit("info", {"message": f"[Legacy NV] ?? Mr-SxR ?? t?o xong t?i kho?n NVR! UID: {uid}. ?ang chuy?n ti?p sang b? m?y X?c Minh Acc NVR chu?n c?a tool...", "uid": uid, "target": submit_target})

                    # 1. L?U NGAY PHI?N T?I KHO?N NVR V?O accounts_unverified.txt & accounts.txt
                    # ??m b?o t?i kho?n NVR lu?n an to?n 100% tr?n ??a tr??c khi b?t ??u x?c minh
                    save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
                    unver_record = f"{uid}|{identity['password']}|{cookie_str}|NVR"
                    if real_email:
                        unver_record = f"{uid}|{identity['password']}|{cookie_str}|{real_email}|NVR"
                    skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                    if not skip_file_save:
                        try:
                            with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f_un:
                                f_un.write(unver_record + "\n")
                            with open("accounts.txt", "a", encoding="utf-8-sig") as f_all:
                                f_all.write(unver_record + "\n")
                        except Exception:
                            pass

                    # Cooldown 3.0s - 4.5s ?? Meta ??ng b? cluster ph?n t?n (Tr?nh trigger WAF ATO khi thao t?c qu? d?n d?p)
                    _safe_sleep(random.uniform(3.0, 4.5))

                    from core.nvr_verifier import verify_single_nvr_account
                    from core.email_service import get_email_provider

                    # 2. KH?I T?O D?CH V? EMAIL X?C MINH CHU?N X?C THEO ??NG C?U H?NH TOOL
                    eff_srv = str(task_input.extra.get("email_service", "clean_trio")).lower().strip()
                    eff_prov = email_provider
                    if not eff_prov:
                        if "hotmail" in eff_srv:
                            eff_mtk_dom = "hotmail.com"
                            eff_mtk_stype = "email"
                        elif "outlook" in eff_srv:
                            eff_mtk_dom = "outlook.com"
                            eff_mtk_stype = "email"
                        elif "icloud" in eff_srv:
                            eff_mtk_dom = "icloud.com"
                            eff_mtk_stype = "email"
                        elif "gmail" in eff_srv:
                            eff_mtk_dom = "gmail.com"
                            eff_mtk_stype = "email"
                        elif "phone" in eff_srv:
                            eff_mtk_dom = "hotmail.com"
                            eff_mtk_stype = "phone"
                        else:
                            eff_mtk_dom = task_input.extra.get("metaking_domain", "hotmail.com") or "hotmail.com"
                            eff_mtk_stype = task_input.extra.get("metaking_service_type", "email")

                        mtk_key = (task_input.extra.get("metaking_api_key") or "").strip()
                        if not mtk_key:
                            try:
                                if os.path.exists("config.json"):
                                    with open("config.json", "r", encoding="utf-8") as f_cfg:
                                        mtk_key = str(json.load(f_cfg).get("metaking_api_key", "")).strip()
                            except Exception:
                                pass

                        custom_doms = task_input.extra.get("selected_domains") or task_input.extra.get("selected_custom_domains")

                        if "metaking" in eff_srv:
                            eff_prov = get_email_provider(
                                eff_srv,
                                api_key=mtk_key,
                                service_type=eff_mtk_stype,
                                server=task_input.extra.get("metaking_server", 1),
                                domain=eff_mtk_dom,
                                service_id=(67 if eff_mtk_stype == "phone" else 1),
                                country_id=task_input.extra.get("metaking_country_id", 154),
                                price=task_input.extra.get("metaking_price", "low"),
                            )
                        else:
                            eff_prov = get_email_provider(eff_srv, api_key=mtk_key, selected_domains=custom_doms)

                    # 3. ??NG G?I D? LI?U T?I KHO?N KH?P 100% SMARTACCOUNTPARSER C?A CH? ?? X?C MINH NVR
                    acc_data = {
                        "uid": str(uid),
                        "password": identity["password"],
                        "two_factor_secret": "",
                        "cookie": cookie_str,
                        "token": token_val or "",
                        "email": real_email if (bait_mode == "none" and real_email) else "",
                        "email_password": mail_pass or "",
                        "email_raw": mail_raw or "",
                        "email_rest": mail_rest or "",
                        "refresh_token": "",
                        "client_id": "",
                        "proxy": task_input.proxy if isinstance(task_input.proxy, str) else "",
                        "is_registered_email": bool(bait_mode == "none" and real_email),
                        "mailbox": active_mailbox if (bait_mode == "none" and active_mailbox) else None,
                        "name": full_name,
                        "gender": identity.get("sex_value", "2"),
                        "birthday": f"{identity.get('b_day')}/{identity.get('b_month')}/{identity.get('b_year')}",
                        "raw_line": unver_record,
                        "detected_format": "UID|PASS|COOKIE",
                        "created_at": time.time(),
                    }

                    # 4. CHUY?N TASK INPUT SANG CH? ?? VERIFY_NVR CHU?N
                    xm_extra = dict(task_input.extra or {})
                    xm_extra["reg_mode"] = "verify_nvr"
                    xm_extra["skip_auto_file_save"] = False
                    xm_task_input = RegistrationInput(
                        identifier=task_input.identifier,
                        first_name=task_input.first_name,
                        last_name=task_input.last_name,
                        gender=task_input.gender,
                        birthday=task_input.birthday,
                        proxy=task_input.proxy,
                        device_type=task_input.device_type,
                        locale=task_input.locale,
                        server=task_input.server,
                        password=identity["password"],
                        browser_type=task_input.browser_type,
                        extra=xm_extra,
                    )

                    # 5. TI?N H?NH X?C MINH QUA B? M?Y X?C MINH ACC NVR CHU?N (HIGH LIVE RATE)
                    try:
                        res = verify_single_nvr_account(
                            account_data=acc_data,
                            email_provider=eff_prov,
                            task_input=xm_task_input,
                            emit_callback=emit,
                        )
                    except Exception as ex_xm:
                        logger.error(f"[Legacy NV XM] L?i trong qu? tr?nh x?c minh: {ex_xm}")
                        emit("warning", {"message": f"[Legacy NV XM] L?i x?c minh: {ex_xm} -> T?i kho?n v?n ? tr?ng th?i NVR an to?n (Kh?ng DIE)!"})
                        res = RegistrationResult(
                            success=False,
                            status="unverified",
                            uid=str(uid),
                            identifier=real_email or submit_target,
                            password=identity["password"],
                            token=token_val,
                            cookies=cookies,
                            cookie_string=cookie_str,
                            name=full_name,
                            error_message=f"L?i x?c minh: {ex_xm}",
                            metadata={"unverified": True, "nvr": True, "not_die": True, "reg_mode": "legacy_nv", "verify_mode": "email"},
                        )

                    # 6. ??NG B? TR?NG TH?I CU?I C?NG
                    if res.success:
                        if hasattr(res, "metadata") and isinstance(res.metadata, dict):
                            res.metadata["reg_mode"] = "legacy_nv"
                            res.metadata["verify_mode"] = "email"
                            res.metadata["verified_nvr"] = True
                            res.metadata["vr_verified"] = True
                            res.metadata["live_verified"] = True
                            res.metadata.pop("unverified", None)
                            res.metadata.pop("nvr", None)
                            res.metadata.pop("not_die", None)
                        emit("success", {"result": res, "message": f"[Legacy NV XM] ?? X?C MINH LIVE TH?NH C?NG CHO UID {uid}!"})
                        return res
                    else:
                        if hasattr(res, "metadata") and isinstance(res.metadata, dict):
                            res.metadata["reg_mode"] = "legacy_nv"
                            res.metadata["verify_mode"] = "email"
                            if res.status != "checkpoint":
                                res.status = "unverified"
                                res.metadata["unverified"] = True
                                res.metadata["nvr"] = True
                                res.metadata["not_die"] = True
                        return res

                # =============================================================
                # CHẾ ĐỘ C: legacy_verify_mode == "phone" (Xác minh Số điện thoại)
                # =============================================================
                elif legacy_verify_mode == "phone":
                    emit("step", {"step": 4, "name": f"Chờ mã OTP SMS gửi về SĐT {target}...", "target": target})
                    ok_confirm, otp_code, conf_link, confirm_text, active_mailbox, verified_target = self.retrieve_and_verify_otp(
                        client=client,
                        target=target,
                        email_provider=phone_provider or email_provider,
                        active_mailbox=active_mailbox,
                        server=server,
                        base_headers=base_headers,
                        fb_dtsg=fb_dtsg,
                        lsd=lsd,
                        jazoest=jazoest,
                        cur_uid=uid,
                        task_input=task_input,
                        emit_func=emit,
                    )

                    final_phone = verified_target or target
                    cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
                    cookie_str = client.get_cookie_string() if hasattr(client, "get_cookie_string") else ""
                    if "c_user" in cookies:
                        uid = cookies["c_user"]

                    # KIỂM ĐỊNH THỰC TẾ NGHIÊM NGẶT TRƯỚC KHI XẾP LOẠI & LƯU FILE
                    final_live_st = "unknown"
                    final_live_msg = ""
                    try:
                        final_live_st, final_live_msg = fb_checker.check_registration_account_live(
                            client=client,
                            server=server,
                            uid=uid,
                            proxy=task_input.proxy,
                            timeout=8
                        )
                    except Exception as e:
                        logger.debug(f"[Legacy VR SĐT] check_registration_account_live error: {e}")

                    if final_live_st in ("session_expired", "conn_error", "unknown", "") and (cookie_str or uid):
                        try:
                            st_fb, msg_fb = fb_checker.check_facebook_account_live_status(
                                cookie_str=cookie_str,
                                uid=uid,
                                proxy=task_input.proxy,
                                timeout=6
                            )
                            if st_fb in ("live", "die_282", "nvr"):
                                final_live_st = "die" if st_fb == "die_282" else st_fb
                                final_live_msg = msg_fb
                        except Exception as e:
                            logger.debug(f"[Legacy VR SĐT] fallback live check error: {e}")

                    is_really_live = (ok_confirm and final_live_st == "live") or (final_live_st == "live")
                    is_really_die = (final_live_st in ("die", "die_282")) or any(bad in str(final_live_msg or confirm_text).lower() for bad in ("tạm ngưng", "vô hiệu hóa", "suspended", "disabled", "checkpoint/block", "180 ngày", "180 days"))

                    if is_really_live and not is_really_die:
                        if task_input.extra.get("session_warmup", True):
                            _perform_anti_die_warmup(client, server, base_headers, geo_profile, uid, emit)
                            cookies = client.get_cookies() if hasattr(client, "get_cookies") else cookies
                            cookie_str = client.get_cookie_string() if hasattr(client, "get_cookie_string") else cookie_str

                        totp_secret = None
                        if task_input.extra.get("enable_2fa", False):
                            try:
                                ok_2fa, sec_2fa, _, _ = enable_facebook_2fa(
                                    client=client,
                                    uid=uid,
                                    password=identity.get("password", ""),
                                    cookies=cookies,
                                    server=server,
                                )
                                if ok_2fa and sec_2fa:
                                    totp_secret = sec_2fa
                            except Exception as e:
                                logger.debug(f"2FA enable error: {e}")

                        token_val = None
                        if task_input.extra.get("extract_token") is True:
                            try:
                                src_text = locals().get("response_text", "") or ""
                                if src_text:
                                    m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)
                                    if m_eaab:
                                        token_val = m_eaab.group(1)
                            except Exception:
                                pass

                        res = RegistrationResult(
                            success=True,
                            status="live",
                            identifier=final_phone,
                            phone=final_phone,
                            uid=uid,
                            password=identity["password"],
                            token=token_val,
                            cookies=cookies,
                            cookie_string=cookie_str,
                            two_factor_secret=totp_secret,
                            name=full_name,
                            birthday=f"{identity.get('b_day')}/{identity.get('b_month')}/{identity.get('b_year')}",
                            gender=identity["sex_value"],
                            elapsed_seconds=round(time.time() - start_time, 2),
                            metadata={
                                "identity": identity,
                                "reg_mode": "legacy_nv",
                                "verify_mode": "phone",
                                "vr_verified": True,
                                "live_verified": True,
                                "device_type": device_type,
                                "server": server,
                            },
                        )

                        skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                        if not skip_file_save:
                            try:
                                save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
                                record_line = res.format_line(save_fmt)
                                for out_f in ["accounts_live.txt", "accounts.txt"]:
                                    with open(out_f, "a", encoding="utf-8-sig") as f:
                                        f.write(record_line + "\n")
                            except Exception:
                                pass

                        emit("success", {"result": res, "message": f"[Legacy VR SĐT] 🟢 LIVE THỰC TẾ! UID: {uid} | SĐT: {final_phone} ({final_live_msg})"})
                        return res

                    elif is_really_die:
                        res = RegistrationResult(
                            success=False,
                            status="checkpoint",
                            identifier=final_phone,
                            phone=final_phone,
                            uid=uid,
                            password=identity["password"],
                            cookies=cookies,
                            cookie_string=cookie_str,
                            name=full_name,
                            error_message=f"Dính Checkpoint 282: {final_live_msg or confirm_text}",
                            elapsed_seconds=round(time.time() - start_time, 2),
                            metadata={
                                "identity": identity,
                                "reg_mode": "legacy_nv",
                                "verify_mode": "phone",
                                "checkpoint": True,
                                "die": True,
                                "error": final_live_msg or confirm_text,
                                "device_type": device_type,
                                "server": server,
                            },
                        )
                        skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                        if not skip_file_save:
                            try:
                                die_file = task_input.extra.get("output_die_file", "accounts_die.txt")
                                with open(die_file, "a", encoding="utf-8-sig") as f_die:
                                    f_die.write(f"{uid or final_phone}|{identity['password']}|{res.error_message}|{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            except Exception:
                                pass

                        emit("failed", {"result": res, "message": f"[Legacy VR SĐT] 🔴 DIE / Checkpoint 282: {final_live_msg or confirm_text}", "uid": uid, "phone": final_phone})
                        return res

                    else:
                        eff_status = "unverified" if (uid and str(uid).isdigit() and len(str(uid)) >= 8) else "failed"
                        res = RegistrationResult(
                            success=False,
                            status=eff_status,
                            identifier=final_phone,
                            phone=final_phone,
                            uid=uid,
                            password=identity["password"],
                            token=token_val if 'token_val' in locals() else None,
                            cookies=cookies,
                            cookie_string=cookie_str,
                            name=full_name,
                            error_message=final_live_msg or confirm_text or "Chưa hoàn tất xác minh mã OTP SMS",
                            elapsed_seconds=round(time.time() - start_time, 2),
                            metadata={
                                "identity": identity,
                                "reg_mode": "legacy_nv",
                                "verify_mode": "phone",
                                "unverified": True,
                                "nvr": True,
                                "not_die": True,
                                "device_type": device_type,
                                "server": server,
                            },
                        )
                        skip_file_save = task_input.extra.get("skip_auto_file_save", False)
                        if not skip_file_save:
                            try:
                                save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")
                                record_line = res.format_line(save_fmt)
                                tag_suffix = "" if "|NVR" in record_line else "|NVR"
                                with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f_un:
                                    f_un.write(record_line + tag_suffix + "\n")
                                with open("accounts.txt", "a", encoding="utf-8-sig") as f_all:
                                    f_all.write(record_line + tag_suffix + "\n")
                            except Exception:
                                pass

                        emit("unverified", {"result": res, "message": f"[Legacy VR SĐT] 🟡 CHƯA XÁC MINH (NVR) UID {uid}: {final_live_msg or confirm_text}", "uid": uid, "phone": final_phone})
                        return res
            else:
                debug_msg = "Unknown Error"
                try:
                    err_data = json.loads(response_text.split("for (;;);")[1]) if "for (;;);" in response_text else json.loads(response_text)
                    if isinstance(err_data, dict):
                        err_code = err_data.get("error")
                        err_sum = err_data.get("errorSummary")
                        err_desc = err_data.get("errorDescription")
                        if err_desc or err_sum:
                            debug_msg = f"{err_sum or ''}: {err_desc or ''} (Mã {err_code or ''})".strip()
                        elif "payload" in err_data and isinstance(err_data["payload"], dict):
                            payload_obj = err_data["payload"]
                            actions = payload_obj.get("actions") or []
                            extracted_err = ""
                            if isinstance(actions, list):
                                for act in actions:
                                    if isinstance(act, dict):
                                        h_val = str(act.get("html") or "")
                                        if h_val:
                                            clean_txt = re.sub(r'<[^>]+>', ' ', h_val).strip()
                                            if clean_txt:
                                                extracted_err = clean_txt
                                                break
                            if extracted_err:
                                debug_msg = extracted_err
                            elif "error" in payload_obj:
                                debug_msg = str(payload_obj["error"])
                            else:
                                debug_msg = "Facebook từ chối biểu mẫu (Lỗi WAF 1351050)"
                        else:
                            debug_msg = str(err_data)[:180]
                    else:
                        debug_msg = str(err_data)[:180]
                except Exception:
                    debug_msg = response_text.replace("\n", " ")[:200]

                res = RegistrationResult(
                    success=False,
                    status="failed",
                    identifier=current_target or target,
                    password=identity["password"],
                    name=full_name,
                    error_message=f"Facebook Error: {debug_msg}",
                    elapsed_seconds=elapsed,
                )
                emit("failed", {"result": res, "message": f"Facebook Error: {debug_msg}"})
                return res

        except ProxyConnectionError:
            elapsed = time.time() - start_time
            res = RegistrationResult(
                success=False,
                status="error",
                identifier=target,
                error_message="L?i k?t n?i Proxy",
                elapsed_seconds=elapsed,
            )
            emit("error", {"result": res, "message": "Proxy Connection Error"})
            return res
        except RequestTimeoutError:
            elapsed = time.time() - start_time
            res = RegistrationResult(
                success=False,
                status="error",
                identifier=target,
                error_message="H?t th?i gian ch? (Timeout)",
                elapsed_seconds=elapsed,
            )
            emit("error", {"result": res, "message": "Request Timeout Error"})
            return res
        except Exception as e:
            elapsed = time.time() - start_time
            res = RegistrationResult(
                success=False,
                status="error",
                identifier=target,
                error_message=str(e),
                elapsed_seconds=elapsed,
            )
            emit("error", {"result": res, "message": f"Exception: {e}"})
            return res
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    def retrieve_and_verify_otp(
        self,
        client: Any,
        target: str,
        email_provider: Any,
        active_mailbox: Any,
        server: str = "m.facebook.com",
        base_headers: Optional[Dict[str, str]] = None,
        fb_dtsg: str = "",
        lsd: str = "",
        jazoest: str = "",
        cur_uid: str = "",
        task_input: Optional[RegistrationInput] = None,
        emit_func: Optional[Callable[[str, dict], None]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str], str, Any, str]:
        emit = emit_func or (lambda evt, data: None)
        extra = task_input.extra if (task_input and hasattr(task_input, "extra")) else {}
        proxy = getattr(task_input, "proxy", None)
        wid_val = extra.get("worker_id", 1)
        base_headers = dict(base_headers or {})
        cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
        ck_str = client.get_cookie_string() if hasattr(client, "get_cookie_string") and isinstance(client.get_cookie_string(), str) else ""
        if not cur_uid:
            cur_uid = cookies.get("c_user", "") or extract_facebook_uid(cookies=cookies, cookie_str=ck_str)
        init_live_st = ""
        init_live_msg = ""
        is_dead_checkpoint = False

        try:
            HumanBehaviorDynamics.sample_cognitive_pause(min_sec=1.2, max_sec=2.6)
        except Exception:
            pass

        endpoint_page = "confirmphone.php" if ("@" not in str(target) and str(target).strip()) else "confirmemail.php"
        try:
            conf_init_hdrs = dict(base_headers)
            conf_init_hdrs["referer"] = f"https://{server}/reg"
            r_conf_init = client.get(f"https://{server}/{endpoint_page}", headers=conf_init_hdrs, timeout=10)
            _sync_response_cookies(client, r_conf_init)
            if r_conf_init and getattr(r_conf_init, "text", None):
                p_conf = r_conf_init.text
                cand_cf = extract_facebook_uid(p_conf, cookies, client.get_cookie_string() if hasattr(client, "get_cookie_string") else "")
                if cand_cf:
                    cur_uid = cand_cf
                    if "c_user" not in cookies:
                        cookies["c_user"] = cur_uid
                m_dtsg_c = re.search(r'"DTSGInitialData",\[\],\{"token":"([^"]+)"\}', p_conf) or re.search(r'name="fb_dtsg" value="([^"]+)"', p_conf) or re.search(r'"token":"([^"]+)"', p_conf)
                if m_dtsg_c:
                    fb_dtsg = m_dtsg_c.group(1)
                m_lsd_c = re.search(r'name="lsd" value="([^"]+)"', p_conf) or re.search(r'"LSD",\[\],\{"token":"([^"]+)"\}', p_conf)
                if m_lsd_c:
                    lsd = m_lsd_c.group(1)
        except Exception as e:
            logger.debug(f"Init {endpoint_page} probe error: {e}")

        emit("step", {"step": 4, "name": f"Chờ mã OTP Facebook gửi về {target}...", "target": target, "uid": cur_uid, "email": target, "proxy": proxy})
        otp_timeout = int(extra.get("otp_timeout", 20))
        otp_res = None
        if email_provider and active_mailbox:
            try:
                otp_res = email_provider.wait_for_otp(
                    account=active_mailbox,
                    timeout_seconds=otp_timeout,
                    proxy=proxy,
                )
            except Exception as ex_wait:
                logger.debug(f"wait_for_otp round 1 error: {ex_wait}")

        if not getattr(otp_res, "success", False) and not getattr(otp_res, "otp_code", None) and not getattr(otp_res, "confirmation_link", None):
            try:
                emit("info", {"message": f"[Resend OTP] Đang kích hoạt Meta gửi lại mã OTP tới {target}...", "uid": cur_uid, "email": target, "proxy": proxy})
                trigger_facebook_confirmation_resend(
                    client=client,
                    server=server,
                    target=target,
                    base_headers=base_headers,
                    fb_dtsg=fb_dtsg,
                    lsd=lsd,
                    jazoest=jazoest,
                    cur_uid=cur_uid,
                    timeout=8,
                )
                if email_provider and hasattr(email_provider, "request_next_otp"):
                    try:
                        email_provider.request_next_otp(active_mailbox)
                    except Exception:
                        pass
                _safe_sleep(2.0)
                if email_provider and active_mailbox:
                    otp_res2 = email_provider.wait_for_otp(
                        account=active_mailbox,
                        timeout_seconds=min(15, otp_timeout),
                        proxy=proxy,
                    )
                    if getattr(otp_res2, "success", False) and (getattr(otp_res2, "otp_code", None) or getattr(otp_res2, "confirmation_link", None)):
                        otp_res = otp_res2
            except Exception as ex_res:
                logger.debug(f"Resend OTP trigger error: {ex_res}")

        is_otp_ok = getattr(otp_res, "success", False)
        otp_code = getattr(otp_res, "otp_code", None)
        conf_link = getattr(otp_res, "confirmation_link", None)
        res_meta = getattr(otp_res, "metadata", None)
        if not conf_link and res_meta and isinstance(res_meta, dict):
            conf_link = res_meta.get("confirmation_link")

        ok_confirm = False
        confirm_text = ""

        if is_otp_ok and (otp_code or conf_link):
            try:
                _safe_sleep(sum([HumanBehaviorDynamics.sample_keystroke_flight_time() * 0.1 for _ in str(otp_code or "")]) + 0.3)
            except Exception:
                pass
            emit("info", {"message": f"Bắt được mã OTP: {otp_code}" if otp_code else "Bắt được link xác minh", "uid": cur_uid, "email": target, "proxy": proxy})
            emit("step", {"step": 5, "name": f"Gửi mã OTP '{otp_code}' xác minh với Facebook", "target": target, "uid": cur_uid, "email": target, "proxy": proxy})

            cur_cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
            cur_uid = cur_cookies.get("c_user", "") or cur_uid or ""

            ok_confirm, confirm_text = email_service.submit_facebook_web_email_otp(
                session=client,
                server=server,
                otp_code=otp_code or "",
                headers=base_headers,
                confirmation_link=conf_link,
                email=target,
                fb_dtsg=fb_dtsg,
                lsd=lsd,
                uid=cur_uid,
                enable_otp_pacing=task_input.extra.get("enable_otp_pacing", True),
                pacing_min=float(task_input.extra.get("otp_pacing_min", 2.0)),
                pacing_max=float(task_input.extra.get("otp_pacing_max", 3.5)),
                proxy_ip=task_input.extra.get("proxy_ip"),
                emit_callback=emit,
            )
            if ok_confirm:
                _safe_sleep(random.uniform(0.8, 1.4))

            cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
            cur_uid = cookies.get("c_user", "") or cur_uid or ""

            # Sau khi submit OTP: BẮT BUỘC kiểm định trạng thái phiên thực tế qua probe
            emit("step", {"step": 6, "name": f"Kiểm định trạng thái tài khoản sau OTP ({cur_uid or target})...", "target": target, "uid": cur_uid, "email": target, "proxy": proxy})
            init_live_st = "unknown"
            init_live_msg = ""
            try:
                init_live_st, init_live_msg = fb_checker.check_registration_account_live(
                    client=client,
                    server=server,
                    uid=cur_uid,
                    proxy=proxy,
                    timeout=8
                )
            except Exception as e:
                logger.debug(f"check_registration_account_live exception: {e}")
                init_live_st, init_live_msg = "unknown", str(e)

            if init_live_st in ("session_expired", "conn_error", "unknown", "") and hasattr(client, "get_cookie_string"):
                try:
                    ck_st, ck_msg = fb_checker.check_facebook_account_live_status(
                        cookie_str=client.get_cookie_string(), uid=cur_uid, proxy=proxy, timeout=5
                    )
                    if ck_st == "live":
                        init_live_st, init_live_msg = "live", ck_msg
                    elif ck_st in ("die_282", "die"):
                        init_live_st, init_live_msg = "die", ck_msg
                    elif ck_st == "nvr":
                        init_live_st, init_live_msg = "nvr", ck_msg
                except Exception:
                    pass

            if init_live_st in ("die", "die_282"):
                ok_confirm = False
                is_dead_checkpoint = True
                confirm_text = f"Tài khoản dính Checkpoint 282 (DIE: {init_live_msg})"
                emit("error", {"message": f"❌ Xác thực OTP thất bại: {confirm_text}", "email": target, "uid": cur_uid})
            elif init_live_st == "live":
                ok_confirm = True
                confirm_text = init_live_msg or "Tài khoản LIVE!"
                emit("verified", {"message": f"🎉 Xác thực OTP '{otp_code}' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({confirm_text})", "email": target, "uid": cur_uid})
            elif init_live_st == "nvr":
                if ok_confirm:
                    try:
                        d_hdrs = dict(base_headers or {})
                        d_hdrs['referer'] = f'https://{server}/{endpoint_page}'
                        client.get(f'https://{server}/home.php', headers=d_hdrs, timeout=6, allow_redirects=True)
                    except Exception:
                        pass
                    ok_confirm = True
                    confirm_text = "Đã giải phóng onboarding sang LIVE"
                    emit("verified", {"message": f"🟢 Xác thực OTP '{otp_code}' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({confirm_text})", "email": target, "uid": cur_uid})
                else:
                    confirm_text = f"Tài khoản vẫn ở form xác minh OTP ({init_live_msg}) - Chưa thoát form!"
                    emit("warning", {"message": f"⚠️ Sau khi nhập OTP '{otp_code}' Facebook vẫn chuyển hướng về form xác minh ({init_live_msg}). Cần tiếp tục đổi email để xác minh lại...", "email": target, "uid": cur_uid})
            else:
                if ok_confirm:
                    try:
                        d_hdrs = dict(base_headers or {})
                        d_hdrs['referer'] = f'https://{server}/{endpoint_page}'
                        client.get(f'https://{server}/home.php', headers=d_hdrs, timeout=6, allow_redirects=True)
                    except Exception:
                        pass
                    ok_confirm = True
                    confirm_text = "Đã giải phóng onboarding sang LIVE"
                    emit("verified", {"message": f"🟢 Xác thực OTP '{otp_code}' thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({confirm_text})", "email": target, "uid": cur_uid})
                else:
                    confirm_text = f"Tài khoản vẫn ở form xác minh OTP ({init_live_msg}) - Chưa thoát form!"
                    emit("warning", {"message": f"⚠️ Sau khi nhập OTP '{otp_code}' Facebook vẫn chuyển hướng về form xác minh ({init_live_msg}). Cần tiếp tục đổi email để xác minh lại...", "email": target, "uid": cur_uid})
        else:
            otp_err = getattr(otp_res, "error", None) or "Hết thời gian chờ"
            confirm_text = f"Không nhận được OTP từ hòm thư ({otp_err})"
            emit("error", {"message": confirm_text})

        retry_on_nvr = bool(extra.get("retry_on_nvr_with_new_mail", True))
        max_email_retries = min(int(extra.get("max_otp_email_retries", 3)), 3)
        retry_email_service_cfg = str(extra.get("retry_email_service", "as_setting")).lower().strip()
        retry_use_free = bool(extra.get("retry_use_free_mail", False))
        free_prov_name = str(extra.get("fallback_email_service", "tempmail_plus")).lower().strip()

        from core.email_service import is_checkpoint_die
        is_dead_checkpoint = is_dead_checkpoint or is_checkpoint_die(confirm_text)

        def _resolve_retry_provider_for_attempt(attempt_idx: int):
            custom_doms = extra.get("selected_domains") or extra.get("selected_custom_domains")
            if retry_email_service_cfg in ("clean_trio", "trio", "clean_suite") or any(k in str(retry_email_service_cfg).lower() for k in ("clean_trio", "clean_suite", "trio")):
                p = get_email_provider("clean_trio", selected_domains=custom_doms)
                return p, "🎯 Bộ Mail Sạch: @smail1s.com + @laoia.com + @smailwork.com + @mailto.plus"
            elif retry_email_service_cfg in ("hotmailtrusted_domain",):
                p = get_email_provider("clean_trio", selected_domains=["hotmailtrusted.com"])
                return p, "Mail Ảo Riêng: @hotmailtrusted.com"
            elif retry_email_service_cfg in ("mailtoplus_domain",):
                p = get_email_provider("clean_trio", selected_domains=["mailto.plus"])
                return p, "Mail Ảo Riêng: @mailto.plus"
            elif retry_email_service_cfg in ("smail1s_domain",) or "smail1s_domain" in str(retry_email_service_cfg).lower():
                p = get_email_provider("smail1s_domain")
                return p, "Mail Ảo Riêng: @smail1s.com"
            elif retry_email_service_cfg in ("laoia_domain",) or "laoia_domain" in str(retry_email_service_cfg).lower():
                p = get_email_provider("laoia_domain")
                return p, "Mail Ảo Riêng: @laoia.com"
            elif retry_email_service_cfg in ("smailwork_domain",) or "smailwork_domain" in str(retry_email_service_cfg).lower():
                p = get_email_provider("smailwork_domain")
                return p, "Mail Ảo Riêng: @smailwork.com (pqudx6448)"
            elif retry_email_service_cfg in ("all_free", "all_free_mail", "tat_ca_mail_free") or any(k in str(retry_email_service_cfg).lower() for k in ("all_free", "tat_ca", "tất cả")):
                p = get_email_provider("all_free")
                return p, "🎲 Tất Cả Mail Free (Random Toàn Bộ Nguồn)"
            elif retry_email_service_cfg in ("auto_rotator", "smart_rotator") or any(k in str(retry_email_service_cfg).lower() for k in ("auto_rotator", "xoay", "mọi nguồn", "moi nguon")):
                p = get_email_provider("auto_rotator")
                return p, "🌟 Mail Ảo Free: Tự Động Xoay Mọi Nguồn (Khuyên Dùng)"
            elif retry_email_service_cfg and retry_email_service_cfg not in ("as_setting", "setting", ""):
                api_key = extra.get("api_key") or getattr(task_input, "api_key", None)
                p = get_email_provider(retry_email_service_cfg, api_key=api_key, selected_domains=custom_doms)
                lbl = getattr(p, "provider_name", retry_email_service_cfg)
                if not p:
                    p = email_provider or get_email_provider("auto_rotator", selected_domains=custom_doms)
                return p, lbl

            main_srv_name = str(extra.get("email_service", "")).lower()
            is_main_free = any(f_name in main_srv_name for f_name in ("clean_trio", "clean_suite", "smail1s", "laoia", "smailwork", "hotmailtrusted", "mailto", "fexpost", "mailbox", "rover", "tanpony", "10minutemail", "tempmail", "guerrilla", "mailnesia", "mohmal", "maildrop", "auto_rotator", "tat_ca", "all_free", "xoay", "moi nguon", "mọi nguồn"))

            api_key = extra.get("api_key") or getattr(task_input, "api_key", None)
            if retry_use_free:
                p = get_email_provider(free_prov_name or "auto_rotator", selected_domains=custom_doms)
                return p, "Mail Ảo Free (Random Toàn Bộ Nguồn)"

            p = email_provider
            if not p:
                main_srv = extra.get("email_service", "auto_rotator")
                p = get_email_provider(main_srv, api_key=api_key, selected_domains=custom_doms)
            lbl = getattr(p, "provider_name", "Cấu hình chính (Setting)")
            return p, f"Cấu hình chính ({lbl})"

        cur_cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
        ck_str = client.get_cookie_string() if hasattr(client, "get_cookie_string") and isinstance(client.get_cookie_string(), str) else ""
        if not cur_uid:
            cur_uid = cur_cookies.get("c_user", "") or extract_facebook_uid(cookies=cur_cookies, cookie_str=ck_str)
        cur_xs = cur_cookies.get("xs", "")
        if not cur_xs and ck_str:
            m_xs = re.search(r'(?:^|[;\s])xs=([^;]+)', ck_str)
            if m_xs:
                cur_xs = m_xs.group(1).strip()
        has_session_tokens = bool(
            cur_uid
            and str(cur_uid).isdigit()
            and len(str(cur_uid)) >= 8
        )
        if not has_session_tokens:
            try:
                r_cf_p = client.get(f"https://{server}/confirmemail.php", timeout=6)
                if r_cf_p and r_cf_p.text:
                    cur_uid = cur_uid or extract_facebook_uid(r_cf_p.text, cur_cookies, ck_str)
                    has_session_tokens = bool(cur_uid and str(cur_uid).isdigit() and len(str(cur_uid)) >= 8)
            except Exception:
                pass
        if not has_session_tokens:
            retry_on_nvr = False

        if not ok_confirm and retry_on_nvr and not is_dead_checkpoint and max_email_retries > 0:
            emit("warning", {
                "message": f"Tài khoản chưa thoát form xác minh với {target}. Bắt đầu đổi sang email mới xác minh lại ({max_email_retries} lần thử)...",
                "uid": cur_uid,
                "email": target,
                "proxy": proxy
            })
            if active_mailbox and email_provider and hasattr(email_provider, "release_account"):
                try:
                    email_provider.release_account(active_mailbox.email)
                except Exception:
                    pass

            tried_emails = set([target] if target else [])

            for retry_attempt in range(1, max_email_retries + 1):
                if ok_confirm or is_dead_checkpoint:
                    break

                cur_cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
                cur_uid = cur_cookies.get("c_user", "") or cur_uid or extract_facebook_uid(cookies=cur_cookies, cookie_str=client.get_cookie_string() if hasattr(client, "get_cookie_string") else "")
                if not cur_uid:
                    try:
                        r_cf_p = client.get(f"https://{server}/confirmemail.php", timeout=6)
                        if r_cf_p and r_cf_p.text:
                            cur_uid = extract_facebook_uid(r_cf_p.text, cur_cookies, client.get_cookie_string() if hasattr(client, "get_cookie_string") else "")
                            if cur_uid and "c_user" not in cur_cookies:
                                cur_cookies["c_user"] = cur_uid
                    except Exception:
                        pass

                try:
                    pre_chk_st, pre_chk_msg = fb_checker.check_registration_account_live(
                        client=client,
                        server=server,
                        uid=cur_uid,
                        proxy=proxy,
                    )
                except Exception as e:
                    logger.debug(f"check_registration_account_live exception: {e}")
                    pre_chk_st, pre_chk_msg = "unknown", str(e)
                if pre_chk_st in ("session_expired", "conn_error", "unknown", "") and hasattr(client, "get_cookie_string"):
                    try:
                        ck_st, ck_msg = fb_checker.check_facebook_account_live_status(
                            cookie_str=client.get_cookie_string(), uid=cur_uid, proxy=proxy, timeout=5
                        )
                        if ck_st == "live":
                            pre_chk_st, pre_chk_msg = "live", ck_msg
                        elif ck_st in ("die_282", "die"):
                            pre_chk_st, pre_chk_msg = "die", ck_msg
                        elif ck_st == "nvr":
                            pre_chk_st, pre_chk_msg = "nvr", ck_msg
                    except Exception:
                        pass
                if pre_chk_st == "die":
                    confirm_text = f"Tài khoản dính Checkpoint 282 (DIE: {pre_chk_msg})"
                    emit("error", {
                        "message": f"❌ [Lần {retry_attempt}/{max_email_retries}] Tài khoản UID {cur_uid} đã bị DIE ({pre_chk_msg}) -> Dừng xác minh lại ngay!"
                    })
                    is_dead_checkpoint = True
                    break
                elif pre_chk_st == "live":
                    emit("verified", {
                        "message": f"🟢 [Lần {retry_attempt}/{max_email_retries}] Tài khoản UID {cur_uid} đã thoát form xác minh thành công và LIVE ({pre_chk_msg})!",
                        "email": target,
                    })
                    ok_confirm = True
                    break

                emit("info", {
                    "message": f"ℹ️ [Lần {retry_attempt}/{max_email_retries}] Tài khoản {f'UID {cur_uid} ' if cur_uid else ''}còn sống (vẫn ở form xác minh NVR). Tiến hành lấy email mới...",
                    "uid": cur_uid,
                    "email": target,
                    "proxy": proxy
                })
                emit("step", {
                    "step": 4,
                    "name": f"Đổi email mới xác minh lại [Lần {retry_attempt}/{max_email_retries}]...",
                    "target": target,
                    "uid": cur_uid,
                    "email": target,
                    "proxy": proxy
                })

                # Meta tu dong thay the contactpoint khi OTP moi thanh cong; khong gui mutation go contactpoint cu de chong Checkpoint 282 (ATO defense)
                current_retry_prov, prov_label = _resolve_retry_provider_for_attempt(retry_attempt)

                new_mailbox = None
                domain_target = extra.get("domain") or (extra.get("metaking_domain") if "metaking" in str(getattr(current_retry_prov, "provider_name", "")).lower() else None)
                for alloc_try in range(3):
                    try:
                        if domain_target:
                            new_mailbox = current_retry_prov.create_mailbox(proxy=proxy, domain=domain_target, worker_id=wid_val)
                        else:
                            new_mailbox = current_retry_prov.create_mailbox(proxy=proxy, worker_id=wid_val)
                    except TypeError:
                        try:
                            new_mailbox = current_retry_prov.create_mailbox(proxy=proxy, domain=domain_target)
                        except TypeError:
                            try:
                                new_mailbox = current_retry_prov.create_mailbox(proxy=proxy, worker_id=wid_val)
                            except TypeError:
                                try:
                                    new_mailbox = current_retry_prov.create_mailbox(proxy=proxy)
                                except Exception:
                                    pass
                    except Exception as ex_m:
                        logger.debug(f"Retry mailbox error on {prov_label}: {ex_m}")

                    if new_mailbox and getattr(new_mailbox, "email", None) and new_mailbox.email not in tried_emails:
                        break

                if not new_mailbox or not getattr(new_mailbox, "email", None) or new_mailbox.email in tried_emails:
                    is_rot_retry = (
                        retry_email_service_cfg in ("auto_rotator", "all_free", "tat_ca_mail_free", "smart_rotator")
                        or any(k in str(retry_email_service_cfg).lower() for k in ("tat_ca", "tất cả", "all_free", "auto_rotator", "xoay mọi nguồn", "xoay"))
                    )
                    if is_rot_retry:
                        current_retry_prov = get_email_provider("auto_rotator")
                        prov_label = "Mail Ảo Free (Random Toàn Bộ Nguồn)"
                        try:
                            new_mailbox = current_retry_prov.create_mailbox(proxy=proxy, worker_id=wid_val)
                        except Exception:
                            new_mailbox = None

                if not new_mailbox or not getattr(new_mailbox, "email", None):
                    emit("error", {"message": f"[Lần {retry_attempt}/{max_email_retries}] Không thể tạo hòm thư mới ({prov_label}). Tiếp tục lần thử sau..."})
                    continue

                new_email = new_mailbox.email
                tried_emails.add(new_email)
                emit("info", {"message": f"[Lần {retry_attempt}/{max_email_retries}] Đã nhận hòm thư: {new_email} ({prov_label}). Đang gắn vào Facebook qua GraphQL Relay (useCAAFBConfirmationAddContactPointMutation)...", "uid": cur_uid, "email": new_email, "proxy": proxy})

                bind_ok = bind_facebook_session_email(
                    client=client,
                    server=server,
                    new_email=new_email,
                    base_headers=base_headers,
                    fb_dtsg=fb_dtsg,
                    jazoest=jazoest,
                    timeout=10,
                    uid=cur_uid,
                )

                if not bind_ok:
                    emit("warning", {"message": f"[Lần {retry_attempt}/{max_email_retries}] Gắn {new_email} vào Facebook thất bại. Thử hòm thư khác..."})
                    continue

                target = new_email
                active_mailbox = new_mailbox
                email_provider = current_retry_prov

                emit("step", {
                    "step": 4,
                    "name": f"Chờ mã OTP Facebook gửi về {new_email} [Lần {retry_attempt}/{max_email_retries}]...",
                    "target": new_email,
                    "uid": cur_uid,
                    "email": new_email,
                    "proxy": proxy
                })

                otp_timeout = int(extra.get("otp_timeout", 20))
                otp_res = current_retry_prov.wait_for_otp(
                    account=active_mailbox,
                    timeout_seconds=otp_timeout,
                    proxy=proxy,
                )

                if not getattr(otp_res, "success", False) and not getattr(otp_res, "otp_code", None):
                    try:
                        emit("info", {"message": f"[Resend OTP] Đang kích hoạt Meta gửi lại mã OTP tới {new_email}...", "uid": cur_uid, "email": new_email, "proxy": proxy})
                        trigger_facebook_confirmation_resend(
                            client=client,
                            server=server,
                            target=new_email,
                            base_headers=base_headers,
                            fb_dtsg=fb_dtsg,
                            lsd=lsd,
                            jazoest=jazoest,
                            cur_uid=cur_uid,
                            timeout=8,
                        )
                        if hasattr(current_retry_prov, "request_next_otp"):
                            try:
                                current_retry_prov.request_next_otp(active_mailbox)
                            except Exception:
                                pass
                        _safe_sleep(2.0)
                        otp_res2 = current_retry_prov.wait_for_otp(
                            account=active_mailbox,
                            timeout_seconds=min(15, otp_timeout),
                            proxy=proxy,
                        )
                        if getattr(otp_res2, "success", False) and (getattr(otp_res2, "otp_code", None) or getattr(otp_res2, "confirmation_link", None)):
                            otp_res = otp_res2
                    except Exception:
                        pass

                is_otp_ok = getattr(otp_res, "success", False)
                otp_code = getattr(otp_res, "otp_code", None)
                conf_link = getattr(otp_res, "confirmation_link", None)
                res_meta = getattr(otp_res, "metadata", None)
                if not conf_link and res_meta and isinstance(res_meta, dict):
                    conf_link = res_meta.get("confirmation_link")

                if is_otp_ok and (otp_code or conf_link):
                    emit("info", {"message": f"[Lần {retry_attempt}/{max_email_retries}] Bắt được mã OTP: {otp_code}" if otp_code else f"[Lần {retry_attempt}/{max_email_retries}] Bắt được link xác minh"})
                    emit("step", {"step": 5, "name": f"Gửi mã OTP '{otp_code}' xác minh với Facebook", "target": new_email})

                    cur_cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
                    cur_uid = cur_cookies.get("c_user", "") or cur_uid or ""

                    ok_confirm, confirm_text = email_service.submit_facebook_web_email_otp(
                        session=client,
                        server=server,
                        otp_code=otp_code or "",
                        headers=base_headers,
                        confirmation_link=conf_link,
                        email=new_email,
                        fb_dtsg=fb_dtsg,
                        lsd=lsd,
                        uid=cur_uid,
                        enable_otp_pacing=task_input.extra.get("enable_otp_pacing", True),
                        pacing_min=float(task_input.extra.get("otp_pacing_min", 2.0)),
                        pacing_max=float(task_input.extra.get("otp_pacing_max", 3.5)),
                        proxy_ip=task_input.extra.get("proxy_ip"),
                    )
                    if ok_confirm:
                        _safe_sleep(random.uniform(0.8, 1.4))

                    # Sau khi submit OTP email mới: LUÔN kiểm định trạng thái phiên thực tế
                    post_chk_st = "unknown"
                    post_chk_msg = ""
                    try:
                        post_chk_st, post_chk_msg = fb_checker.check_registration_account_live(
                            client=client,
                            server=server,
                            uid=cur_uid,
                            proxy=proxy,
                            timeout=8
                        )
                    except Exception as e:
                        logger.debug(f"check_registration_account_live exception: {e}")
                        post_chk_st, post_chk_msg = "unknown", str(e)

                    if post_chk_st in ("session_expired", "conn_error", "unknown", "") and hasattr(client, "get_cookie_string"):
                        try:
                            ck_st, ck_msg = fb_checker.check_facebook_account_live_status(
                                cookie_str=client.get_cookie_string(), uid=cur_uid, proxy=proxy, timeout=5
                            )
                            if ck_st == "live":
                                post_chk_st, post_chk_msg = "live", ck_msg
                            elif ck_st in ("die_282", "die"):
                                post_chk_st, post_chk_msg = "die", ck_msg
                            elif ck_st == "nvr":
                                post_chk_st, post_chk_msg = "nvr", ck_msg
                        except Exception:
                            pass

                    if post_chk_st in ("die", "die_282"):
                        is_actually_dead = True
                        ok_confirm = False
                        is_dead_checkpoint = True
                        confirm_text = f"Tài khoản dính Checkpoint 282 sau OTP ({post_chk_msg})"
                        emit("error", {"message": f"[Lần {retry_attempt}/{max_email_retries}] ❌ {confirm_text} -> Dừng thử lại!"})
                        break
                    elif post_chk_st == "live":
                        ok_confirm = True
                        target = new_email
                        active_mailbox = new_mailbox
                        confirm_text = f"Xác thực OTP '{otp_code}' thành công ({post_chk_msg or 'LIVE'})"
                        emit("verified", {"message": f"🎉 [Lần {retry_attempt}/{max_email_retries}] Xác thực OTP '{otp_code}' với email mới {new_email} thành công! Tài khoản đã hoàn tất xác minh sang LIVE! ({confirm_text})", "email": new_email, "uid": cur_uid})
                        break
                    else:
                        if ok_confirm:
                            try:
                                d_hdrs = dict(base_headers or {})
                                d_hdrs['referer'] = f'https://{server}/confirmemail.php'
                                client.get(f'https://{server}/home.php', headers=d_hdrs, timeout=6, allow_redirects=True)
                            except Exception:
                                pass
                            ok_confirm = True
                            target = new_email
                            active_mailbox = new_mailbox
                            confirm_text = "Đã giải phóng onboarding sang LIVE"
                            emit("verified", {"message": f"🟢 [Lần {retry_attempt}/{max_email_retries}] Xác thực OTP '{otp_code}' với email mới {new_email} thành công! Đã giải phóng sang LIVE!", "email": new_email, "uid": cur_uid})
                            break
                        else:
                            ok_confirm = False
                            confirm_text = f"Tài khoản vẫn ở form xác minh OTP ({post_chk_msg}) - Chưa thoát form!"
                            emit('warning', {'message': f"[Lần {retry_attempt}/{max_email_retries}] ⚠️ Sau khi nhập OTP '{otp_code}' Facebook vẫn chuyển hướng về form xác minh (vẫn là NVR: {post_chk_msg}) ➔ Tiếp tục đổi email khác để xác minh tiếp..."})
                        try:
                            if hasattr(current_retry_prov, 'release_account'):
                                current_retry_prov.release_account(new_email)
                            elif hasattr(email_provider, 'release_account'):
                                email_provider.release_account(new_email)
                        except Exception:
                            pass
                else:
                    otp_err = getattr(otp_res, "error", None) or "Hết thời gian chờ"
                    emit("error", {"message": f"[Lần {retry_attempt}/{max_email_retries}] Không nhận được OTP từ hòm thư {new_email} ({otp_err})"})
                    try:
                        if hasattr(current_retry_prov, "release_account"):
                            current_retry_prov.release_account(new_email)
                        elif hasattr(email_provider, "release_account"):
                            email_provider.release_account(new_email)
                    except Exception:
                        pass

        return ok_confirm, otp_code, conf_link, confirm_text, active_mailbox, target
    def register(self, task_input: RegistrationInput) -> RegistrationResult:

        """

        Execute account registration flow based on configured reg_mode:

        - Mode 'vr': Verifies email OTP (Direct email or smart bait-phone bind fallback), saves to LIVE.

        """

        start_time = time.time()

        server, server_tag = resolve_facebook_server(
            task_input.server,
            server_pool=task_input.extra.get("server_pool"),
            random_subset=task_input.extra.get("random_subset", False),
            random_server=task_input.extra.get("random_server", False),
        )

        device_type = task_input.device_type or "Android"

        browser_type = task_input.browser_type or "Default"

        locale = task_input.locale or "vi_VN"



        wid = task_input.extra.get("worker_id", 1)

        reg_mode = str(task_input.extra.get("reg_mode", "vr")).lower().strip()

        # Delegate to iOS Bloks CAA flow (extracted from regfb.py)
        if reg_mode in ("ios_bloks", "bloks_ios", "regfb", "bloks", "ios"):
            from core.ios_bloks_engine import run_ios_bloks_registration
            return run_ios_bloks_registration(task_input, emit_func=self._emit_event if hasattr(self, "_emit_event") else None, parent_service=self)

        # Automatically delegate to Mr-SxR Legacy NV flow if requested or if caller passes phone number without VR email config
        if (
            reg_mode in ("legacy", "legacy_nv", "legacy_web", "nv_web", "nv_mr_sxr")
            or task_input.extra.get("use_legacy_web", False)
            or (not task_input.extra.get("reg_mode") and task_input.extra.get("password_config") is not None)
            or (not task_input.extra.get("reg_mode") and not task_input.extra.get("email_service") and not ("@" in str(task_input.identifier or "")) and not task_input.extra.get("email"))
        ):
            return self.register_legacy_nv(task_input)

        is_vr = (reg_mode == "vr")

        raw_bait_mode = task_input.extra.get("bait_mode")
        if raw_bait_mode:
            bait_mode = str(raw_bait_mode).lower().strip()
        elif task_input.extra.get("use_bait_gmail"):
            bait_mode = "gmail"
        elif task_input.extra.get("use_bait_phone") is not None:
            bait_mode = "phone" if bool(task_input.extra.get("use_bait_phone")) else "none"
        elif task_input.extra.get("auto_gen_phone") is not None:
            bait_mode = "phone" if bool(task_input.extra.get("auto_gen_phone")) else "none"
        else:
            bait_mode = "phone"
        if bait_mode not in ("phone", "gmail", "none"):
            bait_mode = "phone"

        use_bait = (bait_mode != "none")
        b_label = "Gmail ảo" if bait_mode == "gmail" else "SĐT ảo" 
        raw_enable_retry = bool(task_input.extra.get("enable_bait_retry", True))
        raw_bait_retries = task_input.extra.get("bait_retries") or task_input.extra.get("max_bait_retries") or 3
        if not raw_enable_retry:
            max_bait_retries = 1
        else:
            try:
                max_bait_retries = int(raw_bait_retries)
            except Exception:
                max_bait_retries = 3
            max_bait_retries = max(1, min(10, max_bait_retries))

        confirm_text = ""

        ok_confirm = False

        token_val = ""

        init_live_st = ""

        init_live_msg = ""



        def emit(event_name: str, payload: dict) -> None:

            if "worker_id" not in payload:

                payload["worker_id"] = wid

            self._emit_event(event_name, payload)



        # Đồng bộ hóa vị trí địa lý, nhà mạng viễn thông (MNO) & thiết bị

        # top-level GeoTelephonyResolver

        from core.proxy_manager import ProxyManager



        target_host = task_input.extra.get("proxy_ip", "") or ""

        if not target_host and task_input.proxy:

            try:

                p_parsed = ProxyManager.parse_proxy(task_input.proxy)

                if p_parsed:

                    target_host = p_parsed.real_ip or p_parsed.host

            except Exception:

                pass



        geo_profile = task_input.extra.get("geo_profile")
        hint_c = task_input.extra.get("country_code") or task_input.extra.get("proxy_country")
        if not geo_profile and target_host and target_host not in ("Direct", "127.0.0.1", ""):
            try:
                geo_profile = GeoTelephonyResolver.resolve_ip(target_host, hint_country=hint_c, proxy=task_input.proxy)
            except Exception:
                pass
        elif not geo_profile and hint_c:
            try:
                geo_profile = GeoTelephonyResolver.get_profile_for_country(hint_c)
            except Exception:
                pass

        if not geo_profile:
            loc_country = "VN"
            if hint_c:
                loc_country = hint_c
            elif "_" in locale:
                loc_country = locale.split("_")[-1].upper()
            geo_profile = GeoTelephonyResolver.get_profile_for_country(loc_country)

        profile = get_random_device_profile(device_type, geo_profile=geo_profile)

        emit("info", {

            "message": f"[Hồ sơ thiết bị] {profile.name} ({profile.brand}) | Màn hình: {profile.viewport_width}x{profile.viewport_height} (DPR {profile.pixel_ratio}) | TLS: {profile.impersonate}"

        })



        # Khởi tạo Ma trận Phòng thủ & 12 Lớp An ninh Toàn diện

        import uuid

        lifecycle = ActivityLifecycleManager()

        lifecycle.on_create(f"Session initialized for {device_type}")

        def _generate_bait_identifier() -> str:
            if bait_mode == "gmail":
                try:
                    # top-level generate_bait_gmail_identifier
                    fn = getattr(task_input, "first_name", None)
                    ln = getattr(task_input, "last_name", None)
                    return generate_bait_gmail_identifier(first_name=fn, last_name=ln)
                except Exception:
                    try:
                        from core.email_service import generate_bait_gmail_identifier
                        return generate_bait_gmail_identifier()
                    except Exception:
                        return f"user{random.randint(1992, 2005)}{random.randint(10, 99)}@gmail.com"
            # Mồi SĐT ngẫu nhiên hợp lệ khớp theo đầu số của quốc gia IP đó
            c_code = getattr(geo_profile, "country_code", "") if geo_profile else ""
            if not c_code and target_host and target_host not in ("Direct", "127.0.0.1", ""):
                try:
                    # top-level GeoTelephonyResolver
                    g_res = GeoTelephonyResolver.resolve_ip(target_host, proxy=task_input.proxy)
                    c_code = getattr(g_res, "country_code", "VN")
                except Exception:
                    c_code = "VN"
            raw_phone = generate_mno_carrier_phone(geo_profile=geo_profile, country_code=c_code, ip=target_host, force_vn=False)
            return _format_e164_phone(raw_phone, geo_profile=geo_profile)

        nonce_mgr = PlayIntegrityNonceManager(ttl_seconds=180)

        session_nonce = nonce_mgr.generate_nonce(session_id=str(uuid.uuid4()), action="fb_registration")

        battery_engine = BatteryThermalEngine(

            initial_battery=round(random.uniform(72.0, 93.0), 1),

            initial_temp=round(random.uniform(32.5, 35.8), 1)

        )

        sensor_engine = SensorTelemetryEngine()

        kinematics = TouchKinematicsEngine()

        velocity_limiter = BehaviorVelocityLimiter()

        pow_engine = PoWChallengeEngine(default_difficulty=3)



        # 1. Thẩm định Môi trường HĐH & Phần cứng thật (EnvironmentDetector)

        env_profile = EnvironmentDetector.evaluate_genuine_device({

            "brand": profile.brand,

            "model": profile.model,

            "manufacturer": profile.brand

        })



        # 2. Thẩm định GPU phần cứng & Subsystem Âm thanh (HardwareGpuAudioProfiler)

        gpu_profile = HardwareGpuAudioProfiler.get_genuine_gpu_profile(profile.brand, profile.name)



        # 3. Chứng thực Phần cứng Key Attestation & Widevine DRM (HardwareKeystoreDRMEngine)

        hw_drm_profile = HardwareKeystoreDRMEngine.build_katana_hardware_profile(

            challenge=session_nonce,

            security_level="L1"

        )



        # 4. Kiểm định tính toàn vẹn Native & Syscall trực tiếp (NativeIntegrityAuditor)

        native_report = NativeIntegrityAuditor.get_genuine_native_report()



        # 5. Dấu vân tay Giao vận Katana Liger TLS JA4 (TransportFingerprintEngine)

        transport_profile = TransportFingerprintEngine.get_katana_liger_transport_profile()



        is_android_dev = (getattr(profile, "os_name", "") == "Android")
        if is_android_dev:
            emit("info", {
                "message": f"[??? Play Integrity & DRM] Nonce: {session_nonce[:16]}... | TEE: MEETS_DEVICE_INTEGRITY | Widevine: L1 (Hardware Secure)"
            })
            emit("info", {
                "message": f"[??? Môi trường OS & GPU] SELinux: {env_profile['selinux_state']} | GPU: {gpu_profile['gl_renderer']} ({gpu_profile['gl_vendor']}) | Audio DAC: {gpu_profile['audio_frames_per_buffer']}f"
            })
            emit("info", {
                "message": f"[??? Native & Giao vận] Syscall: {native_report['syscall_mode']} | TracerPid: 0 | TLS JA4: {transport_profile['tls']['ja4']}"
            })
        else:
            emit("info", {
                "message": f"[??? Môi trường OS & GPU] Windows Desktop Subsystem | GPU: ANGLE (Direct3D11) | Audio DAC: 256f"
            })
            emit("info", {
                "message": f"[??? Native & Giao vận] Desktop Win32 Direct | TracerPid: 0 | TLS JA4: t13d1516h2_8daaf6152771_027e697f6ced"
            })

        active_mailbox = None

        email_provider = None

        mail_pass = ""

        mail_raw = ""

        mail_rest = ""

        ok_confirm = False



        should_allocate_mailbox = is_vr or (not use_bait)

        if should_allocate_mailbox:

            # 1. Cấp phát hòm thư email theo setting (Dành cho VR OTP hoặc NVR khi chọn dùng mail)

            try:

                from core.email_service import get_email_provider, EmailAccount

                prov_name = task_input.extra.get("email_service", "dongvanfb")

                api_key = task_input.extra.get("dongvanfb_api_key") or task_input.extra.get("email_api_key")

                if "metaking" in str(prov_name).lower():

                    api_key = task_input.extra.get("metaking_api_key") or api_key

                    srv_type = "phone" if "phone" in str(prov_name).lower() else task_input.extra.get("metaking_service_type", "email")

                    sid = 67 if srv_type == "phone" else 1

                    email_provider = get_email_provider(

                        prov_name,

                        api_key=api_key,

                        service_type=srv_type,

                        server=task_input.extra.get("metaking_server", 1),

                        domain=task_input.extra.get("metaking_domain", "gmail.com"),

                        service_id=sid,

                        country_id=task_input.extra.get("metaking_country_id", 154),

                        price=task_input.extra.get("metaking_price", "low"),

                    )

                else:
                    custom_doms = task_input.extra.get("selected_domains") or task_input.extra.get("selected_custom_domains")
                    email_provider = get_email_provider(prov_name, api_key=api_key, selected_domains=custom_doms)

                domain_target = task_input.extra.get("domain") or (task_input.extra.get("metaking_domain") if "metaking" in str(prov_name).lower() else None)
                wid = task_input.extra.get("worker_id", 1)

                try:
                    active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target, worker_id=wid)
                except TypeError:
                    try:
                        active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target)
                    except TypeError:
                        try:
                            active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, worker_id=wid)
                        except TypeError:
                            active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy)

            except Exception as e:

                logger.warning(f"Mailbox allocation error: {e}")



            # Neu la dich vu mail ao hoac tra phi ma tao that bai:
            # Neu nguoi dung da chi dinh ro nha cung cap (vi du: Metaking Hotmail, 10minutemail), giu nguyen va thu lai:
            is_generic_rotator = (
                prov_name in ("auto_rotator", "all_free", "tat_ca_mail_free", "smart_rotator")
                or any(k in str(prov_name).lower() for k in ("tat_ca", "tất cả", "all_free", "auto_rotator", "xoay mọi nguồn", "xoay"))
            )
            if not active_mailbox and not is_generic_rotator:
                wid = task_input.extra.get("worker_id", 1)
                for retry_alloc in range(1, 4):
                    _safe_sleep(random.uniform(0.8, 1.8) + (wid % 4) * 0.3)
                    try:
                        active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target, worker_id=wid)
                    except TypeError:
                        try:
                            active_mailbox = email_provider.create_mailbox(proxy=task_input.proxy, domain=domain_target)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    if active_mailbox:
                        break

            if not active_mailbox and is_generic_rotator:
                from core.email_service import AutoRotatorEmailProvider
                fallback_providers = [name for name, _ in AutoRotatorEmailProvider()._providers]
                wid = task_input.extra.get("worker_id", 1)
                random.shuffle(fallback_providers)
                for alt_prov in fallback_providers:
                    try:
                        alt_provider_inst = get_email_provider(alt_prov)
                        try:
                            alt_mb = alt_provider_inst.create_mailbox(proxy=task_input.proxy, worker_id=wid)
                        except TypeError:
                            alt_mb = alt_provider_inst.create_mailbox(proxy=task_input.proxy)
                        if alt_mb:
                            active_mailbox = alt_mb
                            email_provider = alt_provider_inst
                            emit("info", {"message": f"[Hòm thư ảo] 🎲 Luồng {wid} ➔ Cấp hòm thư ngẫu nhiên từ nguồn '{alt_mb.provider}' (Random Đa Nguồn): {alt_mb.email}"})
                            break
                    except Exception:
                        continue

            if not active_mailbox:

                elapsed = time.time() - start_time

                if "metaking" in str(prov_name).lower():

                    err_msg = "Không thể thuê email/SĐT từ Metaking.top! Vui lòng kiểm tra API Key hoặc số dư tài khoản."

                elif prov_name in ("custom_hotmail", "dongvanfb", "smail1s", "hotmail"):

                    err_msg = "Kho Hotmail (hotmails.txt) đã hết tài khoản khả dụng! Vui lòng bấm [📂 Mở DS Hotmail] để nạp thêm hoặc chọn Mail Ảo Miễn Phí."

                else:

                    err_msg = f"Dịch vụ mail ảo ({prov_name}) hiện không phản hồi. Vui lòng thử lại hoặc chọn nguồn mail khác."

                emit("error", {"message": err_msg})

                res = RegistrationResult(

                    success=False,

                    status="failed",

                    identifier="No-Mailbox",

                    error_message=err_msg,

                    elapsed_seconds=elapsed,

                )

                emit("failed", {"result": res})

                return res



            target = active_mailbox.email

            mail_pass = getattr(active_mailbox, "password", "") or ""

            mail_meta = getattr(active_mailbox, "metadata", {}) or {}

            mail_raw = mail_meta.get("raw_line") or ""

            mail_rest = ""

            if mail_raw and "|" in mail_raw:

                mail_rest = mail_raw.split("|", 1)[1]

            else:

                mail_parts = []

                if mail_pass:

                    mail_parts.append(str(mail_pass))

                for k in ("refresh_token", "client_id", "rec_email", "rec_pwd"):

                    v = mail_meta.get(k)

                    if v:

                        mail_parts.append(str(v))

                mail_rest = "|".join(mail_parts)

                if not mail_raw and mail_rest:

                    mail_raw = f"{target}|{mail_rest}"

            if not mail_pass and mail_rest:

                mail_pass = mail_rest.split("|")[0].strip()



            # Trụ cột 4: Kiểm định uy tín Email (Chống Checkpoint 282 do DEA / Mail rác)

            if task_input.extra.get("email_integrity_guard", True):

                try:

                    guard = EmailIntegrityGuard()

                    email_domain = target.split("@")[-1].lower() if "@" in target else ""

                    if email_domain in TRUSTED_PROVIDER_DOMAINS:

                        emit("info", {

                            "message": f"[🛡️ Trụ cột 4 - Email Audit] Domain '@{email_domain}' (High-Trust Consumer Webmail | DEA Risk: 0/100 | Checkpoint 282: An toàn tuyệt đối)"

                        })

                    else:

                        is_disposable = guard.check_disposable_blacklist(email_domain)

                        if is_disposable:

                            emit("warning", {

                                "message": f"[⚠️ DEA Alert] Domain '{email_domain}' thuộc danh sách đen Disposable Mail (Nguy cơ Checkpoint 282: 95/100)! Khuyến nghị dùng Hotmail tự nhập."

                            })

                        else:

                            emit("info", {

                                "message": f"[🛡️ Email Audit] Domain '@{email_domain}' hợp lệ (Đạt chuẩn Anti-DEA / High-Trust Mail)."

                            })

                except Exception as e:

                    logger.debug(f"Email audit exception: {e}")



            if use_bait:
                bait_target = _generate_bait_identifier()
                submit_target = bait_target
                if is_vr:
                    _step1_name = f"Mồi {b_label} {bait_target} để kích hoạt phiên Facebook (Email đích: {target})"
                else:
                    target = bait_target
                    _step1_name = f"Chế độ NVR: Sinh {b_label} {bait_target}"
                emit("step", {"step": 1, "name": _step1_name, "target": bait_target})
                emit("start", {"target": bait_target, "device_type": device_type})
            else:
                submit_target = target
                _step1_name = f"Đã nạp hòm thư ({active_mailbox.provider}): {target}" if is_vr else f"Chế độ NVR (Theo setting): Đã nạp hòm thư {target}"
                emit("step", {"step": 1, "name": _step1_name, "target": target})
                emit("start", {"target": target, "device_type": device_type})

        else:

            # Chế độ NVR (No-Verify) có mồi SĐT/Gmail ảo ngẫu nhiên hợp lệ:

            target = _generate_bait_identifier()
            submit_target = target

            emit("step", {"step": 1, "name": f"Chế độ NVR: Sinh {b_label} {target}", "target": target})

            emit("start", {"target": target, "device_type": device_type})



        # 2. Khởi tạo danh tính người dùng

        fixed_pwd = task_input.password or task_input.extra.get("default_password") or task_input.extra.get("fixed_password")

        identity = {

            "first_name": task_input.first_name or "",

            "last_name": task_input.last_name or "",

            "sex_value": task_input.gender or "",

            "password": fixed_pwd or "",

        }

        if not (identity["first_name"] and identity["last_name"] and identity["password"]):

            n_type = task_input.extra.get("name_type")

            c_file = task_input.extra.get("custom_name_file", "names.txt")

            m_names = task_input.extra.get("mix_file_names", False)

            generated = self.generate_identity(

                password_seed=fixed_pwd,

                locale=locale,

                name_type=n_type,

                custom_file=c_file,

                mix_file_names=m_names,

                geo_profile=geo_profile,

            )

            for k, v in generated.items():

                if not identity.get(k):

                    identity[k] = v



        full_name = identity.get("full_name") or f"{identity['first_name']} {identity['last_name']}"

        name_tag = identity.get("name_tag") or "Mặc định"

        emit("info", {"message": f"Họ tên đăng ký: {full_name} ({name_tag})"})



        # 3. Chuẩn bị HTTP Client và lấy security tokens

        client = None

        try:

            client = HttpClient(

                device_type=device_type,

                proxy=task_input.proxy,

                timeout=self.timeout,

                profile=profile,

            )

            # Khong pre-seed cookies man hinh truoc luot GET dau tien
            ctx = build_request_context(device_type, browser_type, locale, profile=profile, geo_profile=geo_profile)

            base_headers = ctx["base_headers"]



            lifecycle.on_start("Registration form rendered")

            lifecycle.on_resume("Active form filling")



            # Bảo toàn nguyên bản Mobile Chrome Browser (Tuyệt đối KHÔNG gắn header native Liger vào web request)



            # Đánh giá rủi ro mạng TCP Stack & CGNAT (NetworkRiskProfiler)

            if task_input.proxy and task_input.extra.get("network_risk_check", True):

                try:

                    network_profiler = NetworkRiskProfiler()
                    claimed_os = getattr(profile, "os_name", "Android") or "Android"
                    is_win = "windows" in str(claimed_os).lower()
                    measured_mss = 1460 if is_win else 1380
                    measured_ttl = 128 if is_win else 64
                    claimed_network = "Broadband" if is_win else "4G_LTE"
                    net_eval = network_profiler.evaluate_tcp_fingerprint(
                        claimed_os=claimed_os,
                        claimed_network=claimed_network,
                        measured_mss=measured_mss,
                        measured_ttl=measured_ttl
                    )
                    carrier_name = getattr(profile, "carrier", "Mobifone")
                    emit("info", {
                        "message": f"[??? Network Risk Profiler] Mạng {claimed_network} {carrier_name} (CGNAT: OK | MSS: {measured_mss} | TTL: {measured_ttl} | RTT: {net_eval.get('rtt_ms', 45):.0f}ms | Jitter: {net_eval.get('jitter_ms', 18):.1f}ms)"
                    })
                except Exception as e:
                    logger.debug(f"Network audit exception: {e}")



            # Đánh giá đồ thị cụm Sybil & Cách ly thiết bị (DeviceGraphProfiler)

            curr_ip = task_input.extra.get("proxy_ip") or (task_input.proxy or "Direct")

            graph_eval = DeviceGraphProfiler.evaluate_cluster_risk(

                ip_address=curr_ip,

                device_id=profile.model,

                advertising_id=str(uuid.uuid4()),

                session_history=[]

            )

            emit("info", {

                "message": f"[🛡️ Đồ thị Sybil Graph] Trạng thái: {graph_eval.get('verdict', 'ISOLATED_CLEAN_NODE')} | Điểm rủi ro cụm: {graph_eval.get('cluster_risk_score', 0.0):.2f}"

            })



            # Tải form đăng ký & trích xuất mã bảo mật Facebook (LSD) (Hỗ trợ tự động xoay proxy nếu lỗi kết nối / timeout)

            html_text = ""

            landing_html = ""

            max_form_attempts = 5

            # Để tránh việc Facebook chuyển hướng Android Chrome 120-131 sang /ig/login_via/app/ (làm mất form HTML),
            # ta dùng User-Agent KaiOS / Feature Phone hợp lệ từ Mr-SxR để lấy 100% form đăng ký gốc từ Meta CDN
            ua_reg = getattr(profile, "user_agent", "") or base_headers.get("user-agent") or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
            reg_headers = dict(base_headers)
            reg_headers["user-agent"] = ua_reg
            reg_headers["accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            reg_headers["referer"] = f"https://{server}/"
            # top-level is_chromium_ua
            if not is_chromium_ua(ua_reg):
                clean_client_hints(reg_headers, ua_reg)
            for h in ("x-fb-supports-fresco", "x-fb-net-hni", "x-fb-sim-hni", "x-fb-connection-type", "x-fb-device-group", "x-requested-with"):
                reg_headers.pop(h, None)

            candidate_reg_urls = []
            for u in [
                f"https://{server}/reg?soft=hjk",
                f"https://{server}/r.php?soft=hjk",
                "https://mbasic.facebook.com/reg?soft=hjk",
                f"https://{server}/reg/?soft=hjk",
            ]:
                if u not in candidate_reg_urls:
                    candidate_reg_urls.append(u)

            def _extract_lsd_token(text: str) -> str:
                if not text:
                    return ""
                patterns = [
                    r'name="lsd" value="([^"]+)"',
                    r'name="lsd" value="([^"]+)"',
                    r'\["LSD",\[\],\{"token":"([^"]+)"\}',
                    r'\[\"LSD\",\[\],\{\"token\":\"([^\"]+)\"\}',
                    r'"tokenName":"lsd","token":"([^"]+)"',
                    r'\"tokenName\":\"lsd\",\"token\":\"([^\"]+)\"',
                    r'\["LSDInitialData",\[\],\{"token":"([^"]+)"\}',
                    r'\[\"LSDInitialData\",\[\],\{\"token\":\"([^\"]+)\"\}',
                    r'"LSDInitialData",\[\],\{"token":"([^"]+)"\}',
                    r'"lsd":\s*"([^"]+)"',
                    r'\"lsd\":\s*\"([^\"]+)\"',
                    r'"lsd"[:\s]+"([^"]+)"',
                    r'name="lsd"\s+value="([^"]+)"',
                ]
                for p in patterns:
                    m = re.search(p, text)
                    if m and m.group(1):
                        return m.group(1)
                return ""

            for form_attempt in range(max_form_attempts):
                if form_attempt > 0:
                    _safe_sleep(0.5)
                try:
                    step2_target = submit_target if use_bait else target
                    step2_name = f"Tải form đăng ký & trích xuất mã bảo mật Facebook (LSD) (Mồi: {step2_target})" if use_bait else "Tải form đăng ký & trích xuất mã bảo mật Facebook (LSD)"
                    emit("step", {"step": 2, "name": step2_name, "target": step2_target})
                    reg_url = candidate_reg_urls[form_attempt % len(candidate_reg_urls)]
                    reg_resp = client.get(reg_url, headers=reg_headers, timeout=15, allow_redirects=True)
                    _sync_response_cookies(client, reg_resp)
                    setup_session_cookies(client, device_type=device_type, profile=profile)
                    html_text = reg_resp.text or ""
                    if _extract_lsd_token(html_text):
                        try:
                            if task_input.extra.get("proxy_provider") in ("free_proxy", "free_proxy_live", "free_proxy_cached") and task_input.proxy:
                                # top-level FreeProxyManager
                                FreeProxyManager().record_live_proxy(task_input.proxy)
                        except Exception:
                            pass
                        break
                    else:
                        if form_attempt < max_form_attempts - 1:
                            prov = task_input.extra.get("proxy_provider", "")
                            if prov in ("free_proxy", "free_proxy_live", "free_proxy_cached"):
                                try:
                                    # top-level FreeProxyManager
                                    fm = FreeProxyManager()
                                    if task_input.proxy:
                                        fm.mark_bad_proxy(task_input.proxy)
                                    new_p = fm.get_verified_live_proxy(worker_id=wid, timeout=5.0) or fm.claim_instant_candidate(worker_id=wid)
                                    if new_p:
                                        client.set_proxy(new_p)
                                        task_input.proxy = new_p.as_url() if hasattr(new_p, "as_url") else str(new_p)
                                        emit("info", {"message": f"[Proxy Live] 🔄 Tự động đổi sang Proxy LIVE mới ({fm._get_host(task_input.proxy)}) để tải lại form Facebook..."})
                                except Exception:
                                    pass
                except (ProxyConnectionError, RequestTimeoutError, HttpClientError) as p_err:
                    logger.debug(f"[Handshake Error] Proxy lỗi kết nối (lần {form_attempt+1}/{max_form_attempts}): {p_err}")
                    if form_attempt < max_form_attempts - 1:
                        prov = task_input.extra.get("proxy_provider", "")
                        if prov in ("free_proxy", "free_proxy_live", "free_proxy_cached"):
                            try:
                                # top-level FreeProxyManager
                                fm = FreeProxyManager()
                                if task_input.proxy:
                                    fm.mark_bad_proxy(task_input.proxy)
                                new_p = fm.get_verified_live_proxy(worker_id=wid, timeout=5.0) or fm.claim_instant_candidate(worker_id=wid)
                                if new_p:
                                    client.set_proxy(new_p)
                                    task_input.proxy = new_p.as_url() if hasattr(new_p, "as_url") else str(new_p)
                                    emit("info", {"message": f"[Proxy Live] 🔄 Tự động đổi sang Proxy LIVE mới ({fm._get_host(task_input.proxy)}) do proxy cũ lỗi mạng..."})
                            except Exception:
                                pass
                    elif form_attempt == max_form_attempts - 1:
                        try:
                            prov = task_input.extra.get("proxy_provider", "")
                            if prov in ("free_proxy", "free_proxy_live", "free_proxy_cached") and task_input.proxy:
                                # top-level FreeProxyManager
                                FreeProxyManager().mark_bad_proxy(task_input.proxy)
                        except Exception:
                            pass
                        raise

            def _extract_all_reg_tokens(text: str) -> dict:

                if not text:

                    return {}

                return {

                    "lsd": _extract_lsd_token(text),

                    "jazoest": _extract_regex(r'name="jazoest" value="([^"]+)"', text),

                    "ccp": _extract_regex(r'name="ccp" value="([^"]+)"', text),

                    "reg_instance": _extract_regex(r'name="reg_instance" value="([^"]+)"', text) or _extract_regex(r'"reg_instance"[:\s]+"([^"]+)"', text),

                    "reg_impression_id": _extract_regex(r'name="reg_impression_id" value="([^"]+)"', text) or _extract_regex(r'"impressionId"[:\s]+"([^"]+)"', text),

                    "ns": _extract_regex(r'name="ns" value="([^"]+)"', text),

                    "logger_id": _extract_regex(r'name="logger_id" value="([^"]+)"', text) or _extract_regex(r'"lid"[:\s]+"([^"]+)"', text),

                    "encrypted": _extract_regex(r'"encrypted"\s*:\s*"([^"]+)"', text),

                    "fb_dtsg": _extract_regex(r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', text) or _extract_regex(r'name="fb_dtsg" value="([^"]+)"', text),

                    "privacy_token": _extract_regex(r'privacy_mutation_token=([^&"\'\s]+)', text),

                    "spin_r": _extract_regex(r'"__spin_r":(\d+)', text) or _extract_regex(r'"spin_r":(\d+)', text) or "",

                    "spin_t": _extract_regex(r'"__spin_t":(\d+)', text) or _extract_regex(r'"spin_t":(\d+)', text) or "",

                    "spin_b": _extract_regex(r'"__spin_b":"([^"]+)"', text) or "trunk",

                    "hsi": _extract_regex(r'"hsi":"([^"]+)"', text) or "",

                    "dyn": _extract_regex(r'"__dyn":"([^"]+)"', text) or _extract_regex(r'name="__dyn" value="([^"]+)"', text) or "1Z3pawlEnwm8_Bg9ppoW5UdE4a2i5U4e0C86u7E39x60zU3ex608ewk9E4W0pKq0FE6S0x81vohw73wGwcq1GwqU2YwbK0oi0zE1jU1soG0hi0Lo6-0Co1kU1UU3jwGwbu",

                    "csr": _extract_regex(r'"__csr":"([^"]+)"', text) or _extract_regex(r'name="__csr" value="([^"]+)"', text) or "",

                    "hsdp": _extract_regex(r'"__hsdp":"([^"]+)"', text) or "",

                    "hblp": _extract_regex(r'"__hblp":"([^"]+)"', text) or "",

                    "sjsp": _extract_regex(r'"__sjsp":"([^"]+)"', text) or "",

                    "req": _extract_regex(r'"__req":"([^"]+)"', text) or "r",
                    "submit": _extract_regex(r'<input[^>]+name="submit"[^>]+value="([^"]+)"', text) or _extract_regex(r'value="([^"]+)"[^>]+name="submit"', text) or _extract_regex(r'<button[^>]+name="submit"[^>]*>([^<]+)</button>', text) or "",


                }



            toks = _extract_all_reg_tokens(html_text)

            if not (toks.get("reg_instance") and toks.get("privacy_token")):

                toks_landing = _extract_all_reg_tokens(landing_html)

                if toks_landing.get("reg_instance") and toks_landing.get("privacy_token"):

                    toks = toks_landing

                    html_text = landing_html



            # Bắt tay dự phòng qua hồ sơ di động cổ điển (KaiOS / Windows Phone) như repo Mr-SxR

            # nhằm vượt cổng chuyển hướng /ig/login_via/app/ của Facebook và lấy 100% token thật

            if not (toks.get("reg_instance") and toks.get("privacy_token")):
                try:
                    for fb_url in [f"https://{server}/r.php?soft=hjk", f"https://mbasic.facebook.com/reg?soft=hjk", f"https://{server}/reg?soft=hjk"]:
                        alt_resp = client.get(fb_url, headers=reg_headers, timeout=10, allow_redirects=True)
                        _sync_response_cookies(client, alt_resp)
                        alt_html = alt_resp.text or ""
                        alt_toks = _extract_all_reg_tokens(alt_html)
                        if alt_toks.get("reg_instance") and alt_toks.get("privacy_token"):
                            toks = alt_toks
                            html_text = alt_html
                            reg_url = fb_url
                            break
                except Exception as alt_err:
                    logger.debug(f"Registration tokens fallback warning: {alt_err}")

            lsd = toks.get("lsd") or ""

            jazoest = toks.get("jazoest") or (f"2{sum(ord(c) for c in lsd)}" if lsd else "")

            ccp = toks.get("ccp") or "2"

            reg_instance = toks.get("reg_instance") or ""

            reg_impression_id = toks.get("reg_impression_id") or ""

            ns_value = toks.get("ns") or "0"

            logger_id = toks.get("logger_id") or ""

            encrypted_token = toks.get("encrypted") or ""

            fb_dtsg = toks.get("fb_dtsg") or ""

            privacy_token = (toks.get("privacy_token") or "").replace("%3D", "=")

            spin_r = toks.get("spin_r") or ""

            spin_t = toks.get("spin_t") or ""

            spin_b = toks.get("spin_b") or "trunk"

            hsi = toks.get("hsi") or ""

            dyn_val = toks.get("dyn") or toks.get("__dyn") or ""

            csr_val = toks.get("csr") or toks.get("__csr") or ""

            hsdp_val = toks.get("hsdp") or toks.get("__hsdp") or ""

            hblp_val = toks.get("hblp") or toks.get("__hblp") or ""

            sjsp_val = toks.get("sjsp") or toks.get("__sjsp") or ""

            req_val = toks.get("req") or toks.get("__req") or "r"

            # Đảm bảo bộ Telemetry Comet hoàn chỉnh, ngẫu nhiên động đa dạng theo browser thật
            if not dyn_val or dyn_val == "1Z3pawlEnwm8_Bg9ppoW5UdE4a2i5U4e0C86u7E39x60zU3ex608ewk9E4W0pKq0FE6S0x81vohw73wGwcq1GwqU2YwbK0oi0zE1jU1soG0hi0Lo6-0Co1kU1UU3jwGwbu":
                from core.email_service import get_random_comet_telemetry
                _rand_t = get_random_comet_telemetry()
                dyn_val = _rand_t.get("__dyn") or dyn_val
                if not csr_val:
                    csr_val = _rand_t.get("__csr", "")
                if not hsdp_val:
                    hsdp_val = _rand_t.get("__hsdp", "")
                if not hblp_val:
                    hblp_val = _rand_t.get("__hblp", "")
                if not sjsp_val:
                    sjsp_val = _rand_t.get("__sjsp", "")
                if not hsi:
                    hsi = _rand_t.get("__hsi", "")



            if not lsd:

                elapsed = time.time() - start_time

                res = RegistrationResult(

                    success=False,

                    status="error",

                    identifier=target,

                    error_message="Không trích xuất được LSD token từ Facebook",

                    elapsed_seconds=elapsed,

                )

                emit("error", {"result": res})

                return res



            # Mô phỏng độ trễ điền form tự nhiên

            typing_prof = get_random_typing_profile()

            form_read_pause = random.uniform(typing_prof["read_min"], typing_prof["read_max"])

            mean_flight = typing_prof["flight_mean_ms"] / 1000.0

            jitter_flight = typing_prof["jitter_ms"] / 1000.0



            name_flight = sum([max(0.05, mean_flight + random.gauss(0, jitter_flight)) for _ in full_name])

            dob_pause = random.uniform(0.7, 1.8)

            contact_flight = sum([max(0.05, mean_flight + random.gauss(0, jitter_flight)) for _ in target])

            pwd_flight = sum([max(0.05, mean_flight + random.gauss(0, jitter_flight)) for _ in identity.get("password", "")])

            review_pause = random.uniform(typing_prof["review_min"], typing_prof["review_max"])



            typing_delay = form_read_pause + name_flight + dob_pause + contact_flight + pwd_flight + review_pause

            

            # Sinh trắc học hành vi, cảm biến quán tính 8-12Hz (SensorTelemetryEngine & TouchKinematics)

            sensor_stream = sensor_engine.generate_human_sensor_stream(duration_sec=1.5, sample_rate_hz=100)

            tremor_info = sensor_engine.analyze_sensor_microtremor(sensor_stream)

            t_sx = round(profile.viewport_width * random.uniform(0.35, 0.65), 1)

            t_sy = round(profile.viewport_height * random.uniform(0.55, 0.80), 1)

            t_ex = round(t_sx + random.uniform(-15.0, 15.0), 1)

            t_ey = round(t_sy + random.uniform(-20.0, 20.0), 1)

            touch_traj = kinematics.generate_human_swipe_trajectory(

                start_pt=(t_sx, t_sy),

                end_pt=(t_ex, t_ey),

                duration_sec=random.uniform(0.28, 0.48),

                points_count=random.randint(18, 30)

            )



            # Mô phỏng Tương quan Đa Cảm biến (MultiSensorFusionEngine) - Loại bỏ nhận diện giá đỡ phone farm

            sensor_fusion = MultiSensorFusionEngine.generate_coupled_touch_sensor_frame(

                touch_x=profile.viewport_width * random.uniform(0.35, 0.65),

                touch_y=profile.viewport_height * random.uniform(0.55, 0.80),

                screen_width=profile.viewport_width,

                screen_height=profile.viewport_height,

                pressure=random.uniform(0.55, 0.72)

            )



            # Thử thách Mật mã Máy trạm (PoWChallengeEngine) - Chứng minh có thực thi chu trình CPU thật

            pow_challenge = pow_engine.generate_challenge("fb_reg_submit", difficulty=3)

            pow_solution = pow_engine.solve_challenge(pow_challenge)

            pow_valid = pow_engine.verify_solution(pow_solution)



            # Kiểm soát vận tốc hành động (BehaviorVelocityLimiter)

            velocity_limiter.allow_action("submit_registration")



            if _is_test_env() or task_input.extra.get('skip_sleep', False) or task_input.extra.get('fast_mode', False) or task_input.extra.get('otp_timeout', 60) <= 10:
                total_human_pause = 0.0
            else:
                cog_pause = HumanBehaviorDynamics.sample_cognitive_pause(min_sec=0.5, max_sec=1.2)
                total_human_pause = min(2.5, max(0.5, typing_delay * 0.15 + cog_pause))

            battery_engine.tick(elapsed_seconds=total_human_pause, cpu_workload="heavy")



            emit("info", {

                "message": f"[🛡️ Đa cảm biến & Sinh trắc học] Cầm tay: Pitch {sensor_fusion['posture']['pitch_degrees']}° / Roll {sensor_fusion['posture']['roll_degrees']}° | Vi chấn: {tremor_info['peak_frequency_hz']} Hz | PoW: {pow_solution.get('elapsed_ms', round(pow_solution.get('elapsed_seconds', 0) * 1000, 1))}ms CPU | Pin: {battery_engine.battery_level}% ({battery_engine.temperature}°C)"

            })

            _safe_sleep(total_human_pause)



            # 4. Gửi form đăng ký

            # 4. Gửi form đăng ký
            post_target_url = f"https://{server}/reg/submit/"

            # POST headers PHẢI kế thừa 100% từ reg_headers (đã dùng để GET /reg thành công)
            # để đảm bảo User-Agent, Accept và Client Hints hoàn toàn nhất quán, không bị Facebook WAF phát hiện đổi client
            post_headers = dict(reg_headers)
            post_headers.update({
                "accept": "*/*",
                "content-type": "application/x-www-form-urlencoded",
                "origin": f"https://{server}",
                "referer": f"https://{server}/reg?soft=hjk",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "x-fb-lsd": lsd,
                "x-requested-with": "XMLHttpRequest",
                "x-response-format": "JSONStream",
            })
            post_headers.pop("upgrade-insecure-requests", None)
            post_headers.pop("sec-fetch-user", None)

            params = {
                "privacy_mutation_token": privacy_token or "",
                "multi_step_form": "1",
                "skip_suma": "0",
                            }

            def build_post_data(contact_target: str) -> dict:
                timestamp = int(time.time())
                raw_target = str(contact_target).strip()
                if "@" not in raw_target:
                    clean_contact = _format_e164_phone(raw_target, geo_profile=geo_profile)
                else:
                    clean_contact = raw_target

                payload_data = {
                    "ccp": ccp,
                    "reg_instance": reg_instance,
                    "submission_request": "true",
                    "helper": "",
                    "reg_impression_id": reg_impression_id,
                    "ns": ns_value,
                    "zero_header_af_client": "",
                    "app_id": "",
                    "logger_id": logger_id,
                    "field_names[0]": "firstname",
                    "firstname": identity["first_name"],
                    "lastname": identity["last_name"],
                    "field_names[1]": "birthday_wrapper",
                    "birthday_day": str(identity.get("b_day", "15")),
                    "birthday_month": str(identity.get("b_month", "6")),
                    "birthday_year": str(identity.get("b_year", "1998")),
                    "age_step_input": "",
                    "did_use_age": "false",
                    "field_names[2]": "reg_email__",
                    "reg_email__": clean_contact,
                    "field_names[3]": "sex",
                    "sex": str(identity.get("sex_value", "2")),
                    "preferred_pronoun": "",
                    "custom_gender": "",
                    "field_names[4]": "reg_passwd__",
                    "name_suggest_elig": "true" if identity.get("did_use_suggested_name") == "true" else "false",
                    "was_shown_name_suggestions": "true" if identity.get("did_use_suggested_name") == "true" else "false",
                    "did_use_suggested_name": identity.get("did_use_suggested_name", "false"),
                    "use_custom_gender": "false",
                    "guid": "",
                    "pre_form_step": "",
                    "encpass": f"#PWD_BROWSER:0:{int(time.time())}:{identity['password']}",
                    "fb_dtsg": fb_dtsg,
                    "jazoest": jazoest,
                    "lsd": lsd,
                    "__dyn": dyn_val,
                    "__csr": csr_val,
                    "__hsdp": hsdp_val,
                    "__hblp": hblp_val,
                    "__sjsp": sjsp_val,
                    "__req": req_val or "r",
                    "__hsi": hsi,
                    "__fmt": "1",
                    "__a": encrypted_token,
                    "__user": "0",
                }
                # Form Facebook mobile chuẩn: reg_email__ chứa SĐT/Email, không có trường phụ
                return payload_data

            def parse_fb_error(response_text: str) -> Tuple[bool, str]:
                try:
                    raw_json = response_text.split("for (;;);")[1] if "for (;;);" in response_text else response_text
                    data = json.loads(raw_json)
                    if "error" in data or "errorSummary" in data or "errorDescription" in data:
                        msg = data.get("errorDescription") or data.get("errorSummary") or f"Facebook Error {data.get('error')}"
                        return True, msg
                    if "payload" in data and isinstance(data["payload"], dict):
                        if "error" in data["payload"]:
                            err_obj = data["payload"]["error"]
                            return True, str(err_obj)
                        actions = data["payload"].get("actions") or []
                        if isinstance(actions, list):
                            for act in actions:
                                if isinstance(act, dict):
                                    if act.get("target") in ("form_error", "contactpoint_step_body", "contactpoint_step_error", "reg_error"):
                                        html_err = str(act.get("html") or "")
                                        if html_err:
                                            clean_err = re.sub(r'<[^>]+>', ' ', html_err).strip()
                                            if clean_err:
                                                return True, clean_err
                except Exception:
                    pass
                if "There was an error with your registration" in response_text or "Đã xảy ra lỗi với đăng ký của bạn" in response_text:
                    return True, "There was an error with your registration. Please try registering again."
                return False, ""

            if use_bait:
                if "submit_target" not in locals() or not submit_target:
                    bait_target = _generate_bait_identifier()
                    submit_target = bait_target
                if is_vr:
                    emit("step", {"step": 3, "name": f"Mồi {b_label} {submit_target} để kích hoạt phiên Facebook (Email đích: {target})", "target": submit_target})
                else:
                    emit("step", {"step": 3, "name": f"Mồi {b_label} {submit_target} để kích hoạt phiên Facebook NVR", "target": submit_target})
            else:
                submit_target = target
                emit("step", {"step": 3, "name": f"Gửi thông tin đăng ký lên Facebook theo setting: {target}", "target": target})

            post_resp = None
            max_post_attempts = 2
            vr_slot_key = task_input.extra.get("proxy_ip", "") or (task_input.proxy.real_ip if hasattr(task_input.proxy, "real_ip") and task_input.proxy.real_ip else str(task_input.proxy or ""))
            vr_ip_lock = ProxySubmitRateLimiter.get_ip_lock(vr_slot_key)
            with vr_ip_lock:
                ProxySubmitRateLimiter.wait_turn(vr_slot_key, min_interval=random.uniform(2.8, 4.0))
                try:
                    for post_attempt in range(max_post_attempts):
                        try:
                            post_resp = client.post(
                                post_target_url,
                                params=params,
                                headers=post_headers,
                                data=build_post_data(submit_target),
                                allow_redirects=False,
                                timeout=25,
                            )
                            break
                        except (ProxyConnectionError, RequestTimeoutError, HttpClientError) as p_err:
                            logger.warning(f"[Submit Error] Proxy error submitting form (attempt {post_attempt+1}/{max_post_attempts}): {p_err}")
                            prov = task_input.extra.get("proxy_provider", "")
                            if prov in ("free_proxy", "free_proxy_live", "free_proxy_cached"):
                                try:
                                    # top-level FreeProxyManager
                                    free_mgr = FreeProxyManager()
                                    old_p = getattr(client, "proxy", None) or task_input.proxy
                                    if old_p:
                                        free_mgr.mark_bad_proxy(old_p)
                                    if post_attempt < max_post_attempts - 1:
                                        new_p = free_mgr.get_verified_live_proxy(worker_id=wid, timeout=5.0) or free_mgr.claim_instant_candidate(worker_id=wid)
                                        if new_p:
                                            client.set_proxy(new_p)
                                            task_input.proxy = new_p.as_url() if hasattr(new_p, "as_url") else str(new_p)
                                            emit("info", {"message": f"[Proxy Live] 🔄 Tự động đổi sang Proxy LIVE mới ({free_mgr._get_host(task_input.proxy)}) để gửi lại biểu mẫu Facebook..."})
                                except Exception:
                                    pass
                            if post_attempt == max_post_attempts - 1:
                                return RegistrationResult(
                                    success=False,
                                    status="failed",
                                    error_message=f"Facebook từ chối kết nối/mồi form (Chưa tạo nick - Lỗi proxy): {p_err}",
                                    elapsed_seconds=round(time.time() - start_time, 2)
                                )
                finally:
                    ProxySubmitRateLimiter.record_submit_finish(vr_slot_key)

            if not post_resp:
                return RegistrationResult(
                    success=False,
                    status="failed",
                    error_message="Facebook từ chối kết nối/mồi form (Chưa tạo nick - Không nhận được phản hồi submit)",
                    elapsed_seconds=round(time.time() - start_time, 2)
                )

            _sync_response_cookies(client, post_resp)

            is_302_success = bool(post_resp and getattr(post_resp, "status_code", 0) in (301, 302, 303))
            if is_302_success:
                _loc = post_resp.headers.get("location") or post_resp.headers.get("Location") or ""
                if _loc:
                    _loc_uid = extract_facebook_uid(_loc, client.get_cookies(), client.get_cookie_string())
                    if _loc_uid and "c_user" not in client.get_cookies():
                        client.set_cookie("c_user", _loc_uid, domain=".facebook.com")
                    _redir_url = _loc if _loc.startswith("http") else f"https://{server}{_loc}"
                    for _redir_att in range(2):
                        try:
                            _redir_resp = client.get(_redir_url, headers=dict(reg_headers), timeout=max(25, int(self.timeout * 0.75)), allow_redirects=True)
                            if _redir_resp is not None:
                                _sync_response_cookies(client, _redir_resp)
                                break
                        except Exception:
                            if hasattr(client, "_reset_session_connections"):
                                client._reset_session_connections()
                            _safe_sleep(1.0)

            cookies = client.get_cookies()
            resp_text = getattr(post_resp, "text", "") or ""
            if "_redir_resp" in locals() and _redir_resp and getattr(_redir_resp, "text", ""):
                resp_text = _redir_resp.text

            cand_uid = extract_facebook_uid(resp_text, cookies, client.get_cookie_string())
            if cand_uid and "c_user" not in cookies:
                cookies["c_user"] = cand_uid
                client.set_cookie("c_user", cand_uid, domain=".facebook.com")

            # Nếu Facebook trả về 302 nhưng chưa có c_user, probe trực tiếp confirmemail.php
            if is_302_success and "c_user" not in cookies:
                for probe_u in [f"https://{server}/confirmemail.php", f"https://{server}/confirmphone.php"]:
                    try:
                        p_resp = client.get(probe_u, headers=dict(reg_headers), timeout=max(25, int(self.timeout * 0.75)), allow_redirects=True)
                        if p_resp is not None:
                            _sync_response_cookies(client, p_resp)
                            p_uid = extract_facebook_uid(getattr(p_resp, "text", ""), client.get_cookies(), client.get_cookie_string())
                            if p_uid:
                                cookies["c_user"] = p_uid
                                client.set_cookie("c_user", p_uid, domain=".facebook.com")
                                break
                    except Exception:
                        pass

            elapsed = time.time() - start_time

            has_error, err_msg = parse_fb_error(resp_text)

            has_valid_session = bool(
                not has_error
                and cookies and any(k in cookies for k in ("c_user", "xs"))
                and str(cookies.get("c_user", "")).isdigit()
                and len(str(cookies.get("c_user", ""))) >= 8
            )

            # Nếu Facebook đã trả về HTTP 302: Form đăng ký ĐÃ THÀNH CÔNG trên máy chủ Meta!
            # Tuyệt đối KHÔNG chạy mồi lại (max_bait_retries) vì sẽ gửi đè làm hỏng nick đã tạo!
            if is_302_success:
                has_error = False
                has_valid_session = True

            # Kịch bản 1: Đã chọn chế độ mồi (SĐT/Gmail) nhưng lần mồi đầu tiên bị Facebook từ chối form hoặc chưa có c_user:
            # Tự động mồi lại bằng SĐT/Gmail mới theo đúng số lần cài đặt (max_bait_retries)
            if use_bait and not is_302_success and (has_error or not has_valid_session):
                if any(k in (err_msg or "").lower() for k in ("block", "ban", "checkpoint", "restrict", "limit", "anti-bot")):
                    pass
                elif max_bait_retries > 1:
                    emit("info", {"message": f"[Mồi phiên] Facebook từ chối {b_label} '{submit_target}' ({err_msg or 'chưa có c_user'}). Đang tự sinh {b_label} mới mồi lại (Cài đặt: {max_bait_retries} lần)..."})
                    last_target = submit_target
                    total_bait_attempts = (max_bait_retries + 1)
                    for b_attempt in range(2, total_bait_attempts + 1):
                        try:
                            _safe_sleep(random.uniform(0.8, 1.4))
                            prev_was_phone = ("@" not in str(last_target))
                            is_phone_err = any(k in str(err_msg).lower() for k in ("số điện thoại", "phone", "sđt", "invalid", "valid mobile", "vui lòng nhập số", "enter a valid"))
                            is_waf_err = any(k in str(err_msg).lower() for k in ("1351050", "đã xảy ra lỗi với đăng ký", "waf", "form_error"))

                            is_gmail_mode = (bait_mode == "gmail" or task_input.extra.get("use_bait_gmail"))
                            is_phone_mode = (bait_mode == "phone" or task_input.extra.get("use_bait_phone"))
                            if is_gmail_mode:
                                new_bait = _generate_bait_identifier(force_fresh=True, force_mode="gmail")
                                cur_b_label = "Gmail cứu phiên"
                                emit("info", {"message": f"[Mồi phiên] Thử lại với Gmail mới: {new_bait}!"})
                            elif is_phone_mode:
                                raw_bait = _generate_bait_identifier(force_fresh=True, force_mode="phone")
                                new_bait = _format_e164_phone(raw_bait, geo_profile=geo_profile) if "@" not in str(raw_bait) else raw_bait
                                cur_b_label = "SĐT cứu phiên"
                                emit("info", {"message": f"[Mồi phiên] Thử lại với SĐT mới: {new_bait}!"})
                            elif prev_was_phone and (is_phone_err or b_attempt == max_bait_retries):
                                new_bait = _generate_bait_identifier(force_fresh=True, force_mode="gmail")
                                cur_b_label = "Gmail cứu phiên"
                                emit("info", {"message": f"[Mồi phiên] Facebook từ chối SĐT ở lượt trước ➔ Tự động ứng cứu bằng Gmail quốc tế: {new_bait}!"})
                            elif not prev_was_phone and (is_waf_err or b_attempt == max_bait_retries):
                                new_bait = _generate_bait_identifier(force_fresh=True, force_mode="phone")
                                cur_b_label = "SĐT cứu phiên"
                                emit("info", {"message": f"[Mồi phiên] Facebook từ chối Gmail ở lượt trước ➔ Tự động ứng cứu bằng SĐT chuẩn E.164: {new_bait}!"})
                            else:
                                raw_bait = _generate_bait_identifier(force_fresh=True, force_mode=("phone" if prev_was_phone else "gmail"))
                                new_bait = _format_e164_phone(raw_bait, geo_profile=geo_profile) if "@" not in str(raw_bait) else raw_bait
                                cur_b_label = "SĐT cứu phiên" if "@" not in str(new_bait) else "Gmail cứu phiên"

                            last_target = new_bait
                            emit("step", {"step": 3, "name": f"Mồi lại {cur_b_label} #{b_attempt}/{max_bait_retries}: {new_bait}", "target": new_bait})
                            emit("info", {"message": f"[Mồi phiên] Thử lại #{b_attempt}/{max_bait_retries}: Đang gửi {cur_b_label} {new_bait} lên Facebook..."})
                            try:
                                ref_resp = client.get(f"https://{server}/reg?soft=hjk", headers=reg_headers, timeout=10, allow_redirects=True)
                                _sync_response_cookies(client, ref_resp)
                                ref_toks = _extract_all_reg_tokens(ref_resp.text or "")
                                if ref_toks.get("reg_instance"):
                                    reg_instance = ref_toks["reg_instance"]
                                if ref_toks.get("reg_impression_id"):
                                    reg_impression_id = ref_toks["reg_impression_id"]
                                if ref_toks.get("privacy_token"):
                                    privacy_token = ref_toks["privacy_token"]
                                    params["privacy_mutation_token"] = privacy_token
                                if ref_toks.get("lsd"):
                                    lsd = ref_toks["lsd"]
                                    post_headers["x-fb-lsd"] = lsd
                            except Exception:
                                reg_instance = str(uuid.uuid4())
                                reg_impression_id = str(uuid.uuid4())
                            post_resp = client.post(
                                post_target_url,
                                params=params,
                                headers=post_headers,
                                data=build_post_data(new_bait),
                                timeout=15,
                            )
                            _sync_response_cookies(client, post_resp)
                            cookies = client.get_cookies()
                            resp_text = getattr(post_resp, "text", "") or ""
                            cand_b_uid = extract_facebook_uid(resp_text, cookies, client.get_cookie_string() if hasattr(client, "get_cookie_string") else "")
                            if cand_b_uid and "c_user" not in cookies:
                                cookies["c_user"] = cand_b_uid
                            has_error, err_msg = parse_fb_error(resp_text)
                            has_valid_session = bool(cookies and any(k in cookies for k in ("c_user", "xs")) and str(cookies.get("c_user", "")).isdigit() and len(str(cookies.get("c_user", ""))) >= 8)
                            if not has_error and has_valid_session:
                                has_error = False
                                err_msg = ""
                                submit_target = new_bait
                                emit("info", {"message": f"[Mồi phiên] 🎉 Mồi {b_label} {new_bait} thành công ở lần #{b_attempt}! Facebook đã cấp phiên (UID {cookies.get('c_user', '')})."})
                                break
                            else:
                                has_error = True
                                if not err_msg:
                                    err_msg = "Chưa nhận được cookie phiên (c_user) từ Facebook"
                                if any(k in (err_msg or "").lower() for k in ("block", "ban", "checkpoint", "restrict", "limit", "anti-bot")):
                                    break
                        except Exception as bait_err:
                            logger.debug(f"Bait retry attempt {b_attempt} error: {bait_err}")

            # Kịch bản 2: Nếu đăng ký trực tiếp bằng Email (không mồi) bị Facebook từ chối form:
            # Lập tức mồi SĐT/Gmail ảo trên phiên hiện tại để vượt form theo đúng số lần cài đặt (max_bait_retries)
            elif is_vr and submit_target == target and (has_error or not has_valid_session):
                if any(k in (err_msg or "").lower() for k in ("block", "ban", "checkpoint", "restrict", "limit", "anti-bot")):
                    pass
                else:
                    emit("info", {"message": f"[VR OTP] Hòm thư '{target}' bị Facebook từ chối form ({err_msg or 'kiểm duyệt'}). Đang tự động mồi {b_label} vượt rào (Cài đặt: {max_bait_retries} lần)..."})
                    for b_attempt in range(1, max_bait_retries + 1):
                        try:
                            _safe_sleep(random.uniform(0.8, 1.4))
                            bait_num = _generate_bait_identifier()
                            emit("info", {"message": f"[VR OTP] Mồi {b_label} {bait_num} để kích hoạt phiên Facebook (Lần {b_attempt}/{max_bait_retries})..."})
                            reg_instance = str(uuid.uuid4())
                            reg_impression_id = str(uuid.uuid4())
                            post_resp = client.post(
                                post_target_url,
                                params=params,
                                headers=post_headers,
                                data=build_post_data(bait_num),
                                timeout=15,
                            )
                            _sync_response_cookies(client, post_resp)
                            cookies = client.get_cookies()
                            resp_text = getattr(post_resp, "text", "") or ""
                            cand_b_uid = extract_facebook_uid(resp_text, cookies, client.get_cookie_string() if hasattr(client, "get_cookie_string") else "")
                            if cand_b_uid and "c_user" not in cookies:
                                cookies["c_user"] = cand_b_uid
                            has_error, err_msg = parse_fb_error(resp_text)
                            has_valid_session = bool(cookies and any(k in cookies for k in ("c_user", "xs")) and str(cookies.get("c_user", "")).isdigit() and len(str(cookies.get("c_user", ""))) >= 8)
                            if not has_error and has_valid_session:
                                has_error = False
                                err_msg = ""
                                submit_target = bait_num
                                emit("info", {"message": f"[VR OTP] 🎉 Mồi {b_label} {bait_num} thành công! Facebook đã cấp phiên (UID {cookies.get('c_user', '')})."})
                                break
                            else:
                                has_error = True
                                if not err_msg:
                                    err_msg = "Chưa nhận được cookie phiên (c_user) từ Facebook"
                                if any(k in (err_msg or "").lower() for k in ("block", "ban", "checkpoint", "restrict", "limit", "anti-bot")):
                                    break
                        except Exception as bait_err:
                            logger.debug(f"Bait fallback attempt {b_attempt} error: {bait_err}")

            if has_error or not has_valid_session:
                fail_reason = err_msg or "Chưa nhận được cookie phiên (c_user) từ Facebook"
                is_net_proxy_err = any(k in (fail_reason or "").lower() for k in ("proxy", "timeout", "connection refused", "handshake", "ssl", "connect error", "timed out"))
                if is_net_proxy_err:
                    reason_desc = "Lỗi kết nối Proxy"
                    advise_action = "Đổi ngay Proxy khác chạy nick tiếp theo!"
                elif any(k in (fail_reason or "").lower() for k in ("đã xảy ra lỗi với đăng ký", "1351050", "there was an error with your registration")):
                    reason_desc = "Facebook chặn biểu mẫu (FB WAF / Rate-limit IP / Mồi ảo bị FB lọc)"
                    advise_action = "Thử đổi sang mồi SĐT ảo hoặc tắt mồi để dùng trực tiếp Email!"
                else:
                    reason_desc = "Facebook từ chối biểu mẫu tạo nick"
                    advise_action = "Chuyển sang xử lý nick tiếp theo!"

                emit("warning", {
                    "message": f"⚠️ Facebook từ chối kết nối/mồi form ({reason_desc}): Facebook Error: {fail_reason} ➔ {advise_action}"
                })
                if active_mailbox and email_provider and hasattr(email_provider, "release_account"):
                    try:
                        email_provider.release_account(active_mailbox.email)
                    except Exception:
                        pass
                result = RegistrationResult(
                    success=False,
                    status="failed",
                    identifier=submit_target,
                    email=(submit_target if "@" in submit_target else ""),
                    phone=(submit_target if "@" not in submit_target else ""),
                    uid="",
                    password=identity.get("password", ""),
                    name=full_name,
                    error_message=f"Facebook Error: {fail_reason}",
                    elapsed_seconds=time.time() - start_time,
                )
                emit("failed", {"result": result})
                return result

            email_attached = False

            if is_vr and submit_target != target and cookies and any(k in cookies for k in ("c_user", "xs")):
                uid_cur = cookies.get("c_user", "")
                if task_input.extra.get("enable_account_maturation", False):
                    raw_mat = task_input.extra.get("account_maturation_delay", "60-120s (Ngẫu nhiên)")
                    mat_s = parse_maturation_delay_seconds(raw_mat, default=90.0)
                    emit("info", {"message": f"⏳ [Chờ ngấu] Tạo phiên thành công UID {uid_cur}. Đang chờ ngấu {int(mat_s)}s để phiên ổn định trên hệ thống Meta trước khi gắn mail...", "uid": uid_cur})
                    emit("step", {"step": 4, "name": f"Chờ ngấu tài khoản ({int(mat_s)}s)...", "uid": uid_cur, "email": target, "proxy": proxy})
                    t_end = time.time() + mat_s
                    stop_evt = task_input.extra.get("stop_event")
                    while time.time() < t_end:
                        if stop_evt and stop_evt.is_set():
                            break
                        _safe_sleep(min(1.0, t_end - time.time()))
                emit("info", {"message": f"[VR OTP] Tạo phiên thành công (UID {uid_cur}). Đang gắn hòm thư thật {target} qua GraphQL (useCAAFBConfirmationAddContactPointMutation)..."})
                from core.email_service import add_facebook_confirmation_contactpoint
                ok_add, msg_add = add_facebook_confirmation_contactpoint(
                    session=client,
                    email=target,
                    server=server,
                    headers=base_headers,
                    uid=cookies.get("c_user"),
                    fb_dtsg=fb_dtsg,
                    lsd=lsd,
                    timeout=15,
                )
                if ok_add:
                    has_error = False
                    email_attached = True
                    emit("info", {"message": f"[VR OTP] Gắn email {target} thành công qua GraphQL Relay! Đang kích hoạt máy chủ Meta gửi mã OTP..."})
                    try:
                        cf_hdrs = dict(base_headers or {})
                        cf_hdrs["referer"] = f"https://{server}/confirmemail.php"
                        r_cf = client.get(f"https://{server}/confirmemail.php", headers=cf_hdrs, timeout=8)
                        _sync_response_cookies(client, r_cf)
                    except Exception as ex_trig:
                        logger.debug(f"[VR OTP] Initial confirmemail trigger error: {ex_trig}")
                else:
                    try:
                        ch_headers = dict(base_headers)
                        ch_headers["cookie"] = client.get_cookie_string()
                        r_ch = client.get(f"https://{server}/changeemail/", headers=ch_headers)
                        _sync_response_cookies(client, r_ch)
                        cur_dtsg = _extract_regex(r'name="fb_dtsg" value="([^"]+)"', r_ch.text) or _extract_regex(r'"token":"([^"]+)"', r_ch.text) or fb_dtsg
                        cur_jazoest = _extract_regex(r'name="jazoest" value="([^"]+)"', r_ch.text) or jazoest
                        cur_old_email = _extract_regex(r'name="old_email" value="([^"]+)"', r_ch.text) or submit_target
                        cur_reg_inst = _extract_regex(r'name="reg_instance" value="([^"]+)"', r_ch.text) or reg_instance
                        set_headers = dict(ch_headers)
                        set_headers.update({
                            "origin": f"https://{server}",
                            "referer": f"https://{server}/changeemail/",
                            "content-type": "application/x-www-form-urlencoded",
                        })
                        cur_submit = _extract_regex(r'name="submit" value="([^"]+)"', r_ch.text) or "Thêm"
                        set_payload = {
                            "fb_dtsg": cur_dtsg,
                            "jazoest": cur_jazoest,
                            "next": "",
                            "old_email": cur_old_email,
                            "reg_instance": cur_reg_inst,
                            "new": target,
                            "submit": cur_submit,
                        }
                        r_set = client.post(f"https://{server}/setemail/", data=set_payload, headers=set_headers)
                        _sync_response_cookies(client, r_set)
                        has_error = False
                        email_attached = True
                    except Exception as ex_legacy_set:
                        logger.debug(f"[VR OTP] Legacy setemail error: {ex_legacy_set}")



            # Xử lý kết quả theo từng chế độ:

            token_val = ""

            totp_secret = ""

            # ======================== CHẾ ĐỘ NVR (NO-VERIFY) ========================

            if not is_vr:

                if cookies and any(k in cookies for k in ("c_user", "xs")):

                    uid = cookies.get("c_user", "")

                    cookie_str = client.get_cookie_string()

                    if task_input.extra.get("session_warmup", True) and is_vr:

                        try:

                            emit("step", {"step": 4, "name": "Làm ấm phiên sâu (Home Feed & Seed Interest) để giữ nick...", "target": target})

                            warmup_headers = dict(base_headers)

                            warmup_headers["referer"] = f"https://{server}/"

                            client.get(f"https://{server}/", headers=warmup_headers, timeout=10)

                            _safe_sleep(random.uniform(2.5, 4.5))

                            try:

                                c_code = getattr(geo_profile, "country_code", "VN").upper() if geo_profile else "VN"

                                country_seeds = SEED_PAGES_BY_COUNTRY.get(c_code, ["bbcnews", "cnn", "natgeo"])

                                seed_page = random.choice(country_seeds)

                                client.get(f"https://{server}/{seed_page}/", headers=warmup_headers, timeout=8)

                                _safe_sleep(random.uniform(1.5, 2.5))

                            except Exception:

                                pass

                            for ck, cv in client.get_cookies().items():

                                cookies[ck] = cv

                            cookie_str = client.get_cookie_string()

                        except Exception:

                            pass



                    totp_secret = ""

                    if task_input.extra.get("enable_2fa", False):

                        try:

                            pause_2fa = random.uniform(3.0, 5.5)

                            emit("step", {"step": 5, "name": f"Nghỉ nhận thức ({pause_2fa:.1f}s) rồi kích hoạt 2FA TOTP (UID {uid})...", "target": target})

                            _safe_sleep(pause_2fa)

                            # top-level enable_facebook_2fa

                            ok_2fa, sec_2fa, otp_2fa, msg_2fa = enable_facebook_2fa(

                                client=client,

                                uid=uid,

                                password=identity.get("password", ""),

                                server=server,

                                fb_dtsg=None,

                                lsd=None,

                                emit=emit,

                            )

                            if ok_2fa and sec_2fa:

                                totp_secret = sec_2fa

                                emit("info", {"message": f"[2FA] Kích hoạt 2FA TOTP THẬT thành công! Secret: {sec_2fa}"})

                            else:

                                emit("warning", {"message": f"[2FA] Không kích hoạt được 2FA thật ({msg_2fa})."})

                        except Exception as e:

                            emit("warning", {"message": f"[2FA] Lỗi kích hoạt 2FA: {e}"})



                    token_val = ""

                    if task_input.extra.get("extract_token", True):

                        try:

                            src_text = locals().get("response_text", "") or ""

                            if src_text:

                                m_tok = re.search(r'access_token["\s:=]+([A-Za-z0-9_]{35,})', src_text)

                                if m_tok:

                                    token_val = m_tok.group(1)

                                else:

                                    m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)

                                    if m_eaab:

                                        token_val = m_eaab.group(1)

                        except Exception:

                            pass



                    result = RegistrationResult(

                        success=True,

                        status="unverified",

                        identifier=target,

                        email=target,

                        uid=uid,

                        password=identity.get("password", ""),

                        token=token_val,

                        cookies=cookies,

                        cookie_string=cookie_str,

                        two_factor_secret=totp_secret,

                        name=full_name,

                        birthday=f"{identity.get('b_day')}/{identity.get('b_month')}/{identity.get('b_year')}",

                        gender=identity["sex_value"],

                        elapsed_seconds=elapsed,

                        email_password=mail_pass,

                        email_raw=mail_raw,

                        email_rest=mail_rest,

                        metadata={"identity": identity, "reg_mode": "nvr", "unverified": True, "device_profile": {"name": profile.name, "brand": profile.brand, "model": profile.model, "os_version": getattr(profile, "os_version", ""), "user_agent": profile.user_agent, "web_user_agent": getattr(profile, "web_user_agent", ""), "app_user_agent": getattr(profile, "app_user_agent", ""), "dalvik_user_agent": getattr(profile, "dalvik_user_agent", ""), "viewport": f"{profile.viewport_width}x{profile.viewport_height}", "carrier": profile.carrier, "locale": profile.locale, "timezone": profile.timezone}},

                    )

                    # BẢO VỆ CHỐNG DIE CHO NVR: Warmup nhẹ Newsfeed & Profile

                    try:

                        warmup_headers = dict(base_headers)

                        warmup_headers["cookie"] = client.get_cookie_string()

                        warmup_headers["referer"] = f"https://{server}/reg/submit/"

                        _safe_sleep(random.uniform(1.2, 2.0))

                        client.get(f"https://{server}/", headers=warmup_headers, timeout=10)

                        cookies = client.get_cookies()

                        cookie_str = client.get_cookie_string()

                        result.cookies = cookies

                        result.cookie_string = cookie_str

                    except Exception as e:

                        logger.debug(f"NVR Warmup error: {e}")



                    emit("unverified", {"result": result, "message": f"Tạo UID {uid} thành công (NVR - Chưa xác minh)"})

                    return result

                else:

                    fail_msg = err_msg or "Facebook không tạo được phiên đăng nhập NVR"

                    result = RegistrationResult(

                        success=False,

                        status="failed",

                        identifier=target,

                        name=full_name,

                        error_message=fail_msg,

                        elapsed_seconds=elapsed,

                    )

                    emit("failed", {"result": result})

                    return result



            # ======================== CHẾ ĐỘ VR OTP ========================

            r_conf_init = None

            cur_uid = cookies.get("c_user") if cookies else None



            # Nếu chưa có c_user/xs trực tiếp từ cookies POST /reg/submit/, thăm dò confirmemail.php

            if not cur_uid:

                try:

                    conf_probe_hdrs = dict(base_headers)

                    conf_probe_hdrs["referer"] = f"https://{server}/reg/submit/"

                    r_conf_init = client.get(f"https://{server}/confirmemail.php", headers=conf_probe_hdrs, timeout=10)

                    _sync_response_cookies(client, r_conf_init)

                    cookies = client.get_cookies()



                    p_txt = r_conf_init.text
                    cand_u = extract_facebook_uid(p_txt, cookies, client.get_cookie_string())
                    if cand_u:
                        cur_uid = cand_u
                        if "c_user" not in cookies:
                            cookies["c_user"] = cur_uid

                    m_dtsg = re.search(r'name="fb_dtsg" value="([^"]+)"', p_txt) or re.search(r'"dtsg"[:\s]+\{"token":"([^"]+)"\}', p_txt) or re.search(r'"token":"([^"]+)"', p_txt)

                    if m_dtsg:

                        fb_dtsg = m_dtsg.group(1)

                    m_lsd = re.search(r'name="lsd" value="([^"]+)"', p_txt) or re.search(r'"LSD",\[\],\{"token":"([^"]+)"\}', p_txt)

                    if m_lsd:

                        lsd = m_lsd.group(1)

                except Exception as e:

                    logger.debug(f"Confirm probe error: {e}")



            # Nếu có lỗi nghiêm trọng từ Facebook và không vào được confirmemail:

            if has_error and not cur_uid:

                if active_mailbox and email_provider and hasattr(email_provider, "release_account"):

                    try:

                        email_provider.release_account(active_mailbox.email)

                    except Exception:

                        pass

                fail_reason = err_msg or "Facebook từ chối biểu mẫu đăng ký"

                emit("error", {"message": f"Facebook từ chối tạo tài khoản: {fail_reason}"})

                result = RegistrationResult(

                    success=False,

                    status="failed",

                    identifier=target,

                    name=full_name,

                    error_message=f"Facebook Error: {fail_reason}",

                    elapsed_seconds=elapsed,

                )

                emit("failed", {"result": result})

                return result



            # ĐỢI VÀ XÁC MINH MÃ OTP THẬT TỪ HÒM THƯ (BẮT BUỘC CHO VR OTP)
            ok_confirm, otp_code, conf_link, confirm_text, active_mailbox, target = self.retrieve_and_verify_otp(
                client=client,
                target=target,
                email_provider=email_provider,
                active_mailbox=active_mailbox,
                server=server,
                base_headers=base_headers,
                fb_dtsg=fb_dtsg,
                lsd=lsd,
                jazoest=jazoest,
                cur_uid=cur_uid,
                task_input=task_input,
                emit_func=emit,
            )

            if active_mailbox:
                if getattr(active_mailbox, "password", None):
                    mail_pass = active_mailbox.password
                if getattr(active_mailbox, "raw_account", None):
                    mail_raw = active_mailbox.raw_account
                    mail_rest = active_mailbox.raw_account
                elif getattr(active_mailbox, "metadata", None) and isinstance(active_mailbox.metadata, dict):
                    mail_raw = active_mailbox.metadata.get("raw_line") or target
                    mail_rest = mail_raw

            cookies = client.get_cookies() if hasattr(client, "get_cookies") else {}
            if "c_user" in cookies:
                cur_uid = cookies["c_user"]

            # Đồng bộ cookies & c_user sau khi xác nhận OTP

            if ok_confirm:

                try:

                    splash_hdrs = dict(base_headers)

                    splash_hdrs["referer"] = f"https://{server}/confirmemail.php"

                    for splash_url in [

                        f"https://{server}/?caa_reg_splash_screen=1",

                        "https://www.facebook.com/?caa_reg_splash_screen=1",

                    ]:

                        try:

                            r_sp = client.get(splash_url, headers=splash_hdrs, timeout=8)

                            _sync_response_cookies(client, r_sp)

                            if "checkpoint" in str(getattr(r_sp, "url", "")).lower():

                                break

                        except Exception:

                            pass

                    _safe_sleep(random.uniform(0.6, 1.2))

                    nux_hdrs = dict(base_headers)

                    nux_hdrs["referer"] = f"https://{server}/confirmemail.php"

                    r_sd = client.get(f"https://{server}/save-device/", headers=nux_hdrs, timeout=6)

                    _sync_response_cookies(client, r_sd)

                    _safe_sleep(random.uniform(0.6, 1.2))

                    r_gs = client.get(f"https://{server}/gettingstarted/", headers=nux_hdrs, timeout=6)

                    _sync_response_cookies(client, r_gs)

                    _safe_sleep(random.uniform(0.5, 1.0))

                    r_nx = client.get(f"https://{server}/nux/", headers=nux_hdrs, timeout=6)

                    _sync_response_cookies(client, r_nx)

                    _safe_sleep(random.uniform(0.5, 1.0))

                except Exception:

                    pass

                try:

                    r_home = client.get(f"https://{server}/", headers=base_headers, timeout=10)

                    _sync_response_cookies(client, r_home)

                    if not cur_uid and r_home and r_home.text:

                        m_uid_home = (

                            re.search(r'"actorID"\s*:\s*"(\d+)"', r_home.text)

                            or re.search(r'"USER_ID"\s*:\s*"(\d+)"', r_home.text)

                            or re.search(r'"ACCOUNT_ID"\s*:\s*"(\d+)"', r_home.text)

                            or re.search(r'"fbId"\s*:\s*"(\d+)"', r_home.text)

                            or re.search(r'"userID"\s*:\s*(\d+)', r_home.text)

                            or re.search(r'actor_id=(\d+)', r_home.text)

                            or re.search(r'c_user=(\d+)', r_home.text)

                        )

                        if m_uid_home:

                            cur_uid = m_uid_home.group(1)

                except Exception:

                    pass



            cur_cookies = client.get_cookies()

            for ck, cv in cur_cookies.items():

                cookies[ck] = cv



            if not cur_uid:

                m_uid_cf = (

                    re.search(r"UID:\s*(\d+)", confirm_text or "")

                    or re.search(r'c_user=(\d+)', client.get_cookie_string() or "")

                    or re.search(r'"fbId"[:\s]+"(\d+)"', client.get_cookie_string() or "")

                )

                if m_uid_cf:

                    cand_cf = m_uid_cf.group(1)

                    if cand_cf and cand_cf.isdigit() and cand_cf != "0" and len(cand_cf) >= 8:

                        cur_uid = cand_cf



            if cur_uid and cur_uid != "0" and len(cur_uid) >= 8 and "c_user" not in cookies:

                cookies["c_user"] = cur_uid



            uid = cookies.get("c_user", "") or cur_uid or ""

            if uid == "0" or (uid and (not uid.isdigit() or len(uid) < 8)):

                uid = ""

            cookie_str = client.get_cookie_string()



            # KIỂM ĐỊNH KẾT QUẢ CUỐI CÙNG CHO CHẾ ĐỘ VR OTP:

            # Chỉ coi là xác minh OTP thành công khi ok_confirm == True!

            # Nếu ok_confirm == False:

            # - Nếu Facebook đã cấp c_user/xs: Nick ở trạng thái NVR (Chờ xác minh OTP - Tuyệt đối KHÔNG PHẢI DIE và KHÔNG PHẢI LIVE!)

            # - Lưu vào accounts_unverified.txt và accounts.txt (kèm tag NVR). KHÔNG BAO GIỜ lưu vào accounts_live.txt hoặc accounts_die.txt!

            if not ok_confirm:

                if active_mailbox and email_provider and hasattr(email_provider, "release_account"):

                    try:

                        email_provider.release_account(active_mailbox.email)

                    except Exception:

                        pass

                elapsed = time.time() - start_time

                fail_reason = (confirm_text if (not ok_confirm and "confirm_text" in locals() and confirm_text) else ("Không nhận được mã OTP từ hòm thư" if not (otp_code or conf_link) else "Xác nhận mã OTP với Facebook không thành công"))

                uid_probe = cookies.get("c_user", "") or cur_uid or ""

                is_graph_live = False

                g_network_err = False

                if uid_probe:

                    try:

                        g_ok, g_m = fb_checker.check_facebook_uid_live(uid_probe, proxy=task_input.proxy, timeout=5)

                        is_graph_live = g_ok

                        if "lỗi mạng" in g_m.lower():

                            g_network_err = True

                    except Exception:

                        g_network_err = True

                f_low = str(fail_reason).lower()
                c_low = str(confirm_text).lower() if "confirm_text" in locals() and confirm_text else ""
                is_not_die_msg = any(k in f_low or k in c_low for k in (
                    "không die", "khong die", "chưa die", "chua die", "nvr", "chờ xác minh",
                    "chua xac minh", "chưa xác minh", "dạng checkpoint khác", "form xác minh",
                    "chưa thoát trang", "chưa thoát form", "chưa hoàn tất"
                ))
                strict_cp_keywords = (
                    "tài khoản của bạn đã bị tạm ngưng", "chúng tôi đã tạm ngưng tài khoản",
                    "your account has been suspended", "we suspended your account",
                    "tài khoản của bạn đã bị vô hiệu hóa", "your account has been disabled",
                    "180 ngày để phản đối", "180 days to disagree", "phản đối quyết định",
                    "upload your id", "take a video selfie", "help/103873106370583",
                    "checkpoint/block", "checkpoint/disabled", "checkpoint/suspended",
                    "kháng nghị", "đình chỉ", "1501092823525282", "checkpoint 282",
                    "die 282", "die_282", "ufac"
                )
                has_die_keyword = (
                    (init_live_st in ("die_282", "die"))
                    or any(k in f_low for k in strict_cp_keywords)
                    or any(k in c_low for k in strict_cp_keywords)
                )
                is_checkpoint_err = bool(has_die_keyword or (not is_not_die_msg and ("checkpoint" in f_low or "checkpoint" in c_low)))

                if is_checkpoint_err:

                    uid = cookies.get("c_user", "") or cur_uid or ""

                    emit("error", {"message": f"🔴 Tài khoản UID {uid} dính Checkpoint 282 khi xác minh OTP: {fail_reason}"})

                    result = RegistrationResult(

                        success=False,

                        status="checkpoint",

                        identifier=target,

                        email=target,

                        uid=uid,

                        password=identity.get("password", ""),

                        cookies=cookies,

                        cookie_string=cookie_str,

                        token=token_val,

                        two_factor_secret=totp_secret,

                        name=full_name,

                        error_message=f"Dính Checkpoint 282: {fail_reason}",

                        elapsed_seconds=elapsed,

                        metadata={"checkpoint": True, "die": True, "error": fail_reason},

                    )

                    skip_file_save = task_input.extra.get("skip_auto_file_save", False)

                    if not skip_file_save:

                        try:

                            with open("accounts_die.txt", "a", encoding="utf-8-sig") as f_die:

                                f_die.write(f"{uid or target}|{identity.get('password', '')}|{target}|Checkpoint 282 ({fail_reason})\n")

                        except Exception:

                            pass

                    emit("failed", {"result": result, "message": f"Tài khoản dính Checkpoint 282 ({fail_reason})"})

                    return result



                valid_c_user = bool(cookies and "c_user" in cookies and str(cookies["c_user"]).isdigit() and str(cookies["c_user"]) != "0" and len(str(cookies["c_user"])) >= 8)

                valid_cur_uid = bool(cur_uid and str(cur_uid).isdigit() and str(cur_uid) != "0" and len(str(cur_uid)) >= 8)

                has_nvr_session = valid_c_user or valid_cur_uid

                if has_nvr_session:

                    uid = cookies.get("c_user", "") or cur_uid or ""

                    emit("warning", {"message": f"⚠️ Tài khoản UID {uid} chưa xác minh xong OTP ({fail_reason}) -> Lưu ở dạng NVR (Chờ xác minh - Tuyệt đối không DIE)."})

                    result = RegistrationResult(

                        success=False,

                        status="unverified",

                        identifier=target,

                        email=target,

                        uid=uid,

                        password=identity.get("password", ""),

                        cookies=cookies,

                        cookie_string=cookie_str,

                        token=token_val,

                        two_factor_secret=totp_secret,

                        name=full_name,

                        email_password=mail_pass,

                        email_raw=mail_raw,

                        email_rest=mail_rest,

                        error_message=f"Chưa xác minh OTP (Vẫn NVR - Không DIE): {fail_reason}",

                        elapsed_seconds=elapsed,

                        metadata={"unverified": True, "nvr": True, "not_die": True, "reg_mode": "nvr", "email": target},

                    )

                    skip_file_save = task_input.extra.get("skip_auto_file_save", False)

                    if not skip_file_save:

                        save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")

                        record_line = result.format_line(save_fmt)

                        try:

                            with open("accounts_unverified.txt", "a", encoding="utf-8-sig") as f_un:

                                f_un.write(record_line + "|NVR\n")

                            with open("accounts.txt", "a", encoding="utf-8-sig") as f_all:

                                f_all.write(record_line + "|NVR\n")

                        except Exception:

                            pass

                    emit("unverified", {"result": result, "message": f"Tài khoản UID {uid} chưa xác minh OTP (Lưu dạng NVR - KHÔNG DIE)"})

                    return result

                else:

                    emit("error", {"message": f"Thất bại tạo tài khoản VR OTP: {fail_reason}"})

                    result = RegistrationResult(

                        success=False,

                        status="failed",

                        identifier=target,

                        email=target,

                        uid="",

                        password=identity.get("password", ""),

                        name=full_name,

                        error_message=f"Thất bại VR OTP ({fail_reason})",

                        elapsed_seconds=elapsed,

                    )

                    emit("failed", {"result": result})

                    return result



            # Khi đã thành công VR OTP: Gán uid và cập nhật cookie c_user
            uid = cookies.get("c_user", "") or cur_uid or ""
            has_valid_acc = bool(uid and uid != "0" and str(uid).isdigit() and len(str(uid)) >= 8)
            if (cookies and any(k in cookies for k in ("c_user", "xs")) or ok_confirm) and has_valid_acc:



                # Trụ cột Bảo vệ Phiên: Làm ấm phiên sâu (Deep Session Warm-up) TRƯỚC KHI BẬT 2FA

                if task_input.extra.get("session_warmup", True):

                    try:

                        emit("step", {"step": 6, "name": "Làm ấm phiên sâu (Home Feed & Seed Interest) để chống Checkpoint 282...", "target": target})

                        warmup_headers = dict(base_headers)

                        warmup_headers["referer"] = f"https://{server}/"



                        # 1. Tải Home Feed và đồng bộ full cookie phiên

                        r_wf1 = client.get(f"https://{server}/", headers=warmup_headers, timeout=10)

                        _sync_response_cookies(client, r_wf1)

                        feed_read_time = random.uniform(3.0, 5.5)

                        _safe_sleep(feed_read_time)



                        # 2. Xem trang thông báo hoặc profile (mô phỏng người thật kiểm tra nick mới)

                        try:

                            r_wf2 = client.get(f"https://{server}/notifications.php", headers=warmup_headers, timeout=8)

                            _sync_response_cookies(client, r_wf2)

                            _safe_sleep(random.uniform(1.8, 3.2))

                        except Exception:

                            pass



                        # 4. Tương tác mồi an toàn (Seed Interest): Xem 1 Fanpage tin tức chính thống khớp quốc gia

                        try:

                            c_code = getattr(geo_profile, "country_code", "VN").upper() if geo_profile else "VN"

                            country_seeds = SEED_PAGES_BY_COUNTRY.get(c_code, ["bbcnews", "cnn", "natgeo"])

                            seed_page = random.choice(country_seeds)

                            client.get(f"https://{server}/{seed_page}/", headers=warmup_headers, timeout=8)

                            _safe_sleep(random.uniform(1.5, 2.8))

                        except Exception:

                            pass



                        # Cập nhật cookies mới nhất từ Facebook

                        for ck, cv in client.get_cookies().items():

                            cookies[ck] = cv

                        cookie_str = client.get_cookie_string()

                        emit("info", {"message": "[🛡️ Làm ấm phiên sâu] Đã tạo lịch sử duyệt web tự nhiên & đồng bộ phiên an toàn (Kháng Checkpoint 282/956)."})

                    except Exception as e:

                        logger.debug(f"Warmup exception: {e}")



                totp_secret = ""
                # Khoi tao totp_secret = "". Tien trinh bat 2FA TOTP THAT se duoc kich hoat
                # chinh xac NGAY SAU KHI tai khoan duoc xet duyet va xac nhan LIVE thuc te 100% (KO BIA).
                mail_pass = ""

                mail_raw = ""

                mail_rest = ""

                if active_mailbox:

                    mail_pass = getattr(active_mailbox, "password", "") or ""

                    mail_meta = getattr(active_mailbox, "metadata", {}) or {}

                    mail_raw = mail_meta.get("raw_line") or ""

                    if mail_raw and "|" in mail_raw:

                        mail_rest = mail_raw.split("|", 1)[1]

                    else:

                        mail_parts = []

                        if mail_pass:

                            mail_parts.append(str(mail_pass))

                        for k in ("refresh_token", "client_id", "rec_email", "rec_pwd"):

                            v = mail_meta.get(k)

                            if v:

                                mail_parts.append(str(v))

                        mail_rest = "|".join(mail_parts)

                        if not mail_raw and mail_rest:

                            mail_raw = f"{target}|{mail_rest}"

                    if not mail_pass and mail_rest:

                        mail_pass = mail_rest.split("|")[0].strip()



                token_val = ""

                if task_input.extra.get("extract_token", True):

                    try:

                        src_text = locals().get("response_text", "") or ""

                        if src_text:

                            m_tok = re.search(r'access_token["\s:=]+([A-Za-z0-9_]{35,})', src_text)

                            if m_tok:

                                token_val = m_tok.group(1)

                            else:

                                m_eaab = re.search(r'(EAAB[A-Za-z0-9]+)', src_text)

                                if m_eaab:

                                    token_val = m_eaab.group(1)

                    except Exception:

                        pass



                result = RegistrationResult(

                    success=True,

                    status="live",

                    identifier=target,

                    email=target,

                    uid=uid,

                    password=identity.get("password", ""),

                    token=token_val,

                    cookies=cookies,

                    cookie_string=cookie_str,

                    two_factor_secret=totp_secret,

                    name=full_name,

                    birthday=f"{identity.get('b_day')}/{identity.get('b_month')}/{identity.get('b_year')}",

                    gender=identity["sex_value"],

                    elapsed_seconds=elapsed,

                    email_password=mail_pass,

                    email_raw=mail_raw,

                    email_rest=mail_rest,

                    metadata={"identity": identity, "live_verified": True, "vr_verified": True, "otp_code": otp_code, "active_mailbox": getattr(active_mailbox, "metadata", {}) if active_mailbox else {}, "device_profile": {"name": profile.name, "brand": profile.brand, "model": profile.model, "os_version": getattr(profile, "os_version", ""), "user_agent": profile.user_agent, "web_user_agent": getattr(profile, "web_user_agent", ""), "app_user_agent": getattr(profile, "app_user_agent", ""), "dalvik_user_agent": getattr(profile, "dalvik_user_agent", ""), "viewport": f"{profile.viewport_width}x{profile.viewport_height}", "carrier": profile.carrier, "locale": profile.locale, "timezone": profile.timezone}},

                )

                # ====================================================================

                # BẢO VỆ CHỐNG DIE: WARMUP PHIÊN TƯƠNG TÁC THẬT (CHỐNG CHECKPOINT 282)

                # ====================================================================

                emit("step", {"step": 6, "name": f"Kích hoạt phiên thực tế: Lướt Newsfeed & Khởi tạo Profile (Chống Checkpoint 282)", "target": target})

                try:

                    warmup_headers = dict(base_headers)

                    warmup_headers["cookie"] = client.get_cookie_string()

                    warmup_headers["referer"] = f"https://{server}/reg/submit/"



                    # 1. Tải Newsfeed ban đầu (Establish initial session handshake)

                    _safe_sleep(random.uniform(0.15, 0.35))

                    r_post1 = client.get(f"https://{server}/", headers=warmup_headers, timeout=10)

                    _sync_response_cookies(client, r_post1)



                    # 2. Truy cập Profile cá nhân để kích hoạt timeline thực tế

                    _safe_sleep(random.uniform(1.0, 1.8))

                    r_post2 = client.get(f"https://{server}/me", headers=warmup_headers, timeout=10)

                    _sync_response_cookies(client, r_post2)



                    # 3. Cập nhật lại cookies phiên hoàn chỉnh

                    cookies = client.get_cookies()

                    cookie_str = client.get_cookie_string()

                    result.cookies = cookies

                    result.cookie_string = cookie_str

                    lifecycle.on_pause("Completed registration and initial warmup")

                    emit("info", {"message": f"[🛡️ Anti-Die Warmup] Hoàn tất kích hoạt phiên! Tài khoản UID {uid} đã được gắn kết an toàn vào hệ thống."})

                except Exception as e:

                    logger.debug(f"Warmup error: {e}")



                                # ====================================================================

                # KIEM DINH LIVE UID CHUAN XAC: DOI 10 GIAY DE FACEBOOK ON DINH PHIEN

                # ====================================================================

                verify_live = task_input.extra.get('verify_live_status', True)

                if verify_live and uid:

                    live_delay = 0.0 if _is_test_env() else float(task_input.extra.get('live_check_delay', 2.0))

                    if live_delay > 0:

                        emit('step', {'step': 7, 'name': f'Kiem dinh Live UID ({uid})...', 'target': target})

                        _safe_sleep(live_delay)



                    # live check: Ưu tiên kiểm định bằng session client đang mở (tốc độ cao 200-500ms, không treo cold-handshake)
                    live_status = "unknown"
                    live_msg = ""
                    if client:
                        try:
                            c_st, c_msg = fb_checker.check_registration_account_live(
                                client=client,
                                server=server,
                                uid=uid,
                                proxy=task_input.proxy,
                                timeout=5,
                            )
                            if c_st in ("live", "die", "nvr"):
                                live_status = "die_282" if c_st == "die" else c_st
                                live_msg = c_msg
                        except Exception as ex_c:
                            logger.debug(f"Direct client live check err: {ex_c}")

                    # Nếu client không xác định được, fallback sang check_facebook_account_live_status với timeout ngắn (5s)
                    if live_status == "unknown":
                        try:
                            live_status, live_msg = fb_checker.check_facebook_account_live_status(
                                cookie_str=client.get_cookie_string() if hasattr(client, "get_cookie_string") else "",
                                uid=uid,
                                password=identity.get("password", ""),
                                proxy=task_input.proxy,
                                timeout=5,
                            )
                        except Exception as ex_fb:
                            live_status = "unknown"
                            live_msg = f"Lỗi kiểm tra live: {ex_fb}"



                    # Đảm bảo không override status nếu nick vẫn NVR hoặc dính Checkpoint

                    if live_status == "die_282":
                        emit('warning', {'message': '[Luong ' + str(wid) + '] Facebook quet Checkpoint 282 sau ' + str(int(live_delay)) + 's: ' + str(live_msg) + ' (UID ' + str(uid) + ')'})

                        result.success = False

                        result.status = 'checkpoint'

                        result.error_message = 'Dinh Checkpoint 282 sau ' + str(int(live_delay)) + 's (' + str(live_msg) + ')'

                        result.metadata['checkpoint'] = True

                        result.metadata['live_check'] = live_msg



                        skip_file_save = task_input.extra.get('skip_auto_file_save', False)

                        if not skip_file_save:

                            try:

                                with open('accounts_die.txt', 'a', encoding='utf-8-sig') as f_die:

                                    f_die.write(str(uid) + '|' + str(identity.get('password', '')) + '|' + str(target) + '|Checkpoint 282 (' + str(live_msg) + ')' + chr(10))

                            except Exception:

                                pass

                        emit('failed', {'result': result, 'message': 'Tai khoan UID ' + str(uid) + ' bi Checkpoint 282 sau ' + str(int(live_delay)) + 's (' + str(live_msg) + ')'})

                        return result



                    if ok_confirm and live_status == 'live':
                        # Tài khoản đã xác minh OTP thành công VÀ kiểm chứng LIVE thực tế -> Giữ nick LIVE!
                        result.success = True
                        result.status = 'live'
                        result.metadata['vr_verified'] = True
                        result.metadata['live_verified'] = True
                    else:
                        emit('warning', {'message': '[Luong ' + str(wid) + '] Tai khoan UID ' + str(uid) + ' chua vao duoc Facebook (' + str(live_msg) + ') -> Luu dang NVR (Khong DIE).'})
    
                        result.success = False
    
                        result.status = 'unverified'
    
                        result.error_message = 'Chua thoat trang xac minh OTP (Van NVR - Khong DIE): ' + str(live_msg)
    
                        result.metadata['unverified'] = True
    
                        result.metadata['nvr'] = True
    
                        result.metadata['not_die'] = True
    
                        result.metadata['live_check'] = live_msg
    
    
    
                        skip_file_save = task_input.extra.get('skip_auto_file_save', False)
    
                        if not skip_file_save:
    
                            save_fmt = task_input.extra.get('save_format', 'UID|PASS|2FA|COOKIE|TOKEN|EMAIL')
    
                            record_line = result.format_line(save_fmt)
    
                            try:
    
                                with open('accounts_unverified.txt', 'a', encoding='utf-8-sig') as f_un:
    
                                    f_un.write(record_line + '|NVR\n')
    
                                with open('accounts.txt', 'a', encoding='utf-8-sig') as f_all:
    
                                    f_all.write(record_line + '|NVR\n')
    
                            except Exception:
    
                                pass
    
                        emit('unverified', {'result': result, 'message': 'Tai khoan UID ' + str(uid) + ' van o trang thai NVR (Khong DIE)'})
    
                        return result



                    # Tai khoan da xac minh OTP thanh cong: Giu nguyen Live

                    emit('info', {'message': '[Luong ' + str(wid) + '] DA XAC NHAN LIVE THUC TE! ' + str(live_msg) + ' (UID ' + str(uid) + ')'})

                    result.success = True

                    result.status = 'live'

                    result.metadata['live_verified'] = True

                    result.metadata['vr_verified'] = True

                    result.metadata['live_check'] = live_msg





                                # ====================================================================
                # KÍCH HOẠT 2FA TOTP THẬT CHO TÀI KHOẢN LIVE THỰC TẾ (KO BỊA)
                # ====================================================================
                if result.success and result.status == "live" and uid and task_input.extra.get('enable_2fa', False) and not totp_secret:
                    try:
                        pause_2fa = 0.0 if _is_test_env() else random.uniform(1.0, 2.0)
                        if pause_2fa > 0:
                            emit('step', {'step': 8, 'name': f'Nghỉ nhận thức ({pause_2fa:.1f}s) rồi kích hoạt 2FA TOTP THẬT (UID {uid})...', 'target': target})
                            _safe_sleep(pause_2fa)

                        # top-level enable_facebook_2fa
                        ok_2fa, sec_2fa, otp_2fa, msg_2fa = enable_facebook_2fa(
                            client=client,
                            uid=uid,
                            password=identity.get('password', ''),
                            server='www.facebook.com',
                            fb_dtsg=fb_dtsg or None,
                            lsd=lsd or None,
                            emit=emit,
                        )
                        if ok_2fa and sec_2fa:
                            totp_secret = sec_2fa
                            result.two_factor_secret = sec_2fa
                            emit('info', {'message': f'[2FA] KÍCH HOẠT 2FA TOTP THẬT THÀNH CÔNG! Secret: {sec_2fa} (OTP hiện tại: {otp_2fa})'})
                        else:
                            totp_secret = ''
                            result.two_factor_secret = ''
                            emit('warning', {'message': f'[2FA] Không kích hoạt được 2FA thật trên Facebook ({msg_2fa}). Lưu tài khoản Live không 2FA (KO BỊA 2FA).'})
                    except Exception as ex_2fa:
                        emit('warning', {'message': f'[2FA] Lỗi trong tiến trình kích hoạt 2FA: {ex_2fa}'})

                if is_vr and target:

                    from core.email_service import remove_hotmail

                    remove_hotmail(target)

                skip_file_save = task_input.extra.get("skip_auto_file_save", False)

                if not skip_file_save:

                    save_fmt = task_input.extra.get("save_format", "UID|PASS|2FA|COOKIE|TOKEN|EMAIL")

                    if totp_secret and "2FA" not in str(save_fmt).upper():
                        if "PASS|" in str(save_fmt).upper():
                            save_fmt = str(save_fmt).replace("PASS|", "PASS|2FA|")
                        elif "PASSWORD|" in str(save_fmt).upper():
                            save_fmt = str(save_fmt).replace("PASSWORD|", "PASSWORD|2FA|")
                        else:
                            save_fmt = f"{save_fmt}|2FA"
                    record_line = result.format_line(save_fmt)

                    is_truly_live = bool(
                        result.success
                        and result.status == "live"
                        and not result.metadata.get("unverified")
                        and not result.metadata.get("nvr")
                        and not result.metadata.get("checkpoint")
                    )
                    target_files = ["accounts_live.txt", "accounts.txt"] if is_truly_live else ["accounts_unverified.txt", "accounts.txt"]
                    uid_val = str(result.uid or "").strip()

                    for out_file in target_files:
                        try:
                            tag_suffix = "" if is_truly_live or "|NVR" in record_line else "|NVR"
                            line_to_write = record_line + tag_suffix
                            already_exists = False
                            if os.path.exists(out_file) and uid_val and uid_val != "N/A":
                                with open(out_file, "r", encoding="utf-8-sig", errors="ignore") as f_chk:
                                    already_exists = any(
                                        l.strip().startswith(uid_val + "|") or f"c_user={uid_val}" in l for l in f_chk
                                    )
                            if not already_exists:
                                with open(out_file, "a", encoding="utf-8-sig") as f:
                                    f.write(line_to_write + "\n")
                        except Exception:
                            pass

# Handled exclusively by GUI based on user checkbox (auto_ttc_pipeline)

                    if is_truly_live and uid_val and uid_val != "N/A" and os.path.exists("accounts_unverified.txt"):
                        try:
                            with open("accounts_unverified.txt", "r", encoding="utf-8-sig", errors="ignore") as f_un:
                                un_lines = f_un.readlines()
                            filtered = [l for l in un_lines if not (l.strip().startswith(uid_val + "|") or f"c_user={uid_val}" in l)]
                            if len(filtered) < len(un_lines):
                                with open("accounts_unverified.txt", "w", encoding="utf-8-sig") as f_un:
                                    f_un.writelines(filtered)
                        except Exception:
                            pass

                emit("success", {"result": result})

                return result



            # Không có cookies auth

            debug_msg = "Facebook không tạo được phiên đăng nhập"

            try:

                raw_json = resp_text.split("for (;;);")[1] if "for (;;);" in resp_text else resp_text

                err_data = json.loads(raw_json)

                debug_msg = str(err_data)[:150]

                cur_fail_reason = locals().get("fail_reason", "Chưa nhận diện được phiên đăng nhập")

                debug_msg = (f"Facebook từ chối tạo tài khoản: {err_msg}" if err_msg else f"Thất bại VR OTP ({cur_fail_reason})")

            except Exception:

                pass



            result = RegistrationResult(

                success=False,

                status="failed",

                identifier=target,

                password=identity.get("password", ""),

                name=full_name,

                error_message=debug_msg,

                elapsed_seconds=elapsed,

            )

            emit("failed", {"result": result})

            return result



        except ProxyConnectionError as e:

            elapsed = time.time() - start_time

            res = RegistrationResult(

                success=False,

                status="error",

                identifier=target,

                error_message=f"Lỗi kết nối Proxy: {e}",

                elapsed_seconds=elapsed,

            )

            emit("error", {"result": res})

            return res

        except RequestTimeoutError as e:

            elapsed = time.time() - start_time

            res = RegistrationResult(

                success=False,

                status="error",

                identifier=target,

                error_message=f"Quá thời gian kết nối (Timeout): {e}",

                elapsed_seconds=elapsed,

            )

            emit("error", {"result": res})

            return res

        except Exception as e:

            elapsed = time.time() - start_time

            res = RegistrationResult(

                success=False,

                status="error",

                identifier=target,

                error_message=str(e),

                elapsed_seconds=elapsed,

            )

            emit("error", {"result": res})

            return res

        finally:

            if is_vr and active_mailbox and email_provider and not ok_confirm:

                try:

                    if locals().get("post_resp") is None:

                        # Email chua tung gui submit len Facebook (loi proxy/timeout) -> Tra ve kho

                        if hasattr(email_provider, "release_account"):

                            email_provider.release_account(active_mailbox.email)

                    else:

                        # Mail da gui len Facebook nhung chua xac minh -> Go khoi kho

                        if hasattr(email_provider, "remove_account"):

                            email_provider.remove_account(active_mailbox.email)

                except Exception:

                    pass

            if client:

                try:

                    client.close()

                except Exception:

                    pass


def register_via_legacy_web(
    task_input: RegistrationInput,
    event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    timeout: int = 30,
) -> RegistrationResult:
    """Standalone function executing Facebook Legacy NV Web registration (Mr-SxR Engine)."""
    service = RegistrationService(event_callback=event_callback, timeout=timeout)
    return service.register_legacy_nv(task_input)


def create_worker(wid, phone_number, proxy_data, config, counter=None) -> RegistrationResult:
    """
    Backward-compatible wrapper function matching create_worker from Mr-SxR (facebook-account-registration).
    Executes registration flow on worker thread and updates terminal counter if provided.
    """
    service = RegistrationService()
    task = RegistrationInput(
        identifier=phone_number,
        proxy=proxy_data,
        device_type=config.get("device_type", "Android"),
        browser_type=config.get("browser_type", "Default"),
        server=config.get("server", "m.facebook.com"),
        extra={
            "worker_id": wid,
            "reg_mode": "legacy_nv",
            "password_config": config.get("password_config"),
            "random_server": bool(config.get("random_server", False) or str(config.get("server", "")).lower() == "random"),
            "random_subset": bool(config.get("random_subset", False) or config.get("server_mode") == "subset"),
            "server_pool": config.get("server_pool", []),
        },
    )
    result = service.register_legacy_nv(task)

    if counter and hasattr(counter, "update"):
        try:
            from ui.colors import GREEN, RED, ORANGE, YELLOW
        except Exception:
            GREEN = RED = ORANGE = YELLOW = ""

        if result.success:
            counter.update(
                "success",
                number=phone_number,
                message=f" Name : {result.name} | Birthday : {result.birthday} \n [SxR-NV] {result.uid} | {result.password} | {result.cookie_string}",
                color=GREEN,
            )
            try:
                from core.number_manager import remove_number
                remove_number(phone_number)
            except Exception:
                pass
            _save_success_output(f"{result.uid}|{result.password}|{result.cookie_string}")
        elif result.status == "failed":
            counter.update(
                "failed",
                number=phone_number,
                message=f"Failed | Debug: {result.error_message}",
                color=YELLOW,
            )
        else:
            counter.update("error", number=phone_number, message=result.error_message or "Error", color=RED)

    return result


def generate_identity(
    password_config: Optional[Union[Dict[str, Any], str]] = None,
    locale: str = "vi_VN",
    name_type: Optional[str] = None,
    custom_file: str = "names.txt",
    mix_file_names: bool = False,
    geo_profile: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Standalone identity generator matching Mr-SxR generate_identity(password_config).
    Generates first name, last name, sex_value, birthday, and password.
    """
    svc = RegistrationService()
    return svc.generate_identity(
        password_seed=password_config,
        locale=locale,
        name_type=name_type,
        custom_file=custom_file,
        mix_file_names=mix_file_names,
        geo_profile=geo_profile,
    )


# Re-export auxiliary managers and tools from Mr-SxR architecture for unified 100% integration
from core.batch_runner import BatchRunner, BatchSummary, run_batch
from core.counter import Counter
from core.device_manager import select_device, select_browser, select_server
from core.password_manager import generate_random_password, select_password_config
from core.number_manager import (
    load_numbers,
    save_numbers,
    remove_number,
    get_next_number,
    process_file_input,
    get_number_list_filepath,
)
from core.path_manager import (
    is_termux_or_mobile,
    get_base_storage_dir,
    get_output_dir,
    get_output_filepaths,
)
from core.proxy_manager import (
    ProxyManager,
    format_proxy_for_requests,
    get_proxy_list,
    create_proxy_cycle,
    get_no_proxy_data,
)
from core.session_builder import (
    create_http_session,
    setup_session_cookies,
    build_request_context,
)
from core.settings_manager import load_settings
from core.user_agent import (
    get_android_browser_ua,
    get_iphone_app_ua,
    get_android_app_ua,
    get_kaios_ua,
    get_windows_phone_ua,
    get_blackberry_ua,
)
from core.locale_data import get_locale, get_timezone, get_language
from core.worker_manager import get_worker_count


def retrieve_and_verify_otp(*args, **kwargs):
    """Top-level function to retrieve and verify Facebook OTP using RegistrationService."""
    service = RegistrationService()
    return service.retrieve_and_verify_otp(*args, **kwargs)

__all__ = [
    "RegistrationService",
    "bind_facebook_session_email",
    "bind_facebook_session_contactpoint",
    "trigger_facebook_confirmation_resend",
    "retrieve_and_verify_otp",
    "register_via_legacy_web",
    "create_worker",
    "_save_success_output",
    "SERVER_MAP",
    "resolve_facebook_server",
    "LEGACY_DEVICE_TYPES",
    "_search",
    "generate_identity",
    # Re-exported Mr-SxR core architecture components:
    "BatchRunner",
    "BatchSummary",
    "run_batch",
    "Counter",
    "select_device",
    "select_browser",
    "select_server",
    "generate_random_password",
    "select_password_config",
    "load_numbers",
    "save_numbers",
    "remove_number",
    "get_next_number",
    "process_file_input",
    "get_number_list_filepath",
    "is_termux_or_mobile",
    "get_base_storage_dir",
    "get_output_dir",
    "get_output_filepaths",
    "ProxyManager",
    "format_proxy_for_requests",
    "get_proxy_list",
    "create_proxy_cycle",
    "get_no_proxy_data",
    "create_http_session",
    "setup_session_cookies",
    "build_request_context",
    "load_settings",
    "get_android_browser_ua",
    "get_iphone_app_ua",
    "get_android_app_ua",
    "get_kaios_ua",
    "get_windows_phone_ua",
    "get_blackberry_ua",
    "get_locale",
    "get_timezone",
    "get_language",
    "get_worker_count",
]
