# -*- coding: utf-8 -*-
"""
core.nvr_pipeline_bridge

Module cầu nối tự động kết hợp giữa 2 tool:
1. Tool Reg NVR: C:\\Users\\truon\\Downloads\\reg clonefb 2_3 (Chế độ tạo acc NVR)
2. Tool Verry:   C:\\Users\\truon\\Downloads\\verry (Chế độ Xác minh NVR)

Quy trình tự động hóa:
- Khi Tool Reg tạo thành công tài khoản NVR (Chưa xác minh):
  -> Đẩy thông tin tài khoản vào hàng đợi Pipeline kèm mốc thời gian hẹn giờ (ready_at = hiện tại + delay_minutes).
  -> Tự động lưu bản ghi vào C:\\Users\\truon\\Downloads\\verry\\accounts_unverified.txt.
- Sau khi ngấu đủ thời gian hẹn (1 phút, 2 phút, 5 phút, 10 phút... tùy theo setting):
  -> Nếu Tool Verry đang mở giao diện: Tool Verry sẽ tự động kéo tài khoản vào bảng hiển thị và chạy xác minh bằng dàn luồng/proxy của Verry.
  -> Nếu Tool Verry không mở giao diện: Tool Reg sẽ tự động kích hoạt luồng chạy nền xác minh theo đúng file cấu hình (config.json, Proxy, Mail LaoIA/MetaKing...) của bên thư mục Verry.
- Kết quả LIVE được lưu vào C:\\Users\\truon\\Downloads\\verry\\accounts_live.txt và tự up lên Bot Shop (nếu bật).
- Có thể bật/tắt toàn bộ tính năng này linh hoạt trong Cài đặt và Quick Bar.
"""

import os
import sys
import time
import json
import random
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple, Union, Callable

logger = logging.getLogger("nvr_pipeline_bridge")

DEFAULT_VERRY_DIR = r"C:\Users\truon\Downloads\verry"
QUEUE_FILENAME = "pipeline_nvr_queue.json"


def _safe_float(val: Any, default: float = 2.0) -> float:
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip().lower()
        digits = "".join(c for c in val_str if (c.isdigit() or c in (".", ","))).replace(",", ".")
        return float(digits) if digits else default
    except Exception:
        return default


def _safe_int(val: Any, default: int = 50) -> int:
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return int(val)
        val_str = str(val).strip()
        digits = "".join(c for c in val_str if c.isdigit())
        return int(digits) if digits else default
    except Exception:
        return default


class NVRPipelineStorage:
    """Quản lý file JSON hàng đợi đa tiến trình an toàn với cơ chế Atomic Write & File Lock."""

    _mem_lock = threading.Lock()

    @classmethod
    def get_queue_path(cls, verry_dir: str = DEFAULT_VERRY_DIR) -> str:
        v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
        return os.path.join(v_dir, QUEUE_FILENAME)

    @classmethod
    def load_queue(cls, verry_dir: str = DEFAULT_VERRY_DIR) -> Dict[str, Any]:
        q_path = cls.get_queue_path(verry_dir)
        empty_data = {
            "version": "1.0",
            "items": {},
            "stats": {"total_enqueued": 0, "total_live": 0, "total_die": 0},
            "updated_at": time.time()
        }
        if not os.path.exists(q_path):
            return empty_data

        with cls._mem_lock:
            for _ in range(6):
                try:
                    with open(q_path, "r", encoding="utf-8-sig", errors="ignore") as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "items" in data:
                            return data
                except Exception:
                    time.sleep(0.04)
        return empty_data

    @classmethod
    def save_queue(cls, data: Dict[str, Any], verry_dir: str = DEFAULT_VERRY_DIR) -> bool:
        q_path = cls.get_queue_path(verry_dir)
        tmp_path = q_path + f".tmp.{os.getpid()}.{random.randint(1000, 9999)}"
        data["updated_at"] = time.time()

        with cls._mem_lock:
            try:
                os.makedirs(os.path.dirname(q_path), exist_ok=True)
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                for _ in range(6):
                    try:
                        os.replace(tmp_path, q_path)
                        return True
                    except Exception:
                        time.sleep(0.04)
            except Exception as e:
                logger.warning(f"Error saving pipeline queue: {e}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        return False


def is_verry_gui_running(verry_dir: str = DEFAULT_VERRY_DIR) -> bool:
    """Kiểm tra xem Tool Verry (app_gui.py trong thư mục verry) có đang mở không."""
    try:
        import psutil
        norm_target = os.path.normpath(verry_dir).lower()
        current_pid = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
            try:
                if p.info["pid"] == current_pid:
                    continue
                p_name = (p.info.get("name") or "").lower()
                if "python" in p_name:
                    cwd = os.path.normpath(p.info.get("cwd") or "").lower()
                    if cwd == norm_target:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
    except Exception:
        pass
    return False


def enqueue_nvr_account(
    account_data_or_line: Union[str, Dict[str, Any], Any],
    delay_minutes: float = 2.0,
    verry_dir: str = DEFAULT_VERRY_DIR,
    logger_fn: Optional[Callable[[str, str], None]] = None,
) -> bool:
    """
    Đẩy 1 tài khoản NVR vừa reg xong vào hàng đợi chuyển giao sang Tool Verry.
    Tự động tính thời gian ready_at = now + delay_minutes * 60.
    Tự động ghi vào file accounts_unverified.txt của bên Tool Verry.
    """
    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    delay_m = max(0.0, _safe_float(delay_minutes, 2.0))
    now_ts = time.time()
    ready_ts = now_ts + (delay_m * 60.0)

    # 1. Trích xuất UID, Pass, Cookie, Line từ đối tượng hoặc chuỗi
    uid = ""
    pwd = ""
    cookie = ""
    token = ""
    email = ""
    raw_line = ""

    if isinstance(account_data_or_line, str):
        raw_line = account_data_or_line.strip()
        parts = raw_line.split("|")
        if parts:
            uid = parts[0].strip()
            if len(parts) > 1:
                pwd = parts[1].strip()
            if len(parts) > 2:
                for p in parts[2:]:
                    if "c_user=" in p or "xs=" in p or "datr=" in p:
                        cookie = p.strip()
                    elif p.startswith("EAAB"):
                        token = p.strip()
                    elif "@" in p:
                        email = p.strip()
    elif isinstance(account_data_or_line, dict):
        uid = str(account_data_or_line.get("uid") or "").strip()
        pwd = str(account_data_or_line.get("password") or "").strip()
        cookie = str(account_data_or_line.get("cookie") or account_data_or_line.get("cookie_string") or "").strip()
        token = str(account_data_or_line.get("token") or "").strip()
        email = str(account_data_or_line.get("email") or "").strip()
        raw_line = str(account_data_or_line.get("raw_line") or "").strip()
    elif hasattr(account_data_or_line, "uid"):
        uid = str(getattr(account_data_or_line, "uid", "") or "").strip()
        pwd = str(getattr(account_data_or_line, "password", "") or "").strip()
        cookie = str(getattr(account_data_or_line, "cookie_string", "") or getattr(account_data_or_line, "cookie", "") or "").strip()
        token = str(getattr(account_data_or_line, "token", "") or "").strip()
        email = str(getattr(account_data_or_line, "email", "") or getattr(account_data_or_line, "identifier", "") or "").strip()
        if hasattr(account_data_or_line, "format_line"):
            try:
                raw_line = account_data_or_line.format_line("UID|PASS|COOKIE|TOKEN|EMAIL")
            except Exception:
                pass

    if not uid or not uid.isdigit():
        return False

    if not raw_line:
        raw_line = f"{uid}|{pwd}|{cookie}|{token}|{email}"

    # 2. Lưu vào C:\\Users\\truon\\Downloads\\verry\\accounts_unverified.txt
    unver_file = os.path.join(v_dir, "accounts_unverified.txt")
    now_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now_ts))
    try:
        already_in_unver = False
        if os.path.exists(unver_file):
            with open(unver_file, "r", encoding="utf-8-sig", errors="ignore") as f_u:
                for line in f_u:
                    l_s = line.strip()
                    if l_s and (l_s.startswith(f"{uid}|") or f"c_user={uid}" in l_s):
                        already_in_unver = True
                        break
        if not already_in_unver:
            with open(unver_file, "a", encoding="utf-8-sig") as f_u:
                f_u.write(f"{raw_line}|NVR|{now_str}\n")
    except Exception as e_file:
        logger.warning(f"Error appending to verry unverified file: {e_file}")

    # 3. Ghi vào hàng đợi pipeline_nvr_queue.json
    q_data = NVRPipelineStorage.load_queue(v_dir)
    items = q_data.setdefault("items", {})

    existing_item = items.get(uid)
    if existing_item and existing_item.get("status") in ("live", "verified_live"):
        return False

    items[uid] = {
        "uid": uid,
        "password": pwd,
        "cookie": cookie,
        "token": token,
        "email": email,
        "raw_line": raw_line,
        "created_at": now_ts,
        "ready_at": ready_ts,
        "delay_minutes": delay_m,
        "status": "waiting",
        "claimed_by": None,
        "claimed_at": None,
        "verified_at": None,
        "error": None
    }
    q_data["stats"]["total_enqueued"] = len(items)
    NVRPipelineStorage.save_queue(q_data, v_dir)

    delay_desc = f"{int(delay_m)} phút" if delay_m.is_integer() else f"{delay_m} phút"
    ready_time_str = time.strftime("%H:%M:%S", time.localtime(ready_ts))
    log_msg = f"🚀 [Pipeline Verry] Đã chuyển UID [{uid}] sang hàng đợi Verry (Hẹn giờ sau {delay_desc} lúc {ready_time_str} sẽ xác minh)!"
    if logger_fn:
        logger_fn(log_msg, "info")
    else:
        logger.info(log_msg)
    return True


def reset_stuck_processing_accounts(verry_dir: str = DEFAULT_VERRY_DIR, max_age_seconds: float = 60.0) -> int:
    """Reset các tài khoản đang ở trạng thái processing mà chưa hoàn tất về lại waiting."""
    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    q_data = NVRPipelineStorage.load_queue(v_dir)
    items = q_data.get("items", {})
    if not items:
        return 0
    now_ts = time.time()
    reset_cnt = 0
    for uid, item in items.items():
        if item.get("status") == "processing" and not item.get("verified_at"):
            claimed_at = float(item.get("claimed_at") or 0.0)
            if (now_ts - claimed_at) >= max_age_seconds or claimed_at <= 0:
                item["status"] = "waiting"
                item.pop("claimed_by", None)
                item.pop("claimed_at", None)
                reset_cnt += 1
    if reset_cnt > 0:
        NVRPipelineStorage.save_queue(q_data, v_dir)
    return reset_cnt


def claim_ready_accounts(
    verry_dir: str = DEFAULT_VERRY_DIR,
    max_count: int = 50,
    worker_tag: str = "verry_worker"
) -> List[Dict[str, Any]]:
    """
    Rút các tài khoản đã đến hạn (now >= ready_at) từ hàng đợi để đưa vào luồng xác minh.
    Đánh dấu status = 'processing' để tránh bị xử lý trùng lặp.
    """
    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    q_data = NVRPipelineStorage.load_queue(v_dir)
    items = q_data.get("items", {})
    if not items:
        return []

    now_ts = time.time()
    ready_items = []
    for uid, item in items.items():
        st = item.get("status")
        # Hoặc đang chờ và đã đến hạn, hoặc bị treo quá 15 phút (timeout reset)
        is_ready = (st == "waiting" and now_ts >= item.get("ready_at", 0.0))
        is_stuck = (st == "processing" and (now_ts - float(item.get("claimed_at") or 0.0) > 90.0) and not item.get("verified_at"))

        if is_ready or is_stuck:
            item["status"] = "processing"
            item["claimed_by"] = worker_tag
            item["claimed_at"] = now_ts
            ready_items.append(dict(item))
            if len(ready_items) >= max_count:
                break

    if ready_items:
        NVRPipelineStorage.save_queue(q_data, v_dir)
    return ready_items


def mark_account_result(
    uid: str,
    success: bool,
    result_line: str = "",
    verry_dir: str = DEFAULT_VERRY_DIR,
    error: str = "",
    is_checkpoint: bool = False
) -> bool:
    """Cập nhật kết quả sau khi xác minh xong: LIVE hoặc DIE."""
    if not uid:
        return False
    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    q_data = NVRPipelineStorage.load_queue(v_dir)
    items = q_data.get("items", {})
    item = items.get(uid)
    if not item:
        # Nếu chưa có trong queue thì tạo mới
        item = {"uid": uid, "raw_line": result_line}
        items[uid] = item

    now_ts = time.time()
    item["verified_at"] = now_ts
    item["error"] = error

    if success:
        item["status"] = "live"
        q_data["stats"]["total_live"] = q_data["stats"].get("total_live", 0) + 1
        # Ghi vào accounts_live.txt của bên Verry
        live_file = os.path.join(v_dir, "accounts_live.txt")
        try:
            with open(live_file, "a", encoding="utf-8-sig") as f_l:
                f_l.write((result_line or item.get("raw_line", uid)).strip() + "\n")
        except Exception:
            pass
        # Gỡ khỏi accounts_unverified.txt của bên Verry
        _clean_unverified_file(uid, v_dir)
    else:
        item["status"] = "die" if is_checkpoint else "failed"
        q_data["stats"]["total_die"] = q_data["stats"].get("total_die", 0) + 1
        die_file = os.path.join(v_dir, "accounts_die.txt")
        try:
            err_msg = error or "Xác minh thất bại"
            line_out = (result_line or item.get("raw_line", uid)).strip()
            with open(die_file, "a", encoding="utf-8-sig") as f_d:
                f_d.write(f"{line_out}|DIE: {err_msg}\n")
        except Exception:
            pass
        _clean_unverified_file(uid, v_dir)

    NVRPipelineStorage.save_queue(q_data, v_dir)
    return True


def _clean_unverified_file(uid: str, verry_dir: str):
    """Bảo toàn 100% dữ liệu accounts_unverified.txt, không bao giờ xóa acc No-Verify."""
    return


def _clean_unverified_file_bulk(uid_set: set, verry_dir: str):
    """Bảo toàn 100% dữ liệu accounts_unverified.txt, không bao giờ xóa acc No-Verify."""
    return


def remove_accounts_from_pipeline(uids, verry_dir = DEFAULT_VERRY_DIR) -> int:
    """Xóa danh sách UID khỏi hàng đợi pipeline_nvr_queue.json và dọn khỏi accounts_unverified.txt."""
    if not uids:
        return 0
    if isinstance(uids, str):
        uid_set = {uids.strip()}
    else:
        uid_set = {str(u).strip() for u in uids if str(u).strip() and str(u).strip() != "N/A"}
    if not uid_set:
        return 0

    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    q_data = NVRPipelineStorage.load_queue(v_dir)
    items = q_data.get("items", {})
    removed = 0
    for u in uid_set:
        if u in items:
            del items[u]
            removed += 1

    _clean_unverified_file_bulk(uid_set, v_dir)

    if removed > 0:
        q_data["stats"]["total_enqueued"] = len(items)
        NVRPipelineStorage.save_queue(q_data, v_dir)
    return removed


def clear_pipeline_queue(verry_dir = DEFAULT_VERRY_DIR) -> bool:
    """Xóa toàn bộ hàng đợi pipeline_nvr_queue.json."""
    v_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
    empty_data = {
        "version": "1.0",
        "items": {},
        "stats": {"total_enqueued": 0, "total_live": 0, "total_die": 0},
        "updated_at": time.time()
    }
    return NVRPipelineStorage.save_queue(empty_data, v_dir)


def get_pipeline_summary(verry_dir: str = DEFAULT_VERRY_DIR) -> Dict[str, int]:
    """Lấy số lượng tổng quan hàng đợi: chờ, đang xử lý, đã live, đã die."""
    q_data = NVRPipelineStorage.load_queue(verry_dir)
    items = q_data.get("items", {})
    now_ts = time.time()

    waiting = 0
    maturing = 0
    processing = 0
    live = 0
    die = 0

    for item in items.values():
        st = item.get("status")
        if st == "waiting":
            if now_ts >= item.get("ready_at", 0.0):
                waiting += 1
            else:
                maturing += 1
        elif st == "processing":
            processing += 1
        elif st in ("live", "verified_live"):
            live += 1
        elif st in ("die", "failed"):
            die += 1

    return {
        "waiting": waiting,
        "maturing": maturing,
        "processing": processing,
        "live": live,
        "die": die,
        "total": len(items)
    }


class StandaloneVerryEngine:
    """
    Tiến trình chạy nền độc lập bên trong Tool Reg khi Tool Verry không mở.
    Tự động đọc cấu hình config.json của bên Thư mục Verry (KiotProxy, Mail LaoIA/MetaKing...)
    để xác minh đúng chuẩn cài đặt của Tool Verry.
    """

    _instance: Optional["StandaloneVerryEngine"] = None
    _init_lock = threading.Lock()

    def __init__(self, verry_dir: str = DEFAULT_VERRY_DIR, threads: int = 50):
        self.verry_dir = verry_dir if os.path.exists(verry_dir) else DEFAULT_VERRY_DIR
        self.threads = max(1, min(500, threads))
        self.is_running = False
        self.stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._logger_callback: Optional[Callable[[str, str], None]] = None

    @classmethod
    def get_instance(cls, verry_dir: str = DEFAULT_VERRY_DIR, threads: int = 50) -> "StandaloneVerryEngine":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls(verry_dir, threads)
            return cls._instance

    def set_logger(self, callback: Callable[[str, str], None]):
        self._logger_callback = callback

    def log(self, msg: str, tag: str = "info"):
        if self._logger_callback:
            try:
                self._logger_callback(msg, tag)
            except Exception:
                pass
        else:
            logger.info(f"[{tag.upper()}] {msg}")

    def load_verry_config(self) -> Dict[str, Any]:
        cfg_p = os.path.join(self.verry_dir, "config.json")
        if os.path.exists(cfg_p):
            try:
                with open(cfg_p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="StandaloneVerryEngine")
        self._worker_thread.start()
        self.log(f"⚡ [Pipeline Verry] Đã khởi động luồng xác minh nền tự động ({self.threads} luồng verry)...", "info")

    def stop(self):
        self.is_running = False
        self.stop_event.set()

    def _run_loop(self):
        while not self.stop_event.is_set():
            # Nếu người dùng đã mở giao diện Tool Verry riêng, nhường quyền cho giao diện Verry
            if is_verry_gui_running(self.verry_dir):
                self.stop_event.wait(timeout=3.0)
                continue

            ready_accs = claim_ready_accounts(self.verry_dir, max_count=min(self.threads, 30), worker_tag="standalone_engine")
            if not ready_accs:
                self.stop_event.wait(timeout=2.0)
                continue

            # Nạp cấu hình từ Tool Verry
            verry_cfg = self.load_verry_config()
            v_prov = verry_cfg.get("proxy_provider", "kiotproxy")
            v_keys = verry_cfg.get(f"{v_prov}_keys", [])
            v_srv = verry_cfg.get("email_service", "laoia_domain")
            v_doms = verry_cfg.get("selected_custom_domains", ["laoia.com"])
            save_fmt = verry_cfg.get("save_format", "UID|PASS|COOKIE|TOKEN|EMAIL")

            # Xử lý song song các tài khoản đã ngấu đủ thời gian
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=min(len(ready_accs), self.threads)) as executor:
                futures = []
                for idx, acc in enumerate(ready_accs):
                    futures.append(executor.submit(self._verify_one_account, acc, idx, verry_cfg, v_prov, v_keys, v_srv, v_doms, save_fmt))
                for f in futures:
                    try:
                        f.result()
                    except Exception as ex:
                        logger.warning(f"Error in standalone verify worker: {ex}")

            self.stop_event.wait(timeout=1.0)

    def _verify_one_account(self, acc: dict, worker_idx: int, verry_cfg: dict, v_prov: str, v_keys: list, v_srv: str, v_doms: list, save_fmt: str):
        uid = acc.get("uid", "")
        if not uid:
            return

        from core.nvr_verifier import verify_single_nvr_account
        from core.email_service import get_email_provider
        from core.models import RegistrationInput

        # Phân bổ proxy KiotProxy / ProxyVN theo đúng setting của bên Verry
        proxy_item = None
        if v_keys and v_prov in ("kiotproxy", "kiotproxy_current"):
            try:
                from core.proxy_manager import KiotProxyClient, ProxyManager
                k = v_keys[worker_idx % len(v_keys)]
                kc = KiotProxyClient(k)
                p_inf = kc.get_current_proxy(force_refresh=True)
                if not p_inf or not p_inf.get("http"):
                    p_inf = kc.get_new_proxy(fallback_current=True)
                if p_inf and p_inf.get("http"):
                    proxy_item = ProxyManager.parse_proxy(p_inf["http"])
            except Exception:
                pass
        elif v_prov == "proxyvn":
            try:
                from core.proxy_manager import ProxyVNClient, ProxyManager
                pvn_keys = verry_cfg.get("proxyvn_keys", [])
                if pvn_keys:
                    k = pvn_keys[worker_idx % len(pvn_keys)]
                    pvn_c = ProxyVNClient(k)
                    p_inf = pvn_c.get_current_proxy()
                    if not p_inf or not p_inf.get("http"):
                        p_inf = pvn_c.get_new_proxy()
                    if p_inf and p_inf.get("http"):
                        proxy_item = ProxyManager.parse_proxy(p_inf["http"])
            except Exception:
                pass

        try:
            email_prov = get_email_provider(v_srv, selected_domains=v_doms)
        except Exception:
            email_prov = None

        task_in = RegistrationInput(
            proxy=proxy_item,
            device_type="mr_sxr",
            locale="vi_VN",
            password=acc.get("password"),
            extra={
                "worker_id": worker_idx + 1,
                "reg_mode": "verify_nvr",
                "email_service": v_srv,
                "selected_domains": v_doms,
                "otp_timeout": verry_cfg.get("otp_timeout", 25),
                "save_format": save_fmt,
            }
        )

        self.log(f"🔄 [Pipeline Verry] Bắt đầu xác minh UID [{uid}] qua {v_prov} ({v_srv})...", "info")
        try:
            res = verify_single_nvr_account(
                account_data=acc,
                email_provider=email_prov,
                task_input=task_in,
                emit_callback=lambda evt, data: None
            )
            if res.success:
                rec_line = res.format_line(save_fmt) if hasattr(res, "format_line") else f"{uid}|{acc.get('password')}|{res.cookie_string}"
                mark_account_result(uid, success=True, result_line=rec_line, verry_dir=self.verry_dir)
                self.log(f"🎉 [Pipeline Verry] ✅ XÁC MINH LIVE THÀNH CÔNG UID: {uid} -> Đã lưu accounts_live.txt (Verry)!", "success")
                # Tự động up lên Bot nếu cấu hình Bot trong verry bật
                if verry_cfg.get("bot_auto_upload"):
                    self._upload_account_to_bot(res, verry_cfg, acc)
            else:
                err_msg = res.error_message or "Checkpoint"
                mark_account_result(uid, success=False, result_line=acc.get("raw_line", uid), verry_dir=self.verry_dir, error=err_msg, is_checkpoint=True)
                self.log(f"⚠️ [Pipeline Verry] UID [{uid}] không live: {err_msg} -> Đã lưu accounts_die.txt", "warning")
        except Exception as e:
            mark_account_result(uid, success=False, verry_dir=self.verry_dir, error=str(e))
            self.log(f"❌ [Pipeline Verry] Lỗi xác minh UID [{uid}]: {e}", "error")

    def _upload_account_to_bot(self, result, verry_cfg: dict, acc: Optional[dict] = None):
        """Đẩy nick LIVE lên Bot Shop nếu cấu hình verry có bật bot_auto_upload."""
        try:
            import urllib.request
            api_url = verry_cfg.get("bot_api_url", "https://shopcl.onrender.com").rstrip("/")
            api_key = verry_cfg.get("bot_api_key", "MatKhauAdminCuaBan123")
            media_id = verry_cfg.get("bot_media_id", "")
            if not media_id:
                return

            uid = str(getattr(result, "uid", "")).strip()
            pwd = str(getattr(result, "password", "")).strip() or (str(acc.get("password", "")).strip() if (acc and isinstance(acc, dict)) else "") or str(verry_cfg.get("default_password", "")).strip() or "FacebookPassword123"
            cookie = str(getattr(result, "cookie_string", "")).strip()
            if not cookie and hasattr(result, "cookies") and result.cookies:
                if isinstance(result.cookies, dict):
                    cookie = "; ".join([f"{k}={v}" for k, v in result.cookies.items()])
                elif isinstance(result.cookies, str):
                    cookie = str(result.cookies)
            if uid and cookie and "c_user=" not in cookie:
                cookie = f"c_user={uid}; {cookie}"
            if not uid or not pwd or not cookie:
                return

            cat_name = "Clone Facebook"
            subcat_name = "Clone Facebook"
            price = 0.02
            try:
                lookup_url = f"{api_url}/api/subcategory/lookup-media-id"
                headers_l = {"Content-Type": "application/json", "x-api-key": api_key, "User-Agent": "RegFB-BotUpload-Client/1.0"}
                req_l = urllib.request.Request(lookup_url, data=json.dumps({"media_id": media_id}).encode("utf-8"), headers=headers_l, method="POST")
                with urllib.request.urlopen(req_l, timeout=8) as r_l:
                    if r_l.status == 200:
                        d_l = json.loads(r_l.read().decode("utf-8"))
                        sc_l = d_l.get("subcategory", {})
                        if sc_l:
                            subcat_name = sc_l.get("name") or subcat_name
                            cat_name = sc_l.get("category_name") or cat_name
                            price = float(sc_l.get("price") or price)
            except Exception:
                pass

            payload = {
                "media_id": media_id,
                "category_name": cat_name,
                "subcategory_name": subcat_name,
                "price": price,
                "description": "Tài khoản Clone Facebook reg tự động từ Tool",
                "items": [f"{uid}|{pwd}|{cookie}"],
                "check_live": False,
                "is_facebook": False
            }
            req = urllib.request.Request(
                f"{api_url}/api/items/bulk-upload",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-api-key": api_key},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                self.log(f"🤖 [Bot Shop] ✅ Đã tự up thành công UID [{uid}] (uid|pass|cookie) vào thư mục [{subcat_name}] (Media ID: {media_id[:12]}...)!", "success")
        except Exception as e:
            logger.warning(f"Failed to upload account to bot: {e}")
