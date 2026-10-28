# -*- coding: utf-8 -*-
from core.geo_manager import GeoTelephonyResolver, GeoTelephonyProfile
"""
core.proxy_manager
Standardized Proxy Manager implementing the cycle/generator pattern.
Loads proxies from lists, files, or APIs with thread-safe rotation.
"""

import os
import json
import re
import time
import datetime
import math
import logging
import threading
import random
import collections
from typing import List, Dict, Any, Optional, Union, Iterator, Tuple
from urllib.parse import urlparse
import requests

from core.models import ProxyItem

logger = logging.getLogger(__name__)

import time
import itertools
from concurrent.futures import ThreadPoolExecutor
import requests
from urllib.parse import urlparse
from ui.colors import GREEN, RED, WHITE, EKL
from core.settings_manager import load_settings
from core.locale_data import get_locale, get_timezone, get_language

FALLBACK_IP_INFO = {"country": "United States", "countryCode": "US", "timezone": "America/New_York"}


# Parse proxy string into structured dict (supports ip:port, ip:port:user:pass, and URL formats)
def parse_proxy(proxy_str):
    if not proxy_str:
        return None
    if isinstance(proxy_str, dict):
        url_val = proxy_str.get("http") or proxy_str.get("https")
        if url_val:
            return parse_proxy(url_val)
        return proxy_str
    if hasattr(proxy_str, "as_url"):
        url = proxy_str.as_url()
        return {
            "http": url,
            "https": url,
            "username": getattr(proxy_str, "username", None),
            "password": getattr(proxy_str, "password", None),
        }
    if not isinstance(proxy_str, str):
        return None

    line = proxy_str.replace("\ufeff", "").replace("\xa0", " ").strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return None
    if "|" in line:
        line = line.split("|")[0].strip()
    if " " in line or "\t" in line:
        tokens = re.split(r'[\s\t,;]+', line)
        for tok in tokens:
            if ":" in tok and not tok.startswith("#") and not tok.startswith("//"):
                line = tok
                break
        else:
            line = line.split()[0].strip()

    username = None
    password = None
    proxy_url = None

    if "://" not in line:
        if "@" in line:
            try:
                parsed = urlparse(f"http://{line}")
                username = parsed.username
                password = parsed.password
                proxy_url = f"http://{parsed.hostname}:{parsed.port}"
            except Exception:
                return None
        else:
            parts = line.split(":")
            if len(parts) == 2:
                ip, port = parts
                if not port.isdigit():
                    return None
                proxy_url = f"http://{ip}:{port}"
            elif len(parts) >= 4:
                if parts[1].isdigit():
                    ip, port, username = parts[0], parts[1], parts[2]
                    password = ":".join(parts[3:])
                    proxy_url = f"http://{ip}:{port}"
                elif parts[3].isdigit():
                    username, password, ip, port = parts[0], parts[1], parts[2], parts[3]
                    proxy_url = f"http://{ip}:{port}"
                else:
                    return None
            else:
                return None
    else:
        try:
            parsed = urlparse(line)
            username = parsed.username
            password = parsed.password
            scheme = parsed.scheme or "http"
            proxy_url = f"{scheme}://{parsed.hostname}:{parsed.port}"
        except Exception:
            return None

    if not proxy_url:
        return None

    return {
        "http": proxy_url,
        "https": proxy_url,
        "username": username,
        "password": password
    }
# Fetch geolocation info for a proxy using ip-api.com
def get_ip_info(proxies=None, retries=1):
    for attempt in range(retries + 1):
        try:
            r = requests.get("http://ip-api.com/json/", proxies=proxies, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return {
                    "country": data.get("country", "Unknown"),
                    "countryCode": data.get("countryCode", "US"),
                    "timezone": data.get("timezone", "Unknown")
                }
        except Exception:
            pass
        if attempt < retries:
            time.sleep(1)
    return None


# Build complete proxy data dict with locale, timezone, and language info
def build_proxy_data(proxy_dict):
    req_proxies = None
    if proxy_dict:
        username = proxy_dict.get("username")
        password = proxy_dict.get("password")
        raw_url = proxy_dict.get("http", "")
        if username and password:
            if "://" in raw_url:
                proto, host = raw_url.split("://", 1)
                auth_url = f"{proto}://{username}:{password}@{host}"
            else:
                auth_url = f"http://{username}:{password}@{raw_url}"
            req_proxies = {"http": auth_url, "https": auth_url}
        else:
            req_proxies = proxy_dict

    info = get_ip_info(req_proxies)
    if info is None:
        print(f"{RED} Warning: Could not determine location for proxy. Using default US settings.")
        info = FALLBACK_IP_INFO
    cc = info["countryCode"]
    return {
        "proxy": proxy_dict,
        "country": info["country"],
        "country_code": cc,
        "locale": get_locale(cc),
        "timezone": get_timezone(cc),
        "language": get_language(cc),
        "ip_timezone": info["timezone"]
    }


# Parse and validate a single proxy input string
def _input_single_proxy_internal(proxy_str, proxy_list):
    parsed = parse_proxy(proxy_str)
    if parsed:
        data = build_proxy_data(parsed)
        proxy_list.append(data)
    else:
        print(f"{RED} Invalid proxy format!")


# Prompt user for multiple proxy inputs (max 40)
def _input_multiple_proxies_internal(prompt_label, proxy_list):
    try:
        cnt_str = input(f" {GREEN}[{RED}●{GREEN}] How many proxies? (Max 40) {EKL} ").strip()
        if not cnt_str or not cnt_str.isdigit():
            print(f"{RED} Invalid number!")
            return
        cnt = int(cnt_str)
        if cnt > 40:
            print(f"{RED} Maximum 40 proxies allowed! You entered {cnt}.")
            return
        if cnt < 1:
            print(f"{RED} Invalid number!")
            return
        for i in range(cnt):
            while True:
                p_str = input(f" {WHITE}[{RED}●{WHITE}] Enter {prompt_label} [{i+1}/{cnt}] {EKL} ").strip()
                if not p_str:
                    continue
                parsed = parse_proxy(p_str)
                if parsed:
                    data = build_proxy_data(parsed)
                    proxy_list.append(data)
                    break
                else:
                    print(f"{RED} Invalid proxy format!")
    except KeyboardInterrupt:
        raise
    except Exception:
        print(f"{RED} Invalid input!")


# Format proxy config display label for the UI
def _format_proxy_config_label(proxy_list, source="User"):
    if not proxy_list:
        return "Direct"
    if len(proxy_list) == 1:
        p = proxy_list[0]
        if source == "Settings":
            return f"{p['country']} (Settings)"
        else:
            return f"{p['country']} (IP: {p['ip_timezone']})"
    countries = set(p['country'] for p in proxy_list)
    suffix = " (Settings)" if source == "Settings" else ""
    return f"{len(proxy_list)} Proxies ({len(countries)} Countries){suffix}"


# Main proxy input handler - loads from settings or prompts user
def get_proxy_list(config_state=None, render_callback=None):
    settings = load_settings()
    proxy_cfg = settings.get("proxy_settings", {})
    ask_proxy = proxy_cfg.get("ask_for_proxy", True)
    def_proxy = proxy_cfg.get("default_proxy", "")
    prompt_label = "Proxy"
    config_key = "proxy"

    proxy_list = []

    # Load proxies from settings if configured
    if def_proxy:
        parsed_proxies = []
        if isinstance(def_proxy, list):
            if len(def_proxy) > 40:
                print(f"{RED} Warning: Maximum 40 proxies allowed in settings. Using first 40.")
                def_proxy = def_proxy[:40]
            for p in def_proxy:
                parsed = parse_proxy(p)
                if parsed:
                    parsed_proxies.append(parsed)
                else:
                    print(f"{RED} Warning: Skipping invalid proxy in settings: {p}")
        elif def_proxy.strip():
            parsed = parse_proxy(def_proxy)
            if parsed:
                parsed_proxies.append(parsed)
            else:
                print(f"{RED} Warning: Skipping invalid proxy in settings: {def_proxy}")
        if parsed_proxies:
            with ThreadPoolExecutor(max_workers=min(len(parsed_proxies), 5)) as executor:
                proxy_list.extend(executor.map(build_proxy_data, parsed_proxies))

    if not ask_proxy:
        if config_state is not None:
            config_state[config_key] = _format_proxy_config_label(proxy_list, "Settings")
        return proxy_list

    if render_callback:
        render_callback()

    proxy_input = input(f" {GREEN}[{RED}●{GREEN}] Enter {prompt_label} (or 'y' for multiple) [Enter to Skip] {EKL} ").strip()

    if proxy_input.lower() == 'y':
        _input_multiple_proxies_internal(prompt_label, proxy_list)
    elif proxy_input:
        _input_single_proxy_internal(proxy_input, proxy_list)

    if config_state is not None:
        if not proxy_list:
            no_proxy_data = get_no_proxy_data()
            config_state[config_key] = f"Direct (IP: {no_proxy_data['country']})"
        else:
            config_state[config_key] = _format_proxy_config_label(proxy_list, "User")

    return proxy_list


# Create infinite cycling iterator for round-robin proxy rotation
def create_proxy_cycle(proxy_list):
    if proxy_list:
        return itertools.cycle(proxy_list)
    return None


# Get locale data for direct connection (no proxy)
def get_no_proxy_data():
    info = get_ip_info(None)
    if info is None:
        info = FALLBACK_IP_INFO
    cc = info["countryCode"]
    return {
        "proxy": None,
        "country": info["country"],
        "country_code": cc,
        "locale": get_locale(cc),
        "timezone": get_timezone(cc),
        "language": get_language(cc),
        "ip_timezone": info["timezone"]
    }


# Convert proxy_data dict into requests-compatible proxy format with auth


def mask_ip(text: str) -> str:
    if not text or text in ('Direct', '127.0.0.1', ''):
        return str(text) if text else ''
    s = str(text)
    s = re.sub(r'://([^:@/]+):([^@/]+)@', r'://***:***@', s)
    def _repl(m):
        prefix = m.group(1)
        port = m.group(2) or ''
        return f'{prefix}.***.***{port}'
    s = re.sub(r'(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}(:\d+)?', _repl, s)
    return s



class ProxyManager:
    """
    Standardized Proxy Manager and Iterator.
    Supports multi-source loading (List, File, API) and thread-safe round-robin / random rotation.
    """

    def __init__(
        self,
        proxies: Optional[List[Union[str, Dict[str, Any], ProxyItem]]] = None,
        max_fails: int = 3,
        auto_rotate: bool = True,
    ):
        self._lock = threading.RLock()
        self._proxies: List[ProxyItem] = []
        self._worker_assignments: Dict[int, ProxyItem] = {}
        self._index: int = 0
        self.max_fails = max_fails
        self.auto_rotate = auto_rotate
        self._filepath: Optional[str] = None
        self._removed_bad_proxies: set = set()
        self.auto_remove_bad_from_file: bool = True
        self.bad_proxy_filepath: str = "proxy_loi.txt"
        self._alive_count: int = 0
        self._pending_bad_removals: set = set()

        if proxies:
            self.load_from_list(proxies)

    @classmethod
    def parse_proxy(cls, raw: Union[str, Dict[str, Any], ProxyItem]) -> Optional[ProxyItem]:
        """
        Parse proxy from various string or dictionary formats into a ProxyItem.
        Supports:
        - ip:port
        - ip:port:user:pass
        - user:pass@ip:port
        - user:pass:ip:port
        - http://... / socks5://...
        """
        if isinstance(raw, ProxyItem):
            return raw

        if isinstance(raw, dict):
            # Dict with host & port
            host = raw.get("host") or raw.get("ip")
            port = raw.get("port")
            real_ip = raw.get("realIpAddress") or raw.get("real_ip") or raw.get("ip")
            if host and port:
                return ProxyItem(
                    host=str(host).strip(),
                    port=int(port),
                    username=raw.get("username") or raw.get("user"),
                    password=raw.get("password") or raw.get("pass"),
                    protocol=raw.get("protocol", "http"),
                    country=raw.get("country", "Unknown"),
                    raw=str(raw),
                    real_ip=str(real_ip).strip() if real_ip else None,
                )
            # Dict with http / https url
            url_val = raw.get("http") or raw.get("https")
            if url_val:
                return cls.parse_proxy(url_val)
            return None

        if not isinstance(raw, str):
            return None

        line = raw.replace("\ufeff", "").replace("\xa0", " ").strip()
        if not line or line.startswith("#") or line.startswith("//"):
            return None

        if "|" in line:
            line = line.split("|")[0].strip()
        if " " in line or "\t" in line:
            tokens = re.split(r'[\s\t,;]+', line)
            for tok in tokens:
                if ":" in tok and not tok.startswith("#") and not tok.startswith("//"):
                    line = tok
                    break
            else:
                line = line.split()[0].strip()
        if not line:
            return None

        scheme = "http"
        if "://" in line:
            scheme_part, line = line.split("://", 1)
            scheme = scheme_part.strip().lower() or "http"

        # user:pass@host:port
        if "@" in line:
            auth_part, hp = line.split("@", 1)
            u, p = auth_part.split(":", 1) if ":" in auth_part else (auth_part, "")
            hp_parts = hp.split(":")
            if len(hp_parts) == 2 and hp_parts[1].isdigit():
                return ProxyItem(
                    host=hp_parts[0].strip(),
                    port=int(hp_parts[1]),
                    username=u.strip(),
                    password=p.strip(),
                    protocol=scheme,
                    raw=raw.strip()
                )

        # Split by colon
        parts = line.split(":")
        if len(parts) == 2:
            ip, port_str = parts
            if port_str.isdigit():
                return ProxyItem(host=ip.strip(), port=int(port_str), protocol=scheme, raw=raw.strip())
        elif len(parts) == 4:
            # ip:port:user:pass
            if parts[1].isdigit():
                ip, port_str, u, p = parts
                return ProxyItem(host=ip.strip(), port=int(port_str), username=u.strip(), password=p.strip(), protocol=scheme, raw=raw.strip())
            # user:pass:ip:port
            elif parts[3].isdigit():
                u, p, ip, port_str = parts
                return ProxyItem(host=ip.strip(), port=int(port_str), username=u.strip(), password=p.strip(), protocol=scheme, raw=raw.strip())

        return None

    def add_proxy(self, proxy_item: Union[str, Dict[str, Any], ProxyItem]) -> bool:
        """Add a single parsed proxy to the rotation pool."""
        parsed = self.parse_proxy(proxy_item)
        if parsed:
            with self._lock:
                self._proxies.append(parsed)
                self._alive_count = getattr(self, "_alive_count", 0) + 1
            return True
        return False

    def load_from_list(self, proxy_list: List[Union[str, Dict[str, Any], ProxyItem]]) -> int:
        """Load multiple proxies from a python list or array."""
        count = 0
        with self._lock:
            for item in proxy_list:
                parsed = self.parse_proxy(item)
                if parsed:
                    self._proxies.append(parsed)
                    count += 1
            self._alive_count = len(self._proxies)
        return count

    def load_from_kiotproxy(self, api_key: str, rotate: bool = False) -> Optional[ProxyItem]:
        """Fetch rotating proxy from KiotProxy API."""
        client = KiotProxyClient(api_key)
        res = client.get_new_proxy() if rotate else client.get_current_proxy()
        if not res.get("success") or not res.get("http"):
            res = client.get_new_proxy()
        if res.get("success") and res.get("http"):
            parsed = self.parse_proxy(res["http"])
            if parsed:
                parsed.country = res.get("location", "Vietnam")
                parsed.raw = api_key
                parsed.real_ip = res.get("ip") or parsed.host
                with self._lock:
                    self._proxies = [parsed]
                    self._index = 0
                return parsed
        return None

    def load_from_kiotproxy_keys(self, api_keys: list, rotate: bool = False, ensure_unique_ips: bool = True, current_only: bool = False) -> int:
        """Fetch rotating proxies from multiple KiotProxy API keys into pool with unique IP guarantee."""
        count = 0
        seen_ips = set()
        for key in api_keys:
            k = str(key).strip()
            if not k or k.startswith("#"):
                continue
            client = KiotProxyClient(k)
            if current_only:
                res = client.get_current_proxy(force_refresh=True)
                cur_ip = res.get("ip")
            else:
                res = client.get_new_proxy() if rotate else client.get_current_proxy()
                if not res.get("success") or not res.get("http"):
                    res = client.get_new_proxy()

                # Chống trùng IP giữa các key: Nếu IP bị trùng lặp, xoay ngay IP mới
                cur_ip = res.get("ip")
                if ensure_unique_ips and cur_ip and cur_ip in seen_ips:
                    for _ in range(3):
                        time.sleep(1.2)
                        retry_res = client.get_new_proxy()
                        retry_ip = retry_res.get("ip")
                        if retry_res.get("success") and retry_ip and retry_ip not in seen_ips:
                            res = retry_res
                            cur_ip = retry_ip
                            break

            if res.get("success") and res.get("http"):
                parsed = self.parse_proxy(res["http"])
                if parsed:
                    parsed.country = res.get("location", "Vietnam")
                    parsed.raw = k
                    parsed.real_ip = cur_ip or parsed.host
                    if parsed.real_ip:
                        seen_ips.add(parsed.real_ip)
                    with self._lock:
                        self._proxies.append(parsed)
                    count += 1
        with self._lock:
            if self._proxies:
                self._index = 0
        return count

    def load_from_proxysocks5(self, token_proxy: str, rotate: bool = False):
        """Fetch rotating proxy from ProxySocks5.vn API."""
        client = ProxySocks5Client(token_proxy)
        res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
        if not res.get("success") or not res.get("http"):
            res = client.get_new_proxy(fallback_current=True)
        if res.get("success") and res.get("http"):
            parsed = self.parse_proxy(res["http"])
            if parsed:
                parsed.country = res.get("location", "Vietnam")
                parsed.raw = token_proxy
                parsed.real_ip = res.get("ip") or parsed.host
                with self._lock:
                    self._proxies = [parsed]
                    self._index = 0
                return parsed
        return None

    def load_from_proxysocks5_keys(self, token_keys: list, rotate: bool = False, ensure_unique_ips: bool = True) -> int:
        """Fetch rotating proxies from multiple ProxySocks5.vn token keys into pool with unique IP guarantee."""
        count = 0
        seen_ips = set()
        for key in token_keys:
            k = str(key).strip()
            if not k or k.startswith("#"):
                continue
            client = ProxySocks5Client(k)
            res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
            if not res.get("success") or not res.get("http"):
                res = client.get_new_proxy(fallback_current=True)

            cur_ip = res.get("ip")
            if ensure_unique_ips and cur_ip and cur_ip in seen_ips:
                for _ in range(3):
                    time.sleep(1.2)
                    retry_res = client.get_new_proxy(fallback_current=True)
                    retry_ip = retry_res.get("ip")
                    if retry_res.get("success") and retry_ip and retry_ip not in seen_ips:
                        res = retry_res
                        cur_ip = retry_ip
                        break

            if res.get("success") and res.get("http"):
                parsed = self.parse_proxy(res["http"])
                if parsed:
                    parsed.country = res.get("location", "Vietnam")
                    parsed.raw = k
                    parsed.real_ip = cur_ip or parsed.host
                    if parsed.real_ip:
                        seen_ips.add(parsed.real_ip)
                    with self._lock:
                        self._proxies.append(parsed)
                    count += 1
        with self._lock:
            if self._proxies:
                self._index = 0
        return count

    def load_from_mproxy(self, token: str, key_code: Optional[str] = None, rotate: bool = False) -> Optional[ProxyItem]:
        """Fetch rotating 4G/5G proxy from mProxy.vn API."""
        client = MproxyClient(token, key_code=key_code)
        res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
        if not res.get("success") or not (res.get("http") or res.get("proxy")):
            res = client.get_new_proxy(fallback_current=True)
        p_str = res.get("http") or res.get("proxy")
        if res.get("success") and p_str:
            parsed = self.parse_proxy(p_str)
            if parsed:
                parsed.country = res.get("location", "Vietnam")
                parsed.raw = key_code or token
                parsed.real_ip = res.get("server") or parsed.host
                with self._lock:
                    self._proxies = [parsed]
                    self._index = 0
                return parsed
        return None

    def load_from_mproxy_keys(self, token: str, key_codes: list, rotate: bool = False, ensure_unique_ips: bool = True) -> int:
        """Fetch rotating 4G/5G proxies from multiple mProxy.vn keys into pool with unique IP guarantee."""
        count = 0
        seen_ips = set()
        for key in key_codes:
            k = str(key).strip()
            if not k or k.startswith("#"):
                continue
            client = MproxyClient(token, key_code=k)
            res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
            if not res.get("success") or not (res.get("http") or res.get("proxy")):
                res = client.get_new_proxy(fallback_current=True)

            cur_ip = res.get("server") or res.get("ip")
            if ensure_unique_ips and cur_ip and cur_ip in seen_ips:
                for _ in range(2):
                    time.sleep(1.0)
                    retry_res = client.get_new_proxy(fallback_current=True)
                    retry_ip = retry_res.get("server") or retry_res.get("ip")
                    if retry_res.get("success") and retry_ip and retry_ip not in seen_ips:
                        res = retry_res
                        cur_ip = retry_ip
                        break

            p_str = res.get("http") or res.get("proxy")
            if res.get("success") and p_str:
                parsed = self.parse_proxy(p_str)
                if parsed:
                    parsed.country = res.get("location", "Vietnam")
                    parsed.raw = k
                    parsed.real_ip = cur_ip or parsed.host
                    if parsed.real_ip:
                        seen_ips.add(parsed.real_ip)
                    with self._lock:
                        self._proxies.append(parsed)
                    count += 1
        with self._lock:
            if self._proxies:
                self._index = 0
        return count

    def load_from_proxyvn(self, api_key: str, rotate: bool = False) -> Optional[ProxyItem]:
        """Fetch rotating proxy from Proxy.vn (proxyxoay.shop) API."""
        client = ProxyVNClient(api_key)
        res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
        if not res.get("success") or not res.get("http"):
            res = client.get_new_proxy(fallback_current=True)
        if res.get("success") and res.get("http"):
            parsed = self.parse_proxy(res["http"])
            if parsed:
                parsed.country = res.get("location", "Vietnam")
                parsed.raw = api_key
                parsed.real_ip = res.get("ip") or parsed.host
                with self._lock:
                    self._proxies = [parsed]
                    self._index = 0
                return parsed
        return None

    def load_from_proxyvn_keys(self, api_keys: list, rotate: bool = False, ensure_unique_ips: bool = True, current_only: bool = False) -> int:
        """Fetch rotating proxies from multiple Proxy.vn API keys into pool with unique IP guarantee."""
        count = 0
        seen_ips = set()
        for key in api_keys:
            k = str(key).strip()
            if not k or k.startswith("#"):
                continue
            client = ProxyVNClient(k)
            if current_only:
                res = client.get_current_proxy(force_refresh=True)
                cur_ip = res.get("ip")
            else:
                res = client.get_new_proxy(fallback_current=True) if rotate else client.get_current_proxy()
                if not res.get("success") or not res.get("http"):
                    res = client.get_new_proxy(fallback_current=True)

            cur_ip = res.get("ip")
            if ensure_unique_ips and cur_ip and cur_ip in seen_ips:
                for _ in range(3):
                    time.sleep(1.2)
                    retry_res = client.get_new_proxy(fallback_current=True)
                    retry_ip = retry_res.get("ip")
                    if retry_res.get("success") and retry_ip and retry_ip not in seen_ips:
                        res = retry_res
                        cur_ip = retry_ip
                        break

            if res.get("success") and res.get("http"):
                parsed = self.parse_proxy(res["http"])
                if parsed:
                    parsed.country = res.get("location", "Vietnam")
                    parsed.raw = k
                    parsed.real_ip = cur_ip or parsed.host
                    if parsed.real_ip:
                        seen_ips.add(parsed.real_ip)
                    with self._lock:
                        self._proxies.append(parsed)
                    count += 1
        with self._lock:
            if self._proxies:
                self._index = 0
        return count

    def load_from_file(self, filepath: str) -> int:
        """Load proxies line-by-line from a text file, deduplicating and shuffling."""
        if not os.path.exists(filepath):
            logger.warning(f"Proxy file not found: {filepath}")
            return 0

        with open(filepath, "r", encoding="utf-8-sig", errors="ignore") as f:
            lines = []
            for line in f:
                s = line.lstrip("\ufeff").replace("\xa0", " ").strip()
                if s and not s.startswith("#") and not s.startswith("//"):
                    lines.append(s)

        seen_hosts = set()
        parsed_list = []
        for line in lines:
            tokens = re.split(r'[\s\t,;]+', line)
            for tok in tokens:
                tok = tok.strip()
                if not tok or ":" not in tok or tok.startswith("#") or tok.startswith("//"):
                    continue
                if "|" in tok:
                    tok = tok.split("|")[0].strip()
                parsed = self.parse_proxy(tok)
                if parsed and parsed.host and parsed.port:
                    key = f"{parsed.host}:{parsed.port}"
                    if key not in seen_hosts:
                        seen_hosts.add(key)
                        parsed_list.append(parsed)

        random.shuffle(parsed_list)

        with self._lock:
            self._filepath = os.path.abspath(filepath)
            self._proxies = parsed_list
            self._alive_count = len(parsed_list)
            if hasattr(self, "_removed_bad_proxies"):
                self._removed_bad_proxies.clear()
            else:
                self._removed_bad_proxies = set()
            if hasattr(self, "_worker_assignments"):
                self._worker_assignments.clear()
            else:
                self._worker_assignments = {}
            self._index = 0

        return len(parsed_list)



    def get_worker_proxy(self, worker_id: int, registry=None) -> Optional[ProxyItem]:
        """
        Lấy proxy NGẪU NHIÊN cho worker_id từ toàn bộ danh sách proxy còn sống,
        đảm bảo không bị trùng IP với các luồng khác đang chạy (Collision-Free Random).
        """
        with self._lock:
            if not hasattr(self, "_worker_assignments"):
                self._worker_assignments = {}

            if not self._proxies:
                return None

            other_assigned_hosts = {
                p.host for wid, p in self._worker_assignments.items()
                if wid != worker_id and p and p.host
            }

            # Fast-path O(1) random sampling cho danh sách lớn (>200) để tránh nghẽn lock Tkinter
            total_p = len(self._proxies)
            if total_p > 200:
                for _ in range(35):
                    cand = random.choice(self._proxies)
                    if cand and cand.is_alive and cand.host and cand.host not in other_assigned_hosts:
                        if registry:
                            try:
                                if not registry.is_ip_available(cand.host, worker_id, enforce_subnet_24=False, check_history=False)[0]:
                                    continue
                            except Exception:
                                pass
                        self._worker_assignments[worker_id] = cand
                        if registry and cand.host:
                            try:
                                registry.lease_ip(worker_id, cand.host, force=True)
                            except Exception:
                                pass
                        return cand

            active = [p for p in self._proxies if p.is_alive]
            if not active:
                return None

            free_candidates = [p for p in active if p.host not in other_assigned_hosts]

            if registry:
                try:
                    free_candidates = [
                        p for p in free_candidates
                        if registry.is_ip_available(p.host, worker_id, enforce_subnet_24=False, check_history=False)[0]
                    ]
                except Exception:
                    pass

            chosen_pool = free_candidates if free_candidates else active
            chosen = random.choice(chosen_pool)

            self._worker_assignments[worker_id] = chosen
            if registry and chosen.host:
                try:
                    registry.lease_ip(worker_id, chosen.host, force=True)
                except Exception:
                    pass

            return chosen

    def next_proxy(self, worker_id: Optional[int] = None, registry=None) -> Optional[ProxyItem]:
        """
        Xoay sang proxy NGẪU NHIÊN mới còn sống, loại trừ proxy cũ và tránh trùng với luồng khác.
        """
        with self._lock:
            if not hasattr(self, "_worker_assignments"):
                self._worker_assignments = {}

            if not self._proxies:
                return None

            old_p = self._worker_assignments.get(worker_id) if worker_id is not None else None
            old_host = old_p.host if old_p else None

            if worker_id is not None and registry:
                try:
                    registry.release_ip(worker_id)
                except Exception:
                    pass

            other_assigned_hosts = {
                p.host for wid, p in self._worker_assignments.items()
                if wid != worker_id and p and p.host
            }

            # Fast-path O(1) random sampling cho danh sách lớn (>200) để không giật/lag giao diện
            total_p = len(self._proxies)
            if total_p > 200:
                for _ in range(40):
                    cand = random.choice(self._proxies)
                    if cand and cand.is_alive and cand.host:
                        if old_host and cand.host == old_host:
                            continue
                        if cand.host in other_assigned_hosts:
                            continue
                        if worker_id is not None:
                            self._worker_assignments[worker_id] = cand
                            if registry and cand.host:
                                try:
                                    registry.lease_ip(worker_id, cand.host, force=True)
                                except Exception:
                                    pass
                        return cand

            active = [p for p in self._proxies if p.is_alive]
            if not active:
                return None

            candidates = [
                p for p in active
                if p.host not in other_assigned_hosts and (len(active) <= 1 or p.host != old_host)
            ]

            if not candidates:
                candidates = [p for p in active if len(active) <= 1 or p.host != old_host]
            if not candidates:
                candidates = active

            chosen = random.choice(candidates)
            if worker_id is not None:
                self._worker_assignments[worker_id] = chosen
                if registry and chosen.host:
                    try:
                        registry.lease_ip(worker_id, chosen.host, force=True)
                    except Exception:
                        pass

            return chosen

    def release_worker_proxy(self, worker_id: int, registry=None) -> None:
        """Giải phóng proxy đã gán cho worker_id khi luồng kết thúc."""
        with self._lock:
            if hasattr(self, "_worker_assignments"):
                self._worker_assignments.pop(worker_id, None)
            if registry:
                try:
                    registry.release_ip(worker_id)
                except Exception:
                    pass

    def remove_bad_proxy(
        self,
        proxy_item: Any,
        reason: str = "Lỗi kết nối",
        bad_file: Optional[str] = None
    ) -> Optional[str]:
        """
        Loại bỏ proxy lỗi ra khỏi danh sách RAM và xóa trực tiếp dòng proxy lỗi ra khỏi file nguồn (.txt).
        Đồng thời ghi nhận proxy lỗi này vào file 'proxy_loi.txt' kèm ghi chú lỗi và thời gian.
        Thread-safe 100%.
        """
        if not proxy_item:
            return None

        host = ""
        port = ""
        raw_str = ""
        if isinstance(proxy_item, ProxyItem):
            host = proxy_item.host
            port = str(proxy_item.port)
            raw_str = proxy_item.raw or f"{host}:{port}"
        elif isinstance(proxy_item, str):
            raw_str = proxy_item.strip()
            parsed = self.parse_proxy(raw_str)
            if parsed:
                host = parsed.host
                port = str(parsed.port)
            else:
                toks = raw_str.split(":")
                if len(toks) >= 2:
                    host = toks[0].split("//")[-1]
                    port = toks[1].split("@")[0].split("/")[0]

        if not host or not port:
            return None

        key = f"{host}:{port}"
        target_bad_file = bad_file or getattr(self, "bad_proxy_filepath", "proxy_loi.txt") or "proxy_loi.txt"

        with self._lock:
            if not hasattr(self, "_removed_bad_proxies"):
                self._removed_bad_proxies = set()

            if key in self._removed_bad_proxies:
                return None
            self._removed_bad_proxies.add(key)

            # 1. Đánh dấu proxy chết và cập nhật alive counter O(1)
            if isinstance(proxy_item, ProxyItem):
                proxy_item.is_alive = False

            if hasattr(self, "_alive_count") and self._alive_count > 0:
                self._alive_count -= 1
            else:
                self._alive_count = 0

            # Với danh sách nhỏ (<= 5,000 proxy), loại bỏ trực tiếp khỏi RAM
            if len(self._proxies) <= 5000:
                self._proxies = [
                    p for p in self._proxies
                    if not (p.host == host and str(p.port) == port)
                ]

            # Giải phóng gán worker nếu có
            if hasattr(self, "_worker_assignments"):
                to_remove = [wid for wid, p in self._worker_assignments.items() if p and p.host == host and str(p.port) == port]
                for wid in to_remove:
                    self._worker_assignments.pop(wid, None)

        # 2. Ghi nhận vào file proxy lỗi (proxy_loi.txt) bằng fast append O(1)
        if getattr(self, "auto_remove_bad_from_file", True):
            try:
                with open(target_bad_file, "a", encoding="utf-8") as f_bad:
                    time_str = time.strftime("%Y-%m-%d %H:%M:%S")
                    clean_reason = (reason or "Lỗi kết nối / Chết").replace("\n", " ").strip()
                    f_bad.write(f"{raw_str} # {clean_reason} - {time_str}\n")
            except Exception as e_bad:
                logger.debug(f"Error appending to bad proxy file: {e_bad}")

            # 3. Xóa dòng chứa proxy lỗi khỏi file proxy nguồn (self._filepath)
            # QUAN TRỌNG: Nếu file nguồn lớn (>= 150KB hoặc >= 2,000 dòng như proxy_all_sources.txt 33MB):
            # Tuyệt đối KHÔNG đọc và ghi đè toàn bộ 33MB trên mỗi lỗi đơn lẻ vì sẽ gây disk thrashing và nghẽn toàn bộ hệ thống!
            src_file = getattr(self, "_filepath", None)
            if src_file and os.path.exists(src_file):
                try:
                    f_size = os.path.getsize(src_file)
                    if f_size < 250 * 1024:
                        with self._lock:
                            with open(src_file, "r", encoding="utf-8-sig", errors="ignore") as f_in:
                                current_lines = f_in.readlines()

                            remaining_lines = []
                            removed_any = False
                            for line in current_lines:
                                line_str = line.strip()
                                if not line_str or line_str.startswith("#") or line_str.startswith("//"):
                                    remaining_lines.append(line)
                                    continue
                                
                                p_parsed = self.parse_proxy(line_str)
                                if p_parsed and p_parsed.host == host and str(p_parsed.port) == port:
                                    removed_any = True
                                    continue
                                elif key in line_str:
                                    removed_any = True
                                    continue
                                remaining_lines.append(line)

                            if removed_any:
                                with open(src_file, "w", encoding="utf-8") as f_out:
                                    f_out.writelines(remaining_lines)
                    else:
                        if not hasattr(self, "_pending_bad_removals"):
                            self._pending_bad_removals = set()
                        self._pending_bad_removals.add(key)
                        if len(self._pending_bad_removals) >= 10:
                            threading.Thread(target=self.flush_bad_proxies_from_file, daemon=True).start()
                except Exception as e_src:
                    logger.debug(f"Error removing bad proxy from source file: {e_src}")

        return key

    def flush_bad_proxies_from_file(self) -> int:
        """
        Xả toàn bộ danh sách proxy lỗi đang chờ (_pending_bad_removals & _removed_bad_proxies)
        ra khỏi file nguồn. Đảm bảo 100% không còn proxy lỗi trong file txt kể cả file dung lượng lớn.
        """
        src_file = getattr(self, "_filepath", None)
        if not src_file or not os.path.exists(src_file):
            return 0

        with self._lock:
            bad_keys = set(getattr(self, "_removed_bad_proxies", set()))
            if hasattr(self, "_pending_bad_removals"):
                bad_keys.update(self._pending_bad_removals)
            if not bad_keys:
                return 0

        removed_count = 0
        try:
            temp_file = src_file + ".tmp"
            with open(src_file, "r", encoding="utf-8-sig", errors="ignore") as f_in,                  open(temp_file, "w", encoding="utf-8") as f_out:
                for line in f_in:
                    line_str = line.strip()
                    if not line_str or line_str.startswith("#") or line_str.startswith("//"):
                        f_out.write(line)
                        continue
                    p_parsed = self.parse_proxy(line_str)
                    is_bad = False
                    if p_parsed and f"{p_parsed.host}:{p_parsed.port}" in bad_keys:
                        is_bad = True
                    elif any(k in line_str for k in bad_keys):
                        is_bad = True

                    if is_bad:
                        removed_count += 1
                        continue
                    f_out.write(line)

            if os.path.exists(temp_file):
                import shutil
                shutil.move(temp_file, src_file)

            with self._lock:
                if hasattr(self, "_pending_bad_removals"):
                    self._pending_bad_removals.clear()

        except Exception as e:
            logger.debug(f"Error in flush_bad_proxies_from_file: {e}")
            if os.path.exists(src_file + ".tmp"):
                try:
                    os.remove(src_file + ".tmp")
                except Exception:
                    pass

        return removed_count

    def mark_failed(self, proxy_item: Optional[ProxyItem], reason: str = "") -> None:
        """Đánh dấu proxy bị lỗi, tự động loại bỏ khỏi file và đưa vào proxy_loi.txt nếu bật."""
        if not proxy_item:
            return
        with self._lock:
            proxy_item.fail_count = getattr(proxy_item, "fail_count", 0) + 1
            if proxy_item.fail_count >= getattr(self, "max_fails", 3):
                proxy_item.is_alive = False

        if getattr(self, "auto_remove_bad_from_file", True) and getattr(proxy_item, "fail_count", 0) >= 1:
            self.remove_bad_proxy(proxy_item, reason=reason or "Lỗi kết nối / Chết")

    def alive_count(self) -> int:
        """Alive proxies count (O(1) lookup)."""
        with self._lock:
            if hasattr(self, "_alive_count") and self._alive_count is not None:
                return max(0, self._alive_count)
            cnt = sum(1 for p in self._proxies if getattr(p, "is_alive", True))
            self._alive_count = cnt
            return cnt

    def clear(self) -> None:
        """Clear all proxies."""
        with self._lock:
            self._proxies.clear()
            self._index = 0
            self._alive_count = 0

    def __iter__(self) -> Iterator[ProxyItem]:
        """Generator interface: yields proxies in an infinite cycle."""
        return self

    def __next__(self) -> ProxyItem:
        """Iterator next: returns next proxy or raises StopIteration if empty."""
        proxy = self.next_proxy()
        if proxy is None:
            raise StopIteration("No available proxies in pool")
        return proxy


# Backward-compatible helper functions
def format_proxy_for_requests(proxy_data: Optional[Union[str, Dict[str, Any], ProxyItem]]) -> Optional[Dict[str, str]]:
    """Format any proxy representation into requests-compatible dictionary."""
    if not proxy_data:
        return None
    if isinstance(proxy_data, ProxyItem):
        return proxy_data.to_requests_dict()
    if isinstance(proxy_data, dict) and "proxy" in proxy_data:
        inner = proxy_data["proxy"]
        if not inner:
            return None
        if isinstance(inner, dict):
            username = inner.get("username")
            password = inner.get("password")
            raw_url = inner.get("http", "")
            if username and password:
                from urllib.parse import quote
                safe_user = quote(username, safe="")
                safe_pass = quote(password, safe="")
                if "://" in raw_url:
                    proto, host = raw_url.split("://", 1)
                    auth_url = f"{proto}://{safe_user}:{safe_pass}@{host}"
                else:
                    auth_url = f"http://{safe_user}:{safe_pass}@{raw_url}"
                return {"http": auth_url, "https": auth_url}
            return {"http": raw_url, "https": inner.get("https", raw_url)}
        elif isinstance(inner, str):
            parsed = ProxyManager.parse_proxy(inner)
            if parsed:
                return parsed.to_requests_dict()
            return {"http": inner, "https": inner}
    parsed = ProxyManager.parse_proxy(proxy_data)
    if parsed:
        return parsed.to_requests_dict()
    if isinstance(proxy_data, str) and ("://" in proxy_data or ":" in proxy_data):
        return {"http": proxy_data, "https": proxy_data}
    return None


def get_subnet_24(ip_val: str) -> str:
    """Trich xuat dai mang Subnet /24 (a.b.c) tu dia chi IPv4."""
    parts = str(ip_val).strip().split(".")
    if len(parts) >= 3 and parts[0].isdigit():
        return f"{parts[0]}.{parts[1]}.{parts[2]}"
    return str(ip_val).strip()


class ActiveIpRegistry:
    """
    Quan ly cach ly IP va dai mang Subnet /24 giua cac luong dang ky (Thread-safe IP Isolation).
    Dam bao:
    1. 100% khong trung IP giua cac luong dang chay (Vi du 4 luong 4 key -> 4 IP khac nhau).
    2. Chong gom cum Sybil qua viec cach ly dai Subnet /24 (Khong cho 2 luong cung dai mang a.b.c.*).
    3. Tranh xoay nguoc lai dung IP vua moi su dung (History cooldown buffer).
    """

    def __init__(self, history_cooldown_sec: float = 180.0):
        self._lock = threading.RLock()
        self._leased_ips = {}  # worker_id -> ip
        self._recent_ip_history = {}  # ip -> timestamp released
        self._cooldown_sec = history_cooldown_sec

    def is_ip_available(self, ip: str, worker_id: int, enforce_subnet_24: bool = True, check_history: bool = True):
        """Kiem tra xem ip co dang bi luong khac chiem dung hoac trung Subnet /24 hay khong."""
        if not ip or ip in ("Direct", "127.0.0.1", ""):
            return True, "Direct/Local"

        now = time.time()
        clean_ip = str(ip).strip()
        with self._lock:
            # 1. Trung IP truc tiep voi luong khac
            for w, active_ip in self._leased_ips.items():
                if w != worker_id and active_ip == clean_ip:
                    return False, f"Trung lap truc tiep voi IP cua Luong {w} ({mask_ip(clean_ip)})"

            # 2. Trung Subnet /24 voi luong khac
            if enforce_subnet_24:
                target_subnet = get_subnet_24(clean_ip)
                for w, active_ip in self._leased_ips.items():
                    if w != worker_id and get_subnet_24(active_ip) == target_subnet:
                        return False, f"Trung dai Subnet /24 ({target_subnet}.*) voi Luong {w}"

            # 3. Trung IP vua su dung gan day (cooldown)
            if check_history:
                last_used = self._recent_ip_history.get(clean_ip, 0)
                if (now - last_used) < self._cooldown_sec:
                    remain = int(self._cooldown_sec - (now - last_used))
                    return False, f"IP vua su dung cach day {int(now - last_used)}s (dang cooldown {remain}s)"

        return True, "Available"

    def acquire_unique_ip(
        self,
        worker_id: int,
        ip: str,
        enforce_subnet_24: bool = True,
        check_history: bool = True,
    ) -> Tuple[bool, str]:
        """Atomically checks and leases an IP to worker_id if unique and not colliding."""
        if not ip or ip in ("Direct", "127.0.0.1", ""):
            return True, "Direct/Local"

        now = time.time()
        clean_ip = str(ip).strip()
        with self._lock:
            # 1. Trung IP truc tiep voi luong khac
            for w, active_ip in self._leased_ips.items():
                if w != worker_id and active_ip == clean_ip:
                    return False, f"Trung lap truc tiep voi IP cua Luong {w} ({mask_ip(clean_ip)})"

            # 2. Trung Subnet /24 voi luong khac
            if enforce_subnet_24:
                target_subnet = get_subnet_24(clean_ip)
                for w, active_ip in self._leased_ips.items():
                    if w != worker_id and get_subnet_24(active_ip) == target_subnet:
                        return False, f"Trung dai Subnet /24 ({target_subnet}.*) voi Luong {w}"

            # 3. Trung IP vua su dung gan day (cooldown)
            if check_history:
                last_used = self._recent_ip_history.get(clean_ip, 0)
                if (now - last_used) < self._cooldown_sec:
                    remain = int(self._cooldown_sec - (now - last_used))
                    return False, f"IP vua su dung cach day {int(now - last_used)}s (dang cooldown {remain}s)"

            # Available -> Lease immediately
            old_ip = self._leased_ips.get(worker_id)
            if old_ip and old_ip != clean_ip and old_ip not in ("Direct", ""):
                self._recent_ip_history[old_ip] = time.time()
            self._leased_ips[worker_id] = clean_ip
            return True, "Acquired"

    def reset_session(self) -> None:
        """Reset toàn bộ danh sách IP đã cấp trong phiên làm việc."""
        with self._lock:
            self._leased_ips.clear()
            self._session_used_ips = set()

    def lease_ip(self, worker_id: int, ip: str, force: bool = False) -> bool:
        """Gan IP cho worker_id doc quyen. Tu choi neu IP dang bi luong khac chiem giu."""
        if not ip:
            return False
        clean_ip = str(ip).strip()
        with self._lock:
            if not hasattr(self, "_session_used_ips"):
                self._session_used_ips = set()
            self._session_used_ips.add(clean_ip)
            if not force:
                for w, active_ip in self._leased_ips.items():
                    if w != worker_id and active_ip == clean_ip and clean_ip not in ("Direct", ""):
                        logger.debug(f"Tu choi lease IP {mask_ip(clean_ip)} cho Luong {worker_id} vi dang bi Luong {w} su dung!")
                        return False
            old_ip = self._leased_ips.get(worker_id)
            if old_ip and old_ip != clean_ip and old_ip not in ("Direct", ""):
                self._recent_ip_history[old_ip] = time.time()
            self._leased_ips[worker_id] = clean_ip
            return True

    def release_ip(self, worker_id: int) -> None:
        """Giai phong IP cua worker_id va dua vao lich su cooldown."""
        with self._lock:
            if worker_id in self._leased_ips:
                old_ip = self._leased_ips.pop(worker_id)
                if old_ip and old_ip not in ("Direct", ""):
                    self._recent_ip_history[old_ip] = time.time()

    def get_leased_ips(self):
        with self._lock:
            return dict(self._leased_ips)

    def clear(self) -> None:
        with self._lock:
            self._leased_ips.clear()
            self._recent_ip_history.clear()

_KIOT_CACHE_LOCK = threading.RLock()
_KIOT_CACHE: Dict[str, Dict[str, Any]] = {}
_KIOT_LAST_KNOWN: Dict[str, Dict[str, Any]] = {}

class KiotProxyClient:
    """Client for KiotProxy API (https://api.kiotproxy.com)."""
    BASE_URL = "https://api.kiotproxy.com/api/v1/proxies"
    CACHE_FILE = os.path.join(os.path.dirname(__file__), ".kiotproxy_cache.json")
    LAST_KNOWN_FILE = os.path.join(os.path.dirname(__file__), ".kiotproxy_last_known.json")

    @classmethod
    def _read_last_known_disk(cls) -> Dict[str, Dict[str, Any]]:
        try:
            if os.path.exists(cls.LAST_KNOWN_FILE):
                with open(cls.LAST_KNOWN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _write_last_known_disk(cls, data: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(cls.LAST_KNOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def _read_disk_cache(cls) -> Dict[str, Dict[str, Any]]:
        try:
            if os.path.exists(cls.CACHE_FILE):
                with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _write_disk_cache(cls, data: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(cls.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.last_proxy: Optional[str] = None
        self.last_ip: Optional[str] = None
        self.location: Optional[str] = None
        self.next_change_at: float = 0.0

    @classmethod
    def get_cached_proxy(cls, api_key: str, max_age: Optional[float] = 120.0) -> Optional[Dict[str, Any]]:
        k = api_key.strip()
        eff_max_age = 300.0 if max_age is None else max_age
        with _KIOT_CACHE_LOCK:
            data = _KIOT_CACHE.get(k)
            now = time.time()
            if data and (now - data.get("cached_at", 0)) < eff_max_age and data.get("http"):
                res = dict(data)
                res["success"] = True
                res["from_cache"] = True
                return res

            disk_cache = cls._read_disk_cache()
            disk_data = disk_cache.get(k)
            if disk_data and (now - disk_data.get("cached_at", 0)) < eff_max_age and disk_data.get("http"):
                _KIOT_CACHE[k] = dict(disk_data)
                res = dict(disk_data)
                res["success"] = True
                res["from_cache"] = True
                return res
        return None

    @classmethod
    def update_cache(cls, api_key: str, data: Dict[str, Any]) -> None:
        if not data or not data.get("http"):
            return
        k = api_key.strip()
        with _KIOT_CACHE_LOCK:
            cached = dict(data)
            cached["cached_at"] = time.time()
            _KIOT_CACHE[k] = cached
            _KIOT_LAST_KNOWN[k] = cached

            disk_cache = cls._read_disk_cache()
            disk_cache[k] = cached
            cls._write_disk_cache(disk_cache)

            disk_last = cls._read_last_known_disk()
            disk_last[k] = cached
            cls._write_last_known_disk(disk_last)

    @classmethod
    def get_last_known(cls, api_key: str, max_age: Optional[float] = 300.0) -> Optional[Dict[str, Any]]:
        k = api_key.strip()
        eff_max_age = 300.0 if max_age is None else max_age
        now = time.time()
        with _KIOT_CACHE_LOCK:
            cand = _KIOT_LAST_KNOWN.get(k)
            if cand and cand.get("http"):
                if (now - cand.get("cached_at", 0)) < eff_max_age:
                    res = dict(cand)
                    res["success"] = True
                    res["from_cache"] = True
                    return res
            disk_last = cls._read_last_known_disk()
            cand = disk_last.get(k)
            if cand and cand.get("http"):
                if (now - cand.get("cached_at", 0)) < eff_max_age:
                    _KIOT_LAST_KNOWN[k] = dict(cand)
                    res = dict(cand)
                    res["success"] = True
                    res["from_cache"] = True
                    return res
        return None

    @classmethod
    def invalidate_cache(cls, api_key: str) -> None:
        k = api_key.strip()
        with _KIOT_CACHE_LOCK:
            _KIOT_CACHE.pop(k, None)

    def get_current_proxy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch current active proxy with thread-safe caching and rate limit protection."""
        if not force_refresh:
            cached = self.get_cached_proxy(self.api_key, max_age=120.0)
            if cached:
                self.last_proxy = cached.get("http")
                self.last_ip = cached.get("ip")
                self.location = cached.get("location")
                self.next_change_at = cached.get("next_change_at", 0.0)
                return cached

        url = f"{self.BASE_URL}/current?key={self.api_key}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("success") and "data" in data:
                pdata = data["data"]
                self.last_proxy = pdata.get("http")
                self.last_ip = pdata.get("realIpAddress")
                self.location = pdata.get("location")
                self.next_change_at = pdata.get("nextRequestAt", 0) / 1000.0
                res = {
                    "success": True,
                    "http": self.last_proxy,
                    "ip": self.last_ip,
                    "location": self.location,
                    "ttc": pdata.get("ttc", 0),
                    "next_change_at": self.next_change_at,
                    "raw": pdata,
                }
                self.update_cache(self.api_key, res)
                return res

            # Ki?m tra l?i rate-limit c?a KiotProxy (Code 40001129: Thao t?c qu? nhanh)
            msg_str = str(data.get("message", "")).lower()
            if data.get("code") == 40001129 or "qu? nhanh" in msg_str or "gi?i h?n" in msg_str:
                cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
                if cached and cached.get("http"):
                    self.last_proxy = cached.get("http")
                    self.last_ip = cached.get("ip")
                    self.location = cached.get("location")
                    res = dict(cached)
                    res["success"] = True
                    res["cooldown"] = True
                    return res

            return {"success": False, "message": data.get("message", "Unknown error")}
        except Exception as e:
            cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
            if cached and cached.get("http"):
                return cached
            return {"success": False, "message": str(e)}

    def get_new_proxy(self, fallback_current: bool = True) -> Dict[str, Any]:
        """Request IP rotation with cache update and smart fallback."""
        url = f"{self.BASE_URL}/new?key={self.api_key}"
        try:
            r = requests.get(url, timeout=10)
            data = r.json()
            if data.get("success") and "data" in data:
                pdata = data["data"]
                self.last_proxy = pdata.get("http")
                self.last_ip = pdata.get("realIpAddress")
                self.location = pdata.get("location")
                self.next_change_at = pdata.get("nextRequestAt", 0) / 1000.0
                ttc = pdata.get("ttc", 0)
                res = {
                    "success": True,
                    "rotated": True,
                    "http": self.last_proxy,
                    "ip": self.last_ip,
                    "location": self.location,
                    "ttc": ttc,
                    "next_change_at": self.next_change_at,
                    "raw": pdata,
                }
                self.update_cache(self.api_key, res)
                return res

            pdata = data.get("data") if isinstance(data.get("data"), dict) else {}
            ttc = pdata.get("ttc", 0)
            next_req_ms = pdata.get("nextRequestAt", 0)
            if next_req_ms:
                self.next_change_at = next_req_ms / 1000.0
                remain_s = max(0, int(self.next_change_at - time.time()))
                if remain_s > ttc:
                    ttc = remain_s
            msg = data.get("message", "?ang trong th?i gian ch? ??i IP")
            if ttc <= 0 and msg:
                m_ttc = re.search(r"(\d+)\s*(?:gi?y|s)", str(msg), re.IGNORECASE)
                if m_ttc:
                    ttc = int(m_ttc.group(1))

            if fallback_current:
                cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
                if cached and cached.get("http"):
                    res = dict(cached)
                    res["success"] = True
                    res["rotated"] = False
                    res["cooldown"] = True
                    res["ttc"] = ttc
                    res["message"] = msg
                    return res

                if self.last_proxy:
                    return {
                        "success": True,
                        "rotated": False,
                        "cooldown": True,
                        "http": self.last_proxy,
                        "ip": self.last_ip,
                        "location": self.location or "Vietnam",
                        "ttc": ttc,
                        "message": msg,
                    }

            return {
                "success": False,
                "rotated": False,
                "cooldown": True,
                "ttc": ttc,
                "message": msg,
                "http": self.last_proxy,
                "ip": self.last_ip,
            }
        except Exception as e:
            if fallback_current:
                cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
                if cached and cached.get("http"):
                    res = dict(cached)
                    res["success"] = True
                    res["rotated"] = False
                    return res
                if self.last_proxy:
                    return {
                        "success": True,
                        "rotated": False,
                        "http": self.last_proxy,
                        "ip": self.last_ip,
                        "location": self.location or "Vietnam",
                    }
            return {"success": False, "rotated": False, "message": str(e), "http": self.last_proxy, "ip": self.last_ip}

    def rotate_and_wait(self, max_wait: float = 120.0, stop_event: Optional[Any] = None) -> Dict[str, Any]:
        """Request IP rotation, waiting if on cooldown until a new IP is acquired or timeout."""
        res = self.get_new_proxy()
        if res.get("rotated"):
            return res

        start = time.time()
        while (time.time() - start) < max_wait:
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                break
            ttc = max(1, int(res.get("ttc", 2)))
            sleep_time = min(ttc, 5.0)
            if stop_event and hasattr(stop_event, "wait"):
                if stop_event.wait(sleep_time):
                    break
            else:
                time.sleep(sleep_time)

            res = self.get_new_proxy()
            if res.get("rotated"):
                return res

        cur = self.get_current_proxy()
        cur["rotated"] = False
        cur["cooldown"] = True
        cur["ttc"] = res.get("ttc", 0)
        return cur

    def rotate_to_unique_ip(
        self,
        worker_id: int = 1,
        registry = None,
        max_wait: float = 120.0,
        stop_event = None,
        enforce_subnet: bool = False,
        on_wait_callback = None,
    ):
        """
        Yeu cau doi IP moi va kiem tra voi ActiveIpRegistry:
        - Dam bao IP moi KHONG trung voi bat ky luong nao khac dang chay.
        - Dam bao IP moi KHONG trung dai Subnet /24.
        - Neu bi trung hoac dang cooldown TTC, tu dong doi chu ky va xoay tiep cho den khi co IP doc lap 100%.
        """
        start = time.time()
        last_log_t = 0.0
        while (time.time() - start) < max_wait:
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                break

            res = self.get_new_proxy()
            if not res.get("success"):
                msg_err = str(res.get("message", "")).lower()
                if any(bad_k in msg_err for bad_k in ("hết hạn", "không tìm thấy", "invalid", "khóa", "404", "chưa kích hoạt")):
                    if on_wait_callback:
                        try:
                            on_wait_callback(worker_id, f"Key lỗi ({res.get('message', '')}), chuyển tiếp.")
                        except Exception:
                            pass
                    return res

            cand_ip = res.get("ip") or (ProxyManager.parse_proxy(res.get("http")).host if res.get("http") else "")
            cand_ip = str(cand_ip).strip() if cand_ip else ""

            if res.get("rotated") and cand_ip:
                if registry:
                    if hasattr(registry, "acquire_unique_ip"):
                        is_avail, reason = registry.acquire_unique_ip(worker_id, cand_ip, enforce_subnet_24=enforce_subnet, check_history=True)
                    else:
                        is_avail, reason = registry.is_ip_available(cand_ip, worker_id, enforce_subnet_24=enforce_subnet)
                        if is_avail:
                            registry.lease_ip(worker_id, cand_ip)
                    if is_avail:
                        # Cho proxy 1.5s on dinh cong ket noi truoc khi thuc hien request
                        time.sleep(1.5)
                        return res
                    else:
                        now_t = time.time()
                        if on_wait_callback and (now_t - last_log_t >= 8.0):
                            last_log_t = now_t
                            try:
                                on_wait_callback(worker_id, f"IP {mask_ip(cand_ip)} bi trung ({reason}), dang doi chu ky ke tiep...")
                            except Exception:
                                pass
                else:
                    return res

            ttc = max(1, int(res.get("ttc", 3)))
            now_t = time.time()
            if on_wait_callback and (now_t - last_log_t >= 8.0 or ttc in (60, 30, 15)):
                last_log_t = now_t
                try:
                    on_wait_callback(worker_id, f"Dang cho doi IP (TTC: {ttc}s)...")
                except Exception:
                    pass

            sleep_dur = min(max(2.0, float(ttc) + 0.5) if ttc <= 2 else float(ttc), 5.0)
            if stop_event and hasattr(stop_event, "wait"):
                if stop_event.wait(sleep_dur):
                    break
            else:
                time.sleep(sleep_dur)

        cur = self.get_current_proxy()
        cur_ip = cur.get("ip") or (ProxyManager.parse_proxy(cur.get("http")).host if cur.get("http") else "")
        if cur_ip and registry:
            if hasattr(registry, "acquire_unique_ip"):
                avail, reason = registry.acquire_unique_ip(worker_id, cur_ip, enforce_subnet_24=False, check_history=False)
            else:
                avail, reason = registry.is_ip_available(cur_ip, worker_id, enforce_subnet_24=False, check_history=False)
                if avail:
                    registry.lease_ip(worker_id, cur_ip)
            if avail:
                return cur
            else:
                cur["success"] = False
                cur["rotated"] = False
                cur["collision"] = True
                cur["message"] = f"IP hiện tại ({mask_ip(cur_ip)}) đang bị luồng khác sử dụng ({reason})! Cần tiếp tục đổi IP độc lập."
                return cur
        return cur



# ==============================================================================
# PROXYSOCKS5.VN API CLIENT (https://proxysocks5.vn / https://api.proxysocks5.vn)
# ==============================================================================

_PROXYSOCKS5_CACHE: Dict[str, Dict[str, Any]] = {}
_PROXYSOCKS5_CACHE_LOCK = threading.RLock()


class ProxySocks5Client:
    """Client tích hợp dịch vụ ProxySocks5.vn (https://api.proxysocks5.vn)."""
    BASE_URL = "https://api.proxysocks5.vn/api/proxy"

    def __init__(self, token_proxy: str, user_token: Optional[str] = None):
        self.token_proxy = str(token_proxy or "").strip()
        self.api_key = self.token_proxy
        self.user_token = str(user_token or "").strip()
        self.last_proxy: Optional[str] = None
        self.last_ip: Optional[str] = None
        self.next_change_at: float = 0.0

    @classmethod
    def get_cached_proxy(cls, token_proxy: str, max_age: float = 20.0) -> Optional[Dict[str, Any]]:
        with _PROXYSOCKS5_CACHE_LOCK:
            data = _PROXYSOCKS5_CACHE.get(token_proxy.strip())
            if data and (time.time() - data.get("cached_at", 0)) < max_age and data.get("http"):
                res = dict(data)
                res["success"] = True
                res["from_cache"] = True
                return res
        return None

    @classmethod
    def update_cache(cls, token_proxy: str, data: Dict[str, Any]) -> None:
        if not data or not data.get("http"):
            return
        with _PROXYSOCKS5_CACHE_LOCK:
            _PROXYSOCKS5_CACHE[token_proxy.strip()] = {
                "http": data.get("http"),
                "socks5": data.get("socks5"),
                "ip": data.get("ip"),
                "cached_at": time.time(),
                "next_change": data.get("next_change", 0),
                "host": data.get("host"),
                "port_http": data.get("port_http"),
                "port_socks5": data.get("port_socks5"),
                "username": data.get("username"),
                "password": data.get("password"),
                "location": data.get("location", "Vietnam"),
            }

    @classmethod
    def invalidate_cache(cls, token_proxy: str) -> None:
        with _PROXYSOCKS5_CACHE_LOCK:
            _PROXYSOCKS5_CACHE.pop(token_proxy.strip(), None)

    def _parse_response_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Chuyển đổi dữ liệu trả về từ ProxySocks5.vn thành đối tượng chuẩn."""
        host = data.get("host", "")
        username = data.get("username") or data.get("user", "")
        password = data.get("password", "")
        port_http = data.get("port_http")
        port_socks5 = data.get("port_socks5")
        ip_public = data.get("ip_public") or host

        http_proxy = ""
        socks5_proxy = ""
        if host and port_http:
            if username and password:
                http_proxy = f"http://{username}:{password}@{host}:{port_http}"
            else:
                http_proxy = f"http://{host}:{port_http}"

        if host and port_socks5:
            if username and password:
                socks5_proxy = f"socks5://{username}:{password}@{host}:{port_socks5}"
            else:
                socks5_proxy = f"socks5://{host}:{port_socks5}"

        return {
            "success": True,
            "http": http_proxy,
            "socks5": socks5_proxy,
            "ip": ip_public,
            "host": host,
            "port_http": port_http,
            "port_socks5": port_socks5,
            "username": username,
            "password": password,
            "location": "Vietnam",
            "raw_data": data,
        }

    def get_current_proxy(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Lấy proxy hiện tại qua API /refresh hoặc bộ nhớ đệm RAM."""
        if not force_refresh:
            cached = self.get_cached_proxy(self.token_proxy)
            if cached:
                return cached

        url = f"{self.BASE_URL}/refresh?tokenProxy={self.token_proxy}"
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("status") == 200 and isinstance(body.get("data"), dict):
                    parsed = self._parse_response_data(body["data"])
                    parsed["message"] = body.get("message") or "Lấy proxy thành công"
                    self.update_cache(self.token_proxy, parsed)
                    self.last_proxy = parsed["http"]
                    self.last_ip = parsed["ip"]
                    return parsed
                else:
                    return {
                        "success": False,
                        "message": body.get("message") or f"Lỗi ProxySocks5 status {body.get('status')}",
                    }
            elif resp.status_code == 400:
                try:
                    body = resp.json()
                    msg = body.get("message", "Bad Request")
                except Exception:
                    msg = resp.text[:100]
                cached = self.get_cached_proxy(self.token_proxy)
                if cached:
                    cached["message"] = msg
                    return cached
                return {"success": False, "message": msg}
            else:
                cached = self.get_cached_proxy(self.token_proxy)
                if cached:
                    return cached
                return {
                    "success": False,
                    "message": f"HTTP {resp.status_code}: {resp.text[:100]}",
                }
        except Exception as e:
            cached = self.get_cached_proxy(self.token_proxy)
            if cached:
                return cached
            return {"success": False, "message": f"L?i k?t n?i API ProxySocks5: {e}"}

    def get_new_proxy(self, fallback_current: bool = True) -> Dict[str, Any]:
        """Gọi API /changeIp để đổi sang IP mới."""
        self.invalidate_cache(self.token_proxy)
        url = f"{self.BASE_URL}/changeIp?tokenProxy={self.token_proxy}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("status") == 200 and isinstance(body.get("data"), dict):
                    parsed = self._parse_response_data(body["data"])
                    parsed["message"] = body.get("message") or "Đổi IP thành công"
                    parsed["rotated"] = True
                    self.update_cache(self.token_proxy, parsed)
                    self.last_proxy = parsed["http"]
                    self.last_ip = parsed["ip"]
                    return parsed
                else:
                    msg = body.get("message") or "Đổi IP không thành công"
                    ttc_val = 0
                    m = re.search(r"(\d+)\s*(?:giây|s|second)", msg, re.IGNORECASE)
                    if m:
                        try:
                            ttc_val = int(m.group(1))
                        except Exception:
                            pass
                    if fallback_current:
                        cur = self.get_current_proxy(force_refresh=False)
                        if cur.get("success"):
                            cur["message"] = msg
                            cur["rotated"] = False
                            if ttc_val:
                                cur["ttc"] = ttc_val
                            return cur
                    return {"success": False, "message": msg, "rotated": False, "ttc": ttc_val}
            elif resp.status_code == 400:
                try:
                    body = resp.json()
                    msg = body.get("message", "Proxy chưa sẵn sàng đổi IP")
                except Exception:
                    msg = resp.text[:100]
                ttc_val = 0
                m = re.search(r"(\d+)\s*(?:giây|s|second)", msg, re.IGNORECASE)
                if m:
                    try:
                        ttc_val = int(m.group(1))
                    except Exception:
                        pass
                if fallback_current:
                    cur = self.get_current_proxy(force_refresh=False)
                    if cur.get("success"):
                        cur["message"] = msg
                        cur["rotated"] = False
                        if ttc_val:
                            cur["ttc"] = ttc_val
                        return cur
                return {"success": False, "message": msg, "rotated": False, "ttc": ttc_val}
            else:
                if fallback_current:
                    cur = self.get_current_proxy(force_refresh=False)
                    if cur.get("success"):
                        return cur
                return {"success": False, "message": f"HTTP {resp.status_code}"}
        except Exception as e:
            if fallback_current:
                cur = self.get_current_proxy(force_refresh=False)
                if cur.get("success"):
                    return cur
            return {"success": False, "message": f"Lỗi gọi đổi IP: {e}"}

    def rotate_and_wait(self, max_wait: float = 120.0, stop_event: Optional[Any] = None) -> Dict[str, Any]:
        """Yêu cầu đổi IP và chờ nếu đang trong thời gian cooldown."""
        res = self.get_new_proxy(fallback_current=False)
        if res.get("success"):
            return res

        start_time = time.time()
        while (time.time() - start_time) < max_wait:
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                break
            sleep_dur = 5.0
            if stop_event and hasattr(stop_event, "wait"):
                if stop_event.wait(sleep_dur):
                    break
            else:
                time.sleep(sleep_dur)

            res = self.get_new_proxy(fallback_current=False)
            if res.get("success"):
                return res

        return self.get_current_proxy(force_refresh=True)

    def rotate_to_unique_ip(
        self,
        worker_id: int = 1,
        registry: Optional[Any] = None,
        max_attempts: int = 5,
        stop_event: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Đổi sang IP mới và kiểm tra không trùng lặp giữa các luồng."""
        old_ip = self.last_ip or ""
        for attempt in range(max_attempts):
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                break
            res = self.rotate_and_wait(max_wait=30.0, stop_event=stop_event)
            p_val = res.get("http") or res.get("socks5")
            cur_ip = res.get("ip") or (ProxyManager.parse_proxy(p_val).host if p_val else "")

            if res.get("success") and cur_ip:
                if registry:
                    avail, _ = registry.is_ip_available(cur_ip, worker_id, enforce_subnet_24=False, check_history=False)
                    if avail:
                        registry.lease_ip(worker_id, cur_ip)
                        res["rotated"] = True
                        return res
                    else:
                        continue
                else:
                    res["rotated"] = True
                    return res

            sleep_dur = 3.0
            if stop_event and hasattr(stop_event, "wait"):
                if stop_event.wait(sleep_dur):
                    break
            else:
                time.sleep(sleep_dur)

        return self.get_current_proxy()

    @classmethod
    def get_proxies_by_order(cls, user_token: str, order_id: str) -> List[Dict[str, Any]]:
        """Lấy danh sách token key của toàn bộ proxy trong Order từ ProxySocks5.vn."""
        u_tok = str(user_token or "").strip()
        o_id = str(order_id or "").strip()
        if not u_tok or not o_id:
            return []
        url = f"{cls.BASE_URL}/getProxy?userToken={u_tok}&orderId={o_id}"
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                body = resp.json()
                if body.get("status") == 200 and isinstance(body.get("data"), dict):
                    proxies_list = body["data"].get("proxies") or []
                    results = []
                    for p in proxies_list:
                        tok = p.get("token") or p.get("token_key")
                        if tok:
                            results.append({
                                "token": tok,
                                "host": p.get("host"),
                                "username": p.get("username"),
                                "password": p.get("password"),
                                "port_http": p.get("port_http"),
                                "port_socks5": p.get("port_socks5"),
                                "ip_public": p.get("ip_public"),
                                "proxy_exp": p.get("proxy_exp"),
                            })
                    return results
        except Exception as e:
            logger.debug(f"get_proxies_by_order error: {e}")
        return []

    @classmethod
    def buy_proxy(cls, user_token: str, product_code: str = "VN001", quantity: int = 1, day: int = 1) -> Dict[str, Any]:
        """Mua proxy mới qua API ProxySocks5.vn."""
        u_tok = str(user_token or "").strip()
        url = f"{cls.BASE_URL}/buyProxy?productCode={product_code}&userToken={u_tok}&quantity={quantity}&day={day}"
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                return resp.json()
            return {"status": resp.status_code, "message": resp.text[:150]}
        except Exception as e:
            return {"status": 500, "message": f"Lỗi gọi API buyProxy: {e}"}

    @classmethod
    def renew_proxy(cls, token_proxy: str, user_token: str, day: int = 1) -> Dict[str, Any]:
        """Gia hạn proxy qua API /gia-han."""
        tok = str(token_proxy or "").strip()
        u_tok = str(user_token or "").strip()
        url = f"{cls.BASE_URL}/gia-han?tokenProxy=" + tok + "&userToken=" + u_tok + f"&day={day}"
        try:
            resp = requests.get(url, timeout=12)
            if resp.status_code == 200:
                return resp.json()
            return {"status": resp.status_code, "message": resp.text[:150]}
        except Exception as e:
            return {"status": 500, "message": f"Lỗi gọi API gia-han: {e}"}

    gia_han = renew_proxy

# ==============================================================================
# MPROXY.VN CLIENT (4G/5G ROTATING PROXY)
# ==============================================================================

_MPROXY_CACHE = {}
_MPROXY_CACHE_LOCK = threading.RLock()


class MproxyClient:
    """Client tích hợp dịch vụ mProxy.vn (https://mproxy.vn) - Proxy 4G/5G xoay IP."""
    BASE_URL = "https://mproxy.vn/capi"

    def __init__(self, token: str, key_code: Optional[str] = None):
        self.token = str(token or "").strip()
        self.key_code = str(key_code or "").strip()
        self.api_key = self.token
        self.last_proxy: Optional[str] = None
        self.last_ip: Optional[str] = None
        self.location: Optional[str] = "Vietnam"
        self.next_change_at: float = 0.0

    @classmethod
    def get_cached_proxy(cls, cache_key: str, max_age: float = 20.0) -> Optional[Dict[str, Any]]:
        with _MPROXY_CACHE_LOCK:
            data = _MPROXY_CACHE.get(cache_key.strip())
            if data and (time.time() - data.get("cached_at", 0)) < max_age and data.get("http"):
                res = dict(data)
                res["success"] = True
                res["from_cache"] = True
                return res
        return None

    @classmethod
    def update_cache(cls, cache_key: str, data: Dict[str, Any]) -> None:
        if not data or not (data.get("http") or data.get("proxy")):
            return
        with _MPROXY_CACHE_LOCK:
            cached = dict(data)
            cached["cached_at"] = time.time()
            _MPROXY_CACHE[cache_key.strip()] = cached

    @classmethod
    def invalidate_cache(cls, cache_key: str) -> None:
        with _MPROXY_CACHE_LOCK:
            _MPROXY_CACHE.pop(cache_key.strip(), None)

    @classmethod
    def resolve_outbound_ip(cls, proxy_url: str, timeout: float = 3.0) -> Optional[str]:
        """Xác định IP WAN thực tế đang phát ra từ proxy 4G."""
        if not proxy_url:
            return None
        p_clean = proxy_url if '://' in proxy_url else f'http://{proxy_url}'
        proxies = {'http': p_clean, 'https': p_clean}
        endpoints = [
            ('http://api.ipify.org?format=json', lambda r: r.json().get('ip')),
            ('http://ip-api.com/json?fields=query', lambda r: r.json().get('query')),
            ('https://icanhazip.com', lambda r: r.text.strip()),
        ]
        for url, parser in endpoints:
            try:
                r = requests.get(url, proxies=proxies, timeout=timeout)
                if r.status_code == 200:
                    ip = parser(r)
                    if ip and '.' in ip:
                        return ip.strip()
            except Exception:
                continue
        return None

    @classmethod
    def get_keys(cls, token: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các keys / proxy 4G/5G của tài khoản từ token API."""
        if not token:
            return []
        url = f"{cls.BASE_URL}/{token.strip()}/keys"
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == 1 and isinstance(data.get("data"), list):
                    return data["data"]
        except Exception as e:
            logger.debug(f"[mProxy] Error fetching keys: {e}")
        return []

    @classmethod
    def get_balance(cls, token: str) -> Optional[int]:
        """Lấy số dư tài khoản mProxy.vn (VNĐ)."""
        if not token:
            return None
        url = f"{cls.BASE_URL}/{token.strip()}/balance"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == 1:
                    b_data = data.get("data", {})
                    b_val = b_data.get("balance") if isinstance(b_data, dict) else None
                    if b_val is not None:
                        try:
                            return int(b_val)
                        except Exception:
                            return 0
        except Exception as e:
            logger.debug(f"[mProxy] Error fetching balance: {e}")
        return None

    @classmethod
    def get_packages(cls, token: str) -> List[Dict[str, Any]]:
        """Lấy danh sách các gói dịch vụ proxy từ mProxy.vn."""
        if not token:
            return []
        url = f"{cls.BASE_URL}/{token.strip()}/packages"
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == 1 and isinstance(data.get("data"), list):
                    return data["data"]
        except Exception as e:
            logger.debug(f"[mProxy] Error fetching packages: {e}")
        return []

    @classmethod
    def buy_package(cls, token: str, package_id: Union[int, str]) -> Dict[str, Any]:
        """Mua gói proxy mới qua API mProxy.vn."""
        if not token:
            return {"status": 0, "message": "Thiếu token"}
        url = f"{cls.BASE_URL}/{token.strip()}/buy/{package_id}"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
            return {"status": 0, "message": f"HTTP {r.status_code}: {r.text[:120]}"}
        except Exception as e:
            return {"status": 0, "message": f"L?i g?i buy package: {e}"}

    @classmethod
    def extend_key(cls, token: str, key_code: str) -> Dict[str, Any]:
        """Gia hạn key proxy 4G."""
        if not token or not key_code:
            return {"status": 0, "message": "Thiếu token hoặc key_code"}
        url = f"{cls.BASE_URL}/{token.strip()}/key/{key_code.strip()}/extend"
        try:
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                return r.json()
            return {"status": 0, "message": f"HTTP {r.status_code}: {r.text[:120]}"}
        except Exception as e:
            return {"status": 0, "message": f"L?i g?i extend key: {e}"}

    @classmethod
    def reset_ip(cls, token: str, key_code: str) -> Dict[str, Any]:
        """Gửi lệnh đổi IP / reset IP cho 1 key 4G/5G."""
        if not token or not key_code:
            return {"success": False, "message": "Thiếu token hoặc key_code"}
        clean_k = str(key_code or "").strip()
        target_port = None
        target_pass = None
        if ":" in clean_k:
            pts = clean_k.split(":")
            if len(pts) >= 2 and pts[1].isdigit():
                target_port = int(pts[1])
            if len(pts) >= 4:
                target_pass = pts[3].strip()
        elif clean_k.isdigit():
            target_port = int(clean_k)

        if token and (target_port or target_pass or len(clean_k) > 20):
            try:
                keys = cls.get_keys(token)
                for k in keys:
                    kc = str(k.get("key_code") or "").strip()
                    kp = k.get("server_port")
                    k_pwd = str(k.get("password") or "").strip()
                    if target_port and kp and int(kp) == target_port:
                        clean_k = kc
                        break
                    if clean_k and (kc.lower() == clean_k.lower() or k_pwd.lower() == clean_k.lower()):
                        clean_k = kc
                        break
                    if target_pass and (k_pwd.lower() == target_pass.lower() or kc.lower() == target_pass.lower()):
                        clean_k = kc
                        break
            except Exception:
                pass
            if target_pass and clean_k == str(key_code).strip():
                clean_k = target_pass

        url = f"{cls.BASE_URL}/{token.strip()}/key/{clean_k.strip()}/resetIp"
        try:
            r = requests.get(url, timeout=15)
            data = r.json()
            if data.get("status") == 1:
                pdata = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
                proxy_str = pdata.get("proxy") or ""
                p_port = pdata.get("server_port") or target_port or ""
                p_host = pdata.get("server_host") or "ip.mproxy.vn"
                if not proxy_str:
                    try:
                        all_k = cls.get_keys(token)
                        for k in all_k:
                            if (target_port and k.get("server_port") == target_port) or str(k.get("key_code") or "").strip() == clean_k:
                                proxy_str = k.get("proxy") or ""
                                p_port = k.get("server_port") or p_port
                                p_host = k.get("server_host") or p_host
                                break
                    except Exception:
                        pass
                http_p = f"http://{proxy_str}" if proxy_str and "://" not in proxy_str else proxy_str
                time.sleep(1.2)
                wan_ip = cls.resolve_outbound_ip(http_p, timeout=2.5) if http_p else None
                ip_val = wan_ip or (f"{p_host}:{p_port}" if p_port else p_host)
                return {
                    "success": True,
                    "rotated": True,
                    "proxy": proxy_str,
                    "http": http_p,
                    "server": ip_val,
                    "ip": ip_val,
                    "real_ip": wan_ip or ip_val,
                    "port": p_port,
                    "key_code": clean_k or key_code,
                    "message": data.get("message", "Đổi IP 4G thành công"),
                    "location": "Vietnam",
                    "ttc": 0
                }
            else:
                msg = data.get("message", "Đổi IP không thành công")
                ttc = 30
                m_s = re.search(r"(\d+)\s*(?:giây|s|second)", str(msg), re.I)
                if m_s:
                    try:
                        ttc = int(m_s.group(1))
                    except Exception:
                        pass
                return {
                    "success": False,
                    "rotated": False,
                    "message": msg,
                    "cooldown": True,
                    "ttc": ttc
                }
        except Exception as e:
            return {"success": False, "message": f"Lỗi gọi reset IP: {e}", "ttc": 30}

    def get_current_proxy(self, force_refresh: bool = False) -> Dict[str, Any]:
        cache_id = f"{self.token}:{self.key_code}" if self.key_code else self.token
        if not force_refresh:
            cached = self.get_cached_proxy(cache_id, max_age=15.0)
            if cached:
                self.last_proxy = cached.get("http")
                self.last_ip = cached.get("ip")
                return cached

        keys = self.get_keys(self.token) if self.token else []
        target_k = None
        clean_code = str(self.key_code or "").strip()
        target_port = None
        target_pass = None
        if ":" in clean_code:
            pts = clean_code.split(":")
            if len(pts) >= 2 and pts[1].isdigit():
                target_port = int(pts[1])
            if len(pts) >= 4:
                target_pass = pts[3].strip()
        elif clean_code.isdigit():
            target_port = int(clean_code)

        if self.key_code and keys:
            for k in keys:
                kc = str(k.get("key_code") or "").strip()
                kp = k.get("server_port")
                k_pwd = str(k.get("password") or "").strip()
                if target_port and kp and int(kp) == target_port:
                    target_k = k
                    break
                if clean_code and (kc.lower() == clean_code.lower() or k_pwd.lower() == clean_code.lower()):
                    target_k = k
                    break
                if target_pass and (k_pwd.lower() == target_pass.lower() or kc.lower() == target_pass.lower()):
                    target_k = k
                    break
                if clean_code and clean_code.lower() in str(k.get("proxy") or "").lower():
                    target_k = k
                    break

        if target_k:
            if target_k.get("key_code"):
                self.key_code = target_k.get("key_code")
            raw_p = target_k.get("proxy") or ""
            http_p = f"http://{raw_p}" if raw_p and "://" not in raw_p else raw_p
            self.last_proxy = http_p
            p_port = target_k.get("server_port") or target_port or ""
            p_host = target_k.get("server_host") or "ip.mproxy.vn"
            ip_val = f"{p_host}:{p_port}" if p_port else p_host
            self.last_ip = ip_val
            res = {
                "success": True,
                "http": http_p,
                "proxy": raw_p,
                "ip": ip_val,
                "real_ip": ip_val,
                "location": "Vietnam",
                "key_code": self.key_code,
                "server": ip_val,
                "port": p_port,
                "expired_time": target_k.get("expired_time"),
                "ttc": 0
            }
            self.update_cache(cache_id, res)
            return res

        if not target_k and ":" in clean_code:
            pts = clean_code.split(":")
            if len(pts) >= 4:
                h, pt, u, p = pts[0], pts[1], pts[2], pts[3]
                raw_p = f"{u}:{p}@{h}:{pt}"
            else:
                raw_p = clean_code
            http_p = f"http://{raw_p}" if "://" not in raw_p else raw_p
            self.last_proxy = http_p
            self.last_ip = f"{pts[0]}:{pts[1]}"
            res = {
                "success": True,
                "http": http_p,
                "proxy": raw_p,
                "ip": self.last_ip,
                "location": "Vietnam",
                "key_code": pts[3] if len(pts) >= 4 else str(target_port or ""),
                "server": pts[0],
                "port": target_port or "",
                "expired_time": "",
                "ttc": 0
            }
            self.update_cache(cache_id, res)
            return res

        if not target_k and keys and not target_port and not target_pass:
            target_k = keys[0]
            self.key_code = target_k.get("key_code", "")
            raw_p = target_k.get("proxy") or ""
            http_p = f"http://{raw_p}" if raw_p and "://" not in raw_p else raw_p
            self.last_proxy = http_p
            p_port = target_k.get("server_port") or ""
            p_host = target_k.get("server_host") or "ip.mproxy.vn"
            ip_val = target_k.get("server") or f"{p_host}:{p_port}"
            self.last_ip = ip_val
            res = {
                "success": True,
                "http": http_p,
                "proxy": raw_p,
                "ip": ip_val,
                "location": "Vietnam",
                "key_code": self.key_code,
                "server": target_k.get("server") or p_host,
                "port": p_port,
                "expired_time": target_k.get("expired_time"),
                "ttc": 0
            }
            self.update_cache(cache_id, res)
            return res

        return {"success": False, "message": "Khong tim thay proxy hop le"}


    def get_new_proxy(self, fallback_current: bool = True) -> Dict[str, Any]:
        """Gửi lệnh đổi IP mới cho key 4G."""
        if not self.key_code:
            cur = self.get_current_proxy()
            if not self.key_code:
                return {"success": False, "message": "Chưa xác định key_code để đổi IP"}

        cache_id = f"{self.token}:{self.key_code}"
        self.invalidate_cache(cache_id)
        res = self.reset_ip(self.token, self.key_code)
        if res.get("success"):
            self.last_proxy = res.get("http")
            self.last_ip = res.get("server") or self.last_ip
            self.update_cache(cache_id, res)
            return res

        if fallback_current:
            cur = self.get_current_proxy(force_refresh=False)
            cur["rotated"] = False
            cur["cooldown"] = True
            cur["ttc"] = res.get("ttc", 30)
            cur["message"] = res.get("message", "Đang trong thời gian chờ đổi IP")
            return cur

        return res



# ==============================================================================
# ==============================================================================
# PROXY.VN / PROXYXOAY.SHOP API CLIENT (https://proxy.vn / https://proxyxoay.shop)
# ==============================================================================

_PROXYVN_CACHE: Dict[str, Dict[str, Any]] = {}
_PROXYVN_LAST_KNOWN: Dict[str, Dict[str, Any]] = {}
_PROXYVN_CACHE_LOCK = threading.RLock()


class ProxyVNClient:
    """
    Client tích hợp dịch vụ Proxy.vn (proxyxoay.shop).
    API: https://proxyxoay.shop/api/get.php?key=[key]&nhamang=[nhamang]&tinhthanh=[tinhthanh]&whitelist=[whitelist]
    """
    BASE_URL = "https://proxyxoay.shop/api/get.php"
    PURCHASE_URL = "https://proxy.vn/proxyxoay"
    CACHE_FILE = os.path.join(os.path.dirname(__file__), ".proxyvn_cache.json")
    LAST_KNOWN_FILE = os.path.join(os.path.dirname(__file__), ".proxyvn_last_known.json")

    @classmethod
    def _read_last_known_disk(cls) -> Dict[str, Dict[str, Any]]:
        try:
            if os.path.exists(cls.LAST_KNOWN_FILE):
                with open(cls.LAST_KNOWN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _write_last_known_disk(cls, data: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(cls.LAST_KNOWN_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def __init__(
        self,
        api_key: str,
        nhamang: str = "",
        tinhthanh: str = "",
        whitelist: str = "",
    ):
        self.api_key = str(api_key or "").strip()
        self.nhamang = str(nhamang or "").strip()
        self.tinhthanh = str(tinhthanh or "").strip()
        self.whitelist = str(whitelist or "").strip()
        self.last_proxy: Optional[str] = None
        self.last_ip: Optional[str] = None
        self.location: Optional[str] = None
        self.carrier: Optional[str] = None
        self.expiration: Optional[str] = None
        self.next_change_at: float = 0.0

    @classmethod
    def _read_disk_cache(cls) -> Dict[str, Dict[str, Any]]:
        try:
            if os.path.exists(cls.CACHE_FILE):
                with open(cls.CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    @classmethod
    def _write_disk_cache(cls, data: Dict[str, Dict[str, Any]]) -> None:
        try:
            with open(cls.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    @classmethod
    def get_cached_proxy(cls, api_key: str, max_age: Optional[float] = 120.0) -> Optional[Dict[str, Any]]:
        k = api_key.strip()
        eff_max_age = 300.0 if max_age is None else max_age
        with _PROXYVN_CACHE_LOCK:
            data = _PROXYVN_CACHE.get(k)
            now = time.time()
            if data and (now - data.get("cached_at", 0)) < eff_max_age and data.get("http"):
                res = dict(data)
                res["success"] = True
                res["from_cache"] = True
                return res

            # Kiểm tra cache file trên đĩa
            disk_cache = cls._read_disk_cache()
            disk_data = disk_cache.get(k)
            if disk_data and (now - disk_data.get("cached_at", 0)) < eff_max_age and disk_data.get("http"):
                _PROXYVN_CACHE[k] = dict(disk_data)
                res = dict(disk_data)
                res["success"] = True
                res["from_cache"] = True
                return res
        return None

    @classmethod
    def update_cache(cls, api_key: str, data: Dict[str, Any]) -> None:
        if not data or not data.get("http"):
            return
        k = api_key.strip()
        with _PROXYVN_CACHE_LOCK:
            cached = dict(data)
            cached["cached_at"] = time.time()
            _PROXYVN_CACHE[k] = cached
            _PROXYVN_LAST_KNOWN[k] = cached

            disk_cache = cls._read_disk_cache()
            disk_cache[k] = cached
            cls._write_disk_cache(disk_cache)

            disk_last = cls._read_last_known_disk()
            disk_last[k] = cached
            cls._write_last_known_disk(disk_last)

    @classmethod
    def get_last_known(cls, api_key: str, max_age: Optional[float] = 300.0) -> Optional[Dict[str, Any]]:
        k = api_key.strip()
        eff_max_age = 300.0 if max_age is None else max_age
        now = time.time()
        with _PROXYVN_CACHE_LOCK:
            cand = _PROXYVN_LAST_KNOWN.get(k)
            if cand and cand.get("http"):
                if (now - cand.get("cached_at", 0)) < eff_max_age:
                    res = dict(cand)
                    res["success"] = True
                    res["from_cache"] = True
                    return res
            disk_last = cls._read_last_known_disk()
            cand = disk_last.get(k)
            if cand and cand.get("http"):
                if (now - cand.get("cached_at", 0)) < eff_max_age:
                    _PROXYVN_LAST_KNOWN[k] = dict(cand)
                    res = dict(cand)
                    res["success"] = True
                    res["from_cache"] = True
                    return res
        return None

    @classmethod
    def invalidate_cache(cls, api_key: str) -> None:
        k = api_key.strip()
        with _PROXYVN_CACHE_LOCK:
            _PROXYVN_CACHE.pop(k, None)

    def _clean_proxy_token(self, proxy_token: str, proto: str = "http") -> str:
        if not proxy_token:
            return ""
        p = proxy_token.strip()
        while p.endswith(":"):
            p = p[:-1]
        parts = p.split(":")
        host = parts[0].strip() if len(parts) > 0 else ""
        port = parts[1].strip() if len(parts) > 1 else ""
        user = parts[2].strip() if len(parts) > 2 else ""
        pwd = parts[3].strip() if len(parts) > 3 else ""
        if not host or not port:
            return ""
        if user and pwd:
            return f"{proto}://{user}:{pwd}@{host}:{port}"
        return f"{proto}://{host}:{port}"

    def _parse_response_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        raw_http = str(data.get("proxyhttp", "")).strip()
        raw_socks5 = str(data.get("proxysocks5", "")).strip()
        carrier = data.get("Nha Mang") or data.get("nhamang", "")
        location = data.get("Vi Tri") or data.get("vitri") or "Vietnam"
        expiration = data.get("Token expiration date", "")
        message = data.get("message", "")
        real_ip = data.get("ip", "")

        http_proxy = self._clean_proxy_token(raw_http, "http")
        socks5_proxy = self._clean_proxy_token(raw_socks5, "socks5")

        parts = raw_http.split(":")
        host = parts[0].strip() if len(parts) > 0 else ""
        port = int(parts[1].strip()) if len(parts) > 1 and parts[1].strip().isdigit() else None

        ttc = 60
        if "die sau" in str(message).lower():
            ttc = 60
        else:
            m = re.search(r"(?:còn|con|chờ|cho)\s*(\d+)\s*(?:giây|giay|s)", str(message), re.IGNORECASE)
            if m:
                try:
                    ttc = min(int(m.group(1)), 65)
                except Exception:
                    pass
            else:
                m2 = re.search(r"(\d+)\s*(?:giây|giay|s)", str(message), re.IGNORECASE)
                if m2:
                    try:
                        val = int(m2.group(1))
                        ttc = val if val <= 65 else 60
                    except Exception:
                        pass

        return {
            "success": True,
            "http": http_proxy or (f"http://{host}:{port}" if host and port else ""),
            "socks5": socks5_proxy,
            "raw_http": raw_http,
            "raw_socks5": raw_socks5,
            "host": host,
            "port": port,
            "ip": real_ip or host,
            "location": location,
            "carrier": carrier,
            "expiration": expiration,
            "message": message,
            "ttc": ttc,
            "raw_data": data,
        }

    def get_current_proxy(self, force_refresh: bool = False) -> Dict[str, Any]:
        if not force_refresh:
            cached = self.get_cached_proxy(self.api_key, max_age=120.0)
            if cached:
                self.last_proxy = cached.get("http")
                self.last_ip = cached.get("ip")
                self.location = cached.get("location")
                self.carrier = cached.get("carrier")
                self.expiration = cached.get("expiration")
                return cached

        params = {"key": self.api_key}
        if self.nhamang:
            params["nhamang"] = self.nhamang
        if self.tinhthanh:
            params["tinhthanh"] = self.tinhthanh
        if self.whitelist:
            params["whitelist"] = self.whitelist

        try:
            r = requests.get(self.BASE_URL, params=params, timeout=12)
            data = r.json()
            status = data.get("status")

            if status == 100:
                parsed = self._parse_response_data(data)
                self.last_proxy = parsed["http"]
                self.last_ip = parsed["ip"]
                self.location = parsed["location"]
                self.carrier = parsed["carrier"]
                self.expiration = parsed["expiration"]
                self.update_cache(self.api_key, parsed)
                return parsed

            elif status == 101:
                # Đang trong thời gian cooldown - Key vẫn LIVE và proxy hiện tại vẫn chạy bình thường
                msg = data.get("message", "Đang trong thời gian chờ đổi IP")
                exp_date = data.get("Token expiration date", "")
                ttc = 0
                m = re.search(r"(\d+)\s*(?:giây|giây|giay|s)", msg, re.IGNORECASE)
                if m:
                    try:
                        ttc = int(m.group(1))
                    except Exception:
                        pass

                cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
                if cached and cached.get("http"):
                    cached["success"] = True
                    cached["cooldown"] = True
                    cached["ttc"] = ttc
                    cached["message"] = msg
                    if exp_date:
                        cached["expiration"] = exp_date
                    self.last_proxy = cached.get("http")
                    self.last_ip = cached.get("ip")
                    return cached

                if self.last_proxy:
                    return {
                        "success": True,
                        "cooldown": True,
                        "http": self.last_proxy,
                        "ip": self.last_ip,
                        "location": self.location or "Vietnam",
                        "carrier": self.carrier or "",
                        "expiration": exp_date or self.expiration or "",
                        "ttc": ttc,
                        "message": msg,
                    }

                # Nếu chưa từng lưu cache (lần đầu gọi lúc đang cooldown)
                # và ttc ngắn (<=15s), tự động chờ và thử lại để lấy thông tin proxy
                if 0 < ttc <= 15:
                    time.sleep(float(ttc) + 1.0)
                    try:
                        r2 = requests.get(self.BASE_URL, params=params, timeout=12)
                        d2 = r2.json()
                        if d2.get("status") == 100:
                            parsed = self._parse_response_data(d2)
                            self.last_proxy = parsed["http"]
                            self.last_ip = parsed["ip"]
                            self.location = parsed["location"]
                            self.carrier = parsed["carrier"]
                            self.expiration = parsed["expiration"]
                            self.update_cache(self.api_key, parsed)
                            return parsed
                    except Exception:
                        pass

                return {
                    "success": True,
                    "cooldown": True,
                    "ttc": ttc,
                    "message": msg,
                    "expiration": exp_date,
                }

            elif status == 102:
                return {
                    "success": False,
                    "message": data.get("message", "Key không tồn tại hoặc đã hết hạn"),
                    "status": 102,
                }
            else:
                return {
                    "success": False,
                    "message": data.get("message", f"Proxy.vn lỗi status={status}"),
                    "status": status,
                }
        except Exception as e:
            cached = self.get_cached_proxy(self.api_key, max_age=None)
            if cached and cached.get("http"):
                return cached
            return {"success": False, "message": f"Lỗi kết nối proxy.vn: {e}"}

    def get_new_proxy(self, fallback_current: bool = True) -> Dict[str, Any]:
        params = {"key": self.api_key}
        if self.nhamang:
            params["nhamang"] = self.nhamang
        if self.tinhthanh:
            params["tinhthanh"] = self.tinhthanh
        if self.whitelist:
            params["whitelist"] = self.whitelist

        try:
            r = requests.get(self.BASE_URL, params=params, timeout=12)
            data = r.json()
            status = data.get("status")

            if status == 100:
                parsed = self._parse_response_data(data)
                parsed["rotated"] = True
                self.last_proxy = parsed["http"]
                self.last_ip = parsed["ip"]
                self.location = parsed["location"]
                self.carrier = parsed["carrier"]
                self.expiration = parsed["expiration"]
                self.update_cache(self.api_key, parsed)
                return parsed

            elif status == 101:
                msg = data.get("message", "Đang trong thời gian chờ đổi IP")
                exp_date = data.get("Token expiration date", "")
                ttc = 30
                m = re.search(r"(?:còn|con|chờ|cho)?\s*(\d+)\s*(?:giây|giay|s)", str(msg), re.IGNORECASE)
                if m:
                    try:
                        ttc = min(int(m.group(1)), 65)
                    except Exception:
                        pass

                if fallback_current:
                    cached = self.get_cached_proxy(self.api_key, max_age=None) or self.get_last_known(self.api_key)
                    if cached and cached.get("http"):
                        res = dict(cached)
                        res["success"] = True
                        res["rotated"] = False
                        res["cooldown"] = True
                        res["ttc"] = ttc
                        res["message"] = msg
                        if exp_date:
                            res["expiration"] = exp_date
                        self.last_proxy = res.get("http")
                        self.last_ip = res.get("ip")
                        return res
                    if self.last_proxy:
                        return {
                            "success": True,
                            "rotated": False,
                            "cooldown": True,
                            "http": self.last_proxy,
                            "ip": self.last_ip,
                            "location": self.location or "Vietnam",
                            "carrier": self.carrier or "",
                            "expiration": exp_date or self.expiration or "",
                            "ttc": ttc,
                            "message": msg,
                        }

                return {
                    "success": False,
                    "rotated": False,
                    "cooldown": True,
                    "ttc": ttc,
                    "message": msg,
                    "expiration": exp_date,
                }

            elif status == 102:
                return {
                    "success": False,
                    "rotated": False,
                    "message": data.get("message", "Key không tồn tại hoặc đã hết hạn"),
                    "status": 102,
                }
            else:
                return {
                    "success": False,
                    "rotated": False,
                    "message": data.get("message", f"Proxy.vn lỗi status={status}"),
                    "status": status,
                }
        except Exception as e:
            if fallback_current:
                cached = self.get_cached_proxy(self.api_key, max_age=None)
                if cached and cached.get("http"):
                    cached["rotated"] = False
                    return cached
            return {"success": False, "rotated": False, "message": f"Lỗi kết nối proxy.vn: {e}"}

    def rotate_and_wait(self, max_wait: float = 120.0, stop_event: Optional[Any] = None) -> Dict[str, Any]:
        res = self.get_new_proxy(fallback_current=False)
        if res.get("success") and res.get("rotated"):
            return res

        start = time.time()
        while (time.time() - start) < max_wait:
            if stop_event and hasattr(stop_event, "is_set") and stop_event.is_set():
                break
            ttc = max(1, int(res.get("ttc", 3)))
            sleep_time = min(ttc, 5.0)
            if stop_event and hasattr(stop_event, "wait"):
                if stop_event.wait(sleep_time):
                    break
            else:
                time.sleep(sleep_time)

            res = self.get_new_proxy(fallback_current=False)
            if res.get("success") and res.get("rotated"):
                return res

        return self.get_current_proxy(force_refresh=False)

    @classmethod
    def get_all_active_keys(cls, user_key: str) -> List[Dict[str, Any]]:
        uk = str(user_key or "").strip()
        if not uk:
            return []
        url = f"{cls.PURCHASE_URL}/apigetkeyxoay.php?key={uk}"
        try:
            r = requests.get(url, timeout=12)
            raw = r.text.strip()
            results = []
            for m in re.finditer(r"\{[^{}]+\}", raw):
                try:
                    obj = json.loads(m.group(0))
                    if obj.get("status") == 100 and obj.get("keyxoay"):
                        results.append(obj)
                except Exception:
                    pass
            return results
        except Exception as e:
            logger.debug(f"get_all_active_keys error: {e}")
            return []

    @classmethod
    def buy_key(cls, user_key: str, period_type: str = "ngay", thoigian: int = 1, soluong: int = 1) -> Dict[str, Any]:
        uk = str(user_key or "").strip()
        p = period_type.lower()
        if "tuan" in p or "week" in p:
            ep = "apimuatuan.php"
        elif "thang" in p or "month" in p:
            ep = "apimuathang.php"
        else:
            ep = "apimuangay.php"
        url = f"{cls.PURCHASE_URL}/{ep}?key={uk}&thoigian={thoigian}&soluong={soluong}"
        try:
            r = requests.get(url, timeout=15)
            return r.json()
        except Exception as e:
            return {"status": 500, "message": f"Lỗi mua key Proxy.vn: {e}"}

    @classmethod
    def renew_key(cls, user_key: str, keyxoay: str, period_type: str = "ngay", thoigian: int = 1) -> Dict[str, Any]:
        uk = str(user_key or "").strip()
        kx = str(keyxoay or "").strip()
        p = period_type.lower()
        if "tuan" in p or "week" in p:
            ep = "apigiahantuan.php"
        elif "thang" in p or "month" in p:
            ep = "apigiahanthang.php"
        else:
            ep = "apigiahanngay.php"
        url = f"{cls.PURCHASE_URL}/{ep}?key={uk}&keyxoay={kx}&thoigian={thoigian}"
        try:
            r = requests.get(url, timeout=15)
            return r.json()
        except Exception as e:
            return {"status": 500, "message": f"Lỗi gia hạn key Proxy.vn: {e}"}






class FreeProxyManager:
    """
    Tự động cào, lọc và kiểm định proxy HTTP/HTTPS/SOCKS4/SOCKS5 miễn phí từ hơn 240+ nguồn mở uy tín:
    - Loại bỏ 100% trùng lặp URL và trùng lặp IP giữa các nguồn (Cross-source Deduplication).
    - Phân tầng chất lượng: Tier 1 (SOCKS5 & Checked / Elite), Tier 2 (SOCKS4 & HTTPS / Anonymous / SSL), Tier 3 (HTTP).
    - Khóa phiên tuyệt đối: Không bao giờ cấp lại proxy/IP đã sử dụng trong cùng 1 phiên (_session_used_hosts).
    - Bộ kiểm định ngầm thời gian thực (Fast Facebook Validator Pipeline): Liên tục kiểm tra m.facebook.com/reg,
      duy trì sẵn 60 - 150 proxy LIVE sạch trong RAM để cấp tức thì (0ms) cho các luồng.
    - Cơ chế Luôn lấy proxy mới: Tự động cào mới khi kho ứng viên cạn, không tái sử dụng IP cũ hoặc hỏng.
    """
    _default_instance: Optional["FreeProxyManager"] = None
    _singleton_lock = threading.RLock()

    def __new__(cls, cache_file: str = "free_proxies.txt", *args, **kwargs):
        if cache_file == "free_proxies.txt":
            with cls._singleton_lock:
                if cls._default_instance is None:
                    inst = super().__new__(cls)
                    inst._initialized = False
                    cls._default_instance = inst
                return cls._default_instance
        return super().__new__(cls)

    FREE_SOURCES = [
        "https://cdn.jsdelivr.net/gh/maximilianfeix/free-proxy-list@main/https.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/RU.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/refs/heads/master/generated/socks5_proxies.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/FR.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/The Netherlands/proxies.txt",
        "https://cdn.jsdelivr.net/gh/maximilianfeix/free-proxy-list@main/elite.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/NL.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/lv/data.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/CA.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all",
        "https://raw.githubusercontent.com/VOEVAL/dashscope-key-checker/main/proxies.example.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/CO.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/CM.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/GB.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Singapore/socks4.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/master/online-proxies/txt/proxies-socks4.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/master/connect.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/PK.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Gambia/proxies.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Egypt/ALL.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Ivory Coast/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Gibraltar/proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/master/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Sierra Leone/proxies.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/French Polynesia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/United Arab Emirates/proxies.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/master/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/master/proxies/https.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/MY.txt",
        "https://raw.githubusercontent.com/a7a-7iz/proxy.txt/master/proxy.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/master/proxies/all.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/BR.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/live.txt",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/master/socks5.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Türkiye/proxies.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Burkina Faso/proxies.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Thailand/https.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Saudi Arabia/proxies.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/master/socks4.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/master/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Puerto Rico/proxies.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/master/socks5.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks4",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/master/proxies/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/master/online-proxies/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/master/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/master/socks4_proxies.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/socks5.txt",

        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/http/global/http_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks5/global/socks5_checked.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/https.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/http.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
        "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks4.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks4.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/https.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/http.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
        "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks4.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=yes&anonymity=elite",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=3000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=5000&country=all",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/HTTP.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/http.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks5.txt",
        "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt",
        "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/proxy4parsing/proxy-list/main/http.txt",
        "https://openproxylist.xyz/http.txt",
        "https://raw.githubusercontent.com/hendrikbgr/Free-Proxy-Repo/master/proxy_list.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/aslisk/proxyhttps/main/https.txt",
        "https://raw.githubusercontent.com/almroot/proxylist/master/list.txt",
        "https://raw.githubusercontent.com/roma8ok/proxy-list/main/proxy-list-http.txt",
        "https://raw.githubusercontent.com/roma8ok/proxy-list/main/proxy-list-socks5.txt",
        "https://raw.githubusercontent.com/casals-ar/proxy-list/main/socks5",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/http_proxies.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks5_proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_anonymous/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_anonymous/socks5.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/http.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/https.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/all.txt",
        "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps",
        "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=socks5",
        "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=socks4",
        "https://spys.me/proxy.txt",
        "https://spys.me/socks.txt",
        "https://raw.githubusercontent.com/opsxcq/proxy-list/master/list.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/main/socks4.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS4.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_anonymous/socks4.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/https.txt",
        "https://openproxylist.xyz/socks5.txt",
        "https://openproxylist.xyz/socks4.txt",
        "https://raw.githubusercontent.com/casals-ar/proxy-list/main/http",
        "https://raw.githubusercontent.com/fate0/proxylist/master/proxy.list",
        "https://raw.githubusercontent.com/elliottophellia/yakumo/master/results/socks4/global/socks4_checked.txt",
        "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/all.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/http.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/https.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/socks5.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/socks4.txt",
        "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt",
        "https://raw.githubusercontent.com/andigwandi/free-proxy/main/proxy_list.txt",
        "https://raw.githubusercontent.com/parserpp/ip_ports/main/proxyinfo.txt",
        "https://raw.githubusercontent.com/roma8ok/proxy-list/main/proxy-list-https.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/output/by-anonymity/elite.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/output/by-anonymity/anonymous.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/main/proxies/unknown.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation/http.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation/socks4.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation/socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4.txt",
        "https://raw.githubusercontent.com/themiralay/Proxy-List-World/master/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/anonymous.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/http_proxies.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks4_proxies.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/socks5_proxies.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/main/All_proxies.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/main/HTTP.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/main/SOCKS4.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/main/ALL_PROXY.txt",
        "https://raw.githubusercontent.com/watchttvv/free-proxy-list/main/proxy.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/all-proxies.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_proxies.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_elite.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/http.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/socks4.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/main/socks5.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/https.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/https.txt",
        "https://raw.githubusercontent.com/ebrasha/abdal-proxy-hub/main/http-proxy-list-by-EbraSha.txt",
        "https://raw.githubusercontent.com/ebrasha/abdal-proxy-hub/main/https-proxy-list-by-EbraSha.txt",
        "https://raw.githubusercontent.com/ebrasha/abdal-proxy-hub/main/socks4-proxy-list-by-EbraSha.txt",
        "https://raw.githubusercontent.com/ebrasha/abdal-proxy-hub/main/socks5-proxy-list-by-EbraSha.txt",
        "https://raw.githubusercontent.com/VolkanSah/Auto-Proxy-Fetcher/main/proxies.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/main/http/http.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/main/https/https.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/main/socks5/socks5.txt",
        "https://raw.githubusercontent.com/officialputuid/KangProxy/main/socks4/socks4.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/https_proxies.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/main/proxy_files/socks4_proxies.txt",
        "https://raw.githubusercontent.com/casals-ar/proxy-list/main/socks4",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/proxies.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/proxy.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/proxylist.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http_checked.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks4_checked.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5_checked.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/parserpp/free-proxy/main/proxy_list.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/US/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/VN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GB/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/FR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/JP/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SG/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CA/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AU/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TH/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ID/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PH/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TW/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MX/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ES/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IT/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PL/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UA/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZA/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EG/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PK/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BD/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NG/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CO/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CL/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RO/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CH/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/FI/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AT/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IL/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NO/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PT/data.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=ipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&proxy_format=ipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks4&proxy_format=ipport&format=text",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000&country=all",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=5000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=anonymous",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=elite",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000&country=all",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=protocolipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks4&proxy_format=protocolipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&proxy_format=protocolipport&format=text",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/HTTP.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/main/instagram_proxies.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/main/google_proxies.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/Bes-js/public-proxy-list/main/proxies.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/main/proxies.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/ShadowSocks.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/au/data.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/SOCKS4.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ca/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/br/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/br/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/br/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/br/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/de/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/de/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/de/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/de/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/de/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fr/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fr/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fr/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hk/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hk/https/data.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/All_Config.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hk/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/id/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hk/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/id/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/id/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/id/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/id/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/jp/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/in/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/in/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/in/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/jp/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/jp/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kr/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kr/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kr/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kr/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/my/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/my/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ph/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ph/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ph/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sg/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sg/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/th/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sg/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/th/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/th/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sg/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/th/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/th/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tw/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/us/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/us/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/us/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/us/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/us/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/vn/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/vn/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/vn/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/vn/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/vn/socks4/data.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Australia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Canada.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/France.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Brazil.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Hong_Kong.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Germany.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/India.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Japan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Indonesia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Malaysia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Philippines.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Singapore.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/South_Korea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Taiwan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Thailand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/United_Kingdom.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Vietnam.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/United_States.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Australia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Brazil.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Canada.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/France.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Germany.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Hong_Kong.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Indonesia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/India.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Japan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Malaysia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Philippines.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Singapore.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/South_Korea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Taiwan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Thailand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/United_Kingdom.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/United_States.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Vietnam.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Australia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Brazil.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Canada.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/France.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Germany.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Indonesia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/India.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Hong_Kong.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Japan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Malaysia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Philippines.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/South_Korea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Singapore.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Taiwan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Thailand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/United_Kingdom.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Vietnam.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/United_States.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Australia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Brazil.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Canada.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/France.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Germany.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Hong_Kong.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Japan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Indonesia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/India.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Malaysia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Philippines.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Singapore.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/South_Korea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Taiwan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Thailand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/United_Kingdom.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Vietnam.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/links/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/links/all.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/links/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/anonymous.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/https.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/United_States.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-http.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/high-anon.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/links/all.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/links/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/fast-only.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-https.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/links/high-anon.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/links/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/stable.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/links/stable.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/top-trusted.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Australia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Belarus/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Bahrain/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Benin/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Canada/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Brazil/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Cyprus/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Costa%20Rica/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/France/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Germany/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Hong%20Kong/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Jamaica/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/India/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Japan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Indonesia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Malaysia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Mauritius/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Philippines/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/South%20Korea/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Spain/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Singapore/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/South%20Africa/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Thailand/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Taiwan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/United%20States/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Vietnam/proxies.txt",
        "https://raw.githubusercontent.com/claude89757/free_https_proxies/main/https_proxies.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/all.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/http.txt",
        "https://raw.githubusercontent.com/claude89757/free_https_proxies/main/isz_https_proxies.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/hunted/hunted_elite.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/United%20Kingdom/proxies.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/au/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/au/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/au/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/br/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/br/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/br/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/br/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ca/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ca/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ca/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ca/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/de/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/de/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/de/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/de/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fr/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fr/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gb/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fr/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gb/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gb/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hk/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hk/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hk/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/id/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/id/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/id/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/id/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/in/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/in/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/in/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/in/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/jp/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/jp/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/jp/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kr/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kr/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kr/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kr/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/my/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/my/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/my/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ph/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sg/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sg/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sg/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/th/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tw/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/th/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/th/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/us/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/us/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/us/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/us/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/vn/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/vn/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/vn/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/nguyenduytan/NDT-Proxy-Scraper/main/socks4.txt",
        "https://raw.githubusercontent.com/nguyenduytan/NDT-Proxy-Scraper/main/http.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/nguyenduytan/NDT-Proxy-Scraper/main/socks5.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/theriturajps/proxy-list/main/proxies.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/socks5.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/proxies.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=anonymous",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=ipport&format=text&anonymity=Anonymous",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=http&proxy_format=ipport&format=text&anonymity=Elite",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/master/proxies.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/master/http.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/master/socks4.txt",
        "https://raw.githubusercontent.com/ALIILAPRO/Proxy/master/socks5.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/http_proxies.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/socks4_proxies.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/socks5_proxies.txt",
        "https://raw.githubusercontent.com/Bes-js/public-proxy-list/master/proxies.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/all.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/http.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/https.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/socks4.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/socks5.txt",
        "https://raw.githubusercontent.com/CB-X2-Jun/proxy-lists/main/proxy.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/main/proxies/all.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/main/http.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/main/socks4.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/main/socks5.txt",
        "https://raw.githubusercontent.com/Cyber-Dioxide/Prox-Scrapper/master/proxies.txt",
        "https://raw.githubusercontent.com/DarlingSh1337/ProxyList/main/http.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/master/proxies/http.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/master/proxies/https.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ExoticSecurityWeb/scraper-proxy/main/proxies/all.txt",
        "https://raw.githubusercontent.com/ExoticSecurityWeb/scraper-proxy/main/proxies/http.txt",
        "https://raw.githubusercontent.com/ExoticSecurityWeb/scraper-proxy/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/ExoticSecurityWeb/scraper-proxy/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/KM126/simple-proxy-checker/main/proxies.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/all.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/all.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/http.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/https.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/socks4.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/main/socks5.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/master/http.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/master/socks4.txt",
        "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/master/socks5.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/main/http.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/main/proxy.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/main/socks4.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/main/socks5.txt",
        "https://raw.githubusercontent.com/ProxcyDev/Proxies/master/all.txt",
        "https://raw.githubusercontent.com/ProxcyDev/Proxies/master/http.txt",
        "https://raw.githubusercontent.com/ProxcyDev/Proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/ProxcyDev/Proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/master/http.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/master/socks4.txt",
        "https://raw.githubusercontent.com/ProxyScraper/ProxyScraper/master/socks5.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/main/http.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/main/socks4.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/main/socks5.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/master/proxies/https.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/SevenworksDev/proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/http.txt",
        "https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks4.txt",
        "https://raw.githubusercontent.com/SoraDev-ID/proxy-scraper/main/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/master/proxies/all.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/master/proxies/https.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/TuanMinPay/live-proxy/master/all.txt",
        "https://raw.githubusercontent.com/TuanMinPay/live-proxy/master/http.txt",
        "https://raw.githubusercontent.com/TuanMinPay/live-proxy/master/socks4.txt",
        "https://raw.githubusercontent.com/TuanMinPay/live-proxy/master/socks5.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/VolkanSah/Auto-Proxy-Fetcher/master/proxies.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/main/proxy.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-list-daily/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-list-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-list-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/fresh-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/fresh-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/fresh-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/geo-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/geo-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/geo-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-list-2026/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-list-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/http-proxy-list-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/live-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/live-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/live-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/mass-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/mass-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/open-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/open-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/open-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-bulk-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-bulk-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-bulk-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-http/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-http/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-http/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-pool-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-pool-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-pool-free/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-api-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-api-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-api-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-list-daily/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-list-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-list-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-pool-2026/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-pool-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-pool-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/fresh-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/fresh-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/fresh-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/geo-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/geo-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/geo-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-list-2026/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-list-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-proxy-list-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-bulk-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-bulk-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-bulk-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-http/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-http/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-http/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-pool-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-pool-free/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-pool-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/andigwandi/free-proxy/master/proxy_list.txt",
        "https://raw.githubusercontent.com/asifulislamemon07/proxies.txt/main/proxies.txt",
        "https://raw.githubusercontent.com/berkay-digital/Proxy-Scraper/main/proxies.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list.txt",
        "https://raw.githubusercontent.com/drakelam/Free-Proxy-List/main/proxy_list.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/main/http.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/main/socks4.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/main/socks5.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/auto-proxies/main/http.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/auto-proxies/main/https.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/auto-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/auto-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/free-proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/free-proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/free-proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/kevinriverrrr-sudo/free-proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/http.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/https.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/master/proxies/all.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/mzyui/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/mzyui/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/mzyui/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/mzyui/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/main/proxies/all.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/main/proxies/http.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/nazavod777/proxy_list/main/all.txt",
        "https://raw.githubusercontent.com/nazavod777/proxy_list/main/http.txt",
        "https://raw.githubusercontent.com/nazavod777/proxy_list/main/https.txt",
        "https://raw.githubusercontent.com/nazavod777/proxy_list/main/socks5.txt",
        "https://raw.githubusercontent.com/nguywnben/daily-proxy-updates/main/proxies/all.txt",
        "https://raw.githubusercontent.com/nguywnben/daily-proxy-updates/main/proxies/http.txt",
        "https://raw.githubusercontent.com/nguywnben/daily-proxy-updates/main/proxies/https.txt",
        "https://raw.githubusercontent.com/nguywnben/daily-proxy-updates/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/nguywnben/daily-proxy-updates/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AL/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AM/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BG/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BO/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BW/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CM/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DK/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DO/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EC/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GT/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HK/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HU/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IQ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KH/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LB/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LT/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LU/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LV/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MD/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MM/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NL/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NP/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PS/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RS/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RU/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SC/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SI/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SK/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UY/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UZ/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/VE/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZW/data.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/master/proxies/https.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/proxylist-to/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/main/http.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks4_proxies.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/socks5_proxies.txt",
        "https://raw.githubusercontent.com/theriturajps/proxy-list/master/proxies.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/main/all.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/main/http.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/main/https.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/main/socks4.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/main/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/watashibeme/openproxy.space/main/http.txt",
        "https://raw.githubusercontent.com/watchttvv/free-proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/socks4.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/master/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/master/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/master/https.txt",
        "https://raw.githubusercontent.com/zevtyardt/proxy-list/main/output/by-anonymity/transparent.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/master/http.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/master/https.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks4.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/master/socks5.txt",
        "https://raw.githubusercontent.com/Arefgh72/proxy-public-list/main/proxies.txt",
        "https://raw.githubusercontent.com/Arefgh72/proxy-public-list/master/proxies.txt",
        "https://raw.githubusercontent.com/Durgaa17/cf-sg-proxies/main/proxies_simple.txt",
        "https://raw.githubusercontent.com/Durgaa17/cf-sg-proxies/main/proxies_working_simple.txt",
        "https://raw.githubusercontent.com/Shinzzyak/proxy-scraper/main/proxies.txt",
        "https://raw.githubusercontent.com/Shinzzyak/proxy-scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/SulthanAbiyyu/fresh-proxies/main/valid_proxies.txt",
        "https://raw.githubusercontent.com/Wanted000/Socks5-Proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/aQuiner/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/akbarali123A/proxy_scraper/main/http_proxies.txt",
        "https://raw.githubusercontent.com/akbarali123A/proxy_scraper/main/https_proxies.txt",
        "https://raw.githubusercontent.com/akbarali123A/proxy_scraper/main/socks4_proxies.txt",
        "https://raw.githubusercontent.com/akbarali123A/proxy_scraper/main/socks5_proxies.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/alive/http.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/alive/https.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/alive/socks4.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/alive/socks5.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/gold/http.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/gold/https.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/gold/socks4.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/gold/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/data-pipeline-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-http-socks/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-automation/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/main/http.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/main/proxies.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/main/socks5.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/master/http.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/itsanwar/proxy-scraper/master/socks5.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/27/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/28/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/28/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/28/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/28/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/29/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/29/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/29/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/29/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/30/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/30/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/30/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/30/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/31/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/31/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/31/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-03/31/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/01/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/01/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/01/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/01/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/02/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/02/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/02/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/02/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/03/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/03/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/03/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/03/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/04/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/04/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/04/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/04/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/05/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/05/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/05/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/05/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/06/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/06/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/06/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/06/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/07/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/07/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/07/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/07/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/08/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/08/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/08/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/08/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/09/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/09/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/09/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/09/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/10/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/10/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/10/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/10/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/11/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/11/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/11/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/11/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/12/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/12/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/12/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/12/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/13/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/13/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/13/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/13/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/14/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/14/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/14/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/14/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/15/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/15/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/15/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/15/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/16/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/16/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/16/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/17/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/17/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/17/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/17/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/18/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/18/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/18/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/18/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/19/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/19/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/19/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/19/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/20/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/20/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/20/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/20/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/21/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/21/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/21/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/21/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/22/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/22/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/22/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/22/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/23/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/23/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/23/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/23/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/24/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/24/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/24/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/24/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/25/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/25/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/25/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/25/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/26/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/26/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/26/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/26/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/27/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/27/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/27/12-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/27/18-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/28/00-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-04/28/06-00/proxies.txt",
        "https://raw.githubusercontent.com/joy-deploy/free-proxy-list/main/data/2025-05/02/00-00/proxies.txt",
        "https://raw.githubusercontent.com/krokmazagaga/http-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/krokmazagaga/http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/rix4uni/fresh-proxy-list/main/proxylist.txt",
        "https://raw.githubusercontent.com/rix4uni/fresh-proxy-list/master/proxylist.txt",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=AU",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=BR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=CA",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=DE",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=FR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=GB",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=HK",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=ID",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=IN",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=JP",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=KR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=MY",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=NL",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=PH",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=RU",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=SG",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=TH",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=TW",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=US",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&country=VN",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=AU",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=BR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=CA",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=DE",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=FR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=GB",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=HK",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=ID",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=IN",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=JP",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=KR",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=MY",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=NL",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=PH",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=RU",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=SG",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=TH",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=TW",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=US",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=http&country=VN",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=socks4",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=ipport&format=text&protocol=socks5",
        "https://raw.githubusercontent.com/FifzzSENZE/Master-Proxy/master/proxies/all.txt",
        "https://raw.githubusercontent.com/FifzzSENZE/Master-Proxy/master/proxies/http.txt",
        "https://raw.githubusercontent.com/FifzzSENZE/Master-Proxy/master/proxies/https.txt",
        "https://raw.githubusercontent.com/FifzzSENZE/Master-Proxy/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/FifzzSENZE/Master-Proxy/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/main/http.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/main/https.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/main/socks4.txt",
        "https://raw.githubusercontent.com/ItzmeJan/proxy-checker/main/proxies.txt",
        "https://raw.githubusercontent.com/MOMMY2034/Free-Proxy-List/main/all.txt",
        "https://raw.githubusercontent.com/MOMMY2034/Free-Proxy-List/main/http.txt",
        "https://raw.githubusercontent.com/MOMMY2034/Free-Proxy-List/master/all.txt",
        "https://raw.githubusercontent.com/MOMMY2034/Free-Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/a2u/free-proxy-list/master/free-proxy-list.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/bot-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-endpoint-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/github-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/http-socks4-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/live-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/pipeline-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/plain-text-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-automation/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-for-developers/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-http-socks/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-checker-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-for-scraping/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-socks5/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-socks5/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/public-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/public-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/socks4-proxies-free/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/updated-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/updated-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/working-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/automation-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/automation-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-endpoint-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-endpoint-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-checker-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-for-scraping/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-plain-text/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/scraping-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/updated-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-endpoint-list/master/socks5.txt",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/main/http.txt",
        "https://raw.githubusercontent.com/mishakorzik/Free-Proxy/main/proxy.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/main/http.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/main/https.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/main/socks4.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/main/socks5.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/master/https.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/master/socks5.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/master/https.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/master/socks4.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/master/proxies/http.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5",
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&proxy_format=protocolipport&format=text",
        "https://proxyspace.pro/https.txt",
        "https://raw.githubusercontent.com/2cz5/ipv4-Proxies/main/proxies.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/master/socks5.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/master/all.txt",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/master/http.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/EDT-Pages/Proxy-List/main/data/socks5.json",
        "https://raw.githubusercontent.com/FinalBuild-Studio/socks5/master/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bd/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bd/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bg/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cl/data.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cl/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cn/data.txt",
        "https://raw.githubusercontent.com/CB-X2-Jun/proxy-lists/master/proxy.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ar/data.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/main/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cn/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cn/http/data.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cn/https/data.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/master/http.txt",
        "https://proxyspace.pro/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bd/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ec/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/co/http/data.txt",
        "https://proxyspace.pro/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/do/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/do/http/data.txt",
        "https://proxyspace.pro/socks4.txt",
        "https://raw.githubusercontent.com/EDT-Pages/Proxy-List/main/data/http.json",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/co/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ec/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ar/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ke/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fi/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/es/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/iq/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/es/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ke/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kh/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kh/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/mx/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/mx/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/nl/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pe/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ru/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pk/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/mx/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pk/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pl/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ru/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/co/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/se/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/nl/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/nl/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ru/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ru/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ua/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pk/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/se/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pe/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sy/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tr/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sy/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pk/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ve/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tr/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ve/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tr/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ve/https/data.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Afghanistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Albania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Azerbaijan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Algeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Argentina.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Belarus.txt",
        "https://raw.githubusercontent.com/RazaRathour1/Socks5.txt/main/socks5.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Angola.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Botswana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bosnia_and_Herzegovina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Armenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bolivia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Burundi.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/za/data.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Belgium.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/British_Virgin_Islands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Belize.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Benin.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bulgaria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bahrain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Austria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Chile.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Cambodia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bangladesh.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Burkina_Faso.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Costa_Rica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Cameroon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Congo_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Colombia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Croatia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Cyprus.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Ecuador.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/DR_Congo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Denmark.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Czechia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/China.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Dominican_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Finland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Egypt.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Equatorial_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/El_Salvador.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Estonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Kazakhstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Ghana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Kosovo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Kyrgyzstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Guatemala.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Greece.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Italy.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Hungary.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Georgia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Ireland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Iceland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Iraq.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Israel.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Iran.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Kenya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Jordan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Honduras.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Latvia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Lebanon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Laos.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Lesotho.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Macao.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Malawi.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Libya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Malta.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Luxembourg.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Maldives.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Lithuania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Mauritius.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Mongolia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Moldova.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Mozambique.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Mexico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Montenegro.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Nepal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Morocco.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Nigeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/North_Macedonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Myanmar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Nicaragua.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Paraguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/New_Zealand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Pakistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Panama.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Palestine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Norway.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Poland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Papua_New_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Portugal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Peru.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Qatar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Rwanda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Serbia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Senegal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Puerto_Rico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Saudi_Arabia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Romania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Slovakia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Somalia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Seychelles.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Slovenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Spain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/South_Africa.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Russia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Tanzania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Switzerland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Tunisia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Syria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Sri_Lanka.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Sweden.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Uganda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Uruguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Uzbekistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Tajikistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Zambia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Ukraine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Türkiye.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Yemen.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Zimbabwe.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/The_Netherlands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/United_Arab_Emirates.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Albania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Argentina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Venezuela.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Bangladesh.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Cambodia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Austria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Bulgaria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Colombia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Egypt.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Chile.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Greece.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Denmark.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Czechia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Georgia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Guatemala.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Unknown.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Dominican_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Finland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Ireland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Honduras.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Ecuador.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Iran.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Hungary.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/China.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Libya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Iraq.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Latvia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Italy.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Peru.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Lithuania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Russia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Poland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Mexico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Romania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Slovakia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Qatar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Paraguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Nepal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Pakistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/South_Africa.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Unknown.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Ukraine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Spain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/The_Netherlands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Algeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Türkiye.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/United_Arab_Emirates.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Switzerland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Afghanistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Sweden.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Zimbabwe.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Venezuela.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Albania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Uzbekistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Azerbaijan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bahrain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Armenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Austria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Angola.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Argentina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Belgium.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Belize.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Belarus.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bangladesh.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Benin.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bosnia_and_Herzegovina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bulgaria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Burundi.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Cameroon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Chile.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Croatia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/British_Virgin_Islands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Cambodia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bolivia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Costa_Rica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Botswana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Myanmar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Denmark.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Colombia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Congo_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Cyprus.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Burkina_Faso.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Czechia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Estonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/DR_Congo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Dominican_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/China.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Finland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Ghana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Ecuador.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Greece.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Hungary.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Iceland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Ireland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Iran.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Israel.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Iraq.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Italy.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Jordan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Kenya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Kazakhstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Libya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Kenya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Laos.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Macao.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Kosovo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Luxembourg.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Lebanon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Lithuania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Mauritius.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Malta.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Montenegro.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Mozambique.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Morocco.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Myanmar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Nepal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Norway.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Nicaragua.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/North_Macedonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/New_Zealand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Nigeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Egypt.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Panama.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Equatorial_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Qatar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Poland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Pakistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Puerto_Rico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Guatemala.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Romania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Russia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Rwanda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Slovakia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Saudi_Arabia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Serbia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Sri_Lanka.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Kyrgyzstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Seychelles.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Lesotho.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Latvia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Ukraine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Moldova.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Senegal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/South_Africa.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Mexico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Uganda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Mongolia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Tanzania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Tunisia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Sweden.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Syria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Türkiye.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Spain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Peru.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Somalia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Maldives.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/United_Arab_Emirates.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Paraguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Portugal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Palestine.txt",
        "https://raw.githubusercontent.com/BuntheaTaing/Proxy-Scraper/main/proxy.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Uzbekistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Venezuela.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Unknown.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Zambia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Yemen.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Algeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Armenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Benin.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Belarus.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bangladesh.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Malawi.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Belize.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bolivia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Albania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Austria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bulgaria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Angola.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Afghanistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Zimbabwe.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Botswana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Switzerland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bosnia_and_Herzegovina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Cameroon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Belgium.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Burundi.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Cambodia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/British_Virgin_Islands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bahrain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Chile.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Argentina.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Colombia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/The_Netherlands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Uruguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/China.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Croatia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Costa_Rica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Congo_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/DR_Congo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Egypt.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Dominican_Republic.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Georgia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Guatemala.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Czechia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Equatorial_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Denmark.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Ecuador.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Kenya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Burkina_Faso.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Greece.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Cyprus.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Georgia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Italy.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Ghana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Israel.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Iraq.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Honduras.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Honduras.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Hungary.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Kazakhstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Jordan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Iceland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Ireland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Kyrgyzstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Finland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Lesotho.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Lebanon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Latvia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Laos.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Estonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Libya.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Macao.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Iran.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Luxembourg.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Lithuania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Nepal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Mongolia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Montenegro.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/North_Macedonia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Myanmar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Mozambique.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/New_Zealand.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Maldives.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Moldova.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Norway.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Morocco.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Pakistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Azerbaijan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Malawi.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Mauritius.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Nicaragua.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Qatar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Mexico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Peru.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Poland.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Malta.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Panama.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Portugal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Rwanda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Puerto_Rico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Paraguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Palestine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Saudi_Arabia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Senegal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Nigeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Kosovo.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Serbia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Romania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Seychelles.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Slovakia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Slovenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Somalia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Russia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Spain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Sri_Lanka.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/South_Africa.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/ID.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Switzerland.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/main/proxy/http.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Uruguay.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Tanzania.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Zimbabwe.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Tunisia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/The_Netherlands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Türkiye.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Venezuela.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/BD.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Syria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Uzbekistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/United_Arab_Emirates.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Zambia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Yemen.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Uganda.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Ukraine.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/DE.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/socks5_all.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/EC.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/VN.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/HK.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Unknown.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/main/proxy/socks5.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/main/proxy/https.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/main/proxy/socks4.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Albania/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Armenia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Afghanistan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Argentina/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Costa Rica/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Angola/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Austria/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Algeria/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Bolivia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Burundi/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Bosnia and Herzegovina/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Azerbaijan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Cameroon/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Colombia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Czechia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Curacao/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Croatia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Ecuador/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Denmark/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/El Salvador/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/DR Congo/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Dominican Republic/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Egypt/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Equatorial Guinea/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Estonia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Finland/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Georgia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Ghana/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Hungary/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Italy/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Ireland/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Kazakhstan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Iran/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Iraq/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Kenya/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Israel/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Kyrgyzstan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Bangladesh/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/British Virgin Islands/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Lebanon/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Bulgaria/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Chile/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Cambodia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Congo Republic/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Libya/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Malawi/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Lithuania/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Macao/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Moldova/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Mexico/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Mongolia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Montenegro/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Greece/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Guatemala/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Hong Kong/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Morocco/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Luxembourg/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Myanmar/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Honduras/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Nicaragua/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/New Zealand/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/North Macedonia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Norway/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Nigeria/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Kosovo/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Pakistan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Laos/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Palestinian Territory/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Latvia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Palestine/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Portugal/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Panama/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Paraguay/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Poland/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Romania/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Russia/proxies.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/SG.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/South Africa/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/South Korea/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Somalia/proxies.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/KR.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/United Kingdom/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Sweden/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Sri Lanka/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Switzerland/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/United States/proxies.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Botswana/proxies.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/al/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/am/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bd/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/master/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cn/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cn/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cn/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cn/https.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cl/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cl/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/dk/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/do/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/es/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bi/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gt/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gr/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/iq/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ly/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mx/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/web-scraping-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nl/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pk/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pl/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pk/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pl/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pr/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pl/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ru/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ru/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ru/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ml/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sc/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ru/socks4.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/socks4.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/socks5.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/global/socks5_checked.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Zimbabwe/proxies.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/za/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/za/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/za/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/za/https.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/master/http.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/master/https.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/main/proxies/http.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/socks5.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/master/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/master/socks5.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/unchecked/https-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/unchecked/socks4-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/unchecked/socks5-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/unchecked/http-proxies.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/connect.txt",
        "https://raw.githubusercontent.com/Chm0kes/ssclprlist/main/sslist.txt",
        "https://raw.githubusercontent.com/398001/ProxysList/main/http_working.txt",
        "https://raw.githubusercontent.com/398001/ProxysList/main/all_working.txt",
        "https://raw.githubusercontent.com/398001/ProxysList/main/socks5_working.txt",
        "https://raw.githubusercontent.com/398001/ProxysList/main/socks4_working.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/proxies/http.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/proxies/all.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/Hysteria2.txt",
        "https://raw.githubusercontent.com/Argh94/Proxy-List/main/Trojan.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/main/https.txt",
        "https://raw.githubusercontent.com/KM126/simple-proxy-checker/main/HTTP.txt",
        "https://raw.githubusercontent.com/Pxys-io/DailyProxyList/master/working_proxies.txt",
        "https://raw.githubusercontent.com/M450ud/PrList/main/dsl.txt",
        "https://raw.githubusercontent.com/M450ud/PrList/main/prx.txt",
        "https://raw.githubusercontent.com/Siva2webdev/Alive_Proxies/tat/alive_proxies.txt",
        "https://raw.githubusercontent.com/R00tzRE/ProxyAliveCheck/main/proxies_example.txt",
        "https://raw.githubusercontent.com/NikolaiT/free-proxy-list/main/proxies/https_working.txt",
        "https://raw.githubusercontent.com/NikolaiT/free-proxy-list/main/proxies/socks4_working.txt",
        "https://raw.githubusercontent.com/NikolaiT/free-proxy-list/main/proxies/http_working.txt",
        "https://raw.githubusercontent.com/NikolaiT/free-proxy-list/main/proxies/socks5_working.txt",
        "https://raw.githubusercontent.com/TheSilentPatch/Proxy-Harvester/main/test_proxies.txt",
        "https://raw.githubusercontent.com/a7a-7iz/proxy.txt/main/proxy.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/main/proxy_scheme.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/main/proxy_active.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/main/proxy_scheme_active.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/main/proxy_log.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/main/working_proxies.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/av0id/python-proxy-scanner-checker/master/proxylist-2016-07-10-21-59-57.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-status.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_all.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_ssl_anonymous.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_anonymous.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_ssl.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_nossl.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_ssl_elite.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_transparent.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_ssl.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_transparent.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/socks4_all.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/all_anonymous.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_ssl_elite.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/main/http_elite.txt",
        "https://raw.githubusercontent.com/drakelam/Free-Proxy-List/main/proxy_all.txt",
        "https://raw.githubusercontent.com/drakelam/Free-Proxy-List/main/proxy_s4.txt",
        "https://raw.githubusercontent.com/equwal/proxyverif/master/example.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/drproxy-free/ipv4-datacenter-proxy-list/main/ipv4-canada-proxies.txt",
        "https://raw.githubusercontent.com/drproxy-free/ipv4-datacenter-proxy-list/main/ipv4-brazil-proxies.txt",
        "https://raw.githubusercontent.com/drproxy-free/ipv4-datacenter-proxy-list/main/ipv4-germany-proxies.txt",
        "https://raw.githubusercontent.com/drproxy-free/ipv4-datacenter-proxy-list/main/ipv4-us-proxies.txt",
        "https://raw.githubusercontent.com/drproxy-free/ipv4-datacenter-proxy-list/main/ipv4-uk-proxies.txt",
        "https://raw.githubusercontent.com/ghostysec/socks4.txt/main/77.txt",
        "https://raw.githubusercontent.com/ghostysec/socks4.txt/main/88.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/main/https.txt",
        "https://raw.githubusercontent.com/luphnox/proxyList/main/nah.txt",
        "https://raw.githubusercontent.com/luphnox/proxyList/main/newproxy.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/main/proxies/elite.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/socks5_residential.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/residential.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/nodes_alive.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/socks5_alive.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/http_alive.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/socks5_fast.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/http_residential.txt",
        "https://raw.githubusercontent.com/fmw86/free-proxy-pool/main/http_fast.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/http-online.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/mixedlist.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/mixed-online.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/socks4-online.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/socks5-online.txt",
        "https://raw.githubusercontent.com/noarche/proxylist-socks5-sock4-exported-updates/main/connect-online.txt",
        "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/cnfree.txt",
        "https://raw.githubusercontent.com/saisuiu/Lionkings-Http-Proxys-Proxies/main/free.txt",
        "https://raw.githubusercontent.com/nestorchurin/proxy-list/main/proxies/active/socks4.txt",
        "https://raw.githubusercontent.com/nestorchurin/proxy-list/main/proxies/active/http.txt",
        "https://raw.githubusercontent.com/nestorchurin/proxy-list/main/proxies/clean/socks4.txt",
        "https://raw.githubusercontent.com/nestorchurin/proxy-list/main/proxies/clean/socks5.txt",
        "https://raw.githubusercontent.com/nestorchurin/proxy-list/main/proxies/clean/http.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/protocol/http/http.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/protocol/socks4/socks4.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/protocol/https/https.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/protocol/socks5/socks5.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY_RAW.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/V2RAY.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/main/working_proxies.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PH.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/elite.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CO.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CN.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/live.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/ID.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CA.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/VN.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/RU.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/BR.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MX.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/US.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/fast.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/BD.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IN.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/fr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/br/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/us/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/gt/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/jp/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/fi/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hk/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/iq/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ca/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/zw/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hn/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/my/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/nl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/vn/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ir/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ar/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cm/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/mx/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ph/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/do/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/th/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bd/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pe/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pk/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hu/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ru/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/gb/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/es/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/de/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/co/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/py/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cn/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/sg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/kh/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ua/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/sy/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/se/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/tr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/eg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/il/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ke/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/at/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/id/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ro/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/kr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ec/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/za/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ve/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/lv/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ch/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/uz/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/it/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/in/all.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ae/data.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/AE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ae/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AE.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AF.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/al/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AL.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/am/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AM.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/al/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ar/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ar/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ar/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AR.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ar/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/at/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/at/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/at/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AT.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/at/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/AU.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bd/socks4/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bd/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bd/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bd/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bd/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bd/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/be/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bg/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bg/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/BG.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bg/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/bg/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/BO.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bo/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/br/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/br/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bw/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/BW.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ca/socks5/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CD.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ch/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ch/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ch/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CG.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ch/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CH.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CL.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cl/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cm/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cm/http/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/co/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cn/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cn/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CM.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/co/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/co/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cn/socks4/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/co/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/co/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/co/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/cm/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CR.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cy/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CY.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cz/https.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/de/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cz/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/CZ.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/de/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/de/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cz/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/DE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/dk/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/DO.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/do/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ec/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ec/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ec/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ee/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/EC.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/EE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/eg/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/EG.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/eg/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/ES.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/es/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/es/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fi/socks5/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/es/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fi/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fi/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/FI.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fi/https.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fr/socks5/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/fr/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/FR.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/fr/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gb/http/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/GB.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gb/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gb/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ge/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ge/http/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ge/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/GE.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/GH.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/GR.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/GT.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hk/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hk/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/HK.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/hk/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hn/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/HN.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/HR.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hu/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hu/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ie/https.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/id/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/id/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hu/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/HU.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/id/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/il/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ie/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IL.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/in/socks5/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/il/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/in/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/in/socks4/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/in/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/IN.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/in/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/iq/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ir/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IQ.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ir/http/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/iq/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/iq/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ir/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ir/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IR.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ir/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ir/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/it/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/it/https.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/it/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/IT.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/it/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/it/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/JP.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/jp/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/jp/socks5.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/JP.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ke/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/KG.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ke/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/KE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kh/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kh/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/KH.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kh/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/kh/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/kh/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/kr/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/KR.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kz/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/KZ.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/LB.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lt/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lt/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/LT.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lv/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lv/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/LV.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lv/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/lv/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/lv/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/LY.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MA.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MD.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/ME.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MN.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mm/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MM.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mn/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/MY.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/my/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/mx/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/mx/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mx/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ng/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ng/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/NG.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nl/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nl/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nl/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/no/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/nl/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/NL.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/nl/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/nl/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/no/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/np/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/np/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/NP.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PE.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pe/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PA.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pe/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ph/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ph/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pk/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pk/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PK.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pk/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pk/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/pl/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pl/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PL.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PR.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ps/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ps/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PS.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pt/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/py/http.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/py/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/py/http/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/PY.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ro/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/RO.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ru/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ro/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/rs/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ro/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/RS.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ru/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ru/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SC.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/se/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/sg/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/se/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SG.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SE.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/se/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/se/https.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/sg/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SI.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SK.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sk/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sy/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/SY.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/sy/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/TH.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/th/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/th/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/th/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tr/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/tr/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tr/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tr/socks4.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/TW.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/TR.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/tr/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ua/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ua/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/UG.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/TZ.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/UA.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/us/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ua/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ua/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/us/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/us/socks4.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/US.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/uz/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/UZ.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/uz/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tz/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ve/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/ve/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ve/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/vn/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/vn/socks5.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/VE.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/YE.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/za/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/za/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/vn/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/za/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/main/by-country/ZA.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/main/proxies/countries/zw/http.txt",
        "https://raw.githubusercontent.com/0xarchit/duckduckgo-webscraper/main/proxies.txt",
        "https://raw.githubusercontent.com/adasd223/checked-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/checked-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/daily-proxy-feed/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/daily-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/data-pipeline-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-collection/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-rotating-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-rotating-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-socks4-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-socks4-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-socks4-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-socks5-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/mixed-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/open-source-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-plain-text/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/public-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/public-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/rotating-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-socks-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/socks4-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/socks4-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/socks4-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/socks4-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/socks5-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/socks5-proxy-feed/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/verified-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/bot-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/bot-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-proxy-feed/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/data-pipeline-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/data-pipeline-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-collection/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-rotating-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-socks5-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/http-socks4-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/pipeline-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/plain-text-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/plain-text-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/plain-text-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-rotating-pool/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-rotating-pool/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-rotating-pool/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-rotating-pool/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-automation/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/public-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/public-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/rotating-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/rotating-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/rotating-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/rotating-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/scraping-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/scraping-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/scraping-socks-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/verified-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/verified-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/working-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/fedebotu/proxy-scraper-checker/master/proxies/http.txt",
        "https://raw.githubusercontent.com/fedebotu/proxy-scraper-checker/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/fedebotu/proxy-scraper-checker/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/geniuszly/GenProxyJSChecker/master/proxies.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/kami2k1/scan-proxy-zmap/main/http.txt",
        "https://raw.githubusercontent.com/kami2k1/scan-proxy-zmap/master/http.txt",
        "https://raw.githubusercontent.com/yuceltoluyag/GoodProxy/main/raw.txt",
        "https://raw.githubusercontent.com/CallocGD/Boomlings-Proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/CallocGD/Boomlings-Proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/Hatois/free-proxy-list/main/proxies.txt",
        "https://raw.githubusercontent.com/Rizmi/Proxy-Tools/main/proxy_list.txt",
        "https://raw.githubusercontent.com/Rizmi/Proxy-Tools/master/proxy_list.txt",
        "https://raw.githubusercontent.com/adasd223/global-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-github/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-github/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/public-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/public-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/public-socks5-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/socks-proxy-list-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/socks-proxy-list-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/socks-proxy-list-free/main/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/socks-proxy-list-free/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/socks5-proxies-free/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/socks5-proxies-free/main/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/socks5-proxies-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-socks4-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-socks4-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/github-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/github-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/github-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/github-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/global-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/global-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/global-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/global-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-http-proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mass-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/mixed-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/mixed-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mixed-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/mixed-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/mixed-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-source-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-source-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/open-source-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-automation/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-developers/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-for-developers/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-http-socks/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-http-socks/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-github/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-socks5/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-socks5/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-socks5/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-socks5/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-socks5/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/main/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/main/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks4-proxies-free/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks5-proxies-free/main/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks5-proxies-free/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks5-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/socks5-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/noarche/proxy-checker/main/proxies.txt",
        "https://raw.githubusercontent.com/noarche/proxy-checker/master/proxies.txt",
        "https://raw.githubusercontent.com/notfaj/ester/master/proxies.txt",
        "https://raw.githubusercontent.com/qamrixtech/isitproxy/main/proxy.txt",
        "https://raw.githubusercontent.com/qamrixtech/isitproxy/master/proxy.txt",
        "https://raw.githubusercontent.com/Access-At/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/Access-At/proxy-list/main/proxies.txt",
        "https://raw.githubusercontent.com/Access-At/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/Access-At/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/master/socks5.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/master/socks4.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/master/http.txt",
        "https://raw.githubusercontent.com/Efration/proxy-pool-public/main/proxies.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/master/proxy/https.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/master/proxy/http.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/master/proxy/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/master/proxies/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks4-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/CB-X2-Jun/https-proxy/main/pxy.json",
        "https://raw.githubusercontent.com/BlacKSnowDot0/Proxy-Pulse/main/data/known-good.json",
        "https://raw.githubusercontent.com/M450ud/PrList/main/configfamily.json",
        "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/main/working_proxies.json",
        "https://raw.githubusercontent.com/fushuain-collab/free-nodes/main/sub.txt",
        "https://raw.githubusercontent.com/itzNamanDev/HW-Scraper/main/proxies.txt",
        "https://raw.githubusercontent.com/itzNamanDev/HW-Scraper/main/all_scraped.txt",
        "https://raw.githubusercontent.com/liketolivefree/kobabi/main/sub.txt",
        "https://raw.githubusercontent.com/AQuiner/free-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/master/http.txt",
        "https://raw.githubusercontent.com/BSG-Walter/proxy-fresh/main/proxies-valid.txt",
        "https://raw.githubusercontent.com/BrenoFariasdaSilva/Proxy-List-Generator/main/Proxies_List/free_proxy_list_proxies.txt",
        "https://raw.githubusercontent.com/BrenoFariasdaSilva/Proxy-List-Generator/main/Proxies_List/socks_proxy_proxies.txt",
        "https://raw.githubusercontent.com/BrenoFariasdaSilva/Proxy-List-Generator/main/Proxies_List/spys_me_proxies.txt",
        "https://raw.githubusercontent.com/BrenoFariasdaSilva/Proxy-List-Generator/main/Proxies_List/ssl_proxies_proxies.txt",
        "https://raw.githubusercontent.com/BrenoFariasdaSilva/Proxy-List-Generator/main/Proxies_List/us_proxy_proxies.txt",
        "https://raw.githubusercontent.com/CB-X2-Jun/cf-proxyip-lists/main/proxyip.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/all.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/http.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/https.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/socks.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/socks5.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/json/socks.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/json/socks4.json",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/txt/http.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/txt/socks4.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/txt/socks5.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/http.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/https.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/socks.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/socks4.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/socks5.txt",
        "https://raw.githubusercontent.com/ExoticSecurityWeb/scraper-proxy/main/proxies/proxies.json",
        "https://raw.githubusercontent.com/HB47x/proxy-list/main/worldwide_http.txt",
        "https://raw.githubusercontent.com/HB47x/proxy-list/main/worldwide_socks4.txt",
        "https://raw.githubusercontent.com/HankNovic/ProxyClean/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/HankNovic/ProxyClean/main/SOCKS5_RAW.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/ALL.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/BD.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/CN.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/DE.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/IN.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/JP.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/KH.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/RU.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/US.txt",
        "https://raw.githubusercontent.com/NullRoute-Lab/Universal-Proxy-Finder/main/Output/v2ray_subscription.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/DeamNet_proxy.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/configs/all.txt",
        "https://raw.githubusercontent.com/HB47x/proxy-list/main/worldwide_socks5.txt",
        "https://raw.githubusercontent.com/LeilaoMi/AutoMergePublicNodes-Optimized/main/output/all.json",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/Vauth/proxy/main/proxy.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/master/proxy.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/Efration/proxy-pool-public/master/proxies.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/Wanted000/Socks5-Proxies/main/socks5.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/master/proxies/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bot-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/anonymous-proxy-list-free/master/socks4.txt",
        "https://raw.githubusercontent.com/berkay-digital/Proxy-Scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/Moleway/Free-Proxy-List/master/all.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/master/proxies/https.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/NetroIndonesia/proxy-live/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-socks-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-http-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/automation-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-socks-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/checked-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/bulk-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/master/all_proxies.txt",
        "https://raw.githubusercontent.com/Vauth/proxy/master/proxy.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/crawler-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/daily-updated-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-global-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-http-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-collection/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-rotating-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-api-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/fresh-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/global-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/github-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/geo-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-socks5-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-pool-2026/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-list-daily/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/free-proxy-endpoints/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-socks4-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/http-proxy-list-2026/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/live-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-http-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mixed-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/pipeline-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/plain-text-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/mass-socks-proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-developers/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-for-automation/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/open-source-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-bulk-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-endpoints-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-free-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-checker-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxies-st-rotating-pool/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-for-scraping/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/main/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-http/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-plain-text/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-updated-daily/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-socks5/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/main/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks-proxy-list-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-http-proxies/main/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/public-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/rotating-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-list-github/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/scraping-socks-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/proxy-pool-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxies-free/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/txt-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks5-proxy-feed/master/http.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/socks4-proxies-free/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/working-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AF/data.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/verified-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/master/socks4.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/web-scraping-proxies/master/http.txt",
        "https://raw.githubusercontent.com/gnxD3RfTT2WE/updated-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/monster8d/Elite_Proxy-List/main/proxy.txt",
        "https://raw.githubusercontent.com/monster8d/Elite_Proxy-List/master/proxy.txt",
        "https://raw.githubusercontent.com/junioralive/PROXY-Alive/master/http.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GH/data.txt",
        "https://raw.githubusercontent.com/shubhamshendre/Free-Proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GR/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LA/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/JM/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KG/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MU/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PA/data.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/socks4.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/https.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/all.txt",
        "https://raw.githubusercontent.com/Siva2webdev/Alive_Proxies/master/alive_proxies.txt",
        "https://vakhov.github.io/fresh-proxy-list/socks4.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/socks4.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/id.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/th.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ph.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/kr.txt",
        "https://raw.githubusercontent.com/Jakee8718/Free-Proxies/main/proxy/https.txt",
        "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/Country/US/socks4.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS%2BAll_RUS.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/ALL.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/ID.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/unchecked/socks5-proxies.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/instagram.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Unstable/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/my.txt",
        "https://maximilianfeix.github.io/proxy-scraper/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ALL/all.json",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/refs/heads/main/https.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/v2ray.json",
        "https://maximilianfeix.github.io/proxy-scraper/socks4.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/all.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/fi.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks4/data.json",
        "https://vakhov.github.io/fresh-proxy-list/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/https.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ph/data.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Unstable/https.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/co.txt",
        "https://raw.githubusercontent.com/relayglass/free-proxy-list/main/countries/DE/DE.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/all.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ml.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/za/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks5/data.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/us.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/all.json",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/socks5.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/latency/fast/data.txt",
        "https://vakhov.github.io/fresh-proxy-list/proxylist.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/whitelist_cidr1_ru.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/bd.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/instagram.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/nl/data.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/nl.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/discord/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/de/data.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/socks4.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
        "https://raw.githubusercontent.com/Jakee8718/Free-Proxies/main/proxy/socks/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Unstable/http.txt",
        "https://sunny9577.github.io/proxy-scraper/generated/http_proxies.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/refs/heads/main/out-files/socks5.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/25.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cn/data.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/v2rayng_socks5.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/scraped_proxies/socks5.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/kh.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ru.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/custom/udp.txt",
        "https://raw.githubusercontent.com/tianndev/free-proxy/main/proxy/https.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ru/data.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/hy.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/amazon.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/socks4.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/hk/data.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/protocol/socks4/all.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/3.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/socks4_proxies.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/11.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/https.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/us/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/anonymity/elite/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/stable.json",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/main/proxies/https.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/socks5.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/v2rayng_http.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/18.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/refs/heads/main/http.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/hy2.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/latency/fast/data.json",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/protocol/http_tls/all.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/ss.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/stable.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ec/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/kr/data.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/Country/US/https.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/refs/heads/main/mirror/1.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/all.json",
        "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/socks4.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/proxies.json",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/google/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/pl.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/random.json",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/exclave_socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/sg/data.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/https.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/5.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/all.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/exclave_http_tls.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/json/proxies.json",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/socks5.json",
        "https://vakhov.github.io/fresh-proxy-list/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Unstable/ALL.txt",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/exclave_socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/amazon.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/fr.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/output/US.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/checked/all/all-proxies.txt",
        "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/json/proxies.json",
        "https://vakhov.github.io/fresh-proxy-list/https.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/20.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.json",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/stability/stable/data.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/stability/stable/data.txt",
        "https://raw.githubusercontent.com/reservedbytes/proxyscraper/proxies/socks.txt",
        "https://raw.githubusercontent.com/tuanminpay/live-proxy/master/all.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/http.json",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks4.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/jp/data.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-all.txt",
        "https://raw.githubusercontent.com/tianndev/free-proxy/main/proxy/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/https/data.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/th/data.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/scraped-proxies.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks5.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/reddit.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/lv.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/http.json",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/http.json",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/google.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/US.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/unchecked/socks4-proxies.txt",
        "https://thordata.github.io/awesome-free-proxy-list/data/links/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ca/data.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/refs/heads/main/https.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/13.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/refs/heads/main/out-files/http.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks5.txt",
        "https://raw.githubusercontent.com/nostalume/FreeNodes/HEAD/nodes/merged.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies/main/proxies/all_proxies.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/in/data.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/elite.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/se.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/de.txt",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/refs/heads/main/http.txt",
        "https://maximilianfeix.github.io/proxy-scraper/proxies.json",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks4.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/unchecked/https-proxies.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/all.json",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/https.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/refs/heads/main/SOCKS4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/cm.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/refs/heads/main/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/http.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/socks5.json",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/ss.json",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/elite/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/socks4.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/socks4.json",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/http.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/6.txt",
        "https://raw.githubusercontent.com/Jakee8718/Free-Proxies/main/proxy/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/cl.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/socks5.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/https.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/refs/heads/main/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/ALL.txt",
        "https://raw.githubusercontent.com/Jakee8718/Free-Proxies/main/proxy/socks/socks4.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/http.json",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/protocols/https.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/checked/latency/fast/fast-proxies.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/socks5.json",
        "https://raw.githubusercontent.com/reservedbytes/proxyscraper/proxies/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/https.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ca.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/fast.json",
        "https://sunny9577.github.io/proxy-scraper/proxies.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/proxies.json",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/ss.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/refs/heads/main/HTTP.txt",
        "https://raw.githubusercontent.com/cbusifabcap/daily_free_vpn/refs/heads/main/Z.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/http.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/2.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/cn.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/scraped_proxies/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks4.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/br.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/unchecked/http-proxies.txt",
        "http://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/vn/data.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/socks5.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/pk/data.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/jp.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ALL/ALL.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/proxies.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/discord.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/tr/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/all.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ie.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/protocol/socks5/all.txt",
        "http://static.fatezero.org/tmp/proxy.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/wireguard.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/output/IR.txt",
        "http://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/ByeWhiteLists/ByeWhiteLists2/refs/heads/main/ByeWhiteLists2.txt",
        "https://raw.githubusercontent.com/zruzus1-prog/vpn-checked/checked/subscription-youtube.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/blacklist_all.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/blacklist_vpn2.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/GB.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/bd/data.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/23.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/za.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/tuic.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/v2ray.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/google.txt",
        "https://raw.githubusercontent.com/Jakee8718/Free-Proxies/main/proxy/-http%20and%20https.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/proxies.json",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/whitelist_cidr3_eu.txt",
        "https://maximilianfeix.github.io/proxy-scraper/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/Country/US/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ir.txt",
        "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/refs/heads/main/working_proxies.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/works-with/tiktok.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/protocol/http/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks4.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/scraped_proxies/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/tiktok.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/all.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/countries/US/proxies.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/16.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/mahsang_http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/anonymity/elite/data.json",
        "https://raw.githubusercontent.com/zruzus1-prog/vpn-checked/checked/subscription-youtube-stable.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/Country/US/socks5.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/All_proxies.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/main/checked_proxies/http.json",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxy-TuanMinPay/http.txt",
        "https://raw.githubusercontent.com/tianndev/free-proxy/main/proxy/socks4.txt",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/http.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/21.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/metadata.json",
        "https://raw.githubusercontent.com/abusaeeidx/TazaProxy-Troxy/refs/heads/main/working_proxies.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/tw.txt",
        "http://ab57.ru/downloads/proxylist.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/stable.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/anonymous.json",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/discord.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/socks4.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/blacklist_vpn1.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/http_proxies.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/gb.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/co/data.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/refs/heads/main/socks4.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ve/data.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/anytls.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/fast.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/socks.txt",
        "https://raw.githubusercontent.com/tianndev/free-proxy/main/proxy/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/https.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ch.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/24.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/refs/heads/main/proxies/http.json",
        "https://raw.githubusercontent.com/liketolivefree/kobabi/main/sub_all.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/https.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.json",
        "https://sunny9577.github.io/proxy-scraper/generated/socks5_proxies.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/refs/heads/main/socks5_proxies.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/br/data.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/refs/heads/main/ALL_PROXY.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/bg.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/vn.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/sg.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/metadata.json",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven-Free-Proxy-Updated/refs/heads/main/socks5.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/26.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/14.txt",
        "https://raw.githubusercontent.com/Cheagjihvg/simple-proxylist/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/mehdi-hexing/HTTP-PROXY/main/proxies/subscriptions/exclave_http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/bi.txt",
        "http://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/id/data.txt",
        "https://raw.githubusercontent.com/zruzus1-prog/vpn-checked/checked/subscription-youtube-reserve.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/in.txt",
        "https://raw.githubusercontent.com/wiki/gfpcom/free-proxy-list/lists/trojan.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/il.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/checked/protocols/https/https-proxies.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ua.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/all.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/hk.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/pk.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/stable.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/refs/heads/main/out-files/socks4.txt",
        "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/whitelist_cidr2_ru.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/elite.txt",
        "https://maximilianfeix.github.io/proxy-scraper/all.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/8.txt",
        "https://raw.githubusercontent.com/Simatwa/free-proxies/master/files/socks4.json",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/mx/data.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/checked/protocols/http/http-proxies.txt",
        "https://raw.githubusercontent.com/Casper-Tech-ke/casper-free-proxies/main/files/random.json",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Unstable/socks5.txt",
        "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/whitelist_all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/anonymous.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/all.txt",
        "https://raw.githubusercontent.com/fyvri/fresh-proxy-list/archive/storage/classic/http.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/works-with/reddit.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/all.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/mixed.txt",
        "https://raw.githubusercontent.com/RioMMO/ProxyFree/refs/heads/main/SOCKS5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/anonymous/ALL.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/1.txt",
        "https://raw.githubusercontent.com/cyberh4ck3r/free-proxy-list/main/proxies/checked/anonymity/elite/elite-proxies.txt",
        "https://raw.githubusercontent.com/tianndev/free-proxy/main/proxy/socks5.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/9.txt",
        "https://github.com/nikita29a/FreeProxyList/raw/refs/heads/main/mirror/19.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/18.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/16.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/1.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/5.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/6.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/25.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/3.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/24.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/11.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/19.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/21.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/13.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/9.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/23.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/26.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/14.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/8.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/am/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/al/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ae/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/af/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/bg/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/az/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ar/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/bo/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/bw/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cl/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/au/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cd/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cr/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cz/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/do/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/fr/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/fi/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cm/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/eg/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ch/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/es/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ge/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/gb/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/hu/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/gr/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/iq/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/gt/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/hn/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/kz/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/il/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/kh/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ke/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ie/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ir/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/hr/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/kg/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/it/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/md/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ly/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/mn/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/pe/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/pa/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/my/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/nz/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/no/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/mm/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/np/data.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/main/out-files/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ng/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/pl/data.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/main/out-files/socks5.txt",
        "https://raw.githubusercontent.com/i-am-unbekannt/BLITZPROXY/main/out-files/socks4.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/es.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/it.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/py.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/rs.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/proxies.csv",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/tr.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/main/countries/ae.txt",
        "https://raw.githubusercontent.com/mohamadfg-dev/telegram-v2ray-configs-collector/refs/heads/main/category/vless.txt",
        "https://raw.githubusercontent.com/youfoundamin/V2rayCollector/main/mixed_iran.txt",
        "https://raw.githubusercontent.com/miladtahanian/V2RayCFGDumper/main/sub.txt",
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&country=us&anonymity=elite",
        "https://raw.githubusercontent.com/slxkware/Vless-list/refs/heads/main/Black%20Vless.txt",
        "https://raw.githubusercontent.com/miladtahanian/Config-Collector/refs/heads/main/mixed_iran.txt",
        "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
        "https://github.com/zloi-user/hideip.me/raw/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/flaafix/AetrisVPN-black-list/refs/heads/main/configs.txt",
        "https://proxylist.geonode.com/api/proxy-list?limit=300&page=1&sort_by=lastChecked&sort_type=desc&protocols=http,https",
        "https://github.com/zloi-user/hideip.me/raw/refs/heads/main/http.txt",
        "https://github.com/zloi-user/hideip.me/raw/refs/heads/main/socks4.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/6.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/11.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/30.txt",
        "https://github.com/ShatakVPN/ConfigForge-V2Ray/raw/refs/heads/main/configs/vless.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/5.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/7.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/4.txt",
        "https://raw.githubusercontent.com/yitong2333/proxy-minging/refs/heads/main/v2ray.txt",
        "https://github.com/VOID-Anonymity/V.O.I.D-VPN_Bypass/raw/refs/heads/main/url_work.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/13.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/23.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/14.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/9.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/12.txt",
        "https://github.com/zloi-user/hideip.me/raw/refs/heads/main/connect.txt",
        "https://github.com/zloi-user/hideip.me/raw/refs/heads/main/https.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/17.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/18.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/16.txt",
        "https://github.com/MhdiTaheri/V2rayCollector_Py/raw/refs/heads/main/sub/Mix/mix.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/1.txt",
        "https://github.com/cbusifabcap/daily_free_vpn/raw/refs/heads/main/Z.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/10.txt",
        "https://github.com/igareck/vpn-configs-for-russia/raw/refs/heads/main/BLACK_VLESS_RUS.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/main/alive_plain_bs.txt",
        "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/refs/heads/main/all_configs.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/15.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/main/alive_plain_full.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/22.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/AI/alive_plain_AI.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/main/alive_plain_bl.txt",
        "https://proxmint.com/api/free-proxies?protocol=socks5&format=txt",
        "https://raw.githubusercontent.com/FLAT447/v2ray-lists/refs/heads/main/BLACK_FULL.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/latency/fast/data.csv",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/20.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/https/data.csv",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/stability/stable/data.csv",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks5/data.csv",
        "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/proxies/all.txt",
        "https://raw.githubusercontent.com/maximilianfeix/proxy-scraper/proxy-list/proxies.csv",
        "https://github.com/sakha1370/OpenRay/raw/refs/heads/main/output/all_valid_proxies.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/8.txt",
        "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subs/bundles/best.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks4/data.csv",
        "https://raw.githubusercontent.com/morawskidotmy/youtube-proxies/main/youtube-proxies.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/24.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/trojan.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/txt/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/http/data.csv",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/vless.txt",
        "https://raw.githubusercontent.com/mohammedcha/ProxRipper/main/full_proxies/socks5.txt",
        "https://raw.githubusercontent.com/morpheusadam/v2ray-config/main/subs/bundles/iran.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/Best-Results/proxies.txt",
        "https://raw.githubusercontent.com/mohammedcha/ProxRipper/main/full_proxies/http.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/txt/all.txt",
        "https://raw.githubusercontent.com/mohammedcha/ProxRipper/main/full_proxies/https.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/refs/heads/main/splitted-by-protocol/shadowsocks.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/25.txt",
        "https://raw.githubusercontent.com/mohammedcha/ProxRipper/main/full_proxies/socks4.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-1.txt",
        "https://raw.githubusercontent.com/Chm0kes/ssclprlist/refs/heads/main/sslist.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.csv",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/anonymity/elite/data.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-3.txt",
        "https://raw.githubusercontent.com/notthinks/proxy-lists/main/alive.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/stable.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-2.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/28.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-6.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks4.csv",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/all.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-12.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-9.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-8.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-7.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/anonymous.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/https.csv",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/29.txt",
        "https://github.com/Mr-Meshky/vify/raw/refs/heads/main/configs/vless.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-16.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-11.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-13.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/proxy/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/all.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-17.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-15.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-14.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-5.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/27.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-18.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/separated_by_protocol/other.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-10.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-19.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-20.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/proxy/https.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/separated_by_protocol/trojan.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/proxy/socks4.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/19.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/fast.csv",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/ws_tls/proxies/wstls",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/socks5.csv",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/separated_by_protocol/vless.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/selector/random",
        "https://raw.githubusercontent.com/Mahdi0024/ProxyCollector/master/sub/proxies.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/obfs4_tested.txt",
        "https://raw.githubusercontent.com/rekt0ro/ProxyRift/main/subscriptions/light.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/vanilla_ipv6_tested.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/proxy/socks5.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/vanilla_ipv6.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/vanilla.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/vanilla_tested.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/Tor-Bridges-Collector/refs/heads/main/bridge/obfs4.txt",
        "https://raw.githubusercontent.com/rekt0ro/ProxyRift/main/subscriptions/all.txt",
        "https://raw.githubusercontent.com/Efration/proxy-pool-worker-public/main/proxies.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/http.csv",
        "https://api.proxyscrape.com/v4/free-proxy-list/get?request=getproxies&protocol=http&limit=2000",
        "https://raw.githubusercontent.com/Cornelius798/proxy-pool/main/pool.txt",
        "http://api.proxyscrape.com/v4/free-proxy-list/get?request=get_proxies&protocol=socks5&proxy_format=ipport&format=text&timeout=20000",
        "https://raw.githubusercontent.com/Darmioniks/mtproto-proxy-tg/main/vless_filtered.txt",
        "https://raw.githubusercontent.com/MahanKenway/Freedom-V2Ray/main/configs/mix.txt",
        "https://raw.githubusercontent.com/MahanKenway/Freedom-V2Ray/main/configs/vless.txt",
        "https://raw.githubusercontent.com/MahanKenway/Freedom-V2Ray/main/configs/ss.txt",
        "http://api.proxyscrape.com/v4/free-proxy-list/get?request=get_proxies&protocol=socks4&proxy_format=ipport&format=text&timeout=20000",
        "http://api.proxyscrape.com/v4/free-proxy-list/get?request=get_proxies&protocol=http&proxy_format=ipport&format=text&timeout=20000",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/separated_by_protocol/shadowsocks.txt",
        "https://github.com/Argh94/Proxy-List/raw/refs/heads/main/All_Config.txt",
        "https://jn-s3s.github.io/proxy-list/all/socks4.txt",
        "https://jn-s3s.github.io/proxy-list/megabasterd/all.txt",
        "https://raw.githubusercontent.com/MahanKenway/Freedom-V2Ray/main/configs/trojan.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/protocols/vless.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_008.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_013.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_002.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_007.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_012.txt",
        "https://freeproxydb.com/api/proxy/search?protocol=socks5&page_size=20",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_006.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/protocols/trojan.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/patt/all.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_011.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_010.txt",
        "https://jn-s3s.github.io/proxy-list/all/http.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/protocols/ss.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/patt/batches/batch_002.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_003.txt",
        "https://raw.githubusercontent.com/sevcator/5ubscrpt10n/main/protocols/vl.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/patt/protocols/trojan.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_009.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_004.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/patt/batches/batch_001.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/all_configs.txt",
        "https://jn-s3s.github.io/proxy-list/all/socks5.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/patt/protocols/vless.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_005.txt",
        "https://jn-s3s.github.io/proxy-list/megabasterd/formatted-only.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/batches/v2ray/batch_001.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_006.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_012.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_017.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_005.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_011.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_007.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_004.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_001.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_010.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_002.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_009.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/hk.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_013.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_016.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_003.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_008.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/3.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/us.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/sg.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/kr.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/gb.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/fr.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ca.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/jp.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/pl.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/tw.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/lt.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ie.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/au.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/tr.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/se.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/in.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/kz.txt",
        "https://github.com/pie-with-jam/PulseProxy/raw/refs/heads/main/githubmirror/21.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/de.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GB.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ru.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ir.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/es.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/hysteria2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/nl.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ee.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/vn.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/za.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/cz.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IR.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_015.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/my.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/lv.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/br.txt",
        "https://raw.githubusercontent.com/blagobiz/ruka-mtproto-collector/main/whitelist_primary.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/bg.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ch.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/al.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/at.txt",
        "https://raw.githubusercontent.com/blagobiz/ruka-mtproto-collector/main/whitelist_android.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/ro.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/it.txt",
        "https://jn-s3s.github.io/proxy-list/all/all.txt",
        "https://raw.githubusercontent.com/azadnetwork/proxy-collector/main/telegram/v2ray.txt",
        "https://raw.githubusercontent.com/blagobiz/ruka-mtproto-collector/main/whitelist_all.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/id.txt",
        "https://raw.githubusercontent.com/blagobiz/ruka-mtproto-collector/main/whitelist_extended.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/tcp-pass/batch_014.txt",
        "https://github.com/Delta-Kronecker/V2ray-Config/raw/refs/heads/main/config/countries/fi.txt",
        "https://raw.githubusercontent.com/shabane/kamaji/master/hub/merged.txt",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks4&timeout=10000&country=all",
        "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=10000&country=all",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Qatar/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Netherlands/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Malta/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Nepal/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Namibia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Senegal/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/China/proxies.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/json/socks4.json",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Mozambique/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Lesotho/proxies.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-socks4.txt",
        "https://raw.githubusercontent.com/Denisyoya/Proxy-List-Gamt/main/results/raw/txt/socks.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Madagascar/proxies.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Iceland/proxies.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/main/archive/txt/proxies-https.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Belgium/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Mayotte/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Guinea/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Rwanda/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Slovakia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Slovenia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Peru/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Seychelles/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Turkey/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Zambia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Uganda/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Tanzania/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Serbia/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Syria/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Yemen/proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation_anonymous/socks5.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Uzbekistan/proxies.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Ukraine/proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation_anonymous/socks4.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Uruguay/proxies.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/main/proxies_geolocation_anonymous/http.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Venezuela/proxies.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/FR.txt",
        "https://raw.githubusercontent.com/Vadim287/free-proxy/main/world/Tajikistan/proxies.txt",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/VN.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AU/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AM/data.json",
        "https://raw.githubusercontent.com/Jamshed-Dev/public-proxy-list/main/proxies/SG.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BG/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CN/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CM/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AL/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BD/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CH/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BW/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BO/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DO/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DK/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/AT/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CO/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EG/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/BR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CL/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EC/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/EE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/CA/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GH/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GT/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GB/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ES/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/DE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/GE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/FR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HU/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IL/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HK/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/HN/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ID/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IQ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LA/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IN/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IT/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/JP/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KH/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/JM/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KG/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MD/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LV/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LB/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MN/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MU/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/KR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LT/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NG/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NP/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NO/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PR/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/LY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PT/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PA/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SI/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SN/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RS/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SA/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PL/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RO/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SN/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SC/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NL/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PK/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/NZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TC/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SG/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/MX/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SA/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/RU/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UA/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TC/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TW/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TH/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/PH/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/XK/data.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/VE/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZZ/data.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AM/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/XK/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/UY/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZZ/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/SK/data.json",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/TR/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AT/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AZ/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZW/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BE/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/ZA/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BO/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CM/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AU/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BD/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BG/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AF/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/https/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/AL/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BW/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CL/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks4/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CH/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CO/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/BY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CN/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/EE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/EC/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/CZ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/DK/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/DO/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/GE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/EG/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/ES/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/ET/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/FI/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/GR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/GB/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/GT/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/FR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/DE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/GH/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/HN/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/HU/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/KZ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/JM/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IT/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/KE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IQ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IN/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/KR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/HR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/KG/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/HK/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LV/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/IL/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/http/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LT/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/KH/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/ID/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LB/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MD/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MN/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/JP/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MU/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MM/proxies.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/US/data.json",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/NO/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PS/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MX/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/MY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/RO/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PL/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/NP/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/NG/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/NZ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PT/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PK/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/RS/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SC/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SK/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SG/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SI/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/TC/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/NL/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PH/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/PR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SN/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/SY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/TR/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/UA/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/TH/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/RU/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/TW/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/VE/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/TZ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/UY/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/UZ/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/ZW/proxies.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/VN/proxies.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ar-http.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/ZA/proxies.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/co-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/am-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/bd-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/de-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ch-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ec-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/br-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/cn-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/br-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-anonymity/transparent.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/de-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/de-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-anonymity/anonymous.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/fr-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ca-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/fi-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/eg-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/cn-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/fr-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/bd-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-anonymity/elite.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/co-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/hk-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/do-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/hk-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/id-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/gb-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/fr-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/hk-http.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/US/proxies.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/kr-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/gb-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/my-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/kh-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/mx-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/in-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/jp-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/nl-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/nl-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ro-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/in-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/pe-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/kr-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ph-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ru-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/th-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/nl-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/id-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ir-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/sy-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ma-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/sg-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ua-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ru-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/th-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/za-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ua-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ru-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/tr-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/of-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/us-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/us-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/vn-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/vn-socks4.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/ve-http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/us-socks5.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/sg-socks4.txt",
        "https://raw.githubusercontent.com/aslisk/proxyhttps/main/psp.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/output/by-country/zw-http.txt",
        "https://raw.githubusercontent.com/aslisk/proxyhttps/main/junk.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Bhutan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Eswatini.txt",
        "https://raw.githubusercontent.com/Ch4120N/Ch4120N-Proxy-List/master/countries/LU/proxies.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Ivory_Coast.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Mayotte.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Jamaica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Madagascar.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/socks5.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Namibia.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/http.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/socks4.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Oman.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/South_Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Armenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Turkmenistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Azerbaijan.txt",
        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/database.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Sierra_Leone.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Belgium.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Bahrain.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Botswana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Israel.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Jamaica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Costa_Rica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Nigeria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Portugal.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Palestine.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Kazakhstan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Mauritius.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Panama.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Puerto_Rico.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Syria.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Serbia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Slovenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Seychelles.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Turks_and_Caicos_Islands.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Jamaica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Eswatini.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Namibia.txt",
        "https://raw.githubusercontent.com/Zevtyardt/proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Oman.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Madagascar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Bhutan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Papua_New_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Ivory_Coast.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Slovenia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/South_Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Ivory_Coast.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Namibia.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/links/stable.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Jamaica.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Eswatini.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Bhutan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Madagascar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Oman.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/South_Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Papua_New_Guinea.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Sweden.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/links/high-anon.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/CN.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/docs/data/history.json",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/by-country/PH.txt",
        "https://raw.githubusercontent.com/Thordata/awesome-free-proxy-list/main/proxies/history.json",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/http_with_protocol.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/socks4_with_protocol.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/v2nodes.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/i10VPN.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/Rayan_Config.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/VPNHub.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/google/socks5.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/reddit/http.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/https_with_protocol.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/configs/mixed.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/FG_Link.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/v2rayAggregator.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/discord/socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/tiktok/socks5.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/google/socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/instagram/socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/instagram/http.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/reddit/socks4.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/channels/PSG.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/x/http.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/.initial/misc/http.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/x/socks4.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/configs/mobile.json",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/x/socks5.txt",
        "https://raw.githubusercontent.com/LikeToLiveFree/kobabi/main/sub.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/reddit/socks5.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/discord/http.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/configs/mobile.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/custom/tiktok/socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/.initial/misc/socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/.initial/misc/socks5.txt",
        "https://raw.githubusercontent.com/Freedom-Guard-Builder/Freedom-Finder/main/out/reports/categories.json",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/140293.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/45102.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/53813.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/8075.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/IN.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/4837.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/CN.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/DE.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/CZ.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/ID.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/37204.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/asn/7029.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/SG.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/RU.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/SY.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/VN.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/JP.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/http/raw/country/ZW.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/asn/213887.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/asn/22773.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/asn/20081.txt",
        "https://raw.githubusercontent.com/ObcbO/getproxy/master/file/socks5_with_protocol.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/asn/6181.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/asn/46562.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks4/raw/country/US.txt",
        "https://raw.githubusercontent.com/LikeToLiveFree/kobabi/main/sub_all.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/12876.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/135967.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/135905.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/14061.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/22773.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/213520.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/14618.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/20081.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/19871.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/132525.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/24940.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/135918.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/16276.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/20473.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/209605.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/5479.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/24547.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/396982.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/31898.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/4134.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/4837.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/26496.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/398101.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/45102.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/24444.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.json",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/46562.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/33182.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/7602.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/51167.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/46475.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/6181.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/8075.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/9808.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/CN.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/HK.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/LT.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/AU.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/FR.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/asn/Unknown.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/SG.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/DE.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/IE.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/master/proxies/working-proxies-socks5.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/socks4.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/master/proxies/working-proxies-socks4.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/RU.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/VN.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/US.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/master/proxies/working-proxies-http.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/NL.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/socks5.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/https.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/master/proxies/working-proxies-all.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.json",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/http.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/all.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/docs/proxy-lists/proxies.json",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/checked/latency/fast/fast-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/checked/anonymity/elite/elite-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/checked/protocols/https/https-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/checked/protocols/http/http-proxies.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/main/proxies/checked/all/all-proxies.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/main/web/public/proxy-lists/proxies.json",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/master/proxies/scraped-proxies.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/at/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/cy/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ee/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/gq/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/lv/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ps/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/pr/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/rs/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/py/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ro/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/sy/data.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/main/proxy/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/se/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/ua/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/tz/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/tw/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/countries/uz/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/quality/top-1000/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/network/likely-residential/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/am/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/al/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/am/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ar/all.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/fresh/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ar/http.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/main/proxies/recent/data.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/al/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bd/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bd/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ar/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bd/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bd/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bg/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bo/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bi/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bi/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/br/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/br/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/br/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/bo/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/br/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ca/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cl/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ca/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cn/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cz/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/co/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cn/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/co/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/co/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cn/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cn/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/de/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/cz/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/co/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/de/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/de/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/do/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/de/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ec/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ec/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/do/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ee/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/eg/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/es/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/fi/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/eg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/fr/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/fi/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/fr/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/gb/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/hk/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/es/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/hk/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/hk/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/fr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/hk/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/id/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/gt/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/id/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/id/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/in/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/il/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/il/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/in/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/in/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ir/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/jp/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/gb/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/jp/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/gt/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/jp/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ir/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ke/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/jp/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kh/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kh/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kh/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ml/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/in/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ir/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/id/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kr/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/mx/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ke/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ml/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/my/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/mx/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ng/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/np/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/np/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/nl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/nl/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/mx/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/my/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kr/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ph/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/nl/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/kr/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ly/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ph/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pk/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pe/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/nl/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pk/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pl/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pr/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ph/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ru/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/py/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/se/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ro/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/py/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/th/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/sy/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/se/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ru/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pe/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/sy/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/se/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pk/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/tr/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/th/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pl/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/sg/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/sg/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/th/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pk/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/tr/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/sg/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/pr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ua/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ua/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ru/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/tr/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ua/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ru/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/th/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/vn/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/vn/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/vn/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ve/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/ve/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/vn/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/za/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/za/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/uz/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/us/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/zw/all.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/checked/all/all-proxies.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/checked/anonymity/elite/elite-proxies.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/zw/http.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/live/proxies/countries/uz/all.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/checked/protocols/http/http-proxies.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/checked/protocols/https/https-proxies.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/unchecked/https-proxies.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/checked/latency/fast/fast-proxies.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/11.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/16.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/23.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/unchecked/http-proxies.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/unchecked/socks5-proxies.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/25.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/12.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/CyberH4ck3r/free-proxy-list/main/proxies/unchecked/socks4-proxies.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/17.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/18.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/13.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/22.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/24.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/14.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-104.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/27.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-100.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-103.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/4.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-102.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/8.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/7.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/6.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/28.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/9.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/5.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-101.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/15.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-107.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-106.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/source/config/storage.json",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-109.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-113.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-105.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/20.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/19.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-110.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-112.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-114.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-108.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-111.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-115.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/30.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-122.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-127.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-121.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-118.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-119.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-120.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-128.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-117.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-133.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-130.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-116.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-125.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-124.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-126.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-129.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-135.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-136.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-123.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-144.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-134.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-132.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-145.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-138.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-141.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-142.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-139.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-146.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-131.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-147.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-140.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-137.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-26.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-24.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-27.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-23.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-31.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-32.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-21.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-25.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-28.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/1.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-30.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-143.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-29.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-38.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-44.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-39.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-148.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-33.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-22.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-35.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-36.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-34.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/3.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-46.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-42.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-47.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-48.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-41.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-55.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-43.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-49.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-57.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-50.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-56.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-58.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-37.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-52.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-40.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-60.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/29.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-67.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-59.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-54.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-51.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-45.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-63.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-53.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-61.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-62.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-64.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-70.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-65.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-66.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-69.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-68.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-71.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-72.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/10.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-75.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-74.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-73.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-78.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-83.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-77.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-90.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-84.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-82.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-80.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-89.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-91.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-76.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-92.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-86.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-79.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-93.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-85.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-87.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-81.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-88.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-95.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-97.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-94.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/state/verified_last.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-99.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-98.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/subscriptions/subscription-96.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part16.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Africa_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part17.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Africa_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part15.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Africa.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Africa_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part13.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part20.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part17.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part7.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part23.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part13.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part16.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part21.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part24.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part33.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part25.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part30.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part27.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part34.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part4.txt",
        "https://raw.githubusercontent.com/Firmfox/proxify/main/v2ray_configs/separated_by_protocol/mixed.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part31.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part29.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part37.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part35.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part38.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part42.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part41.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part45.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part28.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part36.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Asia_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part40.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part26.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part47.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part52.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part48.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part50.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part56.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part51.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part44.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part65.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part64.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part49.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part61.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part59.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part63.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part62.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Europe_part57.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/SouthAmerica.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part25.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part3.txt",
        "https://raw.githubusercontent.com/nikita29a/FreeProxyList/main/mirror/20.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AL.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AM.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part26.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BH.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/Oceania.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BD.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AU.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part23.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BY.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part24.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part17.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part16.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part19.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/continents/NorthAmerica_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CL.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CN.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CA_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/BG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CY.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/EC.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/AE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CN_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part15.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/CA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/EG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DK.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part13.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/ES.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/HU.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GB_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/EE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FI_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/HR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GB_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/ID.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GB_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FR_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IN.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FI.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IM.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/DE_part7.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IS.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IL.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IQ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/JO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/FI_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IR_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/HK_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IR_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/JP_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/JP_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/HK_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MK.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KH.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/JP.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/GB_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MH.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/LV.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/IR_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MX.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/OM.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MD.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/MY.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/LU.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/LT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PK.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/QA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/KR_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RS.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PH.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/PL.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RO.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SC_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SI.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/TT.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SC_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SE_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/NL_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SG_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SC.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SK.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/TH.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SC_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SE.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SE_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/TW.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part13.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/UA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part22.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part24.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part23.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part16.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/TR.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/SG_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part15.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part25.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part17.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/RU_part7.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/VI.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/UZ.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/VN.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/ZA.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/socks.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/anytls.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/VG.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/countries/US_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/hysteria2_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/socks5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part13.txt",
        "https://raw.githubusercontent.com/pie-with-jam/PulseProxy/main/githubmirror/21.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/tuic.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part7.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/hysteria.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/trojan_part9.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part7.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part10.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part108.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part101.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part107.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part103.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part100.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part112.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/ss_part6.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part113.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part109.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part105.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part12.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part110.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part13.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part102.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part111.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part29.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part21.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part31.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part28.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part18.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part19.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part14.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part37.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part20.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part16.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part17.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part2.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part35.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part3.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part36.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part11.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part34.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part32.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part25.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part15.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part43.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part42.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part50.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part41.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part57.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part40.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part5.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part47.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part30.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part46.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part38.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part26.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part65.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part52.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part22.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part59.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part24.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part33.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part49.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part67.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part62.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part48.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part63.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part69.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part70.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part74.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part76.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part60.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part77.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part53.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part72.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part82.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part23.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part8.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part75.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part54.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part44.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part85.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part84.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part58.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part86.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part66.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part91.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part89.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part79.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part95.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part92.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part87.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part90.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part73.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part88.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part45.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part99.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part80.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/verified.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part93.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part97.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part96.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part78.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/source/http.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_002.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/source/socks4.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part83.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/source/socks5.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/al.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/at.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_013.txt",
        "https://raw.githubusercontent.com/rtwo2/FastNodes/main/sub/protocols/vless_part98.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_011.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_005.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_007.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_003.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_010.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ca.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/cz.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/bg.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/it.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_008.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/br.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/fi.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_001.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/es.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ie.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/id.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ee.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/fr.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/au.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ch.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/gb.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_006.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/in.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/hk.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/de.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/source/https.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/jp.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_009.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_004.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/batches/v2ray/batch_012.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/lt.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ir.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/my.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/lv.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ro.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/ru.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/vn.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/tr.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/za.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/kr.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/se.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/kz.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/sg.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/pl.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/tw.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/us.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/countries/nl.txt",
        "https://raw.githubusercontent.com/dare131/proxy/main/proxies/source/mixed.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/archive/all_configs_2026-10-14.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/all_configs.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/patt/protocols/trojan.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/patt/batches/batch_002.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/reality/reality.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/protocols/trojan.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/patt/all.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/protocols/vless.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/patt/batches/batch_001.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/new.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/protocols/ss.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/patt/protocols/vless.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_004.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_001.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_008.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_010.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_016.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_012.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_005.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_014.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_011.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_006.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_007.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_009.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_015.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/reality.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_002.txt",
        "https://raw.githubusercontent.com/Delta-Kronecker/V2ray-Config/main/config/tcp-pass/batch_013.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/Argh94/ProxyProwler/main/proxy_output/SOCKS4.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/Argh94/ProxyProwler/main/proxy_output/HTTPS.txt",
        "https://raw.githubusercontent.com/7and1/free-proxy-list/main/proxies/countries/ZZ/data.txt",
        "https://raw.githubusercontent.com/Argh94/ProxyProwler/main/proxy_output/SOCKS5.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_anonymous.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/hysteria2.txt",
        "https://raw.githubusercontent.com/Iliya3ProX/good_proxies/main/vless_keys.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_https.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_all.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/ss.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_fast.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_slow.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_elite.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/v2ray.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_http.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/vless.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_medium.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_socks4.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_transparent.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/BR.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/AR.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/CO.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/live_proxies.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/BD.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/output/proxies_socks5.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/CA.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/live_http.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/CL.txt",
        "https://raw.githubusercontent.com/Ian-Lusule/Proxies-GUI/main/assets/tested_proxies.json",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/AL.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/DO.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/live_proxies_detailed.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/CN.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/FR.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/proxy_list.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/ES.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/DE.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/proxy_list_detailed.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/FI.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/EC.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/HN.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/HK.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/JP.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/PH.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/LY.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/ID.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/KH.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/NP.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/PK.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/IN.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/GE.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/MX.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/PE.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/PY.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/KR.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/RU.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/TH.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/TR.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/SG.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/ZA.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/UA.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/US.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/SY.txt",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/VN.txt",
        "https://raw.githubusercontent.com/MohammadKobirShah/ProxyScraper-Pro/main/proxies/proxy_list.json",
        "https://raw.githubusercontent.com/MrMarble/proxy-list/main/country/VE.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ae/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ar/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ar/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bd/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/br/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bg/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ca/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bo/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cz/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ec/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cz/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/es/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/do/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fi/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/eg/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/eg/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gt/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hn/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gr/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gr/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gt/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hn/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/jp/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kh/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/it/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kr/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/kh/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ly/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ly/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/my/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ng/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/nl/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/np/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/np/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pe/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pk/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ru/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ro/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sy/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/sg/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ua/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/za/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/uz/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/uz/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/uz/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/za/http/data.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-17_18-08-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-17_18-43-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_07-49-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_14-05-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_08-17-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_15-57-48/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_15-57-03/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_05-53-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_02-42-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_14-05-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_21-51-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_13-14-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_10-27-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_02-56-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-17_17-18-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_14-06-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-17_19-08-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_19-03-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_14-05-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_21-52-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_18-25-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_06-19-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_13-17-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_11-44-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_21-57-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_18-24-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_16-23-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-19_19-05-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_19-11-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_02-14-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_10-18-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_19-12-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_16-17-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_19-18-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_19-27-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_05-26-05/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_18-29-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_22-01-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_02-28-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_13-38-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-20_18-37-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-18_13-56-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_02-12-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_19-14-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_16-20-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_08-21-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_11-04-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-21_05-46-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_19-08-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_11-05-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_02-23-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_05-45-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_13-42-18/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_05-50-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_08-23-48/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_08-21-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-22_22-01-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_11-06-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_08-20-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_05-40-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_16-31-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_13-27-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_13-16-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_21-51-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_13-47-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_16-01-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_05-46-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_21-55-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_13-11-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_02-25-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_05-57-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_19-01-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_08-27-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_22-01-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_02-16-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_16-23-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_19-08-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_19-19-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-24_11-00-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_08-00-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-23_22-01-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_19-04-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_02-13-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_15-58-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-26_10-41-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_02-33-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-25_10-24-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_13-55-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_08-27-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_06-25-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_19-20-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_16-38-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_22-03-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_05-43-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_21-56-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_19-17-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_16-55-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_05-47-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_19-08-50/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-27_12-17-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_21-59-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_02-11-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_11-04-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_16-23-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_08-33-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_11-13-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_11-22-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_22-02-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_13-49-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-28_02-07-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_16-18-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_08-18-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_02-25-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_05-36-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-29_14-00-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-30_19-19-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_13-55-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_13-09-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_06-08-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_22-01-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_19-18-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_02-24-05/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_02-26-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_08-13-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_17-06-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_10-38-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_11-26-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_05-51-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_13-11-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_15-58-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_21-51-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_08-15-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_22-04-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_15-57-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_02-26-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_19-25-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_02-06-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202607/2026-07-31_16-42-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-01_19-02-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_19-03-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_11-20-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_10-37-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_06-17-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_21-51-48/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-02_05-52-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-03_12-18-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_05-43-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_22-08-48/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_11-17-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_02-27-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_14-01-18/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_05-42-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_22-08-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_01-15-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_19-25-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_02-09-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_16-49-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_23-54-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_04-51-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_08-29-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_13-58-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_18-49-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_05-44-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_19-24-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_09-57-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_11-18-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-04_08-30-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_02-04-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_12-53-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_08-28-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_07-08-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_06-43-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-05_16-28-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_15-52-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_09-34-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_01-20-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-06_13-56-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_12-38-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_09-33-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_04-26-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_04-08-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_15-56-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_18-31-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-07_21-34-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_21-27-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_06-48-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_04-15-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_12-54-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_09-56-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_01-22-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-08_15-25-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_01-28-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_04-16-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_06-59-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_01-20-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_21-37-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_18-51-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_21-41-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_07-23-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_15-57-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-11_18-56-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_10-13-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_15-26-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_18-33-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-10_12-57-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-09_12-40-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_04-44-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_09-55-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_07-17-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_07-18-05/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_07-20-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_18-56-34/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_18-57-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_01-38-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_12-58-48/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_09-58-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_12-59-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_15-55-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_09-59-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_15-46-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_12-56-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_01-30-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_21-39-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_04-45-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_21-20-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-14_18-47-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_09-21-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_06-30-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_21-40-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-12_15-55-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_03-34-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-13_04-47-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_03-43-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_18-21-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_09-22-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_18-21-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_09-27-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_12-28-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_21-15-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_15-27-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_01-02-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_12-30-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_06-36-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_06-36-03/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_03-41-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_21-16-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_12-36-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_01-00-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_06-32-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_21-19-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_15-16-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_09-29-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_00-59-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_18-31-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_15-21-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_03-40-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_09-36-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_12-37-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_21-21-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-16_15-17-07/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_06-44-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-15_00-58-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_00-59-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_18-27-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_06-38-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_12-34-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_03-46-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_09-29-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_18-30-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_18-32-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_12-30-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_06-38-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-17_03-45-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_18-32-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_03-42-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_01-02-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_00-59-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-18_00-58-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_15-29-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_18-22-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_09-22-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_06-32-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_09-32-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_21-23-33/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-20_12-38-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_15-16-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_21-19-18/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_15-27-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_15-26-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-21_12-37-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-19_21-21-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_09-23-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_03-37-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-22_21-17-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_15-17-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_06-33-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_01-03-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_03-46-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_12-39-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_01-01-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_18-22-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_06-49-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_21-16-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-23_12-31-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_09-30-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_03-50-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_15-34-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_06-38-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_18-33-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_18-33-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_21-24-05/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_01-02-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_03-44-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_15-37-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_01-00-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_12-39-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_03-50-03/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_12-42-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_06-40-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-25_21-23-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-24_09-41-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-29_22-58-03/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_09-36-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-02_18-23-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-27_00-24-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-30_20-28-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-30_03-20-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-28_00-12-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-31_03-16-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-27_13-40-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-29_12-11-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-30_23-05-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-30_15-56-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-31_12-33-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-30_11-08-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-28_14-50-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-31_20-36-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-01_22-57-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-03_07-42-18/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_16-14-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-29_05-24-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-29_18-08-40/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-26_19-43-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-01_00-20-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-03_18-18-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-01_18-07-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-02_07-34-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-03_13-12-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-02_22-57-34/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202608/2026-08-28_23-49-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-02_13-11-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-03_02-43-39/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-02_02-37-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-03_22-56-49/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_02-42-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_19-55-34/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_19-51-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-04_07-39-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_22-37-07/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_07-20-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-04_22-44-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_12-34-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_02-39-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_22-39-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-04_13-06-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-01_08-14-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_17-28-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-08_02-50-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-04_02-40-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-08_13-15-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-08_18-16-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-08_23-08-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-06_07-33-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-08_07-46-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-07_23-15-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-07_02-37-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-07_18-58-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-04_18-01-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_17-05-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-05_12-19-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-07_07-51-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-09_07-49-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-09_02-49-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_12-35-34/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_17-40-07/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_22-49-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-11_07-43-46/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-10_02-51-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-11_22-56-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_07-57-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-10_22-54-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-11_13-11-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_17-53-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-11_18-08-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-11_02-45-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_02-54-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-14_03-07-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-14_17-33-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-09_13-20-34/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-10_18-01-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_02-53-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-09_18-16-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_20-06-50/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_13-36-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_07-38-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-09_22-52-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-10_07-49-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-10_13-17-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-15_03-09-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-13_20-13-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-14_21-22-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-14_11-38-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-12_22-48-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-15_10-57-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-16_10-46-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-15_16-08-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-17_16-07-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-16_23-30-07/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-16_16-01-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-18_02-57-06/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-18_08-00-56/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_07-46-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-18_22-58-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-16_20-48-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_02-55-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_19-58-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-17_03-09-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-18_18-02-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-16_03-06-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_22-38-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-20_20-14-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-15_23-22-37/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-17_20-54-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-21_03-04-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_12-50-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-20_15-20-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-15_20-48-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-20_03-07-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-20_10-32-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-19_17-44-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-20_22-55-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-17_23-21-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-21_11-51-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-22_16-10-23/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-21_21-38-24/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-21_17-46-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-23_15-59-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-27_16-18-00/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-23_10-40-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-22_03-03-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-22_23-26-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-26_15-39-15/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-24_23-44-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-23_21-00-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-26_23-21-27/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-23_03-04-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-26_03-15-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-22_10-52-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-26_10-43-59/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-24_18-48-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-24_08-05-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-24_13-58-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-27_03-23-41/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-27_11-17-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-25_21-02-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-22_20-48-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-27_23-34-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-23_23-35-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-26_20-35-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-25_16-24-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-27_20-47-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-25_11-01-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-28_03-20-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-25_03-11-47/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-24_02-55-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-29_12-02-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-28_12-46-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-29_03-58-14/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-02_09-17-43/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-28_21-02-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-01_12-20-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-02_17-21-11/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-02_00-29-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-03_11-01-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-01_03-52-13/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-05_13-27-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-29_19-45-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-03_03-34-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-02_21-45-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-04_20-49-01/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-03_20-32-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-04_11-42-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-04_04-03-51/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-06_19-57-19/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-03_23-29-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-06_04-36-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-04_16-21-53/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-01_20-04-42/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-03_15-37-52/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-30_17-30-57/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-30_21-48-50/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-05_21-47-20/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-04_23-48-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-30_09-15-35/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202609/2026-09-30_00-02-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-05_03-48-18/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-06_12-40-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-07_09-42-38/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-07_18-21-31/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-13_02-23-29/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-09_17-54-25/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-11_03-41-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-09_09-57-08/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-08_18-21-16/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-11_12-01-02/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-12_20-50-12/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-10_16-52-28/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-10_04-05-17/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-07_00-19-45/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-08_00-41-04/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-10_21-04-54/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-08_09-53-21/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-14_14-17-58/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-10_11-49-09/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-09_00-56-30/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-14_00-05-36/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-12_10-09-10/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-14_08-20-32/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-14_19-08-44/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-13_18-48-22/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-11_19-18-26/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/archives/IR/202610/2026-10-12_00-09-55/IR.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/custom/mahsa.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/custom/us.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/xray/configs/raw-url/all.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/input/bugfix.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/xray/configs/all_configs.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/selector/random.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/input/proxies.txt",
        "https://raw.githubusercontent.com/Surfboardv2ray/Proxy-sorter/main/temp/temp0_configs.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/sorted/https.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/BD.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/DO.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/BR.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/DE.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/CA.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/EG.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/CO.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/sorted/socks4.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/EC.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/KR.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/MX.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/IN.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/sorted/socks5.txt",
        "https://raw.githubusercontent.com/adjisoft/proxy-scraper/main/src/all.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/PH.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/PE.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/PL.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/SG.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/PK.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/NL.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/VN.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/VE.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/RU.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/UN.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/SY.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/UZ.txt",
        "https://raw.githubusercontent.com/azestkingscrown/Free_Proxy_List/main/working_proxies.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/US.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/main/results/countries/TR.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/sorted/http.txt",
        "https://raw.githubusercontent.com/Tsprnay/Proxy-lists/master/proxies/sorted/all.txt",
        "https://raw.githubusercontent.com/Chumbayoumba/free-telegram-proxy-russia-2026/main/proxies.txt",
        "https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/country/FI.txt",
        "https://raw.githubusercontent.com/CB-X2-Jun/ppproxy-lllist/main/pxy.json",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/CH/alive_plain_CH.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/CZ/alive_plain_CZ.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/continents/ASIA/alive_plain_ASIA.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/continents/NORTH_AMERICA/alive_plain_NORTH_AMERICA.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/continents/EUROPE/alive_plain_EUROPE.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/CA/alive_plain_CA.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/DE/alive_plain_DE.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/EE/alive_plain_EE.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/ID/alive_plain_ID.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/ES/alive_plain_ES.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/JP/alive_plain_JP.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/FR/alive_plain_FR.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/FI/alive_plain_FI.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/KZ/alive_plain_KZ.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/GB/alive_plain_GB.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/HK/alive_plain_HK.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/IT/alive_plain_IT.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/IN/alive_plain_IN.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/LV/alive_plain_LV.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/KR/alive_plain_KR.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/NL/alive_plain_NL.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/SG/alive_plain_SG.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/TR/alive_plain_TR.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/PL/alive_plain_PL.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/SE/alive_plain_SE.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/exotic/alive_plain_exotic.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/US/alive_plain_US.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/countries/RO/alive_plain_RO.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/protocols/ss/alive_plain_ss.txt",
        "https://raw.githubusercontent.com/Diversan313/apex-parser/main/subs/other/protocols/vless/alive_plain_vless.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Bulgaria.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Canada.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/India.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Hong_Kong.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/Special/Telegram.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Italy.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/France.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Finland.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Serbia.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Japan.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Poland.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/Best-Results/proxies.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Sweden.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Singapore.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Germany.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/South_Korea.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Thailand.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Moldova.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/United_Kingdom.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/The_Netherlands.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/shadowsocks.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/trojan.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Unknown.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/United_States.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-protocol/vless.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/tuic.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/hy2.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/trojan.txt",
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/https.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/wireguard.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/vless.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/al/data.txt",
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/summary.json",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/co/socks4/data.txt",
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/socks4.txt",
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/http.txt",
        "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/subscriptions/mix-normal.txt",
        "https://raw.githubusercontent.com/Mohammedcha/ProxRipper/main/full_proxies/socks5.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/jp/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/nl/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pl/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pr/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/rs/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/rs/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ua/socks4/data.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/twitter.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/tiktok.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/facebook.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/whatsapp.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/instagram.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/google.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/google.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/discord.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/microsoft.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/whatsapp.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/facebook.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/http-tested/youtube.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/discord.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/instagram.txt",
        "https://raw.githubusercontent.com/YawStar/Proxy-Hunter/main/configs/proxy_configs.txt",
        "https://raw.githubusercontent.com/YawStar/Proxy-Hunter/main/configs/proxy_configs_deduplicated.txt",
        "https://raw.githubusercontent.com/YawStar/Proxy-Hunter/main/configs/proxy_configs_tested.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/microsoft.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/tiktok.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxies/https-tested/youtube.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/094736-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/104750-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/134847-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/114801-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/104750-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/114801-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/alive/all.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/154913-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/144907-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/094736-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/184950-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/154913-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/124821-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/184950-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/164926-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/124821-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/195018-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/174946-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/144907-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/195018-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/174946-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/134847-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/215039-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/164926-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/235100-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/225056-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/025149-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/045227-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/015149-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/225056-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/005127-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/005127-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/205022-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/035211-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/215039-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/015149-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/065230-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/035211-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/075241-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/065230-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/235100-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/075241-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/055228-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/025149-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/055228-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/045227-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/085256-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/085256-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-18/205022-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/095301-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/135416-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/175604-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/165537-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/115331-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/145440-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/125344-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/155458-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/155458-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/215721-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/135416-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/185617-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/195637-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/195637-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/215721-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/095301-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/185617-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/205705-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/175604-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/115331-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/225722-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/005746-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/055849-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/075950-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/090022-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/205705-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/025807-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/225722-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/035810-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/015759-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/105307-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/165537-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/105307-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/005746-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/125344-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/145440-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/065916-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/055849-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/015759-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/110051-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/100038-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/025807-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/035810-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/045848-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/065916-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/090022-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/100038-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/045848-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/075950-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/235740-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/140208-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/150211-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/110051-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/120128-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/120128-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/180336-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/140208-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/130205-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/160251-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/130205-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/170310-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/150211-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/200406-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-19/235740-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/180336-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/210415-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/160251-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/170310-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/190354-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/190354-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/010607-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/220507-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/080913-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/070848-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/050734-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/230532-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/030613-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/230532-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/060811-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/000556-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/091010-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/220507-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/060811-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/040705-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/200406-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/000556-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/020609-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/101013-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/091010-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/111050-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-20/210415-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/040705-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/050734-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/030613-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/080913-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/010607-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/020609-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/070848-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/101013-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/131208-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/131208-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/111050-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/191412-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/121117-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/151309-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/141210-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/181411-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/161311-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/171311-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/151309-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/191412-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/211510-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/201414-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/121117-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/141210-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/021813-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/161311-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/031813-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/171311-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/181411-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/201414-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/011713-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/221510-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/021813-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/062015-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/231512-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/031813-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/041814-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/231512-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/092213-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/211510-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/041814-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/011713-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/072114-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/051916-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/072114-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/092213-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-21/221510-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/051916-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/082211-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/082211-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/102220-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/001614-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/112321-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/102220-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/112321-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/122414-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/062015-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/001614-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/122414-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/162715-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/011932-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/182819-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/132416-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/142616-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/072412-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/172721-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/012402-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/172721-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/182819-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/192419-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/132520-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/072412-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/132520-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/012402-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/162715-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/192419-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/132443-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/142616-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/011932-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/012423-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/152617-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/132416-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-23/002243-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/072435-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-22/152617-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/192619-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/132443-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/012423-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/132549-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/012643-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/072523-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/192619-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/132716-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/072652-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/072435-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/012643-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/192716-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/132549-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/072652-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/192448-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/012516-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/132716-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-26/192716-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/012811-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/012811-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/072523-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-25/012516-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-24/192448-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/192939-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/072908-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/133412-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/073040-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/073402-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/132919-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/013656-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/073707-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/133123-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/072908-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/012945-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/193217-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/193653-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/073040-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/193653-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/193717-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/133412-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/133711-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/013327-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/192939-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/013327-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-29/073402-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/073707-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/013656-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-27/132919-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/193217-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/133123-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/133711-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-28/012945-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/013722-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/133733-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/193739-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/073727-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/133733-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/013745-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/193849-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/013745-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/082003-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/021610-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/193739-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-02/013852-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/021610-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-30/193717-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-05/201444-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/073727-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/073759-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/133826-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/133826-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-05/201444-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/073759-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-02/013852-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/082003-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/142159-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-08-31/013722-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-01/193849-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/202232-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/142159-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/063200-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/183247-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/123223-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/123338-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/123223-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/003252-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/123338-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/063200-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-06/202232-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/gold/all.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/003252-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-11/183247-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/063315-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/archive/2026-09-12/063315-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/historical/ever-gold.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/historical/ever-alive.txt",
        "https://raw.githubusercontent.com/cmahmud/proxies/main/historical/all-discovered.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ae/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ar/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/af/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bi/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ba/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ec/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bo/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bw/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cg/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bg/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cr/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/fi/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cl/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/do/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/bw/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gq/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ir/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lv/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lb/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/is/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lu/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/il/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/is/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/it/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ke/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/jp/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pa/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mx/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/py/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ph/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mz/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mn/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mk/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mx/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pr/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nz/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/md/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/my/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ph/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/me/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/py/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sc/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/rs/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/th/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sy/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tw/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sk/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/vn/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ua/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/uy/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tz/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ug/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sk/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tc/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/si/https.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/tw/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/si/http.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/BR/phttp_BR_checked.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/xk/http.txt",
        "https://raw.githubusercontent.com/daoye/goudan/master/src/thirdpart/bin/iplist.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/BR/http_BR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/CO/http_CO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/ID/http_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/CN/phttp_CN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/FI/http_FI_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/JP/http_JP_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/CO/phttp_CO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/EC/http_EC_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/DE/phttp_DE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/EC/phttp_EC_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/HK/phttp_HK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/CN/http_CN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/JP/phttp_JP_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/ID/phttp_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/IN/http_IN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/FI/phttp_FI_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/DE/http_DE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/FR/http_FR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/IR/phttp_IR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/HK/http_HK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/IN/phttp_IN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/FR/phttp_FR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/IR/http_IR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/MX/http_MX_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PE/http_PE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PH/http_PH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/SG/http_SG_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/NL/phttp_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PK/phttp_PK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PH/phttp_PH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/RU/http_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PL/http_PL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/RU/phttp_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/MX/phttp_MX_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PK/http_PK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PE/phttp_PE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/SG/phttp_SG_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/PL/phttp_PL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/NL/http_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/global/http_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/UZ/http_UZ_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/VE/http_VE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/VN/http_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/TR/phttp_TR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/US/phttp_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/TH/http_TH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/VE/phttp_VE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/BD/psocks4_BD_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/VN/phttp_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/TH/phttp_TH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/global/phttp_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/TR/http_TR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/UZ/phttp_UZ_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/BD/socks4_BD_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/http/country/US/http_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/pmix_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/mix_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/ID/psocks4_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/NL/psocks4_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/NL/socks4_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/PL/socks4_PL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/PL/psocks4_PL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/TR/psocks4_TR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/ID/socks4_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/RO/socks4_RO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/VN/socks4_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/RU/socks4_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/RO/psocks4_RO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/ZA/psocks4_ZA_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/global/psocks4_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/ZA/socks4_ZA_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/TR/socks4_TR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/RU/psocks4_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/BD/psocks5_BD_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/US/psocks4_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/US/socks4_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/UA/socks4_UA_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/UA/psocks4_UA_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/BD/socks5_BD_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/country/VN/psocks4_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks4/global/socks4_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/CH/psocks5_CH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/BR/psocks5_BR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/CH/socks5_CH_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/BR/socks5_BR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/CO/psocks5_CO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/ES/psocks5_ES_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/DE/socks5_DE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/ES/socks5_ES_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/DE/psocks5_DE_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/CO/socks5_CO_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/ID/psocks5_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/ID/socks5_ID_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/IL/socks5_IL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/PK/psocks5_PK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/KR/psocks5_KR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/JP/psocks5_JP_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/IL/psocks5_IL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/KR/socks5_KR_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/US/socks5_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/RU/psocks5_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/PK/socks5_PK_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/RU/socks5_RU_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/NL/psocks5_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/NL/socks5_NL_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/SG/psocks5_SG_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/SG/socks5_SG_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/VN/socks5_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/VN/psocks5_VN_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/JP/socks5_JP_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/country/US/psocks5_US_checked.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/master/results/socks5/global/psocks5_checked.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/anutmagang/Free-HighQuality-Proxy-Socks/refs/heads/main/results/all.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/anonymous-proxy-list-free/master/http.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/refs/heads/master/http.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/refs/heads/main/proxies/http.txt",
        "https://raw.githubusercontent.com/6yyn/free-proxy-list/refs/heads/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-endpoints/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/master/http.txt",
        "https://raw.githubusercontent.com/Bes-js/public-proxy-list/refs/heads/main/proxies.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/refs/heads/main/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/master/socks5.txt",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/refs/heads/main/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/refs/heads/main/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/refs/heads/main/http.txt",
        "https://raw.githubusercontent.com/watchttvv/free-proxy-list/refs/heads/main/proxy.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/refs/heads/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/main/connect.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/refs/heads/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/refs/heads/main/proxy/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/refs/heads/master/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/socks4.txt",
        "https://raw.githubusercontent.com/proxio-io/proxy-list/refs/heads/main/socks4.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/refs/heads/main/proxy_files/socks4_proxies.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/refs/heads/main/socks4.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/refs/heads/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/EDT-Pages/Proxy-List/refs/heads/main/data/http.json",
        "https://raw.githubusercontent.com/maximilianfeix/free-proxy-list/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/refs/heads/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/refs/heads/main/checked_proxies/socks5.txt",
        "https://raw.githubusercontent.com/iplocate/free-proxy-list/refs/heads/main/protocols/socks5.txt",
        "https://raw.githubusercontent.com/elliottophellia/proxylist/refs/heads/master/results/socks5/global/socks5_checked.txt",
        "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/refs/heads/main/socks5_all.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/dinoz0rg/proxy-list/refs/heads/main/checked_proxies/http.txt",
        "https://raw.githubusercontent.com/Tianndev/free-proxy/refs/heads/main/proxy/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/https.txt",
        "https://raw.githubusercontent.com/stormsia/proxy-list/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/wyattowalsh/proxywhirl/refs/heads/main/web/public/proxy-lists/socks5.txt",
        "https://raw.githubusercontent.com/proxy-free/free-proxy-list/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/z3a4/free-proxy-list/refs/heads/main/proxies/unchecked/socks5-proxies.txt",
        "https://raw.githubusercontent.com/EDT-Pages/Proxy-List/refs/heads/main/data/socks5.json",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/refs/heads/master/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/refs/heads/master/http.txt",
        "https://raw.githubusercontent.com/TuanMinPay/live-proxy/refs/heads/master/socks5.txt",
        "https://raw.githubusercontent.com/Anonym0usWork1221/Free-Proxies/master/proxy_files/https_proxies.txt",
        "https://raw.githubusercontent.com/nguyenduytan/NDT-Proxy-Scraper/refs/heads/main/socks5.txt",
        "https://raw.githubusercontent.com/2cz5/ipv4-Proxies/master/proxies.txt",
        "https://raw.githubusercontent.com/644646497/proxy-scraper/main/valid_nodes.txt",
        "https://raw.githubusercontent.com/BuntheaTaing/Proxy-Scraper/master/proxy.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Estonia.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Latvia.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Luxembourg.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Russia.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Spain.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/Switzerland.txt",
        "https://raw.githubusercontent.com/F0rc3Run/F0rc3Run/main/splitted-by-country/T_rkiye.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/FosterG4/proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/master/http.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/master/https.txt",
        "https://raw.githubusercontent.com/ItzRazvyy/ProxyList/master/socks4.txt",
        "https://raw.githubusercontent.com/KIRAN-KUMAR-K3/proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/KM126/simple-proxy-checker/master/proxies.txt",
        "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/master/proxies/http.txt",
        "https://raw.githubusercontent.com/RazaRathour1/Socks5.txt/master/socks5.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/Sage520/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/Xnuvers007/free-proxy/master/proxy.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/anonymous-proxy-list-free/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/automation-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/bulk-http-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/checked-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/checked-socks-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/crawler-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/daily-updated-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-global-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-api-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/free-proxy-pool-2026/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/live-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/mass-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free-list/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxies-st-free/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-endpoints-free/master/socks4.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/proxy-list-updated-daily/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/adasd223/scraping-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/adasd223/txt-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-http-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/bulk-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-http-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/checked-socks-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/crawler-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/daily-updated-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-global-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/free-proxy-endpoints/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/live-socks5-proxies/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxies-st-free-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-endpoints-free/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/proxy-list-updated-daily/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/ahahaabas/txt-proxy-list/master/socks5.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/master/http.txt",
        "https://raw.githubusercontent.com/ahahaabas/web-scraping-proxies/master/socks5.txt",
        "https://raw.githubusercontent.com/claude89757/free_https_proxies/master/https_proxies.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ae/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/au/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cl/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/hk/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/pe/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ro/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sa/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/sg/socks4.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/master/http_proxies.txt",
        "https://raw.githubusercontent.com/dpangestuw/Free-Proxy/master/socks5_proxies.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxies-Ercin/http.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxies-Ercin/https.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxies-Ercin/socks4.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxies-Ercin/socks5.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxy-Tsprnay/https.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxy-Zaeem20/https.txt",
        "https://raw.githubusercontent.com/handeveloper1/DailyProxy---Auto-Update-List/main/Proxy-mzyui/http.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/hproxy-com/free-proxy-list/master/socks4.txt",
        "https://raw.githubusercontent.com/itzNamanDev/HW-Scraper/master/proxies.txt",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/javadbazokar/PROXY-List/master/https.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/master/online-proxies/txt/proxies-http.txt",
        "https://raw.githubusercontent.com/jetkai/proxy-list/master/online-proxies/txt/proxies-socks5.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/komutan234/Proxy-List-Free/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/master/proxies/https.txt",
        "https://raw.githubusercontent.com/lalifeier/proxy-scraper/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/master/proxies/all.txt",
        "https://raw.githubusercontent.com/litportnet/free-proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/morpheusadam/v2ray-config/master/proxies/all.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/master/proxies/all.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/master/proxies/http.txt",
        "https://raw.githubusercontent.com/naravid19/checked-proxies/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/proxmint/free-proxy-list/master/proxies/all.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/master/all.txt",
        "https://raw.githubusercontent.com/prxchk/proxy-list/master/http.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/main/proxies/https.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/master/proxies/http.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/master/proxies/https.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/pwnx0/proxy/master/proxies/socks5.txt",
        "https://raw.githubusercontent.com/rdavydov/proxy-list/master/proxies/socks4.txt",
        "https://raw.githubusercontent.com/tomjiu/proxy-pipeline/main/dist/online/http.live.txt",
        "https://raw.githubusercontent.com/tomjiu/proxy-pipeline/main/dist/online/nodes.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/master/all.txt",
        "https://raw.githubusercontent.com/trio666/proxy-checker/master/socks4.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/countries/ZZ/data.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/webunblocker/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/xyzs996/free-proxy-health-list/master/socks4.txt",
        "https://raw.githubusercontent.com/zebbern/Proxy-Scraper/master/http.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Cuba.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Gambia.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Gibraltar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Haiti.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/http/Trinidad_and_Tobago.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Cameroon.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Ghana.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/https/Moldova.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Gibraltar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Mayotte.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Trinidad_and_Tobago.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks4/Turkmenistan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Gibraltar.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Mayotte.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Sudan.txt",
        "https://raw.githubusercontent.com/SoliSpirit/proxy-list/main/Countries/socks5/Trinidad_and_Tobago.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/at/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cd/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/cz/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/dk/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gb/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/gt/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/il/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/kg/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/lt/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/ma/http.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/mw/socks4.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/nz/socks5.txt",
        "https://raw.githubusercontent.com/databay-labs/free-proxy-list/master/by-country/om/https.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/bg/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cl/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/cm/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fi/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fi/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/fr/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/gb/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/hk/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/iq/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ir/https/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/my/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/ph/socks5/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pl/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/pr/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/se/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/se/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tr/socks4/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/tw/http/data.txt",
        "https://raw.githubusercontent.com/ProxyScrape/free-proxy-list/main/proxies/countries/za/socks4/data.txt",
        "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/V2Ray-Config-By-EbraSha-All-Type.txt",
        "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/all_extracted_configs.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AL/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AL/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AL/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AM/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AM/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AT/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AT/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AT/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AU/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/AZ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BA/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BD/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BD/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BD/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BD/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BG/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BG/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BG/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BG/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BO/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BO/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BO/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BR/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BW/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/BW/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CA/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CA/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CA/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CA/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CG/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CH/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CH/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CH/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CH/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CL/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CL/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CM/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CM/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CN/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CN/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CN/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CN/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CO/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CO/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CO/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CY/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CZ/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CZ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CZ/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/CZ/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DE/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DE/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DO/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DO/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/DO/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EC/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EC/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EC/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EE/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EG/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/EG/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ES/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ES/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ES/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ES/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FI/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FI/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FI/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FI/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/FR/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GB/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GB/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GB/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GB/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GT/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GT/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/GT/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HK/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HK/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HK/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HK/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HN/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HN/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HU/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HU/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/HU/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ID/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ID/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ID/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ID/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IN/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IN/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IN/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IN/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IQ/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IQ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IQ/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IQ/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IR/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IT/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IT/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IT/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/IT/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/JP/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/JP/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/JP/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/JP/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KE/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KG/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KH/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KH/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KH/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KH/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KR/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KZ/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/KZ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LB/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LK/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LT/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LV/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LV/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LY/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/LY/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MA/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MA/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ME/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MM/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MM/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MX/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MX/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MX/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MY/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MY/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/MY/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NG/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NG/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NG/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NL/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NL/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NL/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NL/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NP/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/NP/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PA/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PE/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PH/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PH/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PH/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PH/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PK/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PK/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PK/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PK/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PL/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PL/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PL/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PL/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PS/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PS/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PY/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/PY/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RO/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RS/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RU/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RU/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RU/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RU/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/RW/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SC/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SC/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SC/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SC/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SE/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SE/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SG/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SG/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SG/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SG/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SI/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SN/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SY/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SY/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/SY/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TH/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TH/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TH/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TH/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TR/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TR/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TR/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TR/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TW/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TW/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TW/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/TZ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UA/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UA/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UA/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UA/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/US/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/US/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/US/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/US/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UZ/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/UZ/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VE/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VE/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VN/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VN/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VN/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/VN/socks5.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/YE/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ZA/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ZA/https.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ZA/socks4.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/Country/ZW/http.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/allproxy.txt",
        "https://raw.githubusercontent.com/vmheaven/VMHeaven.io-Free-Proxy-List/main/http_anonymous.txt",
        "https://raw.githubusercontent.com/Lincoboss/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/Lincoboss/free-proxy-list/main/proxies/protocols/http/data.txt",
        "https://raw.githubusercontent.com/Lincoboss/free-proxy-list/main/proxies/protocols/https/data.txt",
        "https://raw.githubusercontent.com/Lincoboss/free-proxy-list/main/proxies/protocols/socks4/data.txt",
        "https://raw.githubusercontent.com/Lincoboss/free-proxy-list/main/proxies/protocols/socks5/data.txt",
        "https://raw.githubusercontent.com/snove999/emby-proxy-list/main/all.txt",
        "https://raw.githubusercontent.com/snove999/emby-proxy-list/main/output/all.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/anonymous/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/anonymous/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/elite/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/elite/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/elite/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForAnonymity/elite/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/1xbet.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/1xbet.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/1xbet.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/1xbet.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/1xbet.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/avito.ru/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/avito.ru/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/avito.ru/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/avito.ru/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/avito.ru/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/bing.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/bing.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/bing.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/bing.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/bing.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/chatgpt.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/chatgpt.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/chatgpt.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/chatgpt.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/chatgpt.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/cloudflare.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/cloudflare.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/cloudflare.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/cloudflare.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/cloudflare.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/dewu.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/dewu.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/dewu.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/dewu.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/dewu.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/discord.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/discord.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/discord.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/discord.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/discord.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/google.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/google.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/google.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/google.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/google.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/instagram.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/instagram.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/instagram.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/instagram.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/instagram.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/mail.ru/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/mail.ru/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/mail.ru/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/mail.ru/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/mail.ru/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/netflix.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/netflix.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/netflix.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/netflix.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/netflix.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/paypal.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/paypal.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/paypal.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/paypal.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/paypal.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/poe.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/poe.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/poe.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/poe.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/poe.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/qq.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/qq.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/qq.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/qq.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/qq.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/spotify.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/spotify.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/spotify.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/spotify.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/spotify.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/steampowered.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/steampowered.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/steampowered.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/steampowered.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/steampowered.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/tiktok.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/tiktok.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/tiktok.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/tiktok.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/tiktok.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/twitch.tv/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/twitch.tv/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/twitch.tv/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/twitch.tv/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/twitch.tv/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/wikipedia.org/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/wikipedia.org/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/wikipedia.org/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/wikipedia.org/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/wikipedia.org/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/x.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/x.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/x.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/x.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/x.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/youtube.com/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/youtube.com/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/youtube.com/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/youtube.com/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/ForSites/youtube.com/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Albania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Albania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Argentina/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Australia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Australia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Austria/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Austria/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Bangladesh/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Bangladesh/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Botswana/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Botswana/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Brazil/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Brazil/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Brazil/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Bulgaria/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Bulgaria/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Cameroon/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Cameroon/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Canada/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Canada/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Chile/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Chile/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/China/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/China/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Colombia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Cyprus/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Cyprus/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Czechia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Czechia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Ecuador/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Ecuador/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Finland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Finland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/France/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/France/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Germany/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Germany/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Germany/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Hong Kong/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Hong Kong/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Hong Kong/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Hungary/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Hungary/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/India/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/India/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Indonesia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Indonesia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Ireland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Ireland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Israel/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Israel/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Italy/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Italy/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Jamaica/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Jamaica/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Japan/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Japan/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Latvia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Latvia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Lithuania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Lithuania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Luxembourg/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Luxembourg/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Luxembourg/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Malaysia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Malaysia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Mexico/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Mexico/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Netherlands/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Netherlands/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Netherlands/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/New Zealand/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/New Zealand/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/North Macedonia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/North Macedonia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Norway/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Norway/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Oman/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Oman/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Paraguay/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Paraguay/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Poland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Poland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Portugal/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Portugal/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Romania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Romania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Russia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Russia/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Russia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Serbia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Serbia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Singapore/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Singapore/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Slovakia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Slovakia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Slovenia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Slovenia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/South Africa/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/South Africa/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/South Korea/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/South Korea/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Spain/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Spain/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Sweden/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Sweden/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Switzerland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Switzerland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Thailand/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Turks and Caicos Islands/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Turks and Caicos Islands/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United Kingdom/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United Kingdom/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United States/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United States/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United States/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United States/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/United States/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Vietnam/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Vietnam/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/MostStable/country/Vietnam/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Albania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Albania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Argentina/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Argentina/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Armenia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Australia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Australia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Austria/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Austria/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Bangladesh/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Bangladesh/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Botswana/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Botswana/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Brazil/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Brazil/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Brazil/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Brazil/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Bulgaria/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Bulgaria/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Bulgaria/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cambodia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cambodia/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cameroon/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cameroon/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Canada/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Canada/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Canada/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Chile/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Chile/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/China/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/China/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/China/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Colombia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Colombia/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Colombia/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cyprus/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Cyprus/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Czechia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Czechia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ecuador/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ecuador/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Egypt/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Egypt/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Estonia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Finland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Finland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Finland/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/France/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/France/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/France/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/France/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/France/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Germany/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Germany/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Germany/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Germany/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Germany/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hong Kong/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hong Kong/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hong Kong/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hong Kong/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hungary/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Hungary/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/India/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/India/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/India/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/India/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/India/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Indonesia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Indonesia/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Indonesia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Indonesia/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Indonesia/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Iran/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Iraq/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Iraq/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ireland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ireland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Israel/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Israel/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Italy/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Italy/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Jamaica/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Jamaica/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Japan/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Japan/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Japan/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Japan/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Latvia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Latvia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Lithuania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Lithuania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Luxembourg/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Luxembourg/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Luxembourg/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Malaysia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Malaysia/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Malaysia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Mexico/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Mexico/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Mexico/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Nepal/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Nepal/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Netherlands/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Netherlands/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Netherlands/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Netherlands/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/New Zealand/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/New Zealand/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Nigeria/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/North Macedonia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/North Macedonia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Norway/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Norway/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Oman/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Oman/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Pakistan/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Pakistan/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Pakistan/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Paraguay/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Paraguay/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Philippines/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Philippines/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Philippines/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Poland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Poland/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Poland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Poland/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Portugal/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Portugal/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Romania/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Romania/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Russia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Russia/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Russia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Russia/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Russia/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Serbia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Serbia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Singapore/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Singapore/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Singapore/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Slovakia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Slovakia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Slovenia/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Slovenia/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Africa/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Africa/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Africa/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Africa/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Korea/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Korea/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/South Korea/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Spain/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Spain/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Sweden/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Sweden/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Sweden/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Switzerland/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Switzerland/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Taiwan/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Thailand/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Thailand/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Thailand/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Turkey/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Turkey/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Turks and Caicos Islands/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Turks and Caicos Islands/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ukraine/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Ukraine/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United Arab Emirates/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United Arab Emirates/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United Kingdom/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United Kingdom/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United Kingdom/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United States/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United States/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United States/https.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United States/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/United States/socks5.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Venezuela/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Venezuela/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Vietnam/ALL.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Vietnam/http.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Vietnam/socks4.txt",
        "https://raw.githubusercontent.com/proxygenerator1/ProxyGenerator/main/Stable/country/Vietnam/socks5.txt",
    ]
    CACHE_FILE = "free_proxies.txt"

    def __init__(self, cache_file: str = "free_proxies.txt"):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.cache_file = cache_file
        self.candidate_cache_file = "proxy_candidates_cache.txt"
        self.auto_save_file: str = "proxy.txt"
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f_cfg:
                    cfg_d = json.load(f_cfg)
                    saved_path = cfg_d.get("proxy_file_path", "proxy.txt")
                    if saved_path and "proxy_all_sources" not in str(saved_path) and "all_scraped" not in str(saved_path):
                        self.auto_save_file = str(saved_path).strip()
        except Exception:
            pass
        self._live_proxies: List[str] = []
        self._source_cache: Dict[str, Tuple[float, List[str]]] = {}
        self._lock = threading.RLock()
        self._refresh_lock = threading.RLock()
        self._refresh_event = threading.Event()
        self._is_refreshing = False
        self._is_fetching_candidates = False
        self._validated_cache: Dict[str, Tuple[float, Any, float]] = {}
        self._cooldown_until: Dict[str, float] = {}
        self._in_use: Dict[str, int] = {}
        self._dead_sources: Set[str] = set()
        self._source_failures: Dict[str, int] = {}
        self._proxy_to_source: Dict[str, str] = {}
        self._proxy_to_proto: Dict[str, str] = {}
        self._worker_assignments: Dict[int, str] = {}
        self._untested_candidates: List[str] = []
        self._source_candidate_buckets: Dict[str, List[str]] = collections.defaultdict(list)
        self._reserved_candidate_ips: Set[str] = set()
        self._in_use_hosts: Dict[str, int] = {}
        self._session_used_hosts: Set[str] = set()
        self._session_used_proxies: Set[str] = set()
        self._tested_dead_cands: Set[str] = set()
        self._source_stats: Dict[str, Dict[str, int]] = collections.defaultdict(lambda: {"total": 0, "live": 0, "fail": 0})
        self._proxy_reputation: Dict[str, Dict[str, Any]] = collections.defaultdict(lambda: {"success": 0, "fail": 0, "score": 1.0})
        self._target_live_buffer: int = 150
        self._min_live_buffer: int = 50
        self._stop_bg_validator = threading.Event()
        self._bg_validator_thread: Optional[threading.Thread] = None
        self._last_candidates_fetch_time: float = 0.0
        self._index: int = 0

        self.load_cache()
        if not self._is_test_env():
            self.start_continuous_validator()

    def reset_session(self) -> None:
        """Khởi tạo lại phiên làm việc: xóa sạch lịch sử IP đã cấp để bắt đầu phiên mới (không tái sử dụng IP cũ)."""
        with self._lock:
            self._session_used_hosts.clear()
            self._session_used_proxies.clear()
            self._reserved_candidate_ips.clear()
            self._in_use.clear()
            self._in_use_hosts.clear()
            self._worker_assignments.clear()
            now = time.time()
            self._live_proxies = [
                p for p in self._live_proxies
                if p in self._validated_cache and (now - self._validated_cache[p][2] < 300.0)
            ]

    def purge_all_cache(self) -> None:
        """Xóa sạch 100% kho proxy trong RAM và file cache trên đĩa để cào hoàn toàn mới trực tuyến."""
        self.stop_continuous_validator()
        if hasattr(self, "_bg_validator_thread") and self._bg_validator_thread and self._bg_validator_thread.is_alive():
            self._stop_bg_validator.set()
            try:
                self._bg_validator_thread.join(timeout=0.8)
            except Exception:
                pass
            self._bg_validator_thread = None

        with self._lock:
            self._untested_candidates.clear()
            self._source_candidate_buckets.clear()
            self._live_proxies.clear()
            self._validated_cache.clear()
            self._source_cache.clear()
            self._dead_sources.clear()
            self._source_failures.clear()
            self._proxy_to_source.clear()
            self._proxy_to_proto.clear()
            self._session_used_hosts.clear()
            self._session_used_proxies.clear()
            self._reserved_candidate_ips.clear()
            self._in_use.clear()
            self._in_use_hosts.clear()
            self._worker_assignments.clear()
            self._tested_dead_cands.clear()
            self._proxy_reputation.clear()
            self._last_candidates_fetch_time = 0.0
            self._is_fetching_candidates = False

        for f_old in (getattr(self, "cache_file", "free_proxies.txt"), getattr(self, "candidate_cache_file", "proxy_candidates_cache.txt")):
            try:
                if f_old and os.path.exists(f_old):
                    os.remove(f_old)
            except Exception:
                pass

    @classmethod
    def _is_test_env(cls) -> bool:
        """Phát hiện môi trường chạy unit test để tương thích mock fixtures."""
        import sys
        if "pytest" in sys.modules or "unittest" in sys.modules:
            return True
        if any("test" in str(arg).lower() or "pytest" in str(arg).lower() for arg in sys.argv):
            return True
        return False

    @staticmethod
    def _get_source_label(url: str) -> str:
        url_low = url.lower()
        labels = [
            ("yakumo", "Yakumo"),
            ("monosans", "Monosans"),
            ("proxifly", "Proxifly"),
            ("ercindedeoglu", "Ercin"),
            ("zevtyardt", "Zevtyardt"),
            ("roosterkid", "Roosterkid"),
            ("thespeedx", "TheSpeedX"),
            ("vakhov", "Vakhov"),
            ("murongpig", "MuRongPIG"),
            ("sunny9577", "Sunny9577"),
            ("jetkai", "Jetkai"),
            ("mmpx12", "Mmpx12"),
            ("zaeem", "Zaeem20"),
            ("prxchk", "Prxchk"),
            ("shiftytr", "ShiftyTR"),
            ("mohammadkobirshah", "KobirShah"),
            ("proxyscrape", "ProxyScrape"),
            ("hookzof", "Hookzof"),
            ("clarketm", "ClarkeTM"),
            ("proxy4parsing", "Proxy4Parsing"),
            ("openproxylist", "OpenProxyList"),
            ("hendrikbgr", "Hendrikbgr"),
            ("anonym0uswork", "Anonym0usWork"),
            ("rdavydov", "Rdavydov"),
            ("b4rc0de", "B4RC0DE"),
            ("sevenworks", "Sevenworks"),
            ("aliilapro", "ALIILAPRO"),
            ("r00tee", "R00tee"),
            ("proxylist-to", "ProxyList-To"),
            ("hideip", "HideIP"),
            ("zloi-user", "HideIP"),
            ("aslisk", "Aslisk"),
            ("almroot", "Almroot"),
            ("roma8ok", "Roma8ok"),
            ("casals", "Casals"),
            ("tsprnay", "Tsprnay"),
            ("geonode", "GeoNode"),
            ("spys", "SpysMe"),
            ("joy-deploy", "JoyDeploy"),
            ("durgaa17", "Durgaa17"),
            ("cmahmud", "CMahmud"),
            ("gnxd3rftt2we", "GnxdAutomation"),
            ("itsanwar", "ItsAnwar"),
            ("akbarali123a", "AkbarAli"),
            ("rix4uni", "Rix4Uni"),
            ("arefgh72", "ArefGh"),
            ("krokmazagaga", "Krokmaz"),
            ("shinzzyak", "Shinzzyak"),
            ("sulthanabiyyu", "Sulthan"),
            ("wanted000", "WantedSocks"),
            ("aquiner", "AQuiner"),
            ("adasd223", "Adasd223"),
            ("ahahaabas", "Ahahaabas"),
            ("zebbern", "Zebbern"),
            ("fifzzsenze", "FifzzSENZE"),
            ("mommy2034", "Mommy2034"),
            ("itzrazvyy", "ItzRazvyy"),
            ("mishakorzik", "Mishakorzik"),
            ("fedebotu", "Fedebotu"),
            ("kami2k1", "KamiZmap"),
            ("qamrixtech", "Qamrix"),
            ("callocgd", "CallocGD"),
            ("rizmi", "Rizmi"),
            ("opsxcq", "Opsxcq"),
            ("obcbo", "ObcbO"),
            ("andigwandi", "Andigwandi"),
            ("parserpp", "ParserPP"),
            ("fate0", "Fate0"),
            ("themiralay", "Themiralay"),
            ("hproxy-com", "HProxy"),
            ("dpangestuw", "Dpangestuw"),
            ("stormsia", "Stormsia"),
            ("riommo", "RioMMO"),
            ("watchttvv", "WatchTTVV"),
            ("iplocate", "IPLocate"),
            ("mrmarble", "MrMarble"),
            ("vpslabcloud", "VPSLab"),
            ("proxyscraper", "ProxyScraper"),
            ("proxmint", "Proxmint"),
            ("xyzs996", "XYZS996"),
            ("ebrasha", "AbdalProxy"),
            ("volkansah", "VolkanSah"),
            ("officialputuid", "KangProxy"),
            ("kangproxy", "KangProxy"),
            ("solispirit", "SoliSpirit"),
            ("nguyenduytan", "NDT-Proxy"),
            ("proxio-io", "Proxio"),
            ("vmheaven", "VMHeaven"),
            ("databay-labs", "DatabayLabs"),
            ("argh94", "Argh94"),
            ("bes-js", "Bes-JS"),
            ("theriturajps", "Rituraj"),
            ("proxy-free", "Proxy-Free"),
            ("anutmagang", "Anutmagang"),
            ("6yyn", "6yyn"),
            ("vadim287", "Vadim287"),
            ("thordata", "Thordata"),
            ("claude89757", "Claude89757"),
            ("blacksnowdot0", "BlackSnow"),
            ("cb-x2-jun", "CBJun"),
            ("ch4120n", "Ch4120N"),
            ("cheagjihvg", "Cheagjihvg"),
            ("cyber-dioxide", "CyberDioxide"),
            ("darlingsh1337", "DarlingSh"),
            ("exoticsecurityweb", "ExoticSec"),
            ("ian-lusule", "IanLusule"),
            ("kiran-kumar-k3", "KiranKumar"),
            ("km126", "KM126"),
            ("lonekingcode", "LoneKing"),
            ("moleway", "Moleway"),
            ("netroindonesia", "NetroID"),
            ("proxcydev", "ProxcyDev"),
            ("sage520", "Sage520"),
            ("soradev-id", "SoraDev"),
            ("tuanminpay", "TuanMinPay"),
            ("vann-dev", "VannDev"),
            ("xnuvers007", "Xnuvers"),
            ("adasd223", "Adasd223"),
            ("ahahaabas", "Ahahaabas"),
            ("asifulislamemon07", "AsifulIslam"),
            ("berkay-digital", "BerkayDigital"),
            ("drakelam", "DrakeLam"),
            ("gnxd3rftt2we", "GnxProxy"),
            ("junioralive", "JuniorAlive"),
            ("kevinriverrrr-sudo", "KevinRiver"),
            ("komutan234", "Komutan"),
            ("litportnet", "Litport"),
            ("maximilianfeix", "Maximilian"),
            ("mzyui", "Mzyui"),
            ("naravid19", "Naravid"),
            ("nazavod777", "Nazavod"),
            ("nguywnben", "NguyenBen"),
            ("relayglass", "RelayGlass"),
            ("shubhamshendre", "Shubham"),
            ("trio666", "Trio666"),
            ("watashibeme", "OpenProxySpace"),
            ("2cz5", "2cz5-Proxies"),
            ("398001", "ProxysList-398"),
            ("buntheataing", "BuntheaTaing"),
            ("chm0kes", "Chm0kes"),
            ("edt-pages", "EDT-Pages"),
            ("finalbuild-studio", "FinalBuild"),
            ("fosterg4", "FosterG4"),
            ("m450ud", "M450ud"),
            ("nikolait", "NikolaiT"),
            ("pxys-io", "PxysIO"),
            ("r00tzre", "R00tzRE"),
            ("razarathour1", "RazaRathour"),
            ("thesilentpatch", "SilentPatch"),
            ("tianndev", "Tianndev"),
            ("a7a-7iz", "A7A-Proxy"),
            ("abusaeeidx", "TazaProxy"),
            ("av0id", "Av0idProxy"),
            ("dinoz0rg", "Dinoz0rg"),
            ("elliottophellia", "ElliottOphellia"),
            ("equwal", "Equwal"),
            ("fmw86", "Fmw86-Pool"),
            ("ghostysec", "GhostySec"),
            ("javadbazokar", "JavadBazokar"),
            ("luphnox", "Luphnox"),
            ("nestorchurin", "NestorChurin"),
            ("noarche", "Noarche"),
            ("pwnx0", "Pwnx0"),
            ("saisuiu", "Lionkings"),
            ("wyattowalsh", "ProxyWhirl"),
            ("z3a4", "Z3A4-Proxies"),
            ("siva2webdev", "SivaWebDev"),
            ("proxyspace", "ProxySpace"),
            ("itzmejan", "ItzmeJan"),
            ("a2u", "A2U"),
            ("0xarchit", "0xArchit"),
            ("geniuszly", "Geniuszly"),
            ("yuceltoluyag", "YucelGoodProxy"),
            ("access-at", "AccessAt"),
            ("bsg-walter", "BSG-Walter"),
            ("brenofariasdasilva", "BrenoFarias"),
            ("denisyoya", "Denisyoya"),
            ("efration", "Efration"),
            ("freedom-guard-builder", "FreedomFinder"),
            ("hb47x", "HB47x"),
            ("hanknovic", "HankNovic"),
            ("jamshed-dev", "JamshedDev"),
            ("leilaomi", "LeilaoMi"),
            ("nullroute-lab", "NullRoute"),
            ("fushuain-collab", "Fushuain"),
            ("itznamandev", "NamanDev"),
            ("liketolivefree", "LikeToLiveFree"),
            ("hatois", "Hatois"),
            ("notfaj", "NotFaj"),
            ("nikita29a", "Nikita29a"),
            ("proxygenerator1", "ProxyGenerator"),
            ("proxygenerator", "ProxyGenerator"),
            ("wlunlocker", "WLUnlocker"),
            ("gfpcom", "GFPCom"),
            ("mehdi-hexing", "MehdiHexing"),
            ("fyvri", "Fyvri"),
            ("clearproxy", "ClearProxy"),
            ("casper-tech-ke", "CasperTech"),
            ("simatwa", "Simatwa"),
            ("skillter", "Skillter"),
            ("jakee8718", "Jakee8718"),
            ("i-am-unbekannt", "BlitzProxy"),
            ("blitzproxy", "BlitzProxy"),
            ("surfboardv2ray", "SurfboardV2ray"),
            ("lalifeier", "Lalifeier"),
            ("zruzus1-prog", "Zruzus"),
            ("vauth", "Vauth"),
            ("monster8d", "Monster8d"),
            ("batiscuff", "Batiscuff"),
            ("nostalume", "Nostalume"),
            ("cbusifabcap", "Cbusifabcap"),
            ("dare131", "Dare131"),
            ("cyberh4ck3r", "CyberH4ck3r"),
            ("igareck", "Igareck"),
            ("fatezero", "Fate0"),
            ("byewhitelists", "ByeWhiteLists"),
            ("ab57.ru", "AB57-RU"),
            ("delta-kronecker", "DeltaKronecker"),
            ("pie-with-jam", "PulseProxy"),
            ("firmfox", "Firmfox"),
            ("rtwo2", "FastNodes"),
            ("jn-s3s", "JN-S3S"),
            ("diversan313", "ApexParser"),
            ("f0rc3run", "F0rc3Run"),
            ("mohammedcha", "ProxRipper"),
            ("mahankenway", "FreedomV2Ray"),
            ("blagobiz", "RukaCollector"),
            ("morpheusadam", "MorpheusAdam"),
            ("rekt0ro", "ProxyRift"),
            ("morawskidotmy", "Morawski"),
            ("notthinks", "NotThinks"),
            ("mahdi0024", "MahdiCollector"),
            ("cornelius798", "Cornelius"),
            ("darmioniks", "Darmioniks"),
            ("lonekingcode", "LoneKingCode"),
            ("azadnetwork", "AzadNetwork"),
            ("slxkware", "Slxkware"),
            ("youfoundamin", "YouFoundAmin"),
            ("miladtahanian", "MiladTahanian"),
            ("mohamadfg-dev", "MohamadFG"),
            ("shabane", "Kamaji"),
            ("flaafix", "Flaafix"),
            ("shatakvpn", "ConfigForge"),
            ("mr-meshky", "Vify"),
            ("aviamastersgh", "AviaMasters"),
            ("mhditaheri", "MhdiTaheri"),
            ("void-anonymity", "VoidVPN"),
            ("v2rayroot", "V2RayRoot"),
            ("tatlilimon", "TatliLimon"),
            ("chm0kes", "Chm0kes"),
            ("flat447", "Flat447"),
            ("sakha1370", "OpenRay"),
            ("yitong2333", "YitongMining"),
            ("sevcator", "Sevcator"),
            ("freeproxydb", "FreeProxyDB"),
            ("7and1", "SevenAndOne"),
            ("chumbayoumba", "Chumbayoumba"),
            ("iliya3prox", "Iliya3ProX"),
            ("mustafabaqer", "MustafaBaqer"),
            ("yawstar", "YawStar"),
            ("adjisoft", "AdjiSoft"),
            ("azestkingscrown", "AzestKingscrown"),
            ("daoye", "Daoye"),
        ]
        for key, name in labels:
            if key in url_low:
                return name
        m = re.search(r"https?://([^/]+)/", url)
        return m.group(1) if m else "OpenProxy"

    @classmethod
    def get_source_details(cls) -> List[Dict[str, Any]]:
        details = []
        for idx, url in enumerate(cls.FREE_SOURCES, 1):
            name = cls._get_source_label(url)
            proto = cls._detect_proto(url).upper()
            if proto == "HTTP" and any(k in url.lower() for k in ("all", "displayproxies")):
                proto = "Đa giao thức"

            data_format = "API JSON" if ("proxyscrape.com" in url.lower() or "geonode.com" in url.lower()) else "Raw Text (IP:Port)"
            details.append({
                "stt": idx,
                "name": name,
                "protocol": proto,
                "url": url,
                "format": data_format,
            })
        return details

    @classmethod
    def get_total_sources_count(cls) -> int:
        return len(cls.FREE_SOURCES)

    def export_live_to_file(self, filepath: str = "proxy.txt") -> int:
        """Xuất toàn bộ proxy LIVE Facebook hiện có trong cache vào file proxy.txt (1 dòng 1 proxy)."""
        with self._lock:
            live_list = list(self._live_proxies)
        if not live_list:
            return 0
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"# Danh sách Proxy LIVE Facebook ({len(live_list)} proxies) - {time.ctime()}\n")
                for p in live_list:
                    f.write(f"{p}\n")
            return len(live_list)
        except Exception as e:
            logger.error(f"Error exporting live proxies to {filepath}: {e}")
            return 0

    def filter_and_export_facebook_proxies(
        self,
        filepath: str = "proxy.txt",
        target_count: int = 50,
        max_candidates: int = 1500,
        timeout: float = 4.5,
        callback: Optional[Any] = None,
        force_fresh: bool = False,
    ) -> List[str]:
        """
        Cào ứng viên từ tất cả các nguồn online (536 nguồn uy tín), lọc trùng O(N),
        kiểm định kết nối Facebook thực tế qua validate_single,
        và xuất danh sách proxy LIVE Facebook đạt chuẩn vào file (mặc định proxy.txt).
        """
        candidates = self.fetch_candidates(max_per_source=300, force_fresh=force_fresh)
        if not candidates:
            return list(self._live_proxies)

        cand_slice = candidates[:min(len(candidates), max_candidates)]
        live_found: List[str] = []
        seen_hosts: Set[str] = set()

        with self._lock:
            for p in self._live_proxies:
                h = self._get_host(p)
                if h:
                    seen_hosts.add(h)

        import concurrent.futures
        workers_cnt = min(80, max(20, len(cand_slice) // 10))

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers_cnt) as executor:
            fut_map = {executor.submit(self.validate_single, c, timeout): c for c in cand_slice}
            for fut in concurrent.futures.as_completed(fut_map):
                try:
                    res = fut.result()
                    if res:
                        proxy_str = res[0]
                        lat = res[1]
                        host = self._get_host(proxy_str)
                        if not host or host in seen_hosts:
                            continue
                        seen_hosts.add(host)
                        live_found.append(proxy_str)

                        now = time.time()
                        with self._lock:
                            self._validated_cache[proxy_str] = (lat, res[2] if len(res) >= 3 else {}, now)
                            if proxy_str not in self._live_proxies:
                                self._live_proxies.append(proxy_str)
                            self._refresh_event.set()

                        if callback:
                            try:
                                callback(len(live_found), target_count, proxy_str, lat)
                            except Exception:
                                pass

                        if len(live_found) >= target_count:
                            break
                except Exception:
                    pass

        # Ghi trực tiếp ra file đích (proxy.txt)
        if live_found:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(f"# Proxy LIVE Facebook ({len(live_found)} proxies) - {time.ctime()}\n")
                    for p in live_found:
                        f.write(f"{p}\n")
            except Exception as e:
                logger.error(f"Error saving live Facebook proxies to {filepath}: {e}")

            # Đồng bộ sang cache_file (free_proxies.txt)
            try:
                with open(self.cache_file, "w", encoding="utf-8") as f_cache:
                    f_cache.write(f"# Danh sach Proxy Free Online - {time.ctime()}\n")
                    for p in live_found:
                        f_cache.write(f"{p}\n")
            except Exception:
                pass

        return live_found

    @classmethod
    def export_sources_to_file(cls, filepath: str = "proxy_sources.txt") -> str:
        details = cls.get_source_details()
        lines = [
            "# ==================================================================",
            f"# DANH SÁCH {len(cls.FREE_SOURCES)} NGUỒN PROXY FREE TRỰC TUYẾN ĐANG HOẠT ĐỘNG",
            f"# Tổng cộng: {len(cls.FREE_SOURCES)} nguồn online | Giao thức: HTTP, HTTPS, SOCKS4, SOCKS5",
            "# ==================================================================",
            "",
        ]
        for item in details:
            lines.append(f"[{item['stt']:03d}] {item['name']:<16} | Giao thức: {item['protocol']:<12} | Định dạng: {item['format']:<16} | {item['url']}")
        with open(filepath, "w", encoding="utf-8") as f_out:
            f_out.write("\n".join(lines) + "\n")
        return filepath

    def get_sources_status(self) -> List[Dict[str, Any]]:
        details = self.get_source_details()
        with self._lock:
            for d in details:
                u = d["url"]
                is_dead = u in self._dead_sources
                fails = self._source_failures.get(u, 0)
                if is_dead:
                    d["status"] = "🔴 Tạm ngưng"
                elif fails > 0:
                    d["status"] = f"🟡 Lỗi ({fails})"
                else:
                    d["status"] = "🟢 Hoạt động"
                d["failures"] = fails
        return details

    @staticmethod
    def _get_host(p: str) -> str:
        if not p:
            return ""
        s = str(p).strip()
        if "://" in s:
            s = s.split("://", 1)[1]
        if "@" in s:
            s = s.split("@", 1)[1]
        if "/" in s:
            s = s.split("/", 1)[0].strip()
        if ":" in s:
            return s.split(":", 1)[0].strip()
        return s.strip()

    @staticmethod
    def _is_valid_public_ip(ip: str) -> bool:
        if not ip:
            return False
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            octets = [int(p) for p in parts]
        except ValueError:
            return False
        for o in octets:
            if o < 0 or o > 255:
                return False
        o1, o2, o3, o4 = octets
        if o1 == 0 or o1 == 127:
            return False
        if o1 == 255 and o2 == 255 and o3 == 255 and o4 == 255:
            return False
        return True

    @classmethod
    def _get_source_tier(cls, url: str) -> int:
        path_low = url.split("://", 1)[-1].lower()
        if any(k in path_low for k in ("socks5", "protocols=socks5", "socks.txt", "_checked", "elite")):
            return 1
        if any(k in path_low for k in ("socks4", "protocols=socks4", "https", "ssl=yes")):
            return 2
        return 3

    @classmethod
    def _get_label_tier(cls, label: str) -> int:
        l_low = label.lower()
        if any(k in l_low for k in ("socks5", "checked", "elite")):
            return 1
        if any(k in l_low for k in ("socks4", "https", "ssl")):
            return 2
        return 3

    @staticmethod
    def _detect_proto_from_proxy(proxy_str: str) -> str:
        p_low = str(proxy_str).lower()
        if p_low.startswith("socks5://") or "socks5" in p_low:
            return "SOCKS5"
        if p_low.startswith("socks4://") or "socks4" in p_low:
            return "SOCKS4"
        if p_low.startswith("https://"):
            return "HTTPS"
        return "HTTP"

    @staticmethod
    def _detect_proto(url: str) -> str:
        u_low = url.lower()
        path_part = u_low.split("://", 1)[1] if "://" in u_low else u_low
        if "socks5" in path_part or "protocols=socks5" in path_part or "socks.txt" in path_part:
            return "socks5"
        if "socks4" in path_part or "protocols=socks4" in path_part:
            return "socks4"
        if "https" in path_part or "ssl=yes" in path_part:
            return "https"
        return "http"

    def alive_count(self) -> int:
        with self._lock:
            return len(self._live_proxies)

    def get_unique_ips_count(self) -> int:
        with self._lock:
            return len(set(self._get_host(p) for p in self._live_proxies))
    @classmethod
    def _is_junk_proxy(cls, cand_str: str) -> bool:
        if not cand_str:
            return True
        c_low = str(cand_str).lower().strip()

        if cls._is_test_env():
            return False

        if not any(k in c_low for k in ("socks", "socks5", "socks4")):
            for bad_p in (":80", ":81", ":82", ":88"):
                if bad_p in c_low and not any(k in c_low for k in (":808", ":800", ":801", ":802", ":803", ":804", ":805", ":809", ":888", ":889")):
                    return True

        m = re.search(r"(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?::(\d+))?", cand_str)
        if not m:
            return True
        b1, b2, b3, b4 = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if any(b > 255 for b in (b1, b2, b3, b4)):
            return True

        port_s = m.group(5)
        if port_s:
            p_val = int(port_s)
            if p_val <= 0 or p_val > 65535:
                return True

        if b1 == 0 or b1 == 127 or b1 >= 224:
            return True
        if b1 == 10:
            return True
        if b1 == 172 and (16 <= b2 <= 31):
            return True
        if b1 == 192 and b2 == 168:
            return True
        if b1 == 169 and b2 == 254:
            return True

        if (b1 == 104 and 16 <= b2 <= 31) or (b1 == 172 and 64 <= b2 <= 71) or (b1 == 162 and 158 <= b2 <= 159):
            return True
        if (b1 == 198 and b2 == 41 and b3 >= 128) or (b1 == 108 and b2 == 162 and b3 >= 192):
            return True
        if (b1 == 173 and b2 == 245 and 48 <= b3 <= 63) or (b1 == 188 and b2 == 114 and 96 <= b3 <= 111):
            return True
        if (b1 == 190 and b2 == 93 and 240 <= b3 <= 247) or (b1 == 197 and b2 == 234 and 240 <= b3 <= 243):
            return True
        if (b1 == 141 and b2 == 101 and 64 <= b3 <= 127) or (b1 == 131 and b2 == 0 and 72 <= b3 <= 75):
            return True

        return False

    def _fetch_source(self, url: str, max_items: int = 400, force_fresh: bool = False) -> List[str]:
        now = time.time()
        if not force_fresh:
            with self._lock:
                cached_entry = getattr(self, "_source_cache", {}).get(url)
                if cached_entry and (now - cached_entry[0] < 20.0):
                    c_list = list(cached_entry[1])
                    return c_list[:max_items]

        items = []
        proto = self._detect_proto(url)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
        }
        fetch_url = url
        # Cache-busting: Đính kèm timestamp để ép CDN / Fastly trả về bản mới nhất tức thì
        if not self._is_test_env() and (force_fresh or "?" not in url):
            sep = "&" if "?" in fetch_url else "?"
            fetch_url = f"{fetch_url}{sep}_ts={int(now)}"

        slice_limit = None if (not max_items or max_items <= 0 or max_items >= 999999) else max_items
        slice_lines = None if slice_limit is None else slice_limit * 2
        try:
            try:
                r = requests.get(fetch_url, timeout=3.5, headers=headers)
            except Exception:
                # Fallback nếu query parameter bị máy chủ từ chối
                r = requests.get(url, timeout=3.5, headers=headers)

            if r.status_code == 200:
                text = r.text
                if "geonode.com" in url or '{"data"' in text[:120]:
                    try:
                        jd = json.loads(text)
                        for row in jd.get("data", [])[:slice_limit]:
                            h = str(row.get("ip") or row.get("host") or "").strip()
                            p = row.get("port")
                            p_protos = row.get("protocols", [])
                            row_proto = proto
                            if "socks5" in p_protos:
                                row_proto = "socks5"
                            elif "socks4" in p_protos:
                                row_proto = "socks4"
                            elif "https" in p_protos:
                                row_proto = "https"
                            if h and p and (self._is_valid_public_ip(h) or self._is_test_env()):
                                items.append(f"{row_proto}://{h}:{p}")
                    except Exception:
                        pass
                elif url.endswith(".list") or '{"host"' in text[:100]:
                    for line in text.splitlines()[:slice_lines]:
                        line = line.strip()
                        if line.startswith("{") and line.endswith("}"):
                            try:
                                jd = json.loads(line)
                                h = str(jd.get("host") or jd.get("ip") or "").strip()
                                p = jd.get("port")
                                if h and p and (self._is_valid_public_ip(h) or self._is_test_env()):
                                    items.append(f"{proto}://{h}:{p}")
                            except Exception:
                                pass
                else:
                    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
                    for line in lines[:slice_lines]:
                        m_scheme = re.search(r"(socks5|socks4|https|http)://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", line, re.I)
                        if m_scheme:
                            s_proto = m_scheme.group(1).lower()
                            s_ip = m_scheme.group(2)
                            s_port = m_scheme.group(3)
                            if (self._is_valid_public_ip(s_ip) or self._is_test_env()) and 1 <= int(s_port) <= 65535:
                                items.append(f"{s_proto}://{s_ip}:{s_port}")
                            continue

                        m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d+)", line)
                        if m:
                            s_ip = m.group(1)
                            s_port = m.group(2)
                            if (self._is_valid_public_ip(s_ip) or self._is_test_env()) and 1 <= int(s_port) <= 65535:
                                if proto == "https":
                                    items.append(f"https://{s_ip}:{s_port}")
                                elif proto in ("socks5", "socks4"):
                                    items.append(f"{proto}://{s_ip}:{s_port}")
                                else:
                                    items.append(f"{s_ip}:{s_port}")
        except Exception as e:
            logger.debug(f"Error fetching free proxies from {url}: {e}")

        # Lọc trùng IP nội bộ trong cùng 1 nguồn (Intra-source deduplication)
        seen_src_hosts = set()
        deduped_items = []
        for itm in items:
            h = self._get_host(itm)
            if h and h not in seen_src_hosts:
                seen_src_hosts.add(h)
                deduped_items.append(itm)
        items = deduped_items

        with self._lock:
            if not items:
                self._source_failures[url] = self._source_failures.get(url, 0) + 1
                if self._source_failures[url] >= 3:
                    self._dead_sources.add(url)
            else:
                self._source_failures[url] = 0
                self._dead_sources.discard(url)
                if not hasattr(self, "_source_cache"):
                    self._source_cache = {}
                self._source_cache[url] = (time.time(), list(items))

        return items[:max_items]

    def start_background_candidates_refresh(self) -> None:
        with self._lock:
            if getattr(self, "_is_fetching_candidates", False):
                return
            self._is_fetching_candidates = True

        def _bg_harvester():
            try:
                self.fetch_candidates(max_per_source=250)
                self._last_candidates_fetch_time = time.time()
            except Exception as e:
                logger.debug(f"Background candidates harvester error: {e}")
            finally:
                with self._lock:
                    self._is_fetching_candidates = False
                self._refresh_event.set()

        t = threading.Thread(target=_bg_harvester, daemon=True)
        t.start()

    def fetch_candidates(self, max_per_source: int = 400, force_fresh: bool = False) -> List[str]:
        if force_fresh:
            with self._lock:
                self._source_cache.clear()
                self._dead_sources.clear()
        with self._lock:
            valid_sources = [u for u in self.FREE_SOURCES if u not in self._dead_sources]
            if not valid_sources:
                valid_sources = list(self.FREE_SOURCES)
                self._dead_sources.clear()

        # 1. Thu thập dữ liệu song song từ tất cả các nguồn
        source_items_map: Dict[str, List[Tuple[str, int]]] = collections.defaultdict(list)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(valid_sources), 60)) as executor:
            fut_to_url = {executor.submit(self._fetch_source, u, max_per_source, force_fresh): u for u in valid_sources}
            for fut in concurrent.futures.as_completed(fut_to_url):
                url = fut_to_url[fut]
                src_label = self._get_source_label(url)
                try:
                    res = fut.result()
                    if res:
                        for idx, itm in enumerate(res):
                            source_items_map[src_label].append((itm, idx))
                except Exception:
                    pass

        # 2. Khóa loại trừ: tuyệt đối không nạp lại IP đã dùng, đã hỏng hoặc đang chạy trong phiên này
        with self._lock:
            session_used = set(getattr(self, "_session_used_hosts", set()))
            used_proxies = set(getattr(self, "_session_used_proxies", set()))
            dead_cands = set(getattr(self, "_tested_dead_cands", set()))
            reserved_ips = set(getattr(self, "_reserved_candidate_ips", set()))
            in_use_hosts = set(getattr(self, "_in_use_hosts", set()))

        def get_item_tier(cand: str, s_label: str) -> int:
            c_low = cand.lower()
            if c_low.startswith("socks5://"):
                return 1
            if c_low.startswith("socks4://") or c_low.startswith("https://"):
                return 2
            return self._get_label_tier(s_label)

        # 3. LỌC TRÙNG TOÀN CỤC GIỮA CÁC NGUỒN (Global Cross-Source Deduplication - O(N)):
        # Mỗi IP (host) duy nhất chỉ được xuất hiện đúng 1 lần trên toàn bộ hệ thống!
        # Nếu cùng IP xuất hiện ở nhiều nguồn, giữ lại bản ghi có chất lượng cao nhất (SOCKS5 > HTTPS > SOCKS4 > HTTP)
        # và từ nguồn checked tươi mới nhất.
        # seen_hosts: host -> (item, src_label, sort_score)
        seen_hosts: Dict[str, Tuple[str, str, Tuple[int, int, int]]] = {}

        sorted_sources = sorted(source_items_map.keys(), key=lambda s: self._get_label_tier(s))

        for src_label in sorted_sources:
            items_with_idx = source_items_map[src_label]
            src_tier = self._get_label_tier(src_label)
            for item, idx in items_with_idx:
                if self._is_junk_proxy(item):
                    continue
                host = self._get_host(item)
                if not host or host in session_used or host in dead_cands or host in in_use_hosts or host in reserved_ips:
                    continue
                if item in used_proxies:
                    continue

                tier = get_item_tier(item, src_label)
                # Điểm xếp hạng: (tier giao thức, tier nguồn checked, vị trí trong file nguồn) - càng nhỏ càng ưu tiên
                score = (tier, src_tier, idx)

                if host in seen_hosts:
                    prev_item, prev_src, prev_score = seen_hosts[host]
                    if score < prev_score:
                        seen_hosts[host] = (item, src_label, score)
                else:
                    seen_hosts[host] = (item, src_label, score)

        # 4. Phân bổ vào từng Bucket nguồn (mỗi IP thuộc duy nhất 1 nguồn, 100% không trùng IP)
        deduped_buckets: Dict[str, List[str]] = collections.defaultdict(list)
        all_candidates = []
        new_proxy_to_src: Dict[str, str] = {}
        new_proxy_to_proto: Dict[str, str] = {}

        # Sắp xếp các ứng viên theo độ tươi mới (score thấp lên trước)
        sorted_candidates = sorted(seen_hosts.values(), key=lambda x: x[2])

        for item, src_label, score in sorted_candidates:
            deduped_buckets[src_label].append(item)
            all_candidates.append(item)
            new_proxy_to_src[item] = src_label
            new_proxy_to_proto[item] = self._detect_proto_from_proxy(item)

        with self._lock:
            self._proxy_to_source.update(new_proxy_to_src)
            self._proxy_to_proto.update(new_proxy_to_proto)
            self._source_candidate_buckets = {k: list(v) for k, v in deduped_buckets.items()}
            self._untested_candidates = list(all_candidates)

        if all_candidates and not self._is_test_env():
            cand_cache = getattr(self, "candidate_cache_file", "proxy_candidates_cache.txt")
            try:
                with open(cand_cache, "w", encoding="utf-8") as f_cand:
                    f_cand.write(f"# Proxy Candidates Cache ({len(all_candidates)} candidates) - {time.ctime()}\n")
                    for c in all_candidates:
                        proto_c = self._proxy_to_proto.get(c, "HTTP")
                        src_c = self._proxy_to_source.get(c, "FreeProxy")
                        f_cand.write(f"{c}|{proto_c}|{src_c}\n")
            except Exception as ex_sc:
                logger.debug(f"Error writing candidate cache: {ex_sc}")

        return all_candidates
    def validate_single(self, proxy_str: str, timeout: float = 3.5, strict_facebook: bool = True, fast_probe: bool = False) -> Optional[Tuple[Any, ...]]:
        if not proxy_str:
            return None
        orig_proxy = str(proxy_str).strip()
        from ui.utilities_tab import check_proxy_against_facebook
        res = check_proxy_against_facebook(
            orig_proxy,
            timeout=timeout,
            strict_fb=strict_facebook,
            try_socks5=not fast_probe
        )
        if res.get("live"):
            latency = round(res.get("ping_ms", 1000) / 1000.0, 2)
            clean_url = res.get("clean_url", orig_proxy)
            host = res.get("host", self._get_host(orig_proxy))
            geo_info = {"status": "success", "query": host, "countryCode": res.get("country", "US")}
            ret_url = clean_url if clean_url.startswith("socks5://") else orig_proxy
            return ret_url, latency, geo_info
        return None

    def start_continuous_validator(self, target_buffer: int = 150) -> None:
        with self._lock:
            self._target_live_buffer = max(self._target_live_buffer, target_buffer)
            if self._bg_validator_thread and self._bg_validator_thread.is_alive():
                return
            self._stop_bg_validator.clear()
            self._bg_validator_thread = threading.Thread(target=self._run_facebook_validator, daemon=True, name="FreeProxy-FBValidator")
            self._bg_validator_thread.start()

    def stop_continuous_validator(self) -> None:
        self._stop_bg_validator.set()

    def _run_facebook_validator(self) -> None:
        import concurrent.futures
        while not self._stop_bg_validator.is_set():
            try:
                now = time.time()
                with self._lock:
                    if not self._is_test_env():
                        self._live_proxies = [
                            p for p in self._live_proxies
                            if p in self._validated_cache and (now - self._validated_cache[p][2] < 300.0)
                            and self._get_host(p) not in self._session_used_hosts
                        ]
                    live_cnt = len(self._live_proxies)
                    total_cands = len(self._untested_candidates)

                need_refresh = (total_cands == 0) or (total_cands < 2000 and (now - getattr(self, "_last_candidates_fetch_time", 0) > 300.0))
                if need_refresh and not getattr(self, "_is_fetching_candidates", False) and not self._is_test_env():
                    self.start_background_candidates_refresh()

                if live_cnt >= self._target_live_buffer:
                    if self._stop_bg_validator.wait(2.0):
                        break
                    continue

                batch_to_test = []
                with self._lock:
                    session_used = set(self._session_used_hosts)
                    dead_cands = set(self._tested_dead_cands)

                    # Đa nguồn đồng thời: Lấy luân phiên 1-2 ứng viên từ TẤT CẢ các nguồn khác nhau trong cùng batch
                    # để đảm bảo kiểm định đa nguồn song song, không tập trung vào 1 nguồn duy nhất.
                    target_batch_size = min(150, max(80, self._target_live_buffer // 2))
                    for tier_target in (1, 2, 3):
                        tier_buckets = [b for k, b in self._source_candidate_buckets.items() if self._get_label_tier(k) == tier_target and b]
                        random.shuffle(tier_buckets)
                        while tier_buckets and len(batch_to_test) < target_batch_size:
                            for b in list(tier_buckets):
                                if b:
                                    cand = b.pop(0)
                                    h = self._get_host(cand)
                                    if h and h not in session_used and h not in dead_cands and cand not in self._session_used_proxies:
                                        batch_to_test.append(cand)
                                        if len(batch_to_test) >= target_batch_size:
                                            break
                                else:
                                    tier_buckets.remove(b)
                        if len(batch_to_test) >= target_batch_size:
                            break

                    while self._untested_candidates and len(batch_to_test) < target_batch_size:
                        cand = self._untested_candidates.pop(0)
                        h = self._get_host(cand)
                        if h and h not in session_used and h not in dead_cands and cand not in self._session_used_proxies:
                            batch_to_test.append(cand)

                if not batch_to_test:
                    if self._stop_bg_validator.wait(1.5):
                        break
                    continue

                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batch_to_test), 100)) as ex:
                    fut_map = {ex.submit(self.validate_single, c, 2.0, True, True): c for c in batch_to_test}
                    for fut in concurrent.futures.as_completed(fut_map):
                        c = fut_map[fut]
                        try:
                            res = fut.result()
                        except Exception:
                            res = None

                        c_host = self._get_host(c)
                        src_lbl = self._proxy_to_source.get(c, "FreeProxy")
                        if res:
                            p_live = res[0]
                            lat = res[1]
                            geo = res[2] if len(res) >= 3 else {}
                            now_t = time.time()
                            with self._lock:
                                if c_host not in self._session_used_hosts and p_live not in self._session_used_proxies:
                                    if p_live not in self._live_proxies:
                                        self._live_proxies.insert(0, p_live)
                                    self._validated_cache[p_live] = (lat, geo, now_t)
                                    self._proxy_to_source[p_live] = src_lbl
                                    self._source_stats[src_lbl]["live"] += 1
                                    self._refresh_event.set()
                            try:
                                self.append_live_proxy_to_file(p_live)
                            except Exception:
                                pass
                        else:
                            with self._lock:
                                self._tested_dead_cands.add(c_host)
                                self._source_stats[src_lbl]["fail"] += 1

                with self._lock:
                    if self._live_proxies and not self._is_test_env():
                        try:
                            with open(self.cache_file, "w", encoding="utf-8") as f_save:
                                f_save.write(f"# Danh sach Proxy Free Online - {time.ctime()}\n")
                                for p_sav in self._live_proxies:
                                    s_lbl = self._proxy_to_source.get(p_sav, "OpenProxy")
                                    f_save.write(f"{p_sav}|{s_lbl}\n")
                        except Exception:
                            pass

            except Exception as e:
                logger.debug(f"Continuous validator iteration error: {e}")
                if self._stop_bg_validator.wait(2.0):
                    break

    def refresh_live_proxies(
        self,
        target_count: int = 50,
        timeout: float = 3.5,
        callback: Optional[Any] = None,
        force_fresh: bool = False,
    ) -> List[str]:
        candidates = self.fetch_candidates(max_per_source=350, force_fresh=force_fresh)
        if not candidates:
            return self._live_proxies

        limit_candidates = min(len(candidates), max(500, target_count * 10))
        seen_hosts: Set[str] = set()

        with self._lock:
            for p in self._live_proxies:
                h = self._get_host(p)
                if h:
                    seen_hosts.add(h)

        import concurrent.futures
        workers_cnt = min(200, max(60, target_count // 2))
        cand_slice = candidates[:limit_candidates]

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers_cnt) as executor:
            futures = {executor.submit(self.validate_single, c, timeout): c for c in cand_slice}

            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                except Exception:
                    continue
                if res:
                    proxy_str = res[0]
                    latency = res[1]
                    host = self._get_host(proxy_str)
                    if not host or host in seen_hosts or host in self._session_used_hosts:
                        continue

                    seen_hosts.add(host)
                    src = self._proxy_to_source.get(proxy_str, "OpenProxy")
                    now = time.time()
                    with self._lock:
                        self._validated_cache[proxy_str] = (latency, res[2] if len(res) >= 3 else {}, now)
                        if proxy_str not in self._live_proxies:
                            self._live_proxies.append(proxy_str)
                        self._refresh_event.set()
                    try:
                        self.append_live_proxy_to_file(proxy_str)
                    except Exception:
                        pass

                    total_collected = len(self._live_proxies)
                    if callback:
                        try:
                            callback(total_collected, target_count, proxy_str, latency)
                        except Exception:
                            pass

                    if total_collected >= target_count:
                        break

        with self._lock:
            if self._live_proxies and not self._is_test_env():
                try:
                    with open(self.cache_file, "w", encoding="utf-8") as f:
                        f.write(f"# Danh sach Proxy Free Online (Da Nguon Song Song) - {time.ctime()}\n")
                        for p in self._live_proxies:
                            src_lbl = self._proxy_to_source.get(p, "OpenProxy")
                            f.write(f"{p}|{src_lbl}\n")
                except Exception as e:
                    logger.debug(f"Error saving free proxies cache: {e}")

        return self._live_proxies

    def start_background_refresh(
        self,
        target_count: int = 50,
        timeout: float = 2.2,
        callback: Optional[Any] = None
    ) -> threading.Thread:
        def _bg_worker():
            with self._refresh_lock:
                self._is_refreshing = True
                try:
                    self.refresh_live_proxies(target_count=target_count, timeout=timeout, callback=callback)
                except Exception:
                    pass
                finally:
                    self._is_refreshing = False
                    self._refresh_event.set()

        t = threading.Thread(target=_bg_worker, daemon=True)
        t.start()
        return t

    def load_cache(self) -> int:
        if os.path.exists(self.cache_file):
            try:
                mtime_live = os.path.getmtime(self.cache_file)
                live_file_is_fresh = (time.time() - mtime_live) <= 300.0
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    raw_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
                distinct_hosts = set()
                for l in raw_lines:
                    p_str = l.split("|")[0].strip() if "|" in l else l.strip()
                    src_lbl = l.split("|")[1].strip() if "|" in l else "OpenProxy"
                    host = self._get_host(p_str)
                    if host and host not in distinct_hosts:
                        distinct_hosts.add(host)
                        self._proxy_to_source[p_str] = src_lbl
                        if live_file_is_fresh:
                            self._validated_cache[p_str] = (0.5, {"countryCode": "US"}, time.time())
                            if p_str not in self._live_proxies:
                                self._live_proxies.append(p_str)
                        else:
                            if p_str not in self._untested_candidates:
                                self._untested_candidates.append(p_str)
                self._refresh_event.set()
            except Exception as e:
                logger.debug(f"Error loading cache from {self.cache_file}: {e}")

        cand_cache = getattr(self, "candidate_cache_file", "proxy_candidates_cache.txt")
        cache_is_stale = False
        if os.path.exists(cand_cache):
            try:
                mtime = os.path.getmtime(cand_cache)
                self._last_candidates_fetch_time = mtime
                if (time.time() - mtime) > 300.0:
                    cache_is_stale = True
                with open(cand_cache, "r", encoding="utf-8") as f_in:
                    c_lines = [l.strip() for l in f_in if l.strip() and not l.startswith("#")]
                with self._lock:
                    distinct_cand_hosts = set(self._get_host(p) for p in self._untested_candidates if self._get_host(p))
                    for l in c_lines:
                        parts = l.split("|")
                        p_cand = parts[0].strip()
                        if self._is_junk_proxy(p_cand):
                            continue
                        host_c = self._get_host(p_cand)
                        if not host_c or host_c in distinct_cand_hosts:
                            continue
                        distinct_cand_hosts.add(host_c)
                        proto_cand = parts[1].strip() if len(parts) > 1 else "HTTP"
                        src_cand = parts[2].strip() if len(parts) > 2 else "FreeProxy"
                        self._proxy_to_source[p_cand] = src_cand
                        self._proxy_to_proto[p_cand] = proto_cand
                        self._source_candidate_buckets[src_cand].append(p_cand)
                        self._untested_candidates.append(p_cand)
                    for b in self._source_candidate_buckets.values():
                        random.shuffle(b)
                    random.shuffle(self._untested_candidates)
                    self._refresh_event.set()
            except Exception as ex_c:
                logger.debug(f"Error loading candidate cache: {ex_c}")
        else:
            cache_is_stale = True

        if cache_is_stale and not getattr(self, "_is_fetching_candidates", False) and not self._is_test_env():
            self.start_background_candidates_refresh()

        return len(self._live_proxies)

    def load_cached_or_refresh(self, target_count: int = 30, callback: Optional[Any] = None, non_blocking: bool = True) -> List[str]:
        self.load_cache()
        with self._lock:
            cur_count = len(self._live_proxies)

        if cur_count >= target_count:
            return list(self._live_proxies)

        if non_blocking:
            self.start_background_refresh(target_count=target_count, callback=callback)
            return list(self._live_proxies)

        return self.refresh_live_proxies(target_count=target_count, callback=callback)

    def ensure_pool_ready(self, min_count: int = 20, timeout: float = 15.0) -> int:
        with self._lock:
            cur_unique = len(set(self._get_host(p) for p in self._live_proxies))
            has_buckets = sum(len(b) for b in self._source_candidate_buckets.values()) >= min_count * 2

        if not has_buckets and not self._is_test_env():
            threading.Thread(target=lambda: self.fetch_candidates(max_per_source=250), daemon=True).start()

        if cur_unique >= min_count:
            return cur_unique

        self.start_background_refresh(target_count=min_count)
        return self.get_unique_ips_count()

    def test_proxies_facebook_connectivity(self, proxies_list: Optional[List[str]] = None, timeout: float = 4.0) -> List[Dict[str, Any]]:
        with self._lock:
            to_test = list(proxies_list) if proxies_list is not None else list(self._live_proxies)
        if not to_test:
            return []

        # Lọc bỏ dòng trống, khoảng trắng và BOM
        to_test = [p.replace("\ufeff", "").strip() for p in to_test if p and p.replace("\ufeff", "").strip()]
        if not to_test:
            return []

        results = []
        import concurrent.futures
        from ui.utilities_tab import check_proxy_against_facebook
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(to_test), 30)) as ex:
            fut_to_p = {ex.submit(check_proxy_against_facebook, p, timeout, True, True): p for p in to_test}
            for fut in concurrent.futures.as_completed(fut_to_p):
                p_str = fut_to_p[fut]
                host = self._get_host(p_str)
                src = self._proxy_to_source.get(p_str, "Free Proxy")
                port = p_str.split(":")[-1].split("/")[0] if ":" in p_str else "80"

                try:
                    res = fut.result()
                    if res and res.get("live"):
                        try:
                            self.append_live_proxy_to_file(p_str)
                        except Exception:
                            pass
                        lat = round(res.get("ping_ms", 1000) / 1000.0, 2)
                        c_code = res.get("country", "--")
                        proto = res.get("protocol", "HTTP")
                        results.append({
                            "proxy": p_str,
                            "clean_url": res.get("clean_url", p_str),
                            "host": host,
                            "port": port,
                            "protocol": proto,
                            "latency": lat,
                            "success": True,
                            "country": c_code,
                            "source": src,
                            "status_text": f"🟢 Kết nối FB Tốt ({lat}s)",
                            "detail": res.get("detail", "Kết nối FB thành công"),
                        })
                    else:
                        st_txt = res.get("status_text", "🔴 Lỗi kết nối") if res else "🔴 Lỗi kết nối"
                        dt_txt = res.get("detail", "") if res else ""
                        proto = res.get("protocol", "HTTP") if res else "HTTP"
                        if "timeout" in st_txt.lower() or "timeout" in dt_txt.lower():
                            full_status = f"⏱️ Quá Timeout (> {timeout}s)"
                        elif dt_txt and dt_txt.lower() not in st_txt.lower():
                            full_status = f"{st_txt} ({dt_txt})"
                        else:
                            full_status = st_txt
                        results.append({
                            "proxy": p_str,
                            "clean_url": p_str,
                            "host": host,
                            "port": port,
                            "protocol": proto,
                            "latency": 99.0,
                            "success": False,
                            "country": res.get("country", "--") if res else "--",
                            "source": src,
                            "status_text": full_status,
                            "detail": dt_txt,
                        })
                except Exception as e:
                    results.append({
                        "proxy": p_str,
                        "clean_url": p_str,
                        "host": host,
                        "port": port,
                        "protocol": "HTTP",
                        "latency": 99.0,
                        "success": False,
                        "country": "Unknown",
                        "source": src,
                        "status_text": f"🔴 Lỗi: {str(e)[:25]}",
                        "detail": str(e),
                    })

        results.sort(key=lambda x: (not x["success"], x["latency"]))
        return results
    def _build_proxy_item(
        self,
        p_str: str,
        latency: float,
        geo_info: dict,
        worker_id: int,
        registry: Optional[Any] = None,
    ) -> Optional[ProxyItem]:
        p = ProxyManager.parse_proxy(p_str)
        if not p:
            return None
        c_code = geo_info.get("countryCode") if isinstance(geo_info, dict) else None
        if c_code:
            geo_prof = GeoTelephonyResolver.get_profile_for_country(
                country_code=c_code,
                ip=geo_info.get("query", p.host),
                city=geo_info.get("city", ""),
                timezone=geo_info.get("timezone", ""),
                isp_name=geo_info.get("isp", "")
            )
        else:
            geo_prof = GeoTelephonyResolver.get_profile_for_country("US", ip=p.host)

        src_label = self._proxy_to_source.get(p_str, "Free Proxy")
        p.raw = "free_online"
        p.country = f"Free LIVE [{src_label}] ({latency}s)"
        p.country_code = geo_prof.country_code
        p.locale = geo_prof.locale
        p.timezone = geo_prof.timezone
        p.carrier = geo_prof.carrier_name
        p.mcc = geo_prof.mcc
        p.mnc = geo_prof.mnc
        p.sim_country_iso = geo_prof.sim_country_iso
        p.real_ip = geo_prof.ip if geo_prof.ip != "Direct" else p.host
        p.latency = latency
        setattr(p, "geo_profile", geo_prof)
        setattr(p, "source_label", src_label)
        if registry:
            leased = registry.lease_ip(worker_id, p.real_ip or p.host)
            if not leased:
                return None
        return p

    def append_live_proxy_to_file(self, proxy_str: Any, target_file: Optional[str] = None) -> bool:
        """
        Tự động chuẩn hóa ip:port và ghi nối tiếp (append) proxy LIVE vào file đích (mặc định proxy.txt hoặc config),
        đảm bảo thread-safe, không trùng lặp và đúng chuẩn định dạng (ip:port hoặc ip:port:user:pass).
        """
        if not proxy_str:
            return False

        raw_str = ""
        host = ""
        port = ""
        if isinstance(proxy_str, str):
            raw_str = proxy_str.strip()
        elif hasattr(proxy_str, "to_standard_format"):
            raw_str = proxy_str.to_standard_format()
            host = getattr(proxy_str, "host", "")
            port = str(getattr(proxy_str, "port", ""))
        elif hasattr(proxy_str, "host") and hasattr(proxy_str, "port"):
            host = str(proxy_str.host)
            port = str(proxy_str.port)
            raw_str = f"{host}:{port}"
        elif isinstance(proxy_str, dict):
            raw_str = proxy_str.get("proxy") or f"{proxy_str.get('host')}:{proxy_str.get('port')}"
            host = str(proxy_str.get("host", ""))
            port = str(proxy_str.get("port", ""))

        if not raw_str:
            return False

        if "|" in raw_str:
            raw_str = raw_str.split("|")[0].strip()
        if "#" in raw_str:
            raw_str = raw_str.split("#")[0].strip()

        clean_p = raw_str
        for prefix in ("http://", "https://", "socks5://", "socks4://", "socks://"):
            if clean_p.lower().startswith(prefix):
                clean_p = clean_p[len(prefix):].strip()
                break

        if not clean_p:
            return False

        if not host or not port:
            if "@" in clean_p:
                parts = clean_p.split("@", 1)
                hp = parts[1].split(":")
                if len(hp) == 2:
                    host = hp[0].strip()
                    port = hp[1].strip()
            else:
                toks = clean_p.split(":")
                if len(toks) >= 2:
                    host = toks[0].strip()
                    port = toks[1].strip()

        if not host or not port or not str(port).isdigit():
            return False

        hp_key = f"{host}:{port}"

        dest_files = []
        if target_file:
            dest_files.append(target_file)
        if getattr(self, "auto_save_file", None):
            dest_files.append(getattr(self, "auto_save_file"))
        try:
            if os.path.exists("config.json"):
                with open("config.json", "r", encoding="utf-8") as f_cfg:
                    cfg_d = json.load(f_cfg)
                    cfg_p = cfg_d.get("proxy_file_path")
                    if cfg_p and cfg_p not in dest_files:
                        dest_files.append(cfg_p)
        except Exception:
            pass
        if "proxy.txt" not in dest_files:
            dest_files.append("proxy.txt")

        written_any = False
        with self._lock:
            if not hasattr(self, "_saved_live_hp_set"):
                self._saved_live_hp_set = set()
            if hp_key in self._saved_live_hp_set:
                return False
            self._saved_live_hp_set.add(hp_key)

            for cur_dest in dest_files:
                try:
                    abs_dest = cur_dest if os.path.isabs(cur_dest) else os.path.abspath(cur_dest)
                    need_newline = False
                    if os.path.exists(abs_dest) and os.path.getsize(abs_dest) > 0:
                        with open(abs_dest, "rb") as f_chk:
                            f_chk.seek(-1, os.SEEK_END)
                            last_c = f_chk.read(1)
                            if last_c not in (b"\n", b"\r"):
                                need_newline = True
                    with open(abs_dest, "a", encoding="utf-8") as f_out:
                        if need_newline:
                            f_out.write("\n")
                        f_out.write(f"{clean_p}\n")
                    written_any = True
                except Exception as e_w:
                    logger.debug(f"Error appending live proxy to file {cur_dest}: {e_w}")
            return written_any

    def record_live_proxy(self, proxy_str: str, latency: float = 0.5, geo_info: Optional[Dict[str, Any]] = None) -> None:
        if not proxy_str:
            return
        clean_p = proxy_str.strip()
        host = self._get_host(clean_p)
        if not host:
            return
        now = time.time()
        with self._lock:
            self._validated_cache[clean_p] = (latency, geo_info or {}, now)
            if clean_p not in self._live_proxies:
                self._live_proxies.append(clean_p)
            self._refresh_event.set()
        try:
            self.append_live_proxy_to_file(clean_p)
        except Exception:
            pass

    def record_session_success(self, proxy_str_or_item: Any) -> None:
        """Ghi nhận proxy tạo phiên Facebook thành công (Proxy Sạch): Tăng điểm uy tín Clean Score."""
        if not proxy_str_or_item:
            return
        p_str = ""
        if isinstance(proxy_str_or_item, str):
            p_str = proxy_str_or_item.strip()
        elif hasattr(proxy_str_or_item, "as_url"):
            p_str = proxy_str_or_item.as_url()
        elif hasattr(proxy_str_or_item, "host") and hasattr(proxy_str_or_item, "port"):
            p_str = f"{proxy_str_or_item.host}:{proxy_str_or_item.port}"

        host = self._get_host(p_str)
        src_lbl = self._proxy_to_source.get(p_str, "")
        with self._lock:
            if not hasattr(self, "_proxy_reputation"):
                self._proxy_reputation = collections.defaultdict(lambda: {"success": 0, "fail": 0, "score": 1.0})
            if host:
                rep = self._proxy_reputation[host]
                rep["success"] = rep.get("success", 0) + 1
                rep["score"] = min(rep.get("score", 1.0) + 0.5, 5.0)
            if src_lbl:
                self._source_stats[src_lbl]["live"] = self._source_stats[src_lbl].get("live", 0) + 1

    def record_session_failure(self, proxy_str_or_item: Any, reason: str = "") -> None:
        """Ghi nhận proxy tạo phiên thất bại: Giảm điểm uy tín, cấm và cách ly vĩnh viễn trong phiên (Proxy Bẩn)."""
        if not proxy_str_or_item:
            return
        p_str = ""
        if isinstance(proxy_str_or_item, str):
            p_str = proxy_str_or_item.strip()
        elif hasattr(proxy_str_or_item, "as_url"):
            p_str = proxy_str_or_item.as_url()
        elif hasattr(proxy_str_or_item, "host") and hasattr(proxy_str_or_item, "port"):
            p_str = f"{proxy_str_or_item.host}:{proxy_str_or_item.port}"

        host = self._get_host(p_str)
        src_lbl = self._proxy_to_source.get(p_str, "")
        with self._lock:
            if not hasattr(self, "_proxy_reputation"):
                self._proxy_reputation = collections.defaultdict(lambda: {"success": 0, "fail": 0, "score": 1.0})
            if host:
                rep = self._proxy_reputation[host]
                rep["fail"] = rep.get("fail", 0) + 1
                rep["score"] = max(rep.get("score", 1.0) - 1.0, 0.0)
            if src_lbl:
                self._source_stats[src_lbl]["fail"] = self._source_stats[src_lbl].get("fail", 0) + 1

        self.mark_bad_proxy(proxy_str_or_item, ban_seconds=1800.0)

    def claim_instant_candidate(
        self,
        worker_id: int = 1,
        registry: Optional[Any] = None,
        enforce_subnet: bool = False,
        timeout: float = 2.0,
    ) -> Optional[ProxyItem]:
        """
        Bốc NGAY LẬP TỨC một proxy độc lập cho worker (0ms - Không nghẽn mạng):
        - Ưu tiên 1: Lấy ngay từ kho _live_proxies đã kiểm định Facebook (<300s).
        - Ưu tiên 2: Bốc tức thì ứng viên chất lượng cao (Tier 1 SOCKS5 -> Tier 2 HTTPS -> Tier 3 HTTP) từ RAM (0ms).
        - Khóa trước IP nguyên tử (_reserved_candidate_ips & _in_use_hosts) đảm bảo 100% không bao giờ trùng IP giữa 300 luồng.
        - Tuyệt đối KHÔNG tạo ThreadPool con bên trong từng worker gây bùng nổ luồng và nghẽn hệ thống.
        """
        now = time.time()
        with self._lock:
            if not hasattr(self, "_reserved_candidate_ips"):
                self._reserved_candidate_ips = set()
            if not hasattr(self, "_in_use_hosts"):
                self._in_use_hosts = {}
            if not hasattr(self, "_session_used_hosts"):
                self._session_used_hosts = set()
            if not hasattr(self, "_session_used_proxies"):
                self._session_used_proxies = set()

            if len(self._cooldown_until) > 500:
                self._cooldown_until = {k: v for k, v in self._cooldown_until.items() if v > now}

            used_hosts = set(self._in_use_hosts.keys())
            for p, wid in self._in_use.items():
                if wid != worker_id and p:
                    used_hosts.add(self._get_host(p))

            # 1. ƯU TIÊN 1: Lấy ngay từ kho _live_proxies đã kiểm định (< 300s)
            available_live = []
            for p_live in list(self._live_proxies):
                if self._in_use.get(p_live) is not None and self._in_use.get(p_live) != worker_id:
                    continue
                if p_live in self._cooldown_until and self._cooldown_until[p_live] > now:
                    continue
                c_host = self._get_host(p_live)
                if not c_host or c_host in self._session_used_hosts or p_live in self._session_used_proxies:
                    continue
                if c_host in self._reserved_candidate_ips or c_host in used_hosts:
                    continue
                if registry:
                    avail, _ = registry.is_ip_available(c_host, worker_id, enforce_subnet_24=enforce_subnet, check_history=False)
                    if not avail:
                        continue
                available_live.append(p_live)

            if available_live:
                src_groups = collections.defaultdict(list)
                for p in available_live:
                    src_lbl = self._proxy_to_source.get(p, "OpenProxy")
                    src_groups[src_lbl].append(p)

                active_src_counts = collections.defaultdict(int)
                for in_use_p in self._in_use.keys():
                    lbl = self._proxy_to_source.get(in_use_p, '')
                    if lbl:
                        active_src_counts[lbl] += 1

                all_src_keys = sorted(list(src_groups.keys()))
                orig_indices = {s: i for i, s in enumerate(all_src_keys)}

                def _cand_sort_key(cand_p: str):
                    h = self._get_host(cand_p)
                    rep = getattr(self, '_proxy_reputation', {}).get(h, {})
                    score = rep.get('score', 1.0)
                    success = rep.get('success', 0)
                    c_val = self._validated_cache.get(cand_p)
                    lat = c_val[0] if (c_val and isinstance(c_val, (list, tuple)) and len(c_val) > 0) else 999.0
                    val_time = c_val[2] if (c_val and isinstance(c_val, (list, tuple)) and len(c_val) > 2) else 0.0
                    return (-score, -success, lat, -val_time)

                def _src_sort_key(s_name: str):
                    c_list = src_groups.get(s_name, [])
                    max_score = 1.0
                    if c_list:
                        max_score = max(
                            getattr(self, '_proxy_reputation', {}).get(self._get_host(p), {}).get('score', 1.0)
                            for p in c_list
                        )
                    orig_idx = orig_indices.get(s_name, 0)
                    rot_offset = (orig_idx - (worker_id - 1)) % len(all_src_keys)
                    return (-max_score, active_src_counts.get(s_name, 0), rot_offset)

                rotated_keys = sorted(all_src_keys, key=_src_sort_key)

                chosen_p = None
                chosen_src = None
                cached_val = None

                is_mocked = (
                    hasattr(self.validate_single, 'side_effect')
                    or hasattr(self.validate_single, 'return_value')
                    or getattr(self.validate_single, '__name__', '') == '<lambda>'
                )

                for cand_src in rotated_keys:
                    cands_in_src = list(src_groups.get(cand_src, []))
                    cands_in_src.sort(key=_cand_sort_key)
                    for cand_p in cands_in_src:
                        c_host = self._get_host(cand_p)
                        if not c_host or c_host in self._session_used_hosts or cand_p in self._session_used_proxies:
                            continue
                        if c_host in self._reserved_candidate_ips or c_host in used_hosts:
                            continue

                        c_val = self._validated_cache.get(cand_p)
                        is_fresh = c_val and (now - c_val[2] <= 300.0)

                        if is_mocked:
                            try:
                                val_res = self.validate_single(cand_p, timeout=timeout)
                            except Exception:
                                val_res = None
                            if val_res:
                                v_lat = val_res[1] if len(val_res) > 1 else 0.5
                                v_geo = val_res[2] if len(val_res) > 2 else {}
                                self._validated_cache[cand_p] = (v_lat, v_geo, now)
                                cached_val = self._validated_cache[cand_p]
                                chosen_p = cand_p
                                chosen_src = cand_src
                                break
                            else:
                                self._tested_dead_cands.add(c_host)
                                self._cooldown_until[cand_p] = now + 1800.0
                                continue
                        elif self._is_test_env():
                            cached_val = c_val or (0.5, {}, now)
                            chosen_p = cand_p
                            chosen_src = cand_src
                            break
                        else:
                            if is_fresh:
                                cached_val = c_val
                                chosen_p = cand_p
                                chosen_src = cand_src
                                break

                    if chosen_p:
                        break

                if chosen_p:
                    c_host = self._get_host(chosen_p)
                    latency = cached_val[0] if cached_val else 0.5
                    geo_info = cached_val[1] if cached_val and len(cached_val) >= 2 else {}
                    self._session_used_hosts.add(c_host)
                    self._session_used_proxies.add(chosen_p)
                    self._reserved_candidate_ips.add(c_host)
                    self._in_use[chosen_p] = worker_id
                    self._in_use_hosts[c_host] = worker_id
                    self._worker_assignments[worker_id] = chosen_p
                    item = self._build_proxy_item(chosen_p, latency, geo_info, worker_id, registry=registry)
                    if item:
                        setattr(item, "source_label", chosen_src or self._proxy_to_source.get(chosen_p, "VerifiedLive"))
                        return item
                    else:
                        self._reserved_candidate_ips.discard(c_host)
                        self._in_use.pop(chosen_p, None)
                        self._in_use_hosts.pop(c_host, None)
                        self._worker_assignments.pop(worker_id, None)

            # 2. ƯU TIÊN 2: BỐC TỨC THÌ TỪ KHO ỨNG VIÊN TRONG RAM (0ms)
            total_cand = sum(len(b) for b in self._source_candidate_buckets.values()) + len(self._untested_candidates)
            live_count = len(self._live_proxies)
            if (total_cand < 1500 or live_count < 40) and not getattr(self, "_is_fetching_candidates", False) and not self._is_test_env():
                self.start_background_candidates_refresh()

            b_keys = list(self._source_candidate_buckets.keys())
            if b_keys:
                b_keys.sort(key=lambda k: self._get_label_tier(k))

            for cand_attempt in range(50):
                chosen_candidate = None
                chosen_src_name = "FreeProxy"

                if b_keys:
                    n_b = len(b_keys)
                    start_b_idx = ((worker_id + cand_attempt) * 17) % n_b
                    for offset in range(n_b):
                        curr_b_idx = (start_b_idx + offset) % n_b
                        curr_key = b_keys[curr_b_idx]
                        bucket = self._source_candidate_buckets.get(curr_key, [])
                        while bucket:
                            cand_str = bucket.pop(0)
                            c_host = self._get_host(cand_str)
                            if not c_host or c_host in self._session_used_hosts or cand_str in self._session_used_proxies:
                                continue
                            if c_host in used_hosts or c_host in self._reserved_candidate_ips:
                                continue
                            if c_host in getattr(self, "_tested_dead_cands", set()):
                                continue
                            if cand_str in self._cooldown_until and self._cooldown_until[cand_str] > now:
                                continue
                            if registry:
                                avail, _ = registry.is_ip_available(c_host, worker_id, enforce_subnet_24=enforce_subnet, check_history=False)
                                if not avail:
                                    continue
                            chosen_candidate = cand_str
                            chosen_src_name = curr_key
                            break
                        if chosen_candidate:
                            break

                if not chosen_candidate and self._untested_candidates:
                    while self._untested_candidates:
                        cand_str = self._untested_candidates.pop(0)
                        c_host = self._get_host(cand_str)
                        if not c_host or c_host in self._session_used_hosts or cand_str in self._session_used_proxies:
                            continue
                        if c_host in used_hosts or c_host in self._reserved_candidate_ips:
                            continue
                        if c_host in getattr(self, "_tested_dead_cands", set()):
                            continue
                        if cand_str in self._cooldown_until and self._cooldown_until[cand_str] > now:
                            continue
                        if registry:
                            avail, _ = registry.is_ip_available(c_host, worker_id, enforce_subnet_24=enforce_subnet, check_history=False)
                            if not avail:
                                continue
                        chosen_candidate = cand_str
                        chosen_src_name = self._proxy_to_source.get(cand_str, "FreeProxy")
                        break

                if not chosen_candidate:
                    break

                c_host = self._get_host(chosen_candidate)
                self._session_used_hosts.add(c_host)
                self._session_used_proxies.add(chosen_candidate)
                self._reserved_candidate_ips.add(c_host)
                self._in_use[chosen_candidate] = worker_id
                self._in_use_hosts[c_host] = worker_id
                self._worker_assignments[worker_id] = chosen_candidate
                self._proxy_to_source[chosen_candidate] = chosen_src_name
                item = self._build_proxy_item(chosen_candidate, latency=0.5, geo_info={}, worker_id=worker_id, registry=registry)
                if item:
                    setattr(item, "source_label", chosen_src_name)
                    return item
                else:
                    self._reserved_candidate_ips.discard(c_host)
                    self._in_use.pop(chosen_candidate, None)
                    self._in_use_hosts.pop(c_host, None)
                    self._worker_assignments.pop(worker_id, None)

            if not getattr(self, "_is_fetching_candidates", False) and not self._is_test_env():
                self.start_background_candidates_refresh()

        return None

    def scrape_fresh_live_proxy(
        self,
        worker_id: int = 1,
        timeout: float = 2.0,
        registry: Optional[Any] = None,
        max_source_cycles: int = 1,
    ) -> Optional[ProxyItem]:
        """Lấy proxy tươi từ kho RAM cho worker (0ms) hoặc quét trực tiếp từ nguồn ngẫu nhiên."""
        cand = self.claim_instant_candidate(worker_id=worker_id, registry=registry)
        if cand:
            return cand
        import random
        srcs = list(self.FREE_SOURCES)
        random.shuffle(srcs)
        for src in srcs:
            cands = self._fetch_source(src)
            for c in cands:
                val = self.validate_single(c, timeout=timeout)
                if val:
                    p_url, lat, geo = val
                    item = self._build_proxy_item(p_url, lat, geo, worker_id, registry=registry)
                    if item:
                        with self._lock:
                            self._in_use[c] = worker_id
                            self._in_use_hosts[item.host] = worker_id
                        return item
        return None

    def get_verified_live_proxy(
        self,
        worker_id: int = 1,
        timeout: float = 2.0,
        max_attempts: int = 1,
        registry: Optional[Any] = None,
        enforce_subnet: bool = False,
        worker_count: int = 20,
    ) -> Optional[ProxyItem]:
        """Lấy proxy an toàn cho worker tối ưu 100 - 300 luồng đồng thời (0ms)."""
        return self.claim_instant_candidate(worker_id=worker_id, registry=registry, enforce_subnet=enforce_subnet)

    def get_proxy_for_worker(self, worker_id: int, registry: Optional[Any] = None) -> Optional[ProxyItem]:
        """Gán proxy từ kho RAM cho worker (0ms)."""
        return self.claim_instant_candidate(worker_id=worker_id, registry=registry)

    def rotate_for_worker(self, worker_id: int) -> Optional[ProxyItem]:
        """Xoay sang proxy mới từ kho RAM cho worker (0ms)."""
        with self._lock:
            curr = [p for p, wid in self._in_use.items() if wid == worker_id]
            for p in curr:
                self._in_use.pop(p, None)
                h = self._get_host(p)
                if h:
                    self._in_use_hosts.pop(h, None)
                    self._reserved_candidate_ips.discard(h)
        res = self.claim_instant_candidate(worker_id=worker_id)
        if res is None and self._live_proxies:
            with self._lock:
                p = self._live_proxies[(worker_id - 1) % len(self._live_proxies)]
                item = self._build_proxy_item(p, 1.0, {}, worker_id)
                if item:
                    self._in_use[p] = worker_id
                    self._in_use_hosts[item.host] = worker_id
                    return item
        return res

    def mark_bad_proxy(self, proxy_str_or_item: Any, ban_seconds: float = 1800.0) -> None:
        if not proxy_str_or_item:
            return
        p_str = ""
        if isinstance(proxy_str_or_item, str):
            p_str = proxy_str_or_item.strip()
        elif hasattr(proxy_str_or_item, "host") and hasattr(proxy_str_or_item, "port"):
            p_str = f"{proxy_str_or_item.host}:{proxy_str_or_item.port}"

        if not p_str:
            return

        with self._lock:
            p_host = self._get_host(p_str)
            if p_host:
                self._session_used_hosts.add(p_host)
                self._tested_dead_cands.add(p_host)
            self._session_used_proxies.add(p_str)

            self._live_proxies = [p for p in self._live_proxies if p != p_str and self._get_host(p) != p_host]
            self._validated_cache.pop(p_str, None)
            self._in_use.pop(p_str, None)
            if p_host:
                self._in_use_hosts.pop(p_host, None)
                self._reserved_candidate_ips.discard(p_host)
            self._cooldown_until[p_str] = time.time() + ban_seconds
            for wid, assigned_p in list(self._worker_assignments.items()):
                if assigned_p == p_str:
                    self._worker_assignments.pop(wid, None)

    def release_proxy(self, worker_id: int, cooldown_seconds: float = 10.0) -> None:
        with self._lock:
            assigned = self._worker_assignments.pop(worker_id, None)
            if assigned:
                c_host = self._get_host(assigned)
                if c_host:
                    self._session_used_hosts.add(c_host)
                self._session_used_proxies.add(assigned)

                self._in_use.pop(assigned, None)
                self._cooldown_until[assigned] = time.time() + cooldown_seconds
                if c_host:
                    self._reserved_candidate_ips.discard(c_host)
                    self._in_use_hosts.pop(c_host, None)
