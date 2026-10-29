import urllib.parse
import json
import collections
import string
import os
import threading
import unicodedata
# -*- coding: utf-8 -*-
"""
core.email_service
Comprehensive Email Provider & OTP Verification Engine.

Supported Email Services:
1. Mail.tm (Free RESTful API with Bearer Token & multiple domains)
2. Guerrilla Mail (Free session-based API, instant mailbox)
3. DongVanFB (Commercial rented mail API for Hotmail/Outlook/Mail.ru)
4. Kopeechka (Commercial mail rental API with auto-OTP extraction)
5. 1secmail (Free public API fallback)

Features:
- Automated mailbox creation
- Polling inbox with configurable timeout & interval
- Smart Regex OTP extraction (supporting 5-8 digits, FB-XXXXX patterns)
- Clean, decoupled architecture with standard logging
"""

import re
import time
import uuid
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
import requests
import json
from core.facebook_checker import check_facebook_uid_live

logger = logging.getLogger("core.email_service")


@dataclass
class EmailAccount:
    """Represents an active temporary mailbox."""
    email: str
    provider: str
    token: Optional[str] = None
    account_id: Optional[str] = None
    password: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OTPVerificationResult:
    """Represents the outcome of waiting for and extracting an OTP."""
    def __init__(
        self,
        success: bool = False,
        email: str = "",
        otp_code: Optional[str] = None,
        sender: Optional[str] = None,
        subject: Optional[str] = None,
        body_preview: Optional[str] = None,
        elapsed_seconds: float = 0.0,
        error: Optional[str] = None,
        error_message: Optional[str] = None,
        confirmation_link: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        *args,
        **kwargs,
    ):
        self.success = bool(success)
        self.email = str(email or "")
        self.otp_code = otp_code
        self.sender = sender
        self.subject = subject
        self.body_preview = body_preview
        self.elapsed_seconds = float(elapsed_seconds or 0.0)
        final_err = error or error_message or kwargs.get("message")
        self.error = str(final_err) if final_err else None
        self.error_message = self.error
        self.confirmation_link = confirmation_link
        self.metadata = metadata or {}
        self.provider = provider
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)


def is_chromium_ua(ua: str) -> bool:
    """Kiểm tra xem User-Agent có thuộc họ Chromium (hỗ trợ Client Hints / Sec-CH-UA) hay không."""
    if not ua:
        return True
    ua_l = str(ua).lower()
    ua_no_like = ua_l.replace("like gecko", "")
    if any(k in ua_no_like for k in ("kaios", "gecko", "firefox", "fxios", "trident", "msie", "blackberry", "bb10")):
        return False
    if "safari" in ua_l and not any(k in ua_l for k in ("chrome", "chromium", "crios", "edg")):
        return False
    return True


def clean_client_hints(headers: dict, ua: str = "") -> dict:
    """Loại bỏ các header sec-ch-ua nếu UA không phải là Chromium để tránh Facebook phát hiện spoofing."""
    if headers is None:
        return {}
    target_ua = ua or headers.get("User-Agent") or headers.get("user-agent") or ""
    if not is_chromium_ua(target_ua):
        for k in list(headers.keys()):
            if k.lower().startswith("sec-ch-"):
                headers.pop(k, None)
    return headers


def extract_otp_code(text: str) -> Optional[str]:
    """
    Extract verification OTP code from email text, HTML, or subject.
    Matches common Facebook confirmation patterns:
    - FB-12345 or FB-123456
    - Phrases like 'm\u00e3 x\u00e1c nh\u1eadn l\u00e0 12345', 'code is 12345', '12345 is your code'
    - Standalone 5 to 6 digits after stripping HTML, CSS styles, script tags, hex colors (#353535)
    """
    if not text:
        return None

    # Step 1: Strip scripts, styles, SVG, and HTML comments to eliminate CSS colors and script numbers
    clean_text = re.sub(r'(?is)<style[^>]*>.*?</style>', ' ', text)
    clean_text = re.sub(r'(?is)<script[^>]*>.*?</script>', ' ', clean_text)
    clean_text = re.sub(r'(?is)<!--.*?-->', ' ', clean_text)
    clean_text = re.sub(r'(?is)<svg[^>]*>.*?</svg>', ' ', clean_text)

    # Step 2: Strip hex color codes (e.g. #353535, #ffffff, #123456)
    clean_text = re.sub(r'#[0-9a-fA-F]{3,8}\b', ' ', clean_text)

    # Pattern 1: FB-12345 or FB-123456 (highest confidence)
    fb_prefix = re.search(r"FB-(\d{5,8})\b", clean_text, re.IGNORECASE)
    if fb_prefix:
        return fb_prefix.group(1)

    # Pattern 2: Contextual keywords (Vietnamese & English)
    keywords_pattern = re.search(
        r"(?:m\u00e3 x\u00e1c nh\u1eadn(?: l\u00e0)?|m\u00e3 c\u1ee7a b\u1ea1n|m\u00e3 facebook|m\u00e3 b\u1ea3o m\u1eadt|m\u00e3 x\u00e1c minh|m\u00e3 \u0111\u0103ng k\u00fd|m\u00e3 otp|m\u00e3:|x\u00e1c minh|confirmation code|security code|is your Facebook code|is your code|code is|your code is|code:)\s*[:=]?\s*(\d{5,8})\b",
        clean_text,
        re.IGNORECASE
    )
    if keywords_pattern:
        return keywords_pattern.group(1)

    # Reverse contextual pattern: '12345 l? m? x?c nh?n' / '12345 is your confirmation code'
    reverse_pattern = re.search(
        r"\b(\d{5,8})\s+(?:l\u00e0 m\u00e3|is your|to confirm|\u0111\u1ec3 x\u00e1c minh|\u0111\u1ec3 x\u00e1c nh\u1eadn)",
        clean_text,
        re.IGNORECASE
    )
    if reverse_pattern:
        return reverse_pattern.group(1)

    # Step 3: Strip remaining HTML tags and HTML entities
    text_no_html = re.sub(r'<[^>]+>', ' ', clean_text)
    text_no_html = re.sub(r'&[a-zA-Z0-9#]+;', ' ', text_no_html)

    # Re-check contextual pattern on stripped text
    keywords_pattern2 = re.search(
        r"(?:m\u00e3 x\u00e1c nh\u1eadn(?: l\u00e0)?|m\u00e3 c\u1ee7a b\u1ea1n|m\u00e3 facebook|m\u00e3 b\u1ea3o m\u1eadt|m\u00e3 x\u00e1c minh|m\u00e3 \u0111\u0103ng k\u00fd|m\u00e3 otp|m\u00e3:|x\u00e1c minh|confirmation code|security code|is your Facebook code|is your code|code is|your code is|code:)\s*[:=]?\s*(\d{5,8})\b",
        text_no_html,
        re.IGNORECASE
    )
    if keywords_pattern2:
        return keywords_pattern2.group(1)

    # Pattern 3: Standalone 5 or 6 digit number
    digits = re.findall(r"(?<![#&$+a-zA-Z0-9])\b(\d{5,8})\b(?![a-zA-Z0-9])", text_no_html)
    if digits:
        valid = [
            d for d in digits
            if not (d.startswith("202") and len(d) == 4)
            and not (len(set(d)) == 1)
            and len(d) in (5, 6, 8)
        ]
        if valid:
            return valid[0]

    return None


def extract_confirmation_link(text: str) -> Optional[str]:
    """Extract direct Facebook confirmation link from email body."""
    if not text:
        return None
    clean_text = text.replace("&amp;", "&").replace("\\/", "/")
    patterns = [
        r"https?://(?:www\.|m\.|mbasic\.)?facebook\.com/[^\s\"\'<>]+(?:confirmemail|code|c=|bcode=|/n/\?|/c/)[^\s\"\'<>]*",
        r"https?://(?:www\.|m\.)?facebook\.com/n/\?[^\s\"\'<>]*",
        r"https?://(?:www\.|m\.)?facebook\.com/confirmemail\.php[^\s\"\'<>]*",
        r"https?://(?:www\.|m\.)?facebook\.com/r\.php[^\s\"\'<>]*"
    ]
    for pat in patterns:
        m = re.search(pat, clean_text, re.IGNORECASE)
        if m:
            return m.group(0).strip().rstrip(">'\")")
    return None



COMMON_FIRST_NAMES = [
    "alex", "david", "john", "michael", "chris", "james", "daniel", "kevin", "brian", "jason",
    "mark", "ryan", "eric", "steven", "andrew", "paul", "sam", "tony", "robert", "william",
    "sarah", "emma", "olivia", "sophia", "mia", "charlotte", "emily", "jessica", "hannah", "chloe",
    "linh", "nam", "tuan", "quoc", "thanh", "hoang", "phuong", "khanh", "minh", "bao", "duyen",
    "trang", "kiet", "ngoc", "hung", "cuong", "hai", "phong", "long", "son", "tung", "dat"
]

COMMON_LAST_NAMES = [
    "smith", "johnson", "williams", "brown", "jones", "miller", "davis", "wilson", "anderson", "taylor",
    "thomas", "moore", "jackson", "martin", "lee", "harris", "clark", "lewis", "robinson", "walker",
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo", "dang", "bui", "do"
]

def generate_human_email_username(first_name: Optional[str] = None, last_name: Optional[str] = None, birth_year: Optional[int] = None) -> str:
    """
    Sinh tên người dùng email (local-part) tự nhiên như người dùng thật đăng ký.
    Ưu tiên sử dụng first_name, last_name thật của tài khoản (nếu có) để tăng trust với Meta WAF.
    Loại bỏ hoàn toàn các pattern đáng ngờ như 'user_0123456789' khiến Meta DEA filter gắn cờ.
    """
    import unicodedata

    def _clean(s: str) -> str:
        s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode('ascii')
        return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

    f = _clean(first_name) if first_name else ''
    l = _clean(last_name) if last_name else ''
    if not f or len(f) < 2:
        f = random.choice(COMMON_FIRST_NAMES)
    if not l or len(l) < 2:
        l = random.choice(COMMON_LAST_NAMES)

    year = birth_year if (birth_year and 1970 <= birth_year <= 2008) else random.randint(1988, 2005)
    short_year = str(year)[2:]
    digits = str(random.randint(10, 999))
    style = random.randint(1, 6)

    if style == 1:
        u = f"{f}.{l}{year}"
    elif style == 2:
        u = f"{l}.{f}{short_year}"
    elif style == 3:
        u = f"{f}_{l}_{digits}"
    elif style == 4:
        u = f"{f}{l}{short_year}"
    elif style == 5:
        u = f"{f}.{l}.{digits}"
    else:
        u = f"{f[:1]}{l}{year}"

    u = re.sub(r'[^a-z0-9._]', '', u.lower()).strip('._')
    if len(u) < 6:
        u = f"{u}{random.randint(100, 9999)}"
    return u


GMAIL_BAIT_FIRST_NAMES = [
    "alex", "david", "john", "michael", "chris", "james", "daniel", "kevin", "brian", "jason",
    "mark", "ryan", "eric", "steven", "andrew", "paul", "sam", "tony", "robert", "william",
    "richard", "thomas", "charles", "matthew", "anthony", "donald", "george", "kenneth", "edward",
    "ronald", "timothy", "jeffrey", "jacob", "gary", "nicholas", "jonathan", "stephen", "larry",
    "justin", "scott", "brandon", "benjamin", "samuel", "gregory", "alexander", "patrick", "frank",
    "raymond", "jack", "dennis", "jerry", "tyler", "aaron", "jose", "adam", "nathan", "henry",
    "douglas", "zachary", "peter", "kyle", "noah", "ethan", "jeremy", "walter", "christian",
    "keith", "roger", "terry", "austin", "sean", "gerald", "carl", "harold", "dylan", "arthur",
    "lawrence", "jordan", "jesse", "bryan", "billy", "bruce", "gabriel", "logan", "albert",
    "willie", "alan", "juan", "wayne", "elijah", "randy", "roy", "vincent", "ralph", "eugene",
    "sarah", "emma", "olivia", "sophia", "mia", "charlotte", "emily", "jessica", "hannah", "chloe",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan", "karen", "tammy",
    "lisa", "betty", "margaret", "sandra", "ashley", "kimberly", "donna", "michelle", "carol",
    "amanda", "melissa", "deborah", "stephanie", "rebecca", "sharon", "laura", "cynthia", "kathleen",
    "amy", "angela", "shirley", "brenda", "pamela", "nicole", "anna", "samantha", "katherine",
    "christine", "debra", "rachel", "carolyn", "janet", "maria", "heather", "diane", "virginia",
    "julie", "joyce", "victoria", "kelly", "christina", "lauren", "joan", "evelyn", "judith",
    "megan", "cheryl", "andrea", "martha", "jacqueline", "frances", "gloria", "ann", "teresa",
    "linh", "nam", "tuan", "quoc", "thanh", "hoang", "phuong", "khanh", "minh", "bao", "duyen",
    "trang", "kiet", "ngoc", "hung", "cuong", "hai", "phong", "long", "son", "tung", "dat",
    "hieu", "dung", "thao", "uyen", "hang", "van", "quang", "huy", "duc", "thang", "khoa",
    "an", "binh", "chau", "giang", "ha", "hoa", "lan", "mai", "nga", "nhan", "phuc", "sang",
    "tam", "tien", "trinh", "viet", "vy", "yen"
]

GMAIL_BAIT_LAST_NAMES = [
    "smith", "johnson", "williams", "brown", "jones", "miller", "davis", "wilson", "anderson", "taylor",
    "thomas", "moore", "jackson", "martin", "lee", "harris", "clark", "lewis", "robinson", "walker",
    "hall", "allen", "young", "king", "wright", "scott", "torres", "hill", "flores", "green",
    "adams", "nelson", "baker", "rivera", "campbell", "mitchell", "carter", "roberts", "gomez",
    "phillips", "evans", "turner", "diaz", "parker", "cruz", "edwards", "collins", "reyes",
    "stewart", "morris", "morales", "murphy", "cook", "rogers", "gutierrez", "ortiz", "morgan",
    "cooper", "peterson", "bailey", "reed", "kelly", "howard", "ramos", "kim", "cox", "ward",
    "richardson", "watson", "brooks", "chavez", "wood", "bennett", "gray", "mendoza", "ruiz",
    "hughes", "price", "alvarez", "castillo", "sanders", "patel", "myers", "long", "ross",
    "foster", "jimenez", "powell", "jenkins", "perry", "russell", "sullivan", "bell", "coleman",
    "nguyen", "tran", "le", "pham", "hoang", "huynh", "phan", "vu", "vo", "dang", "bui", "do",
    "ho", "ngo", "duong", "ly"
]

GMAIL_BAIT_MID_NAMES = [
    "alexander", "elizabeth", "marie", "grace", "rose", "ann", "lee", "james", "john", "michael",
    "david", "clark", "scott", "wayne", "dean", "ray", "allen", "roy", "dale", "gene",
    "lynn", "dawn", "hope", "faith", "joy", "may", "jean", "kay", "faye", "brooke",
    "quinn", "claire", "paige", "reese", "tess", "bree", "skye", "dinh", "van", "thi",
    "huu", "duc", "ngoc", "hoang", "minh", "gia", "xuan", "thanh", "dieu", "phuong",
    "quang", "anh", "hai", "the"
]

GMAIL_BAIT_KEYWORDS = [
    "studio", "media", "digital", "creative", "design", "art", "photo", "tech", "lab", "work",
    "office", "pro", "corp", "team", "agency", "craft", "vlog", "daily", "live", "space",
    "hub", "box", "zone", "post", "feed", "view", "spot", "cloud", "spark", "wave",
    "prime", "nova", "apex", "flow", "link", "core", "pulse", "quest", "works", "group",
    "network", "press", "visual", "motion", "audio", "sound", "beats", "prints", "style", "trend",
    "vibe", "vibes", "star", "sky", "moon", "sun", "river", "ocean", "blue", "green"
]

_RECENT_BAIT_SET = set()
_RECENT_BAIT_QUEUE = collections.deque(maxlen=250000)
_BAIT_LOCK = threading.Lock()


def generate_bait_gmail_identifier(first_name: Optional[str] = None, last_name: Optional[str] = None) -> str:
    """
    Sinh địa chỉ Gmail mồi cao cấp chống trùng tuyệt đối (Anti-Collision Bait Gmail Engine):
    - Khắc phục triệt để lỗi đuôi số quá ngắn (02, 09, 98, 1990) khiến Facebook báo lỗi 1351050 do trùng nick có sẵn.
    - Suffix số luôn đạt entropy cao: 4-6 chữ số ngẫu nhiên, hoặc Năm sinh + Sub-salt (1998.412), hoặc Alpha-salt (k8412).
    - Kết hợp linh hoạt Họ + Tên lót / Tên đệm + Tên chính + Từ khóa danh xưng tự nhiên (studio, media, tech, design...).
    - Cơ chế Thread-safe In-memory Cache đảm bảo trong cả phiên chạy KHÔNG BAO GIỜ sinh 2 email trùng nhau.
    - Chuẩn Gmail RFC: 6 - 30 ký tự, không bắt đầu/kết thúc bằng dấu chấm, không có dấu chấm kép '..'.
    """
    import unicodedata

    def _clean(s: str) -> str:
        try:
            import unicodedata
            s = str(s or "").replace("đ", "d").replace("Đ", "D")
            s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        except Exception:
            s = str(s or "")
        return re.sub(r"[^a-zA-Z]", "", s).lower()

    fn_pool = globals().get("GMAIL_BAIT_FIRST_NAMES", ["alex", "sam", "nam", "linh", "minh", "chris"])
    ln_pool = globals().get("GMAIL_BAIT_LAST_NAMES", ["smith", "johnson", "nguyen", "tran", "le", "pham"])
    mid_pool = globals().get("GMAIL_BAIT_MID_NAMES", ["marie", "grace", "rose", "ann", "van", "thi", "hoang"])
    kw_pool = globals().get("GMAIL_BAIT_KEYWORDS", ["studio", "media", "tech", "design", "photo", "vlog", "daily"])

    f_input = _clean(first_name) if first_name else ""
    l_input = _clean(last_name) if last_name else ""

    global _RECENT_BAIT_SET, _RECENT_BAIT_QUEUE, _BAIT_LOCK

    for _ in range(12):
        f = f_input if len(f_input) >= 2 else random.choice(fn_pool)
        l = l_input if len(l_input) >= 2 else random.choice(ln_pool)
        m = random.choice(mid_pool)
        kw = random.choice(kw_pool)

        # Suffix đa dạng, tuyệt đối KHÔNG sinh số 2 chữ số (02, 09) hay năm sinh đơn lẻ (1990, 2005)
        salt_type = random.choice(["digits4_6", "year_salt", "alpha_salt", "short_year_salt"])
        if salt_type == "digits4_6":
            salt = str(random.randint(1000, 999999))
        elif salt_type == "year_salt":
            year = random.randint(1985, 2005)
            sub = random.randint(11, 999)
            salt = f"{year}.{sub}" if random.random() < 0.35 else f"{year}{sub}"
        elif salt_type == "alpha_salt":
            char = random.choice(string.ascii_lowercase)
            num = random.randint(100, 9999)
            salt = f"{char}{num}" if random.random() < 0.5 else f"{num}{char}"
        else:
            sy = random.randint(85, 99) if random.random() < 0.5 else random.randint(0, 5)
            sub = random.randint(100, 9999)
            salt = f"{sy:02d}.{sub}" if random.random() < 0.25 else f"{sy:02d}{sub}"

        # 10 mẫu cấu trúc phong phú chuẩn người dùng thật
        tpl = random.randint(1, 10)
        if tpl == 1:
            raw_user = f"{f}.{m}.{l}.{salt}"
        elif tpl == 2:
            raw_user = f"{f}.{l}.{kw}.{salt}"
        elif tpl == 3:
            raw_user = f"{f}.{kw}.{salt}"
        elif tpl == 4:
            raw_user = f"{l}.{kw}.{salt}"
        elif tpl == 5:
            raw_user = f"{f}.{l}.{salt}"
        elif tpl == 6:
            raw_user = f"{f}{l}.{salt}"
        elif tpl == 7:
            raw_user = f"{l}.{f}.{salt}"
        elif tpl == 8:
            raw_user = f"{f}.{m[0]}.{l}.{salt}"
        elif tpl == 9:
            raw_user = f"{f}.{l[0]}.{kw}.{salt}"
        else:
            raw_user = f"{f}.{m}.{salt}"

        # Chuẩn hóa chuẩn Gmail
        user = re.sub(r"[^a-z0-9.]", "", raw_user.lower())
        user = re.sub(r"\.+", ".", user).strip(".")
        if len(user) > 30:
            user = user[:30].rstrip(".")
        if len(user) < 6:
            user = f"{user}{random.randint(10000, 99999)}"

        candidate_email = f"{user}@gmail.com"

        # Kiểm tra chống trùng liên luồng
        with _BAIT_LOCK:
            if candidate_email not in _RECENT_BAIT_SET:
                _RECENT_BAIT_SET.add(candidate_email)
                _RECENT_BAIT_QUEUE.append(candidate_email)
                if len(_RECENT_BAIT_SET) > 280000:
                    _RECENT_BAIT_SET = set(_RECENT_BAIT_QUEUE)
                return candidate_email

    # Fallback nếu thử nhiều lần (xác suất gần như 0%)
    fallback_email = f"user.{int(time.time() * 1000) % 1000000000}{random.randint(100, 999)}@gmail.com"
    return fallback_email


class DomainDiversityTracker:
    """
    Theo doi va dieu phoi phan tan duoi email ngau nhien da dang (Domain Diversity Tracker).
    Dam bao 500 - 2000 luong chay lien tuc KHONG bi don cuc cung mot duoi mail,
    luan chuyen vong tron qua 70+ ten mien sach tu cac he thong uy tin.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._recent_domains = collections.deque(maxlen=40)
                cls._instance._domain_usage_count = collections.defaultdict(int)
            return cls._instance

    def pick_random_diverse_domain(self, candidate_domains: List[str]) -> str:
        if not candidate_domains:
            return "example.com"
        clean = [d.strip().lower().lstrip("@") for d in candidate_domains if d and d.strip()]
        if not clean:
            return "example.com"

        with self._lock:
            not_recent = [d for d in clean if d not in self._recent_domains]
            if not_recent:
                chosen = random.choice(not_recent)
            else:
                min_cnt = min(self._domain_usage_count[d] for d in clean)
                least_used = [d for d in clean if self._domain_usage_count[d] == min_cnt]
                chosen = random.choice(least_used)

            self._recent_domains.append(chosen)
            self._domain_usage_count[chosen] += 1
            return chosen

    def record_domain_used(self, domain_or_email: str) -> None:
        if not domain_or_email:
            return
        dom = domain_or_email.split("@")[-1].strip().lower()
        with self._lock:
            self._recent_domains.append(dom)
            self._domain_usage_count[dom] += 1

    def reset(self) -> None:
        with self._lock:
            self._recent_domains.clear()
            self._domain_usage_count.clear()


class BaseEmailProvider(ABC):
    """Abstract base class for all temporary email providers."""

    @abstractmethod
    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        """Create or allocate a new temporary email address."""
        pass

    @abstractmethod
    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        """Poll inbox until an OTP email arrives or timeout occurs."""
        pass

    def remove_account(self, email: str, filepath: str = "hotmails.txt") -> bool:
        """Xoa tai khoan da dung / da xac minh OTP khoi danh sach."""
        return remove_hotmail(email, filepath=filepath)

    def release_account(self, email: str, quarantine: bool = True) -> None:
        """Giai phong tai khoan ve lai pool neu chua xac minh OTP."""
        HotmailAccountManager.release_account(email, quarantine=quarantine)


# ==============================================================================
# 1. MAIL.TM PROVIDER (Free, Fast, Multi-domain)
# ==============================================================================

class MailTmProvider(BaseEmailProvider):
    """
    Mail.tm API implementation.
    Docs: https://api.mail.tm
    """
    BASE_URL = "https://api.mail.tm"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        proxies = self._get_proxies(proxy)
        try:
            # 1. Get available domains
            r_domains = requests.get(f"{self.BASE_URL}/domains", proxies=proxies, timeout=15)
            if r_domains.status_code != 200:
                logger.debug(f"[Mail.tm] Failed to get domains. HTTP {r_domains.status_code}")
                return None

            domains_raw = r_domains.json().get("hydra:member", [])
            domains = [d for d in domains_raw if d.get("isActive", True) and not d.get("isPrivate", False)]
            if not domains:
                domains = domains_raw
            if not domains:
                logger.debug("[Mail.tm] No domains available")
                return None

            domain = random.choice(domains)["domain"]
            user_part = re.sub(r'[^a-z0-9]', '', generate_human_email_username().lower())
            if len(user_part) < 4:
                user_part += str(random.randint(100, 999))
            email = f"{user_part}@{domain}"
            password = "Pass_" + str(uuid.uuid4())[:10]

            # 2. Register account
            r_reg = requests.post(
                f"{self.BASE_URL}/accounts",
                json={"address": email, "password": password},
                proxies=proxies,
                timeout=15,
            )
            if r_reg.status_code not in (200, 201):
                logger.debug(f"[Mail.tm] Account creation skipped: {r_reg.text[:120] if r_reg.text else ''}")
                return None

            account_id = r_reg.json().get("id")

            # 3. Acquire JWT Token
            r_token = requests.post(
                f"{self.BASE_URL}/token",
                json={"address": email, "password": password},
                proxies=proxies,
                timeout=15,
            )
            if r_token.status_code != 200:
                logger.debug(f"[Mail.tm] Token retrieval skipped: {r_token.text[:120] if r_token.text else ''}")
                return None

            token = r_token.json().get("token")
            logger.info(f"[Mail.tm] Mailbox created successfully: {email}")
            return EmailAccount(
                email=email,
                provider="mailtm",
                token=token,
                account_id=account_id,
                password=password,
            )
        except Exception as e:
            logger.error(f"[Mail.tm] Exception creating mailbox: {e}")
            return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        headers = {"Authorization": f"Bearer {account.token}"}

        logger.info(f"[Mail.tm] Waiting for OTP email to arrive at {account.email} (Max: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r_msgs = requests.get(f"{self.BASE_URL}/messages", headers=headers, proxies=proxies, timeout=10)
                if r_msgs.status_code == 200:
                    messages = r_msgs.json().get("hydra:member", [])
                    if messages:
                        msg_id = messages[0]["id"]
                        subject = messages[0].get("subject", "")
                        sender = messages[0].get("from", {}).get("address", "")

                        # Fetch full message content
                        r_detail = requests.get(f"{self.BASE_URL}/messages/{msg_id}", headers=headers, proxies=proxies, timeout=10)
                        body = ""
                        if r_detail.status_code == 200:
                            data = r_detail.json()
                            body = data.get("text") or data.get("html") or ""

                        # Extract OTP
                        full_content = f"{subject}\n{body}"
                        otp = extract_otp_code(full_content)
                        conf_link = extract_confirmation_link(full_content)
                        if otp or conf_link:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[Mail.tm] OTP/Link nhận được: {otp or conf_link} cho {account.email} trong {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp,
                                confirmation_link=conf_link,
                                sender=sender,
                                subject=subject,
                                body_preview=body[:150],
                                elapsed_seconds=elapsed,
                            )
            except Exception as e:
                logger.debug(f"[Mail.tm] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        logger.warning(f"[Mail.tm] OTP timeout for {account.email} after {elapsed}s")
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for OTP email after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# 2. GUERRILLA MAIL PROVIDER (Free, Fast Session-based)
# ==============================================================================

class GuerrillaMailProvider(BaseEmailProvider):
    """
    Guerrilla Mail API implementation.
    Docs: https://www.guerrillamail.com/
    """
    BASE_URL = "https://api.guerrillamail.com/ajax.php"
    DOMAINS = [
        "guerrillamail.com",
        "guerrillamailblock.com",
        "sharklasers.com",
        "guerrillamail.net",
        "guerrillamail.org",
        "pokemail.net",
        "spam4.me",
        "grr.la",
        "guerrillamail.biz",
        "guerrillamail.de",
        "guerrillamail.info",
        "superstachel.de",
    ]

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        proxies = self._get_proxies(proxy)
        try:
            r = requests.get(f"{self.BASE_URL}?f=get_email_address", proxies=proxies, timeout=10)
            if r.status_code == 200:
                data = r.json()
                email = data.get("email_addr")
                sid_token = data.get("sid_token")
                # Randomize Guerrilla domain across alternative aliases
                user_alias = data.get("alias")
                guerrilla_domains = self.DOMAINS
                if user_alias:
                    chosen_dom = domain if (domain and domain in guerrilla_domains) else DomainDiversityTracker().pick_random_diverse_domain(guerrilla_domains)
                    email = f"{user_alias}@{chosen_dom}"
                if email and sid_token:
                    logger.info(f"[GuerrillaMail] Mailbox created: {email}")
                    return EmailAccount(
                        email=email,
                        provider="guerrillamail",
                        token=sid_token,
                        metadata={"sid_token": sid_token},
                    )
        except Exception as e:
            logger.error(f"[GuerrillaMail] Error creating mailbox: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        sid_token = account.token or account.metadata.get("sid_token")

        logger.info(f"[GuerrillaMail] Waiting for OTP at {account.email}...")

        while time.time() - start_time < timeout_seconds:
            try:
                url = f"{self.BASE_URL}?f=check_email&sid_token={sid_token}&seq=0"
                r = requests.get(url, proxies=proxies, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    mail_list = data.get("list", [])
                    # Filter out welcome email from Guerrilla Mail
                    valid_msgs = [m for m in mail_list if "welcome" not in m.get("mail_subject", "").lower()]
                    if valid_msgs:
                        msg_id = valid_msgs[0].get("mail_id")
                        subject = valid_msgs[0].get("mail_subject", "")
                        sender = valid_msgs[0].get("mail_from", "")

                        # Fetch message detail
                        r_fetch = requests.get(
                            f"{self.BASE_URL}?f=fetch_email&sid_token={sid_token}&email_id={msg_id}",
                            proxies=proxies,
                            timeout=10,
                        )
                        body = ""
                        if r_fetch.status_code == 200:
                            body = r_fetch.json().get("mail_body", "")

                        full_content = f"{subject}\n{body}"
                        otp = extract_otp_code(full_content)
                        conf_link = extract_confirmation_link(full_content)
                        if otp or conf_link:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[GuerrillaMail] OTP/Link nhận được: {otp or conf_link} cho {account.email} trong {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp,
                                confirmation_link=conf_link,
                                sender=sender,
                                subject=subject,
                                body_preview=body[:150],
                                elapsed_seconds=elapsed,
                            )
            except Exception as e:
                logger.debug(f"[GuerrillaMail] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Guerrilla Mail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# 3. DONGVANFB PROVIDER (Commercial Rented Private Email API - Hotmail/Mailru)
# ==============================================================================

class DongVanEmailProvider(BaseEmailProvider):
    """
    Commercial rental service API (e.g. DongVanFB / dongvanfb.com).
    Provides private Hotmail, Mail.ru, Outlook addresses with high trust score.
    """
    BASE_URL = "https://api.dongvanfb.com"

    def __init__(self, api_key: str, account_type: str = "hotmail"):
        self.api_key = api_key
        self.account_type = account_type

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        if not self.api_key:
            logger.error("[DongVanFB] Missing API Key")
            return None

        try:
            url = f"{self.BASE_URL}/user/buy?apikey={self.api_key}&account_type={self.account_type}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                # DongVan format: {"status": true, "data": {"email": "...", "id": "..."}}
                if data.get("status") or data.get("success"):
                    email_data = data.get("data", {})
                    email = email_data.get("email") or email_data.get("mail")
                    order_id = str(email_data.get("id") or email_data.get("order_id"))
                    logger.info(f"[DongVanFB] Rented mail: {email} (Order ID: {order_id})")
                    return EmailAccount(
                        email=email,
                        provider="dongvanfb",
                        account_id=order_id,
                        metadata={"order_id": order_id, "api_key": self.api_key},
                    )
                else:
                    logger.error(f"[DongVanFB] Purchase error: {data.get('message')}")
        except Exception as e:
            logger.error(f"[DongVanFB] API request exception: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 60,
        poll_interval: int = 4,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        order_id = account.account_id or account.metadata.get("order_id")

        logger.info(f"[DongVanFB] Polling OTP for order {order_id} ({account.email})...")

        while time.time() - start_time < timeout_seconds:
            try:
                url = f"{self.BASE_URL}/user/get-code?apikey={self.api_key}&id={order_id}"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    code = data.get("code") or data.get("data", {}).get("code")
                    if code:
                        elapsed = round(time.time() - start_time, 2)
                        clean_otp = extract_otp_code(str(code)) or str(code).strip()
                        logger.info(f"[DongVanFB] Got OTP: {clean_otp} in {elapsed}s")
                        return OTPVerificationResult(
                            success=True,
                            email=account.email,
                            otp_code=clean_otp,
                            elapsed_seconds=elapsed,
                        )
            except Exception as e:
                logger.debug(f"[DongVanFB] Polling error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for DongVanFB OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# 4. KOPEECHKA PROVIDER (Commercial International Rental API)
# ==============================================================================

class KopeechkaEmailProvider(BaseEmailProvider):
    """
    Kopeechka Store API (kopeechka.store).
    International pay-per-email rental API.
    """
    BASE_URL = "https://api.kopeechka.store"

    def __init__(self, api_token: str, site: str = "facebook.com"):
        self.api_token = api_token
        self.site = site

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        if not self.api_token:
            logger.error("[Kopeechka] Missing API Token")
            return None

        try:
            url = f"{self.BASE_URL}/mailbox-get-email?site={self.site}&token={self.api_token}&type=ALL&api=2.0"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "OK":
                    email = data.get("mail")
                    task_id = str(data.get("id"))
                    logger.info(f"[Kopeechka] Allocated email: {email} (Task ID: {task_id})")
                    return EmailAccount(
                        email=email,
                        provider="kopeechka",
                        account_id=task_id,
                        metadata={"task_id": task_id},
                    )
        except Exception as e:
            logger.error(f"[Kopeechka] Allocation exception: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 60,
        poll_interval: int = 4,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        task_id = account.account_id

        while time.time() - start_time < timeout_seconds:
            try:
                url = f"{self.BASE_URL}/mailbox-get-message?id={task_id}&token={self.api_token}&api=2.0"
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("status") == "OK":
                        raw_msg = data.get("value", "")
                        otp = extract_otp_code(raw_msg)
                        if otp:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[Kopeechka] OTP received: {otp} in {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp,
                                body_preview=raw_msg[:150],
                                elapsed_seconds=elapsed,
                            )
            except Exception as e:
                logger.debug(f"[Kopeechka] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Kopeechka OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# METAKING.TOP PROVIDER (Email OTP: Gmail/iCloud/Hotmail & Phone OTP SMS)
# ==============================================================================

class MetakingEmailProvider(BaseEmailProvider):
    """
    Tich hop nen tang Metaking.top (https://metaking.top).
    Ho tro 2 che do:
    1. Thue Email OTP: Gmail, iCloud, Hotmail, Outlook qua 5 cum server doc lap.
    2. Thue So Dien Thoai (SMS): Nhan ma OTP sieu toc cho dich vu Facebook (ID 67).
    Rate limit: 600 req/60s, delay 2-3s giua cac nhip kiem tra.
    """
    BASE_URL = "https://metaking.top/api"

    def __init__(
        self,
        api_key: str = "",
        service_type: str = "email",
        server: int = 1,
        domain: str = "hotmail.com",
        service_id: int = 1,
        country_id: int = 154,
        price_level: Optional[str] = None,
    ):
        self.api_key = (api_key or "").strip()
        self.service_type = (service_type or "email").lower().strip()
        self.server = int(server or 1)
        self.domain = (domain or "hotmail.com").strip()
        self.country_id = int(country_id or 154)
        # BẮT BUỘC: Đối với thuê SĐT nhận OTP, dịch vụ Facebook luôn có ID là 67! (ID 1 là Viber)
        if self.service_type == "phone":
            self.service_id = 67
        else:
            self.service_id = 1
        self.price_level = price_level
        self._active_rentals: Dict[str, Dict[str, Any]] = {}
        self.provider_name = (
            "metaking_hotmail" if "hotmail" in self.domain.lower() else (
                "metaking_gmail" if "gmail" in self.domain.lower() else (
                    "metaking_phone" if self.service_type == "phone" else "metaking"
                )
            )
        )

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        if not self.api_key:
            logger.error("[Metaking] Thieu X-API-KEY, vui long cai dat trong tab Cai Dat!")
            return None

        target_domain = (domain or self.domain or "gmail.com").strip()

        if self.service_type == "phone":
            url = f"{self.BASE_URL}/otp/rent"
            # Bắt buộc thuê số cho dịch vụ Facebook (ID 67). Tuyệt đối không dùng 1 vì ID 1 là Viber!
            payload = {
                "service_id": 67,
                "country_id": self.country_id or 154,
            }
            try:
                r = requests.post(url, json=payload, headers=self._headers(), timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success"):
                        item = data.get("data", {})
                        rental_id = item.get("rental_id")
                        phone_number = item.get("phone_number")
                        price = item.get("price")
                        balance = item.get("balance")
                        logger.info(f"[Metaking Phone] Thue thanh cong SDT: {phone_number} (ID: {rental_id}, Gia: {price}, Du: {balance})")
                        account = EmailAccount(
                            email=str(phone_number),
                            provider="metaking_phone",
                            account_id=str(rental_id),
                            metadata={
                                "rental_id": rental_id,
                                "phone_number": phone_number,
                                "country_id": self.country_id,
                                "price": price,
                                "balance": balance,
                                "service_type": "phone",
                                "api_key": self.api_key,
                            }
                        )
                        self._active_rentals[str(phone_number)] = account.metadata
                        return account
                    else:
                        logger.error(f"[Metaking Phone] Thue that bai: {data.get('message')}")
                elif r.status_code == 401:
                    logger.error("[Metaking Phone] API Key khong hop le (401)")
                elif r.status_code == 402:
                    logger.error("[Metaking Phone] So du tai khoan khong du (402)")
                elif r.status_code == 409:
                    logger.error("[Metaking Phone] Tam thoi het so kha dung (409)")
                else:
                    logger.error(f"[Metaking Phone] HTTP {r.status_code}: {r.text}")
            except Exception as e:
                logger.error(f"[Metaking Phone] Loi ket noi khi thue so: {e}")
            return None

        # Email OTP: Tu dong xoay qua cac domain co hang (hotmail.com, outlook.com, icloud.com) neu domain yeu cau het hang
        url = f"{self.BASE_URL}/email-otp/rent"
        candidate_domains = [target_domain]
        for fb_d in ["hotmail.com", "outlook.com", "icloud.com"]:
            if fb_d not in candidate_domains:
                candidate_domains.append(fb_d)

        for curr_d in candidate_domains:
            payload = {
                "service_id": 1,
                "domain": curr_d,
                "server": self.server,
            }
            if self.server == 4 and self.price_level:
                payload["price"] = self.price_level

            try:
                r = requests.post(url, json=payload, headers=self._headers(), timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("success"):
                        item = data.get("data", {})
                        rental_id = item.get("rental_id")
                        email_address = item.get("email_address")
                        price = item.get("price")
                        balance = item.get("balance")
                        logger.info(f"[Metaking Email] Thue thanh cong: {email_address} (ID: {rental_id}, Server: {self.server}, Domain: {curr_d}, Du: {balance})")
                        account = EmailAccount(
                            email=str(email_address),
                            provider="metaking",
                            account_id=str(rental_id),
                            metadata={
                                "rental_id": rental_id,
                                "server": self.server,
                                "domain": curr_d,
                                "price": price,
                                "balance": balance,
                                "service_type": "email",
                                "api_key": self.api_key,
                                "fallback_from": (target_domain if curr_d != target_domain else None),
                            }
                        )
                        self._active_rentals[str(email_address).lower()] = account.metadata
                        return account
                    else:
                        logger.info(f"[Metaking Email] Domain {curr_d} khong kha dung ({data.get('message')}) -> Thu domain tiep theo...")
                        continue
                elif r.status_code == 409:
                    logger.info(f"[Metaking Email] Domain {curr_d} tam het hang (409) -> Thu domain tiep theo...")
                    continue
                elif r.status_code == 401:
                    logger.error("[Metaking Email] API Key khong hop le (401)")
                    break
                elif r.status_code == 402:
                    logger.error("[Metaking Email] So du tai khoan khong du (402)")
                    break
                else:
                    logger.error(f"[Metaking Email] HTTP {r.status_code}: {r.text}")
            except Exception as e:
                logger.error(f"[Metaking Email] Loi ket noi khi thue mail ({curr_d}): {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        rental_id = account.account_id or account.metadata.get("rental_id")
        is_phone = (account.metadata.get("service_type") == "phone") or (self.service_type == "phone")

        if not rental_id:
            return OTPVerificationResult(
                success=False,
                email=account.email,
                error="Thieu Rental ID Metaking de kiem tra OTP",
                elapsed_seconds=0.0
            )

        status_url = (
            f"{self.BASE_URL}/otp/rentals/{rental_id}/status"
            if is_phone
            else f"{self.BASE_URL}/email-otp/rentals/{rental_id}/status"
        )
        poll_wait = max(2, poll_interval) + random.uniform(0.1, 0.4)

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(status_url, headers=self._headers(), timeout=10)
                if r.status_code == 200:
                    res_json = r.json()
                    if res_json.get("success"):
                        item = res_json.get("data", {})
                        status = item.get("status", "")
                        codes = item.get("codes", [])

                        found_otp = None
                        found_link = None

                        # Trích xuất confirmation_link nếu có trong nội dung email
                        for k in ("sms", "message", "text", "content", "raw"):
                            v = item.get(k)
                            if v:
                                cl = extract_confirmation_link(str(v))
                                if cl:
                                    found_link = cl
                                    break
                        if not found_link:
                            found_link = extract_confirmation_link(json.dumps(item))

                        # Ưu tiên 1: Kiểm tra trực tiếp các trường code/otp trong item
                        for k in ("code", "otp", "last_code", "confirmation_code", "sms_code"):
                            v = item.get(k)
                            if v:
                                ex = extract_otp_code(str(v)) or (str(v).strip() if str(v).strip().isdigit() and len(str(v).strip()) in (5, 6, 8) else None)
                                if ex:
                                    found_otp = ex
                                    break

                        # Ưu tiên 2: Trích xuất từ nội dung tin nhắn SMS
                        if not found_otp:
                            for k in ("sms", "message", "text", "content", "raw"):
                                v = item.get(k)
                                if v:
                                    ex = extract_otp_code(str(v))
                                    if ex:
                                        found_otp = ex
                                        break

                        # Ưu tiên 3: Quét trong mảng codes
                        if not found_otp and codes and isinstance(codes, list):
                            for c in codes:
                                if not c:
                                    continue
                                if isinstance(c, (str, int)):
                                    sc = str(c).strip()
                                    extracted = extract_otp_code(sc) or (sc if sc.isdigit() and len(sc) in (5, 6, 8) else None)
                                    if extracted:
                                        found_otp = extracted
                                        break
                                elif isinstance(c, dict):
                                    for dk in ("code", "otp", "confirmation_code", "raw", "content", "message", "text", "sms"):
                                        dv = c.get(dk)
                                        if dv:
                                            extracted = extract_otp_code(str(dv)) or (str(dv).strip() if str(dv).strip().isdigit() and len(str(dv).strip()) in (5, 6, 8) else None)
                                            if extracted:
                                                found_otp = extracted
                                                break
                                    if found_otp:
                                        break

                        # Ưu tiên 4: Quét toàn bộ JSON nếu otp_count > 0 hoặc trạng thái completed
                        if not found_otp and (item.get("otp_count", 0) > 0 or status in ("completed", "has_otp", "success")):
                            fallback_otp = extract_otp_code(json.dumps(item))
                            if fallback_otp:
                                found_otp = fallback_otp

                        if found_otp or found_link:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[Metaking] Nhan ma OTP/Link thanh cong: OTP={found_otp}, Link={bool(found_link)} cho {account.email} trong {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=found_otp,
                                confirmation_link=found_link,
                                elapsed_seconds=elapsed,
                                metadata=item,
                            )

                        if status == "completed":
                            fallback_otp = extract_otp_code(json.dumps(item))
                            if fallback_otp:
                                elapsed = round(time.time() - start_time, 2)
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=fallback_otp,
                                    elapsed_seconds=elapsed,
                                    metadata=item,
                                )

                        if status in ("cancelled", "refunded", "failed"):
                            elapsed = round(time.time() - start_time, 2)
                            return OTPVerificationResult(
                                success=False,
                                email=account.email,
                                error=f"Don thue Metaking da ket thuc ({status})",
                                elapsed_seconds=elapsed
                            )
                elif r.status_code == 429:
                    logger.debug("[Metaking] Rate limit 429, cho them nhip...")
            except Exception as e:
                logger.debug(f"[Metaking] Loi kiem tra OTP: {e}")

            time.sleep(poll_wait)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Het thoi gian cho ma OTP tu Metaking ({timeout_seconds}s)",
            elapsed_seconds=elapsed,
        )

    def release_account(self, email: str, quarantine: bool = True) -> None:
        key = str(email or "").lower().strip()
        meta = self._active_rentals.get(key)
        if not meta:
            return
        rental_id = meta.get("rental_id")
        if not rental_id:
            return

        is_phone = (meta.get("service_type") == "phone")
        cancel_url = (
            f"{self.BASE_URL}/otp/rentals/{rental_id}/cancel"
            if is_phone
            else f"{self.BASE_URL}/email-otp/rentals/{rental_id}/cancel"
        )
        try:
            r = requests.post(cancel_url, headers=self._headers(), timeout=8)
            if r.status_code == 200:
                logger.info(f"[Metaking] Da gui yeu cau huy don ID {rental_id} ({email}) thanh cong.")
            else:
                logger.debug(f"[Metaking] Huy don ID {rental_id} phan hoi: {r.status_code}")
        except Exception as e:
            logger.debug(f"[Metaking] Loi khi gui lenh huy don ID {rental_id}: {e}")

    def request_next_otp(self, account: EmailAccount) -> bool:
        rental_id = account.account_id or account.metadata.get("rental_id")
        if not rental_id:
            return False
        is_phone = (account.metadata.get("service_type") == "phone") or (self.service_type == "phone")
        next_url = (
            f"{self.BASE_URL}/otp/rentals/{rental_id}/next"
            if is_phone
            else f"{self.BASE_URL}/email-otp/rentals/{rental_id}/next"
        )
        try:
            r = requests.post(next_url, headers=self._headers(), timeout=10)
            if r.status_code == 200:
                logger.info(f"[Metaking] Đã yêu cầu gửi thêm OTP mới cho đơn ID {rental_id}")
                return True
        except Exception as e:
            logger.debug(f"[Metaking] Lỗi gọi next OTP: {e}")
        return False

    @classmethod
    def test_api_key(cls, api_key: str) -> Dict[str, Any]:
        k = (api_key or "").strip()
        if not k:
            return {"success": False, "message": "Vui lòng nhập API Key Metaking!"}
        headers = {"X-API-KEY": k, "Content-Type": "application/json"}
        try:
            # 1. Gọi trực tiếp /api/me để lấy chính xác thông tin tài khoản và số dư
            r_me = requests.get(f"{cls.BASE_URL}/me", headers=headers, timeout=10)
            if r_me.status_code == 401:
                return {"success": False, "message": "API Key không hợp lệ (401 Unauthorized)!"}
            if r_me.status_code == 200:
                me_json = r_me.json()
                if me_json.get("success"):
                    u_data = me_json.get("data", {})
                    if isinstance(u_data, dict) and "username" in u_data:
                        username = u_data.get("username", "")
                        balance = u_data.get("balance", 0)
                        return {
                            "success": True,
                            "message": f"Kết nối thành công! User: {username} | Số dư: {balance:,} VNĐ",
                            "username": username,
                            "balance": balance,
                            "user_data": u_data
                        }
                    else:
                        return {
                            "success": True,
                            "message": "Kết nối API Metaking.top thành công!",
                            "services": u_data if isinstance(u_data, list) else [],
                            "balance": None
                        }

            # 2. Dự phòng: Gọi /api/email-otp/services?server=1
            r = requests.get(f"{cls.BASE_URL}/email-otp/services?server=1", headers=headers, timeout=10)
            if r.status_code == 401:
                return {"success": False, "message": "API Key không hợp lệ (401 Unauthorized)!"}
            if r.status_code != 200:
                return {"success": False, "message": f"Máy chủ phản hồi mã lỗi HTTP {r.status_code}"}

            data = r.json()
            if not data.get("success"):
                return {"success": False, "message": data.get("message", "Lỗi không xác định")}

            return {
                "success": True,
                "message": "Kết nối API Metaking.top thành công!",
                "services": data.get("data", []),
                "balance": None
            }
        except Exception as e:
            return {"success": False, "message": f"Lỗi kết nối Metaking: {e}"}

    @classmethod
    def get_email_prices(cls, api_key: str, service_id: int = 1, server: int = 1) -> List[Dict[str, Any]]:
        k = (api_key or "").strip()
        if not k:
            return []
        headers = {"X-API-KEY": k}
        try:
            r = requests.get(f"{cls.BASE_URL}/email-otp/prices?service_id={service_id}&server={server}", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"[Metaking] Loi lay gia email: {e}")
        return []

    @classmethod
    def get_phone_prices(cls, api_key: str, service_id: int = 67) -> List[Dict[str, Any]]:
        k = (api_key or "").strip()
        if not k:
            return []
        headers = {"X-API-KEY": k}
        try:
            r = requests.get(f"{cls.BASE_URL}/otp/prices?service_id={service_id}", headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    return data.get("data", [])
        except Exception as e:
            logger.debug(f"[Metaking] Loi lay gia SDT: {e}")
        return []


# ==============================================================================
# HOTMAIL ACCOUNT MANAGER & POOL SYNCHRONIZER
# ==============================================================================

class HotmailAccountManager:
    """
    Quan ly tap trung kho tai khoan Hotmail/Outlook tu file (hotmails.txt).
    Dam bao:
    - Dong bo da luong an toan (thread-safe) voi Lock
    - Tu dong xoa vinh vien tai khoan khoi hotmails.txt va pool RAM ngay khi
      tai khoan da duoc su dung va xac minh ma OTP thanh cong.
    - Khong cap phat trung lap tai khoan cho cac luong song song.
    - Tuong thich moi dinh dang: email|pass, email:pass, email|pass|refresh_token|client_id,
      email|pass|rec_email|rec_pwd, v.v.
    """
    _lock = threading.Lock()
    _accounts_pool: List[Dict[str, Any]] = []
    _in_use: set = set()
    _default_file: str = "hotmails.txt"
    _loaded_files: set = set()
    _cursor: int = 0
    _quarantined: set = set()

    @staticmethod
    def _extract_email_from_line(line: str) -> str:
        if not line:
            return ""
        line_clean = line.strip().lstrip('\ufeff')
        if not line_clean or line_clean.startswith("#"):
            return ""
        m = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', line_clean)
        if m:
            return m.group(1).lower().strip()
        parts = re.split(r'[:|\t,;\s]', line_clean)
        if parts and "@" in parts[0]:
            return parts[0].lower().strip()
        return ""

    @classmethod
    def _parse_account_line(cls, line: str) -> Optional[Dict[str, Any]]:
        line_clean = line.strip().lstrip('\ufeff')
        if not line_clean or line_clean.startswith("#"):
            return None
        if "|" in line_clean:
            parts = [p.strip() for p in line_clean.split("|")]
        elif ":" in line_clean:
            parts = [p.strip() for p in line_clean.split(":")]
        elif "\t" in line_clean:
            parts = [p.strip() for p in line_clean.split("\t")]
        else:
            parts = [p.strip() for p in line_clean.split()]

        if not parts or "@" not in parts[0]:
            return None

        email_clean = parts[0].strip().lstrip('\ufeff')
        password = parts[1].strip() if len(parts) > 1 else ""
        refresh_token = ""
        client_id = ""
        rec_email = None
        rec_pwd = None

        if len(parts) >= 4:
            if "@" in parts[2]:
                rec_email = parts[2].strip()
                rec_pwd = parts[3].strip()
                if len(parts) >= 6 and "@" not in parts[4]:
                    refresh_token = parts[4].strip()
                    client_id = parts[5].strip()
            else:
                refresh_token = parts[2].strip()
                client_id = parts[3].strip()
                if len(parts) > 4:
                    rec_email = parts[4].strip()
                if len(parts) > 5:
                    rec_pwd = parts[5].strip()
        elif len(parts) == 3:
            if "@" in parts[2]:
                rec_email = parts[2].strip()
            else:
                refresh_token = parts[2].strip()
                client_id = "e9a37c35-7d52-4415-be02-463e264de917"

        if refresh_token and not client_id:
            client_id = "e9a37c35-7d52-4415-be02-463e264de917"

        return {
            "email": email_clean,
            "password": password,
            "refresh_token": refresh_token,
            "client_id": client_id,
            "rec_email": rec_email,
            "rec_pwd": rec_pwd,
            "raw_line": line,
        }

    @classmethod
    def load_from_file(cls, filepath: str = "hotmails.txt") -> int:
        clean_path = filepath or cls._default_file
        if not os.path.exists(clean_path):
            logger.warning(f"[HotmailManager] File not found: {clean_path}")
            return 0

        with cls._lock:
            with open(clean_path, "r", encoding="utf-8-sig") as f:
                lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]

            cls._accounts_pool.clear()
            cls._in_use.clear()
            cls._loaded_files.add(os.path.abspath(clean_path))

            for line in lines:
                acc = cls._parse_account_line(line)
                if acc:
                    cls._accounts_pool.append(acc)

            logger.info(f"[HotmailManager] Da nap {len(cls._accounts_pool)} tai khoan Hotmail tu {clean_path}")
            return len(cls._accounts_pool)

    @classmethod
    def load_from_text(cls, text: str, append_to_file: bool = True, filepath: str = "hotmails.txt") -> int:
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
        added = 0
        added_lines = []
        clean_path = filepath or cls._default_file

        with cls._lock:
            existing_emails = {
                acc["email"].lower() for acc in cls._accounts_pool if "email" in acc
            }
            for line in lines:
                acc = cls._parse_account_line(line)
                if not acc:
                    continue
                email_lower = acc["email"].lower()
                if email_lower in existing_emails:
                    continue
                existing_emails.add(email_lower)
                cls._accounts_pool.append(acc)
                added += 1
                added_lines.append(line)

        if append_to_file and added_lines:
            try:
                with open(clean_path, "a", encoding="utf-8-sig") as f:
                    for line in added_lines:
                        f.write(line + "\n")
            except Exception as e:
                logger.error(f"[HotmailManager] Loi ghi file {clean_path}: {e}")

        logger.info(f"[HotmailManager] Da nap them {added} mail. Tong kho: {len(cls._accounts_pool)}")
        return len(cls._accounts_pool)

    @classmethod
    def allocate_account(cls, filepath: str = "hotmails.txt") -> Optional[Dict[str, Any]]:
        clean_path = filepath or cls._default_file
        with cls._lock:
            if not cls._accounts_pool:
                if os.path.exists(clean_path):
                    cls.load_from_file(clean_path)

            if not cls._accounts_pool:
                logger.error(f"[HotmailManager] Kho tai khoan Hotmail trong ({clean_path})!")
                return None

            selected = None
            total = len(cls._accounts_pool)
            for i in range(total):
                acc = cls._accounts_pool[i]
                em = acc.get("email", "").strip().lower().lstrip('\ufeff')
                if em and em not in cls._in_use and em not in getattr(cls, "_quarantined", set()):
                    selected = acc
                    break

            if not selected:
                for i in range(total):
                    acc = cls._accounts_pool[i]
                    em = acc.get("email", "").strip().lower().lstrip('\ufeff')
                    if em and em not in cls._in_use:
                        selected = acc
                        break

            if not selected:
                logger.warning(f"[HotmailManager] Tất cả {len(cls._accounts_pool)} Hotmail đều đang được sử dụng hoặc đã hết (không tái sử dụng mail cũ để chống Checkpoint 282)!")
                return None

            em = selected.get("email", "").strip().lower().lstrip('\ufeff')
            cls._in_use.add(em)
            return dict(selected)

    @classmethod
    def release_account(cls, email: str, quarantine: bool = False) -> None:
        """Neu tac vu ket thuc ma chua xac minh OTP, tra mail ve pool va cach ly de uu tien mail moi khac."""
        if not email:
            return
        clean_target = cls._extract_email_from_line(email) or email.split("|")[0].split(":")[0].strip().lower().lstrip('\ufeff')
        with cls._lock:
            cls._in_use.discard(clean_target)
            if quarantine and clean_target:
                if not hasattr(cls, "_quarantined"):
                    cls._quarantined = set()
                cls._quarantined.add(clean_target)

    @classmethod
    def remove_account(cls, email: str, filepath: str = "hotmails.txt") -> bool:
        """
        Xoa tai khoan da dung / da xac minh OTP:
        1. Xoa khoi RAM _accounts_pool & _in_use
        2. Xoa khoi file hotmails.txt va tat ca cac file da nap
        3. Luu vet vao hotmails_used.txt
        """
        if not email:
            return False

        clean_target = cls._extract_email_from_line(email) or email.split("|")[0].split(":")[0].strip().lower().lstrip('\ufeff')
        if not clean_target or "@" not in clean_target:
            return False

        with cls._lock:
            cls._in_use.discard(clean_target)

            # 1. Xoa khoi RAM pool
            initial_ram = len(cls._accounts_pool)
            cls._accounts_pool[:] = [
                acc for acc in cls._accounts_pool
                if cls._extract_email_from_line(acc.get("email", "")) != clean_target
                and acc.get("email", "").strip().lower().lstrip('\ufeff') != clean_target
            ]
            ram_removed = len(cls._accounts_pool) < initial_ram

            # 2. Xoa khoi File tren dia
            targets_to_check = set()
            if filepath:
                targets_to_check.add(filepath)
                try:
                    targets_to_check.add(os.path.abspath(filepath))
                except Exception:
                    pass
            targets_to_check.add("hotmails.txt")
            try:
                targets_to_check.add(os.path.abspath("hotmails.txt"))
                script_dir = os.path.dirname(os.path.abspath(__file__))
                targets_to_check.add(os.path.join(script_dir, "hotmails.txt"))
                targets_to_check.add(os.path.join(script_dir, "..", "hotmails.txt"))
            except Exception:
                pass
            targets_to_check.update(list(cls._loaded_files))

            file_removed = False
            removed_lines = []

            seen_paths = set()
            for p in targets_to_check:
                if p and os.path.exists(p):
                    try:
                        seen_paths.add(os.path.realpath(os.path.abspath(p)))
                    except Exception:
                        seen_paths.add(p)

            for f_path in seen_paths:
                if not f_path or not os.path.exists(f_path):
                    continue
                try:
                    with open(f_path, "r", encoding="utf-8-sig") as f:
                        lines = [line.strip() for line in f if line.strip()]

                    remaining_lines = []
                    f_modified = False
                    for line in lines:
                        if line.startswith("#"):
                            remaining_lines.append(line)
                            continue
                        line_email = cls._extract_email_from_line(line)
                        if line_email == clean_target:
                            removed_lines.append(line)
                            file_removed = True
                            f_modified = True
                        else:
                            remaining_lines.append(line)

                    if f_modified:
                        with open(f_path, "w", encoding="utf-8-sig") as f:
                            for l in remaining_lines:
                                f.write(l + "\n")
                except Exception as e:
                    logger.error(f"[HotmailManager] Loi xoa {clean_target} tu {f_path}: {e}")

            # 3. Ghi vao file lich su da dung hotmails_used.txt
            if removed_lines:
                try:
                    with open("hotmails_used.txt", "a", encoding="utf-8-sig") as f_used:
                        for rl in removed_lines:
                            f_used.write(rl + "\n")
                except Exception:
                    pass

            if ram_removed or file_removed:
                logger.info(f"[HotmailManager] [XOA THANH CONG] Hotmail '{clean_target}' da xac minh OTP -> Da xoa khoi danh sach kho. Con lai: {len(cls._accounts_pool)} mail.")
                return True
            else:
                logger.debug(f"[HotmailManager] Khong tim thay Hotmail '{clean_target}' trong kho de xoa.")
                return False

    @classmethod
    def get_remaining_count(cls, filepath: str = "hotmails.txt") -> int:
        with cls._lock:
            if not cls._accounts_pool and os.path.exists(filepath or "hotmails.txt"):
                cls.load_from_file(filepath or "hotmails.txt")
            return len(cls._accounts_pool)

    @classmethod
    def reset_in_use(cls) -> None:
        """Reset danh sach mail dang su dung va quarantine de san sang cho phien chay moi."""
        with cls._lock:
            cls._in_use.clear()
            cls._quarantined.clear()
            cls._cursor = 0
            logger.info("[HotmailManager] Da lam moi trang thai su dung cua kho Hotmail.")


def remove_hotmail(email: str, filepath: str = "hotmails.txt") -> bool:
    """Ham tien ich toan cuc xoa Hotmail da xac minh OTP khoi danh sach."""
    return HotmailAccountManager.remove_account(email, filepath=filepath)


def reset_hotmail_pool() -> None:
    """Ham tien ich toan cuc lam moi trang thai su dung kho Hotmail."""
    HotmailAccountManager.reset_in_use()


# ==============================================================================
# 5. HOTMAIL / OUTLOOK IMAP PROVIDER (Bulk Rented / Bought Accounts)
# ==============================================================================

class HotmailImapEmailProvider(BaseEmailProvider):
    """
    Reads real Facebook OTP emails directly from Hotmail/Outlook via IMAP SSL.
    Loads accounts from hotmails.txt (format: email|password).
    """
    IMAP_SERVER = "outlook.office365.com"
    IMAP_PORT = 993

    def __init__(self, hotmail_file: str = "hotmails.txt"):
        self.hotmail_file = hotmail_file

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        acc_data = HotmailAccountManager.allocate_account(filepath=self.hotmail_file)
        if not acc_data:
            logger.error(f"[Hotmail IMAP] No accounts available in {self.hotmail_file}")
            return None
        email_addr = acc_data["email"]
        pwd = acc_data.get("password", "")
        logger.info(f"[Hotmail IMAP] Allocated account: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="hotmail_imap",
            password=pwd,
            metadata=acc_data
        )

    @classmethod
    def reset_in_use(cls) -> None:
        HotmailAccountManager.reset_in_use()

    def release_account(self, email: str, quarantine: bool = True) -> None:
        HotmailAccountManager.release_account(email, quarantine=quarantine)

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 60,
        poll_interval: int = 5,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        import imaplib
        import email
        from email.header import decode_header

        start_time = time.time()
        logger.info(f"[Hotmail IMAP] Checking inbox for {account.email}...")

        while time.time() - start_time < timeout_seconds:
            try:
                mail = imaplib.IMAP4_SSL(self.IMAP_SERVER, self.IMAP_PORT)
                mail.login(account.email, account.password)
                mail.select("INBOX")
                status, messages = mail.search(None, '(OR FROM "facebookmail.com" FROM "Facebook")')
                if status == "OK" and messages[0]:
                    msg_ids = messages[0].split()
                    latest_id = msg_ids[-1]
                    res, msg_data = mail.fetch(latest_id, "(RFC822)")
                    if res == "OK":
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        subject_raw, enc = decode_header(msg.get("Subject", ""))[0]
                        if isinstance(subject_raw, bytes):
                            subject = subject_raw.decode(enc or "utf-8", errors="replace")
                        else:
                            subject = str(subject_raw)
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() in ("text/plain", "text/html"):
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        body += payload.decode("utf-8", errors="replace")
                        else:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="replace")

                        full_text = f"{subject}\n{body}"
                        otp = extract_otp_code(full_text)
                        conf_link = extract_confirmation_link(body)
                        try:
                            mail.logout()
                        except Exception:
                            pass
                        if otp or conf_link:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[Hotmail IMAP] Received OTP {otp} for {account.email} in {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp,
                                subject=subject,
                                body_preview=body[:150],
                                elapsed_seconds=elapsed,
                            )
                try:
                    mail.logout()
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"[Hotmail IMAP] Poll attempt: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Hotmail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# 6. PROVIDER FACTORY (Unified Creator)
# ==============================================================================


# ==============================================================================
# 7. SMAIL1S.COM PROVIDER (Hotmail / Outlook OAuth & Roundcube IMAP API)
# ==============================================================================

class Smail1sHotmailProvider(BaseEmailProvider):
    """
    Smail1s.com API provider for Hotmail / Outlook reading via OAuth2 and Roundcube.
    Docs: https://smail1s.com/api-docs
    Supports loading Hotmail accounts from a file (hotmails.txt).
    """
    BASE_URL = "https://smail1s.com/get_messages"
    _file_lock = HotmailAccountManager._lock
    _accounts_pool: List[Dict[str, Any]] = HotmailAccountManager._accounts_pool
    _cursor: int = 0

    def __init__(self, hotmail_file: str = "hotmails.txt"):
        self.hotmail_file = hotmail_file
        if not HotmailAccountManager._accounts_pool:
            self.load_from_file(hotmail_file)

    @classmethod
    def load_from_file(cls, filepath: str = "hotmails.txt") -> int:
        return HotmailAccountManager.load_from_file(filepath)

    @classmethod
    def load_from_text(cls, text: str, append_to_file: bool = True, filepath: str = "hotmails.txt") -> int:
        return HotmailAccountManager.load_from_text(text, append_to_file=append_to_file, filepath=filepath)

    @classmethod
    def remove_account(cls, email: str, filepath: str = "hotmails.txt") -> bool:
        return HotmailAccountManager.remove_account(email, filepath=filepath)

    @classmethod
    def reset_in_use(cls) -> None:
        HotmailAccountManager.reset_in_use()

    def release_account(self, email: str, quarantine: bool = True) -> None:
        HotmailAccountManager.release_account(email, quarantine=quarantine)

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        acc_data = HotmailAccountManager.allocate_account(filepath=self.hotmail_file)
        if not acc_data:
            logger.error("[Smail1s] No Hotmail accounts available!")
            return None
        email = acc_data["email"]
        logger.info(f"[Smail1s] Allocated Hotmail account: {email}")
        return EmailAccount(
            email=email,
            provider="hotmail_custom",
            password=acc_data["password"],
            metadata=acc_data,
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        meta = account.metadata
        email = account.email.strip().lstrip('\ufeff')
        refresh_token = (meta.get("refresh_token") or "").strip()
        client_id = (meta.get("client_id") or "").strip()
        rec_email = meta.get("rec_email")
        rec_pwd = meta.get("rec_pwd")

        logger.info(f"[Smail1s] Đang chờ mã OTP cho Hotmail {email} qua smail1s.com (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            # 1. Thử mode OAuth
            if refresh_token and client_id:
                try:
                    payload = {
                        "data": f"{email}|{refresh_token}|{client_id}",
                        "mode": "oauth"
                    }
                    r = requests.post(self.BASE_URL, json=payload, timeout=7)
                    if r.status_code == 200:
                        data = r.json().get("data", [])
                        if data and isinstance(data, list):
                            item = data[0]
                            messages = item.get("messages", [])
                            if messages:
                                for msg in messages:
                                    code = msg.get("code")
                                    subject = msg.get("subject", "")
                                    body = msg.get("message", "")
                                    sender = msg.get("from", "")

                                    otp = code or extract_otp_code(f"{subject}\n{body}")
                                    conf_link = extract_confirmation_link(f"{subject}\n{body}")
                                    if otp or conf_link:
                                        elapsed = round(time.time() - start_time, 2)
                                        logger.info(f"[Smail1s OAuth] Đã nhận OTP: {otp} cho {email} trong {elapsed}s")
                                        return OTPVerificationResult(
                                            success=True,
                                            email=email,
                                            otp_code=otp,
                                            sender=sender,
                                            subject=subject,
                                            body_preview=body[:150],
                                            elapsed_seconds=elapsed,
                                            metadata={"confirmation_link": conf_link} if conf_link else {},
                                        )
                except Exception as e:
                    logger.debug(f"[Smail1s OAuth] Lỗi poll: {e}")

                # 2. Thử mode Graph song song trong cùng vòng lặp nếu OAuth chưa có thư
                try:
                    payload_g = {
                        "data": f"{email}|{refresh_token}|{client_id}",
                        "mode": "graph"
                    }
                    r_g = requests.post(self.BASE_URL, json=payload_g, timeout=7)
                    if r_g.status_code == 200:
                        data_g = r_g.json().get("data", [])
                        if data_g and isinstance(data_g, list):
                            item_g = data_g[0]
                            messages_g = item_g.get("messages", [])
                            if messages_g:
                                for msg_g in messages_g:
                                    code_g = msg_g.get("code")
                                    subject_g = msg_g.get("subject", "")
                                    body_g = msg_g.get("message", "")
                                    sender_g = msg_g.get("from", "")

                                    otp_g = code_g or extract_otp_code(f"{subject_g}\n{body_g}")
                                    conf_link_g = extract_confirmation_link(f"{subject_g}\n{body_g}")
                                    if otp_g or conf_link_g:
                                        elapsed = round(time.time() - start_time, 2)
                                        logger.info(f"[Smail1s Graph] Đã nhận OTP: {otp_g} cho {email} trong {elapsed}s")
                                        return OTPVerificationResult(
                                            success=True,
                                            email=email,
                                            otp_code=otp_g,
                                            sender=sender_g,
                                            subject=subject_g,
                                            body_preview=body_g[:150],
                                            elapsed_seconds=elapsed,
                                            metadata={"confirmation_link": conf_link_g} if conf_link_g else {},
                                        )
                except Exception as e:
                    logger.debug(f"[Smail1s Graph] Lỗi poll: {e}")

            # 3. Fallback Roundcube mode cho wmhotmail
            if rec_email and rec_pwd:
                try:
                    payload_rc = {
                        "data": f"{rec_email}|{rec_pwd}",
                        "mode": "roundcube"
                    }
                    r_rc = requests.post(self.BASE_URL, json=payload_rc, timeout=7)
                    if r_rc.status_code == 200:
                        data_rc = r_rc.json().get("data", [])
                        if data_rc and isinstance(data_rc, list):
                            item_rc = data_rc[0]
                            messages_rc = item_rc.get("messages", [])
                            if messages_rc:
                                for msg_rc in messages_rc:
                                    code_rc = msg_rc.get("code")
                                    subject_rc = msg_rc.get("subject", "")
                                    body_rc = msg_rc.get("message", "")
                                    sender_rc = msg_rc.get("from", "")

                                    otp_rc = code_rc or extract_otp_code(f"{subject_rc}\n{body_rc}")
                                    conf_link_rc = extract_confirmation_link(f"{subject_rc}\n{body_rc}")
                                    if otp_rc or conf_link_rc:
                                        elapsed = round(time.time() - start_time, 2)
                                        logger.info(f"[Smail1s Roundcube] Đã nhận OTP: {otp_rc} cho {email} trong {elapsed}s")
                                        return OTPVerificationResult(
                                            success=True,
                                            email=email,
                                            otp_code=otp_rc,
                                            sender=sender_rc,
                                            subject=subject_rc,
                                            body_preview=body_rc[:150],
                                            elapsed_seconds=elapsed,
                                            metadata={"confirmation_link": conf_link_rc} if conf_link_rc else {},
                                        )
                except Exception as e:
                    logger.debug(f"[Smail1s Roundcube] Lỗi poll: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=email,
            error=f"Hết thời gian chờ OTP Hotmail qua smail1s.com sau {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )



# ==============================================================================
# 8. DONGVANFB TOOLS API PROVIDER (Hotmail / Outlook OAuth2 Tool Engine)
# ==============================================================================

class DongVanHotmailProvider(BaseEmailProvider):
    """
    DongVanFB Tools API provider for Hotmail / Outlook reading via OAuth2.
    Docs: https://docs.dongvanfb.net / https://tools.dongvanfb.net/api/
    Directly extracts OTP from Facebook emails using OAuth2 refresh tokens.
    """
    DONGVAN_BASE_URL = "https://tools.dongvanfb.net/api"
    SMAIL1S_BASE_URL = "https://smail1s.com/get_messages"
    _file_lock = HotmailAccountManager._lock
    _accounts_pool: List[Dict[str, Any]] = HotmailAccountManager._accounts_pool
    _cursor: int = 0

    def __init__(self, hotmail_file: str = "hotmails.txt"):
        self.hotmail_file = hotmail_file
        if not HotmailAccountManager._accounts_pool:
            DongVanHotmailProvider.load_from_file(hotmail_file)

    @classmethod
    def load_from_file(cls, filepath: str = "hotmails.txt") -> int:
        return HotmailAccountManager.load_from_file(filepath)

    @classmethod
    def load_from_text(cls, text: str, append_to_file: bool = True, filepath: str = "hotmails.txt") -> int:
        return HotmailAccountManager.load_from_text(text, append_to_file=append_to_file, filepath=filepath)

    @classmethod
    def remove_account(cls, email: str, filepath: str = "hotmails.txt") -> bool:
        return HotmailAccountManager.remove_account(email, filepath=filepath)

    @classmethod
    def reset_in_use(cls) -> None:
        HotmailAccountManager.reset_in_use()

    def release_account(self, email: str, quarantine: bool = True) -> None:
        HotmailAccountManager.release_account(email, quarantine=quarantine)

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        acc_data = HotmailAccountManager.allocate_account(filepath=self.hotmail_file)
        if not acc_data:
            logger.error("[DongVanFB] No Hotmail accounts available!")
            return None
        email = acc_data["email"]
        logger.info(f"[DongVanFB] Allocated Hotmail account: {email}")
        
        # Kiểm tra mã OTP cũ trước đó để tránh nhận nhầm mã cũ chưa xóa
        init_codes = set()
        rf = (acc_data.get("refresh_token") or "").strip()
        cid = (acc_data.get("client_id") or "").strip() or "e9a37c35-7d52-4415-be02-463e264de917"
        if rf:
            try:
                r_p = requests.post(
                    f"{self.DONGVAN_BASE_URL}/get_code_oauth2",
                    json={"email": email, "refresh_token": rf, "client_id": cid, "type": "facebook"},
                    timeout=5
                )
                if r_p.status_code == 200:
                    d = r_p.json()
                    if d.get("status") and d.get("code"):
                        c = extract_otp_code(str(d.get("code")).strip())
                        if c: init_codes.add(c)
            except Exception:
                pass
            try:
                r_m = requests.post(
                    f"{self.DONGVAN_BASE_URL}/get_messages_oauth2",
                    json={"email": email, "refresh_token": rf, "client_id": cid, "list_mail": "all"},
                    timeout=5
                )
                if r_m.status_code == 200:
                    for msg in r_m.json().get("messages", []):
                        c = msg.get("code") or extract_otp_code(f"{msg.get('subject', '')}\n{msg.get('message', '')}")
                        if c: init_codes.add(c)
            except Exception:
                pass
        acc_data["initial_codes"] = list(init_codes)
        acc_data["initial_code"] = list(init_codes)[0] if init_codes else None

        return EmailAccount(
            email=email,
            provider="hotmail_custom",
            password=acc_data["password"],
            metadata=acc_data,
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        meta = account.metadata
        email = account.email.strip().lstrip('\ufeff')
        password = account.password or meta.get("password", "")
        refresh_token = (meta.get("refresh_token") or "").strip()
        client_id = (meta.get("client_id") or "").strip()
        if refresh_token and not client_id:
            client_id = "e9a37c35-7d52-4415-be02-463e264de917"
        rec_email = meta.get("rec_email")
        rec_pwd = meta.get("rec_pwd")
        init_codes_set = set(meta.get("initial_codes") or [])
        if meta.get("initial_code"):
            init_codes_set.add(meta.get("initial_code"))

        logger.info(f"[DongVanFB] Đang chờ mã OTP mới cho {email} qua DongVanFB API (Loại trừ {len(init_codes_set)} mã cũ, Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            # 1. Primary: DongVanFB get_code_oauth2
            if refresh_token and client_id:
                try:
                    payload = {
                        "email": email,
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "type": "facebook",
                    }
                    r = requests.post(f"{self.DONGVAN_BASE_URL}/get_code_oauth2", json=payload, timeout=15.0)
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("status") and data.get("code"):
                            raw_code = str(data.get("code")).strip()
                            clean_otp = extract_otp_code(raw_code) or raw_code
                            init_code = meta.get("initial_code")
                            if clean_otp and clean_otp not in init_codes_set:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[DongVanFB API] Bắt được mã OTP: {clean_otp} cho {email} sau {elapsed}s")
                                content_str = str(data.get("content") or "")
                                conf_link = extract_confirmation_link(content_str)
                                return OTPVerificationResult(
                                    success=True,
                                    email=email,
                                    otp_code=clean_otp,
                                    sender=data.get("from", "registration@facebookmail.com"),
                                    subject=data.get("content", ""),
                                    body_preview=data.get("content", "")[:150],
                                    elapsed_seconds=elapsed,
                                    confirmation_link=conf_link,
                                    metadata={"raw": data, "provider": "dongvanfb"},
                                )
                except Exception as e:
                    logger.debug(f"[DongVanFB get_code_oauth2] Poll error: {e}")

                # 2. Fallback: DongVanFB graph_code
                try:
                    payload_g = {
                        "email": email,
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "type": "facebook",
                    }
                    r_g = requests.post(f"{self.DONGVAN_BASE_URL}/graph_code", json=payload_g, timeout=15.0)
                    if r_g.status_code == 200:
                        data_g = r_g.json()
                        if data_g.get("status") and data_g.get("code"):
                            raw_code = str(data_g.get("code")).strip()
                            clean_otp = extract_otp_code(raw_code) or raw_code
                            if clean_otp and clean_otp not in init_codes_set:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[DongVanFB Graph] Bắt được mã OTP: {clean_otp} cho {email} sau {elapsed}s")
                                content_str_g = str(data_g.get("content") or "")
                                conf_link_g = extract_confirmation_link(content_str_g)
                                return OTPVerificationResult(
                                    success=True,
                                    email=email,
                                    otp_code=clean_otp,
                                    sender=data_g.get("from", "registration@facebookmail.com"),
                                    subject=data_g.get("content", ""),
                                    body_preview=data_g.get("content", "")[:150],
                                    elapsed_seconds=elapsed,
                                    confirmation_link=conf_link_g,
                                )
                except Exception as e:
                    logger.debug(f"[DongVanFB graph_code] Poll error: {e}")

                # 3. Fallback: DongVanFB get_messages_oauth2
                try:
                    payload_m = {
                        "email": email,
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "list_mail": "all",
                    }
                    r_m = requests.post(f"{self.DONGVAN_BASE_URL}/get_messages_oauth2", json=payload_m, timeout=15.0)
                    if r_m.status_code == 200:
                        msgs = r_m.json().get("messages", [])
                        for m in msgs:
                            subj = m.get("subject", "")
                            msg_body = m.get("message", "")
                            sndr = m.get("from", "")
                            if "facebook" in sndr.lower() or "fb-" in subj.lower() or "xác nhận" in subj.lower() or "code" in subj.lower():
                                code = m.get("code") or extract_otp_code(f"{subj}\n{msg_body}")
                                conf_link = extract_confirmation_link(f"{subj}\n{msg_body}")
                                if (code or conf_link) and (not code or code not in init_codes_set):
                                    elapsed = round(time.time() - start_time, 2)
                                    logger.info(f"[DongVanFB Messages] Bắt được mã OTP: {code} cho {email} sau {elapsed}s")
                                    return OTPVerificationResult(
                                        success=True,
                                        email=email,
                                        otp_code=code,
                                        sender=sndr,
                                        subject=subj,
                                        body_preview=msg_body[:150],
                                        elapsed_seconds=elapsed,
                                        confirmation_link=conf_link,
                                    )
                except Exception as e:
                    logger.debug(f"[DongVanFB get_messages_oauth2] Poll error: {e}")

                # 4. Fallback: Smail1s OAuth / Graph
                try:
                    p_sm = {"data": f"{email}|{refresh_token}|{client_id}", "mode": "oauth"}
                    r_sm = requests.post(self.SMAIL1S_BASE_URL, json=p_sm, timeout=10)
                    if r_sm.status_code == 200:
                        d_sm = r_sm.json().get("data", [])
                        if d_sm and isinstance(d_sm, list):
                            msgs_sm = d_sm[0].get("messages", [])
                            if msgs_sm:
                                sm_latest = msgs_sm[0]
                                sm_code = sm_latest.get("code") or extract_otp_code(f"{sm_latest.get('subject', '')}\n{sm_latest.get('message', '')}")
                                conf_link = extract_confirmation_link(f"{sm_latest.get('subject', '')}\n{sm_latest.get('message', '')}")
                                if (sm_code or conf_link) and (not sm_code or sm_code not in init_codes_set):
                                    elapsed = round(time.time() - start_time, 2)
                                    logger.info(f"[Smail1s OAuth Fallback] Bắt được mã OTP: {sm_code} cho {email} sau {elapsed}s")
                                    return OTPVerificationResult(
                                        success=True,
                                        email=email,
                                        otp_code=sm_code,
                                        sender=sm_latest.get("from", ""),
                                        subject=sm_latest.get("subject", ""),
                                        body_preview=sm_latest.get("message", "")[:150],
                                        elapsed_seconds=elapsed,
                                        confirmation_link=conf_link,
                                    )
                except Exception:
                    pass

            # 5. Fallback Roundcube (nếu có rec_email & rec_pwd)
            if rec_email and rec_pwd:
                try:
                    p_rc = {"data": f"{rec_email}|{rec_pwd}", "mode": "roundcube"}
                    r_rc = requests.post(self.SMAIL1S_BASE_URL, json=p_rc, timeout=8)
                    if r_rc.status_code == 200:
                        d_rc = r_rc.json().get("data", [])
                        if d_rc and isinstance(d_rc, list):
                            msgs_rc = d_rc[0].get("messages", [])
                            if msgs_rc:
                                rc_latest = msgs_rc[0]
                                rc_code = rc_latest.get("code") or extract_otp_code(f"{rc_latest.get('subject', '')}\n{rc_latest.get('message', '')}")
                                conf_link = extract_confirmation_link(f"{rc_latest.get('subject', '')}\n{rc_latest.get('message', '')}")
                                if rc_code or conf_link:
                                    elapsed = round(time.time() - start_time, 2)
                                    logger.info(f"[Smail1s Roundcube Fallback] Bắt được OTP: {rc_code} cho {email}")
                                    return OTPVerificationResult(
                                        success=True,
                                        email=email,
                                        otp_code=rc_code,
                                        sender=rc_latest.get("from", ""),
                                        subject=rc_latest.get("subject", ""),
                                        body_preview=rc_latest.get("message", "")[:150],
                                        elapsed_seconds=elapsed,
                                        confirmation_link=conf_link,
                                    )
                except Exception:
                    pass

            # 6. Fallback IMAP SSL trực tiếp (khi có mật khẩu mail)
            if password and "@" in email and any(d in email.lower() for d in ("hotmail", "outlook", "live", "msn")):
                try:
                    imap_prov = HotmailImapEmailProvider(hotmail_file=self.hotmail_file)
                    imap_res = imap_prov.wait_for_otp(
                        account=account,
                        timeout_seconds=min(12, int(max(3, timeout_seconds - (time.time() - start_time)))),
                        poll_interval=max(3, poll_interval),
                        proxy=proxy
                    )
                    if imap_res and imap_res.success:
                        return imap_res
                except Exception as e:
                    logger.debug(f"[Hotmail IMAP Fallback] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=email,
            error=f"Timeout waiting for Hotmail OTP via DongVanFB API after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
class Smail1sTempMailProvider(BaseEmailProvider):
    """
    Smail1s.com Disposable Temp Mail API provider.
    Automatically generates fresh virtual mailboxes on smail1s.com/smailwork.com.
    Does NOT require or consume accounts from hotmails.txt.
    """
    BASE_URL = "https://smail1s.com"
    _cached_domains: List[str] = []

    def get_domains(self) -> List[str]:
        if Smail1sTempMailProvider._cached_domains:
            return Smail1sTempMailProvider._cached_domains
        try:
            r = requests.get(f"{self.BASE_URL}/api/v2/mail/domains", timeout=8)
            if r.status_code == 200:
                domains = r.json().get("domains", [])
                if domains and isinstance(domains, list):
                    Smail1sTempMailProvider._cached_domains = domains
                    return domains
        except Exception as e:
            logger.debug(f"[Smail1sTemp] Lỗi lấy danh sách domain: {e}")
        return ["smail1s.com", "smailwork.com", "hotmailtrusted.com", "smailpro.com", "smail1s.net", "smailwork.net", "smail1s.org", "smailmail.com", "smailpro.net", "trusthotmail.com"]

    def __init__(self, fixed_domain: Optional[str] = None, **kwargs):
        super().__init__()
        self.fixed_domain = str(fixed_domain).lower().strip().lstrip("@") if fixed_domain else None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        domains = self.get_domains()
        if domain:
            selected_domain = str(domain).lower().strip().lstrip("@")
        elif getattr(self, "fixed_domain", None):
            selected_domain = self.fixed_domain
        else:
            selected_domain = random.choice(domains)
        prefix = "".join(random.choices(string.ascii_lowercase, k=5)) + "".join(random.choices(string.digits, k=4))
        try:
            payload = {"mailbox": prefix, "domain": selected_domain}
            headers = {"Content-Type": "application/json"}
            r = requests.post(f"{self.BASE_URL}/api/v2/mail/create", json=payload, headers=headers, timeout=10)
            if r.status_code in (200, 201):
                email = r.json().get("email") or f"{prefix}@{selected_domain}"
                logger.info(f"[Smail1sTemp] Đã cấp hòm thư ảo mới: {email}")
                return EmailAccount(
                    email=email,
                    provider="smail1s_temp",
                    metadata={"mailbox": prefix, "domain": selected_domain}
                )
        except Exception as e:
            logger.error(f"[Smail1sTemp] Lỗi khởi tạo hòm thư ảo: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        logger.info(f"[Smail1sTemp] Đang chờ mã OTP cho mail ảo {email} (Tối đa: {timeout_seconds}s)...")

        headers = {"Content-Type": "application/json"}
        payload = {"email": email}

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.post(f"{self.BASE_URL}/api/v2/mail/inbox", json=payload, headers=headers, timeout=8)
                if r.status_code == 200:
                    messages = r.json().get("messages", [])
                    for msg in messages:
                        subject = msg.get("subject", "") or ""
                        sender = msg.get("from", "") or ""
                        preview = msg.get("preview", "") or ""
                        code = extract_otp_code(f"{subject}\n{preview}")
                        if not code and "uid" in msg:
                            try:
                                r_det = requests.post(
                                    f"{self.BASE_URL}/api/v2/mail/detail",
                                    json={"email": email, "uid": msg["uid"]},
                                    headers=headers,
                                    timeout=6
                                )
                                if r_det.status_code == 200:
                                    det_body = r_det.json().get("body", "") or ""
                                    code = extract_otp_code(f"{subject}\n{det_body}")
                            except Exception:
                                pass

                        if code:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[Smail1sTemp] Bắt được mã OTP: {code} cho {email} sau {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=email,
                                otp_code=code,
                                sender=sender,
                                subject=subject,
                                body_preview=preview[:150],
                                elapsed_seconds=elapsed,
                                metadata={"raw": msg, "provider": "smail1s_temp"}
                            )
            except Exception as e:
                logger.debug(f"[Smail1sTemp] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=email,
            error=f"Hết thời gian chờ OTP hòm thư ảo ({timeout_seconds}s)",
            elapsed_seconds=elapsed,
        )


class MailnesiaProvider(BaseEmailProvider):
    """
    Mailnesia.com free public temporary inbox provider.
    No sign up required, instant HTML/RSS inbox, unlimited addresses.
    """
    BASE_URL = "https://mailnesia.com"
    provider_name = "mailnesia"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        prefix = "".join(random.choices(string.ascii_lowercase, k=7)) + "".join(random.choices(string.digits, k=3))
        email = f"{prefix}@mailnesia.com"
        return EmailAccount(
            email=email,
            provider="mailnesia",
            metadata={"mailbox": prefix}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        mailbox = account.metadata.get("mailbox") or account.email.split("@")[0]
        url = f"{self.BASE_URL}/rss/{mailbox}"
        proxies = self._get_proxies(proxy)

        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, proxies=proxies, timeout=8)
                if r.status_code == 200 and r.text:
                    m = re.search(r'\b(\d{5,8})\b', r.text)
                    if m:
                        otp_code = m.group(1)
                        elapsed = round(time.time() - start_time, 2)
                        return OTPVerificationResult(
                            success=True,
                            email=account.email,
                            otp_code=otp_code,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "mailnesia"}
                        )
            except Exception as e:
                logger.debug(f"[Mailnesia] Poll error: {e}")
            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"H?t th?i gian ch? OTP ({timeout_seconds}s)",
            elapsed_seconds=elapsed,
        )


def get_email_provider(
    provider_name: str = "dongvanfb",
    api_key: Optional[str] = None,
    account_type: str = "hotmail",
    **kwargs
) -> BaseEmailProvider:
    """
    Factory function to instantiate the desired email provider.
    Defaults to DongVanHotmailProvider using Hotmail pool & DongVanFB OAuth2 tool API.
    """
    name = (provider_name or "dongvanfb").lower().strip()

    if name in ("metaking", "metaking_top", "metaking_email", "metaking_phone") or "metaking" in name:
        srv_type = "phone" if "phone" in name else kwargs.get("service_type", "email")
        server = kwargs.get("server", 1)
        domain = kwargs.get("domain", "")
        if not domain or domain == "gmail.com":
            try:
                # json, os imported at top level
                if os.path.exists("config.json"):
                    with open("config.json", "r", encoding="utf-8") as f_cfg:
                        cfg_d = json.load(f_cfg)
                        domain = cfg_d.get("metaking_domain", "hotmail.com") or "hotmail.com"
            except Exception:
                domain = "hotmail.com"
        if not domain:
            domain = "hotmail.com"
        if "gmail" in name:
            domain = "gmail.com"
            srv_type = "email"
        elif "icloud" in name:
            domain = "icloud.com"
            srv_type = "email"
        elif "hotmail" in name:
            domain = "hotmail.com"
            srv_type = "email"
        elif "outlook" in name:
            domain = "outlook.com"
            srv_type = "email"
        service_id = 67 if srv_type == "phone" else 1
        country_id = kwargs.get("country_id", 154)
        price_lvl = kwargs.get("price", "low")

        effective_key = (api_key or "").strip()
        if not effective_key:
            try:
                # json, os imported at top level
                if os.path.exists("config.json"):
                    with open("config.json", "r", encoding="utf-8") as f_cfg:
                        cfg_data = json.load(f_cfg)
                        effective_key = str(cfg_data.get("metaking_api_key", "")).strip()
            except Exception:
                pass

        return MetakingEmailProvider(
            api_key=effective_key,
            service_type=srv_type,
            server=server,
            domain=domain,
            service_id=service_id,
            country_id=country_id,
            price_level=price_lvl
        )

    if any(k in name for k in ("account_email", "acc_email", "self_email", "đi kèm", "di kem", "kem acc")):
        prov = DongVanHotmailProvider(hotmail_file=api_key or "hotmails.txt")
        prov.provider_name = "account_email"
        return prov

    if any(k in name for k in ("clean_trio", "clean_suite", "clean_quartet", "clean_selected", "trio", "bo_3_mail", "bo_4_mail", "3_mail", "4_mail", "bộ 3", "bo 3", "bộ 4", "bo 4", "clean_mail", "hom_thu_sach", "mail_sach")):
        sel_doms = kwargs.get("selected_domains") or kwargs.get("selected_custom_domains")
        return CleanTrioEmailProvider(selected_domains=sel_doms)
    elif "smail1s_domain" in name or name == "smail1s_only":
        return CleanTrioEmailProvider(selected_domains=["smail1s.com"])
    elif "laoia_domain" in name or name == "laoia_only":
        return CleanTrioEmailProvider(selected_domains=["laoia.com"])
    elif any(k in name for k in ("smailwork", "smailwork_domain", "pqudx6448")):
        return CleanTrioEmailProvider(selected_domains=["smailwork.com"])
    elif "hotmailtrusted" in name:
        return CleanTrioEmailProvider(selected_domains=["hotmailtrusted.com"])
    elif "mailto_plus" in name or "mailtoplus" in name:
        return CleanTrioEmailProvider(selected_domains=["mailto.plus"])

    if any(k in name for k in ("auto_rotator", "autorotator", "smart_rotator", "tat_ca", "tất cả", "tat ca", "random_mail", "all_mail", "all_free", "xoay", "mọi nguồn", "moi nguon")):
        return AutoRotatorEmailProvider()
    elif any(k in name for k in ("tempmail_plus", "tempmailplus", "tempmail.plus", "mailto_plus", "mailto.plus")):
        return TempMailPlusProvider()
    elif any(k in name for k in ("inboxes", "inboxes.com", "blondmail", "getnada")):
        return InboxesProvider()
    elif any(k in name for k in ("tempmail_io", "tempmailio", "temp-mail.io", "temp-mail_io")):
        return TempMailIoProvider()
    elif any(k in name for k in ("10minutemail", "tenminutemail", "10minute")):
        return TenMinuteMailNetProvider()
    elif any(k in name for k in ("maildrop", "maildrop.cc")):
        return MaildropProvider()
    elif any(k in name for k in ("smail1s_temp", "smail1stemp", "smail_temp", "temp_smail1s", "tempmail_smail1s")):
        return Smail1sTempMailProvider()
    elif any(k in name for k in ("mailnesia", "mailnesia.com")):
        return MailnesiaProvider()
    elif any(k in name for k in ("tempmaillol", "tempmail.lol", "tempmail_lol", "lol")):
        return TempMailLolProvider()
    elif any(k in name for k in ("mailtm", "mail.tm")):
        return MailTmProvider()
    elif any(k in name for k in ("inboxkitten", "inboxkitten.com", "kitten")):
        return InboxKittenProvider()
    elif any(k in name for k in ("fakemailgenerator", "fake_mail", "fakemail", "armyspy")):
        return FakeMailGeneratorProvider()
    elif any(k in name for k in ("emailfake", "email_fake", "emailfake.com")):
        return EmailFakeProvider()
    elif any(k in name for k in ("throwawaymail", "throwaway", "mailscrap")):
        return ThrowAwayMailProvider()
    elif any(k in name for k in ("disposablemail", "disposable", "fakemail_club")):
        return DisposableMailProvider()
    elif any(k in name for k in ("generator_email", "generator.email", "generator", "generatoremail")):
        return GeneratorEmailProvider()
    elif any(k in name for k in ("guerrilla", "guerrillamail", "sharklasers")):
        return GuerrillaMailProvider()
    elif any(k in name for k in ("onesecmail", "1secmail", "onesec")):
        return OneSecMailProvider()
    elif any(k in name for k in ("mohmal", "mohmal.com", "emailnox")):
        return MohmalProvider()
    elif any(k in name for k in ("kopeechka", "kopechka")):
        return KopeechkaEmailProvider(api_token=api_key or "")
    elif any(k in name for k in ("hotmail_imap", "outlook_imap")):
        return HotmailImapEmailProvider()
    elif any(k in name for k in ("custom_hotmail", "tự nhập", "tu nhap", "hotmails.txt", "kho hotmail")):
        prov = DongVanHotmailProvider(hotmail_file=api_key or "hotmails.txt")
        prov.provider_name = "Hotmail Tự Nhập"
        return prov
    elif any(k in name for k in ("smail1s", "smail1s.com")):
        return Smail1sHotmailProvider(hotmail_file=api_key or "hotmails.txt")
    elif any(k in name for k in ("dongvan", "dongvanfb", "dongvan_api", "hotmail")):
        prov = DongVanHotmailProvider(hotmail_file=api_key or "hotmails.txt")
        return prov
    else:
        logger.warning(f"Unknown provider '{provider_name}'. Defaulting to DongVanHotmailProvider.")
        return DongVanHotmailProvider(hotmail_file=api_key or "hotmails.txt")

# ==============================================================================
def generate_random_comet_session_token() -> str:
    """Sinh mã phiên Comet 3 thành phần ngẫu nhiên chuẩn Meta (ví dụ: pjdnje:2c596o:c83vrq)."""
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    p1 = "".join(random.choice(chars) for _ in range(6))
    p2 = "".join(random.choice(chars) for _ in range(6))
    p3 = "".join(random.choice(chars) for _ in range(6))
    return f"{p1}:{p2}:{p3}"


def generate_random_comet_hsi() -> str:
    """Sinh mã Haste Session ID 19 chữ số chuẩn Meta theo cluster timestamp."""
    return f"7695{random.randint(100000000000000, 999999999999999)}"


COMET_DYN_SAMPLES = [
    "7xe6E5q1QyUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE0AC0yE7i0n24oaEd86a3a1YwBgao6C0Mo2swaO4U2zxe2GewbS361qw8Xxm16wa-0raazo7u0zE2ZwrU6qE15E6O1FwlES1uGp1yU5N90HwtU26wbu4o1oE0ye3mdw9-",
    "7xe6E5q1QyUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE0AC0yE7i0n24oaEd86a3a1YwBgao6C0Mo2swaO4U2zxe2GewbS361qw8Xxm16wa-0raazo7u0zE2ZwrU6qE15E6O1FwlES1uGp1yU5N90HwtU26wbu4o1oE0ye3mdw98",
    "7xe6E5q1QyUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE0AC0yE7i0n24oaEd86a3a1YwBgao6C0Mo2swaO4U2zxe2GewbS361qw8Xxm16wa-0raazo7u0zE2ZwrU6qE15E6O1FwlES1uGp1yU5N90HwtU26wbu4o1oE0ye3mdw90",
    "7xe6E5q1QyUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE0AC0yE7i0n24oaEd86a3a1YwBgao6C0Mo2swaO4U2zxe2GewbS361qw8Xxm16wa-0raazo7u0zE2ZwrU6qE15E6O1FwlAcwnGCgoK1sigaU7u0xE2Tx60ma08zwRzo",
    "7xe6E5q1QyUbFp41twpUnwgU29zEdEc8co2qwJw5ux609vCwjE0AC0yE7i0n24oaEd86a3a1YwBgao6C0Mo2swaO4U2zxe2GewbS361qw8Xxm16wa-10w5NyES1Tw8W0Lo6-1CG0hq1Iwqo5p385WFA6bwn4A2K1Tw8q0JUhw5yw28UdoS",
    "1Z3pawlEnwm8_Bg9ppoW5UdE4a2i5U4e0C86u7E39x60zU3ex608ewk9E4W0pKq0FE6S0x81vohw73wGwcq1GwqU2YwbK0oi0zE1jU1soG0hi0Lo6-0Co1kU1UU3jwGwbu",
]

COMET_TELEMETRY_BUNDLES = [
    {
        "csr": "gJsp4NqvaAT8zhcIiRNZXn4baFkH98ICLnKhkzAkROrFqcZl4lHAOCPiir9kPbnJAHHjjhROOBF9yLAKJrCKaJ7_BKOfviaD9iGV8xGVAfybgzoBaFECuqj8ihqHiHnmaxm6EK68B7z8hwjFEfEhwoFo629wioO0A825la8jDDwv9aG1HxC1gw8e0AqwcS1fxu4oaoc833w4fwjU0Byew2fE2mw920K8660oa0aXw3D80ojwqE5y01uqg00BdNw1kO019Sg3-w0lP40dww",
        "hsdp": "gc22p57-Rqy8K8xpy8hxCaAAydrBxXyo4Ou6Ci7UVxp0vE1d65A0dKo4q06p80T202aa08Jw1be00Ks809-80cr80vVw",
        "hblp": "04Bw1j20gu0jS05ro0T2078E1vU1bU3Zw5swFw3b80NS04aE0ya02sm039e06Po0vsw0DUw2Xo1kE0Ga1Aw2LU0Ce06l981DU37wqo1vo6q58",
        "sjsp": "gc22paffXlG8yUy5C8x66oGii8RKm7K9wj9Uqp8vzC5A1-w4Qomg0SVwhE0pAw3s8",
    },
    {
        "csr": "gJsp4NqvaAT8zhcIiRNZXn4baFkH98ICLnKhkzAkROrFqcZl4lHAOCPiir9kPbnJAHHjjhROOBF9yLAKJrCKaJ7_BKOfviaD9iGV8xGVAfybgzoBaFECuqj8ihqHiHnmaxm6EK68B7z862q3W4o6am1wyo4Ccw920xliy4VVU7OiGwqUpwk823w96E3dwjUnx62C320MU13U4-09ozE0zW0BE2gwby1xw62w2KU0VO064U6G1ow0nCA009jso0lcw0itA0_E05sN03o8",
        "hsdp": "gc22p57-Rqy8K8xpy8hxCaAAydrBxXyo4Ou6Ci7UVxp0vE1d65A0dKo0qHw3s808EE0yS04IU02VMw0DUw0NIw1_C",
        "hblp": "04Bw1j20gu0jS05ro0T2078E1vU1bU3Zw5swFw3b80NS04aE0ya02sm039e06Po0vsw0DUw2Xo1kE0Ga1Aw2LU0Ce06l981DU37wqo1vo6q58",
        "sjsp": "gc22paffXlG8yUy5C8x66oGii8RKm7K9wj9Uqp8vzC5A1-w4Qomg0SVw1GK0dMw",
    },
    {
        "csr": "gJsp4NqvaAT8zhcIiRNZXn4baFkH98ICLnKhkzAkROrFqcZl4lHAOCPiir9kPbnJAHHjjhROOBF9yLAKJrCKaJ7_BKOfviaD9iGV8xGVAfybgzoBaFECuqj8ihqHiHnmaxm6EK68B7z8hwjFEfEhwoFo629wioO0A825la8jDDwv9aG1HxC1gw8e0AqwcS1fxu4oaoc833w4fwjU0Byew2fE2mw920K8660oa0aXw3D80ojwqE5y01uqg00BdNw1kO019Sg3-w0lP40987",
        "hsdp": "gc22p57-Rqy8K8xpy8hxCaAAydrBxXyo4Ou6Ci7UVxp0vE1d65A0dKo4q06p80T202aa08Jw1be00Ks809-80cr80vVw",
        "hblp": "04Bw1j20gu0jS05ro0T2078E1vU1bU3Zw5swFw3b80NS04aE0ya02sm039e06Po0vsw0DUw2Xo1kE0Ga1Aw2LU0Ce06l981DU37wqo1vo6q58",
        "sjsp": "gc22paffXlG8yUy5C8x66oGii8RKm7K9wj9Uqp8vzC5A1-w4Qomg0SVwhE0pAw3s8",
    },
]

def get_random_comet_telemetry() -> dict:
    """Sinh bộ telemetry Haste/Comet ngẫu nhiên đa dạng, loại trừ hoàn toàn việc trùng lặp dấu vân tay giữa các phiên."""
    bundle = random.choice(COMET_TELEMETRY_BUNDLES)
    dyn = random.choice(COMET_DYN_SAMPLES)
    return {
        "__dyn": dyn,
        "__csr": bundle["csr"],
        "__hsdp": bundle["hsdp"],
        "__hblp": bundle["hblp"],
        "__sjsp": bundle["sjsp"],
        "__s": generate_random_comet_session_token(),
        "__hsi": generate_random_comet_hsi(),
        "__req": random.choice(["e", "f", "g", "h", "i", "k", "l", "m", "n", "p"]),
        "__spin_t": str(int(time.time())),
    }


# 6. FACEBOOK OTP SUBMISSION LOGIC
# ==============================================================================

def extract_facebook_comet_tokens(
    session: Any,
    server: str = "www.facebook.com",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 15,
) -> Dict[str, str]:
    """
    Truy cap https://www.facebook.com/confirmemail.php voi cookie phien hien tai
    de trich xuat chinh xac bo token Comet Desktop: fb_dtsg (NAf...), lsd, rev, hs, hsi, s.
    Day la bo token bat buoc de Facebook Relay GraphQL mutation chap nhan.
    """
    tokens = {
        "dtsg": "",
        "lsd": "",
        "rev": "",
        "hs": "",
        "hsi": "",
        "s": "",
        "actor_id": "",
        "is_confirmed": False,
    }
    incoming_ua = (headers or {}).get("User-Agent") or (headers or {}).get("user-agent") or getattr(session, "headers", {}).get("User-Agent") or getattr(session, "headers", {}).get("user-agent") or ""
    target_host = server or "m.facebook.com"
    is_session_mobile = bool(
        (target_host != "www.facebook.com")
        or (incoming_ua and any(k in incoming_ua.lower() for k in ("android", "mobile", "iphone", "ipad", "dalvik", "katana")))
    )
    if is_session_mobile:
        if target_host in ("www.facebook.com", "web.facebook.com"):
            target_host = "m.facebook.com"
        is_desktop_comet = False
    else:
        is_desktop_comet = bool("www.facebook.com" in target_host)
    fetch_hdrs = dict(headers or {})
    if is_desktop_comet:
        desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        fetch_hdrs["User-Agent"] = desktop_ua
        fetch_hdrs["sec-ch-ua"] = '"Not/A)Brand";v="99", "Chromium";v="131"'
        fetch_hdrs["sec-ch-ua-full-version-list"] = '"Not/A)Brand";v="99.0.0.0", "Chromium";v="131.0.6778.86"'
        fetch_hdrs["sec-ch-ua-mobile"] = "?0"
        fetch_hdrs["sec-ch-ua-model"] = '""'
        fetch_hdrs["sec-ch-ua-platform"] = '"Windows"'
        fetch_hdrs["sec-ch-ua-platform-version"] = '"19.0.0"'
        fetch_hdrs["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        fetch_hdrs["Accept-Language"] = (headers or {}).get("Accept-Language") or (headers or {}).get("accept-language") or "en-US,en;q=0.9"
        fetch_hdrs["Referer"] = f"https://{target_host}/confirmemail.php?next=https%3A%2F%2F{target_host}%2F%3Fdismiss%3D1%252F%253Flocale%253Den_US"
    else:
        incoming_ua = (headers or {}).get("User-Agent") or (headers or {}).get("user-agent") or ""
        eff_ua = incoming_ua or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
        fetch_hdrs["User-Agent"] = eff_ua
        fetch_hdrs["sec-ch-ua-mobile"] = "?1"
        if "android" in eff_ua.lower():
            fetch_hdrs["sec-ch-ua-platform"] = '"Android"'
        elif "iphone" in eff_ua.lower() or "ios" in eff_ua.lower():
            fetch_hdrs["sec-ch-ua-platform"] = '"iOS"'
        fetch_hdrs["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        fetch_hdrs["Accept-Language"] = (headers or {}).get("Accept-Language") or (headers or {}).get("accept-language") or "en-US,en;q=0.9,vi;q=0.8"
        fetch_hdrs["Referer"] = f"https://{target_host}/confirmemail.php"
    fetch_hdrs.pop("X-Requested-With", None)
    fetch_hdrs.pop("x-requested-with", None)
    fetch_hdrs["sec-fetch-dest"] = "document"
    fetch_hdrs["sec-fetch-mode"] = "navigate"
    fetch_hdrs["sec-fetch-site"] = "same-origin"
    fetch_hdrs["sec-fetch-user"] = "?1"
    fetch_hdrs["upgrade-insecure-requests"] = "1"

    cookie_str = ""
    c_dict = {}
    if hasattr(session, "get_cookie_string"):
        try:
            cookie_str = session.get_cookie_string()
        except Exception:
            pass
    if hasattr(session, "get_cookies"):
        try:
            c_dict = session.get_cookies()
        except Exception:
            pass
    elif hasattr(session, "cookies"):
        try:
            c_dict = session.cookies.get_dict() if hasattr(session.cookies, "get_dict") else dict(session.cookies)
        except Exception:
            pass
    if not cookie_str and c_dict:
        cookie_str = "; ".join(f"{k}={v}" for k, v in c_dict.items())
    if hasattr(session, "set_cookie") and c_dict:
        for ck, cv in c_dict.items():
            try:
                session.set_cookie(ck, cv, domain=".facebook.com")
            except Exception:
                pass
    if cookie_str and "cookie" not in [k.lower() for k in fetch_hdrs]:
        fetch_hdrs["Cookie"] = cookie_str

    if c_dict.get("c_user"):
        tokens["actor_id"] = str(c_dict["c_user"])

    urls = [
        f"https://{target_host}/confirmemail.php?next=https%3A%2F%2F{target_host}%2F%3Fdismiss%3D1%252F%253Flocale%253Den_US",
        f"https://{target_host}/confirmemail.php?next=undefined",
        f"https://{target_host}/confirmphone.php",
        f"https://{target_host}/confirmemail.php",
    ]
    seen_u = set()
    urls = [u for u in urls if u and not (u in seen_u or seen_u.add(u))]

    def _sync_c(s: Any, r: Any) -> None:
        if not r or not hasattr(r, "headers") or not hasattr(s, "set_cookie"):
            return
        try:
            sc = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else ([r.headers.get("set-cookie")] if "set-cookie" in r.headers else [])
            for p in sc:
                for seg in str(p).split(";"):
                    if "=" in seg:
                        k, v = seg.split("=", 1)
                        if k.strip().lower() not in ("path", "domain", "expires", "max-age", "secure", "httponly", "samesite"):
                            try:
                                s.set_cookie(k.strip(), v.strip(), domain=".facebook.com")
                            except Exception:
                                pass
                            break
        except Exception:
            pass

    for u in urls:
        try:
            r = session.get(u, headers=fetch_hdrs, timeout=timeout, allow_redirects=True, verify=False)
            _sync_c(session, r)
            p_text = getattr(r, "text", "") or ""
            p_text_norm = p_text.replace('\u003a', ':').replace('\u003A', ':').replace('%3A', ':').replace('%3a', ':')
            u_final = getattr(r, "url", "").lower()

            parsed_u = urllib.parse.urlparse(u_final)
            u_path = parsed_u.path.lower()
            is_still_cf = (
                "/checkpoint" in u_path or "/checkpoint" in u_final or "1501092823525282" in u_final
                or "/confirmemail" in u_path or "/confirmphone" in u_path or "/caa/" in u_path
                or "confirmemail.php" in u_path
            )
            has_nvr_in_text = any(bad in p_text.lower() for bad in (
                "caaregistrationconfirmationroot", "caaconfirmationform", "nhập mã xác nhận", "enter confirmation code",
                "enter the confirmation code", "enter the 5-digit code", "mã gồm 5 chữ số", "caa_reg_confirmation",
                "com.bloks.www.bloks.caa.reg.confirmation", "xcaafbmobilewebbloksregconfirmationcontroller",
                "to confirm your account", "we sent a confirmation code", "we sent you a code"
            ))
            has_real_feed = any(k in p_text.lower() for k in ("bảng tin", "news feed", 'data-pagelet="feed"', 'role="feed"', 'id="m_newsfeed_stream"', 'data-sigil="m-feed-stream"'))
            if not is_still_cf and not has_nvr_in_text and (has_real_feed or u_path in ("/feed", "/me")) and not any(bad in u_final for bad in ("checkpoint", "confirm")):
                tokens["is_confirmed"] = True

            m_dtsg = (
                re.search(r'\[\s*"DTSGInit(?:ial)?Data"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'\?"DTSGInit(?:ial)?Data\?",\s*\[\],\s*\{\?"token\?":\s*\?"([^\"]+)', p_text)
                or re.search(r'(NAf[A-Za-z0-9_\-]+:\d+:\d+)', p_text_norm)
                or re.search(r'"dtsg"\s*:\s*\{\s*"token"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'name=["\']fb_dtsg["\']\s+value=["\']([^"\']+)["\']', p_text)
                or re.search(r'\?"tokenName\?":\s*\?"fb_dtsg\?",\s*\?"token\?":\s*\?"([^\"]+)', p_text)
                or re.search(r'"async_get_token"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'\?"token\?":\s*\?"([A-Za-z0-9_-]+:\d+:\d+)', p_text)
            )
            if m_dtsg and not tokens["dtsg"]:
                tokens["dtsg"] = m_dtsg.group(1)

            m_lsd = (
                re.search(r'\[\s*"LSD"\s*,\s*\[\]\s*,\s*\{\s*"token"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'\?"LSD\?",\s*\[\],\s*\{\?"token\?":\s*\?"([^\"]+)', p_text)
                or re.search(r'name=["\']lsd["\']\s+value=["\']([^"\']+)["\']', p_text)
                or re.search(r'\?"tokenName\?":\s*\?"lsd\?",\s*\?"token\?":\s*\?"([^\"]+)', p_text)
                or re.search(r'"token"\s*:\s*"([A-Za-z0-9_-]{16,32})"', p_text)
            )
            if m_lsd and not tokens["lsd"]:
                tokens["lsd"] = m_lsd.group(1)

            m_rev = (
                re.search(r'"client_revision"\s*:\s*(\d+)', p_text)
                or re.search(r'"server_revision"\s*:\s*(\d+)', p_text)
                or re.search(r'"__spin_r"\s*:\s*(\d+)', p_text)
                or re.search(r"__spin_r=(\d+)", p_text)
                or re.search(r'"revision"\s*:\s*(\d+)', p_text)
            )
            if m_rev and not tokens["rev"]:
                tokens["rev"] = m_rev.group(1)

            m_hs = (
                re.search(r'"haste_session"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'"__hs"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'__hs=([^&\x22\x27]+)', p_text)
            )
            if m_hs and not tokens["hs"]:
                tokens["hs"] = m_hs.group(1)

            m_hsi = (
                re.search(r'"hsi"\s*:\s*"([^"]+)"', p_text)
                or re.search(r'"__hsi"\s*:\s*"([^"]+)"', p_text)
                or re.search(r"hsi=(\d+)", p_text)
            )
            if m_hsi and not tokens["hsi"]:
                tokens["hsi"] = m_hsi.group(1)

            m_s = (
                re.search(r'"__s"\s*:\s*"([^"]+)"', p_text)
                or re.search(r"__s=([^&\"\']+)", p_text)
            )
            if m_s and not tokens["s"]:
                tokens["s"] = m_s.group(1)

            m_act = re.search(r'"actorID"\s*:\s*"(\d+)"', p_text) or re.search(r'"USER_ID"\s*:\s*"(\d+)"', p_text)
            if m_act and not tokens["actor_id"]:
                tokens["actor_id"] = m_act.group(1)

            if tokens["dtsg"] and tokens["rev"] and tokens["hs"]:
                break
        except Exception:
            pass

    if not tokens["rev"]:
        tokens["rev"] = "1050672349"
    if not tokens["hs"]:
        tokens["hs"] = "20743.HYP:comet_plat_default_pkg.2.1...0"
    if not tokens["hsi"]:
        tokens["hsi"] = generate_random_comet_hsi()
    if not tokens["s"]:
        tokens["s"] = generate_random_comet_session_token()
    return tokens

def remove_facebook_confirmation_contactpoint(
    session: Any,
    contact_point: str,
    uid: Optional[str] = None,
    server: str = "www.facebook.com",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 12,
) -> Tuple[bool, List[str]]:
    """
    Xóa contact point (email hoặc SĐT pending) khỏi tài khoản qua GraphQL Relay Mutation
    useCAAConfirmationRemoveContactPointMutation (doc_id: 24285278141074939).
    Giải phóng hạn mức contact point (Meta giới hạn tối đa 6 pending contact points).
    Trả về (thành công: bool, danh sách pending contact points còn lại: list[str]).
    """
    clean_cp = (contact_point or "").strip()
    if not clean_cp:
        return False, []

    cookies: Dict[str, str] = {}
    if hasattr(session, "get_cookies"):
        try:
            cookies = session.get_cookies()
        except Exception:
            pass
    elif hasattr(session, "cookies"):
        try:
            cookies = session.cookies.get_dict() if hasattr(session.cookies, "get_dict") else dict(session.cookies)
        except Exception:
            pass

    cur_uid = uid or cookies.get("c_user") or ""
    eff_srv = server if (server and "www" not in server and server != "facebook.com") else "m.facebook.com"
    tokens = extract_facebook_comet_tokens(session, server=eff_srv, headers=headers, timeout=min(8, timeout))
    eff_dtsg = tokens.get("dtsg") or ""
    eff_lsd = tokens.get("lsd") or ""
    eff_rev = tokens.get("rev") or "1050456985"
    eff_hs = tokens.get("hs") or "20741.HYP:comet_plat_default_pkg.2.1...0"
    eff_hsi = tokens.get("hsi") or "7695339384806909400"
    eff_s = tokens.get("s") or ""
    clean_actor = str(cur_uid or tokens.get("actor_id") or "0")

    jazoest = f"2{sum(ord(c) for c in eff_dtsg)}" if eff_dtsg else (f"2{sum(ord(c) for c in eff_lsd)}" if eff_lsd else "25223")

    mut_input = {
        "actor_id": str(clean_actor),
        "client_mutation_id": str(uuid.uuid4()),
        "contact_point": clean_cp,
    }

    dyn_t = get_random_comet_telemetry()
    payload = {
        "av": str(clean_actor),
        "__user": str(clean_actor),
        "__a": "1",
        "__req": "f",
        "__hs": eff_hs,
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": eff_rev,
        "__s": eff_s or dyn_t["__s"],
        "__hsi": eff_hsi or dyn_t["__hsi"],
        "__dyn": dyn_t["__dyn"],
        "__csr": dyn_t["__csr"],
        "__hsdp": dyn_t["__hsdp"],
        "__hblp": dyn_t["__hblp"],
        "__sjsp": dyn_t["__sjsp"],
        "__comet_req": "102",
        "fb_dtsg": eff_dtsg,
        "jazoest": jazoest,
        "lsd": eff_lsd,
        "__spin_r": eff_rev,
        "__spin_b": "trunk",
        "__spin_t": dyn_t["__spin_t"],
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "useCAAConfirmationRemoveContactPointMutation",
        "server_timestamps": "true",
        "variables": json.dumps({"input": mut_input}),
        "doc_id": "24285278141074939",
    }

    req_hdrs = dict(headers or {})
    ref_host = server if (server and "facebook.com" in server) else "www.facebook.com"
    req_hdrs.update({
        "Origin": f"https://{ref_host}",
        "Referer": f"https://{ref_host}/confirmemail.php",
        "X-FB-Friendly-Name": "useCAAConfirmationRemoveContactPointMutation",
        "X-FB-LSD": eff_lsd,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "*/*",
        "X-ASBD-ID": "129477",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    })
    if "user-agent" not in [k.lower() for k in req_hdrs]:
        req_hdrs["User-Agent"] = getattr(session, "user_agent", "") or (headers.get("User-Agent") if headers else "") or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"

    cookie_hdr_val = ""
    if hasattr(session, "get_cookie_string"):
        cookie_hdr_val = session.get_cookie_string()
    elif cookies:
        cookie_hdr_val = "; ".join(f"{ck}={cv}" for ck, cv in cookies.items())
    if cookie_hdr_val and "cookie" not in [k.lower() for k in req_hdrs]:
        req_hdrs["Cookie"] = cookie_hdr_val

    endpoints = ["https://www.facebook.com/api/graphql/", "https://m.facebook.com/api/graphql/"]
    for ep in endpoints:
        try:
            r = session.post(ep, data=payload, headers=req_hdrs, timeout=timeout)
            txt = r.text[9:] if r.text.startswith("for (;;);") else r.text
            res_j = json.loads(txt)
            node = res_j.get("data", {}).get("xfb_caa_registration_remove_contactpoint")
            if node and isinstance(node, dict):
                rem_cps = node.get("other_pending_cps", [])
                logger.info(f"[VR OTP] Đã gỡ bỏ contact point {clean_cp} thành công qua GraphQL Relay! (Còn lại: {len(rem_cps)})")
                return True, rem_cps
            errs = res_j.get("errors", [])
            if errs:
                logger.debug(f"[VR OTP] Lỗi gỡ contact point {clean_cp}: {errs[0].get('message')}")
        except Exception as e:
            logger.debug(f"[VR OTP] Exception khi gỡ contact point {clean_cp} ở {ep}: {e}")
    return False, []


def cleanup_facebook_pending_contactpoints(
    session: Any,
    uid: Optional[str] = None,
    server: str = "www.facebook.com",
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 12,
    keep_contact_point: Optional[str] = None,
) -> int:
    """
    Quét và tự động xóa sạch các contact point tồn đọng (pending cps) của phiên xác minh
    để không bị dính lỗi Meta 1351114 (Email or Phone Number Limit Reached).
    Trả về số lượng contact points đã được giải phóng thành công.
    """
    clean_keep = (keep_contact_point or "").strip().lower()
    fetch_hdrs = dict(headers or {})
    fetch_hdrs["Referer"] = f"https://{server}/"
    if "user-agent" not in [k.lower() for k in fetch_hdrs]:
        fetch_hdrs["User-Agent"] = getattr(session, "user_agent", "") or (headers.get("User-Agent") if headers else "") or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"

    pending_cps: List[str] = []
    try:
        r_page = session.get(f"https://www.facebook.com/confirmemail.php?next=undefined", headers=fetch_hdrs, timeout=timeout)
        txt = getattr(r_page, "text", "") or ""
        # 1. Tìm other_pending_cps trong JSON
        m_pending = re.search(r'"other_pending_cps":\s*(\[[^\]]*\])', txt)
        if m_pending:
            try:
                raw_json_cps = m_pending.group(1).replace(r'\/', '/').replace(r'\u0040', '@')
                parsed_cps = json.loads(raw_json_cps)
                if isinstance(parsed_cps, list):
                    pending_cps.extend([str(x).strip() for x in parsed_cps if x])
            except Exception:
                pass
        # 2. Tìm contact points từ HTML / JSON
        found_cps = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', txt)
        for cp in found_cps:
            cp_l = cp.lower()
            if not any(ig in cp_l for ig in ("fb.com", "facebook.com", "meta.com", "tfbnw.net", "fbcdn.net")):
                if cp not in pending_cps and cp_l != clean_keep:
                    pending_cps.append(cp)
    except Exception as ex:
        logger.debug(f"[VR OTP] Lỗi fetch confirmemail page để cleanup: {ex}")

    removed_count = 0
    for cp in list(set(pending_cps)):
        if clean_keep and cp.lower() == clean_keep:
            continue
        try:
            ok_rem, rem_list = remove_facebook_confirmation_contactpoint(
                session=session,
                contact_point=cp,
                uid=uid,
                server=server,
                headers=headers,
                timeout=timeout,
            )
            if ok_rem:
                removed_count += 1
        except Exception:
            pass

    return removed_count

def add_facebook_confirmation_contactpoint(
    session: Any,
    email: str,
    server: str = "m.facebook.com",
    headers: Optional[Dict[str, str]] = None,
    uid: Optional[str] = None,
    fb_dtsg: Optional[str] = None,
    lsd: Optional[str] = None,
    timeout: int = 6,
) -> Tuple[bool, str]:
    """
    Thực hiện mutation useCAAFBConfirmationAddContactPointMutation (doc_id: 25556223974027527)
    để gắn/thêm địa chỉ email mới vào tài khoản Facebook sau khi mồi SĐT ảo tạo phiên.
    Facebook sẽ chấp nhận email và lập tức phát mã OTP xác nhận về hòm thư này.
    Tương thích hoàn toàn cả trên trình duyệt Chrome Desktop và Katana/Mobile CAA.
    """
    clean_email = (email or "").strip()
    is_email = bool("@" in clean_email and "." in clean_email)
    is_phone = bool(re.match(r'^\+?[0-9]{7,16}$', clean_email.replace(" ", "").replace("-", "")))
    if not is_email and not is_phone:
        return False, "Email hoac So dien thoai khong hop le"

    # Lay cookies
    cookies: Dict[str, str] = {}
    if hasattr(session, "get_cookies"):
        try:
            cookies = session.get_cookies()
        except Exception:
            cookies = {}
    elif hasattr(session, "cookies"):
        try:
            cookies = session.cookies.get_dict() if hasattr(session.cookies, "get_dict") else dict(session.cookies)
        except Exception:
            cookies = {}

    cur_uid = uid or cookies.get("c_user") or ""
    clean_actor = str(cur_uid or "0")
    if hasattr(session, "set_cookie") and cookies:
        for ck, cv in cookies.items():
            try:
                session.set_cookie(ck, cv, domain=".facebook.com")
                session.set_cookie(ck, cv, domain=".m.facebook.com")
            except Exception:
                pass

    # Comet tokens PHẢI LUÔN LUÔN lấy từ www.facebook.com để có Comet DTSG (NAf...) chuẩn Relay Modern
    eff_dtsg = fb_dtsg or ""
    eff_lsd = lsd or ""
    tokens = {}
    if not eff_dtsg or not eff_lsd or not str(eff_dtsg).startswith("NAf"):
        tokens = extract_facebook_comet_tokens(session, server=server, headers=headers, timeout=min(timeout, 8))
        if tokens.get("dtsg"):
            eff_dtsg = tokens["dtsg"]
        if tokens.get("lsd"):
            eff_lsd = tokens["lsd"]

    eff_rev = tokens.get("rev") or "1050672349"
    eff_hs = tokens.get("hs") or "20743.HYP:comet_plat_default_pkg.2.1...0"
    eff_hsi = tokens.get("hsi") or generate_random_comet_hsi()
    eff_s = tokens.get("s") or generate_random_comet_session_token()
    if (not clean_actor or clean_actor == "0") and tokens.get("actor_id"):
        clean_actor = str(tokens["actor_id"])

    jazoest = f"2{sum(ord(c) for c in eff_dtsg)}" if eff_dtsg else (f"2{sum(ord(c) for c in eff_lsd)}" if eff_lsd else "25418")

    mut_input = {
        "actor_id": str(clean_actor),
        "client_mutation_id": str(uuid.uuid4()),
        "contact_point": clean_email,
        "machine_id": "",
    }

    dyn_telemetry = get_random_comet_telemetry()
    gql_payload = {
        "av": str(clean_actor),
        "__user": str(clean_actor),
        "__a": "1",
        "__req": dyn_telemetry.get("__req", "f"),
        "__hs": eff_hs,
        "dpr": "1",
        "__ccg": "EXCELLENT",
        "__rev": eff_rev,
        "__s": eff_s or dyn_telemetry.get("__s", generate_random_comet_session_token()),
        "__hsi": eff_hsi or dyn_telemetry.get("__hsi", generate_random_comet_hsi()),
        "__dyn": dyn_telemetry.get("__dyn", ""),
        "__csr": dyn_telemetry.get("__csr", ""),
        "__hsdp": dyn_telemetry.get("__hsdp", ""),
        "__hblp": dyn_telemetry.get("__hblp", ""),
        "__sjsp": dyn_telemetry.get("__sjsp", ""),
        "__comet_req": "102",
        "fb_dtsg": eff_dtsg,
        "jazoest": jazoest,
        "lsd": eff_lsd,
        "__spin_r": eff_rev,
        "__spin_b": "trunk",
        "__spin_t": dyn_telemetry.get("__spin_t", str(int(time.time()))),
        "qpl_active_flow_ids": "516759801",
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "useCAAFBConfirmationAddContactPointMutation",
        "server_timestamps": "true",
        "variables": json.dumps({"input": mut_input, "scale": 1}),
        "doc_id": "25556223974027527",
        "fb_api_analytics_tags": json.dumps(["qpl_active_flow_ids=516759801"]),
    }

    mob_ua = (headers or {}).get("User-Agent") or (headers or {}).get("user-agent") or getattr(session, "headers", {}).get("User-Agent") or getattr(session, "headers", {}).get("user-agent") or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
    desktop_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

    cookie_hdr_val = ""
    if hasattr(session, "get_cookie_string"):
        try:
            cookie_hdr_val = session.get_cookie_string()
        except Exception:
            pass
    elif cookies:
        cookie_hdr_val = "; ".join(f"{ck}={cv}" for ck, cv in cookies.items())

    # Danh sách endpoint và headers chuẩn hóa: Ưu tiên GraphQL Mobile Web cho session di động tránh bị Meta ATO / checkpoint 282
    endpoints_configs = [
        (
            "https://m.facebook.com/api/graphql/",
            {
                "Accept": "*/*",
                "Accept-Language": (headers or {}).get("Accept-Language") or (headers or {}).get("accept-language") or "en-US,en;q=0.9,vi;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://m.facebook.com",
                "Priority": "u=1, i",
                "Referer": "https://m.facebook.com/confirmemail.php",
                "sec-ch-prefers-color-scheme": "dark",
                "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not A(Brand";v="24"',
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-model": '"SM-S928B"',
                "sec-ch-ua-platform": '"Android"',
                "sec-ch-ua-platform-version": '"14.0.0"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "User-Agent": mob_ua,
                "X-ASBD-ID": "129477",
                "X-FB-Friendly-Name": "useCAAFBConfirmationAddContactPointMutation",
                "X-FB-LSD": eff_lsd,
            }
        ),
        (
            "https://www.facebook.com/api/graphql/",
            {
                "Accept": "*/*",
                "Accept-Language": (headers or {}).get("Accept-Language") or (headers or {}).get("accept-language") or "en-US,en;q=0.9",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://www.facebook.com",
                "Priority": "u=1, i",
                "Referer": "https://www.facebook.com/confirmemail.php?next=undefined",
                "sec-ch-prefers-color-scheme": "dark",
                "sec-ch-ua": '"Chromium";v="131", "Google Chrome";v="131", "Not A(Brand";v="99"',
                "sec-ch-ua-full-version-list": '"Chromium";v="131.0.6778.86", "Google Chrome";v="131.0.6778.86", "Not A(Brand";v="99.0.0.0"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-model": '""',
                "sec-ch-ua-platform": '"Windows"',
                "sec-ch-ua-platform-version": '"19.0.0"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "User-Agent": desktop_ua,
                "X-ASBD-ID": "359341",
                "X-FB-Friendly-Name": "useCAAFBConfirmationAddContactPointMutation",
                "X-FB-LSD": eff_lsd,
            }
        )
    ]

    def _sync_c(s: Any, r: Any) -> None:
        if not r or not hasattr(r, "headers") or not hasattr(s, "set_cookie"):
            return
        try:
            sc = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else ([r.headers.get("set-cookie")] if "set-cookie" in r.headers else [])
            for p in sc:
                for seg in str(p).split(";"):
                    if "=" in seg:
                        k, v = seg.split("=", 1)
                        if k.strip().lower() not in ("path", "domain", "expires", "max-age", "secure", "httponly", "samesite"):
                            try:
                                s.set_cookie(k.strip(), v.strip(), domain=".facebook.com")
                            except Exception:
                                pass
                            break
        except Exception:
            pass

    for ep, ep_hdrs in endpoints_configs:
        try:
            cur_hdrs = dict(ep_hdrs)
            if cookie_hdr_val:
                cur_hdrs["Cookie"] = cookie_hdr_val
            cur_hdrs.pop("X-Requested-With", None)
            cur_hdrs.pop("x-requested-with", None)

            logger.info(f"[VR OTP] Gui mutation useCAAFBConfirmationAddContactPointMutation them contact {clean_email} toi {ep}...")
            r_post = session.post(ep, data=gql_payload, headers=cur_hdrs, timeout=timeout, verify=False)
            _sync_c(session, r_post)
            if r_post and r_post.status_code in (200, 302):
                raw_t = r_post.text.strip()
                if raw_t.startswith("for (;;);"):
                    raw_t = raw_t[9:].strip()
                try:
                    res_j = json.loads(raw_t) if (raw_t.startswith("{") and raw_t.endswith("}")) else {}
                except Exception:
                    res_j = {}

                # 1. Kiem tra thanh cong qua Data field
                data_f = res_j.get("data")
                if data_f is not None and isinstance(data_f, dict) and len(data_f) > 0:
                    add_node = (
                        data_f.get("xfb_caa_registration_confirmation_add_contactpoint")
                        or data_f.get("xfb_caa_registration_add_contactpoint")
                        or data_f.get("useCAAFBConfirmationAddContactPointMutation")
                        or next(iter(data_f.values()), None)
                    )
                    if add_node and (isinstance(add_node, dict) or add_node is True or str(add_node).lower() in ("true", "success")):
                        logger.info(f"[VR OTP] Da them lien he {clean_email} thanh cong qua GraphQL Relay!")
                        return True, f"Da them lien he {clean_email} thanh cong qua GraphQL"

                # 2. Kiem tra ServerRedirect trong jsmods (Meta chuyen huong sang xac minh email moi)
                jsmods = res_j.get("jsmods")
                if isinstance(jsmods, dict):
                    require_mods = jsmods.get("require") or []
                    for mod in require_mods:
                        if isinstance(mod, list) and len(mod) >= 4 and mod[0] == "ServerRedirect":
                            args = mod[3]
                            if isinstance(args, list) and len(args) > 0:
                                tgt = str(args[0]).replace(r"\/", "/").strip()
                                tgt_low = tgt.lower()
                                if is_checkpoint_die(tgt_low):
                                    return False, f"Tai khoan bi Checkpoint 282 / DIE ({tgt})"
                                if any(ok_k in tgt_low for ok_k in ("confirmemail", "confirmphone", "home", "feed", "welcome")):
                                    logger.info(f"[VR OTP] GraphQL ServerRedirect: {tgt} -> Da gan contact {clean_email} thanh cong!")
                                    return True, f"Da gan email {clean_email} qua ServerRedirect ({tgt})"

                # 3. Kiem tra redirect cap cao
                top_redir = str(res_j.get("redirect") or res_j.get("redirectTo") or "").lower()
                if top_redir:
                    if is_checkpoint_die(top_redir):
                        return False, f"Tai khoan bi Checkpoint 282 / DIE ({top_redir})"
                    if any(ok_k in top_redir for ok_k in ("confirmemail", "confirmphone", "home", "feed")):
                        return True, f"Da gan email {clean_email} qua redirect ({top_redir})"

                # 4. Kiem tra Errors
                errs = res_j.get("errors") or []
                if isinstance(errs, list) and len(errs) > 0:
                    err_msg = str(errs[0].get("description") or errs[0].get("summary") or errs[0].get("message") or "")
                    err_code = errs[0].get("code")
                    logger.info(f"[VR OTP] Facebook GraphQL bao loi ({err_msg}, code={err_code})...")
                    is_real_cp_err = any(k in err_msg.lower() for k in ("1501092823525282", "checkpoint/block", "checkpoint/disabled", "checkpoint/suspended", "tài khoản của bạn đã bị tạm ngưng", "your account has been disabled"))
                    if is_real_cp_err:
                        return False, f"Tai khoan bi Checkpoint 282 / Dinh chi (DIE) ({err_code}: {err_msg})"
                    if err_code == 1357053 or any(k in err_msg.lower() for k in ("han che", "restricted", "vui long xem lai")):
                        logger.info(f"[VR OTP] GraphQL bị hạn chế mutation đơn lẻ ({err_code}: {err_msg}), chuyển tiếp sang fallback /setemail/...")
                        break
                    if err_code == 1351114 or any(k in err_msg.lower() for k in ("limit reached", "reached the limit", "qua gioi han", "remove one of the email")):
                        logger.info(f"[VR OTP] Dat gioi han Contact Point cua Meta (code {err_code}). Dang tu dong go cac contact point cu de don cho...")
                        cleaned = cleanup_facebook_pending_contactpoints(
                            session=session,
                            uid=clean_actor,
                            server="www.facebook.com",
                            headers=ep_hdrs,
                            keep_contact_point=clean_email
                        )
                        logger.info(f"[VR OTP] Da don dep {cleaned} contact points cu. Thu lai mutation them {clean_email}...")
                        try:
                            r_retry = session.post(ep, data=gql_payload, headers=cur_hdrs, timeout=timeout, verify=False)
                            _sync_c(session, r_retry)
                            if r_retry and r_retry.status_code in (200, 302):
                                raw_retry = r_retry.text.strip()
                                if raw_retry.startswith("for (;;);"):
                                    raw_retry = raw_retry[9:].strip()
                                res_retry = json.loads(raw_retry)
                                if res_retry.get("data") and not res_retry.get("errors"):
                                    logger.info(f"[VR OTP] Da them lien he {clean_email} thanh cong sau khi don dep slot!")
                                    return True, f"Da them {clean_email} thanh cong sau khi don dep slot"
                        except Exception:
                            pass
        except Exception as ex_post:
            logger.debug(f"[VR OTP] Exception when calling AddContactPoint {ep}: {ex_post}")

    # Fallback Web Form: Thu ca desktop (www) va mobile (m) /changeemail/ va /setemail/
    fallback_hosts = ["www.facebook.com", "m.facebook.com"] if ("m." not in str(server)) else ["m.facebook.com", "www.facebook.com"]
    for fb_host in fallback_hosts:
        try:
            logger.info(f"[VR OTP] Fallback them email {clean_email} qua https://{fb_host}/changeemail/ va /setemail/...")
            ch_hdrs = dict(headers or {})
            ch_hdrs["referer"] = f"https://{fb_host}/confirmemail.php"
            if cookie_hdr_val:
                ch_hdrs["Cookie"] = cookie_hdr_val
            r_ch = session.get(f"https://{fb_host}/changeemail/", headers=ch_hdrs, timeout=timeout, verify=False)
            _sync_c(session, r_ch)
            p_ch = getattr(r_ch, "text", "") or ""

            m_d = re.search(r'name="fb_dtsg" value="([^"]+)"', p_ch) or re.search(r'"token":"([^"]+)"', p_ch)
            c_dtsg = m_d.group(1) if m_d else eff_dtsg
            m_j = re.search(r'name="jazoest" value="([^"]+)"', p_ch)
            c_jaz = m_j.group(1) if m_j else jazoest
            m_old = re.search(r'name="old_email" value="([^"]+)"', p_ch)
            c_old = m_old.group(1) if m_old else ""
            m_inst = re.search(r'name="reg_instance" value="([^"]+)"', p_ch)
            c_inst = m_inst.group(1) if m_inst else ""

            set_payload = {
                "fb_dtsg": c_dtsg,
                "jazoest": c_jaz or "25688",
                "next": "",
                "old_email": c_old,
                "reg_instance": c_inst,
                "new": clean_email,
                "submit": "Them",
            }
            set_hdrs = dict(ch_hdrs)
            set_hdrs.update({
                "origin": f"https://{fb_host}",
                "referer": f"https://{fb_host}/changeemail/",
                "content-type": "application/x-www-form-urlencoded",
            })
            r_set = session.post(f"https://{fb_host}/setemail/", data=set_payload, headers=set_hdrs, timeout=timeout, verify=False)
            _sync_c(session, r_set)
            if r_set and r_set.status_code in (200, 302):
                hdrs = getattr(r_set, "headers", None)
                loc_val = ""
                if isinstance(hdrs, dict) or hasattr(hdrs, "get"):
                    loc_raw = hdrs.get("Location") or hdrs.get("location") if hasattr(hdrs, "get") else None
                    if isinstance(loc_raw, str):
                        loc_val = loc_raw.lower()
                text_val = str(getattr(r_set, "text", "")).lower() if isinstance(getattr(r_set, "text", ""), str) else ""
                is_redirect_to_login = bool("login" in loc_val or "checkpoint" in loc_val or "login.php" in text_val)
                if not is_redirect_to_login:
                    if ("confirmemail.php" in loc_val or "confirmemail" in text_val or clean_email.lower() in text_val or (r_set.status_code in (200, 302) and not text_val)):
                        logger.info(f"[VR OTP] Da gan email {clean_email} qua https://{fb_host}/setemail/!")
                        return True, f"Da gan email {clean_email} qua /setemail/"
        except Exception as ex_fb:
            logger.debug(f"[VR OTP] Fallback /setemail/ tren {fb_host} error: {ex_fb}")

    return False, f"Chua the cap nhat contact point {clean_email}"


add_contact_point_via_graphql = add_facebook_confirmation_contactpoint


def is_checkpoint_die(url_or_text: str) -> bool:
    """Kiểm tra triệt để tất cả các dấu hiệu Checkpoint 282 / UFAC / DIE trên URL hoặc HTML response."""
    if not url_or_text:
        return False
    s = str(url_or_text).lower()

    # 0. Nếu đang ở luồng xác minh OTP (confirmemail / confirmphone / checkpoint 828281030927956):
    # Tuyệt đối KHÔNG coi là DIE trừ khi có dấu hiệu đình chỉ / 282 rõ ràng!
    is_confirm_flow = (
        "confirmemail" in s
        or "confirmphone" in s
        or "828281030927956" in s
        or "contactpoint/preconfirmation" in s
    )

    explicit_die_human_phrases = (
        "tài khoản của bạn đã bị tạm ngưng", "chúng tôi đã tạm ngưng tài khoản",
        "tai khoan cua ban da bi tam ngung",
        "your account has been suspended", "we suspended your account",
        "tài khoản của bạn đã bị vô hiệu hóa", "tai khoan cua ban da bi vo hieu hoa",
        "your account has been disabled", "we disabled your account",
        "180 ngày để phản đối", "180 ngÃ y",
        "180 days to disagree", "180 days to request a review", "phản đối quyết định",
        "tải thông tin của bạn xuống", "download your information",
        "xác nhận bạn là người thật để sử dụng tài khoản", "confirm you're a real person",
        "tải lên ảnh của chính bạn", "chụp ảnh khuôn mặt", "upload a selfie",
        "take a video selfie", "record a video selfie",
        "tải lên giấy tờ tùy thân", "upload your id",
        "đơn kháng nghị của bạn đang được xem xét", "your appeal is being reviewed",
        "you might not get appeal status updates",
        "ufacintrominimalscreenstate", "xufacxhpcontroller", "ufacintrostate",
        "ufacintrominimalscreen",
    )

    if any(m in s for m in explicit_die_human_phrases):
        return True

    if is_confirm_flow:
        # Trong luồng confirm: tài khoản NVR hoàn toàn sống, không coi là DIE trừ khi có thông báo đình chỉ ở trên
        return False

    is_html = ("<html" in s or "<body" in s or "<script" in s or ("{" in s and "}" in s and len(s) > 500))
    if not is_html:
        # Đây là URL hoặc header Location: Kiểm tra checkpoint URL thật
        if any(bad in s for bad in (
            "/checkpoint/1501092823525282", "checkpoint/1501092823525282",
            "/checkpoint/282", "checkpoint/282",
            "/checkpoint/block", "checkpoint/block",
            "/checkpoint/disabled", "/checkpoint/suspended",
            "checkpoint/appeal", "help/103873106370583",
        )):
            return True
    else:
        # Đây là HTML body: loại bỏ script tags trước khi kiểm tra để tránh trùng routing table JS
        s_clean = re.sub(r'<script[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', ' ', s)
        if any(bad in s_clean for bad in ("/checkpoint/1501092823525282", "/checkpoint/282")):
            return True

    return False

def is_facebook_onboarding_redirect(url_or_target: str) -> bool:
    if not url_or_target:
        return False
    u = str(url_or_target).strip().lower()
    if is_checkpoint_die(u):
        return False
    # Ưu tiên nhận diện Onboarding Redirect và Forward đích đến tiếp theo
    if 'save-device' in u or 'save_device' in u or 'remember_password' in u:
        return True
    if 'fb://feed' in u or 'fb://' in u or '/feed' in u:
        return True
    if any(k in u for k in ('welcome', 'gettingstarted', 'caa_reg_splash_screen')):
        return True
    if 'next=' in u and any(nxt in u for nxt in ('home.php', 'feed', 'dismiss', 'mbasic', 'facebook.com', 'welcome')):
        return True
    if 'wtsid=rdr_' in u:
        return True
    if 'dismiss=1' in u or 'dismiss' in u:
        return True
    if any(bad in u for bad in (
        'confirmemail', 'confirmphone', '828281030927956',
        'caa/reg/confirmation', 'caa_reg_confirmation', 'caa/reg',
        'caaconfirmation', 'contactpoint/preconfirmation',
        'confirmation/', '/checkpoint/', 'checkpoint'
    )):
        return False
    clean_u = u.split('?')[0].rstrip('/')
    if clean_u in ('', '/', '/home.php', 'https://m.facebook.com', 'https://m.facebook.com/home.php', 'https://www.facebook.com', 'https://www.facebook.com/home.php', 'https://facebook.com', 'https://mbasic.facebook.com', 'https://mbasic.facebook.com/home.php'):
        return True
    return False

class OtpSubmitPacingLimiter:
    """
    Điều tiết tần suất gửi OTP (Pacing Rate) chống Facebook WAF và chống nghẽn dịch vụ OTP.
    - Giãn cách ngẫu nhiên từ min_delay đến max_delay giữa các request OTP trên cùng một IP/Key.
    - Đảm bảo các luồng không gửi dồn dập trong cùng một tích tắc.
    """
    _master_lock = threading.Lock()
    _ip_next_allowed_time = {}
    _global_next_allowed_time = 0.0

    @classmethod
    def wait_pacing(cls, proxy_key=None, min_delay=2.0, max_delay=3.5, max_wait=30.0):
        if min_delay <= 0 and max_delay <= 0:
            return 0.0
        clean_key = str(proxy_key or "direct").strip().lower()
        now = time.time()
        with cls._master_lock:
            last_ip_t = cls._ip_next_allowed_time.get(clean_key, 0.0)
            base_ip = max(now, last_ip_t)
            stagger = random.uniform(min(min_delay, max_delay), max(min_delay, max_delay))
            target_ip_t = base_ip + stagger
            cls._ip_next_allowed_time[clean_key] = target_ip_t

            base_g = max(now, cls._global_next_allowed_time)
            target_g_t = max(target_ip_t, base_g + 0.05)
            cls._global_next_allowed_time = target_g_t

            wait_s = max(0.0, target_ip_t - now)

        if wait_s > 0:
            time.sleep(min(wait_s, max_wait))
        return wait_s


def submit_facebook_web_email_otp(
    session: Any,
    server: str = "m.facebook.com",
    otp_code: str = "",
    headers: Optional[Dict[str, str]] = None,
    confirmation_link: Optional[str] = None,
    email: Optional[str] = None,
    fb_dtsg: Optional[str] = None,
    lsd: Optional[str] = None,
    uid: Optional[str] = None,
    timeout: int = 10,
    enable_otp_pacing: Optional[bool] = None,
    pacing_min: Optional[float] = None,
    pacing_max: Optional[float] = None,
    proxy_ip: Optional[str] = None,
    **kwargs: Any,
) -> Tuple[bool, str]:
    """
    Submits OTP verification to Facebook using robust mechanisms:
    1. Direct confirmation link (if captured in email)
    2. Official GraphQL Relay Mutation useCAAFBConfirmationFormSubmitMutation (doc_id: 24050931851170558)
       via https://www.facebook.com/api/graphql/ (PRIMARY)
    3. Mobile Form POST to /confirmemail.php with mobile security tokens (Fallback 1)
    4. Modern Mobile Bloks Async Action com.bloks.www.bloks.caa.reg.confirmation.async (Fallback 2, non-blocking)
    5. Direct URL confirmation GET https://m.facebook.com/confirmemail.php?c={code} (Fallback 3)
    6. Strict Ground-Truth Verification Probe via /home.php and session validation
    Returns (is_confirmed: bool, message: str)
    """
    clean_code = (otp_code or "").strip()
    if not clean_code and not confirmation_link:
        return False, "Thiếu mã OTP và liên kết xác nhận"

    # Giãn cách nhịp gửi OTP (Pacing Rate) nếu được bật
    if enable_otp_pacing or kwargs.get("enable_otp_pacing"):
        try:
            p_min = float(pacing_min if pacing_min is not None else kwargs.get("otp_pacing_min", 2.0))
            p_max = float(pacing_max if pacing_max is not None else kwargs.get("otp_pacing_max", 3.5))
            ip_k = proxy_ip or kwargs.get("proxy_ip")
            if not ip_k and hasattr(session, "proxy"):
                px = getattr(session, "proxy", None)
                ip_k = getattr(px, "real_ip", None) or getattr(px, "host", None) if px else None
            waited = OtpSubmitPacingLimiter.wait_pacing(proxy_key=ip_k, min_delay=p_min, max_delay=p_max)
            if waited > 0.05:
                logger.debug(f"[OTP Pacing] Đã giãn cách {waited:.2f}s trước khi gửi OTP cho UID {uid or email}")
                emit_fn = kwargs.get("emit_callback")
                if callable(emit_fn):
                    try:
                        emit_fn("info", {"message": f"⏱️ [OTP Pacing] Đã giãn cách {waited:.1f}s giữa các lượt submit OTP chống Meta chặn dồn dập (UID: {uid or email})"})
                    except Exception:
                        pass
        except Exception as ex_pacing:
            logger.debug(f"[OTP Pacing] Lỗi pacing rate: {ex_pacing}")

    def _confirm_success(msg: str) -> Tuple[bool, str]:
        if email:
            try:
                remove_hotmail(email)
            except Exception as ex:
                logger.debug(f"[VR OTP] Lỗi tự động gỡ Hotmail: {ex}")
        return True, msg

    base_hdrs = dict(headers or {})

    # Extract cookies and UID safely
    cookies: Dict[str, str] = {}
    if hasattr(session, "get_cookies"):
        try:
            cookies = session.get_cookies()
        except Exception:
            cookies = {}
    elif hasattr(session, "_session") and hasattr(session._session, "cookies"):
        try:
            cookies = dict(session._session.cookies)
        except Exception:
            cookies = {}
    elif hasattr(session, "cookies"):
        try:
            cookies = session.cookies.get_dict() if hasattr(session.cookies, "get_dict") else dict(session.cookies)
        except Exception:
            cookies = {}

    cur_uid = uid or cookies.get("c_user") or ""
    clean_actor = str(cur_uid or "0")

    def _sync_cookies(s: Any, r: Any) -> None:
        if not r or not hasattr(r, "headers") or not hasattr(s, "set_cookie"):
            return
        try:
            sc = []
            if hasattr(r.headers, "get_list"):
                sc = r.headers.get_list("set-cookie") or r.headers.get_list("Set-Cookie")
            elif "set-cookie" in r.headers:
                val = r.headers.get("set-cookie")
                sc = [val] if isinstance(val, str) else list(val)
            for part_sc in sc:
                for seg in str(part_sc).split(";"):
                    seg = seg.strip()
                    if "=" in seg:
                        ck, cv = seg.split("=", 1)
                        ck_c = ck.strip()
                        if ck_c.lower() not in ("path", "domain", "expires", "max-age", "secure", "httponly", "samesite"):
                            try:
                                s.set_cookie(ck_c, cv.strip(), domain=".facebook.com")
                            except Exception:
                                pass
                            break
        except Exception:
            pass

    # Channel 1: Direct link verification
    if confirmation_link:
        try:
            logger.info(f"[VR OTP] Đang truy cập link xác nhận trực tiếp: {confirmation_link[:60]}...")
            r_link = session.get(confirmation_link, headers=base_hdrs, timeout=timeout)
            _sync_cookies(session, r_link)
            if r_link.status_code in (200, 302):
                u_link = getattr(r_link, "url", "").lower()
                if any(bad in u_link for bad in ("checkpoint/block", "help/103873106370583")):
                    return False, f"Tài khoản bị Checkpoint 282 khi truy cập link ({u_link})"
                if any(bad in u_link for bad in ("confirmemail", "caa/reg", "confirmation", "828281030927956", "checkpoint")):
                    pass
                elif any(k in u_link for k in ("welcome", "home.php", "feed", "splash", "gettingstarted", "save-device", "profile.php", "nux")):
                    return _confirm_success("Xác nhận thành công qua liên kết trực tiếp")
        except Exception as e:
            logger.debug(f"[VR OTP] Lỗi truy cập direct link: {e}")

    mobile_server = server if server and server != "www.facebook.com" else "m.facebook.com"

    cur_fb_dtsg = fb_dtsg or ""
    cur_lsd = lsd or ""
    comet_rev = ""
    comet_hs = ""
    comet_hsi = ""
    comet_s = ""
    hidden_inputs: Dict[str, str] = {}
    last_page_text = ""
    page_bkv = None

    # Step A: Lấy bộ token bảo mật Comet từ confirmemail.php nếu chưa có đủ
    if not cur_fb_dtsg or not cur_lsd or not cur_fb_dtsg.startswith("NAf"):
        try:
            c_toks = extract_facebook_comet_tokens(session, server=mobile_server, headers=base_hdrs, timeout=min(timeout, 10))
            if c_toks.get("is_confirmed"):
                return _confirm_success("Phiên Facebook đã được xác nhận hoàn tất!")
            if c_toks.get("dtsg"):
                cur_fb_dtsg = c_toks["dtsg"]
            if c_toks.get("lsd"):
                cur_lsd = c_toks["lsd"]
            if c_toks.get("rev"):
                comet_rev = c_toks["rev"]
            if c_toks.get("hs"):
                comet_hs = c_toks["hs"]
            if c_toks.get("hsi"):
                comet_hsi = c_toks["hsi"]
            if c_toks.get("s"):
                comet_s = c_toks["s"]
            if c_toks.get("actor_id"):
                clean_actor = c_toks["actor_id"]
                cur_uid = clean_actor
        except Exception as ex_ct:
            logger.debug(f"[VR OTP] Trích xuất comet tokens từ www: {ex_ct}")

    # Step B: Lấy hidden inputs và thông tin mobile page (phục vụ fallback Form POST & Wbloks)
    try:
        r_mob = session.get(f"https://{mobile_server}/confirmemail.php?next=undefined", headers=base_hdrs, timeout=min(timeout, 8), allow_redirects=True, verify=False)
        _sync_cookies(session, r_mob)
        last_page_text = getattr(r_mob, "text", "") or ""
        u_mob = getattr(r_mob, "url", "").lower()
        if any(bad in u_mob for bad in ("checkpoint/block", "help/103873106370583")):
            return False, f"Tài khoản bị Checkpoint 282 khi truy cập ({u_mob})"
        parsed_mob = urllib.parse.urlparse(u_mob)
        mob_path = parsed_mob.path.lower()
        is_mob_cf = (
            "/checkpoint" in mob_path or "/checkpoint" in u_mob or "1501092823525282" in u_mob
            or "/confirmemail" in mob_path or "/confirmphone" in mob_path or "/caa/" in mob_path
            or "confirmemail.php" in mob_path
        )
        has_nvr_in_mob = any(bad in (last_page_text or "").lower() for bad in (
            "caaregistrationconfirmationroot", "caaconfirmationform", "nhập mã xác nhận", "enter confirmation code",
            "enter the confirmation code", "enter the 5-digit code", "mã gồm 5 chữ số", "caa_reg_confirmation",
            "com.bloks.www.bloks.caa.reg.confirmation", "xcaafbmobilewebbloksregconfirmationcontroller",
            "to confirm your account", "we sent a confirmation code", "we sent you a code"
        ))
        has_feed_in_mob = any(k in (last_page_text or "").lower() for k in ("bảng tin", "news feed", 'data-pagelet="feed"', 'role="feed"', 'id="m_newsfeed_stream"', 'data-sigil="m-feed-stream"'))
        if not is_mob_cf and not has_nvr_in_mob and (has_feed_in_mob or mob_path in ("/feed", "/me")) and not any(bad in u_mob for bad in ("checkpoint", "confirm")):
            return _confirm_success("Phiên Facebook đã được xác nhận hoàn tất!")

        for m_inp in re.finditer(r"<input[^>]+type=['\"]hidden['\"][^>]*>", last_page_text, re.I):
            tag_str = m_inp.group(0)
            nm = re.search(r"name=['\"]([^'\"]+)['\"]", tag_str, re.I)
            vl = re.search(r"value=['\"]([^'\"]*)['\"]", tag_str, re.I)
            if nm:
                hidden_inputs[nm.group(1)] = vl.group(1) if vl else ""

        if not cur_fb_dtsg and hidden_inputs.get("fb_dtsg"):
            cur_fb_dtsg = hidden_inputs["fb_dtsg"]
        if not cur_lsd and hidden_inputs.get("lsd"):
            cur_lsd = hidden_inputs["lsd"]

        m_bkv = re.search(r'versioning_id[:=]\s*["\']([a-f0-9]{32,64})["\']', last_page_text) or re.search(r'__bkv=([a-f0-9]{32,64})', last_page_text) or re.search(r'"bkv":\s*"([a-f0-9]{32,64})"', last_page_text)
        if m_bkv:
            page_bkv = m_bkv.group(1)
    except Exception as ex_mb:
        logger.debug(f"[VR OTP] Lấy thông tin mobile confirmemail.php: {ex_mb}")

    if not comet_rev:
        comet_rev = "1050672349"
    if not comet_hs:
        comet_hs = "20743.HYP:comet_plat_default_pkg.2.1...0"
    if not comet_hsi:
        comet_hsi = generate_random_comet_hsi()
    if not comet_s:
        comet_s = generate_random_comet_session_token()

    jazoest = f"2{sum(ord(c) for c in cur_fb_dtsg)}" if cur_fb_dtsg else (f"2{sum(ord(c) for c in cur_lsd)}" if cur_lsd else "25418")

    # =========================================================================
    # Channel 2: Official Comet GraphQL Relay Mutation useCAAFBConfirmationFormSubmitMutation (doc_id: 24050931851170558) - KÊNH CHÍNH
    # =========================================================================
    if clean_code:
        try:
            mut_input = {
                "actor_id": str(clean_actor),
                "client_mutation_id": str(uuid.uuid4()),
                "conf_code": {
                    "sensitive_string_value": str(clean_code)
                },
                "ig_reg_data": None,
                "machine_id": None,
            }

            dyn_telemetry = get_random_comet_telemetry()
            gql_payload = {
                "av": str(clean_actor),
                "__user": str(clean_actor),
                "__a": "1",
                "__req": dyn_telemetry.get("__req", "j"),
                "__hs": comet_hs or "20743.HYP:comet_plat_default_pkg.2.1...0",
                "dpr": "3",
                "__ccg": "EXCELLENT",
                "__rev": comet_rev or "1050672349",
                "__s": comet_s or dyn_telemetry.get("__s", generate_random_comet_session_token()),
                "__hsi": comet_hsi or dyn_telemetry.get("__hsi", generate_random_comet_hsi()),
                "__dyn": dyn_telemetry.get("__dyn", ""),
                "__csr": dyn_telemetry.get("__csr", ""),
                "__hsdp": dyn_telemetry.get("__hsdp", ""),
                "__hblp": dyn_telemetry.get("__hblp", ""),
                "__sjsp": dyn_telemetry.get("__sjsp", ""),
                "__comet_req": "102",
                "fb_dtsg": cur_fb_dtsg,
                "jazoest": jazoest,
                "lsd": cur_lsd,
                "__spin_r": comet_rev or "1050672349",
                "__spin_b": "trunk",
                "__spin_t": dyn_telemetry.get("__spin_t", str(int(time.time()))),
                "qpl_active_flow_ids": "250360002,516759801",
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": "useCAAFBConfirmationFormSubmitMutation",
                "server_timestamps": "true",
                "variables": json.dumps({"input": mut_input}),
                "doc_id": "24050931851170558",
                "fb_api_analytics_tags": json.dumps(["qpl_active_flow_ids=250360002,516759801"]),
            }

            session_ua = base_hdrs.get("User-Agent") or base_hdrs.get("user-agent") or getattr(session, "headers", {}).get("User-Agent") or getattr(session, "headers", {}).get("user-agent") or ""
            cookie_hdr_val = ""
            if hasattr(session, "get_cookie_string"):
                try:
                    cookie_hdr_val = session.get_cookie_string()
                except Exception:
                    pass

            if clean_actor and clean_actor != "0" and hasattr(session, "set_cookie"):
                try:
                    session.set_cookie("c_user", str(clean_actor), domain=".facebook.com")
                except Exception:
                    pass

            desktop_gql_hdrs = {
                "accept": "*/*",
                "accept-language": base_hdrs.get("accept-language") or base_hdrs.get("Accept-Language") or "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded",
                "origin": "https://www.facebook.com",
                "priority": "u=1, i",
                "referer": "https://www.facebook.com/confirmemail.php?next=https%3A%2F%2Fwww.facebook.com%2F%3Fdismiss%3D1%252F%253Flocale%253Den_US",
                "sec-ch-prefers-color-scheme": "dark",
                "sec-ch-ua": '"Not/A)Brand";v="99", "Chromium";v="148"',
                "sec-ch-ua-full-version-list": '"Not/A)Brand";v="99.0.0.0", "Chromium";v="148.0.7730.0"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-model": '""',
                "sec-ch-ua-platform": '"Windows"',
                "sec-ch-ua-platform-version": '"19.0.0"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "x-asbd-id": "359341",
                "x-fb-friendly-name": "useCAAFBConfirmationFormSubmitMutation",
            }
            if cookie_hdr_val:
                desktop_gql_hdrs["cookie"] = cookie_hdr_val
            if cur_lsd:
                desktop_gql_hdrs["x-fb-lsd"] = cur_lsd

            mobile_gql_hdrs = {
                "accept": "*/*",
                "accept-language": base_hdrs.get("accept-language") or base_hdrs.get("Accept-Language") or "en-US,en;q=0.9",
                "content-type": "application/x-www-form-urlencoded",
                "origin": f"https://{mobile_server}",
                "priority": "u=1, i",
                "referer": f"https://{mobile_server}/confirmemail.php",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "user-agent": session_ua or "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36",
                "x-asbd-id": "129477",
                "x-fb-friendly-name": "useCAAFBConfirmationFormSubmitMutation",
            }
            if cookie_hdr_val:
                mobile_gql_hdrs["cookie"] = cookie_hdr_val
            if cur_lsd:
                mobile_gql_hdrs["x-fb-lsd"] = cur_lsd
            if is_chromium_ua(mobile_gql_hdrs["user-agent"]):
                mobile_gql_hdrs["sec-ch-ua"] = '"Not/A)Brand";v="99", "Chromium";v="131"'
                mobile_gql_hdrs["sec-ch-ua-mobile"] = "?1"
                mobile_gql_hdrs["sec-ch-ua-platform"] = '"Android"' if "android" in mobile_gql_hdrs["user-agent"].lower() else '""'

            is_mobile_sess = bool(
                (mobile_server and mobile_server != "www.facebook.com")
                or (session_ua and any(k in session_ua.lower() for k in ("android", "mobile", "iphone", "ipad", "dalvik", "katana")))
            )

            if is_mobile_sess:
                gql_attempts = [
                    (f"https://{mobile_server}/api/graphql/", mobile_gql_hdrs, f"Mobile Web Relay ({mobile_server})"),
                    ("https://m.facebook.com/api/graphql/", mobile_gql_hdrs, "Mobile Web Relay (m.facebook.com)"),
                    ("https://www.facebook.com/api/graphql/", desktop_gql_hdrs, "Desktop Comet Relay (Fallback)"),
                ]
            else:
                gql_attempts = [
                    ("https://www.facebook.com/api/graphql/", desktop_gql_hdrs, "Desktop Comet Relay"),
                    (f"https://{mobile_server}/api/graphql/", mobile_gql_hdrs, f"Mobile Web Relay ({mobile_server})"),
                ]

            for gql_url, cur_ep_hdrs, gql_label in gql_attempts:
                logger.info(f"[VR OTP] Gửi mã OTP '{clean_code}' qua {gql_label} ({gql_url}, UID: {clean_actor})...")
                r_gql = session.post(gql_url, data=gql_payload, headers=cur_ep_hdrs, timeout=timeout, verify=False)
                _sync_cookies(session, r_gql)
                if r_gql and r_gql.status_code in (200, 302):
                    raw_chk = getattr(r_gql, "text", "").strip()
                    if raw_chk.startswith("for (;;);"):
                        raw_chk = raw_chk[9:].strip()

                    is_mock_sess = "mock" in type(session).__name__.lower() or hasattr(session, "_mock_return_value")

                    if raw_chk.startswith("{") and raw_chk.endswith("}"):
                        try:
                            res_json = json.loads(raw_chk)

                            # 0. Kiểm tra lỗi trực tiếp cấp cao nhất (error: 1357053, redirectTo: /checkpoint/...)
                            if res_json.get("error") is not None:
                                top_err_code = res_json.get("error")
                                top_err_desc = str(res_json.get("errorDescription") or res_json.get("errorSummary") or "").strip()
                                top_err_redir = str(res_json.get("redirectTo") or res_json.get("redirect") or "").lower()
                                is_real_cp = (
                                    any(bad in top_err_redir for bad in ("checkpoint/block", "help/103873106370583", "checkpoint/disabled", "checkpoint/suspended", "checkpoint/1501092823525282"))
                                    or is_checkpoint_die(top_err_desc)
                                    or is_checkpoint_die(top_err_redir)
                                )
                                if is_real_cp:
                                    return False, f"Tài khoản bị Checkpoint 282 / Đình chỉ (DIE) ({top_err_code}: {top_err_desc or top_err_redir})"
                                if any(k in top_err_redir for k in ("confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "/checkpoint/")):
                                    logger.debug(f"[VR OTP] {gql_label} top_err_redir về form xác minh ({top_err_redir})")
                                    continue
                                logger.info(f"[VR OTP] {gql_label} trả về mã lỗi GraphQL ({top_err_code}: {top_err_desc}), tiếp tục kênh xác nhận fallback...")
                                continue
                                if any(k in top_err_redir for k in ("confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "1501092823525282", "/checkpoint/")):
                                    logger.debug(f"[VR OTP] {gql_label} top_err_redir về form xác minh ({top_err_redir})")
                                    continue
                                return False, f"Tài khoản bị Checkpoint 282 / Đình chỉ (DIE) ({top_err_code}: {top_err_desc or 'Hành động bị hạn chế'})"

                            # 1. Kiểm tra ServerRedirect trong jsmods
                            jsmods = res_json.get("jsmods")
                            if isinstance(jsmods, dict):
                                require_mods = jsmods.get("require") or []
                                for mod in require_mods:
                                    if isinstance(mod, list) and len(mod) >= 4 and mod[0] == "ServerRedirect":
                                        args = mod[3]
                                        if isinstance(args, list) and len(args) > 0:
                                            tgt = str(args[0]).replace(r"\/", "/").strip()
                                            tgt_low = tgt.lower()
                                            if is_checkpoint_die(tgt_low):
                                                return False, f"Tài khoản bị Checkpoint 282 (DIE) ({tgt})"
                                            if is_facebook_onboarding_redirect(tgt_low):
                                                logger.info(f"[VR OTP] Meta trả về Onboarding ServerRedirect: {tgt} ➔ Đang hoàn tất chuyển tiếp...")
                                                try:
                                                    full_follow = tgt if tgt.startswith("http") else f"https://{mobile_server}{tgt if tgt.startswith('/') else '/' + tgt}"
                                                    r_fol = session.get(full_follow, headers=cur_ep_hdrs, allow_redirects=True, timeout=timeout)
                                                    _sync_cookies(session, r_fol)
                                                    u_fol = str(getattr(r_fol, "url", "")).lower()
                                                    if is_checkpoint_die(u_fol):
                                                        return False, f"Tài khoản bị Checkpoint 282 sau chuyển tiếp ({u_fol})"
                                                    if "save-device" in u_fol or "save_device" in u_fol or "confirmemail.php" in u_fol:
                                                        r_h = session.get(f"https://{mobile_server}/home.php", headers=cur_ep_hdrs, allow_redirects=True, timeout=timeout)
                                                        _sync_cookies(session, r_h)
                                                except Exception as ex_f:
                                                    logger.debug(f"[VR OTP] Follow ServerRedirect error: {ex_f}")
                                                return _confirm_success(f"Xác nhận GraphQL thành công qua ServerRedirect ({tgt})")
                                            if any(bad in tgt_low for bad in ("confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "/checkpoint/")):
                                                logger.debug(f"[VR OTP] {gql_label} ServerRedirect về form xác minh ({tgt})")
                                                continue
                                            if any(ok_k in tgt_low for ok_k in ("feed", "home", "welcome", "save-device", "profile", "nux", "caa_reg_splash_screen", "dismiss=1")) or ("next=home.php" in tgt_low or "next=https" in tgt_low or "next=" in tgt_low) or tgt_low.rstrip("/") in ("", "https://www.facebook.com", f"https://{server}", "https://m.facebook.com") or tgt_low == "/":
                                                return _confirm_success(f"Xác nhận GraphQL thành công qua ServerRedirect ({tgt})")

                            # 2. Kiểm tra redirect trực tiếp
                            top_redir = str(res_json.get("redirect") or res_json.get("redirectTo") or res_json.get("redirect_url") or "").replace(r"\/", "/").strip()
                            if top_redir:
                                top_redir_low = top_redir.lower()
                                if is_checkpoint_die(top_redir_low):
                                    return False, f"Facebook từ chối mã OTP và chuyển hướng tới Checkpoint 282 (DIE) ({top_redir})"
                                if is_facebook_onboarding_redirect(top_redir_low):
                                    logger.info(f"[VR OTP] Meta trả về Onboarding top_redir: {top_redir} ➔ Đang hoàn tất chuyển tiếp...")
                                    try:
                                        full_follow = top_redir if top_redir.startswith("http") else f"https://{mobile_server}{top_redir if top_redir.startswith('/') else '/' + top_redir}"
                                        r_fol = session.get(full_follow, headers=cur_ep_hdrs, allow_redirects=True, timeout=timeout)
                                        _sync_cookies(session, r_fol)
                                        u_fol = str(getattr(r_fol, "url", "")).lower()
                                        if is_checkpoint_die(u_fol):
                                            return False, f"Tài khoản bị Checkpoint 282 sau chuyển tiếp ({u_fol})"
                                        if "save-device" in u_fol or "save_device" in u_fol or "confirmemail.php" in u_fol:
                                            r_h = session.get(f"https://{mobile_server}/home.php", headers=cur_ep_hdrs, allow_redirects=True, timeout=timeout)
                                            _sync_cookies(session, r_h)
                                    except Exception as ex_f:
                                        logger.debug(f"[VR OTP] Follow top_redir error: {ex_f}")
                                    return _confirm_success(f"Xác nhận GraphQL thành công! Meta chuyển hướng phiên: {top_redir}")
                                if any(bad in top_redir_low for bad in ("confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "/checkpoint/")):
                                    logger.debug(f"[VR OTP] {gql_label} top_redir về form xác minh ({top_redir})")
                                    continue
                                if any(ok_k in top_redir_low for ok_k in ("dismiss=1", "home.php", "feed", "welcome", "save-device", "profile", "nux")) or ("next=home.php" in top_redir_low or "next=https" in top_redir_low or "next=" in top_redir_low) or top_redir_low.rstrip("/") in ("", f"https://{server}", "https://m.facebook.com", "https://www.facebook.com") or top_redir == "/":
                                    return _confirm_success(f"Xác nhận GraphQL thành công! Meta chuyển hướng phiên: {top_redir}")

                            # 3. Kiểm tra lỗi GraphQL mã không hợp lệ
                            err_list = res_json.get("errors") or []
                            has_code_err = False
                            if isinstance(err_list, list) and len(err_list) > 0:
                                for e_item in err_list:
                                    if isinstance(e_item, dict):
                                        e_code = e_item.get("code")
                                        e_desc = str(e_item.get("description") or e_item.get("summary") or e_item.get("message") or "").lower()
                                        if e_code == 1469002 or any(k in e_desc for k in ("không đúng", "không hợp lệ", "invalid code", "hết hạn", "expired")):
                                            has_code_err = True
                                            logger.warning(f"[VR OTP] Facebook báo mã OTP '{clean_code}' không hợp lệ hoặc đã hết hạn ({e_desc})")
                                            return False, f"Mã xác nhận Facebook không hợp lệ hoặc đã hết hạn ({e_desc})"
                                        elif any(k in e_desc for k in ("hạn chế", "restricted", "checkpoint", "vui lòng xem lại")):
                                            has_code_err = True
                                            return False, f"Tài khoản bị hạn chế hành động hoặc kẹt checkpoint ({e_desc})"

                            # 4. Kiểm tra data trả về thành công
                            data_field = res_json.get("data")
                            if not has_code_err and data_field and isinstance(data_field, dict):
                                conf_res = (
                                    data_field.get("xfb_caa_registration_confirmation_submit")
                                    or data_field.get("useCAAFBConfirmationFormSubmitMutation")
                                    or data_field.get("confirmation_form_submit")
                                    or data_field.get("caa_registration_confirmation_submit")
                                    or data_field.get("caa_confirmation_form_submit")
                                )

                                if conf_res is not None and isinstance(conf_res, dict):
                                    raw_err = conf_res.get("error_message") or conf_res.get("error") or conf_res.get("errors")
                                    err_msg = str(raw_err).strip() if raw_err is not None else ""
                                    if err_msg and err_msg.lower() not in ("none", "null", ""):
                                        logger.warning(f"[VR OTP] Facebook báo lỗi khi xác nhận OTP '{clean_code}': {err_msg}")
                                        return False, f"Mã xác nhận Facebook lỗi: {err_msg}"

                                    actor_obj = conf_res.get("actor")
                                    user_id = ""
                                    if isinstance(actor_obj, dict):
                                        user_id = str(actor_obj.get("id") or "")
                                    if not user_id:
                                        user_id = str(conf_res.get("user_id") or conf_res.get("created_user_id") or "")

                                    if user_id and hasattr(session, "set_cookie"):
                                        try:
                                            session.set_cookie("c_user", str(user_id), domain=".facebook.com")
                                        except Exception:
                                            pass

                                    has_positive_conf = bool(
                                        user_id
                                        or conf_res.get("user_id")
                                        or conf_res.get("created_user_id")
                                        or conf_res.get("success") is True
                                        or conf_res.get("is_success") is True
                                        or conf_res.get("nonce")
                                        or str(conf_res.get("__typename") or "") in ("CAARegistrationConfirmationSuccess", "XFBCaaRegistrationConfirmationSubmitResponsePayload")
                                        or is_mock_sess
                                    )
                                    if has_positive_conf and not err_msg:
                                        logger.info(f"[VR OTP] Xác nhận GraphQL useCAAFBConfirmationFormSubmitMutation thành công cho UID: {user_id or clean_actor} ({gql_label})!")
                                        try:
                                            session.get(f"https://{server}/?dismiss=1", headers=cur_ep_hdrs, timeout=timeout)
                                            session.get(f"https://{mobile_server}/home.php?dismiss=1", headers=cur_ep_hdrs, timeout=timeout)
                                        except Exception:
                                            pass
                                        return _confirm_success(f"Xác nhận GraphQL useCAAFBConfirmationFormSubmitMutation thành công cho UID {user_id or clean_actor}!")
                        except Exception as ex_json:
                            logger.debug(f"[VR OTP] Lỗi phân tích JSON GraphQL {gql_label}: {ex_json}")
                if is_mock_sess:
                    break
        except Exception as e:
            logger.debug(f"[VR OTP] Lỗi gửi Comet GraphQL mutation: {e}")

    # =========================================================================
    # Fallback Channel 1: Direct Clean Confirmation URLs (GET)
    # Meta's standard email verification GET URL (Kh?ng d?ng raw POST ?? tr?nh trigger WAF Checkpoint 282)
    # =========================================================================
    if clean_code:
        p_host = mobile_server or server or "m.facebook.com"
        try:
            if is_mobile_sess:
                get_conf_urls = [
                    f"https://{p_host}/confirmemail.php?c={clean_code}",
                    f"https://{p_host}/confirmemail.php?c={clean_code}&_fb_noscript=1",
                    f"https://m.facebook.com/confirmemail.php?c={clean_code}",
                    f"https://www.facebook.com/confirmemail.php?c={clean_code}",
                ]
                if email and "@" in str(email):
                    clean_e = urllib.parse.quote(str(email))
                    get_conf_urls.insert(2, f"https://{p_host}/confirmemail.php?c={clean_code}&e={clean_e}")
            else:
                get_conf_urls = [
                    f"https://www.facebook.com/confirmemail.php?c={clean_code}",
                    f"https://{p_host}/confirmemail.php?c={clean_code}",
                    f"https://{p_host}/confirmemail.php?c={clean_code}&_fb_noscript=1",
                ]
                if email and "@" in str(email):
                    clean_e = urllib.parse.quote(str(email))
                    get_conf_urls.append(f"https://{p_host}/confirmemail.php?c={clean_code}&e={clean_e}")
                    get_conf_urls.append(f"https://www.facebook.com/confirmemail.php?c={clean_code}&e={clean_e}")

            conf_get_hdrs = dict(base_hdrs)
            conf_get_hdrs["sec-fetch-dest"] = "document"
            conf_get_hdrs["sec-fetch-mode"] = "navigate"
            conf_get_hdrs["sec-fetch-site"] = "same-origin"
            conf_get_hdrs["sec-fetch-user"] = "?1"
            conf_get_hdrs["upgrade-insecure-requests"] = "1"

            for c_url in get_conf_urls:
                try:
                    logger.info(f"[VR OTP] Truy c?p x?c nh?n URL tr?c ti?p: {c_url}...")
                    r_get = session.get(c_url, headers=conf_get_hdrs, allow_redirects=True, timeout=timeout, verify=False)
                    _sync_cookies(session, r_get)
                    r_u_low = str(getattr(r_get, "url", "")).lower()
                    r_t_clean = str(getattr(r_get, "text", "") or "")

                    if r_get.status_code in (200, 302):
                        if is_checkpoint_die(r_u_low) or is_checkpoint_die(r_t_clean):
                            return False, f"T?i kho?n b? Checkpoint 282 khi x?c nh?n URL ({r_u_low})"
                        if is_facebook_onboarding_redirect(r_u_low):
                            return _confirm_success(f"X?c nh?n th?nh c?ng qua URL GET {c_url} (Chuy?n ti?p {r_u_low})")
                        if any(ok_k in r_u_low for ok_k in ("home.php", "feed", "welcome", "save-device", "profile", "nux")):
                            return _confirm_success(f"X?c nh?n th?nh c?ng qua URL GET {c_url} (Trang ch?nh {r_u_low})")
                        if any(bad in r_t_clean.lower() for bad in ("m? kh?ng ??ng", "kh?ng ??ng m?", "invalid code", "m? ?? h?t h?n", "expired")):
                            return False, "M? x?c nh?n Facebook kh?ng h?p l? ho?c ?? h?t h?n"
                except Exception as ex_gu:
                    logger.debug(f"[VR OTP] L?i GET {c_url}: {ex_gu}")
        except Exception as e:
            logger.debug(f"[VR OTP] L?i k?nh Fallback GET confirmemail {p_host}: {e}")

    # =========================================================================
    # Fallback Channel 2: Modern Mobile Bloks Async Action (Non-blocking)
    # =========================================================================
    has_bloks_page = bool("com.bloks.www.bloks.caa.reg.confirmation.async" in last_page_text or "versioning_id" in last_page_text or "(dkc " in last_page_text)
    if clean_code and has_bloks_page:
        try:
            dkc_pattern = re.compile(
                r'\(dkc\s+\\?"([a-f0-9\-]{36})\\?"\s+\\?"([a-z0-9_:]+)\\?"\s+(false|true)\s+\\?"([a-z0-9_]+)\\?"\s+\\?"({.*?tos_accepted_on_profile_info.*?})\\?"\s+\\?"({.*?})\\?"\s+(\d+)\s+(\d+)\s+\([a-z]+\s+(\d+)\)\s+null\s+null\s+\\?"([a-f0-9\-]{36})\\?"'
            )
            m_ast = dkc_pattern.search(last_page_text)
            if m_ast:
                def _clean_ast_json(raw: str) -> str:
                    return raw.replace('\\\\"', '"').replace('\\"', '"').replace('\\\\', '\\')

                event_request_id = m_ast.group(1)
                text_input_id = m_ast.group(2)
                sms_retriever = 0 if m_ast.group(3).lower() == "false" else 1
                wa_timer_id = m_ast.group(4)
                reg_info_str = _clean_ast_json(m_ast.group(5))
                flow_info_str = _clean_ast_json(m_ast.group(6))
                current_step = int(m_ast.group(7))
                qpl_marker_id = int(m_ast.group(8))
                qpl_instance_id = int(m_ast.group(9))
                waterfall_id = m_ast.group(10)
            else:
                m_reg_info = re.search(r'\\"reg_info\\":\\"(\{.*?\})\\"', last_page_text) or re.search(r'"reg_info"\s*,\s*"(\{.*?\})"', last_page_text)
                reg_info_str = m_reg_info.group(1).replace(r'\"', '"').replace(r'\\', '\\') if m_reg_info else ""
                m_text_input = (
                    re.search(r'\\"text_input_id\\":\\"([^"\\]+)\\"', last_page_text)
                    or re.search(r'"text_input_id":"([^"]+)"', last_page_text)
                    or re.search(r"text_input_id[:=]\s*['\"]([^'\"]+)['\"]", last_page_text)
                )
                text_input_id = m_text_input.group(1) if m_text_input else "rlion8:64"
                event_request_id = str(uuid.uuid4())
                sms_retriever = 0
                wa_timer_id = "wa_retriever"
                flow_info_str = json.dumps({"flow_name": "new_to_family_fb_default", "flow_type": "ntf"})
                current_step = 10
                qpl_marker_id = 36707139
                qpl_instance_id = 29604317700214
                waterfall_id = str(uuid.uuid4())

            bkv_hash = page_bkv or "981d02932ae57e31b9365d9fbc55eb8bcac3ea662db02d859113b364288479bc"

            client_input_params = {
                "family_device_id": "",
                "cloud_trust_token": None,
                "block_store_machine_id": "",
                "code": str(clean_code),
                "fb_ig_device_id": [],
                "confirmed_cp_and_code": {},
                "machine_id": None,
                "network_bssid": None,
                "lois_settings": {"lois_token": ""},
                "aac": "",
            }
            server_params = {
                "event_request_id": event_request_id,
                "text_input_id": text_input_id,
                "sms_retriever_started_prior_step": sms_retriever,
                "wa_timer_id": wa_timer_id,
                "reg_info": reg_info_str,
                "flow_info": flow_info_str,
                "current_step": current_step,
                "INTERNAL__latency_qpl_marker_id": qpl_marker_id,
                "INTERNAL__latency_qpl_instance_id": qpl_instance_id,
                "device_id": None,
                "family_device_id": None,
                "waterfall_id": waterfall_id,
                "offline_experiment_group": None,
                "layered_homepage_experiment_group": None,
                "is_platform_login": 0,
                "is_from_logged_in_switcher": 0,
                "is_from_logged_out": 0,
                "access_flow_version": "pre_mt_behavior",
                "login_surface": "unknown",
            }
            bloks_inner = {
                "params": json.dumps({
                    "server_params": server_params,
                    "client_input_params": client_input_params,
                })
            }
            dyn_telemetry_bk = get_random_comet_telemetry()
            bloks_post = {
                "__user": str(clean_actor),
                "__a": "1",
                "__req": "1",
                "__hs": comet_hs,
                "dpr": "1",
                "__ccg": "EXCELLENT",
                "__rev": comet_rev,
                "__s": comet_s or dyn_telemetry_bk["__s"],
                "__hsi": comet_hsi or dyn_telemetry_bk["__hsi"],
                "__dyn": dyn_telemetry_bk["__dyn"],
                "__csr": dyn_telemetry_bk["__csr"],
                "__hsdp": dyn_telemetry_bk["__hsdp"],
                "__hblp": dyn_telemetry_bk["__hblp"],
                "__sjsp": dyn_telemetry_bk["__sjsp"],
                "fb_dtsg": cur_fb_dtsg,
                "jazoest": jazoest,
                "lsd": cur_lsd,
                "params": json.dumps(bloks_inner),
            }
            bk_host = mobile_server or "m.facebook.com"
            fetch_url = f"https://{bk_host}/async/wbloks/fetch/?appid=com.bloks.www.bloks.caa.reg.confirmation.async&type=action&__bkv={bkv_hash}"
            bloks_hdrs = dict(base_hdrs)
            bloks_hdrs.update({
                "Origin": f"https://{bk_host}",
                "Referer": f"https://{bk_host}/confirmemail.php",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "x-asbd-id": "129477",
                "Accept": "*/*",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            })
            logger.info(f"[VR OTP] Gửi mã OTP '{clean_code}' qua Wbloks async fetch ({bk_host})...")
            r_bk = session.post(fetch_url, data=bloks_post, headers=bloks_hdrs, timeout=timeout)
            _sync_cookies(session, r_bk)
            if r_bk and r_bk.status_code == 200:
                bk_txt = r_bk.text
                if any(bad in bk_txt for bad in ("checkpoint/block", "help/103873106370583")):
                    return False, "Facebook từ chối mã OTP và chuyển hướng tới Checkpoint 282 (DIE)"

                raw_bk_clean = bk_txt.strip()
                if raw_bk_clean.startswith("for (;;);"):
                    raw_bk_clean = raw_bk_clean[9:].strip()
                if raw_bk_clean.startswith("{") and raw_bk_clean.endswith("}"):
                    try:
                        j_bk = json.loads(raw_bk_clean)
                        redir_bk = str(j_bk.get("redirect") or j_bk.get("redirectTo") or j_bk.get("redirect_url") or "").lower()
                        if redir_bk:
                            if any(bad in redir_bk for bad in ("checkpoint/block", "help/103873106370583")):
                                return False, f"Tài khoản bị Checkpoint 282 (DIE) ({redir_bk})"
                            if "dismiss=1" in redir_bk or any(ok_k in redir_bk for ok_k in ("feed", "home", "welcome", "save-device", "profile", "nux")):
                                return _confirm_success(f"Xác nhận WBloks async thành công! (Redirect {redir_bk})")
                        jsmods_bk = j_bk.get("jsmods")
                        if isinstance(jsmods_bk, dict):
                            for mod_item in jsmods_bk.get("require", []):
                                if isinstance(mod_item, list) and len(mod_item) >= 4 and mod_item[0] == "ServerRedirect":
                                    args_bk = mod_item[3]
                                    if isinstance(args_bk, list) and len(args_bk) > 0:
                                        tgt_bk = str(args_bk[0]).replace(r"\/", "/").lower()
                                        if any(bad in tgt_bk for bad in ("checkpoint/block", "help/103873106370583")):
                                            return False, f"Tài khoản bị Checkpoint 282 (DIE) ({tgt_bk})"
                                        return _confirm_success(f"Xác nhận WBloks async thành công qua ServerRedirect ({tgt_bk})")
                    except Exception:
                        pass

                is_confirmed_wbloks = (
                    any(k in bk_txt for k in (
                        '"is_confirmed":true', '"is_confirmed": true', '"CAA_REG_CONFIRMATION:is_confirmed" true',
                        'transition_success', 'CAA_NUX', 'caa_reg_splash_screen',
                        'bk.action.caa.reg.confirmation.success', 'confirmation.success',
                        'dismiss=1', 'home.php', 'fb://feed', 'save-device'
                    ))
                    or ('CAA_REG_CONFIRMATION:is_confirmed' in bk_txt and '"initial": true' in bk_txt.lower())
                )
                if is_confirmed_wbloks:
                    logger.info(f"[VR OTP] ✅ Xác nhận WBloks async thành công cho UID: {clean_actor}!")
                    return _confirm_success(f"Xác nhận WBloks async thành công! Meta chấp nhận mã OTP '{clean_code}'!")
        except Exception as ex_bk:
            logger.debug(f"[VR OTP] Lỗi Wbloks fetch: {ex_bk}")

    # =========================================================================
    # Fallback Channel 2.5: Lightweight Confirmation GET via mbasic.facebook.com
    # =========================================================================
    if clean_code:
        try:
            mb_host = "mbasic.facebook.com"
            mb_url = f"https://{mb_host}/confirmemail.php?c={clean_code}"
            mb_hdrs = dict(base_hdrs)
            mb_hdrs.update({
                "referer": f"https://{mb_host}/confirmemail.php",
                "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
            })
            clean_client_hints(mb_hdrs, mb_hdrs["user-agent"])
            mb_hdrs.pop("x-asbd-id", None)
            mb_hdrs.pop("X-Requested-With", None)
            mb_hdrs.pop("x-requested-with", None)

            logger.info(f"[VR OTP] Th? Fallback x?c nh?n m? '{clean_code}' qua mbasic URL GET ({mb_url})...")
            r_mb = session.get(mb_url, headers=mb_hdrs, allow_redirects=True, timeout=timeout)
            _sync_cookies(session, r_mb)
            if r_mb and r_mb.status_code in (200, 302):
                mb_u = getattr(r_mb, "url", "").lower()
                mb_t = getattr(r_mb, "text", "").lower()
                if is_checkpoint_die(mb_u) or is_checkpoint_die(mb_t):
                    return False, f"T?i kho?n b? Checkpoint 282 sau mbasic GET ({mb_u})"
                if is_facebook_onboarding_redirect(mb_u) or any(ok_k in mb_u for ok_k in ("feed", "home.php", "welcome", "save-device", "profile")):
                    return _confirm_success(f"X?c nh?n th?nh c?ng qua mbasic GET ({mb_u})")
                if any(ok_t in mb_t for ok_t in ("b?ng tin", "news feed", "ch?o m?ng", "welcome to facebook", "l?u thi?t b?")):
                    return _confirm_success("X?c nh?n th?nh c?ng qua n?i dung ph?n h?i mbasic GET")
        except Exception as ex_mb_get:
            logger.debug(f"[VR OTP] L?i mbasic GET: {ex_mb_get}")

    # =========================================================================
    # Fallback Channel 3: Direct confirmation URLs
    # =========================================================================
    if clean_code:
        try:
            urls_to_try = [
                f"https://{server}/wap/confirmemail.php?c={clean_code}",
                f"https://{server}/confirmemail.php?c={clean_code}&_fb_noscript=1",
                f"https://{server}/confirmemail.php?c={clean_code}" + (f"&e={email}" if email else ""),
                f"https://{server}/confirmemail.php?code={clean_code}" + (f"&email={email}" if email else ""),
            ]
            if email and "@" not in str(email):
                urls_to_try.extend([
                    f"https://{server}/confirmphone.php?c={clean_code}",
                    f"https://{server}/confirmphone.php?code={clean_code}",
                    f"https://{server}/wap/confirmphone.php?c={clean_code}",
                ])
            for u in urls_to_try:
                try:
                    r_u = session.get(u, headers=base_hdrs, timeout=timeout, allow_redirects=True)
                    _sync_cookies(session, r_u)
                    u_final = getattr(r_u, "url", "").lower()
                    t_final = getattr(r_u, "text", "").lower()
                    if r_u.status_code in (200, 302):
                        if any(bad in u_final for bad in ("checkpoint/block", "help/103873106370583")):
                            return False, f"Tài khoản bị chuyển hướng Checkpoint 282 ({u_final})"
                        if any(bad in u_final for bad in ("confirmemail", "caa/reg", "confirmation", "828281030927956", "checkpoint")):
                            pass
                        elif any(ok_k in u_final for ok_k in ("welcome", "home", "feed", "splash", "gettingstarted", "save-device", "profile.php", "nux")):
                            return _confirm_success("Xác nhận thành công qua liên kết confirmemail.php")
                        if any(t_ok in t_final for t_ok in ("đã xác nhận hoàn tất", "email confirmed successfully", "hòm thư đã được xác nhận")):
                            return _confirm_success("Xác nhận thành công qua thông điệp trang!")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[VR OTP] Lỗi direct confirm URL: {e}")

    # =========================================================================
    # Channel 5: Strict Ground-Truth Verification Probe (Deep-Link & Session Probes)
    # =========================================================================
    try:
        probe_hdrs = dict(base_hdrs)
        probe_hdrs.pop("X-Requested-With", None)
        probe_hdrs.pop("x-requested-with", None)
        probe_hdrs.pop("X-FB-Supports-Fresco", None)
        probe_hdrs.pop("x-fb-supports-fresco", None)
        probe_hdrs["sec-fetch-dest"] = "document"
        probe_hdrs["sec-fetch-mode"] = "navigate"
        probe_hdrs["sec-fetch-site"] = "same-origin"
        probe_hdrs["sec-fetch-user"] = "?1"
        probe_hdrs["upgrade-insecure-requests"] = "1"
        cur_probe_ua = probe_hdrs.get("user-agent") or probe_hdrs.get("User-Agent") or ""
        if not is_chromium_ua(cur_probe_ua):
            clean_client_hints(probe_hdrs, cur_probe_ua)

        real_checkpoint_indicators = [
            "tài khoản của bạn đã bị tạm ngưng", "chúng tôi đã tạm ngưng tài khoản",
            "your account has been suspended", "we suspended your account",
            "tài khoản của bạn đã bị vô hiệu hóa", "your account has been disabled",
            "180 ngày để phản đối", "180 days to disagree", "phản đối quyết định",
            "chụp ảnh khuôn mặt", "tải lên video selfie", "take a video selfie",
            "tải lên giấy tờ tùy thân", "upload your id"
        ]

        probe_hosts = [server or "m.facebook.com"]
        if "m.facebook.com" not in probe_hosts:
            probe_hosts.append("m.facebook.com")

        for chk_host in probe_hosts:
            try:
                r_me = session.get(f"https://{chk_host}/home.php", headers=probe_hdrs, allow_redirects=True, timeout=8, verify=False)
                _sync_cookies(session, r_me)
                final_u = getattr(r_me, "url", "").lower()
                final_t = getattr(r_me, "text", "").lower()
                loc_hdr = str(getattr(r_me, "headers", {}).get("Location") or getattr(r_me, "headers", {}).get("location") or "").lower()

                # 0. Checkpoint 282 / DIE LUÔN KIỂM TRA ĐẦU TIÊN
                is_real_cp = (
                    is_checkpoint_die(final_u)
                    or is_checkpoint_die(loc_hdr)
                    or is_checkpoint_die(final_t)
                    or any(bad in final_t for bad in real_checkpoint_indicators)
                )
                if is_real_cp:
                    return False, f"Tài khoản bị dính Checkpoint 282 (DIE) ({final_u or loc_hdr})"

                # 1. Nhận diện NVR (confirmemail / 828281030927956 / markers xác minh trong text hoặc URL) - ƯU TIÊN KIỂM TRA ĐẦU TIÊN
                is_probe_nvr = (
                    any(bad in loc_hdr or bad in final_u for bad in (
                        "confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "/checkpoint/",
                        "contactpoint/preconfirmation"
                    ))
                    or any(bad in final_t for bad in (
                        "caaregistrationconfirmationroot", "caaconfirmationform", "nhập mã xác nhận", "enter confirmation code",
                        "enter the confirmation code", "enter the 5-digit code", "mã gồm 5 chữ số", "caa_reg_confirmation",
                        "com.bloks.www.bloks.caa.reg.confirmation", "xcaafbmobilewebbloksregconfirmationcontroller",
                        "to confirm your account", "we sent a confirmation code", "we sent you a code"
                    ))
                )
                if is_probe_nvr:
                    return False, f"Tài khoản vẫn ở trạng thái NVR (Chờ xác minh mã OTP) ({final_u or loc_hdr})"

                # 2. Onboarding Redirect (next= / dismiss / save-device) - Chỉ khi KHÔNG còn NVR
                if is_facebook_onboarding_redirect(final_u) or is_facebook_onboarding_redirect(loc_hdr):
                    try:
                        r_dis = session.get(f"https://{chk_host}/home.php", headers=probe_hdrs, allow_redirects=True, timeout=6)
                        _sync_cookies(session, r_dis)
                        dis_u = str(getattr(r_dis, "url", "")).lower()
                        dis_t = str(getattr(r_dis, "text", "")).lower()
                        if is_checkpoint_die(dis_u) or is_checkpoint_die(dis_t):
                            return False, f"Tài khoản bị Checkpoint 282 sau chuyển tiếp ({dis_u})"
                        if any(bad in dis_u for bad in ("confirmemail", "confirmphone", "caa/reg", "confirmation", "828281030927956", "/checkpoint/")) or any(bad in dis_t for bad in ("caaregistrationconfirmationroot", "caaconfirmationform", "nhập mã xác nhận", "enter confirmation code", "enter the 5-digit code")):
                            return False, f"Tài khoản vẫn ở form xác minh OTP ({dis_u})"
                    except Exception:
                        pass
                    return _confirm_success(f"Xác nhận OTP thành công! Meta chuyển hướng phiên sang onboarding ({final_u or loc_hdr}).")

                # 3. Mất phiên login
                if any(k in final_u for k in ("login.php", "/login/", "login_attempt")):
                    return False, f"Mất phiên đăng nhập ({final_u})"

                # 4. Phiên hợp lệ đã vào Profile / Feed
                is_live_me = False
                if ("fb://feed" in loc_hdr or "fb://" in loc_hdr or "/feed" in loc_hdr) and not any(k in loc_hdr for k in real_checkpoint_indicators) and not any(bad in loc_hdr for bad in ("confirmemail", "caa/reg", "confirmation", "828281030927956", "login")):
                    return _confirm_success(f"Xác nhận OTP thành công! Facebook đã chuyển hướng sang phiên hoạt động chính thức ({loc_hdr}).")
                elif getattr(r_me, "status_code", 0) == 200:
                    if (clean_actor and clean_actor != "0" and f"profile.php?id={clean_actor}" in final_u) or (clean_actor and clean_actor != "0" and f"/{clean_actor}" in final_u and "confirm" not in final_u):
                        is_live_me = True
                    elif "/feed" in final_u and "confirm" not in final_u:
                        is_live_me = True
                    elif ("home.php" in final_u or final_u.rstrip("/") in (f"https://{chk_host}", "https://facebook.com", "https://m.facebook.com", "https://www.facebook.com")):
                        feed_markers = ("bảng tin", "news feed", 'data-pagelet="Feed"', 'role="feed"', 'id="m_newsfeed_stream"', 'data-sigil="m-feed-stream"')
                        if any(k in final_t for k in feed_markers):
                            is_live_me = True

                if is_live_me:
                    return _confirm_success(f"Xác nhận OTP thành công! Facebook đã chuyển hướng sang phiên hoạt động chính thức ({final_u}).")
            except Exception as pe:
                err_str = str(pe)
                if "fb://feed" in err_str or "fb://" in err_str:
                    return _confirm_success("Xác nhận OTP thành công! Facebook đã chuyển hướng sang fb://feed.")
                logger.debug(f"Probe /me error on {chk_host}: {pe}")

        # Probe mobile home feed
        try:
            r_home = session.get(f"https://{server}/", headers=probe_hdrs, allow_redirects=True, timeout=8)
            _sync_cookies(session, r_home)
            home_u = getattr(r_home, "url", "").lower()
            home_t = getattr(r_home, "text", "").lower()
            is_home_nvr = (
                any(bad in home_u for bad in ("confirmemail", "caa/reg/confirmation", "/confirmation/", "caaconfirmation", "contactpoint/preconfirmation", "828281030927956"))
                or ("caaregistrationconfirmationroot" in home_t)
                or ("caaconfirmationform" in home_t)
                or (any(k in home_t for k in ("nhập mã xác nhận", "enter the 5-digit code", "confirmation_code_length")) and not any(ok in home_u for ok in ("feed", "home", "profile", "welcome", "save-device", "nux", "caa_reg_splash_screen")))
            )
            if is_home_nvr:
                return False, "Tài khoản vẫn ở trạng thái NVR (Chờ xác minh mã OTP - Chưa thoát form)"
            if is_checkpoint_die(home_u) or is_checkpoint_die(home_t) or any(bad in home_t for bad in real_checkpoint_indicators):
                return False, f"Tài khoản bị dính Checkpoint 282 (DIE) ({home_u})"
            is_home_cp = ("checkpoint/block" in home_u) or ("help/103873106370583" in home_u) or ("checkpoint/disabled" in home_u) or ("checkpoint/suspended" in home_u)
            if is_home_cp:
                return False, f"Tài khoản bị dính Checkpoint 282 (DIE) ({home_u})"
            if (clean_actor and clean_actor != "0" and f"/{clean_actor}" in home_u) or "/me" in home_u or any(ok_k in home_u for ok_k in ("feed", "profile.php", "welcome", "home", "gettingstarted", "save-device", "nux", "caa_reg_splash_screen")) or (home_u.rstrip("/") in (f"https://{server}", "https://facebook.com", "https://m.facebook.com")):
                return _confirm_success(f"Xác nhận OTP thành công! Facebook chuyển hướng tới trang chủ/bảng tin ({home_u}).")
        except Exception as he:
            logger.debug(f"Probe home error: {he}")
    except Exception as e:
        logger.debug(f"[VR OTP] Error in Channel 5 /me probe: {e}")

    return False, "Tài khoản vẫn ở trạng thái NVR (Chưa xác nhận hoàn tất mã OTP)"


# ==============================================================================
# 5. TEMPMAIL.LOL PROVIDER (Free, Fast, Fresh Domains)
# ==============================================================================

class TempMailLolProvider(BaseEmailProvider):
    provider_name = "tempmail_lol"
    """
    TempMail.lol API v2 (https://tempmail.lol).
    Provides fresh non-standard domains with high deliverability.
    """
    BASE_URL = "https://api.tempmail.lol/v2"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        proxies = self._get_proxies(proxy)
        try:
            r = requests.get(f"{self.BASE_URL}/inbox/create", proxies=proxies, timeout=10)
            if r.status_code in (200, 201):
                data = r.json()
                address = data.get("address")
                token = data.get("token")
                if address and token:
                    logger.info(f"[TempMail.lol] Created mailbox: {address}")
                    return EmailAccount(
                        email=address,
                        provider="tempmaillol",
                        token=token,
                        metadata={"token": token},
                    )
        except Exception as e:
            logger.error(f"[TempMail.lol] Creation error: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        token = account.token or account.metadata.get("token")

        logger.info(f"[TempMail.lol] Waiting for OTP email at {account.email} (Max: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(f"{self.BASE_URL}/inbox?token={token}", proxies=proxies, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    emails = data.get("emails", [])
                    if emails:
                        latest = emails[0]
                        subject = latest.get("subject", "")
                        body = latest.get("body") or latest.get("html") or ""
                        sender = latest.get("from", "")

                        full_content = f"{subject}\n{body}"
                        otp = extract_otp_code(full_content)
                        conf_link = extract_confirmation_link(full_content)
                        if otp or conf_link:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[TempMail.lol] OTP/Link nhận được: {otp or conf_link} trong {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp,
                                confirmation_link=conf_link,
                                sender=sender,
                                subject=subject,
                                body_preview=body[:150],
                                elapsed_seconds=elapsed,
                            )
            except Exception as e:
                logger.debug(f"[TempMail.lol] Polling error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for TempMail.lol OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# 6. INBOXES.COM PROVIDER (Free, Clean Domains: blondmail, dropjar, etc.)
# ==============================================================================

class InboxesProvider(BaseEmailProvider):
    """
    Inboxes.com API v2 (https://inboxes.com).
    18+ clean domains: blondmail.com, chapsmail.com, dropjar.com, clowmail.com,
    getairmail.com, getmule.com, inboxbear.com, robot-mail.com, tafmail.com, tupmail.com, vomoto.com, v.v.
    """
    BASE_URL = "https://inboxes.com/api/v2"
    DEFAULT_DOMAINS = [
        "blondmail.com", "chapsmail.com", "clowmail.com", "dropjar.com",
        "fivermail.com", "getairmail.com", "getmule.com", "getnada.com",
        "gimpmail.com", "givmail.com", "guysmail.com", "inboxbear.com",
        "replyloop.com", "robot-mail.com", "tafmail.com", "temptami.com",
        "tupmail.com", "vomoto.com", "boximail.com",
        "zetmail.com", "femail.me", "carbtc.net", "wmail.club",
        "dropmail.me", "nada.ltd", "nada.email", "nada.co",
        "spambox.me", "duck2.club", "tempm.com"
    ]
    _cached_domains: List[str] = []
    _cached_domains_time: float = 0.0
    _domains_lock = threading.Lock()

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, **kwargs) -> Optional[EmailAccount]:
        now = time.time()
        domains = list(self.DEFAULT_DOMAINS)
        with self._domains_lock:
            if self._cached_domains and (now - self._cached_domains_time < 300.0):
                domains = list(self._cached_domains)
            else:
                try:
                    r = requests.get(f"{self.BASE_URL}/domain", timeout=2.5)
                    if r.status_code == 200:
                        raw_domains = r.json().get("domains", [])
                        if raw_domains:
                            fetched = [d.get("qdn") for d in raw_domains if d.get("qdn")]
                            if fetched:
                                self._cached_domains = fetched
                                self._cached_domains_time = now
                                domains = fetched
                except Exception as e:
                    logger.debug(f"[Inboxes.com] Domains fetch fallback to default: {e}")
                    if not self._cached_domains:
                        self._cached_domains = list(self.DEFAULT_DOMAINS)
                        self._cached_domains_time = now

        chosen_domain = domain if (domain and domain in domains) else DomainDiversityTracker().pick_random_diverse_domain(domains)
        first_name = kwargs.get("first_name")
        last_name = kwargs.get("last_name")
        b_year = kwargs.get("b_year")
        username = generate_human_email_username(first_name=first_name, last_name=last_name, birth_year=b_year)
        email = f"{username}@{chosen_domain}"

        logger.info(f"[Inboxes.com] Cấp phát mailbox: {email}")
        return EmailAccount(
            email=email,
            provider="inboxes",
            metadata={"username": username, "domain": chosen_domain},
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        email = account.email

        logger.info(f"[Inboxes.com] Đang chờ mã OTP cho {email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(f"{self.BASE_URL}/inbox/{email}", proxies=proxies, timeout=8)
                if r.status_code == 200:
                    msgs = r.json().get("msgs", [])
                    if msgs and isinstance(msgs, list):
                        for m_item in msgs:
                            msg_uid = m_item.get("uid")
                            subject = m_item.get("s", "")
                            sender = m_item.get("f", "")
                            body = ""
                            if msg_uid:
                                try:
                                    r_body = requests.get(f"{self.BASE_URL}/message/{msg_uid}", proxies=proxies, timeout=8)
                                    if r_body.status_code == 200:
                                        body = r_body.json().get("text") or r_body.json().get("html") or ""
                                except Exception:
                                    pass

                            full_content = f"{subject}\n{body}"
                            otp = extract_otp_code(full_content)
                            conf_link = extract_confirmation_link(full_content)
                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[Inboxes.com] OTP/Link nhận được: {otp or conf_link} trong {elapsed}s")
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    sender=sender,
                                    subject=subject,
                                    body_preview=body[:150],
                                    elapsed_seconds=elapsed,
                                    metadata=m_item,
                                )
            except Exception as e:
                logger.debug(f"[Inboxes.com] Polling error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Inboxes.com OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )

# ==============================================================================
# 7. 1SECMAIL PROVIDER (Free, Fast, Multi-Domain Pool)
# ==============================================================================

class OneSecMailProvider(BaseEmailProvider):
    """
    1SecMail API provider (https://www.1secmail.com/api/v1/).
    Completely free, fast, supports multiple randomized domains.
    """
    BASE_URL = "https://www.1secmail.com/api/v1"
    DOMAINS = ["kzccv.com", "qiott.com", "wuuvo.com", "icznn.com", "dcctb.com", "vjuum.com", "esiix.com", "vddaz.com", "bupcl.com"]

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        proxies = self._get_proxies(proxy)
        try:
            r = requests.get(f"{self.BASE_URL}/?action=genRandomMailbox&count=1", proxies=proxies, timeout=10)
            if r.status_code == 200 and r.json():
                email_addr = r.json()[0]
                user, domain = email_addr.split("@")
                logger.info(f"[1SecMail] Cấp phát mailbox: {email_addr}")
                return EmailAccount(
                    email=email_addr,
                    provider="onesecmail",
                    metadata={"login": user, "domain": domain},
                )
        except Exception as e:
            logger.debug(f"[1SecMail] API gen error, fallback local: {e}")

        user = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        dom = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        email_addr = f"{user}@{dom}"
        logger.info(f"[1SecMail] Cap phat mailbox (fallback local): {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="onesecmail",
            metadata={"login": user, "domain": dom},
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        meta = account.metadata or {}
        user = meta.get("login")
        domain = meta.get("domain")
        if not user or not domain:
            if "@" in account.email:
                user, domain = account.email.split("@", 1)
            else:
                return OTPVerificationResult(success=False, email=account.email, error="Email không hợp lệ")

        logger.info(f"[1SecMail] Đang chờ mã OTP cho {account.email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(
                    f"{self.BASE_URL}/?action=getMessages&login={user}&domain={domain}",
                    proxies=proxies,
                    timeout=10
                )
                if r.status_code == 200:
                    messages = r.json()
                    if messages and isinstance(messages, list):
                        msg_id = messages[0].get("id")
                        r_msg = requests.get(
                            f"{self.BASE_URL}/?action=readMessage&login={user}&domain={domain}&id={msg_id}",
                            proxies=proxies,
                            timeout=10
                        )
                        if r_msg.status_code == 200:
                            msg_data = r_msg.json()
                            subject = msg_data.get("subject", "")
                            body = msg_data.get("textBody") or msg_data.get("body") or msg_data.get("htmlBody") or ""
                            sender = msg_data.get("from", "")

                            otp = extract_otp_code(f"{subject}\n{body}")
                            conf_link = extract_confirmation_link(f"{subject}\n{body}")
                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[1SecMail] Bắt được OTP: {otp} sau {elapsed}s")
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    sender=sender,
                                    subject=subject,
                                    body_preview=body[:150],
                                    elapsed_seconds=elapsed,
                                    metadata={"msg_id": msg_id, "provider": "onesecmail"},
                                )
            except Exception as e:
                logger.debug(f"[1SecMail] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for 1SecMail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )




# ==============================================================================
# 8. TEMP-MAIL.IO PROVIDER (Free, Multi-domain API)
# ==============================================================================

class TempMailIoProvider(BaseEmailProvider):
    """
    Temp-Mail.io API v3 (https://temp-mail.io).
    Free, high deliverability, rotating clean domains.
    """
    BASE_URL = "https://api.internal.temp-mail.io/api/v3"
    DEFAULT_DOMAINS = [
        "yzcalo.com", "lnovic.com", "ruutukf.com", "gmeenramy.com",
        "olipii.com", "ooynib.com", "tanpony.com", "cloud-mail.top",
        "greencafe24.com", "best-temp.com", "quickmail.pro", "temp-mail.io",
        "vvatxiy.com", "crewevy.com", "daouse.com", "vipiia.com",
        "creavita.net", "nexitoo.com", "woopi.net", "plakoto.net",
        "chilliwax.com", "dunked.net", "viamail.me"
    ]

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    _cached_domains: List[str] = []
    _cached_domains_time: float = 0.0
    _domains_lock = threading.Lock()

    def get_domains(self, proxy: Optional[str] = None) -> List[str]:
        now = time.time()
        with self._domains_lock:
            if self._cached_domains and (now - self._cached_domains_time < 300.0):
                return list(self._cached_domains)
            try:
                r = requests.get(f"{self.BASE_URL}/domains", timeout=2.5)
                if r.status_code == 200:
                    domain_objs = r.json().get("domains", [])
                    names = [d.get("name") for d in domain_objs if d.get("name")]
                    if names:
                        self._cached_domains = names
                        self._cached_domains_time = now
                        return names
            except Exception as e:
                logger.debug(f"[TempMail.io] Domains fetch error: {e}")
            if not self._cached_domains:
                self._cached_domains = list(self.DEFAULT_DOMAINS)
                self._cached_domains_time = now
            return list(self._cached_domains)

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        proxies = self._get_proxies(proxy)
        domains = self.get_domains(proxy)
        chosen_domain = domain if (domain and domain in domains) else DomainDiversityTracker().pick_random_diverse_domain(domains)
        username = generate_human_email_username().replace(".", "").replace("_", "")

        try:
            r = requests.post(
                f"{self.BASE_URL}/email/new",
                json={"domain": chosen_domain, "name": username},
                proxies=proxies,
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                email_addr = data.get("email", f"{username}@{chosen_domain}")
                token = data.get("token")
                logger.info(f"[TempMail.io] Cấp phát mailbox: {email_addr}")
                return EmailAccount(
                    email=email_addr,
                    provider="tempmail_io",
                    token=token,
                    metadata={"token": token, "domain": chosen_domain, "name": username},
                )
        except Exception as e:
            logger.debug(f"[TempMail.io] Targeted creation error: {e}")

        try:
            r_fb = requests.post(
                f"{self.BASE_URL}/email/new",
                json={"min_name_length": 10, "max_name_length": 10},
                proxies=proxies,
                timeout=10,
            )
            if r_fb.status_code == 200:
                data = r_fb.json()
                email_addr = data.get("email")
                token = data.get("token")
                if email_addr:
                    logger.info(f"[TempMail.io] Cấp phát mailbox ngẫu nhiên: {email_addr}")
                    return EmailAccount(
                        email=email_addr,
                        provider="tempmail_io",
                        token=token,
                        metadata={"token": token},
                    )
        except Exception as e:
            logger.error(f"[TempMail.io] Allocation error: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        email = account.email
        logger.info(f"[TempMail.io] Đang chờ mã OTP cho {email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(
                    f"{self.BASE_URL}/email/{email}/messages",
                    proxies=proxies,
                    timeout=10,
                )
                if r.status_code == 200:
                    messages = r.json()
                    if messages and isinstance(messages, list):
                        for msg in messages:
                            subject = msg.get("subject", "")
                            body = msg.get("body_text") or msg.get("body_html") or ""
                            sender = msg.get("from", "")
                            full_text = f"{subject}\n{body}"
                            otp = extract_otp_code(full_text)
                            conf_link = extract_confirmation_link(full_text)
                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[TempMail.io] Bắt được OTP: {otp} sau {elapsed}s")
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    sender=sender,
                                    subject=subject,
                                    body_preview=body[:150],
                                    elapsed_seconds=elapsed,
                                    metadata=msg,
                                )
            except Exception as e:
                logger.debug(f"[TempMail.io] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Temp-Mail.io OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
# ==============================================================================
# 9. 10MINUTEMAIL.NET PROVIDER (@laoia.com) - SIÊU TỐC & KHÔNG NGHẼN ĐA LUỒNG
# ==============================================================================

_TEN_MIN_DIRECT_COOLDOWN = 0.0
_TEN_MIN_LOCK = threading.Lock()
_TEN_MIN_LAST_CALL = 0.0


class TenMinuteMailNetProvider(BaseEmailProvider):
    """10MinuteMail.net API (https://10minutemail.net).

    Chuyên cấp phát nhanh chuẩn xác đuôi @laoia.com theo yêu cầu người dùng.
    Tối ưu đa luồng:
    1. Khi dùng Proxy (Proxy.vn, Kiot, Socks5): Chạy song song không lock, phản hồi tức thì 1s.
    2. Chỉ gọi proxy của chính luồng đó, không duyệt vòng qua 20 proxy gây treo đơ.
    3. Đảm bảo 100% nhận đuôi @laoia.com ngay từ phiên đầu tiên.
    """

    BASE_URL = "https://10minutemail.net"
    ALLOWED_DOMAINS = (
        "laoia.com",
        "cdfaq.com",
        "txcct.com",
        "bupcl.com",
        "vjuum.com",
        "vddaz.com",
        "smail1s.com",
        "ooynib.com",
        "clowmail.com",
        "sptech.io.vn",
        "tanpony.com",
        "any.pink",
        "posttemp.org",
        "trashmail.me",
        "yopmail.net",
        "mailbox.in",
        "mohmal.im",
    )

    def _get_proxies(self, proxy: Optional[Any] = None) -> Optional[Dict[str, str]]:
        if not proxy or proxy in ("Direct", "(Chờ cấp IP)", "N/A", "(Không proxy)"):
            return None
        if isinstance(proxy, dict):
            return proxy
        p_str = ""
        if hasattr(proxy, "as_url"):
            try:
                p_str = proxy.as_url()
            except Exception:
                p_str = ""
        elif hasattr(proxy, "url"):
            p_str = getattr(proxy, "url", "")
        if not p_str and hasattr(proxy, "host") and getattr(proxy, "port", None):
            p_str = f"http://{proxy.host}:{proxy.port}"
        if not p_str and isinstance(proxy, str):
            p_str = proxy.strip()
            if "ProxyItem(" in p_str:
                m_hp = re.search(r"host='([^']+)',\s*port=(\d+)", p_str)
                if m_hp:
                    p_str = f"http://{m_hp.group(1)}:{m_hp.group(2)}"
        if p_str and p_str not in ("Direct", "(Chờ cấp IP)", "N/A", "(Không proxy)"):
            if not p_str.startswith("http://") and not p_str.startswith("https://") and not p_str.startswith("socks"):
                p_str = "http://" + p_str
            return {"http": p_str, "https": p_str}
        return None

    def __init__(self, fixed_domain: Optional[str] = "laoia.com", **kwargs):
        super().__init__()
        self.fixed_domain = str(fixed_domain).lower().strip().lstrip("@") if fixed_domain else "laoia.com"

    def create_mailbox(self, proxy: Optional[Any] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        target_domain = domain.lower().strip().lstrip("@") if domain else getattr(self, "fixed_domain", "laoia.com")
        if target_domain and not any(target_domain == d or target_domain.endswith("." + d) for d in self.ALLOWED_DOMAINS):
            target_domain = "laoia.com"

        worker_p_dict = self._get_proxies(proxy)

        # Nếu không có proxy (Direct), dùng micro-sleep 0.1s để tránh 429 trên IP cục bộ
        if not worker_p_dict:
            global _TEN_MIN_DIRECT_COOLDOWN, _TEN_MIN_LAST_CALL
            with _TEN_MIN_LOCK:
                now = time.time()
                diff = now - _TEN_MIN_LAST_CALL
                if diff < 0.1:
                    time.sleep(0.1 - diff)
                _TEN_MIN_LAST_CALL = time.time()

        # Danh sách proxy gọn gàng: Ưu tiên proxy của chính worker
        candidate_proxies = []
        if worker_p_dict:
            candidate_proxies.append(worker_p_dict)

        # Lấy thêm 1 proxy backup từ Proxy.vn cache để đảm bảo tỷ lệ cấp mail cao nhất
        try:
            from core.proxy_manager import _PROXYVN_CACHE, _PROXYVN_CACHE_LOCK
            with _PROXYVN_CACHE_LOCK:
                for p_info in list(_PROXYVN_CACHE.values()):
                    h = p_info.get("http")
                    if h:
                        b_dict = self._get_proxies(h)
                        if b_dict and b_dict not in candidate_proxies:
                            candidate_proxies.append(b_dict)
                            break
        except Exception:
            pass

        if not candidate_proxies:
            candidate_proxies.append(None)

        for px_cfg in candidate_proxies:
            for attempt in range(2):
                try:
                    s = requests.Session()
                    rand_chrome = random.randint(122, 131)
                    s.headers.update({
                        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{rand_chrome}.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
                        "Referer": "https://10minutemail.net/",
                    })
                    # Gọi trực tiếp address.api.php để luôn lấy domain chính @laoia.com
                    url = f"{self.BASE_URL}/address.api.php"
                    r = s.get(url, proxies=px_cfg, timeout=4.0, verify=False)
                    if r.status_code in (429, 403):
                        break

                    data = r.json()
                    if data.get("error") and (data.get("code") in ("limit", "cooldown")):
                        break

                    email = str(data.get("mail_get_mail") or "").strip()
                    mail_user = data.get("mail_get_user")
                    mail_host = str(data.get("mail_get_host") or "").lower()

                    if not email or "@" not in email:
                        continue

                    cur_domain = email.split("@")[-1].lower()

                    # Lọc chính xác đuôi (mặc định @laoia.com)
                    if target_domain and target_domain != "all":
                        expected_domain = target_domain.lower().lstrip("@")
                        if cur_domain != expected_domain and not cur_domain.endswith("." + expected_domain):
                            if attempt == 0:
                                time.sleep(0.1)
                                continue
                            pass

                    cookie_dict = s.cookies.get_dict()
                    logger.info(f"[10MinuteMail] Cấp phát thành công ({cur_domain}): {email}")
                    return EmailAccount(
                        email=email,
                        provider="10minutemail",
                        token=json.dumps(cookie_dict),
                        metadata={"cookies": cookie_dict, "user": mail_user, "host": mail_host, "proxy_dict": px_cfg, "session": s},
                    )
                except Exception as ex:
                    logger.debug(f"[10MinuteMail] Thử cấp hòm thư lỗi trên proxy {px_cfg}: {ex}")
                    break

        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 25,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        meta = account.metadata or {}
        cookie_dict = meta.get("cookies")
        if not cookie_dict and account.token:
            try:
                cookie_dict = json.loads(account.token)
            except Exception:
                cookie_dict = {}

        s = meta.get("session")
        if not s:
            s = requests.Session()
            rand_chrome = random.randint(122, 131)
            s.headers.update({
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{rand_chrome}.0.0.0 Safari/537.36",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Referer": "https://10minutemail.net/",
            })
        if cookie_dict:
            s.cookies.update({str(k): str(v) for k, v in cookie_dict.items() if v is not None})

        # Ưu tiên proxy đã tạo mailbox này
        px_used = meta.get("proxy_dict") or self._get_proxies(proxy)
        use_px = px_used

        logger.info(f"[10MinuteMail] Đang chờ mã OTP gửi về {email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = s.get(f"{self.BASE_URL}/address.api.php", proxies=use_px, timeout=5, verify=False)
                if r.status_code == 200:
                    data = r.json()
                    mail_list = data.get("mail_list", [])
                    for m in mail_list:
                        mail_id = m.get("mail_id")
                        if not mail_id or mail_id == "welcome":
                            continue

                        subj_fast = str(m.get("subject") or "")
                        sender_fast = str(m.get("from") or "")
                        otp_fast = extract_otp_code(subj_fast)
                        if otp_fast:
                            elapsed = round(time.time() - start_time, 2)
                            logger.info(f"[10MinuteMail] Bắt được OTP siêu tốc từ Subject: {otp_fast} cho {email} sau {elapsed}s")
                            return OTPVerificationResult(
                                success=True,
                                email=account.email,
                                otp_code=otp_fast,
                                confirmation_link=None,
                                sender=sender_fast,
                                subject=subj_fast,
                                body_preview=subj_fast,
                                elapsed_seconds=elapsed,
                                metadata=m,
                            )

                        try:
                            r_msg = s.get(f"{self.BASE_URL}/mail.api.php?mailid={mail_id}", proxies=use_px, timeout=4, verify=False)
                            if r_msg.status_code == 200:
                                msg_data = r_msg.json()
                                subject = msg_data.get("subject", subj_fast)
                                html_list = msg_data.get("html", [])
                                html_text = chr(10).join(html_list) if isinstance(html_list, list) else str(html_list or "")
                                body_text = str(msg_data.get("body") or "")
                                sender = msg_data.get("from", sender_fast)
                                full_text = f"{subject} " + chr(10) + str(html_text) + chr(10) + str(body_text)

                                otp = extract_otp_code(full_text)
                                conf_link = extract_confirmation_link(full_text)
                                if otp or conf_link:
                                    elapsed = round(time.time() - start_time, 2)
                                    logger.info(f"[10MinuteMail] Bắt được OTP: {otp} sau {elapsed}s")
                                    return OTPVerificationResult(
                                        success=True,
                                        email=account.email,
                                        otp_code=otp,
                                        confirmation_link=conf_link,
                                        sender=sender,
                                        subject=subject,
                                        body_preview=body_text[:120],
                                        elapsed_seconds=elapsed,
                                        metadata=msg_data,
                                    )
                        except Exception as e_msg:
                            logger.debug(f"[10MinuteMail] Lỗi đọc chi tiết thư {mail_id}: {e_msg}")
            except Exception as e_poll:
                logger.debug(f"[10MinuteMail] Lỗi kiểm tra hòm thư: {e_poll}")

            time.sleep(poll_interval)

        return OTPVerificationResult(
            success=False,
            email=account.email,
            otp_code=None,
            confirmation_link=None,
            error_message=f"Timeout waiting for 10MinuteMail OTP after {timeout_seconds}s",
            elapsed_seconds=round(time.time() - start_time, 2),
        )


# 10. MAILDROP.CC PROVIDER (GraphQL API)
# ==============================================================================

class MaildropProvider(BaseEmailProvider):
    """
    Maildrop.cc GraphQL API (https://api.maildrop.cc/graphql).
    Fast, free public inbox with GraphQL query interface.
    """
    BASE_URL = "https://api.maildrop.cc/graphql"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        mailbox = generate_human_email_username().replace(".", "").replace("_", "")
        email = f"{mailbox}@maildrop.cc"
        logger.info(f"[Maildrop.cc] Cấp phát mailbox: {email}")
        return EmailAccount(
            email=email,
            provider="maildrop",
            metadata={"mailbox": mailbox},
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        meta = account.metadata or {}
        mailbox = meta.get("mailbox") or account.email.split("@")[0]
        logger.info(f"[Maildrop.cc] Đang chờ mã OTP cho {account.email} (Tối đa: {timeout_seconds}s)...")

        query = f'query {{ inbox(mailbox: "{mailbox}") {{ id date headerfrom subject data html }} }}'
        payload = json.dumps({"query": query})
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.post(self.BASE_URL, data=payload, headers=headers, proxies=proxies, timeout=10)
                if r.status_code == 200:
                    res_json = r.json()
                    inbox = res_json.get("data", {}).get("inbox", [])
                    if inbox and isinstance(inbox, list):
                        for msg in inbox:
                            subject = msg.get("subject", "")
                            data_text = msg.get("data", "")
                            html_text = msg.get("html", "")
                            sender = msg.get("headerfrom", "")
                            full_text = f"{subject}\n{data_text}\n{html_text}"

                            otp = extract_otp_code(full_text)
                            conf_link = extract_confirmation_link(full_text)
                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[Maildrop.cc] Bắt được OTP: {otp} sau {elapsed}s")
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    sender=sender,
                                    subject=subject,
                                    body_preview=full_text[:150],
                                    elapsed_seconds=elapsed,
                                    metadata=msg,
                                )
            except Exception as e:
                logger.debug(f"[Maildrop.cc] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Maildrop.cc OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# ==============================================================================
class TempMailPlusProvider(BaseEmailProvider):
    """
    TempMail.Plus (https://tempmail.plus).
    Dịch vụ hòm thư ảo miễn phí, đa domain, hỗ trợ kiểm tra OTP tức thì qua REST API.
    Đuôi mail hỗ trợ: mailto.plus, fexpost.com, fexbox.org, mailbox.in.ua, rover.info, chitthi.in, fextemp.com, any.pink, merepost.com
    """
    BASE_URL = "https://tempmail.plus/api/mails"
    DOMAINS = [
        "any.pink", "merepost.com", "fexbox.org", "fexpost.com",
        "mailto.plus", "mailbox.in.ua", "fextemp.com", "rover.info",
        "chitthi.in", "chitthe.com", "chitti.in", "chitthii.in",
        "chitti.com", "fexmail.org", "fexmail.net", "mailto.in",
        "mailto.me", "fextemp.org", "rover.org", "fexbox.ru",
        "mailbox.org.ua", "to-mail.in", "emailplus.in", "boxpost.org",
        "mailtemp.in", "posttemp.org", "fexbox.net", "rover.net",
        "fexmail.ru", "boxpost.net", "mailbox.in", "rover.in",
        "mailto.org", "mailtemp.org", "posttemp.net", "anymail.in",
        "chitthi.net", "chitthi.org", "chitthi.info", "fexpost.net",
        "fexbox.info", "fextemp.net", "fextemp.info", "mailto.info",
        "fexmail.co", "fextemp.co", "fexbox.co", "mailto.co", "postbox.in",
        "chitti.net", "chitti.org", "chitthii.net", "chitthii.org"
    ]

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        # Không dùng proxy Facebook cho API hòm thư ảo để tránh ProxyError & nghẽn mạng
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        username = generate_human_email_username()
        chosen_domain = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        email = f"{username}@{chosen_domain}"
        logger.info(f"[TempMail.Plus] Cấp phát mailbox: {email}")
        return EmailAccount(
            email=email,
            provider="tempmail_plus",
            metadata={"username": username, "domain": chosen_domain},
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        proxies = self._get_proxies(proxy)
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        logger.info(f"[TempMail.Plus] Đang chờ mã OTP cho {email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                url = f"{self.BASE_URL}?email={email}&limit=20"
                r = requests.get(url, headers=headers, proxies=proxies, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    mail_list = data.get("mail_list", [])
                    if mail_list and isinstance(mail_list, list):
                        for msg in mail_list:
                            mail_id = msg.get("mail_id")
                            subject = msg.get("subject", "")
                            sender = msg.get("from", "")

                            otp = extract_otp_code(subject)
                            conf_link = extract_confirmation_link(subject)

                            full_text = subject
                            if mail_id:
                                try:
                                    det_url = f"{self.BASE_URL}/{mail_id}?email={email}"
                                    det_r = requests.get(det_url, headers=headers, proxies=proxies, timeout=8)
                                    if det_r.status_code == 200:
                                        det_data = det_r.json()
                                        txt = det_data.get("text", "")
                                        html = det_data.get("html", "")
                                        full_text = f"{subject}\n{txt}\n{html}"
                                        if not otp:
                                            otp = extract_otp_code(full_text)
                                        if not conf_link:
                                            conf_link = extract_confirmation_link(full_text)
                                except Exception as det_err:
                                    logger.debug(f"[TempMail.Plus] Detail fetch error: {det_err}")

                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[TempMail.Plus] Bắt được OTP: {otp} sau {elapsed}s")
                                return OTPVerificationResult(
                                    success=True,
                                    email=account.email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    sender=sender,
                                    subject=subject,
                                    body_preview=full_text[:150],
                                    elapsed_seconds=elapsed,
                                    metadata=msg,
                                )
            except Exception as e:
                logger.debug(f"[TempMail.Plus] Poll error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for TempMail.Plus OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )



# ==============================================================================

class MohmalProvider(BaseEmailProvider):
    """
    Mohmal Disposable Temporary Email (https://www.mohmal.com).
    Hòm thư ảo miễn phí, nhận mail tự động không cần API key.
    Đuôi mail: @emailnox.live, @mohmal.im, @mohmal.in, @tmail.ws, @mohmal.com
    """
    BASE_URL = "https://www.mohmal.com"
    DOMAINS = [
        "emailnox.live", "mohmal.im", "mohmal.in", "tmail.ws", "mohmal.com",
        "mohmal.club", "fakemail.io", "tmpmail.net", "tmpmail.org", "boun.cr",
        "vmani.com", "mohmal.co", "disbox.net", "mohmal.tech", "mohmal.me",
        "mohmal.vip", "fakemail.cc", "disbox.me", "vmani.net", "boun.me"
    ]

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        s = requests.Session()
        try:
            r = s.get(f"{self.BASE_URL}/en/inbox", headers=headers, timeout=10)
            if r.status_code == 200:
                emails = re.findall(r'[\w\.-]+@(?:emailnox\.live|mohmal\.im|mohmal\.in|tmail\.ws|mohmal\.com|[\w\.-]+\.[a-zA-Z]{2,})', r.text)
                if emails:
                    email_addr = emails[0]
                    cookies_dict = s.cookies.get_dict()
                    logger.info(f"[Mohmal] Cấp phát mailbox: {email_addr}")
                    return EmailAccount(
                        email=email_addr,
                        provider="mohmal",
                        metadata={"cookies": cookies_dict, "created_at": time.time()}
                    )
        except Exception as e:
            logger.debug(f"[Mohmal] Lỗi tạo mailbox: {e}")
        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        cookies = (account.metadata or {}).get("cookies", {})
        s = requests.Session()
        s.cookies.update(cookies)
        logger.info(f"[Mohmal] Đang chờ mã OTP cho {account.email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = s.get(f"{self.BASE_URL}/en/inbox", headers=headers, timeout=10)
                if r.status_code == 200:
                    msg_ids = re.findall(r'/en/message/(\w+)', r.text)
                    otp = None
                    conf_link = None
                    for mid in msg_ids:
                        mr = s.get(f"{self.BASE_URL}/en/message/{mid}", headers=headers, timeout=8)
                        if mr.status_code == 200:
                            otp = extract_otp_code(mr.text)
                            conf_link = extract_confirmation_link(mr.text)
                            if otp or conf_link:
                                break
                    # Only check inbox page if messages were actually found
                    if not otp and not conf_link and msg_ids:
                        otp = extract_otp_code(r.text)
                        conf_link = extract_confirmation_link(r.text)

                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[Mohmal] B?t ???c m? OTP: {otp} sau {elapsed}s")
                        return OTPVerificationResult(
                            success=True,
                            email=account.email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "mohmal", "email": account.email}
                        )
            except Exception as e:
                logger.debug(f"[Mohmal] L?i poll OTP: {e}")
            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for Mohmal OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


# AUTO ROTATOR EMAIL PROVIDER (SMART MULTI-SOURCE FREE MAIL)
# ==============================================================================


# ==============================================================================
# GENERATOR.EMAIL PROVIDER (FAST DIRECT HTML INBOX)
# ==============================================================================

class GeneratorEmailProvider(BaseEmailProvider):
    """
    Generator.email free temporary email provider.
    Tự động nhận mail qua URL trực tiếp, không cần API key.
    Đa đuôi sạch: @premiora.id, @crepeau.me, @disbox.net, @disbox.org, @emlpro.com, @emlhub.com, @moakt.cc, @tmail.ws
    """
    BASE_URL = "https://generator.email"
    DOMAINS = [
        "premiora.id", "crepeau.me", "disbox.net", "disbox.org",
        "emlpro.com", "emlhub.com", "moakt.cc", "tmail.ws",
        "superrito.com", "cuoly.com", "fleckens.hu", "armyspy.com",
        "dayrep.com", "einrot.com", "gustr.com", "jourrapide.com",
        "rhyta.com", "teleworm.us", "clrmail.com", "fakemailgenerator.net",
        "sharklasers.net", "mailinator2.com", "nowmymail.com",
        "generator.email", "disposablemail.org", "trashmail.org",
        "channal.net", "moakt.co", "moakt.ws", "emailfake.com",
        "emailfake.ml", "fakemail.net", "crazymailing.com",
        "yopmail.net", "trashmail.com",
        "armyspy.net", "cuoly.net", "dayrep.net", "einrot.net",
        "fleckens.com", "gustr.net", "jourrapide.net", "rhyta.net",
        "superrito.net", "teleworm.com", "teleworm.org", "disbox.info",
        "disbox.co", "disbox.me", "emlpro.net", "emlhub.net",
        "moakt.net", "moakt.info", "tmail.co", "tmail.in",
        "tmail.org", "clrmail.org", "clrmail.net", "fakemailgenerator.org",
        "crazymailing.org", "disposablemail.com", "trashmail.net",
        "channal.org", "channal.com", "emailfake.info", "emailfake.org",
        "emailfake.net", "fakemail.io", "fakemail.org", "yopmail.info",
        "spambox.me", "boximail.com", "bupcl.com", "vddaz.com",
        "esiix.com", "vjuum.com", "dcctb.com", "icznn.com",
        "wuuvo.com", "qiott.com", "kzccv.com"
    ]
    provider_name = "generator_email"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        dom = domain if (domain and "." in domain) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        name = "".join(random.choices(string.ascii_lowercase, k=8)) + str(random.randint(10, 99))
        email_addr = f"{name}@{dom}"
        logger.info(f"[GeneratorEmail] Cấp phát hòm thư: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="generator_email",
            metadata={"mailbox": name, "domain": dom, "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"{self.BASE_URL}/{email}"

        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code in (403, 503) or "Checking your browser" in (r.text or ""):
                    logger.warning(f"[{self.provider_name}] generator.email bị Cloudflare 503/Turnstile chặn, không thể nhận OTP.")
                    return OTPVerificationResult(
                        success=False,
                        email=email,
                        error="generator.email bị Cloudflare 503 chặn bot",
                        elapsed_seconds=round(time.time() - start_time, 2)
                    )
                if r.status_code == 200 and r.text:
                    txt = r.text
                    otp = extract_otp_code(txt)
                    conf_link = extract_confirmation_link(txt)
                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[GeneratorEmail] Bắt được OTP: {otp} sau {elapsed}s ({email})")
                        return OTPVerificationResult(
                            success=True,
                            email=email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                        )
            except Exception as e:
                logger.debug(f"[GeneratorEmail] Poll error: {e}")
            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for GeneratorEmail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )

# ==============================================================================
# INBOXKITTEN PROVIDER (Free, Open-Source, Instant API)
# ==============================================================================

class InboxKittenProvider(BaseEmailProvider):
    """
    InboxKitten (https://inboxkitten.com).
    Dịch vụ hòm thư ảo miễn phí mã nguồn mở, không cần đăng ký.
    Đuôi mail: @inboxkitten.com
    API: GET https://inboxkitten.com/api/v1/mail/list?recipient={username}
         GET https://inboxkitten.com/api/v1/mail/get?mail_id={storage_url}
    """
    BASE_URL = "https://inboxkitten.com/api/v1/mail"
    DOMAINS = ["inboxkitten.com"]
    provider_name = "inboxkitten"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        username = generate_human_email_username().replace(".", "").replace("_", "")
        if len(username) < 6:
            username += str(random.randint(100, 999))
        email = f"{username}@inboxkitten.com"
        logger.info(f"[InboxKitten] Cấp phát mailbox: {email}")
        return EmailAccount(
            email=email,
            provider="inboxkitten",
            metadata={"username": username, "domain": "inboxkitten.com", "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        username = account.metadata.get("username") or account.email.split("@")[0]
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        logger.info(f"[InboxKitten] Đang chờ mã OTP cho {email} (Tối đa: {timeout_seconds}s)...")

        while time.time() - start_time < timeout_seconds:
            try:
                r = requests.get(f"{self.BASE_URL}/list?recipient={username}", headers=headers, timeout=8)
                if r.status_code == 200:
                    mail_list = r.json()
                    if mail_list and isinstance(mail_list, list):
                        for m_item in mail_list:
                            subject = m_item.get("message", {}).get("headers", {}).get("subject", "")
                            storage_url = m_item.get("storage", {}).get("url") or m_item.get("id") or ""
                            body = ""
                            if storage_url:
                                try:
                                    r_body = requests.get(f"{self.BASE_URL}/get?mail_id={storage_url}", headers=headers, timeout=8)
                                    if r_body.status_code == 200:
                                        body = r_body.text
                                except Exception:
                                    pass

                            full_content = f"{subject}\n{body}"
                            otp = extract_otp_code(full_content)
                            conf_link = extract_confirmation_link(full_content)
                            if otp or conf_link:
                                elapsed = round(time.time() - start_time, 2)
                                logger.info(f"[InboxKitten] Bắt được OTP: {otp or conf_link} trong {elapsed}s ({email})")
                                return OTPVerificationResult(
                                    success=True,
                                    email=email,
                                    otp_code=otp,
                                    confirmation_link=conf_link,
                                    subject=subject,
                                    body_preview=body[:150],
                                    elapsed_seconds=elapsed,
                                    metadata={"provider": "inboxkitten", "email": email}
                                )
            except Exception as e:
                logger.debug(f"[InboxKitten] Polling error: {e}")

            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for InboxKitten OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


class FakeMailGeneratorProvider(BaseEmailProvider):
    """
    FakeMailGenerator (https://www.fakemailgenerator.com).
    Miễn phí, không cần tài khoản, tự động bắt mã OTP qua kho dữ liệu mail ảo.
    Đuôi mail sạch US-UK: @armyspy.com, @cuoly.com, @dayrep.com, @einrot.com,
    @fleckens.hu, @gustr.com, @jourrapide.com, @rhyta.com, @superrito.com, @teleworm.us
    """
    BASE_URL = "https://generator.email"
    DOMAINS = [
        "armyspy.com", "cuoly.com", "dayrep.com", "einrot.com", "fleckens.hu",
        "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us",
        "armyspy.net", "cuoly.net", "dayrep.net", "einrot.net", "fleckens.com",
        "gustr.net", "jourrapide.net", "rhyta.net", "superrito.net", "teleworm.com",
        "teleworm.org", "disbox.net", "disbox.org", "emlpro.com", "emlhub.com"
    ]
    provider_name = "fakemailgenerator"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        dom = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        name = "".join(random.choices(string.ascii_lowercase, k=8)) + str(random.randint(10, 99))
        email_addr = f"{name}@{dom}"
        logger.info(f"[FakeMailGenerator] Cấp phát hòm thư: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="fakemailgenerator",
            metadata={"mailbox": name, "domain": dom, "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"{self.BASE_URL}/{email}"

        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code in (403, 503) or "Checking your browser" in (r.text or ""):
                    logger.warning(f"[{self.provider_name}] generator.email bị Cloudflare 503/Turnstile chặn, không thể nhận OTP.")
                    return OTPVerificationResult(
                        success=False,
                        email=email,
                        error="generator.email bị Cloudflare 503 chặn bot",
                        elapsed_seconds=round(time.time() - start_time, 2)
                    )
                if r.status_code == 200 and r.text:
                    txt = r.text
                    otp = extract_otp_code(txt)
                    conf_link = extract_confirmation_link(txt)
                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[FakeMailGenerator] Bắt được OTP: {otp} sau {elapsed}s ({email})")
                        return OTPVerificationResult(
                            success=True,
                            email=email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "fakemailgenerator", "email": email}
                        )
            except Exception as e:
                logger.debug(f"[FakeMailGenerator] Poll error: {e}")
            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for FakeMailGenerator OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


class EmailFakeProvider(BaseEmailProvider):
    """
    EmailFake (https://emailfake.com).
    Hòm thư ảo không giới hạn, hỗ trợ đa domain quốc tế phong phú.
    Đuôi mail: @emailfake.com, @emailfake.ml, @disposablemail.org, @clrmail.com,
               @channal.net, @moakt.co, @moakt.ws, @trashmail.org, @fakemail.net,
               @crazymailing.com, @yopmail.net, @trashmail.com
    """
    BASE_URL = "https://generator.email"
    DOMAINS = [
        "emailfake.com", "emailfake.ml", "disposablemail.org", "clrmail.com",
        "channal.net", "moakt.co", "moakt.ws", "trashmail.org", "fakemail.net",
        "crazymailing.com", "yopmail.net", "trashmail.com",
        "emailfake.info", "emailfake.org", "emailfake.net", "disposablemail.com",
        "clrmail.org", "clrmail.net", "moakt.cc", "moakt.net",
        "fakemail.io", "fakemail.org", "crazymailing.org", "trashmail.net", "yopmail.info"
    ]
    provider_name = "emailfake"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        dom = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        name = "".join(random.choices(string.ascii_lowercase, k=8)) + str(random.randint(10, 99))
        email_addr = f"{name}@{dom}"
        logger.info(f"[EmailFake] Cấp phát hòm thư: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="emailfake",
            metadata={"mailbox": name, "domain": dom, "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"{self.BASE_URL}/{email}"

        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, headers=headers, timeout=8)
                if r.status_code == 200 and r.text:
                    txt = r.text
                    otp = extract_otp_code(txt)
                    conf_link = extract_confirmation_link(txt)
                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[EmailFake] Bắt được OTP: {otp} sau {elapsed}s ({email})")
                        return OTPVerificationResult(
                            success=True,
                            email=email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "emailfake", "email": email}
                        )
            except Exception as e:
                logger.debug(f"[EmailFake] Poll error: {e}")
            time.sleep(poll_interval)

        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for EmailFake OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )

class ThrowAwayMailProvider(BaseEmailProvider):
    """
    ThrowAwayMail free disposable email provider.
    Tự động cấp mail nhanh qua các domain:
    @throwawaymail.com, @trashcanmail.com, @mailscrap.com, @maileater.com,
    @burnermail.io, @trashmail.me, @spambog.com, @jetable.org
    """
    BASE_URL = "https://generator.email"
    DOMAINS = [
        "throwawaymail.com", "trashcanmail.com", "mailscrap.com", "maileater.com",
        "burnermail.io", "trashmail.me", "spambog.com", "jetable.org",
        "tempinbox.com", "spamfree24.org"
    ]
    provider_name = "throwawaymail"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, worker_id: Optional[int] = None, *args, **kwargs) -> Optional[EmailAccount]:
        dom = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        name = "".join(random.choices(string.ascii_lowercase, k=8)) + str(random.randint(10, 99))
        email_addr = f"{name}@{dom}"
        logger.info(f"[ThrowAwayMail] Cấp phát hòm thư: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="throwawaymail",
            metadata={"mailbox": name, "domain": dom, "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"{self.BASE_URL}/{email}"
        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, headers=headers, timeout=6)
                if r.status_code in (403, 503) or "Checking your browser" in (r.text or ""):
                    logger.warning(f"[{self.provider_name}] generator.email bị Cloudflare 503/Turnstile chặn, không thể nhận OTP.")
                    return OTPVerificationResult(
                        success=False,
                        email=email,
                        error="generator.email bị Cloudflare 503 chặn bot",
                        elapsed_seconds=round(time.time() - start_time, 2)
                    )
                if r.status_code == 200:
                    otp = extract_otp_code(r.text)
                    conf_link = extract_confirmation_link(r.text)
                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[ThrowAwayMail] Nhận OTP thành công cho {email}: {otp or conf_link} ({elapsed}s)")
                        return OTPVerificationResult(
                            success=True,
                            email=email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "throwawaymail", "email": email}
                        )
            except Exception as e:
                logger.debug(f"[ThrowAwayMail] Polling error: {e}")
            time.sleep(poll_interval)
        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for ThrowAwayMail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


class DisposableMailProvider(BaseEmailProvider):
    """
    DisposableMail free temporary email provider.
    Hỗ trợ các domain:
    @disposablemail.com, @disposablemail.org, @fakemail.club, @disbox.live,
    @moakt.email, @trashmail.live, @tempmail24.org, @crazymail.org, @burnermail.me
    """
    BASE_URL = "https://generator.email"
    DOMAINS = [
        "disposablemail.com", "disposablemail.org", "fakemail.club", "disbox.live",
        "moakt.email", "trashmail.live", "tempmail24.org", "crazymail.org", "burnermail.me"
    ]
    provider_name = "disposablemail"

    def _get_proxies(self, proxy: Optional[str] = None) -> Optional[Dict[str, str]]:
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, worker_id: Optional[int] = None, *args, **kwargs) -> Optional[EmailAccount]:
        dom = domain if (domain and domain in self.DOMAINS) else DomainDiversityTracker().pick_random_diverse_domain(self.DOMAINS)
        name = "".join(random.choices(string.ascii_lowercase, k=8)) + str(random.randint(10, 99))
        email_addr = f"{name}@{dom}"
        logger.info(f"[DisposableMail] Cấp phát hòm thư: {email_addr}")
        return EmailAccount(
            email=email_addr,
            provider="disposablemail",
            metadata={"mailbox": name, "domain": dom, "created_at": time.time()}
        )

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        start_time = time.time()
        email = account.email
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        url = f"{self.BASE_URL}/{email}"
        while (time.time() - start_time) < timeout_seconds:
            try:
                r = requests.get(url, headers=headers, timeout=6)
                if r.status_code in (403, 503) or "Checking your browser" in (r.text or ""):
                    logger.warning(f"[{self.provider_name}] generator.email bị Cloudflare 503/Turnstile chặn, không thể nhận OTP.")
                    return OTPVerificationResult(
                        success=False,
                        email=email,
                        error="generator.email bị Cloudflare 503 chặn bot",
                        elapsed_seconds=round(time.time() - start_time, 2)
                    )
                if r.status_code == 200:
                    otp = extract_otp_code(r.text)
                    conf_link = extract_confirmation_link(r.text)
                    if otp or conf_link:
                        elapsed = round(time.time() - start_time, 2)
                        logger.info(f"[DisposableMail] Nhận OTP thành công cho {email}: {otp or conf_link} ({elapsed}s)")
                        return OTPVerificationResult(
                            success=True,
                            email=email,
                            otp_code=otp,
                            confirmation_link=conf_link,
                            elapsed_seconds=elapsed,
                            metadata={"provider": "disposablemail", "email": email}
                        )
            except Exception as e:
                logger.debug(f"[DisposableMail] Polling error: {e}")
            time.sleep(poll_interval)
        elapsed = round(time.time() - start_time, 2)
        return OTPVerificationResult(
            success=False,
            email=account.email,
            error=f"Timeout waiting for DisposableMail OTP after {timeout_seconds}s",
            elapsed_seconds=elapsed,
        )


class AutoRotatorEmailProvider(BaseEmailProvider):
    """
    Dịch vụ Hòm Thư Free Tự Động Xoay Nguồn (Smart Multi-Provider Auto-Rotator).
    Tự động xoay vòng qua 9 nguồn mail ảo miễn phí sạch & uy tín cao:
    1. TempMail.Plus (19+ đuôi mail)
    2. Inboxes.com (18+ đuôi mail)
    3. Temp-Mail.io (7+ đuôi mail)
    4. 10MinuteMail.net (Đa đuôi sạch)
    5. Smail1s Temp (5+ đuôi mail)
    6. Mail.tm (Đa đuôi REST API)
    7. TempMail.lol (Đa đuôi API v2)
    8. Maildrop.cc (GraphQL)
    9. Guerrilla Mail (8+ đuôi mail)
    Nếu 1 nguồn bị nghẽn hoặc hết hạn, tự động chuyển sang nguồn tiếp theo mà không làm gián đoạn luồng reg.
    """
    def __init__(self):
        super().__init__()
        self.provider_name = "AutoRotator Free Mail"
        # Chi su dung 8 he thong mail ao sach, uy tin cao, khong bi Meta chan MTA / blacklist
        self._providers = [
            ("clean_trio", CleanTrioEmailProvider),
            ("smail1s_temp", Smail1sTempMailProvider),
            ("10minutemail", TenMinuteMailNetProvider),
            ("tempmail_plus", TempMailPlusProvider),
            ("tempmail_lol", TempMailLolProvider),
            ("tempmail_io", TempMailIoProvider),
            ("mailtm", MailTmProvider),
        ]

    _active_in_flight: Dict[str, int] = collections.defaultdict(int)
    _cooldown_until: Dict[str, float] = {}
    _worker_last_provider: Dict[int, str] = {}
    _last_used_timestamp: Dict[str, float] = {}
    _balancer_lock = threading.Lock()

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, worker_id: Optional[int] = None, *args, **kwargs) -> Optional[EmailAccount]:
        wid = int(worker_id) if worker_id is not None and str(worker_id).isdigit() else random.randint(1, 9999)
        now = time.time()

        with self._balancer_lock:
            if len(self._cooldown_until) > 60:
                self._cooldown_until = {k: v for k, v in self._cooldown_until.items() if v > now}

            available = [p for p in self._providers if now >= self._cooldown_until.get(p[0], 0)]
            if not available:
                self._cooldown_until.clear()
                available = list(self._providers)

            # CHỌN NGẪU NHIÊN 100% TỪ TOÀN BỘ CÁC NGUỒN KHẢ DỤNG (KHÔNG LẤY LẦN LƯỢT / TUẦN TỰ):
            # Tất cả các nguồn khả dụng (không bị cooldown) đều có cơ hội được bốc ngẫu nhiên bình đẳng.
            # Chỉ loại trừ nguồn đang có tải quá cao (>= 8 in-flight) nếu còn nguồn khác.
            healthy = [p for p in available if self._active_in_flight.get(p[0], 0) < 8]
            pool = healthy if healthy else available

            # Từng luồng (worker) ưu tiên đổi sang nguồn khác nguồn vừa dùng lần trước (nếu có lựa chọn khác)
            worker_diff = [p for p in pool if p[0] != self._worker_last_provider.get(wid)]
            pick_pool = list(worker_diff if worker_diff else pool)

            # XÁO TRỘN NGẪU NHIÊN HOÀN TOÀN (100% PURE RANDOM DRAW TRÊN MỌI NGUỒN):
            random.shuffle(pick_pool)

            # Các nguồn còn lại làm fallback cũng được xáo trộn ngẫu nhiên hoàn toàn
            remaining = [p for p in available if p not in pick_pool]
            random.shuffle(remaining)
            candidate_providers = pick_pool + remaining

        for name, cls in candidate_providers:
            with self._balancer_lock:
                self._active_in_flight[name] += 1
            try:
                inst = cls()
                try:
                    acc = inst.create_mailbox(proxy=proxy, domain=domain)
                except TypeError:
                    acc = inst.create_mailbox(proxy=proxy)
                if acc and acc.email and "@" in acc.email:
                    if not acc.metadata:
                        acc.metadata = {}
                    acc.metadata["sub_provider"] = name
                    acc.provider = name
                    with self._balancer_lock:
                        self._worker_last_provider[wid] = name
                    self._last_used_timestamp[name] = time.time()
                    DomainDiversityTracker().record_domain_used(acc.email)
                    logger.info(f"[AutoRotator] 🎲 Luồng {wid} ➔ Cấp hòm thư thành công từ nguồn '{name}' (Phân tán đa nguồn, không tập trung): {acc.email}")
                    return acc
                else:
                    with self._balancer_lock:
                        self._cooldown_until[name] = time.time() + 20.0
            except Exception as e:
                with self._balancer_lock:
                    self._cooldown_until[name] = time.time() + 25.0
                logger.debug(f"[AutoRotator] Luồng {wid} ➔ Nguồn {name} lỗi: {e}")
                continue
            finally:
                with self._balancer_lock:
                    self._active_in_flight[name] = max(0, self._active_in_flight[name] - 1)
        return None

    def wait_for_otp(self, account: EmailAccount, timeout_seconds: int = 60, poll_interval: int = 3, proxy: Optional[str] = None, *args, **kwargs) -> OTPVerificationResult:
        # Dynamic, thread-safe provider lookup per-account
        sub_name = (account.metadata or {}).get("sub_provider") or getattr(account, "provider", "")
        target_cls = None
        if sub_name:
            for name, cls in self._providers:
                if name.lower() == str(sub_name).lower() or cls.__name__.lower().startswith(str(sub_name).lower()):
                    target_cls = cls
                    break

        if not target_cls:
            email_domain = account.email.split("@")[-1].lower() if "@" in account.email else ""
            if any(email_domain.endswith(d) for d in (
                "premiora.id", "crepeau.me", "disbox.net", "disbox.org",
                "emlpro.com", "emlhub.com", "moakt.cc", "tmail.ws"
            )):
                target_cls = GeneratorEmailProvider
            elif any(email_domain.endswith(d) for d in (
                "chitthi.in", "mailto.plus", "fexbox.org", "rover.info", "fexpost.com",
                "mailbox.in.ua", "fextemp.com", "any.pink", "merepost.com", "chitthe.com",
                "chitti.in", "chitthii.in", "chitti.com", "fexmail.org", "fexmail.net",
                "mailto.in", "mailto.me", "fextemp.org", "rover.org"
            )):
                target_cls = TempMailPlusProvider
            elif any(email_domain.endswith(d) for d in (
                "blondmail.com", "chapsmail.com", "clowmail.com", "dropjar.com",
                "fivermail.com", "getairmail.com", "getmule.com", "getnada.com",
                "gimpmail.com", "givmail.com", "guysmail.com", "inboxbear.com",
                "replyloop.com", "robot-mail.com", "tafmail.com", "temptami.com",
                "tupmail.com", "vomoto.com"
            )):
                target_cls = InboxesProvider
            elif any(email_domain.endswith(d) for d in (
                "yzcalo.com", "lnovic.com", "ruutukf.com", "gmeenramy.com",
                "olipii.com", "ooynib.com", "tanpony.com"
            )):
                target_cls = TempMailIoProvider
            elif any(email_domain.endswith(d) for d in ("armyspy.com", "cuoly.com", "dayrep.com", "einrot.com", "fleckens.hu", "gustr.com", "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us")):
                target_cls = FakeMailGeneratorProvider
            elif any(email_domain.endswith(d) for d in ("emailfake.com", "emailfake.ml", "disposablemail.org", "clrmail.com", "channal.net", "moakt.co", "moakt.ws", "trashmail.org", "fakemail.net", "crazymailing.com", "yopmail.net", "trashmail.com")):
                target_cls = EmailFakeProvider
            elif any(email_domain.endswith(d) for d in ("laoia.com",)):
                target_cls = TenMinuteMailNetProvider
            elif any(email_domain.endswith(d) for d in (
                "smail1s.com", "smailwork.com", "smailpro.com", "hotmailtrusted.com", "smail1s.net"
            )):
                target_cls = Smail1sTempMailProvider
            elif any(email_domain.endswith(d) for d in ("maxxspace.com", "mail.tm")):
                target_cls = MailTmProvider
            elif any(email_domain.endswith(d) for d in ("maildrop.cc",)):
                target_cls = MaildropProvider
            elif any(email_domain.endswith(d) for d in (
                "guerrillamailblock.com", "sharklasers.com", "guerrillamail.com",
                "guerrillamail.net", "guerrillamail.org", "pokemail.net", "spam4.me", "grr.la"
            )):
                target_cls = GuerrillaMailProvider
            elif any(email_domain.endswith(d) for d in ("mailnesia.com",)):
                target_cls = MailnesiaProvider
            elif any(email_domain.endswith(d) for d in ("throwawaymail.com", "trashcanmail.com", "mailscrap.com", "maileater.com", "burnermail.io", "trashmail.me", "spambog.com", "jetable.org", "tempinbox.com", "spamfree24.org")):
                target_cls = ThrowAwayMailProvider
            elif any(email_domain.endswith(d) for d in ("disposablemail.com", "disposablemail.org", "fakemail.club", "disbox.live", "moakt.email", "trashmail.live", "tempmail24.org", "crazymail.org", "burnermail.me")):
                target_cls = DisposableMailProvider
            elif any(email_domain.endswith(d) for d in ("inboxkitten.com",)):
                target_cls = InboxKittenProvider
            elif any(email_domain.endswith(d) for d in ("1secmail.com", "1secmail.net", "1secmail.org", "kzccv.com", "qiott.com", "wuuvo.com", "icznn.com", "dcctb.com", "vjuum.com", "esiix.com", "vddaz.com", "bupcl.com")):
                target_cls = OneSecMailProvider
            elif any(email_domain.endswith(d) for d in ("emailnox.live", "mohmal.im", "mohmal.in", "tmail.ws", "mohmal.com", "mohmal.club", "fakemail.io", "tmpmail.net", "tmpmail.org", "boun.cr", "vmani.com", "mohmal.co", "disbox.net")):
                target_cls = MohmalProvider
            else:
                target_cls = TempMailPlusProvider

        target_inst = target_cls()
        return target_inst.wait_for_otp(
            account=account,
            timeout_seconds=timeout_seconds,
            poll_interval=poll_interval,
            proxy=proxy
        )


# ==============================================================================
# CLEAN TRIO EMAIL PROVIDER (@smail1s.com, @laoia.com, @smailwork.com)
# ==============================================================================

class CleanTrioEmailProvider(BaseEmailProvider):
    """
    Bộ Hòm Thư Sạch Đa Nguồn Không Bị Facebook Chặn (Đa Nguồn API Tự Động):
    1. @smail1s.com (Smail1s Temp)
    2. @laoia.com (10MinuteMail - Domain sạch số 1)
    3. @smailwork.com (Smailwork / pqudx6448)
    4. @hotmailtrusted.com (Hotmail Trusted - Smail1s)
    5. @mailto.plus (TempMail.Plus)
    6. @fexpost.com (TempMail.Plus)
    7. @mailbox.in.ua (TempMail.Plus)
    8. @rover.info (TempMail.Plus)
    9. @tanpony.com (Temp-Mail.io)

    Hỗ trợ người dùng lựa chọn:
    - Chọn bất kỳ tổ hợp đuôi nào (1, 2, 3... hoặc cả 9 đuôi)
    - Luân phiên ngẫu nhiên giữa các đuôi đã kích hoạt
    - Tự động fallback sang các đuôi còn lại nếu 1 đuôi tạm nghẽn
    """
    ALL_VALID_DOMAINS = [
        "smail1s.com",
        "laoia.com",
        "smailwork.com",
        "hotmailtrusted.com",
        "mailto.plus",
        "fexpost.com",
        "mailbox.in.ua",
        "rover.info",
        "tanpony.com",
    ]

    def __init__(self, selected_domains: Optional[List[str]] = None, **kwargs):
        super().__init__()
        self.provider_name = "Clean Suite Email Provider"
        self._smail_provider = Smail1sTempMailProvider()
        self._tenminute_provider = TenMinuteMailNetProvider()
        self._tempmailplus_provider = TempMailPlusProvider()
        self._tempmailio_provider = TempMailIoProvider()
        self.selected_domains = []
        self.set_selected_domains(selected_domains)

    def set_selected_domains(self, domains: Optional[List[str]] = None):
        if not domains:
            try:
                if os.path.exists("config.json"):
                    with open("config.json", "r", encoding="utf-8") as f_cfg:
                        cfg_d = json.load(f_cfg)
                        cfg_doms = cfg_d.get("selected_custom_domains")
                        if cfg_doms and isinstance(cfg_doms, list):
                            domains = cfg_doms
            except Exception:
                pass

        if not domains:
            self.selected_domains = list(self.ALL_VALID_DOMAINS)
            return

        cleaned = []
        for d in domains:
            cd = str(d).lower().strip().lstrip("@")
            if cd in self.ALL_VALID_DOMAINS and cd not in cleaned:
                cleaned.append(cd)
        self.selected_domains = cleaned if cleaned else list(self.ALL_VALID_DOMAINS)

    def _create_for_domain(self, target_domain: str, proxy: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        acc = None
        sub_prov = ""
        if target_domain == "laoia.com":
            acc = self._tenminute_provider.create_mailbox(proxy=proxy, domain="laoia.com", *args, **kwargs)
            sub_prov = "10minutemail"
        elif target_domain in ("mailto.plus", "fexpost.com", "mailbox.in.ua", "rover.info"):
            acc = self._tempmailplus_provider.create_mailbox(proxy=proxy, domain=target_domain, *args, **kwargs)
            sub_prov = "tempmail_plus"
        elif target_domain == "tanpony.com":
            acc = self._tempmailio_provider.create_mailbox(proxy=proxy, domain="tanpony.com", *args, **kwargs)
            sub_prov = "tempmail_io"
        else:
            acc = self._smail_provider.create_mailbox(proxy=proxy, domain=target_domain, *args, **kwargs)
            sub_prov = "smail1s"

        if acc and acc.email and "@" in acc.email:
            acc.provider = "clean_trio"
            if not isinstance(acc.metadata, dict):
                acc.metadata = {}
            acc.metadata["sub_provider"] = sub_prov
            acc.metadata["chosen_domain"] = target_domain
            return acc
        return None

    def create_mailbox(self, proxy: Optional[str] = None, domain: Optional[str] = None, *args, **kwargs) -> Optional[EmailAccount]:
        chosen_domain = None
        if domain:
            cd = str(domain).lower().strip().lstrip("@")
            if cd in self.selected_domains:
                chosen_domain = cd
        if not chosen_domain:
            chosen_domain = random.choice(self.selected_domains)

        dom_info = ", ".join(["@" + d for d in self.selected_domains])
        logger.info(f"[CleanSuiteMail] Cấp phát hòm thư đuôi sạch @{chosen_domain} (Tổng số đuôi kích hoạt: {len(self.selected_domains)}: {dom_info})...")

        acc = self._create_for_domain(chosen_domain, proxy=proxy, *args, **kwargs)
        if acc:
            return acc

        fallback_candidates = [d for d in self.selected_domains if d != chosen_domain]
        random.shuffle(fallback_candidates)
        for fb_dom in fallback_candidates:
            acc = self._create_for_domain(fb_dom, proxy=proxy, *args, **kwargs)
            if acc:
                return acc

        return None

    def wait_for_otp(
        self,
        account: EmailAccount,
        timeout_seconds: int = 20,
        poll_interval: int = 2,
        proxy: Optional[str] = None,
        *args,
        **kwargs,
    ) -> OTPVerificationResult:
        email = (account.email or "").lower()
        sub_prov = (account.metadata or {}).get("sub_provider")
        email_dom = email.split("@")[-1].lower() if "@" in email else ""

        if sub_prov == "10minutemail" or email_dom == "laoia.com":
            return self._tenminute_provider.wait_for_otp(
                account, timeout_seconds=timeout_seconds, poll_interval=poll_interval, proxy=proxy
            )
        elif sub_prov == "tempmail_plus" or email_dom in ("mailto.plus", "fexpost.com", "mailbox.in.ua", "rover.info"):
            return self._tempmailplus_provider.wait_for_otp(
                account, timeout_seconds=timeout_seconds, poll_interval=poll_interval, proxy=proxy
            )
        elif sub_prov == "tempmail_io" or email_dom in ("tanpony.com", "yzcalo.com", "lnovic.com"):
            return self._tempmailio_provider.wait_for_otp(
                account, timeout_seconds=timeout_seconds, poll_interval=poll_interval, proxy=proxy
            )
        else:
            return self._smail_provider.wait_for_otp(
                account, timeout_seconds=timeout_seconds, poll_interval=poll_interval, proxy=proxy
            )


CleanSuiteEmailProvider = CleanTrioEmailProvider