# -*- coding: utf-8 -*-

"""

core.models

Domain models and DTOs (Data Transfer Objects) for automation tasks.

"""



from dataclasses import dataclass, field, asdict

from typing import Optional, Dict, Any, Union

from urllib.parse import quote





@dataclass

class ProxyItem:

    """Standardized representation of a single proxy."""

    host: str

    port: int

    username: Optional[str] = None

    password: Optional[str] = None

    protocol: str = "http"

    country: str = "Unknown"

    country_code: str = ""

    locale: str = ""

    timezone: str = ""

    language: str = ""

    raw: str = ""

    is_alive: bool = True

    fail_count: int = 0

    success_count: int = 0

    real_ip: Optional[str] = None

    carrier: Optional[str] = None

    mcc: Optional[str] = None

    mnc: Optional[str] = None

    sim_country_iso: Optional[str] = None

    latency: Optional[float] = None



    def as_url(self) -> str:

        """Return formatted URL string: scheme://[user:pass@]host:port"""

        scheme = self.protocol.lower() if self.protocol else "http"

        if self.username and self.password:

            safe_u = quote(self.username, safe="")

            safe_p = quote(self.password, safe="")

            return f"{scheme}://{safe_u}:{safe_p}@{self.host}:{self.port}"

        return f"{scheme}://{self.host}:{self.port}"



    def to_requests_dict(self) -> Dict[str, str]:

        """Convert to requests/urllib3 proxies dict."""

        url = self.as_url()

        return {"http": url, "https": url}



    def to_curl_cffi_proxy(self) -> str:

        """Convert to curl_cffi compatible proxy string."""

        return self.as_url()





@dataclass

class RegistrationInput:

    """Input parameters for a registration task."""

    identifier: str = ""

    password: Optional[str] = None

    first_name: Optional[str] = None

    last_name: Optional[str] = None

    birthday: Optional[str] = None

    gender: Optional[str] = None

    proxy: Optional[Union[str, ProxyItem, Dict[str, Any]]] = None

    device_type: str = "Android"

    browser_type: str = "Default"

    locale: str = ""

    server: str = "m.facebook.com"

    extra: Dict[str, Any] = field(default_factory=dict)





@dataclass

class RegistrationResult:

    """Standardized execution result returned by registration services."""

    success: bool

    status: str

    identifier: str = ""

    uid: Optional[str] = None

    password: Optional[str] = None

    token: Optional[str] = None

    cookies: Optional[Dict[str, str]] = None

    cookie_string: Optional[str] = None

    two_factor_secret: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None


    email_password: Optional[str] = None

    email_raw: Optional[str] = None

    email_rest: Optional[str] = None

    name: Optional[str] = None

    birthday: Optional[str] = None

    gender: Optional[str] = None

    error_message: Optional[str] = None

    elapsed_seconds: float = 0.0

    metadata: Dict[str, Any] = field(default_factory=dict)



    def to_dict(self) -> Dict[str, Any]:

        """Convert result object into a pure dictionary."""

        return asdict(self)



    def format_line(self, format_pattern: str = "UID|PASS|COOKIE|TOKEN|EMAIL") -> str:

        """Format the account result according to custom pattern (UID|PASS|COOKIE|TOKEN|EMAIL...)."""

        if not format_pattern:

            format_pattern = "UID|PASS|COOKIE|TOKEN|EMAIL"



        mail_rest = (self.email_rest or "").strip()

        if not mail_rest and self.email_raw:

            parts = self.email_raw.split("|", 1)

            if len(parts) > 1:

                mail_rest = parts[1].strip()



        mail_pass = (self.email_password or "").strip()

        if not mail_pass and mail_rest:

            mail_pass = mail_rest.split("|")[0].strip()



        raw_mail_val = self.email_raw or (f"{self.email}|{mail_rest}" if mail_rest else (self.email or ""))



        # Khi nguoi dung dung token EMAIL nhung khong co cac token boc tach chi tiet:

        # Thi EMAIL duoc thay the bang TOAN BO THANH PHAN MAIL nhu luc dan vao tool

        pattern_upper = format_pattern.upper()

        has_specific_mail_tokens = any(

            k in pattern_upper for k in (

                "PASS_MAIL", "PASSEMAIL", "MAIL_PASS", "HOTMAIL_PASS",

                "MAIL_REST", "HOTMAIL_REST",

                "RAW_MAIL", "RAW_EMAIL", "HOTMAIL_RAW"

            )

        )



        email_val = (raw_mail_val if (raw_mail_val and not has_specific_mail_tokens) else (self.email or (self.identifier if "@" in str(self.identifier or "") else "") or ""))



        replacements = {

            "RAW_EMAIL": raw_mail_val,

            "HOTMAIL_RAW": raw_mail_val,

            "RAW_MAIL": raw_mail_val,

            "HOTMAIL_PASS": mail_pass,

            "PASS_MAIL": mail_pass,

            "PASSEMAIL": mail_pass,

            "MAIL_PASS": mail_pass,

            "HOTMAIL_REST": mail_rest,

            "MAIL_REST": mail_rest,

            "COOKIE": self.cookie_string or "",

            "CCOOKIE": self.cookie_string or "",

            "COOKIES": self.cookie_string or "",

            "TOKEN": self.token or "",

            "EMAIL": email_val,
            "PHONE": self.phone or (self.identifier if ("@" not in str(self.identifier or "")) else "") or "",


            "PASS": self.password or "",

            "PASSWORD": self.password or "",

            "UID": self.uid or "",

            "2FA": self.two_factor_secret or "",

            "NAME": self.name or "",

            "BIRTHDAY": self.birthday or "",

        }



        # Ho tro ca dinh dang chu thuong, chu hoa hoac viet hoa chu cai dau (uid|pass|cookie...)

        ci_map = {}

        for k, v in replacements.items():

            ci_map[k] = v

            ci_map[k.lower()] = v

            ci_map[k.capitalize()] = v



        import re

        token_regex = r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, ci_map.keys()), key=len, reverse=True)) + r")(?![A-Za-z0-9_])"

        return re.sub(token_regex, lambda m: str(ci_map.get(m.group(0), "")), format_pattern)

