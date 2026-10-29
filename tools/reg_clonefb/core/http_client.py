# -*- coding: utf-8 -*-

"""

core.http_client

Standalone HTTP Client managing TLS Fingerprinting (curl_cffi) and Proxy rotation.

Decoupled from UI and business logic.

"""



import time

import logging

import urllib3

try:

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

except Exception:

    pass

from typing import Dict, Any, Optional, Union

from curl_cffi import requests

from curl_cffi.requests.errors import RequestsError



from core.models import ProxyItem



logger = logging.getLogger(__name__)





class HttpClientError(Exception):

    """Base exception for HTTP client operations."""

    pass





class ProxyConnectionError(HttpClientError):

    """Raised when a proxy fails to connect."""

    pass





class RequestTimeoutError(HttpClientError):

    """Raised when a request exceeds timeout limit."""

    pass





# Map device types to TLS impersonation presets

VALID_IMPERSONATE_PRESETS = {
    'chrome99', 'chrome100', 'chrome101', 'chrome104', 'chrome107', 'chrome110',
    'chrome116', 'chrome119', 'chrome120', 'chrome123', 'chrome124', 'chrome131',
    'chrome133a', 'chrome136', 'chrome142', 'chrome99_android', 'chrome131_android',
    'edge99', 'edge101', 'safari15_3', 'safari15_5', 'safari17_0', 'safari17_2_ios',
    'safari18_0', 'safari18_0_ios', 'firefox133', 'firefox135', 'firefox144',
}

def sanitize_impersonate(imp: Optional[str]) -> str:
    if not imp:
        return "chrome131_android"
    s = str(imp).strip().lower()
    if s in VALID_IMPERSONATE_PRESETS:
        return s
    if "android" in s:
        return "chrome131_android"
    if "ios" in s or "iphone" in s:
        return "safari17_2_ios"
    if "safari" in s:
        return "safari17_0"
    if "firefox" in s:
        return "firefox133"
    if "edge" in s:
        return "edge101"
    return "chrome131_android"

DEVICE_TLS_MAPPING = {

    "Android": "chrome107",

    "AndroidApp": "chrome107",

    "Desktop": "chrome131",

    "Chrome": "chrome131",

    "IphoneApp": "safari15_3",

    "iOS": "safari15_3",

    "Safari": "safari15_3",
    "KaiOS": None,
    "WindowsPhone": None,
    "BlackBerry": None,
    "fb_app": "chrome107",
    "katana": "chrome107",
    "fb4a": "chrome107",
    "mr_sxr": "chrome107",
    "sxr_ua": "chrome107",
    "android_katana": "chrome107",
}





class HttpClient:

    """

    Independent TLS-fingerprinted HTTP client based on curl_cffi.

    Provides automated proxy routing, retries, cookie extraction, and session persistence.

    """



    def __init__(

        self,

        impersonate: Optional[str] = None,

        device_type: Optional[str] = None,

        proxy: Optional[Union[str, ProxyItem, Dict[str, str]]] = None,

        timeout: int = 35,

        max_retries: int = 2,

        backoff_seconds: float = 1.0,

        headers: Optional[Dict[str, str]] = None,

        profile: Optional[Any] = None,

    ):

        # Resolve TLS impersonation preset
        if profile and hasattr(profile, "impersonate") and profile.impersonate:

            self.impersonate = profile.impersonate
            if self.impersonate == "safari16_0":
                self.impersonate = "safari17_0"

            self.profile = profile

        elif impersonate:

            self.impersonate = impersonate

            self.profile = None

        elif device_type and (device_type in DEVICE_TLS_MAPPING or any(k in str(device_type).lower() for k in ("mr_sxr", "mr.sxr", "sxr", "katana", "fb4a", "fb_app"))):

            dev_key = device_type if device_type in DEVICE_TLS_MAPPING else "katana"

            self.impersonate = DEVICE_TLS_MAPPING.get(dev_key, "chrome131_android")

            self.profile = None

        else:

            self.impersonate = "chrome131_android"

            self.profile = None



        if self.impersonate:
            self.impersonate = sanitize_impersonate(self.impersonate)
        self.timeout = timeout

        self.max_retries = max_retries

        self.backoff_seconds = backoff_seconds

        self.default_headers = headers or {}

        self.proxy_raw = proxy
        self.proxy = None

        self.user_agent = getattr(profile, "user_agent", "") if profile else ""
        if not self.user_agent and headers:
            self.user_agent = headers.get("User-Agent") or headers.get("user-agent") or ""



        # Initialize curl_cffi session with TLS impersonation

        self._session = self._create_session()

        if proxy:

            self.set_proxy(proxy)



    @property

    def session(self) -> requests.Session:

        return self._session



    def _reset_session_connections(self) -> None:
        """Reset the internal curl session to clear broken/dead sockets while preserving cookies & headers."""
        try:
            old_cookies = dict(self.get_cookies()) if hasattr(self, "get_cookies") else {}
            old_headers = dict(self._session.headers) if hasattr(self._session, "headers") else {}
            try:
                self._session.close()
            except Exception:
                pass
            self._session = self._create_session()
            self._session.headers.update(old_headers)
            for k, v in old_cookies.items():
                self.set_cookie(k, v)
            if getattr(self, "proxy_raw", None):
                self.set_proxy(self.proxy_raw)
        except Exception as e:
            logger.debug(f"Error resetting session: {e}")

    def _create_session(self) -> requests.Session:

        if self.impersonate:

            try:

                session = requests.Session(impersonate=self.impersonate, verify=False)

            except Exception as e:

                try:

                    session = requests.Session(impersonate=self.impersonate)

                    session.verify = False

                except Exception:

                    logger.warning(f"Failed to impersonate {self.impersonate}: {e}. Falling back to default.")

                    session = requests.Session()

                    session.verify = False

        else:

            session = requests.Session()

            session.verify = False



        if self.default_headers:

            session.headers.update(self.default_headers)

        return session



    def set_proxy(self, proxy: Optional[Union[str, ProxyItem, Dict[str, str]]]) -> None:

        """Dynamically attach or change the proxy on the underlying session."""

        self.proxy_raw = proxy

        if not proxy:

            self.proxy = None

            self._session.proxies.clear()

            return



        proxy_url = ""

        if isinstance(proxy, ProxyItem):

            proxy_url = proxy.as_url()

        elif isinstance(proxy, dict):

            proxy_url = proxy.get("http") or proxy.get("https") or ""

        elif isinstance(proxy, str):

            proxy_url = proxy.strip()



        if proxy_url:
            effective_proxy = proxy_url
            if effective_proxy.startswith("socks5://"):
                effective_proxy = "socks5h://" + effective_proxy[9:]
            self.proxy = effective_proxy
            self._session.proxies = {
                "http": effective_proxy,
                "https": effective_proxy,
            }



    def set_header(self, key: str, value: str) -> None:

        """Set a persistent header."""

        self._session.headers[key] = value



    def update_headers(self, headers: Dict[str, str]) -> None:

        """Update multiple persistent headers."""

        self._session.headers.update(headers)



    def set_headers(self, headers: Dict[str, str]) -> None:

        """Alias for update_headers."""

        self.update_headers(headers)



    def set_cookie(self, name: str, value: str, domain: str = ".facebook.com") -> None:

        """Set a single cookie safely avoiding curl_cffi NoneType startswith crash."""

        dom = domain if domain else ".facebook.com"
        try:
            self._session.cookies.set(name, value, domain=dom)
        except Exception:
            try:
                self._session.cookies.set(name, value)
            except Exception:
                pass



    def get_cookies(self) -> Dict[str, str]:

        """Return all cookies in dictionary format."""

        try:

            return self._session.cookies.get_dict()

        except Exception:

            return dict(self._session.cookies)



    def get_cookie_string(self) -> str:

        """Return cookies formatted as a header string (key=value; ...)."""

        cookies = self.get_cookies()

        return "; ".join(f"{k}={v}" for k, v in cookies.items())

    def clear_cookies(self) -> None:

        """Clear all cookies in the underlying session."""

        try:
            self._session.cookies.clear()
        except Exception:
            pass



    def request(

        self,

        method: str,

        url: str,

        params: Optional[Dict[str, Any]] = None,

        data: Optional[Any] = None,

        json: Optional[Any] = None,

        headers: Optional[Dict[str, str]] = None,

        timeout: Optional[int] = None,

        **kwargs

    ) -> requests.Response:

        """Execute HTTP request with automatic retries and clean error handling."""

        req_timeout = timeout if timeout is not None else self.timeout

        has_proxy = bool(getattr(self, "proxy_raw", None) or getattr(self, "proxy", None))
        if isinstance(req_timeout, (tuple, list)):
            c_val = float(req_timeout[0])
            r_val = float(req_timeout[1]) if len(req_timeout) > 1 else c_val
            if has_proxy:
                c_val = min(30.0, max(20.0, c_val))
                r_val = min(60.0, max(35.0, r_val))
            req_timeout = (c_val, r_val)
        elif isinstance(req_timeout, (int, float)):
            val = float(req_timeout)
            if has_proxy:
                # Toi uu connect timeout nhe nhang (8s - 12s) de fail-fast va xoay IP nhanh khi proxy nghen
                c_timeout = min(12.0, max(8.0, val * 0.4))
                r_timeout = min(25.0, max(15.0, val * 0.8))
            elif val <= 8.0:
                c_timeout = min(5.0, val)
                r_timeout = val
            elif val <= 15.0:
                c_timeout = min(8.0, val * 0.6)
                r_timeout = val
            else:
                c_timeout = min(15.0, val * 0.5)
                r_timeout = val
            req_timeout = (c_timeout, r_timeout)

        attempts = 0

        last_error = None

        redir_depth = kwargs.pop("_redirect_depth", 0)

        redir_visited = kwargs.pop("_redirect_visited", None)

        if redir_visited is None:

            redir_visited = set()



        eff_headers = dict(headers or {})
        for c_k in ("cookie", "Cookie", "COOKIE"):
            if c_k in eff_headers:
                raw_c = eff_headers.pop(c_k)
                if raw_c:
                    for part in str(raw_c).split(";"):
                        if "=" in part:
                            k_seg, v_seg = part.strip().split("=", 1)
                            k_s = k_seg.strip()
                            if k_s:
                                self.set_cookie(k_s, v_seg.strip(), domain=".facebook.com")
        # Loại bỏ triệt để các header rò rỉ proxy / IP máy thật tới Facebook
        leak_headers = ("x-forwarded-for", "x-real-ip", "client-ip", "via", "forwarded", "x-client-ip", "cf-connecting-ip")
        for lh in leak_headers:
            for k in list(eff_headers.keys()):
                if k.lower() == lh:
                    eff_headers.pop(k, None)
            if hasattr(self._session, "headers"):
                for k in list(self._session.headers.keys()):
                    if k.lower() == lh:
                        self._session.headers.pop(k, None)
        headers = eff_headers

        if "verify" not in kwargs:

            kwargs["verify"] = False



        while attempts <= self.max_retries:

            try:

                response = self._session.request(

                    method=method.upper(),

                    url=url,

                    params=params,

                    data=data,

                    json=json,

                    headers=headers,

                    timeout=req_timeout,

                    **kwargs

                )

                return response

            except RequestsError as e:

                err_msg = str(e).lower()

                last_error = e

                attempts += 1



                is_custom_scheme_err = any(k in err_msg for k in (

                    "unsupported url scheme",

                    "redirect target url could not be parsed",

                    "unsupported protocol",

                    "protocol 'fb'",

                    "invalidschema",

                    "no connection adapters were found for 'fb",

                    "fb://",

                    "scheme 'fb' not supported",

                ))

                if is_custom_scheme_err:

                    try:

                        no_redir_kwargs = dict(kwargs)

                        no_redir_kwargs["allow_redirects"] = False

                        r_safe = self._session.request(

                            method=method.upper(),

                            url=url,

                            params=params,

                            data=data,

                            json=json,

                            headers=headers,

                            timeout=req_timeout,

                            **no_redir_kwargs

                        )

                        loc = r_safe.headers.get("location", "")

                        if ("fbredirect://" in loc or "intent://" in loc) and "uri=" in loc and redir_depth < 3:

                            import urllib.parse

                            parsed_loc = urllib.parse.urlparse(loc)

                            qs = urllib.parse.parse_qs(parsed_loc.query)

                            target_http_uri = qs.get("uri", [""])[0]

                            clean_target = target_http_uri.split("?")[0].rstrip("/")

                            clean_curr = url.split("?")[0].rstrip("/")

                            if target_http_uri.startswith("http") and clean_target != clean_curr and target_http_uri not in redir_visited:

                                redir_visited.add(url)

                                redir_visited.add(target_http_uri)

                                redir_kwargs = dict(kwargs)

                                redir_kwargs["_redirect_depth"] = redir_depth + 1

                                redir_kwargs["_redirect_visited"] = redir_visited

                                return self.request(method, target_http_uri, params=params, data=data, json=json, headers=headers, timeout=timeout, **redir_kwargs)

                        return r_safe

                    except Exception:

                        pass



                is_hard_proxy_failure = any(k in err_msg for k in (
                    "could not resolve proxy", "curl: (5)", "curl: (6)",
                    "proxy authentication", "407 proxy authentication", "403 forbidden"
                ))
                if is_hard_proxy_failure:
                    # Lỗi cứng của proxy (chết cổng, sai địa chỉ IP, từ chối tunnel, cần xác thực): lập tức raise để worker đổi IP mới, KHÔNG retry vô ích
                    raise ProxyConnectionError(f"Proxy connection failed: {e}") from e

                is_proxy_failure = any(k in err_msg for k in (
                    "proxy", "connection was aborted", "connection closed", "connection reset",
                    "connection was reset", "curl: (28)", "curl: (35)", "curl: (52)", "curl: (56)",
                    "curl: (92)", "timed out", "timeout", "failed to connect", "could not connect to server", "broken pipe"
                ))
                if is_proxy_failure:
                    if attempts <= self.max_retries:
                        self._reset_session_connections()
                        # Tự động hạ cấp sang HTTP/1.1 nếu proxy yếu gặp lỗi rớt gói hoặc HTTP/2 stream framing
                        if any(k in err_msg for k in ("curl: (56)", "curl: (92)", "curl: (52)", "curl: (35)", "reset", "closed", "pipe")):
                            try:
                                from curl_cffi.curl import CurlHttpVersion
                                kwargs["http_version"] = CurlHttpVersion.V1_1
                            except Exception:
                                pass
                        time.sleep(min(1.0, self.backoff_seconds * attempts))
                        continue
                    if any(k in err_msg for k in ("timed out", "timeout", "curl: (28)")):
                        raise RequestTimeoutError(f"Request timed out after {req_timeout}s: {e}") from e
                    raise ProxyConnectionError(f"Proxy connection failed: {e}") from e

                if "timed out" in err_msg or "timeout" in err_msg:
                    raise RequestTimeoutError(f"Request timed out after {req_timeout}s: {e}") from e

                if attempts <= self.max_retries:
                    time.sleep(self.backoff_seconds * attempts)

            except Exception as e:

                last_error = e

                attempts += 1

                if attempts <= self.max_retries:

                    time.sleep(self.backoff_seconds * attempts)



        raise HttpClientError(f"HTTP {method} request failed for {url}: {last_error}") from last_error



    def get(self, url: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:

        """Shorthand GET request."""

        return self.request("GET", url, params=params, **kwargs)



    def post(

        self,

        url: str,

        data: Optional[Any] = None,

        json: Optional[Any] = None,

        params: Optional[Dict[str, Any]] = None,

        **kwargs

    ) -> requests.Response:

        """Shorthand POST request."""

        return self.request("POST", url, data=data, json=json, params=params, **kwargs)



    def close(self) -> None:
        """Close the underlying session resources."""
        try:
            if hasattr(self, "_session") and self._session is not None:
                self._session.close()
                self._session = None
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

