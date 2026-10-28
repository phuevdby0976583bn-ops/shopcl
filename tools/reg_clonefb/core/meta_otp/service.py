# -*- coding: utf-8 -*-
"""
service.py - High-level Meta AI Auto OTP Orchestrator Service.
Supports Multi-threaded API and Selenium Modes with Live Event Callbacks.
"""

import os
import sys
import time
import random
import threading
from typing import List, Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

from core.meta_otp.phone_loader import read_numbers, clean_and_validate
from core.meta_otp.user_agents import get_user_agent_by_profile, get_random_user_agent, USER_AGENT_PROFILES
from core.meta_otp.shared_core import (
    save_remaining_numbers,
    save_failed_number,
    save_success_number,
    file_lock,
)

SUCCESS_FILE = "Success_Numbers.txt"
FAILED_FILE = "Failed_Numbers.txt"
REMAINING_FILE = "Number_List.txt"


@dataclass
class MetaOtpResult:
    """Execution result for a single phone number."""
    phone: str
    success: bool = False
    status: str = "failed"
    account_id: Optional[str] = None
    resends_completed: int = 0
    error_message: Optional[str] = None
    proxy: Optional[str] = None
    user_agent: Optional[str] = None
    elapsed_seconds: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_proxy_to_dict(proxy_input: Any) -> Optional[Dict[str, str]]:
    """Normalize proxy string, ProxyItem or dict to requests proxies dict."""
    if not proxy_input:
        return None
    if isinstance(proxy_input, dict):
        if "http" in proxy_input or "https" in proxy_input:
            return proxy_input
        return None
    if hasattr(proxy_input, "to_requests_dict"):
        return proxy_input.to_requests_dict()
    if hasattr(proxy_input, "as_url"):
        u = proxy_input.as_url()
        return {"http": u, "https": u}
    p_str = str(proxy_input).strip()
    if not p_str or p_str.lower() in ("none", "direct"):
        return None
    if "://" not in p_str:
        parts = p_str.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            url = f"http://{user}:{pwd}@{ip}:{port}"
        elif len(parts) == 2:
            ip, port = parts
            url = f"http://{ip}:{port}"
        else:
            return None
    else:
        url = p_str
    return {"http": url, "https": url}

class MetaOtpService:
    """
    Central service for Meta AI OTP triggering and management.
    Handles thread pools, proxy rotation, event emitting, and result logging.
    """

    def __init__(self, event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None):
        self.event_callback = event_callback
        self.stop_event = threading.Event()
        self.is_running = False

        self.total_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.running_count = 0
        self.counter_lock = threading.Lock()

    def stop(self):
        """Stop any running batch execution."""
        self.stop_event.set()
        self.is_running = False
        self._emit("stopped", {"message": "Tiến trình Meta OTP đã được yêu cầu dừng!"})

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.event_callback:
            try:
                self.event_callback(event_type, data)
            except Exception:
                pass

    def reset_stats(self, total: int = 0):
        with self.counter_lock:
            self.total_count = total
            self.success_count = 0
            self.failed_count = 0
            self.running_count = 0

    def run_single(
        self,
        phone: str,
        mode: str = "api",
        user_agent_profile: str = "random",
        proxy: Optional[Any] = None,
        resend_count: int = 1,
        browser: str = "chrome",
        headless: bool = True,
    ) -> MetaOtpResult:
        """Run OTP trigger on a single phone number."""
        from core.meta_otp.api_engine import process_number as api_process_number
        from core.meta_otp.selenium_engine import process_number as sel_process_number

        cleaned = clean_and_validate(phone)
        if not cleaned:
            return MetaOtpResult(phone=phone, success=False, status="error", error_message="Số điện thoại không hợp lệ")

        ua = get_user_agent_by_profile(user_agent_profile)
        p_dict = normalize_proxy_to_dict(proxy)
        p_disp = "Direct"
        if p_dict and "http" in p_dict:
            p_disp = p_dict["http"].split("@")[-1].replace("http://", "").replace("https://", "")

        t0 = time.time()
        self._emit("row_start", {"phone": cleaned, "mode": mode, "proxy": p_disp})

        try:
            if mode == "selenium":
                sel_process_number(
                    number=cleaned,
                    user_agent=ua,
                    proxy=p_dict,
                    resend_count=resend_count,
                    headless=headless,
                    browser=browser,
                )
            else:
                api_process_number(
                    number=cleaned,
                    user_agent=ua,
                    proxy=p_dict,
                    resend_count=resend_count,
                )

            is_success = False
            if os.path.exists(SUCCESS_FILE):
                try:
                    with open(SUCCESS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [x.strip() for x in f if x.strip()]
                        if cleaned in lines or any(cleaned in l for l in lines[-20:]):
                            is_success = True
                except Exception:
                    pass

            elapsed = round(time.time() - t0, 2)
            if is_success:
                res = MetaOtpResult(phone=cleaned, success=True, status="success", proxy=p_disp, user_agent=ua, elapsed_seconds=elapsed)
                self._emit("row_success", {"phone": cleaned, "proxy": p_disp, "elapsed": elapsed})
            else:
                res = MetaOtpResult(phone=cleaned, success=False, status="failed", proxy=p_disp, user_agent=ua, elapsed_seconds=elapsed, error_message="Gửi OTP không thành công hoặc số đã có tài khoản")
                self._emit("row_failed", {"phone": cleaned, "proxy": p_disp, "elapsed": elapsed})
            return res

        except Exception as ex:
            elapsed = round(time.time() - t0, 2)
            res = MetaOtpResult(phone=cleaned, success=False, status="error", proxy=p_disp, error_message=str(ex), elapsed_seconds=elapsed)
            self._emit("row_error", {"phone": cleaned, "proxy": p_disp, "error": str(ex)})
            return res

    def run_batch(
        self,
        numbers: List[str],
        mode: str = "api",
        threads: int = 10,
        user_agent_profile: str = "random",
        resend_count: int = 1,
        browser: str = "chrome",
        headless: bool = True,
        proxy_provider: str = "none",
        custom_proxies: Optional[List[str]] = None,
    ):
        """Run batch processing on list of phone numbers with multi-threading."""
        if not numbers:
            self._emit("log", {"message": "Danh sách số điện thoại rỗng!", "tag": "warning"})
            return

        valid_numbers = []
        for n in numbers:
            c = clean_and_validate(n)
            if c and c not in valid_numbers:
                valid_numbers.append(c)

        if not valid_numbers:
            self._emit("log", {"message": "Không tìm thấy số điện thoại hợp lệ nào!", "tag": "warning"})
            return

        self.reset_stats(len(valid_numbers))
        self.stop_event.clear()
        self.is_running = True

        self._emit("log", {
            "message": f"[Meta AI Auto OTP] Khởi chạy {threads} Luồng | Chế độ: {mode.upper()} | Tổng {len(valid_numbers)} SĐT | Resend: {resend_count}",
            "tag": "info"
        })

        proxy_pool = []
        if custom_proxies:
            for cp in custom_proxies:
                p_item = normalize_proxy_to_dict(cp)
                if p_item:
                    proxy_pool.append(p_item)
        elif proxy_provider == "proxy_list":
            p_file = "proxy.txt" if os.path.exists("proxy.txt") else ("proxies.txt" if os.path.exists("proxies.txt") else "")
            if p_file:
                try:
                    with open(p_file, "r", encoding="utf-8") as pf:
                        for line in pf:
                            p_item = normalize_proxy_to_dict(line.strip())
                            if p_item:
                                proxy_pool.append(p_item)
                except Exception:
                    pass

        remaining = list(valid_numbers)
        save_remaining_numbers(remaining)

        from core.meta_otp.api_engine import process_number as api_process_number
        from core.meta_otp.selenium_engine import process_number as sel_process_number

        def worker_task(num: str, worker_idx: int):
            if self.stop_event.is_set():
                return

            with self.counter_lock:
                self.running_count += 1
            self._emit("stats_update", {
                "total": self.total_count,
                "success": self.success_count,
                "failed": self.failed_count,
                "running": self.running_count
            })

            cur_proxy = None
            if proxy_pool:
                cur_proxy = proxy_pool[worker_idx % len(proxy_pool)]

            p_disp = "Direct"
            if cur_proxy and "http" in cur_proxy:
                p_disp = cur_proxy["http"].split("@")[-1].replace("http://", "").replace("https://", "")

            ua = get_user_agent_by_profile(user_agent_profile)
            t0 = time.time()

            self._emit("task_status", {
                "phone": num,
                "worker_id": worker_idx + 1,
                "proxy": p_disp,
                "status": "Đang xử lý...",
                "tag": "running"
            })

            try:
                if mode == "selenium":
                    sel_process_number(
                        number=num,
                        user_agent=ua,
                        proxy=cur_proxy,
                        resend_count=resend_count,
                        headless=headless,
                        browser=browser,
                    )
                else:
                    api_process_number(
                        number=num,
                        user_agent=ua,
                        proxy=cur_proxy,
                        resend_count=resend_count,
                    )

                is_success = False
                if os.path.exists(SUCCESS_FILE):
                    try:
                        with open(SUCCESS_FILE, "r", encoding="utf-8", errors="ignore") as f:
                            lines = [x.strip() for x in f if x.strip()]
                            if num in lines or any(num in l for l in lines[-20:]):
                                is_success = True
                    except Exception:
                        pass

                elapsed = round(time.time() - t0, 2)
                with self.counter_lock:
                    if is_success:
                        self.success_count += 1
                        st_text = f"OTP Gửi Thành Công (+{resend_count} resend)"
                        st_tag = "success"
                    else:
                        self.failed_count += 1
                        st_text = "Thất Bại / Acc Đã Có"
                        st_tag = "failed"
                    self.running_count = max(0, self.running_count - 1)

                self._emit("task_status", {
                    "phone": num,
                    "worker_id": worker_idx + 1,
                    "proxy": p_disp,
                    "status": st_text,
                    "tag": st_tag,
                    "elapsed": elapsed
                })
                self._emit("stats_update", {
                    "total": self.total_count,
                    "success": self.success_count,
                    "failed": self.failed_count,
                    "running": self.running_count
                })

            except Exception as e:
                elapsed = round(time.time() - t0, 2)
                with self.counter_lock:
                    self.failed_count += 1
                    self.running_count = max(0, self.running_count - 1)
                self._emit("task_status", {
                    "phone": num,
                    "worker_id": worker_idx + 1,
                    "proxy": p_disp,
                    "status": f"Lỗi: {str(e)[:35]}",
                    "tag": "error",
                    "elapsed": elapsed
                })
                self._emit("stats_update", {
                    "total": self.total_count,
                    "success": self.success_count,
                    "failed": self.failed_count,
                    "running": self.running_count
                })

            finally:
                with file_lock:
                    if num in remaining:
                        remaining.remove(num)
                save_remaining_numbers(remaining)

        with ThreadPoolExecutor(max_workers=max(1, threads)) as executor:
            futures = []
            for idx, n in enumerate(valid_numbers):
                if self.stop_event.is_set():
                    break
                f = executor.submit(worker_task, n, idx)
                futures.append(f)

            for f in as_completed(futures):
                if self.stop_event.is_set():
                    break

        self.is_running = False
        self._emit("log", {
            "message": f"[Meta AI Auto OTP] HOÀN TẤT TIẾN TRÌNH: Tổng {self.total_count} SĐT | Thành công: {self.success_count} | Thất bại: {self.failed_count}",
            "tag": "success"
        })
        self._emit("batch_done", {
            "total": self.total_count,
            "success": self.success_count,
            "failed": self.failed_count
        })
