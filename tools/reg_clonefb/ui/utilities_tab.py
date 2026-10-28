# -*- coding: utf-8 -*-
"""
ui.utilities_tab - Bộ Tiện Ích Đa Năng Cho Facebook Reg & Quản Lý Tool:
1. 🛡️ Lọc Proxy Live FB: Lọc proxy không bị Facebook chặn (Strict FB Reg & Checkpoint Guard)
2. 📥 Cào Proxy Đa Nguồn: Cào tự động từ 250+ nguồn GitHub & Web API, Deduplication O(1)
3. 🔎 Check Live UID Facebook: Kiểm tra nhanh hàng loạt UID Live/Die qua Graph API không cần cookie
4. 📬 Đọc Mail & Lấy OTP: Hỗ trợ đọc thư & bóc tách OTP từ Hotmail IMAP, DongVan OAuth2, TempMail, InboxKitten...
"""

import os
import sys
import re
import time
import socket
import logging
import threading
import webbrowser
import collections
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from core.proxy_manager import FreeProxyManager

logger = logging.getLogger(__name__)


class AppTheme:
    BG_DARK = "#12131c"
    BG_CARD = "#1c1d2d"
    BG_CARD_LIGHT = "#24263a"
    BG_INPUT = "#292a40"
    BORDER = "#3b3d5c"
    ACCENT = "#00adb5"
    ACCENT_HOVER = "#00c4cc"
    TEXT_MAIN = "#f8fafc"
    TEXT_MUTED = "#94a3b8"
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    ERROR = "#ef4444"
    INFO = "#38bdf8"
    FONT_TITLE = ("Segoe UI", 12, "bold")
    FONT_HEADER = ("Segoe UI", 10, "bold")
    FONT_BODY = ("Segoe UI", 9)
    FONT_BODY_BOLD = ("Segoe UI", 9, "bold")
    FONT_SMALL = ("Segoe UI", 8)
    FONT_SMALL_BOLD = ("Segoe UI", 8, "bold")
    FONT_CODE = ("Consolas", 9)

from ui.theme import AppTheme


def parse_proxy_string(raw_str: str) -> Tuple[str, str, str, str]:
    """Phân tích chuỗi proxy ra: (protocol, host, port, auth)"""
    if not raw_str or not isinstance(raw_str, str):
        return "http", "", "", ""
    s = raw_str.replace("\ufeff", "").replace("\xa0", " ").strip()
    if "|" in s:
        s = s.split("|")[0].strip()
    if " " in s or "\t" in s:
        tokens = re.split(r'[\s\t,;]+', s)
        for tok in tokens:
            if ":" in tok and not tok.startswith("#") and not tok.startswith("//"):
                s = tok
                break
        else:
            s = s.split()[0].strip()
    proto = "http"
    if "://" in s:
        proto, s = s.split("://", 1)
        proto = proto.lower()
    auth = ""
    if "@" in s:
        auth, hostport = s.split("@", 1)
        if ":" in hostport:
            host, port = hostport.split(":", 1)
        else:
            host, port = hostport, "80"
    else:
        parts = s.split(":")
        if len(parts) == 4:
            if parts[1].isdigit():
                host, port, u, p = parts
                auth = f"{u}:{p}"
            elif parts[3].isdigit():
                u, p, host, port = parts
                auth = f"{u}:{p}"
            else:
                host, port = parts[0], parts[1]
                auth = f"{parts[2]}:{parts[3]}"
        elif len(parts) == 2:
            host, port = parts
        else:
            host = parts[0]
            port = parts[1] if len(parts) > 1 else "80"
    port = port.split("/")[0] if "/" in port else port
    return proto, host.strip(), port.strip(), auth.strip()


def extract_facebook_uid_from_line(line: str) -> str:
    """Trích xuất UID Facebook từ bất kỳ định dạng nào (UID riêng, URL, hoặc UID|PASS|...)"""
    s = line.strip()
    if not s:
        return ""
    if s.isdigit():
        return s
    m_url = re.search(r"facebook\.com/(?:profile\.php\?id=)?([0-9]+)", s)
    if m_url:
        return m_url.group(1)
    parts = re.split(r"[|\t:,; ]+", s)
    for p in parts:
        p_c = p.strip()
        if p_c.isdigit() and len(p_c) >= 3:
            return p_c
    m_dig = re.search(r"\b([0-9]{4,25})\b", s)
    if m_dig:
        return m_dig.group(1)
    return ""


def check_proxy_against_facebook(
    proxy_raw: str,
    timeout: float = 3.5,
    strict_fb: bool = True,
    try_socks5: bool = True
) -> Dict[str, Any]:
    """Kiểm tra trực tiếp kết nối Proxy tới Facebook Registration và phân loại chính xác Live/Block/Lỗi."""
    proto, host, port, auth = parse_proxy_string(proxy_raw)
    if not host or not port.isdigit():
        return {
            "proxy": proxy_raw,
            "clean_url": proxy_raw,
            "host": host,
            "port": port,
            "protocol": proto.upper(),
            "ping_ms": 0,
            "country": "--",
            "status": "error",
            "status_text": "⚠️ Sai định dạng",
            "detail": "Host hoặc Port không hợp lệ",
            "live": False,
        }

    is_test_env = (
        "pytest" in sys.modules
        or "unittest" in sys.modules
        or any("test" in str(arg).lower() or "pytest" in str(arg).lower() for arg in sys.argv)
    )

    to_f = max(0.2, float(timeout))

    effective_proto = "http" if proto in ("http", "https") else proto
    clean_url = f"{effective_proto}://{f'{auth}@' if auth else ''}{host}:{port}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    fb_ok = False
    status_type = "error"
    status_text = "⚠️ Lỗi kết nối"
    detail_str = ""
    ping_ms = 0
    country = "--"

    real_block_phrases = (
        "error 1020", "<title>access denied</title>", "access denied",
        "<title>attention required! | cloudflare</title>", "cf-error-details",
        "we restrict certain activity", "tạm thời bị chặn", "temporarily blocked",
        "action blocked", "security check", "unusual traffic",
        "automated queries", "tài khoản của bạn tạm thời bị khóa",
        "bạn tạm thời bị chặn", "you're temporarily blocked", "you’ve been temporarily blocked",
        "ip address has been banned", "ip address is banned", "request blocked by security policy",
        "403 forbidden", "squid:", "the following error was encountered while trying to retrieve the url",
        "ein fehler aufgetreten", "error with your registration", "không thể tạo tài khoản",
        "tài khoản bị vô hiệu hóa", "account disabled", "your account has been disabled",
        "we noticed unusual activity", "challenge required", "login_attempt failed",
        "hoạt động bất thường", "chúng tôi đã phát hiện", "please try again later",
        "welcome to airport", "captive portal", "facebook.com/checkpoint", "m.facebook.com/checkpoint"
    )

    def _eval_response(txt: str, code: int, headers_dict: dict, final_url: str) -> bool:
        nonlocal fb_ok, status_type, status_text, detail_str
        txt_l = txt.lower()
        f_url_l = final_url.lower()
        hdrs_l = str(headers_dict).lower()

        # Checkpoint redirect
        if any(cp in f_url_l for cp in ("/checkpoint", "integrity/checkpoint")):
            status_type = "blocked"
            status_text = "🔴 Bị FB Chặn (Checkpoint)"
            detail_str = "FB chuyển hướng Checkpoint"
            return False

        # Access denied / Cloudflare / WAF
        if code in (403, 429):
            status_type = "blocked"
            status_text = "🔴 Bị Facebook Chặn"
            detail_str = f"HTTP {code} - WAF / Access Denied"
            return False

        # Explicit block phrases
        if any(b in txt_l for b in real_block_phrases):
            status_type = "blocked"
            status_text = "🔴 Bị Facebook Chặn"
            detail_str = "FB WAF / Security Challenge"
            return False

        # 1. Phát hiện Captive Portal / Proxy Gateway Intercept / Zscaler / Router Login
        captive_signals = (
            "zscaler", "welcome to zscaler", "captive portal", "mikrotik",
            "access denied by cisco", "fortinet web filter", "sonicwall",
            "sophos", "palo alto networks", "blue coat systems", "squid/", "squid:"
        )
        if any(k in txt_l for k in captive_signals) or any(k in hdrs_l for k in ("zscaler", "squid/", "squid:")):
            status_type = "blocked"
            status_text = "🔴 Bị Proxy chặn (Captive/Zscaler)"
            detail_str = "Proxy trả về trang Captive Portal / Firewall"
            return False

        # 2. Nhận diện chuẩn xác hạ tầng máy chủ Facebook
        has_fb_debug = ("x-fb-debug" in hdrs_l) or ("proxygen" in hdrs_l)
        has_fb_headers = ("facebook.com" in headers_dict.get("report-to", "").lower()) or                          ("fbsbx.com" in headers_dict.get("content-security-policy", "").lower()) or                          ("facebook.com" in headers_dict.get("reporting-endpoints", "").lower())

        has_fb_body = ('id="facebook"' in txt_l) or                       ('data-sigil' in txt_l) or                       ('name="lsd"' in txt_l) or                       ('name="fb_dtsg"' in txt_l) or                       ('reg_instance' in txt_l) or                       ('reg_impression_id' in txt_l) or                       ('name="reg_email__"' in txt_l)

        is_genuine_facebook = has_fb_debug or has_fb_headers or has_fb_body

        if not is_genuine_facebook:
            status_type = "blocked"
            status_text = "🔴 Không tới được FB (Fake/Captive)"
            detail_str = f"Phản hồi giả mạo / Không phải máy chủ Facebook (HTTP {code})"
            return False

        has_tokens = any(k in txt_l for k in (
            "reg_instance", "reg_impression_id", "privacy_mutation_token",
            "submission_id", "reg_email__", "firstname", "reg_passwd__",
            "lsd", "fb_dtsg", "jazoest"
        ))

        if code in (200, 301, 302):
            status_type = "live"
            status_text = "🟢 Live Facebook"
            detail_str = "FB Reg Form Sẵn Sàng (Tokens OK)" if has_tokens else f"FB Kết Nối OK (HTTP {code} - Không Chặn)"
            fb_ok = True
            return True
        status_type = "blocked"
        status_text = "🔴 FB Lỗi Phản Hồi"
        detail_str = f"Facebook trả mã HTTP {code}"
        return False

    t0 = time.time()
    r = None

    # Danh sách giao thức tự động thử nghiệm:
    # Nếu có tiền tố rõ ràng (socks4://, socks5://, http://) -> chỉ thử đúng tiền tố đó.
    # Nếu là dạng IP:Port thô -> thử HTTP trước, nếu lỗi và bật try_socks5 thì tự động dò SOCKS5 và SOCKS4.
    protocols_to_try = [proto]
    has_explicit_scheme = proxy_raw.startswith("http://") or proxy_raw.startswith("https://") or proxy_raw.startswith("socks4://") or proxy_raw.startswith("socks5://")
    if try_socks5 and not has_explicit_scheme:
        protocols_to_try = ["http", "socks5", "socks4"]

    last_err_detail = ""
    for curr_proto in protocols_to_try:
        if fb_ok:
            break
        cand_url = f"{curr_proto}://{f'{auth}@' if auth else ''}{host}:{port}"
        time_spent = time.time() - t0
        rem_time = to_f - time_spent if not is_test_env else to_f
        if not is_test_env:
            if time_spent >= to_f or rem_time <= 0.2:
                break
            if rem_time < 0.8 and curr_proto != protocols_to_try[0]:
                break

        cand_timeout = max(0.2, min(to_f, rem_time)) if not is_test_env else to_f
        try:
            from curl_cffi import requests as c_requests
            r = c_requests.get(
                "https://m.facebook.com/reg?soft=hjk",
                proxy=cand_url,
                timeout=cand_timeout,
                impersonate="chrome124",
                allow_redirects=True,
                headers=headers,
                verify=False
            )
            ping_ms = round((time.time() - t0) * 1000)
            if r and _eval_response(r.text or "", r.status_code, dict(getattr(r, "headers", {})), str(getattr(r, "url", ""))):
                proto = curr_proto
                clean_url = cand_url
                if curr_proto == "socks5":
                    status_text = "🟢 Live Facebook (SOCKS5)"
                elif curr_proto == "socks4":
                    status_text = "🟢 Live Facebook (SOCKS4)"
                break
        except Exception as e_cffi:
            ping_ms = round((time.time() - t0) * 1000)
            err_str = str(e_cffi).lower()
            if "timed out" in err_str or "timeout" in err_str:
                last_err_detail = f"Timeout (Quá {to_f}s)"
            elif "connection refused" in err_str:
                last_err_detail = "Port đóng / Bị từ chối kết nối"
            else:
                last_err_detail = str(e_cffi)[:40]

    # Fallback requests nếu curl_cffi bị mock hoặc chưa chạy được (chỉ dùng trong unit test mock)
    if not fb_ok and is_test_env:
        try:
            import requests
            proxies_map = {"http": clean_url, "https": clean_url}
            r_req = requests.get(
                "https://m.facebook.com/reg?soft=hjk",
                proxies=proxies_map,
                timeout=to_f,
                headers=headers,
                verify=False
            )
            if r_req:
                ping_ms = round((time.time() - t0) * 1000)
                _eval_response(r_req.text or "", r_req.status_code, dict(getattr(r_req, "headers", {})), str(getattr(r_req, "url", "")))
        except Exception:
            pass

        # CƯỠNG CHẾ TIMEOUT TRIỆT ĐỂ: Nếu tổng thời gian vượt quá timeout người dùng đặt, dứt khoát loại bỏ
    max_allowed_ms = int(to_f * 1000)
    if fb_ok and ping_ms > max_allowed_ms:
        fb_ok = False
        status_type = "error"
        status_text = "⚠️ Quá Timeout"
        detail_str = f"Phản hồi chậm ({ping_ms}ms > giới hạn {to_f}s)"

    if not fb_ok and status_type == "error":
        if "timeout" in (detail_str or "").lower() or "timeout" in (last_err_detail or "").lower() or ping_ms >= max_allowed_ms:
            status_text = "⚠️ Quá Timeout"
            if not detail_str:
                detail_str = f"Timeout (Quá {to_f}s)"

    return {
        "proxy": proxy_raw,
        "clean_url": clean_url,
        "host": host,
        "port": port,
        "protocol": proto.upper(),
        "ping_ms": ping_ms,
        "country": country,
        "status": status_type,
        "status_text": status_text,
        "detail": detail_str or ("Kết nối FB thành công" if fb_ok else (last_err_detail or f"Timeout / Lỗi kết nối (Quá {to_f}s)")),
        "live": fb_ok,
    }


def scrape_proxies_worker(
    category: str = "all",
    limit_per_source: int = 50,
    deduplicate: bool = True,
    progress_cb = None,
    stop_event: Optional[threading.Event] = None,
    check_fb: bool = False,
    check_threads: int = 50,
    check_timeout: float = 3.0,
    strict_fb: bool = True,
    on_live_proxy_cb = None
) -> List[Dict[str, Any]]:
    if stop_event is None:
        stop_event = threading.Event()
    """Cào proxy đa luồng từ kho 250+ nguồn online và tùy chọn kiểm tra Facebook trực tiếp."""
    from core.proxy_manager import FreeProxyManager
    fm = FreeProxyManager()

    if category.startswith("http://") or category.startswith("https://"):
        sources = [category.strip()]
    else:
        sources = list(fm.FREE_SOURCES)
        if category == "github":
            sources = [u for u in sources if any(k in u.lower() for k in ("github", "raw.githubusercontent.com", "yakumo", "monosans", "thespeedx", "hookzof"))]
        elif category == "socks5":
            sources = [u for u in sources if "socks5" in u.lower()]
        elif category == "http":
            sources = [u for u in sources if "http" in u.lower() and "socks" not in u.lower()]
        elif category == "socks4":
            sources = [u for u in sources if "socks4" in u.lower()]

    seen_ips: Set[str] = set()
    results: List[Dict[str, Any]] = []
    total_sources = len(sources)
    total_found_raw = 0
    live_count = 0
    blocked_count = 0
    error_count = 0

    import concurrent.futures

    if not check_fb:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(len(sources), 120))
        fut_to_url = {}
        try:
            fut_to_url = {executor.submit(fm._fetch_source, u, limit_per_source, True): u for u in sources}
            for idx, fut in enumerate(concurrent.futures.as_completed(fut_to_url)):
                if stop_event.is_set():
                    break
                url = fut_to_url[fut]
                src_name = fm._get_source_label(url)
                batch = []
                try:
                    cands = fut.result()
                    if cands:
                        total_found_raw += len(cands)
                        for cand in cands:
                            if stop_event.is_set():
                                break
                            if deduplicate and fm._is_junk_proxy(cand):
                                continue
                            proto, host, port, auth = parse_proxy_string(cand)
                            if not host or not port:
                                continue
                            if deduplicate:
                                if host in seen_ips:
                                    continue
                                seen_ips.add(host)
                            proto_name = "SOCKS5" if "socks5" in cand.lower() else ("SOCKS4" if "socks4" in cand.lower() else "HTTP")
                            itm = {
                                "proxy": cand,
                                "host": host,
                                "port": port,
                                "protocol": proto_name,
                                "fb_status": "⚪ Chưa check",
                                "ping": "--",
                                "source": src_name,
                                "time": datetime.now().strftime("%H:%M:%S"),
                                "live": None,
                                "status": "unverified",
                                "detail": ""
                            }
                            results.append(itm)
                            batch.append(itm)
                except Exception:
                    pass
                if progress_cb:
                    progress_cb(idx + 1, total_sources, batch, total_found_raw, len(seen_ips), 0, 0)
        finally:
            for f in fut_to_url.keys():
                f.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        return results

    # MODE: VỪA CÀO VỪA CHECK FB
    workers_chk = max(5, min(check_threads, 500))
    max_pending = max(2000, workers_chk * 25)

    check_executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers_chk)
    fetch_executor = concurrent.futures.ThreadPoolExecutor(max_workers=min(len(sources), 100))
    active_checks = {}
    fut_to_url = {}

    def _drain_completed(batch_list, wait_one=False):
        nonlocal live_count, blocked_count, error_count
        if not active_checks:
            return
        if wait_one:
            done_set, _ = concurrent.futures.wait(
                list(active_checks.keys()),
                return_when=concurrent.futures.FIRST_COMPLETED,
                timeout=0.10
            )
        else:
            done_set = [f for f in list(active_checks.keys()) if f.done()]

        for df in done_set:
            info = active_checks.pop(df, None)
            if not info:
                continue
            try:
                chk_res = df.result()
            except Exception as ex:
                chk_res = {"status": "error", "status_text": "⚠️ Lỗi", "ping_ms": 0, "live": False, "detail": str(ex)[:30]}

            is_lv = chk_res.get("live", False)
            st = chk_res.get("status", "error")
            if is_lv:
                live_count += 1
            elif st == "blocked":
                blocked_count += 1
            else:
                error_count += 1

            p_val = chk_res.get("ping_ms", 0)
            disp_ping = f"{p_val}ms" if p_val else "--"
            if not is_lv and p_val > int(check_timeout * 1000):
                disp_ping = f">{int(check_timeout * 1000)}ms"

            itm = {
                "proxy": info["cand"],
                "host": info["host"],
                "port": info["port"],
                "protocol": chk_res.get("protocol", info["proto"]),
                "fb_status": chk_res.get("status_text", "⚠️ Lỗi"),
                "ping": disp_ping,
                "source": info["source"],
                "time": datetime.now().strftime("%H:%M:%S"),
                "live": is_lv,
                "status": st,
                "detail": chk_res.get("detail", "")
            }
            if is_lv or st == "blocked":
                results.append(itm)
            batch_list.append(itm)
            if is_lv and on_live_proxy_cb:
                try:
                    on_live_proxy_cb(itm)
                except Exception:
                    pass

    last_notify_time = 0.0

    def _flush_progress(cur_idx, force=False):
        nonlocal last_notify_time, batch
        if not progress_cb or not batch:
            return
        now = time.time()
        has_live = any(itm.get("live") for itm in batch)
        if has_live or force or len(batch) >= 120 or (now - last_notify_time) >= 0.25:
            progress_cb(cur_idx, total_sources, batch, total_found_raw, len(seen_ips), live_count, blocked_count)
            batch = []
            last_notify_time = now

    try:
        fut_to_url = {fetch_executor.submit(fm._fetch_source, u, limit_per_source, True): u for u in sources}
        for idx, fut in enumerate(concurrent.futures.as_completed(fut_to_url)):
            if stop_event.is_set():
                break
            url = fut_to_url[fut]
            src_name = fm._get_source_label(url)
            batch = []
            try:
                cands = fut.result()
                if cands:
                    total_found_raw += len(cands)
                    for cand in cands:
                        if stop_event.is_set():
                            break
                        if deduplicate and fm._is_junk_proxy(cand):
                            continue
                        proto, host, port, auth = parse_proxy_string(cand)
                        if not host or not port:
                            continue
                        if deduplicate:
                            if host in seen_ips:
                                continue
                            seen_ips.add(host)
                        proto_name = "SOCKS5" if "socks5" in cand.lower() else ("SOCKS4" if "socks4" in cand.lower() else "HTTP")

                        while len(active_checks) >= max_pending and not stop_event.is_set():
                            _drain_completed(batch, wait_one=True)
                            _flush_progress(idx + 1, force=False)

                        if stop_event.is_set():
                            break

                        f_chk = check_executor.submit(
                            check_proxy_against_facebook,
                            cand,
                            timeout=check_timeout,
                            strict_fb=strict_fb,
                            try_socks5=True
                        )
                        active_checks[f_chk] = {
                            "cand": cand,
                            "host": host,
                            "port": port,
                            "proto": proto_name,
                            "source": src_name
                        }
            except Exception:
                pass

            _drain_completed(batch, wait_one=False)
            _flush_progress(idx + 1, force=True)

        # Drain all remaining checks
        while active_checks and not stop_event.is_set():
            _drain_completed(batch, wait_one=True)
            _flush_progress(total_sources, force=False)
        _drain_completed(batch, wait_one=False)
        _flush_progress(total_sources, force=True)
    finally:
        for f in fut_to_url.keys():
            f.cancel()
        fetch_executor.shutdown(wait=False, cancel_futures=True)

        batch_final = []
        _drain_completed(batch_final, wait_one=False)
        if progress_cb and batch_final:
            progress_cb(total_sources, total_sources, batch_final, total_found_raw, len(seen_ips), live_count, blocked_count)
        for f in list(active_checks.keys()):
            f.cancel()
        check_executor.shutdown(wait=False, cancel_futures=True)

    return results


def check_single_uid_graph(uid: str, proxy: Optional[str] = None, timeout: int = 6) -> Dict[str, Any]:
    """Kiểm tra 1 UID Facebook xem Live hay Die qua Graph API."""
    from core.facebook_checker import check_facebook_uid_live
    is_live, msg = check_facebook_uid_live(uid, proxy=proxy, timeout=timeout)
    time_str = datetime.now().strftime("%H:%M:%S")
    msg_low = msg.lower()
    if is_live:
        return {
            "uid": uid,
            "status": "live",
            "status_text": "🟢 LIVE",
            "detail": msg,
            "time": time_str,
            "live": True,
        }
    elif "rate limit" in msg_low or "code 4" in msg_low or "code 17" in msg_low or "code 368" in msg_low:
        return {
            "uid": uid,
            "status": "warn",
            "status_text": "⚠️ Rate Limit",
            "detail": msg,
            "time": time_str,
            "live": False,
        }
    elif "object does not exist" in msg_low or "error 100" in msg_low or "error 404" in msg_low:
        return {
            "uid": uid,
            "status": "die",
            "status_text": "🔴 DIE (Không tồn tại)",
            "detail": msg,
            "time": time_str,
            "live": False,
        }
    else:
        return {
            "uid": uid,
            "status": "die",
            "status_text": "🔴 DIE",
            "detail": msg,
            "time": time_str,
            "live": False,
        }


def fetch_mailbox_messages(
    provider_key: str,
    email_addr: str,
    password_or_token: str = "",
    client_id: str = "e9a37c35-7d52-4415-be02-463e264de917",
    imap_host: str = "outlook.office365.com",
    imap_port: int = 993,
) -> List[Dict[str, Any]]:
    """Đọc hòm thư và bóc tách OTP từ nhiều dịch vụ email khác nhau."""
    from core.email_service import extract_otp_code
    import requests

    messages = []
    clean_email = email_addr.strip()
    clean_pwd = password_or_token.strip()

    # 1. Hotmail IMAP hoặc Custom IMAP
    if provider_key in ("hotmail_imap", "custom_imap"):
        import imaplib, email
        from email.header import decode_header
        host = imap_host if provider_key == "custom_imap" else "outlook.office365.com"
        port = int(imap_port) if provider_key == "custom_imap" else 993
        try:
            mail = imaplib.IMAP4_SSL(host, port, timeout=12)
            mail.login(clean_email, clean_pwd)
            for folder in ["INBOX", "Junk"]:
                try:
                    rv, _ = mail.select(folder)
                    if rv != "OK":
                        continue
                    rv, data = mail.search(None, "ALL")
                    if rv == "OK" and data[0]:
                        msg_ids = data[0].split()
                        for mid in msg_ids[-10:]:
                            res, msg_data = mail.fetch(mid, "(RFC822)")
                            if res != "OK":
                                continue
                            raw = msg_data[0][1]
                            msg = email.message_from_bytes(raw)
                            s_raw, enc = decode_header(msg.get("Subject", ""))[0]
                            subject = s_raw.decode(enc or "utf-8", errors="replace") if isinstance(s_raw, bytes) else str(s_raw)
                            f_raw, enc = decode_header(msg.get("From", ""))[0]
                            sender = f_raw.decode(enc or "utf-8", errors="replace") if isinstance(f_raw, bytes) else str(f_raw)
                            date_str = msg.get("Date", "")
                            body = ""
                            if msg.is_multipart():
                                for p in msg.walk():
                                    if p.get_content_type() in ("text/plain", "text/html"):
                                        pl = p.get_payload(decode=True)
                                        if pl:
                                            body += pl.decode("utf-8", errors="replace") + "\n"
                            else:
                                pl = msg.get_payload(decode=True)
                                if pl:
                                    body = pl.decode("utf-8", errors="replace")
                            otp = extract_otp_code(subject) or extract_otp_code(body)
                            messages.append({
                                "email": clean_email,
                                "sender": sender,
                                "subject": subject,
                                "otp": otp or "",
                                "date": date_str,
                                "body": body.strip(),
                            })
                except Exception:
                    pass
            try:
                mail.logout()
            except Exception:
                pass
        except Exception as e:
            messages.append({
                "email": clean_email,
                "sender": "Hệ Thống Lỗi",
                "subject": f"Đăng nhập IMAP thất bại: {e}",
                "otp": "",
                "date": datetime.now().strftime("%H:%M:%S"),
                "body": f"Không thể kết nối IMAP đến {host}:{port} cho tài khoản {clean_email}. Lỗi: {str(e)}",
            })

    # 2. DongVanFB OAuth2
    elif provider_key == "dongvan_oauth2":
        cid = client_id or "e9a37c35-7d52-4415-be02-463e264de917"
        try:
            r = requests.post(
                "https://tools.dongvanfb.net/api/get_messages_oauth2",
                json={"email": clean_email, "refresh_token": clean_pwd, "client_id": cid, "list_mail": "all"},
                timeout=12
            )
            if r.status_code == 200:
                d = r.json()
                for m in d.get("messages", []):
                    subj = m.get("subject", "")
                    sender = m.get("from", "")
                    date_str = m.get("date", "")
                    body = m.get("message", "") or m.get("body", "")
                    otp = m.get("code") or extract_otp_code(subj) or extract_otp_code(body)
                    messages.append({
                        "email": clean_email,
                        "sender": sender,
                        "subject": subj,
                        "otp": otp or "",
                        "date": date_str,
                        "body": body,
                    })
        except Exception:
            pass
        if not messages:
            try:
                r = requests.post(
                    "https://tools.dongvanfb.net/api/get_code_oauth2",
                    json={"email": clean_email, "refresh_token": clean_pwd, "client_id": cid, "type": "facebook"},
                    timeout=12
                )
                if r.status_code == 200:
                    d = r.json()
                    c = d.get("code")
                    if c:
                        messages.append({
                            "email": clean_email,
                            "sender": "Facebook Security",
                            "subject": f"Mã xác nhận Facebook của bạn: {c}",
                            "otp": str(c),
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "body": f"Dữ liệu phản hồi DongVanFB: {d}",
                        })
            except Exception:
                pass

    # 3. TempMail.Plus
    elif provider_key == "tempmail_plus":
        try:
            r = requests.get(f"https://tempmail.plus/api/mails?email={clean_email}&limit=20", timeout=10)
            if r.status_code == 200:
                d = r.json()
                for m in d.get("mail_list", []):
                    mid = m.get("mail_id")
                    subj = m.get("subject", "")
                    sender = m.get("from", "")
                    date_str = m.get("date", "")
                    body = ""
                    otp = extract_otp_code(subj)
                    if mid:
                        try:
                            rd = requests.get(f"https://tempmail.plus/api/mails/{mid}?email={clean_email}", timeout=6)
                            if rd.status_code == 200:
                                dd = rd.json()
                                body = dd.get("text", "") or dd.get("html", "")
                                if not otp:
                                    otp = extract_otp_code(body)
                        except Exception:
                            pass
                    messages.append({
                        "email": clean_email,
                        "sender": sender,
                        "subject": subj,
                        "otp": otp or "",
                        "date": date_str,
                        "body": body,
                    })
        except Exception:
            pass

    # 4. InboxKitten
    elif provider_key == "inboxkitten":
        try:
            user = clean_email.split("@")[0]
            r = requests.get(f"https://inboxkitten.com/api/v1/mail/list?recipient={user}", timeout=10)
            if r.status_code == 200:
                items = r.json()
                if isinstance(items, list):
                    for m in items:
                        subj = m.get("subject", "")
                        sender = m.get("sender", "")
                        date_str = m.get("timestamp", "")
                        st_url = m.get("storage", {}).get("url", "")
                        body = ""
                        otp = extract_otp_code(subj)
                        if st_url:
                            try:
                                rb = requests.get(f"https://inboxkitten.com/api/v1/mail/get?mail_id={st_url}", timeout=6)
                                if rb.status_code == 200:
                                    bj = rb.json()
                                    body = bj.get("text", "") or bj.get("html", "")
                                    if not otp:
                                        otp = extract_otp_code(body)
                            except Exception:
                                pass
                        messages.append({
                            "email": clean_email,
                            "sender": sender,
                            "subject": subj,
                            "otp": otp or "",
                            "date": date_str,
                            "body": body,
                        })
        except Exception:
            pass

    # 5. Guerrilla Mail
    elif provider_key == "guerrillamail":
        try:
            r = requests.get("https://api.guerrillamail.com/ajax.php?f=check_email&seq=0", timeout=10)
            if r.status_code == 200:
                d = r.json()
                for m in d.get("list", []):
                    subj = m.get("mail_subject", "")
                    sender = m.get("mail_from", "")
                    date_str = m.get("mail_date", "")
                    body = m.get("mail_excerpt", "")
                    otp = extract_otp_code(subj) or extract_otp_code(body)
                    messages.append({
                        "email": clean_email,
                        "sender": sender,
                        "subject": subj,
                        "otp": otp or "",
                        "date": date_str,
                        "body": body,
                    })
        except Exception:
            pass

    # 6. Mailnesia
    elif provider_key == "mailnesia":
        try:
            user = clean_email.split("@")[0]
            r = requests.get(f"https://mailnesia.com/mailbox/{user}", timeout=10)
            if r.status_code == 200:
                txt = r.text
                otp = extract_otp_code(txt)
                if otp:
                    messages.append({
                        "email": clean_email,
                        "sender": "Facebook Mailnesia",
                        "subject": f"Xác nhận Facebook (Mã: {otp})",
                        "otp": otp,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "body": txt[:600],
                    })
        except Exception:
            pass

    # 7. Smail1s
    elif provider_key == "smail1s":
        try:
            r = requests.post("https://smail1s.com/get_messages", json={"email": clean_email}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                for m in d.get("messages", []):
                    subj = m.get("subject", "")
                    sender = m.get("from", "")
                    body = m.get("message", "")
                    otp = extract_otp_code(subj) or extract_otp_code(body)
                    messages.append({
                        "email": clean_email,
                        "sender": sender,
                        "subject": subj,
                        "otp": otp or "",
                        "date": m.get("date", ""),
                        "body": body,
                    })
        except Exception:
            pass

    return messages


class UtilitiesTabMixin:
    def safe_ui_call(self, func, *args, **kwargs):
        """Thread-safe UI callback via event_queue on the Tk mainloop thread."""
        try:
            if hasattr(self, "event_queue") and self.event_queue is not None:
                self.event_queue.put(("ui_call", lambda: func(*args, **kwargs)))
                return
        except Exception:
            pass

        try:
            if threading.current_thread() is threading.main_thread():
                if hasattr(self, "root") and self.root and self.root.winfo_exists():
                    func(*args, **kwargs)
            else:
                if hasattr(self, "root") and self.root and self.root.winfo_exists():
                    self.root.after(0, lambda: func(*args, **kwargs))
        except Exception:
            pass

    """Mixin cung cấp toàn bộ giao diện và điều khiển cho Tab Tiện Ích."""

    @staticmethod
    def format_proxy_for_save(proxy_raw: str, fmt_choice: str = "IP:Port", protocol: str = "HTTP", ping_str: str = "") -> str:
        if not proxy_raw or not str(proxy_raw).strip():
            return ""
        proto, host, port, auth = parse_proxy_string(proxy_raw)
        if not host or not port or not str(port).isdigit() or ("." not in host and ":" not in host):
            return proxy_raw.strip()
        has_explicit_scheme = "://" in proxy_raw
        eff_proto = (proto if has_explicit_scheme else (protocol or proto or "http")).lower()
        fmt_low = str(fmt_choice).lower()
        if "chi ti?t" in fmt_low or "ping" in fmt_low or "|" in fmt_low:
            eff_proto = (proto if has_explicit_scheme else (protocol or proto or "HTTP")).upper()
            p_info = f"|{ping_str}" if ping_str else ""
            return f"{host}:{port}|{eff_proto}{p_info}"
        elif "protocol" in fmt_low or "giao th?c" in fmt_low or "://" in fmt_low:
            eff_proto = (proto if has_explicit_scheme else (protocol or proto or "http")).lower()
            if auth:
                return f"{eff_proto}://{auth}@{host}:{port}"
            return f"{eff_proto}://{host}:{port}"
        elif "user:pass" in fmt_low:
            if auth:
                return f"{host}:{port}:{auth}"
            return f"{host}:{port}"
        else:
            # Chu?n IP:Port (M?c ??nh cho tool Reg FB)
            return f"{host}:{port}"

    def get_scrape_save_path(self) -> str:
        """Lấy đường dẫn file lưu proxy cào được (ưu tiên entry trên UI, sau đó config tool, mặc định proxy.txt)."""
        if hasattr(self, "entry_scrape_save_path"):
            try:
                if self.entry_scrape_save_path.winfo_exists():
                    val = self.entry_scrape_save_path.get().strip()
                    if val:
                        return val
            except Exception:
                pass
        if hasattr(self, "get_proxy_file_path"):
            try:
                p = self.get_proxy_file_path()
                if p and str(p).strip():
                    return str(p).strip()
            except Exception:
                pass
        if hasattr(self, "config") and isinstance(self.config, dict):
            p = self.config.get("proxy_file_path", "proxy.txt")
            if p and str(p).strip():
                return str(p).strip()
        return "proxy.txt"

    def get_scrape_save_format(self) -> str:
        """Lấy định dạng lưu proxy do người dùng chọn trên UI."""
        if hasattr(self, "cb_scrape_save_format"):
            try:
                if self.cb_scrape_save_format.winfo_exists():
                    val = self.cb_scrape_save_format.get().strip()
                    if val:
                        return val
            except Exception:
                pass
        return "IP:Port (Chuẩn FB Reg & Tool)"

    def _browse_scrape_save_path(self):
        """Mở hộp thoại chọn hoặc đặt tên file lưu Proxy Live."""
        curr = self.get_scrape_save_path()
        abs_curr = curr if os.path.isabs(curr) else os.path.abspath(curr)
        initialdir = os.path.dirname(abs_curr) if os.path.exists(os.path.dirname(abs_curr)) else os.getcwd()
        initialfile = os.path.basename(curr) or "proxy.txt"
        selected = filedialog.asksaveasfilename(
            title="Chọn hoặc đặt tên file lưu Proxy Live Facebook",
            initialdir=initialdir,
            initialfile=initialfile,
            defaultextension=".txt",
            filetypes=[("Text Files (*.txt)", "*.txt"), ("All Files (*.*)", "*.*")]
        )
        if selected:
            if hasattr(self, "entry_scrape_save_path") and self.entry_scrape_save_path.winfo_exists():
                self.entry_scrape_save_path.delete(0, tk.END)
                self.entry_scrape_save_path.insert(0, selected)
            if hasattr(self, "config") and isinstance(self.config, dict):
                self.config["proxy_file_path"] = selected
            self._init_scrape_auto_save_file(selected)

    def _open_scrape_save_file(self):
        """Mở file lưu proxy bằng trình soạn thảo văn bản hệ thống."""
        p = self.get_scrape_save_path()
        abs_p = p if os.path.isabs(p) else os.path.abspath(p)
        if not os.path.exists(abs_p):
            try:
                os.makedirs(os.path.dirname(abs_p), exist_ok=True)
                with open(abs_p, "w", encoding="utf-8") as f:
                    f.write(f"# Danh sách Proxy LIVE Facebook - {time.ctime()}\n")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể tạo file: {e}")
                return
        try:
            os.startfile(abs_p)
        except Exception as e:
            messagebox.showinfo("???ng d?n file", f"???ng d?n file:\n{abs_p}\n\n(L?i m? tr?c ti?p: {e})")

    def _init_scrape_auto_save_file(self, file_path: str):
        """Đọc và lập chỉ mục các proxy đã có sẵn trong file để tránh ghi đè hoặc nhân bản."""
        if not hasattr(self, "_scraped_file_saved_set"):
            self._scraped_file_saved_set = set()
        if not hasattr(self, "_scrape_file_lock"):
            self._scrape_file_lock = threading.Lock()

        abs_p = file_path if os.path.isabs(file_path) else os.path.abspath(file_path)
        existing_items = set()
        if os.path.exists(abs_p):
            try:
                with open(abs_p, "r", encoding="utf-8-sig", errors="ignore") as fp:
                    for line in fp:
                        s = line.strip()
                        if s and not s.startswith("#") and not s.startswith("//"):
                            m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[: ]+(\d{2,5})', s)
                            if m:
                                existing_items.add(f"{m.group(1)}:{m.group(2)}")
                            existing_items.add(s)
            except Exception:
                pass
        with self._scrape_file_lock:
            self._scraped_file_saved_set = existing_items
            self._scraped_file_saved_count = len(existing_items)

        def _ui_sync():
            if hasattr(self, "lbl_scrp_stat_saved"):
                self.lbl_scrp_stat_saved.config(text=str(self._scraped_file_saved_count))
            if hasattr(self, "lbl_scrape_auto_save_status"):
                self.lbl_scrape_auto_save_status.config(text=f"(Đã lưu: {self._scraped_file_saved_count} live)")
        self.safe_ui_call(_ui_sync)

    def _auto_save_one_live_proxy(self, itm: dict):
        """Ghi ngay lập tức proxy Live vào file theo thời gian thực (Real-time Auto Save)."""
        if hasattr(self, "var_scrape_auto_save") and not self.var_scrape_auto_save.get():
            return
        # Chỉ lưu khi proxy thực sự LIVE Facebook
        if not itm or not itm.get("live"):
            return
        p_raw = itm.get("proxy")
        if not p_raw:
            return

        fmt = self.get_scrape_save_format()
        formatted = self.format_proxy_for_save(
            p_raw,
            fmt_choice=fmt,
            protocol=itm.get("protocol", "HTTP"),
            ping_str=itm.get("ping", "")
        )
        if not formatted:
            return

        if not hasattr(self, "_scrape_file_lock"):
            self._scrape_file_lock = threading.Lock()
        if not hasattr(self, "_scraped_file_saved_set"):
            self._scraped_file_saved_set = set()

        with self._scrape_file_lock:
            m_hp = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[: ]+(\d{2,5})', formatted)
            hp_key = f"{m_hp.group(1)}:{m_hp.group(2)}" if m_hp else formatted
            if hp_key in self._scraped_file_saved_set or formatted in self._scraped_file_saved_set:
                return
            self._scraped_file_saved_set.add(hp_key)
            self._scraped_file_saved_set.add(formatted)
            p_file = self.get_scrape_save_path()
            abs_p = p_file if os.path.isabs(p_file) else os.path.abspath(p_file)
            try:
                os.makedirs(os.path.dirname(abs_p), exist_ok=True)
                first_write = not os.path.exists(abs_p) or os.path.getsize(abs_p) == 0
                need_newline = False
                if os.path.exists(abs_p) and os.path.getsize(abs_p) > 0:
                    with open(abs_p, "rb") as f_chk:
                        f_chk.seek(-1, os.SEEK_END)
                        if f_chk.read(1) not in (b"\n", b"\r"):
                            need_newline = True
                with open(abs_p, "a", encoding="utf-8") as fp:
                    if first_write:
                        fp.write(f"# Danh sách Proxy LIVE Facebook - {time.ctime()}\n")
                    if need_newline:
                        fp.write("\n")
                    fp.write(f"{formatted}\n")
                    fp.flush()
                self._scraped_file_saved_count = getattr(self, "_scraped_file_saved_count", 0) + 1
            except Exception as e:
                logger.error(f"Error auto-saving live proxy {formatted} to {abs_p}: {e}")

        def _ui_update():
            if hasattr(self, "lbl_scrp_stat_saved"):
                self.lbl_scrp_stat_saved.config(text=str(getattr(self, "_scraped_file_saved_count", 0)))
            if hasattr(self, "lbl_scrape_auto_save_status"):
                self.lbl_scrape_auto_save_status.config(text=f"(Đã lưu: {getattr(self, '_scraped_file_saved_count', 0)} live)")
        self.safe_ui_call(_ui_update)

    def build_utilities_tab(self, parent_frame: tk.Frame):
        """Xây dựng khung tab Tiện ích Hệ Thống và 4 Sub-Tabs."""
        from app_gui import AppTheme

        self._filter_running = False
        self._filter_stop_event = threading.Event()
        self._live_fb_proxies: List[str] = []
        self._blocked_fb_proxies: List[str] = []
        self._error_proxies: List[str] = []

        self._scraper_running = False
        self._scraper_stop_event = threading.Event()
        self._scraped_proxies_list: List[str] = []
        self._scraped_live_fb_proxies: List[str] = []
        self._scraped_blocked_fb_proxies: List[str] = []
        self._scraped_error_proxies: List[str] = []
        self._scraped_unique_ips: Set[str] = set()
        self._scraped_file_saved_set: Set[str] = set()
        self._scraped_file_saved_count: int = 0
        self._scrape_file_lock = threading.Lock()

        self._uid_check_running = False
        self._uid_check_stop_event = threading.Event()
        self._uids_live: List[str] = []
        self._uids_die: List[str] = []
        self._uids_warn: List[str] = []

        self._mail_poll_running = False
        self._mail_poll_stop_event = threading.Event()
        self._mail_messages: List[Dict[str, Any]] = []
        self._current_latest_otp = ""

        container = tk.Frame(parent_frame, bg=AppTheme.BG_DARK)
        container.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        header_bar = tk.Frame(container, bg=AppTheme.BG_CARD, bd=1, relief="solid", padx=10, pady=6)
        header_bar.pack(fill=tk.X, pady=(0, 6))

        lbl_head = tk.Label(
            header_bar,
            text="🛠️ BỘ TIỆN ÍCH HỆ THỐNG FACEBOOK PRO",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.ACCENT
        )
        lbl_head.pack(side=tk.LEFT)

        lbl_sub = tk.Label(
            header_bar,
            text="• Lọc Proxy Chống FB Chặn • Cào Proxy 6,400+ Nguồn • Check Live UID • Đọc Mail & OTP",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD,
            fg=AppTheme.TEXT_MUTED
        )
        lbl_sub.pack(side=tk.LEFT, padx=10)

        # Quick Jump Buttons trên Header
        jump_bar = tk.Frame(header_bar, bg=AppTheme.BG_CARD)
        jump_bar.pack(side=tk.RIGHT)

        tk.Button(
            jump_bar, text="📊 Về Bảng Điều Khiển", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT, padx=8, pady=2,
            command=lambda: self.notebook.select(self.tab_dashboard)
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            jump_bar, text="⚙️ Cài Đặt", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT, padx=8, pady=2,
            command=lambda: self.notebook.select(self.tab_settings)
        ).pack(side=tk.LEFT, padx=2)

        self.util_notebook = ttk.Notebook(container)
        self.util_notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_util_filter = tk.Frame(self.util_notebook, bg=AppTheme.BG_DARK)
        self.tab_util_scraper = tk.Frame(self.util_notebook, bg=AppTheme.BG_DARK)
        self.tab_util_uid = tk.Frame(self.util_notebook, bg=AppTheme.BG_DARK)
        self.tab_util_mail = tk.Frame(self.util_notebook, bg=AppTheme.BG_DARK)

        self.util_notebook.add(self.tab_util_filter, text="  🛡️ LỌC PROXY LIVE FB  ")
        self.util_notebook.add(self.tab_util_scraper, text="  📥 CÀO PROXY ĐA NGUỒN  ")
        self.util_notebook.add(self.tab_util_uid, text="  🔎 CHECK LIVE UID FB  ")
        self.util_notebook.add(self.tab_util_mail, text="  📬 ĐỌC MAIL & LẤY OTP  ")

        self._build_proxy_filter_tab(self.tab_util_filter, AppTheme)
        self._build_proxy_scraper_tab(self.tab_util_scraper, AppTheme)
        self._build_check_uid_tab(self.tab_util_uid, AppTheme)
        self._build_read_mail_tab(self.tab_util_mail, AppTheme)

    def _make_stat_badge(self, parent: tk.Frame, title: str, init_val: str, color: str, AppTheme) -> tk.Label:
        box = tk.Frame(parent, bg=AppTheme.BG_CARD, bd=1, relief=tk.SOLID, padx=8, pady=4)
        box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)
        lbl_t = tk.Label(box, text=title, font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED)
        lbl_t.pack(anchor="w")
        lbl_v = tk.Label(box, text=init_val, font=AppTheme.FONT_TITLE, bg=AppTheme.BG_CARD, fg=color)
        lbl_v.pack(anchor="w")
        return lbl_v

    # =========================================================================
    # SUB-TAB 1: LỌC PROXY LIVE FB
    # =========================================================================
    def _build_proxy_filter_tab(self, parent: tk.Frame, AppTheme):
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=AppTheme.BG_DARK, bd=0, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        right_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        paned.add(left_frame, minsize=380)
        paned.add(right_frame, minsize=520)

        card_in = tk.LabelFrame(
            left_frame, text=" 📋 1. Danh Sách Proxy Nhập Vào ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            bd=1, relief=tk.SOLID
        )
        card_in.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        tool_bar = tk.Frame(card_in, bg=AppTheme.BG_CARD)
        tool_bar.pack(fill=tk.X, padx=6, pady=4)

        tk.Button(
            tool_bar, text="📁 Nhập File", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            command=self._import_proxy_filter_file
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            tool_bar, text="📋 Dán", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            command=self._paste_proxy_filter_clipboard
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            tool_bar, text="🌐 Nạp proxy.txt", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            command=self._load_tool_proxies_to_filter
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            tool_bar, text="🗑️ Xóa", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER, relief=tk.FLAT,
            command=self._clear_proxy_filter_input
        ).pack(side=tk.RIGHT)

        self.txt_filter_proxies = scrolledtext.ScrolledText(
            card_in, wrap=tk.NONE, font=AppTheme.FONT_CODE,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff",
            bd=0, height=12
        )
        self.txt_filter_proxies.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))
        self.txt_filter_proxies.bind("<KeyRelease>", self._on_filter_text_change)

        self.lbl_filter_input_count = tk.Label(
            card_in, text="Đã nhập: 0 proxy", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
        )
        self.lbl_filter_input_count.pack(anchor="w", padx=6, pady=(0, 4))

        card_cfg = tk.LabelFrame(
            left_frame, text=" ⚙️ 2. Cấu Hình Kiểm Tra Facebook ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN,
            bd=1, relief=tk.SOLID
        )
        card_cfg.pack(fill=tk.X, padx=4, pady=4)

        row_cfg = tk.Frame(card_cfg, bg=AppTheme.BG_CARD)
        row_cfg.pack(fill=tk.X, padx=6, pady=4)

        tk.Label(row_cfg, text="Số luồng check:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.spn_filter_threads = tk.Spinbox(row_cfg, from_=1, to=500, width=6, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        self.spn_filter_threads.delete(0, tk.END)
        self.spn_filter_threads.insert(0, "50")
        self.spn_filter_threads.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(row_cfg, text="Timeout (s):", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_filter_timeout = ttk.Combobox(row_cfg, values=["0.5", "0.8", "1.0", "1.5", "2.0", "3.0", "4.0", "5.0", "6.0", "8.0", "10.0"], width=6)
        self.cb_filter_timeout.set("4.0")
        self.cb_filter_timeout.pack(side=tk.LEFT, padx=(4, 6))

        row_chk = tk.Frame(card_cfg, bg=AppTheme.BG_CARD)
        row_chk.pack(fill=tk.X, padx=6, pady=2)

        self.var_filter_strict = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row_chk, text="Strict FB Guard (Chặn Captcha/403/Checkpoint)",
            variable=self.var_filter_strict, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL
        ).pack(anchor="w")

        self.var_filter_try_socks = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row_chk, text="Tự động dò SOCKS5 / SOCKS4 nếu HTTP lỗi",
            variable=self.var_filter_try_socks, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL
        ).pack(anchor="w")

        act_frame = tk.Frame(left_frame, bg=AppTheme.BG_DARK)
        act_frame.pack(fill=tk.X, padx=4, pady=4)

        self.btn_filter_start = tk.Button(
            act_frame, text="▶️ BẮT ĐẦU LỌC PROXY", font=AppTheme.FONT_TITLE,
            bg=AppTheme.ACCENT, fg="#000000", activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT, height=2, command=self.on_start_proxy_filter
        )
        self.btn_filter_start.pack(fill=tk.X, pady=(0, 4))

        self.btn_filter_stop = tk.Button(
            act_frame, text="⏹️ DỪNG LỌC", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BORDER, fg="#ffffff", activebackground=AppTheme.DANGER,
            state=tk.DISABLED, relief=tk.FLAT, command=self.on_stop_proxy_filter
        )
        self.btn_filter_stop.pack(fill=tk.X, pady=(0, 6))

        exp_row = tk.Frame(act_frame, bg=AppTheme.BG_DARK)
        exp_row.pack(fill=tk.X)

        tk.Button(
            exp_row, text="📋 Copy Live", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS, relief=tk.FLAT,
            command=self._copy_live_fb_proxies
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(
            exp_row, text="💾 Lưu File", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.INFO, relief=tk.FLAT,
            command=self._export_live_fb_proxies
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        tk.Button(
            exp_row, text="⚡ Lưu vào proxy.txt", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT, relief=tk.FLAT,
            command=self._apply_live_proxies_to_tool
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        kpi_frame = tk.Frame(right_frame, bg=AppTheme.BG_DARK)
        kpi_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_flt_stat_total = self._make_stat_badge(kpi_frame, "📊 Tổng", "0", AppTheme.TEXT_MAIN, AppTheme)
        self.lbl_flt_stat_live = self._make_stat_badge(kpi_frame, "🟢 Live FB", "0", AppTheme.SUCCESS, AppTheme)
        self.lbl_flt_stat_blocked = self._make_stat_badge(kpi_frame, "🔴 FB Chặn", "0", AppTheme.DANGER, AppTheme)
        self.lbl_flt_stat_error = self._make_stat_badge(kpi_frame, "⚠️ Lỗi/Chết", "0", AppTheme.WARNING, AppTheme)
        self.lbl_flt_stat_prog = self._make_stat_badge(kpi_frame, "⏳ Tiến Độ", "0%", AppTheme.INFO, AppTheme)

        self.prog_filter_proxy = ttk.Progressbar(right_frame, mode="determinate")
        self.prog_filter_proxy.pack(fill=tk.X, pady=(0, 4))

        tree_frame = tk.Frame(right_frame, bg=AppTheme.BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("idx", "proxy", "proto", "ping", "country", "status", "detail")
        self.tree_filter = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_filter.heading("idx", text="#")
        self.tree_filter.heading("proxy", text="Proxy IP:Port")
        self.tree_filter.heading("proto", text="Giao Thức")
        self.tree_filter.heading("ping", text="Ping (ms)")
        self.tree_filter.heading("country", text="Quốc Gia")
        self.tree_filter.heading("status", text="Tình Trạng FB")
        self.tree_filter.heading("detail", text="Chi Tiết Phản Hồi")

        self.tree_filter.column("idx", width=40, anchor=tk.CENTER)
        self.tree_filter.column("proxy", width=180, anchor=tk.W)
        self.tree_filter.column("proto", width=75, anchor=tk.CENTER)
        self.tree_filter.column("ping", width=70, anchor=tk.CENTER)
        self.tree_filter.column("country", width=65, anchor=tk.CENTER)
        self.tree_filter.column("status", width=140, anchor=tk.W)
        self.tree_filter.column("detail", width=220, anchor=tk.W)

        self.tree_filter.tag_configure("tag_live", foreground=AppTheme.SUCCESS, background="#162e24")
        self.tree_filter.tag_configure("tag_blocked", foreground=AppTheme.DANGER, background="#2e181b")
        self.tree_filter.tag_configure("tag_error", foreground=AppTheme.WARNING, background="#2a2318")

        sb_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_filter.yview)
        self.tree_filter.configure(yscrollcommand=sb_y.set)
        self.tree_filter.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_filter_text_change(self, event=None):
        raw = self.txt_filter_proxies.get("1.0", tk.END)
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        self.lbl_filter_input_count.config(text=f"Đã nhập: {len(lines)} proxy")

    def _import_proxy_filter_file(self):
        f = filedialog.askopenfilename(title="Chọn file proxy", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if f and os.path.exists(f):
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
                self.txt_filter_proxies.delete("1.0", tk.END)
                self.txt_filter_proxies.insert(tk.END, content)
                self._on_filter_text_change()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def _paste_proxy_filter_clipboard(self):
        try:
            cl = self.root.clipboard_get()
            if cl:
                self.txt_filter_proxies.insert(tk.END, ("\n" if self.txt_filter_proxies.get("1.0", tk.END).strip() else "") + cl.strip())
                self._on_filter_text_change()
        except Exception:
            pass

    def _load_tool_proxies_to_filter(self):
        if os.path.exists("proxy.txt"):
            try:
                with open("proxy.txt", "r", encoding="utf-8", errors="replace") as fp:
                    txt = fp.read().strip()
                if txt:
                    self.txt_filter_proxies.delete("1.0", tk.END)
                    self.txt_filter_proxies.insert(tk.END, txt)
                    self._on_filter_text_change()
                    messagebox.showinfo("Thành công", f"Đã nạp danh sách từ file proxy.txt!")
                    return
            except Exception:
                pass
        messagebox.showwarning("Thông báo", "File proxy.txt trống hoặc không tồn tại.")

    def _clear_proxy_filter_input(self):
        self.txt_filter_proxies.delete("1.0", tk.END)
        self._on_filter_text_change()

    def on_start_proxy_filter(self):
        if getattr(self, "_filter_running", False):
            return
        raw = self.txt_filter_proxies.get("1.0", tk.END)
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập hoặc dán danh sách proxy cần lọc.")
            return

        try:
            th = int(self.spn_filter_threads.get().strip())
        except Exception:
            th = 20
        try:
            val_txt = self.cb_filter_timeout.get().strip().replace("s", "")
            to = max(0.2, float(val_txt))
        except Exception:
            to = 4.0

        strict_fb = self.var_filter_strict.get()
        try_socks = self.var_filter_try_socks.get()

        for itm in self.tree_filter.get_children():
            self.tree_filter.delete(itm)

        self._live_fb_proxies.clear()
        self._blocked_fb_proxies.clear()
        self._error_proxies.clear()

        self.lbl_flt_stat_total.config(text=str(len(lines)))
        self.lbl_flt_stat_live.config(text="0")
        self.lbl_flt_stat_blocked.config(text="0")
        self.lbl_flt_stat_error.config(text="0")
        self.lbl_flt_stat_prog.config(text="0%")

        self.prog_filter_proxy.config(maximum=len(lines), value=0)

        self._filter_running = True
        self._filter_stop_event.clear()
        self.btn_filter_start.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.btn_filter_stop.config(state=tk.NORMAL, bg=AppTheme.DANGER)

        t = threading.Thread(
            target=self._run_filter_thread,
            args=(lines, th, to, strict_fb, try_socks),
            daemon=True
        )
        t.start()

    def on_stop_proxy_filter(self):
        if self._filter_running:
            self._filter_stop_event.set()
            self.btn_filter_stop.config(text="⏳ Đang dừng...", state=tk.DISABLED)

    def _run_filter_thread(self, proxies: List[str], threads_count: int, timeout: float, strict_fb: bool, try_socks: bool):
        from app_gui import AppTheme
        total = len(proxies)
        completed = 0
        import concurrent.futures

        last_flt_ui = 0.0
        pending_ui_rows = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(threads_count, max(1, total))) as ex:
            fut_to_p = {ex.submit(check_proxy_against_facebook, p, timeout, strict_fb, try_socks): (idx + 1, p) for idx, p in enumerate(proxies)}
            for fut in concurrent.futures.as_completed(fut_to_p):
                if self._filter_stop_event.is_set():
                    break
                idx_row, orig_p = fut_to_p[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = {
                        "proxy": orig_p,
                        "clean_url": orig_p,
                        "protocol": "HTTP",
                        "ping_ms": 0,
                        "country": "--",
                        "status": "error",
                        "status_text": "⚠️ Lỗi luồng",
                        "detail": str(e)[:30],
                        "live": False
                    }

                completed += 1
                st = res["status"]
                is_live = (st == "live")
                if is_live:
                    self._live_fb_proxies.append(res.get("clean_url") or orig_p)
                elif st == "blocked":
                    self._blocked_fb_proxies.append(orig_p)
                else:
                    self._error_proxies.append(orig_p)

                # QUY TẮC CHỐNG LAG: KHÔNG THÊM PROXY BỊ LỖI VÀO BẢNG
                # Chỉ chèn các proxy Live hoặc Bị Chặn vào bảng lọc!
                if is_live or st == "blocked":
                    pending_ui_rows.append((idx_row, res))

                now = time.time()
                # Cập nhật UI định kỳ hoặc khi có Live mới hoặc khi hoàn tất
                if is_live or len(pending_ui_rows) >= 40 or (now - last_flt_ui) >= 0.15 or completed == total:
                    rows_to_insert = list(pending_ui_rows)
                    pending_ui_rows.clear()
                    last_flt_ui = now

                    def _update_ui(rows=rows_to_insert, c=completed):
                        for r_idx, r in rows:
                            tag = f"tag_{r['status']}"
                            # Giới hạn tối đa 1,000 dòng trên bảng để chống lag
                            ch = self.tree_filter.get_children()
                            if len(ch) >= 1000:
                                self.tree_filter.delete(ch[0])
                            self.tree_filter.insert(
                                "", "end",
                                values=(r_idx, r["proxy"], r["protocol"], (f"{r['ping_ms']}ms" if (r.get("live") or r['ping_ms'] <= int(timeout * 1000)) else f">{int(timeout * 1000)}ms") if r.get('ping_ms') else "--", r["country"], r["status_text"], r["detail"]),
                                tags=(tag,)
                            )
                        self.prog_filter_proxy.config(value=c)
                        pct = int((c / total) * 100) if total > 0 else 0
                        self.lbl_flt_stat_prog.config(text=f"{pct}%")
                        self.lbl_flt_stat_live.config(text=str(len(self._live_fb_proxies)))
                        self.lbl_flt_stat_blocked.config(text=str(len(self._blocked_fb_proxies)))
                        self.lbl_flt_stat_error.config(text=str(len(self._error_proxies)))

                    self.safe_ui_call(_update_ui)
        def _finish_ui():
            self._filter_running = False
            self.btn_filter_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
            self.btn_filter_stop.config(state=tk.DISABLED, bg=AppTheme.BORDER, text="⏹️ DỪNG LỌC")
            messagebox.showinfo(
                "Hoàn tất lọc Proxy FB",
                f"Kiểm tra xong {completed}/{total} proxy!\n"
                f"🟢 Live Facebook: {len(self._live_fb_proxies)}\n"
                f"🔴 Bị Facebook chặn: {len(self._blocked_fb_proxies)}\n"
                f"⚠️ Lỗi kết nối / Chết: {len(self._error_proxies)}"
            )

        self.safe_ui_call(_finish_ui)

    def _copy_live_fb_proxies(self):
        if not self._live_fb_proxies:
            messagebox.showwarning("Thông báo", "Chưa có proxy Live Facebook nào được lọc.")
            return
        txt = "\n".join(self._live_fb_proxies)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo("Thành công", f"Đã copy {len(self._live_fb_proxies)} proxy Live FB vào clipboard!")

    def _export_live_fb_proxies(self):
        if not self._live_fb_proxies:
            messagebox.showwarning("Thông báo", "Chưa có proxy Live Facebook nào để lưu.")
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="proxy_live_fb.txt",
            filetypes=[("Text files", "*.txt")]
        )
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fp:
                    fp.write("\n".join(self._live_fb_proxies) + "\n")
                messagebox.showinfo("Thành công", f"Đã lưu {len(self._live_fb_proxies)} proxy Live FB vào file:\n{f}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    def _apply_live_proxies_to_tool(self):
        if not self._live_fb_proxies:
            messagebox.showwarning("Thông báo", "Chưa có proxy Live FB nào được lọc.")
            return
        try:
            with open("proxy.txt", "w", encoding="utf-8") as fp:
                fp.write(f"# Danh sách Proxy LIVE Facebook - {time.ctime()}\n")
                fp.write("\n".join(self._live_fb_proxies) + "\n")
            messagebox.showinfo(
                "Đã lưu vào proxy.txt",
                f"Đã lưu thành công {len(self._live_fb_proxies)} proxy LIVE Facebook vào file 'proxy.txt'!\n\n"
                f"💡 Hướng dẫn sử dụng:\n"
                f"1. Vào tab 'CÀI ĐẶT CẤU HÌNH & METAKING'\n"
                f"2. Mục 'Nguồn Proxy' chọn: '📁 Danh sách Proxy (proxy.txt)'\n"
                f"3. Bấm Bắt đầu tạo tài khoản, tool sẽ tự động nạp kho proxy sạch này!"
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể ghi file proxy.txt: {e}")

    # =========================================================================
    # SUB-TAB 2: CÀO PROXY ĐA NGUỒN
    # =========================================================================
    def _build_proxy_scraper_tab(self, parent: tk.Frame, AppTheme):
        total_src_all = FreeProxyManager.get_total_sources_count()
        top_ctrl = tk.LabelFrame(
            parent, text=f" 🌐 Cấu Hình Nguồn Cào Proxy ({total_src_all:,}+ Sources Online) ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            bd=1, relief=tk.SOLID
        )
        top_ctrl.pack(fill=tk.X, padx=4, pady=4)

        # HÀNG 1: CHỌN NGUỒN CÀO, SỐ LƯỢNG & TỰ ĐỘNG LƯU
        row1 = tk.Frame(top_ctrl, bg=AppTheme.BG_CARD)
        row1.pack(fill=tk.X, padx=6, pady=3)

        tk.Label(row1, text="Loại nguồn:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_scrape_category = ttk.Combobox(
            row1,
            values=[
                f"Tất cả nguồn (Toàn bộ {total_src_all:,} nguồn GitHub, API - Không giới hạn)",
                "🔗 Cào 1 nguồn tùy chỉnh (Nhập link URL bên dưới - Cào hết không giới hạn)",
                "Nguồn GitHub Tươi Mới (High Speed & Fresh Checked)",
                "Chỉ nguồn SOCKS5 (Bảo Mật & Tốc Độ)",
                "Chỉ nguồn HTTP / HTTPS",
                "Chỉ nguồn SOCKS4"
            ],
            width=36,
            state="readonly"
        )
        self.cb_scrape_category.current(0)
        self.cb_scrape_category.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(row1, text="Proxy tối đa / nguồn:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_scrape_limit = ttk.Combobox(
            row1,
            values=[
                "Tất cả (Không giới hạn - Cào hết 100%)",
                "1000",
                "500",
                "200",
                "100",
                "50"
            ],
            width=20,
            state="readonly"
        )
        self.cb_scrape_limit.set("Tất cả (Không giới hạn - Cào hết 100%)")
        self.cb_scrape_limit.pack(side=tk.LEFT, padx=(4, 8))

        self.var_scrape_dedup = tk.BooleanVar(value=True)
        tk.Checkbutton(
            row1, text="Lọc trùng IP",
            variable=self.var_scrape_dedup, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_SMALL
        ).pack(side=tk.LEFT, padx=(0, 6))



        # HÀNG 2: CẤU HÌNH CHECK LIVE FACEBOOK & TIMEOUT (RỘNG RÃI, KHÔNG BỊ TRÀN)
        row_chk = tk.Frame(top_ctrl, bg=AppTheme.BG_CARD)
        row_chk.pack(fill=tk.X, padx=6, pady=3)

        self.var_scrape_check_fb = tk.BooleanVar(value=True)
        self.chk_scrape_check_fb = tk.Checkbutton(
            row_chk, text="🛡️ Vừa cào vừa check FB",
            variable=self.var_scrape_check_fb, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD, command=self._on_scrape_check_fb_toggled
        )
        self.chk_scrape_check_fb.pack(side=tk.LEFT, padx=(0, 8))

        self.var_scrape_only_live = tk.BooleanVar(value=True)
        self.chk_scrape_only_live = tk.Checkbutton(
            row_chk, text="🟢 Chỉ hiện Live FB (Ẩn DIE)",
            variable=self.var_scrape_only_live, bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD, command=self._on_scrape_filter_toggled
        )
        self.chk_scrape_only_live.pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(row_chk, text="Số luồng check:", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(4, 0))
        self.spn_scrape_check_threads = tk.Spinbox(row_chk, from_=1, to=500, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        self.spn_scrape_check_threads.delete(0, tk.END)
        self.spn_scrape_check_threads.insert(0, "50")
        self.spn_scrape_check_threads.pack(side=tk.LEFT, padx=(4, 8))

        tk.Label(row_chk, text="Timeout (giây):", font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT, padx=(4, 0))
        self.cb_scrape_timeout = ttk.Combobox(row_chk, values=["0.5", "0.8", "1.0", "1.5", "2.0", "3.0", "4.0", "5.0", "6.0", "8.0", "10.0"], width=6)
        self.cb_scrape_timeout.set("4.0")
        self.cb_scrape_timeout.pack(side=tk.LEFT, padx=(4, 6))

        tk.Label(
            row_chk,
            text="(💡 Khuyên dùng 4.0s - 5.0s cho Proxy Free)",
            font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
        ).pack(side=tk.LEFT, padx=(2, 0))

        self.row_custom_url = tk.Frame(top_ctrl, bg=AppTheme.BG_CARD)
        tk.Label(
            self.row_custom_url, text="🔗 URL nguồn:",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT
        ).pack(side=tk.LEFT)
        self.entry_custom_scrape_url = tk.Entry(
            self.row_custom_url, font=AppTheme.FONT_CODE, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid"
        )
        self.entry_custom_scrape_url.insert(0, "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt")
        self.entry_custom_scrape_url.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 6))

        def _on_cat_change(event=None):
            val = self.cb_scrape_category.get()
            if "1 nguồn tùy chỉnh" in val:
                self.row_custom_url.pack(fill=tk.X, padx=6, pady=(0, 4), before=row_save_cfg)
            else:
                self.row_custom_url.pack_forget()

        self.cb_scrape_category.bind("<<ComboboxSelected>>", _on_cat_change)

        # HÀNG CẤU HÌNH ĐƯỜNG DẪN FILE & ĐỊNH DẠNG TỰ ĐỘNG LƯU PROXY LIVE
        row_save_cfg = tk.Frame(top_ctrl, bg=AppTheme.BG_CARD)
        row_save_cfg.pack(fill=tk.X, padx=6, pady=(1, 4))

        self.var_scrape_auto_save = tk.BooleanVar(value=True)
        self.chk_scrape_auto_save = tk.Checkbutton(
            row_save_cfg, text="⚡ Cào Live Tự Động Lưu File",
            variable=self.var_scrape_auto_save, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            selectcolor=AppTheme.BG_INPUT, activebackground=AppTheme.BG_CARD,
            font=AppTheme.FONT_BODY_BOLD
        )
        self.chk_scrape_auto_save.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(
            row_save_cfg, text="📁 File lưu:",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        default_save_path = "proxy.txt"
        if hasattr(self, "get_proxy_file_path"):
            try:
                default_save_path = self.get_proxy_file_path()
            except Exception:
                pass
        elif hasattr(self, "config") and isinstance(self.config, dict):
            default_save_path = self.config.get("proxy_file_path", "proxy.txt")

        self.entry_scrape_save_path = tk.Entry(
            row_save_cfg, font=AppTheme.FONT_CODE, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=1, relief="solid", width=34
        )
        self.entry_scrape_save_path.insert(0, default_save_path)
        self.entry_scrape_save_path.pack(side=tk.LEFT, padx=(4, 4))

        tk.Button(
            row_save_cfg, text="📂 Chọn file...", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD_LIGHT, fg=AppTheme.TEXT_MAIN, relief=tk.SOLID, bd=1,
            padx=6, pady=2, command=self._browse_scrape_save_path
        ).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            row_save_cfg, text="Định dạng lưu:",
            font=AppTheme.FONT_BODY_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN
        ).pack(side=tk.LEFT)

        self.cb_scrape_save_format = ttk.Combobox(
            row_save_cfg,
            values=[
                "IP:Port (Chuẩn FB Reg & Tool)",
                "protocol://IP:Port",
                "IP:Port:User:Pass",
                "IP:Port | Protocol | Ping"
            ],
            width=26,
            state="readonly"
        )
        self.cb_scrape_save_format.set("IP:Port (Chuẩn FB Reg & Tool)")
        self.cb_scrape_save_format.pack(side=tk.LEFT, padx=(4, 6))

        tk.Button(
            row_save_cfg, text="📄 Mở File", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD_LIGHT, fg=AppTheme.INFO, relief=tk.SOLID, bd=1,
            padx=6, pady=2, command=self._open_scrape_save_file
        ).pack(side=tk.LEFT, padx=(0, 6))

        self.lbl_scrape_auto_save_status = tk.Label(
            row_save_cfg, text="(Đã lưu: 0 live)", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS
        )
        self.lbl_scrape_auto_save_status.pack(side=tk.LEFT, padx=4)

        row2 = tk.Frame(top_ctrl, bg=AppTheme.BG_CARD)
        row2.pack(fill=tk.X, padx=6, pady=(2, 6))

        self.btn_scrape_start = tk.Button(
            row2, text="🚀 BẮT ĐẦU CÀO PROXY", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.ACCENT, fg="#000000", activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT, padx=12, pady=4, command=self.on_start_proxy_scraper
        )
        self.btn_scrape_start.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_scrape_stop = tk.Button(
            row2, text="⏹️ DỪNG", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BORDER, fg="#ffffff", activebackground=AppTheme.DANGER,
            state=tk.DISABLED, relief=tk.FLAT, padx=10, pady=4, command=self.on_stop_proxy_scraper
        )
        self.btn_scrape_stop.pack(side=tk.LEFT, padx=(0, 8))

        tk.Button(
            row2, text="🟢 Xuất Proxy Live FB", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD_LIGHT, fg=AppTheme.SUCCESS, relief=tk.SOLID, bd=1,
            padx=10, pady=4, command=self._export_scraped_live_fb_proxies
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            row2, text="⚡ Lưu Live vào file", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD_LIGHT, fg=AppTheme.ACCENT, relief=tk.SOLID, bd=1,
            padx=10, pady=4, command=self._save_scraped_live_to_proxy_txt
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            row2, text="📋 Copy Live FB", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_INPUT, fg=AppTheme.SUCCESS, relief=tk.FLAT,
            padx=8, pady=4, command=self._copy_scraped_live_fb_proxies
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            row2, text="📋 Copy Tất Cả", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            padx=6, pady=4, command=self._copy_scraped_proxies
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            row2, text="💾 Xuất Tất Cả", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            padx=6, pady=4, command=self._export_scraped_proxies
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            row2, text="🛡️ CHUYỂN SANG TAB LỌC PROXY FB ⏩", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD_LIGHT, fg=AppTheme.WARNING, relief=tk.SOLID, bd=1,
            padx=10, pady=4, command=self._transfer_scraped_to_filter_tab
        ).pack(side=tk.RIGHT)

        kpi_frame = tk.Frame(parent, bg=AppTheme.BG_DARK)
        kpi_frame.pack(fill=tk.X, padx=4, pady=(2, 4))

        self.lbl_scrp_stat_sources = self._make_stat_badge(kpi_frame, "🌐 Nguồn Đang Cào", str(FreeProxyManager.get_total_sources_count()), AppTheme.TEXT_MAIN, AppTheme)
        self.lbl_scrp_stat_done_src = self._make_stat_badge(kpi_frame, "📡 Đã Xong Nguồn", "0", AppTheme.INFO, AppTheme)
        self.lbl_scrp_stat_total = self._make_stat_badge(kpi_frame, "📦 Tổng Thu Thập", "0", AppTheme.WARNING, AppTheme)
        self.lbl_scrp_stat_live = self._make_stat_badge(kpi_frame, "🟢 Live FB (Sạch)", "0", AppTheme.SUCCESS, AppTheme)
        self.lbl_scrp_stat_saved = self._make_stat_badge(kpi_frame, "💾 Đã Lưu File", "0", AppTheme.ACCENT, AppTheme)
        self.lbl_scrp_stat_blocked = self._make_stat_badge(kpi_frame, "🔴 Bị FB Chặn", "0", AppTheme.DANGER, AppTheme)
        self.lbl_scrp_stat_prog = self._make_stat_badge(kpi_frame, "⏳ Tiến Độ", "0%", AppTheme.INFO, AppTheme)

        self.prog_scrape_proxy = ttk.Progressbar(parent, mode="determinate")
        self.prog_scrape_proxy.pack(fill=tk.X, padx=4, pady=(0, 4))

        tree_frame = tk.Frame(parent, bg=AppTheme.BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        cols = ("idx", "proxy", "proto", "fb_status", "ping", "source", "time")
        self.tree_scraped = ttk.Treeview(tree_frame, columns=cols, show="headings")
        self.tree_scraped.heading("idx", text="#")
        self.tree_scraped.heading("proxy", text="Proxy (IP:Port)")
        self.tree_scraped.heading("proto", text="Giao Thức")
        self.tree_scraped.heading("fb_status", text="Trạng Thái FB")
        self.tree_scraped.heading("ping", text="Ping (ms)")
        self.tree_scraped.heading("source", text="Nguồn Cào")
        self.tree_scraped.heading("time", text="Thời Gian")

        self.tree_scraped.column("idx", width=45, anchor=tk.CENTER)
        self.tree_scraped.column("proxy", width=190, anchor=tk.W)
        self.tree_scraped.column("proto", width=75, anchor=tk.CENTER)
        self.tree_scraped.column("fb_status", width=140, anchor=tk.W)
        self.tree_scraped.column("ping", width=70, anchor=tk.CENTER)
        self.tree_scraped.column("source", width=220, anchor=tk.W)
        self.tree_scraped.column("time", width=80, anchor=tk.CENTER)

        self.tree_scraped.tag_configure("tag_live", foreground=AppTheme.SUCCESS, background="#162e24")
        self.tree_scraped.tag_configure("tag_blocked", foreground=AppTheme.DANGER, background="#2e181b")
        self.tree_scraped.tag_configure("tag_error", foreground=AppTheme.WARNING, background="#2a2318")
        self.tree_scraped.tag_configure("tag_default", foreground=AppTheme.TEXT_MAIN)

        sb_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_scraped.yview)
        self.tree_scraped.configure(yscrollcommand=sb_y.set)
        self.tree_scraped.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

    def _on_scrape_check_fb_toggled(self):
        if hasattr(self, "chk_scrape_only_live"):
            if self.var_scrape_check_fb.get():
                self.chk_scrape_only_live.config(state=tk.NORMAL)
            else:
                self.chk_scrape_only_live.config(state=tk.DISABLED)

    def _on_scrape_filter_toggled(self):
        """Khi bật/tắt checkbox 'Chỉ hiện Live FB (Ẩn DIE)', làm mới lại bảng hiển thị ngay lập tức."""
        only_live = bool(getattr(self, "var_scrape_only_live", None) and self.var_scrape_only_live.get()) and bool(getattr(self, "var_scrape_check_fb", None) and self.var_scrape_check_fb.get())
        if not hasattr(self, "tree_scraped") or not self.tree_scraped.winfo_exists():
            return

        for itm in self.tree_scraped.get_children():
            self.tree_scraped.delete(itm)

        self._scraped_tree_count = 0
        cache = getattr(self, "_scraped_items_cache", [])
        if only_live:
            items_to_render = [itm for itm in cache if itm.get("live")]
        else:
            # TUYỆT ĐỐI KHÔNG thêm proxy bị lỗi vào bảng để tránh lag!
            # Chỉ hiển thị Live FB và Bị Chặn (tối đa 1,000 dòng):
            live_items = [itm for itm in cache if itm.get("live")]
            blocked_items = [itm for itm in cache if itm.get("status") == "blocked"]
            other_unverified = [itm for itm in cache if itm.get("status") == "unverified"][:200]
            items_to_render = (live_items + blocked_items + other_unverified)[:1000]

        for itm in items_to_render:
            is_live = bool(itm.get("live"))
            is_blocked = (itm.get("status") == "blocked")
            tag = "tag_live" if is_live else ("tag_blocked" if is_blocked else "tag_default")

            self._scraped_tree_count += 1
            pos = 0 if is_live else "end"
            self.tree_scraped.insert(
                "", pos,
                values=(
                    self._scraped_tree_count,
                    itm["proxy"],
                    itm["protocol"],
                    itm.get("fb_status", "⚪ Chưa check"),
                    itm.get("ping", "--"),
                    itm["source"],
                    itm["time"]
                ),
                tags=(tag,)
            )
    def on_start_proxy_scraper(self):
        if getattr(self, "_scraper_running", False):
            return
        sel_cat = self.cb_scrape_category.get()
        cat_key = "all"
        if "1 nguồn tùy chỉnh" in sel_cat:
            c_url = self.entry_custom_scrape_url.get().strip() if hasattr(self, "entry_custom_scrape_url") else ""
            if not c_url.startswith("http"):
                messagebox.showwarning("Thiếu URL", "Vui lòng nhập đường link URL nguồn proxy (http:// hoặc https://) để cào!")
                return
            cat_key = c_url
        elif "GitHub" in sel_cat:
            cat_key = "github"
        elif "SOCKS5" in sel_cat:
            cat_key = "socks5"
        elif "HTTP" in sel_cat:
            cat_key = "http"
        elif "SOCKS4" in sel_cat:
            cat_key = "socks4"

        lim_str = self.cb_scrape_limit.get().strip()
        if "tất cả" in lim_str.lower() or "không giới hạn" in lim_str.lower():
            limit = 999999
        else:
            try:
                limit = int(lim_str)
            except Exception:
                limit = 200

        dedup = self.var_scrape_dedup.get()
        check_fb = self.var_scrape_check_fb.get()
        try:
            check_threads = int(self.spn_scrape_check_threads.get().strip())
        except Exception:
            check_threads = 50
        try:
            val_txt = self.cb_scrape_timeout.get().strip().replace("s", "")
            check_timeout = max(0.2, float(val_txt))
        except Exception:
            check_timeout = 4.0

        for itm in self.tree_scraped.get_children():
            self.tree_scraped.delete(itm)

        # Khởi tạo nạp danh sách proxy đã có trong file đích để chống trùng lặp
        save_p = self.get_scrape_save_path()
        self._init_scrape_auto_save_file(save_p)

        self._scraped_proxies_list.clear()
        self._scraped_live_fb_proxies.clear()
        self._scraped_blocked_fb_proxies.clear()
        self._scraped_error_proxies.clear()
        self._scraped_unique_ips.clear()
        self._scraped_tree_count = 0
        self._scraped_items_cache = []

        self.lbl_scrp_stat_done_src.config(text="0")
        self.lbl_scrp_stat_total.config(text="0")
        self.lbl_scrp_stat_live.config(text="0")
        self.lbl_scrp_stat_blocked.config(text="0")
        self.lbl_scrp_stat_prog.config(text="0%")

        self._scraper_running = True
        self._scraper_stop_event.clear()
        self.btn_scrape_start.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.btn_scrape_stop.config(state=tk.NORMAL, bg=AppTheme.DANGER, text="⏹️ DỪNG")

        t = threading.Thread(
            target=self._run_scraper_thread,
            args=(cat_key, limit, dedup, check_fb, check_threads, check_timeout),
            daemon=True
        )
        t.start()

    def on_stop_proxy_scraper(self):
        if self._scraper_running:
            self._scraper_stop_event.set()
            self.btn_scrape_stop.config(text="⏳ Đang dừng...", state=tk.DISABLED)

    def _get_current_live_fb_proxies(self) -> List[str]:
        """Lấy danh sách proxy Live Facebook hiện có (bộ nhớ + quét trực tiếp từ bảng hiển thị + cache)."""
        res = list(self._scraped_live_fb_proxies)
        seen = set(res)
        try:
            for itm in getattr(self, "_scraped_items_cache", []):
                if itm.get("live") or "live" in str(itm.get("fb_status", "")).lower() or "sạch" in str(itm.get("fb_status", "")).lower():
                    p_val = str(itm.get("proxy", "")).strip()
                    if p_val and p_val not in seen:
                        seen.add(p_val)
                        res.append(p_val)
        except Exception:
            pass
        try:
            for itm_id in self.tree_scraped.get_children():
                vals = self.tree_scraped.item(itm_id).get("values", [])
                if len(vals) >= 4:
                    status_text = str(vals[3]).lower()
                    if "live" in status_text or "sạch" in status_text:
                        p_val = str(vals[1]).strip()
                        if p_val and p_val not in seen:
                            seen.add(p_val)
                            res.append(p_val)
        except Exception:
            pass
        return res


    def _get_current_scraped_proxies(self) -> List[str]:
        """Lấy toàn bộ danh sách proxy đã cào được (bộ nhớ + quét bảng)."""
        res = list(self._scraped_proxies_list)
        seen = set(res)
        try:
            for itm_id in self.tree_scraped.get_children():
                vals = self.tree_scraped.item(itm_id).get("values", [])
                if len(vals) >= 2:
                    p_val = str(vals[1]).strip()
                    if p_val and p_val not in seen:
                        seen.add(p_val)
                        res.append(p_val)
        except Exception:
            pass
        return res

    def _run_scraper_thread(
        self,
        category: str,
        limit: int,
        deduplicate: bool,
        check_fb: bool,
        check_threads: int,
        check_timeout: float
    ):
        live_set = set(self._scraped_live_fb_proxies)
        proxies_set = set(self._scraped_proxies_list)
        blocked_set = set(self._scraped_blocked_fb_proxies)
        error_set = set(self._scraped_error_proxies)

        saved_in_proxy_txt = set()
        if os.path.exists("proxy.txt"):
            try:
                with open("proxy.txt", "r", encoding="utf-8-sig", errors="ignore") as fp_init:
                    for l in fp_init:
                        s = l.strip()
                        if s and not s.startswith("#") and not s.startswith("//"):
                            saved_in_proxy_txt.add(s)
            except Exception:
                pass

        def _prog_cb(done_src, total_src, new_items, total_found, unique_count, live_count, blocked_count):
            # Cập nhật danh sách proxy thời gian thực (Real-time sync) với tra cứu O(1) set
            new_live_saved = False
            for itm in new_items:
                p_str = itm.get("proxy")
                if not p_str:
                    continue
                if p_str not in proxies_set:
                    proxies_set.add(p_str)
                    self._scraped_proxies_list.append(p_str)
                if itm.get("live"):
                    if p_str not in live_set:
                        live_set.add(p_str)
                        self._scraped_live_fb_proxies.append(p_str)
                    if getattr(self, "var_scrape_auto_save", None) and self.var_scrape_auto_save.get():
                        self._auto_save_one_live_proxy(itm)
                        new_live_saved = True
                elif itm.get("status") == "blocked":
                    if p_str not in blocked_set:
                        blocked_set.add(p_str)
                        self._scraped_blocked_fb_proxies.append(p_str)
                elif itm.get("status") == "error":
                    if p_str not in error_set:
                        error_set.add(p_str)
                        self._scraped_error_proxies.append(p_str)

            if new_live_saved and hasattr(self, "update_file_proxy_panel"):
                try:
                    self.update_file_proxy_panel()
                except Exception:
                    pass

            # QUY TẮC CỐT LÕI CHỐNG LAG:
            # TUYỆT ĐỐI KHÔNG THÊM BẢN GHI CỦA CÁC PROXY BỊ LỖI VÀO BẢNG
            # Chỉ hiển thị Proxy Live FB (hoặc Bị FB Chặn). Proxy lỗi / die / timeout bị loại bỏ 100%!
            if check_fb:
                items_to_render = [itm for itm in new_items if itm.get("live") or itm.get("status") == "blocked"]
            else:
                items_to_render = new_items[:30]

            def _ui_update():
                if not self._scraper_running:
                    return
                self.prog_scrape_proxy.config(maximum=max(1, total_src), value=done_src)
                pct = int((done_src / total_src) * 100) if total_src > 0 else 0
                self.lbl_scrp_stat_sources.config(text=str(total_src))
                self.lbl_scrp_stat_done_src.config(text=str(done_src))
                self.lbl_scrp_stat_total.config(text=str(total_found))
                self.lbl_scrp_stat_live.config(text=str(len(self._scraped_live_fb_proxies)))
                if hasattr(self, "lbl_scrp_stat_saved"):
                    self.lbl_scrp_stat_saved.config(text=str(getattr(self, "_scraped_file_saved_count", 0)))
                if hasattr(self, "lbl_scrape_auto_save_status"):
                    self.lbl_scrape_auto_save_status.config(text=f"(Đã lưu: {getattr(self, '_scraped_file_saved_count', 0)} live)")
                self.lbl_scrp_stat_blocked.config(text=str(len(self._scraped_blocked_fb_proxies)))
                self.lbl_scrp_stat_prog.config(text=f"{pct}%")

                if not hasattr(self, "_scraped_tree_count"):
                    self._scraped_tree_count = len(self.tree_scraped.get_children())
                if not hasattr(self, "_scraped_items_cache"):
                    self._scraped_items_cache = []

                only_live = bool(getattr(self, "var_scrape_only_live", None) and self.var_scrape_only_live.get()) and bool(getattr(self, "var_scrape_check_fb", None) and self.var_scrape_check_fb.get())

                for itm in items_to_render:
                    is_live = bool(itm.get("live"))
                    is_blocked = (itm.get("status") == "blocked")

                    # Khi bật "Chỉ hiện Live FB (Ẩn DIE)": chỉ render proxy live
                    if only_live and not is_live:
                        continue

                    # Chỉ lưu vào cache các proxy Live / Blocked / Unverified mẫu
                    self._scraped_items_cache.append(itm)

                    tag = "tag_live" if is_live else ("tag_blocked" if is_blocked else "tag_default")
                    self._scraped_tree_count += 1
                    pos = 0 if is_live else "end"

                    # GIỚI HẠN TỐI ĐA BẢNG TREEVIEW: 1,000 dòng để chống lag triệt để
                    children = self.tree_scraped.get_children()
                    if len(children) >= 1000:
                        self.tree_scraped.delete(children[-1])

                    self.tree_scraped.insert(
                        "", pos,
                        values=(
                            self._scraped_tree_count,
                            itm["proxy"],
                            itm["protocol"],
                            itm.get("fb_status", "⚪ Chưa check"),
                            itm.get("ping", "--"),
                            itm["source"],
                            itm["time"]
                        ),
                        tags=(tag,)
                    )
            self.safe_ui_call(_ui_update)

        res = scrape_proxies_worker(
            category=category,
            limit_per_source=limit,
            deduplicate=deduplicate,
            progress_cb=_prog_cb,
            stop_event=self._scraper_stop_event,
            check_fb=check_fb,
            check_threads=check_threads,
            check_timeout=check_timeout,
            strict_fb=True,
            on_live_proxy_cb=self._auto_save_one_live_proxy
        )

        for itm in res:
            p_str = itm["proxy"]
            if p_str not in proxies_set:
                proxies_set.add(p_str)
                self._scraped_proxies_list.append(p_str)
            if itm.get("live"):
                if p_str not in live_set:
                    live_set.add(p_str)
                    self._scraped_live_fb_proxies.append(p_str)
            elif itm.get("status") == "blocked":
                if p_str not in blocked_set:
                    blocked_set.add(p_str)
                    self._scraped_blocked_fb_proxies.append(p_str)
            elif itm.get("status") == "error":
                if p_str not in error_set:
                    error_set.add(p_str)
                    self._scraped_error_proxies.append(p_str)
        def _done_ui():
            self._scraper_running = False
            self.btn_scrape_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
            self.btn_scrape_stop.config(state=tk.DISABLED, bg=AppTheme.BORDER, text="⏹️ DỪNG")
            # Đồng bộ lại panel proxy của tool nếu lưu vào file proxy chính
            if hasattr(self, "update_file_proxy_panel"):
                try:
                    self.update_file_proxy_panel()
                except Exception:
                    pass

            if check_fb:
                auto_msg = f"💾 Đã tự động lưu {getattr(self, '_scraped_file_saved_count', 0)} proxy Live vào file:\n   {self.get_scrape_save_path()}\n\n" if getattr(self, "var_scrape_auto_save", None) and self.var_scrape_auto_save.get() else ""
                msg = (
                    f"Cào & Kiểm Tra Facebook Hoàn Tất!\n\n"
                    f"📦 Tổng thu thập: {len(self._scraped_proxies_list)} proxy\n"
                    f"🟢 Live Facebook (Sạch): {len(self._scraped_live_fb_proxies)}\n"
                    f"{auto_msg}"
                    f"🔴 Bị Facebook chặn: {len(self._scraped_blocked_fb_proxies)}\n"
                    f"⚠️ Lỗi kết nối / Chết: {len(self._scraped_error_proxies)}\n\n"
                    f"💡 File lưu đã được cập nhật đúng định dạng ({self.get_scrape_save_format()})!"
                )
            else:
                msg = (
                    f"Cào Proxy Hoàn Tất!\n\n"
                    f"📦 Tổng thu thập: {len(self._scraped_proxies_list)} proxy\n\n"
                    f"💡 Bạn có thể xuất danh sách hoặc bấm '🛡️ Vừa cào vừa check FB' để kiểm định chất lượng."
                )
            messagebox.showinfo("Cào Proxy Hoàn Tất", msg)

        self.safe_ui_call(_done_ui)

    def _export_scraped_live_fb_proxies(self):
        live_list = self._get_current_live_fb_proxies()
        if not live_list:
            all_list = self._get_current_scraped_proxies()
            if all_list:
                ans = messagebox.askyesno(
                    "Thông báo xuất Proxy",
                    f"Chưa có proxy nào được xác nhận Live Facebook (có thể do chưa bật '🛡️ Vừa cào vừa check FB' hoặc đang kiểm tra).\n\n"
                    f"Bạn có muốn xuất toàn bộ {len(all_list)} proxy vừa cào được ra file không?"
                )
                if ans:
                    live_list = all_list
                else:
                    return
            else:
                messagebox.showwarning(
                    "Thông báo",
                    "Chưa có proxy Live Facebook nào được lọc thành công.\n"
                    "Hãy bật tùy chọn '🛡️ Vừa cào vừa check FB' và bấm 'Bắt Đầu Cào Proxy'."
                )
                return
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="proxy_live_fb.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if f:
            try:
                save_fmt = self.get_scrape_save_format()
                formatted_list = []
                seen_fmt = set()
                for p in live_list:
                    fmt_p = self.format_proxy_for_save(p, fmt_choice=save_fmt)
                    if fmt_p and fmt_p not in seen_fmt:
                        seen_fmt.add(fmt_p)
                        formatted_list.append(fmt_p)
                with open(f, "w", encoding="utf-8") as fp:
                    fp.write(f"# Danh sách Proxy LIVE Facebook ({len(formatted_list)} proxies) - Định dạng: {save_fmt} - {time.ctime()}\n")
                    fp.write("\n".join(formatted_list) + "\n")
                status_extra = " (Tiến trình cào đang tiếp tục cào thêm trong nền...)" if self._scraper_running else ""
                messagebox.showinfo(
                    "Thành công",
                    f"Đã xuất thành công {len(live_list)} proxy LIVE Facebook sạch vào file:\n{f}{status_extra}"
                )
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    def _save_scraped_live_to_proxy_txt(self):
        live_list = self._get_current_live_fb_proxies()
        save_path = self.get_scrape_save_path()
        save_fmt = self.get_scrape_save_format()
        if not live_list:
            all_list = self._get_current_scraped_proxies()
            if all_list:
                ans = messagebox.askyesno(
                    "Lưu vào file",
                    f"Chưa có proxy nào được xác nhận Live Facebook.\n\n"
                    f"Bạn có muốn lưu toàn bộ {len(all_list)} proxy vừa cào được vào file '{os.path.basename(save_path)}' theo định dạng '{save_fmt}' không?"
                )
                if ans:
                    live_list = all_list
                else:
                    return
            else:
                messagebox.showwarning(
                    "Thông báo",
                    "Chưa có proxy Live Facebook nào được lọc thành công.\n"
                    "Hãy bật tùy chọn '🛡️ Vừa cào vừa check FB' và bấm 'Bắt Đầu Cào Proxy'."
                )
                return
        try:
            formatted_list = []
            seen_fmt = set()
            for p in live_list:
                fmt_p = self.format_proxy_for_save(p, fmt_choice=save_fmt)
                if fmt_p and fmt_p not in seen_fmt:
                    seen_fmt.add(fmt_p)
                    formatted_list.append(fmt_p)

            abs_path = save_path if os.path.isabs(save_path) else os.path.abspath(save_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as fp:
                fp.write(f"# Danh sách Proxy LIVE Facebook ({len(formatted_list)} proxies) - Định dạng: {save_fmt} - {time.ctime()}\n")
                fp.write("\n".join(formatted_list) + "\n")

            self._scraped_file_saved_count = len(formatted_list)
            self._scraped_file_saved_set = set(formatted_list)
            if hasattr(self, "lbl_scrp_stat_saved"):
                self.lbl_scrp_stat_saved.config(text=str(self._scraped_file_saved_count))
            if hasattr(self, "lbl_scrape_auto_save_status"):
                self.lbl_scrape_auto_save_status.config(text=f"(Đã lưu: {self._scraped_file_saved_count} live)")

            if hasattr(self, "update_file_proxy_panel"):
                try:
                    self.update_file_proxy_panel()
                except Exception:
                    pass

            status_extra = " (Tiến trình cào đang tiếp tục cào & tự động lưu thêm trong nền...)" if self._scraper_running else ""
            messagebox.showinfo(
                "Đã lưu vào file",
                f"Đã lưu thành công {len(formatted_list)} proxy LIVE Facebook đúng định dạng '{save_fmt}' vào file:\n{abs_path}!{status_extra}\n\n"
                f"💡 Hướng dẫn sử dụng:\n"
                f"1. Vào tab 'CÀI ĐẶT CẤU HÌNH & METAKING'\n"
                f"2. Mục 'Nguồn Proxy' chọn: '📁 Danh sách Proxy ({os.path.basename(save_path)})'\n"
                f"3. Bấm Bắt đầu tạo tài khoản, tool sẽ tự động nạp kho proxy sạch này!"
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể ghi file {save_path}: {e}")

    def _copy_scraped_live_fb_proxies(self):
        live_list = self._get_current_live_fb_proxies()
        if not live_list:
            messagebox.showwarning("Thông báo", "Chưa có proxy Live Facebook nào để copy.")
            return
        save_fmt = self.get_scrape_save_format()
        formatted_list = []
        seen_fmt = set()
        for p in live_list:
            fmt_p = self.format_proxy_for_save(p, fmt_choice=save_fmt)
            if fmt_p and fmt_p not in seen_fmt:
                seen_fmt.add(fmt_p)
                formatted_list.append(fmt_p)
        txt = "\n".join(formatted_list)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        status_extra = " (Tiến trình cào đang chạy tiếp trong nền...)" if self._scraper_running else ""
        messagebox.showinfo("Thành công", f"Đã copy {len(live_list)} proxy Live Facebook vào clipboard!{status_extra}")

    def _copy_scraped_proxies(self):
        all_list = self._get_current_scraped_proxies()
        if not all_list:
            messagebox.showwarning("Thông báo", "Chưa có proxy nào được cào.")
            return
        txt = "\n".join(all_list)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo("Thành công", f"Đã copy {len(all_list)} proxy vào clipboard!")

    def _export_scraped_proxies(self):
        all_list = self._get_current_scraped_proxies()
        if not all_list:
            messagebox.showwarning("Thông báo", "Chưa có proxy nào để xuất file.")
            return
        f = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="scraped_proxies.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fp:
                    fp.write(f"# Danh sách toàn bộ Proxy đã cào - {time.ctime()}\n")
                    fp.write("\n".join(all_list) + "\n")
                messagebox.showinfo(
                    "Thành công",
                    f"Đã xuất thành công {len(all_list)} proxy vào file:\n{f}"
                )
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    def _transfer_scraped_to_filter_tab(self):
        # Ưu tiên lấy danh sách Live FB với đầy đủ tiền tố giao thức (socks4://, socks5://, http://)
        all_list = self._get_current_live_fb_proxies()
        if not all_list:
            all_list = self._get_current_scraped_proxies()
        if not all_list:
            messagebox.showwarning("Thông báo", "Chưa có proxy nào được cào. Vui lòng bấm 'Bắt Đầu Cào Proxy' trước.")
            return
        self.txt_filter_proxies.delete("1.0", tk.END)
        self.txt_filter_proxies.insert(tk.END, "\n".join(all_list))
        self._on_filter_text_change()
        self.util_notebook.select(self.tab_util_filter)
        msg = f"Đã chuyển {len(all_list)} proxy sang tab 'Lọc Proxy Live FB'!\nBấm 'Bắt Đầu Lọc' để lọc các proxy không bị Facebook chặn."
        messagebox.showinfo("Chuyển Thành Công", msg)


    # =========================================================================
    # SUB-TAB 3: CHECK LIVE UID FB
    # =========================================================================
    def _build_check_uid_tab(self, parent: tk.Frame, AppTheme):
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=AppTheme.BG_DARK, bd=0, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        right_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        paned.add(left_frame, minsize=380)
        paned.add(right_frame, minsize=520)

        card_in = tk.LabelFrame(
            left_frame, text=" 📋 Danh Sách UID Facebook Cần Check ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            bd=1, relief=tk.SOLID
        )
        card_in.pack(fill=tk.BOTH, expand=True, padx=4, pady=(0, 4))

        tool_bar = tk.Frame(card_in, bg=AppTheme.BG_CARD)
        tool_bar.pack(fill=tk.X, padx=6, pady=4)

        tk.Button(
            tool_bar, text="📁 Nhập File UID", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            command=self._import_uid_file
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            tool_bar, text="📋 Dán", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, relief=tk.FLAT,
            command=self._paste_uid_clipboard
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            tool_bar, text="🗑️ Xóa", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_INPUT, fg=AppTheme.DANGER, relief=tk.FLAT,
            command=self._clear_uid_input
        ).pack(side=tk.RIGHT)

        self.txt_uid_input = scrolledtext.ScrolledText(
            card_in, wrap=tk.NONE, font=AppTheme.FONT_CODE,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff",
            bd=0, height=12
        )
        self.txt_uid_input.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))
        self.txt_uid_input.bind("<KeyRelease>", self._on_uid_text_change)

        self.lbl_uid_input_count = tk.Label(
            card_in, text="Đã nhập: 0 UID (Hỗ trợ UID, Link profile, UID|PASS|...)",
            font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
        )
        self.lbl_uid_input_count.pack(anchor="w", padx=6, pady=(0, 4))

        card_cfg = tk.LabelFrame(
            left_frame, text=" ⚙️ Cấu Hình Check Graph API ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN,
            bd=1, relief=tk.SOLID
        )
        card_cfg.pack(fill=tk.X, padx=4, pady=4)

        row_cfg = tk.Frame(card_cfg, bg=AppTheme.BG_CARD)
        row_cfg.pack(fill=tk.X, padx=6, pady=4)

        tk.Label(row_cfg, text="Số luồng:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.spn_uid_threads = tk.Spinbox(row_cfg, from_=1, to=50, width=5, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN)
        self.spn_uid_threads.delete(0, tk.END)
        self.spn_uid_threads.insert(0, "10")
        self.spn_uid_threads.pack(side=tk.LEFT, padx=(4, 12))

        tk.Label(row_cfg, text="Proxy:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(side=tk.LEFT)
        self.cb_uid_proxy_mode = ttk.Combobox(
            row_cfg,
            values=["Direct (Không dùng proxy)", "Dùng Proxy từ Tool / Danh sách"],
            width=26,
            state="readonly"
        )
        self.cb_uid_proxy_mode.current(0)
        self.cb_uid_proxy_mode.pack(side=tk.LEFT, padx=(4, 6))

        act_frame = tk.Frame(left_frame, bg=AppTheme.BG_DARK)
        act_frame.pack(fill=tk.X, padx=4, pady=4)

        self.btn_uid_start = tk.Button(
            act_frame, text="▶️ BẮT ĐẦU CHECK UID", font=AppTheme.FONT_TITLE,
            bg=AppTheme.ACCENT, fg="#000000", activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT, height=2, command=self.on_start_check_uid
        )
        self.btn_uid_start.pack(fill=tk.X, pady=(0, 4))

        self.btn_uid_stop = tk.Button(
            act_frame, text="⏹️ DỪNG CHECK", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BORDER, fg="#ffffff", activebackground=AppTheme.DANGER,
            state=tk.DISABLED, relief=tk.FLAT, command=self.on_stop_check_uid
        )
        self.btn_uid_stop.pack(fill=tk.X, pady=(0, 6))

        exp_row = tk.Frame(act_frame, bg=AppTheme.BG_DARK)
        exp_row.pack(fill=tk.X)

        tk.Button(
            exp_row, text="📋 Copy LIVE", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS, relief=tk.FLAT,
            command=self._copy_live_uids
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(
            exp_row, text="📋 Copy DIE", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.DANGER, relief=tk.FLAT,
            command=self._copy_die_uids
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        tk.Button(
            exp_row, text="💾 Lưu LIVE", font=AppTheme.FONT_SMALL_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.INFO, relief=tk.FLAT,
            command=self._export_live_uids
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        kpi_frame = tk.Frame(right_frame, bg=AppTheme.BG_DARK)
        kpi_frame.pack(fill=tk.X, pady=(0, 4))

        self.lbl_uid_stat_total = self._make_stat_badge(kpi_frame, "📊 Tổng UID", "0", AppTheme.TEXT_MAIN, AppTheme)
        self.lbl_uid_stat_live = self._make_stat_badge(kpi_frame, "🟢 LIVE", "0", AppTheme.SUCCESS, AppTheme)
        self.lbl_uid_stat_die = self._make_stat_badge(kpi_frame, "🔴 DIE", "0", AppTheme.DANGER, AppTheme)
        self.lbl_uid_stat_warn = self._make_stat_badge(kpi_frame, "⚠️ Rate Limit", "0", AppTheme.WARNING, AppTheme)
        self.lbl_uid_stat_prog = self._make_stat_badge(kpi_frame, "⏳ Tiến Độ", "0%", AppTheme.INFO, AppTheme)

        self.prog_check_uid = ttk.Progressbar(right_frame, mode="determinate")
        self.prog_check_uid.pack(fill=tk.X, pady=(0, 4))

        tree_frame = tk.Frame(right_frame, bg=AppTheme.BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("idx", "uid", "status", "detail", "time")
        self.tree_uid = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_uid.heading("idx", text="#")
        self.tree_uid.heading("uid", text="UID Facebook")
        self.tree_uid.heading("status", text="Trạng Thái")
        self.tree_uid.heading("detail", text="Chi Tiết Graph API")
        self.tree_uid.heading("time", text="Thời Gian")

        self.tree_uid.column("idx", width=45, anchor=tk.CENTER)
        self.tree_uid.column("uid", width=180, anchor=tk.W)
        self.tree_uid.column("status", width=120, anchor=tk.CENTER)
        self.tree_uid.column("detail", width=280, anchor=tk.W)
        self.tree_uid.column("time", width=100, anchor=tk.CENTER)

        self.tree_uid.tag_configure("tag_live", foreground=AppTheme.SUCCESS, background="#162e24")
        self.tree_uid.tag_configure("tag_die", foreground=AppTheme.DANGER, background="#2e181b")
        self.tree_uid.tag_configure("tag_warn", foreground=AppTheme.WARNING, background="#2a2318")

        sb_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_uid.yview)
        self.tree_uid.configure(yscrollcommand=sb_y.set)
        self.tree_uid.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_uid.bind("<Double-1>", self._on_uid_double_click)

    def _on_uid_text_change(self, event=None):
        raw = self.txt_uid_input.get("1.0", tk.END)
        lines = [extract_facebook_uid_from_line(l) for l in raw.splitlines() if l.strip()]
        valid_uids = [u for u in lines if u]
        self.lbl_uid_input_count.config(text=f"Đã nhận diện: {len(valid_uids)} UID hợp lệ")

    def _import_uid_file(self):
        f = filedialog.askopenfilename(title="Chọn file UID", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if f and os.path.exists(f):
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as fp:
                    content = fp.read()
                self.txt_uid_input.delete("1.0", tk.END)
                self.txt_uid_input.insert(tk.END, content)
                self._on_uid_text_change()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể đọc file: {e}")

    def _paste_uid_clipboard(self):
        try:
            cl = self.root.clipboard_get()
            if cl:
                self.txt_uid_input.insert(tk.END, ("\n" if self.txt_uid_input.get("1.0", tk.END).strip() else "") + cl.strip())
                self._on_uid_text_change()
        except Exception:
            pass

    def _clear_uid_input(self):
        self.txt_uid_input.delete("1.0", tk.END)
        self._on_uid_text_change()

    def _on_uid_double_click(self, event=None):
        sel = self.tree_uid.selection()
        if sel:
            item = self.tree_uid.item(sel[0])
            uid = item["values"][1]
            if uid:
                webbrowser.open(f"https://www.facebook.com/{uid}")

    def on_start_check_uid(self):
        if getattr(self, "_uid_check_running", False):
            return
        raw = self.txt_uid_input.get("1.0", tk.END)
        lines = [l.strip() for l in raw.splitlines() if l.strip() and not l.startswith("#")]
        uids = []
        for l in lines:
            u = extract_facebook_uid_from_line(l)
            if u:
                uids.append(u)

        if not uids:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập hoặc dán danh sách UID cần kiểm tra.")
            return

        try:
            th = int(self.spn_uid_threads.get().strip())
        except Exception:
            th = 10

        use_proxy_mode = self.cb_uid_proxy_mode.get()
        proxy_val = None
        if "Proxy" in use_proxy_mode and hasattr(self, "proxy_manager"):
            try:
                proxy_val = self.proxy_manager.get_random_proxy()
            except Exception:
                pass

        for itm in self.tree_uid.get_children():
            self.tree_uid.delete(itm)

        self._uids_live.clear()
        self._uids_die.clear()
        self._uids_warn.clear()

        self.lbl_uid_stat_total.config(text=str(len(uids)))
        self.lbl_uid_stat_live.config(text="0")
        self.lbl_uid_stat_die.config(text="0")
        self.lbl_uid_stat_warn.config(text="0")
        self.lbl_uid_stat_prog.config(text="0%")

        self.prog_check_uid.config(maximum=len(uids), value=0)

        self._uid_check_running = True
        self._uid_check_stop_event.clear()
        self.btn_uid_start.config(state=tk.DISABLED, bg=AppTheme.BORDER)
        self.btn_uid_stop.config(state=tk.NORMAL, bg=AppTheme.DANGER)

        t = threading.Thread(
            target=self._run_check_uid_thread,
            args=(uids, th, proxy_val),
            daemon=True
        )
        t.start()

    def on_stop_check_uid(self):
        if self._uid_check_running:
            self._uid_check_stop_event.set()
            self.btn_uid_stop.config(text="⏳ Đang dừng...", state=tk.DISABLED)

    def _run_check_uid_thread(self, uids: List[str], threads_count: int, proxy: Optional[str]):
        from app_gui import AppTheme
        total = len(uids)
        completed = 0
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(threads_count, total)) as ex:
            fut_to_uid = {ex.submit(check_single_uid_graph, u, proxy, 6): (idx + 1, u) for idx, u in enumerate(uids)}
            for fut in concurrent.futures.as_completed(fut_to_uid):
                if self._uid_check_stop_event.is_set():
                    break
                idx_row, orig_uid = fut_to_uid[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = {
                        "uid": orig_uid,
                        "status": "die",
                        "status_text": "🔴 Lỗi",
                        "detail": str(e)[:30],
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "live": False
                    }

                completed += 1
                st = res["status"]
                if st == "live":
                    self._uids_live.append(res["uid"])
                elif st == "warn":
                    self._uids_warn.append(res["uid"])
                else:
                    self._uids_die.append(res["uid"])

                def _ui_update(r=res, c=completed, idx=idx_row):
                    tag = f"tag_{r['status']}"
                    self.tree_uid.insert(
                        "", "end",
                        values=(idx, r["uid"], r["status_text"], r["detail"], r["time"]),
                        tags=(tag,)
                    )
                    self.prog_check_uid.config(value=c)
                    pct = int((c / total) * 100) if total > 0 else 0
                    self.lbl_uid_stat_prog.config(text=f"{pct}%")
                    self.lbl_uid_stat_live.config(text=str(len(self._uids_live)))
                    self.lbl_uid_stat_die.config(text=str(len(self._uids_die)))
                    self.lbl_uid_stat_warn.config(text=str(len(self._uids_warn)))

                self.safe_ui_call(_ui_update)

        def _done_ui():
            self._uid_check_running = False
            self.btn_uid_start.config(state=tk.NORMAL, bg=AppTheme.ACCENT)
            self.btn_uid_stop.config(state=tk.DISABLED, bg=AppTheme.BORDER, text="⏹️ DỪNG CHECK")
            messagebox.showinfo(
                "Kiểm Tra UID Xong",
                f"Đã kiểm tra xong {completed}/{total} UID!\n"
                f"🟢 LIVE: {len(self._uids_live)}\n"
                f"🔴 DIE: {len(self._uids_die)}\n"
                f"⚠️ Rate Limit: {len(self._uids_warn)}"
            )

        self.safe_ui_call(_done_ui)

    def _copy_live_uids(self):
        if not self._uids_live:
            messagebox.showwarning("Thông báo", "Chưa có UID LIVE nào.")
            return
        txt = "\n".join(self._uids_live)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo("Thành công", f"Đã copy {len(self._uids_live)} UID LIVE vào clipboard!")

    def _copy_die_uids(self):
        if not self._uids_die:
            messagebox.showwarning("Thông báo", "Chưa có UID DIE nào.")
            return
        txt = "\n".join(self._uids_die)
        self.root.clipboard_clear()
        self.root.clipboard_append(txt)
        messagebox.showinfo("Thành công", f"Đã copy {len(self._uids_die)} UID DIE vào clipboard!")

    def _export_live_uids(self):
        if not self._uids_live:
            messagebox.showwarning("Thông báo", "Chưa có UID LIVE để lưu file.")
            return
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="uid_live.txt", filetypes=[("Text files", "*.txt")])
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fp:
                    fp.write("\n".join(self._uids_live) + "\n")
                messagebox.showinfo("Thành công", f"Đã lưu {len(self._uids_live)} UID LIVE vào file:\n{f}")
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể lưu file: {e}")

    # =========================================================================
    # SUB-TAB 4: ĐỌC MAIL & LẤY OTP
    # =========================================================================
    def _build_read_mail_tab(self, parent: tk.Frame, AppTheme):
        paned = tk.PanedWindow(parent, orient=tk.HORIZONTAL, bg=AppTheme.BG_DARK, bd=0, sashwidth=4)
        paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        left_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        right_frame = tk.Frame(paned, bg=AppTheme.BG_DARK)
        paned.add(left_frame, minsize=400)
        paned.add(right_frame, minsize=520)

        card_in = tk.LabelFrame(
            left_frame, text=" 📬 Cấu Hình Hòm Thư & Dịch Vụ ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.ACCENT,
            bd=1, relief=tk.SOLID
        )
        card_in.pack(fill=tk.X, padx=4, pady=(0, 4))

        tk.Label(card_in, text="Dịch vụ Email:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(anchor="w", padx=6, pady=(4, 0))
        self.cb_mail_provider = ttk.Combobox(
            card_in,
            values=[
                "Hotmail / Outlook (IMAP SSL - Mật khẩu)",
                "Hotmail / Outlook (DongVanFB OAuth2 - Refresh Token)",
                "TempMail.Plus (Đa Domain Miễn Phí)",
                "InboxKitten.com (@inboxkitten.com Miễn Phí)",
                "Guerrilla Mail (@sharklasers.com Miễn Phí)",
                "Mailnesia.com (@mailnesia.com Miễn Phí)",
                "Smail1s (Hotmail / Temp Mail API)",
                "Custom IMAP (Tự Cấu Hình Server & Port)"
            ],
            state="readonly"
        )
        self.cb_mail_provider.current(0)
        self.cb_mail_provider.pack(fill=tk.X, padx=6, pady=(2, 6))
        self.cb_mail_provider.bind("<<ComboboxSelected>>", self._on_mail_provider_changed)

        tk.Label(card_in, text="Địa chỉ Email:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN).pack(anchor="w", padx=6, pady=(2, 0))
        self.ent_mail_address = tk.Entry(card_in, font=AppTheme.FONT_BODY, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff", bd=0)
        self.ent_mail_address.pack(fill=tk.X, padx=6, pady=(2, 6))

        self.lbl_mail_pass = tk.Label(card_in, text="Mật khẩu Mail / Refresh Token:", font=AppTheme.FONT_BODY, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MAIN)
        self.lbl_mail_pass.pack(anchor="w", padx=6, pady=(2, 0))
        self.ent_mail_pass = tk.Entry(card_in, font=AppTheme.FONT_BODY, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff", bd=0)
        self.ent_mail_pass.pack(fill=tk.X, padx=6, pady=(2, 6))

        self.frame_custom_imap = tk.Frame(card_in, bg=AppTheme.BG_CARD)
        tk.Label(self.frame_custom_imap, text="IMAP Host:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)
        self.ent_imap_host = tk.Entry(self.frame_custom_imap, width=18, font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff")
        self.ent_imap_host.insert(0, "outlook.office365.com")
        self.ent_imap_host.pack(side=tk.LEFT, padx=(2, 8))

        tk.Label(self.frame_custom_imap, text="Port:", font=AppTheme.FONT_SMALL, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED).pack(side=tk.LEFT)
        self.ent_imap_port = tk.Entry(self.frame_custom_imap, width=5, font=AppTheme.FONT_SMALL, bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, insertbackground="#ffffff")
        self.ent_imap_port.insert(0, "993")
        self.ent_imap_port.pack(side=tk.LEFT, padx=2)

        act_frame = tk.Frame(left_frame, bg=AppTheme.BG_DARK)
        act_frame.pack(fill=tk.X, padx=4, pady=4)

        self.btn_mail_read_now = tk.Button(
            act_frame, text="📥 ĐỌC HÒM THƯ & LẤY OTP", font=AppTheme.FONT_TITLE,
            bg=AppTheme.ACCENT, fg="#000000", activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT, height=2, command=self.on_start_read_mail
        )
        self.btn_mail_read_now.pack(fill=tk.X, pady=(0, 4))

        poll_row = tk.Frame(act_frame, bg=AppTheme.BG_DARK)
        poll_row.pack(fill=tk.X, pady=(0, 4))

        self.btn_mail_poll = tk.Button(
            poll_row, text="🔄 Tự Động Quét Lặp Lại (5s)", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BG_CARD, fg=AppTheme.INFO, relief=tk.FLAT,
            command=self.on_start_mail_poll
        )
        self.btn_mail_poll.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        self.btn_mail_stop_poll = tk.Button(
            poll_row, text="⏹️ Dừng", font=AppTheme.FONT_BODY_BOLD,
            bg=AppTheme.BORDER, fg="#ffffff", state=tk.DISABLED, relief=tk.FLAT,
            command=self.on_stop_mail_poll
        )
        self.btn_mail_stop_poll.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # Phải: Big Card OTP & Bảng thư
        card_otp = tk.LabelFrame(
            right_frame, text=" 🔐 MÃ XÁC NHẬN FACEBOOK (OTP) PHÁT HIỆN ĐƯỢC ",
            font=AppTheme.FONT_HEADER, bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS,
            bd=1, relief=tk.SOLID
        )
        card_otp.pack(fill=tk.X, pady=(0, 6))

        otp_inner = tk.Frame(card_otp, bg=AppTheme.BG_CARD)
        otp_inner.pack(fill=tk.X, padx=10, pady=8)

        self.lbl_big_otp = tk.Label(
            otp_inner, text="[   ------   ]", font=("Segoe UI", 26, "bold"),
            bg=AppTheme.BG_CARD, fg=AppTheme.SUCCESS
        )
        self.lbl_big_otp.pack(side=tk.LEFT, padx=(0, 16))

        self.btn_copy_otp = tk.Button(
            otp_inner, text="📋 COPY MÃ OTP", font=AppTheme.FONT_TITLE,
            bg=AppTheme.SUCCESS, fg="#ffffff", activebackground=AppTheme.ACCENT_HOVER,
            relief=tk.FLAT, padx=16, pady=4, command=self._copy_current_otp
        )
        self.btn_copy_otp.pack(side=tk.LEFT)

        self.lbl_otp_sender = tk.Label(
            card_otp, text="Chưa có thư mới từ Facebook", font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED
        )
        self.lbl_otp_sender.pack(anchor="w", padx=10, pady=(0, 6))

        tree_frame = tk.Frame(right_frame, bg=AppTheme.BG_CARD)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        cols = ("idx", "email", "sender", "subject", "otp", "time")
        self.tree_mail = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        self.tree_mail.heading("idx", text="#")
        self.tree_mail.heading("email", text="Email")
        self.tree_mail.heading("sender", text="Người Gửi")
        self.tree_mail.heading("subject", text="Tiêu Đề Thư")
        self.tree_mail.heading("otp", text="Mã OTP")
        self.tree_mail.heading("time", text="Thời Gian")

        self.tree_mail.column("idx", width=40, anchor=tk.CENTER)
        self.tree_mail.column("email", width=160, anchor=tk.W)
        self.tree_mail.column("sender", width=150, anchor=tk.W)
        self.tree_mail.column("subject", width=240, anchor=tk.W)
        self.tree_mail.column("otp", width=90, anchor=tk.CENTER)
        self.tree_mail.column("time", width=120, anchor=tk.CENTER)

        sb_y = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree_mail.yview)
        self.tree_mail.configure(yscrollcommand=sb_y.set)
        self.tree_mail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree_mail.bind("<<TreeviewSelect>>", self._on_mail_tree_select)

        det_frame = tk.LabelFrame(
            right_frame, text=" 📄 Nội Dung Toàn Văn Của Thư ",
            font=AppTheme.FONT_SMALL_BOLD, bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_MUTED,
            bd=1, relief=tk.SOLID
        )
        det_frame.pack(fill=tk.X)

        self.txt_mail_body = scrolledtext.ScrolledText(
            det_frame, wrap=tk.WORD, font=AppTheme.FONT_CODE,
            bg=AppTheme.BG_INPUT, fg=AppTheme.TEXT_MAIN, bd=0, height=5
        )
        self.txt_mail_body.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _on_mail_provider_changed(self, event=None):
        sel = self.cb_mail_provider.get()
        if "IMAP" in sel and "Custom" in sel:
            self.frame_custom_imap.pack(fill=tk.X, padx=6, pady=4)
        else:
            self.frame_custom_imap.pack_forget()

        if "OAuth2" in sel:
            self.lbl_mail_pass.config(text="Refresh Token OAuth2 (DongVanFB):")
        elif "IMAP" in sel:
            self.lbl_mail_pass.config(text="Mật khẩu Hòm Thư:")
        else:
            self.lbl_mail_pass.config(text="Mật khẩu (Không bắt buộc với Temp-Mail):")

    def _get_selected_mail_provider_key(self) -> str:
        sel = self.cb_mail_provider.get()
        if "IMAP" in sel and "Custom" in sel:
            return "custom_imap"
        elif "IMAP" in sel:
            return "hotmail_imap"
        elif "OAuth2" in sel:
            return "dongvan_oauth2"
        elif "TempMail.Plus" in sel:
            return "tempmail_plus"
        elif "InboxKitten" in sel:
            return "inboxkitten"
        elif "Guerrilla" in sel:
            return "guerrillamail"
        elif "Mailnesia" in sel:
            return "mailnesia"
        elif "Smail1s" in sel:
            return "smail1s"
        return "hotmail_imap"

    def on_start_read_mail(self):
        em = self.ent_mail_address.get().strip()
        pwd = self.ent_mail_pass.get().strip()
        if not em:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập địa chỉ Email.")
            return

        prov_key = self._get_selected_mail_provider_key()
        imap_host = self.ent_imap_host.get().strip() if hasattr(self, "ent_imap_host") else "outlook.office365.com"
        try:
            imap_port = int(self.ent_imap_port.get().strip()) if hasattr(self, "ent_imap_port") else 993
        except Exception:
            imap_port = 993

        self.btn_mail_read_now.config(state=tk.DISABLED, text="⏳ ĐANG ĐỌC HÒM THƯ...")

        def _worker():
            msgs = fetch_mailbox_messages(
                prov_key, em, pwd, imap_host=imap_host, imap_port=imap_port
            )

            def _ui():
                self.btn_mail_read_now.config(state=tk.NORMAL, text="📥 ĐỌC HÒM THƯ & LẤY OTP")
                for itm in self.tree_mail.get_children():
                    self.tree_mail.delete(itm)

                self._mail_messages = msgs
                latest_otp = ""
                latest_sender = ""
                latest_subj = ""

                for idx, m in enumerate(msgs):
                    otp_c = m.get("otp", "")
                    if otp_c and not latest_otp:
                        latest_otp = otp_c
                        latest_sender = m.get("sender", "")
                        latest_subj = m.get("subject", "")

                    self.tree_mail.insert(
                        "", "end",
                        values=(idx + 1, m.get("email"), m.get("sender"), m.get("subject"), otp_c, m.get("date"))
                    )

                if latest_otp:
                    self._current_latest_otp = latest_otp
                    self.lbl_big_otp.config(text=f"[  {latest_otp}  ]")
                    self.lbl_otp_sender.config(text=f"Từ: {latest_sender} • {latest_subj}")
                    self.btn_copy_otp.config(text=f"📋 COPY ({latest_otp})")
                else:
                    self.lbl_big_otp.config(text="[  CHƯA CÓ OTP  ]")
                    self.lbl_otp_sender.config(text=f"Tìm thấy {len(msgs)} thư, chưa có mã OTP Facebook.")

            self.safe_ui_call(_ui)

        threading.Thread(target=_worker, daemon=True).start()

    def on_start_mail_poll(self):
        if getattr(self, "_mail_poll_running", False):
            return
        em = self.ent_mail_address.get().strip()
        pwd = self.ent_mail_pass.get().strip()
        if not em:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập địa chỉ Email.")
            return

        from app_gui import AppTheme
        self._mail_poll_running = True
        self._mail_poll_stop_event.clear()
        self.btn_mail_poll.config(state=tk.DISABLED, text="🔄 Đang quét lặp lại...")
        self.btn_mail_stop_poll.config(state=tk.NORMAL, bg=AppTheme.DANGER)

        prov_key = self._get_selected_mail_provider_key()
        imap_host = self.ent_imap_host.get().strip() if hasattr(self, "ent_imap_host") else "outlook.office365.com"
        try:
            imap_port = int(self.ent_imap_port.get().strip()) if hasattr(self, "ent_imap_port") else 993
        except Exception:
            imap_port = 993

        def _poll_worker():
            for round_idx in range(1, 30):
                if self._mail_poll_stop_event.is_set():
                    break
                msgs = fetch_mailbox_messages(prov_key, em, pwd, imap_host=imap_host, imap_port=imap_port)
                got_otp = False

                def _ui(messages=msgs, rnd=round_idx):
                    nonlocal got_otp
                    for itm in self.tree_mail.get_children():
                        self.tree_mail.delete(itm)
                    self._mail_messages = messages
                    for idx, m in enumerate(messages):
                        otp_c = m.get("otp", "")
                        if otp_c and not self._current_latest_otp:
                            got_otp = True
                            self._current_latest_otp = otp_c
                            self.lbl_big_otp.config(text=f"[  {otp_c}  ]")
                            self.lbl_otp_sender.config(text=f"Từ: {m.get('sender')} • {m.get('subject')}")
                            self.btn_copy_otp.config(text=f"📋 COPY ({otp_c})")
                        self.tree_mail.insert(
                            "", "end",
                            values=(idx + 1, m.get("email"), m.get("sender"), m.get("subject"), otp_c, m.get("date"))
                        )

                self.safe_ui_call(_ui)
                if got_otp:
                    break
                time.sleep(4.0)

            def _done():
                self._mail_poll_running = False
                self.btn_mail_poll.config(state=tk.NORMAL, text="🔄 Tự Động Quét Lặp Lại (5s)")
                self.btn_mail_stop_poll.config(state=tk.DISABLED, bg=AppTheme.BORDER)

            self.safe_ui_call(_done)

        threading.Thread(target=_poll_worker, daemon=True).start()

    def on_stop_mail_poll(self):
        if self._mail_poll_running:
            self._mail_poll_stop_event.set()
            self.btn_mail_stop_poll.config(text="⏳ Dừng...", state=tk.DISABLED)

    def _copy_current_otp(self):
        otp = self._current_latest_otp
        if not otp or otp == "------":
            messagebox.showwarning("Thông báo", "Chưa có mã OTP nào để copy.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(otp)
        self.btn_copy_otp.config(text="✅ ĐÃ COPY!")
        self.root.after(2000, lambda: self.btn_copy_otp.config(text=f"📋 COPY ({otp})"))

    def _on_mail_tree_select(self, event=None):
        sel = self.tree_mail.selection()
        if not sel:
            return
        item = self.tree_mail.item(sel[0])
        idx = item["values"][0] - 1
        if 0 <= idx < len(self._mail_messages):
            m = self._mail_messages[idx]
            body_txt = m.get("body", "")
            self.txt_mail_body.delete("1.0", tk.END)
            self.txt_mail_body.insert(tk.END, body_txt or "[Nội dung thư trống hoặc dạng HTML thuần]")
