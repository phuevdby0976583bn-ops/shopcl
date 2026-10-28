# -*- coding: utf-8 -*-
"""
core.ttc_pipeline_bridge

Tich hop hoan hao giua 2 du an:
1. reg clonefb 2: Tao tai khoan Facebook Live (UID | Pass | 2FA | Cookie | Token)
2. tds-ttc-tool-main:
   - Buoc 1: Tu dong doi thong tin (Them Avatar + Anh bia) bang FacebookInfoChanger
   - Buoc 2: Tu dong cau hinh vao tai khoan TuongTacCheo khong bi trung thoi diem voi bat ky nick FB nao khac (1 TTC : 1 FB tai 1 thoi diem)
   - Buoc 3: Nap tai khoan vao danh muc Cay Xu (category = 'cay_xu' trong app_data.db)
   - Buoc 4: Tu dong cay xu theo dung cau hinh & cai dat trong TTC PRO (top_config_panel)
"""

import os
import sys
import time
import json
import uuid
import random
import logging
import sqlite3
import threading
from typing import Optional, Dict, Any, Tuple, List, Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("ttc_pipeline_bridge")

DEFAULT_REG_PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_TTC_PROJECT_DIR = r"C:\Users\truon\Downloads\tds-ttc-tool-main\tds-ttc-tool-main"
DEFAULT_PHOTOS_DIR = r"C:\Users\truon\Downloads\photos\female"

for _p in (DEFAULT_TTC_PROJECT_DIR, DEFAULT_REG_PROJECT_DIR):
    if _p in sys.path:
        sys.path.remove(_p)

if os.path.exists(DEFAULT_TTC_PROJECT_DIR):
    sys.path.insert(0, DEFAULT_TTC_PROJECT_DIR)
if os.path.exists(DEFAULT_REG_PROJECT_DIR):
    sys.path.insert(0, DEFAULT_REG_PROJECT_DIR)

try:
    import core
    ttc_core_p = os.path.join(DEFAULT_TTC_PROJECT_DIR, "core")
    if os.path.exists(ttc_core_p) and hasattr(core, "__path__") and ttc_core_p not in core.__path__:
        core.__path__.append(ttc_core_p)
except Exception:
    pass


def _safe_int(v, default=0) -> int:
    try:
        if isinstance(v, (int, float)):
            return int(v)
        if not v:
            return default
        return int(float(str(v).replace(",", "").strip()))
    except Exception:
        return default


def _calculate_humanized_delay(min_sec: float, max_sec: float, fallback: float = 0.0) -> float:
    low = min(float(min_sec), float(max_sec))
    high = max(float(min_sec), float(max_sec))
    if high <= 0.0:
        return max(0.0, float(fallback))
    base = random.uniform(low, high)
    jitter = random.uniform(0.05, 0.45)
    total = round(base + jitter, 2)
    if random.random() < 0.04 and low >= 1.0:
        total += round(random.uniform(2.0, 5.0), 2)
    return total


class TTCPipelineBridge:
    """Singleton bridge quan ly luong khep kin tu Reg Live -> Doi Info -> Gan TTC (Khong trung thoi diem) -> Cay Xu."""

    _instance: Optional["TTCPipelineBridge"] = None
    _init_lock = threading.Lock()

    def __init__(self, ttc_dir: str = DEFAULT_TTC_PROJECT_DIR, photos_dir: str = DEFAULT_PHOTOS_DIR):
        self.ttc_dir = ttc_dir if os.path.exists(ttc_dir) else DEFAULT_TTC_PROJECT_DIR
        self.photos_dir = photos_dir if os.path.exists(photos_dir) else DEFAULT_PHOTOS_DIR
        self.db_path = os.path.join(self.ttc_dir, "app_data.db")

        if self.ttc_dir not in sys.path:
            sys.path.append(self.ttc_dir)
        try:
            import core
            ttc_core_p = os.path.join(self.ttc_dir, "core")
            if os.path.exists(ttc_core_p) and hasattr(core, "__path__") and ttc_core_p not in core.__path__:
                core.__path__.append(ttc_core_p)
        except Exception:
            pass

        self._pipeline_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="TTCPipeline")
        self._farming_executor = ThreadPoolExecutor(max_workers=30, thread_name_prefix="TTCFarmer")

        self._ttc_assign_lock = threading.Lock()
        self._claimed_ttc_users = set()
        self._running_farm_ttc_users = set()
        self._running_farm_uids = set()
        self._stop_farming_flag = False
        self._kiot_manager = None

    @classmethod
    def get_instance(cls, ttc_dir: str = DEFAULT_TTC_PROJECT_DIR, photos_dir: str = DEFAULT_PHOTOS_DIR) -> "TTCPipelineBridge":
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = cls(ttc_dir, photos_dir)
            return cls._instance

    def is_available(self) -> bool:
        return os.path.exists(self.ttc_dir) and os.path.exists(self.db_path)

    def get_db(self):
        from app.storage.database import DatabaseManager
        return DatabaseManager.get_instance(self.db_path)

    def get_adapter(self):
        from app.backend_adapter.adapter import UnifiedBackendAdapter
        return UnifiedBackendAdapter()

    def get_kiot_manager(self):
        if self._kiot_manager is None:
            try:
                from app.services.kiot_proxy_service import KiotProxyManager
                self._kiot_manager = KiotProxyManager(self.get_db())
                self._kiot_manager.load_settings()
            except Exception as e:
                logger.warning(f"Khong the khoi tao KiotProxyManager: {e}")
        return self._kiot_manager

    def get_kiot_current_proxy(self, uid_or_acc: str, max_age_seconds: Optional[float] = None) -> Tuple[Optional[str], Optional[Any], str]:
        """Lay Proxy HIEN TAI (GET /current) cua Key KiotProxy duoc gan cho nick (tuyet doi khong goi /new)."""
        mgr = self.get_kiot_manager()
        if mgr and mgr.keys:
            return mgr.get_current_proxy_for_account(str(uid_or_acc), max_age_seconds=max_age_seconds)
        return None, None, "Chua cau hinh KiotProxy"

    @staticmethod
    def is_ttc_pro_gui_running() -> bool:
        """Kiem tra xem giao dien TTC PRO (run_app.py) co dang mo khong."""
        try:
            import psutil
            for p in psutil.process_iter(['name', 'cmdline']):
                cmdline = p.info.get('cmdline') or []
                cmd_str = ' '.join(cmdline).lower()
                if 'run_app.py' in cmd_str or ('main_window' in cmd_str and 'tds-ttc' in cmd_str):
                    return True
        except Exception:
            pass
        return False

    def _log(self, callback: Optional[Callable], message: str, level: str = "info"):
        prefix = "[TTC Pipeline] "
        full_msg = prefix + message
        if level == "error":
            logger.error(full_msg)
        elif level == "warning":
            logger.warning(full_msg)
        else:
            logger.info(full_msg)
        if callable(callback):
            try:
                callback(full_msg, level)
            except Exception:
                pass

    # =========================================================================
    # BUOC 1: TU DONG CHANGE INFO (AVATAR + COVER) TU THU MUC ANH
    # =========================================================================
    def execute_change_info(
        self,
        uid: str,
        password: str = "",
        cookie: str = "",
        token: str = "",
        proxy: Optional[str] = None,
        log_callback: Optional[Callable] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Su dung FacebookInfoChanger tu tds-ttc-tool-main de nap Avatar + Anh bia."""
        if not cookie and not token:
            msg = f"Nick [{uid}] thieu Cookie va Access Token de doi avatar/bia"
            self._log(log_callback, msg, "warning")
            return False, msg, {}

        if not os.path.exists(self.photos_dir):
            msg = f"Thu muc anh khong ton tai: {self.photos_dir}"
            self._log(log_callback, msg, "warning")
            return False, msg, {}

        try:
            from app.services.account_info_service import FacebookInfoChanger
            from app.services.page_creator_service import get_random_image_from_folder
        except ImportError as e:
            msg = f"Khong the import module doi info tu TTC: {e}"
            self._log(log_callback, msg, "error")
            return False, msg, {}

        avt_path = get_random_image_from_folder(self.photos_dir)
        cover_path = get_random_image_from_folder(self.photos_dir)
        if avt_path and cover_path and avt_path == cover_path:
            cover_path = get_random_image_from_folder(self.photos_dir)

        if not avt_path or not cover_path:
            msg = f"Khong tim thay anh hop le trong thu muc {self.photos_dir}"
            self._log(log_callback, msg, "warning")
            return False, msg, {}

        # Luon uu tien lay Proxy HIEN TAI cua Key KiotProxy (tuyet doi khong goi /new)
        eff_proxy = proxy
        k_px, k_res, k_msg = self.get_kiot_current_proxy(uid)
        if k_px:
            eff_proxy = k_px
            self._log(log_callback, f"[{uid}] 🌐 Su dung KiotProxy hien tai: {eff_proxy} ({k_msg})")
        elif eff_proxy:
            self._log(log_callback, f"[{uid}] 🌐 Su dung Proxy duoc cung cap: {eff_proxy}")
        else:
            self._log(log_callback, f"[{uid}] ⚠️ Khong co proxy, chay IP truc tiep", "warning")

        self._log(log_callback, f"[{uid}] Bat dau doi Avatar & Anh bia... (Avt: {os.path.basename(avt_path)} | Bia: {os.path.basename(cover_path)})")

        try:
            changer = FacebookInfoChanger(
                cookie=cookie,
                token=token,
                user_id=uid,
                password=password,
                proxy=eff_proxy
            )

            res = changer.process_change_info(
                do_change_name=False,
                do_change_avatar=True,
                avatar_path=avt_path,
                do_change_cover=True,
                cover_path=cover_path,
                do_enable_2fa=False,
                human_delay=False,
                status_callback=lambda m, c="#eab308": self._log(log_callback, f"[{uid}] {m}")
            )

            avt_ok = res.get("avatar_changed", False)
            cover_ok = res.get("cover_changed", False)

            if avt_ok and cover_ok:
                succ_msg = f"[{uid}] Cap nhat Avatar va Anh bia thanh cong 100%!"
                self._log(log_callback, succ_msg, "info")
                return True, succ_msg, res
            elif avt_ok or cover_ok:
                part_msg = f"[{uid}] Da doi: Avatar={avt_ok}, Bia={cover_ok}"
                self._log(log_callback, part_msg, "info")
                return True, part_msg, res
            else:
                err_msg = res.get("error") or "Khong the tai anh len Facebook"
                self._log(log_callback, f"[{uid}] Doi info that bai: {err_msg}", "warning")
                return False, err_msg, res

        except Exception as e:
            err_msg = f"[{uid}] Ngoai le khi doi Avatar/Bia: {e}"
            self._log(log_callback, err_msg, "error")
            return False, err_msg, {}

    # =========================================================================
    # BUOC 2: CAU HINH TTC - 1 TAI KHOAN TTC : 1 TAI KHOAN FB TAI 1 THOI DIEM
    # =========================================================================
    def allocate_and_configure_ttc(
        self,
        uid: str,
        password: str = "",
        two_fa: str = "",
        cookie: str = "",
        token: str = "",
        proxy: Optional[str] = None,
        fb_name: str = "",
        log_callback: Optional[Callable] = None
    ) -> Tuple[bool, Optional[Any], str]:
        """
        Chon 1 tai khoan TTC kha dung tai thoi diem hien tai (TUYET DOI KHONG TRUNG THOI DIEM):
        - Tai thoi diem nay: 1 TTC chi gan va chay dung 1 Facebook duy nhat.
        - Tai thoi diem khac: Khi nick FB cu da DIE / Checkpoint / Dung hoac TTC chua tung co UID,
          TTC do hoan toan duoc phep tai su dung de gan cho nick FB Live moi nay.
        """
        if not uid:
            return False, None, "Thieu UID Facebook"

        # Neu chua co proxy, lay Proxy HIEN TAI tu KiotProxy
        eff_proxy = proxy
        if not eff_proxy:
            k_px, _, _ = self.get_kiot_current_proxy(uid)
            if k_px:
                eff_proxy = k_px

        assigned_user_ttc = None
        assigned_pass_ttc = None
        assigned_acc_id = None
        cand_ua = None
        cand_source = "fresh"

        with self._ttc_assign_lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)
                cur = conn.cursor()

                # 1. Quet tat ca cac tai khoan TTC DANG CO FB LIVE CHAY tai thoi diem nay
                cur.execute("""
                SELECT DISTINCT user_ttc FROM accounts
                WHERE category = 'cay_xu'
                  AND is_stopped = 0
                  AND status_fb = 'Live'
                  AND user_ttc IS NOT NULL
                  AND user_ttc != ''
                  AND current_status NOT LIKE '%Die%'
                  AND current_status NOT LIKE '%Checkpoint%'
                """)
                db_busy = {r[0] for r in cur.fetchall() if r[0]}
                busy_ttc = db_busy | self._claimed_ttc_users | self._running_farm_ttc_users

                # Chien luoc 1: Chon tai khoan TTC sach chua tung gan UID nao (uu tien cao nhat)
                cur.execute("""
                SELECT id, user_ttc, pass_ttc, user_agent
                FROM accounts
                WHERE category = 'quan_ly_nick'
                  AND (uid_fb IS NULL OR uid_fb = '')
                  AND user_ttc IS NOT NULL AND user_ttc != ''
                ORDER BY
                  CASE
                    WHEN user_ttc LIKE 'truongdvmmo%' THEN CAST(SUBSTR(user_ttc, 12) AS INTEGER)
                    ELSE 999999
                  END ASC
                LIMIT 200
                """)
                fresh_candidates = cur.fetchall()
                for cand in fresh_candidates:
                    c_id, c_user, c_pass, c_ua = cand
                    if c_user and c_user not in busy_ttc:
                        assigned_acc_id = c_id
                        assigned_user_ttc = c_user
                        assigned_pass_ttc = c_pass
                        cand_ua = c_ua
                        cand_source = "fresh"
                        break

                # Chien luoc 2: Neu khong co candidate fresh, tai su dung nick TTC co FB cu da DIE / DUNG
                if not assigned_user_ttc:
                    cur.execute("""
                    SELECT id, user_ttc, pass_ttc, user_agent
                    FROM accounts
                    WHERE category = 'cay_xu'
                      AND (is_stopped = 1 OR status_fb IN ('Die', 'Checkpoint', 'Lỗi') OR current_status LIKE '%Die%' OR current_status LIKE '%Checkpoint%')
                      AND user_ttc IS NOT NULL AND user_ttc != ''
                    ORDER BY updated_at ASC
                    LIMIT 200
                    """)
                    reused_candidates = cur.fetchall()
                    for cand in reused_candidates:
                        c_id, c_user, c_pass, c_ua = cand
                        if c_user and c_user not in busy_ttc:
                            assigned_acc_id = c_id
                            assigned_user_ttc = c_user
                            assigned_pass_ttc = c_pass
                            cand_ua = c_ua
                            cand_source = "reused"
                            break

                # Chien luoc 3: Quet toan bo quan_ly_nick tim bat ky TTC nao khong ban
                if not assigned_user_ttc:
                    cur.execute("""
                    SELECT id, user_ttc, pass_ttc, user_agent
                    FROM accounts
                    WHERE category = 'quan_ly_nick'
                      AND user_ttc IS NOT NULL AND user_ttc != ''
                    ORDER BY updated_at ASC
                    LIMIT 200
                    """)
                    all_ql = cur.fetchall()
                    for cand in all_ql:
                        c_id, c_user, c_pass, c_ua = cand
                        if c_user and c_user not in busy_ttc:
                            assigned_acc_id = c_id
                            assigned_user_ttc = c_user
                            assigned_pass_ttc = c_pass
                            cand_ua = c_ua
                            cand_source = "reused_ql"
                            break

                if not assigned_user_ttc:
                    conn.close()
                    msg = "Tat ca tai khoan TuongTacCheo deu dang co Facebook chay tai thoi diem nay!"
                    self._log(log_callback, msg, "error")
                    return False, None, msg

                # Danh dau lock ngay lap tuc de khong luong nao tranh chap
                self._claimed_ttc_users.add(assigned_user_ttc)

                # Cap nhat vao quan_ly_nick
                now_ts = time.time()
                cur.execute(
                    """
                    UPDATE accounts
                    SET uid_fb = ?, pass_fb = ?, two_fa_fb = ?, cookie_fb = ?,
                        token_platform = ?, proxy = ?, status_fb = 'Live',
                        status_platform = 'Dang cau hinh', updated_at = ?
                    WHERE user_ttc = ?
                    """,
                    (uid, password, two_fa, cookie, token or "", eff_proxy or "", now_ts, assigned_user_ttc)
                )
                conn.commit()
                conn.close()

            except Exception as e:
                msg = f"Loi truy van tai khoan TTC tu DB: {e}"
                self._log(log_callback, msg, "error")
                return False, None, msg

        log_extra = "(Tai su dung tu nick FB cu da Dung/Die)" if cand_source != "fresh" else "(TTC moi hoan toan)"
        self._log(log_callback, f"[{uid}] Da chon TTC [{assigned_user_ttc}] {log_extra}. Dang cau hinh len TTC Web...")

        from app.models.account_model import AccountItem, PlatformType
        eff_ua = cand_ua
        if not eff_ua:
            try:
                from app.utils.user_agents import get_or_assign_user_agent
                temp_acc = AccountItem(id=assigned_acc_id, uid_fb=uid, user_ttc=assigned_user_ttc)
                eff_ua = get_or_assign_user_agent(temp_acc, self.get_db(), category="auto", force=False)
            except Exception:
                eff_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

        # Goi Adapter cau hinh nick Facebook chay tren TuongTacCheo Web
        adapter = self.get_adapter()
        cfg_ok, cfg_msg = adapter.config_facebook_id_ttc_web(
            fb_id=uid,
            username=assigned_user_ttc,
            password=assigned_pass_ttc,
            proxy=eff_proxy,
            user_agent=eff_ua,
            fb_name=fb_name
        )

        if not cfg_ok and eff_proxy:
            self._log(log_callback, f"[{uid}] Cau hinh qua Proxy that bai ({cfg_msg}) -> Thu lai ngay bang Direct IP...", "warning")
            cfg_ok, cfg_msg = adapter.config_facebook_id_ttc_web(
                fb_id=uid,
                username=assigned_user_ttc,
                password=assigned_pass_ttc,
                proxy=None,
                user_agent=eff_ua,
                fb_name=fb_name
            )

        status_plat = "Da cau hinh" if cfg_ok else f"Loi cau hinh: {cfg_msg[:30]}"
        if cfg_ok:
            self._log(log_callback, f"[{uid}] Cau hinh TTC [{assigned_user_ttc}] thanh cong: {cfg_msg}", "info")
        else:
            self._log(log_callback, f"[{uid}] Cau hinh TTC [{assigned_user_ttc}] phan hoi: {cfg_msg}", "warning")

        # Cap nhat trang thai quan_ly_nick
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cur = conn.cursor()
            cur.execute(
                "UPDATE accounts SET status_platform = ?, user_agent = ?, updated_at = ? WHERE user_ttc = ?",
                (status_plat, eff_ua, time.time(), assigned_user_ttc)
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

        # =====================================================================
        # BUOC 3: DONG BO VA LUU VAO DANH MUC CAY XU (category = 'cay_xu')
        # =====================================================================
        db = self.get_db()
        existing_in_cay_xu = [a for a in db.get_accounts_cay_xu() if a.user_ttc == assigned_user_ttc]
        if existing_in_cay_xu:
            # Tai su dung dung dong record cay_xu cho TTC nay (thay the UID FB cu da die/dung bang UID FB live moi)
            cay_xu_acc = existing_in_cay_xu[0]
            cay_xu_acc.uid_fb = uid
            cay_xu_acc.pass_fb = password
            cay_xu_acc.two_fa_fb = two_fa
            cay_xu_acc.cookie_fb = cookie
            if token:
                cay_xu_acc.token_platform = token
            cay_xu_acc.proxy = eff_proxy or ""
            cay_xu_acc.user_agent = eff_ua
            cay_xu_acc.status_fb = "Live"
            cay_xu_acc.status_platform = status_plat
            cay_xu_acc.current_status = "San sang"
            cay_xu_acc.current_job = "---"
            cay_xu_acc.is_stopped = False
            cay_xu_acc.selected = True
            cay_xu_acc.notes = f"TTC gan FB moi [{uid}] (khong trung thoi diem)"
            cay_xu_acc.updated_at = time.time()
            db.save_account(cay_xu_acc)
        else:
            # Chen record moi vao cay_xu
            cay_xu_acc = AccountItem(
                id=str(uuid.uuid4())[:8],
                selected=True,
                uid_fb=uid,
                pass_fb=password,
                two_fa_fb=two_fa,
                cookie_fb=cookie,
                token_platform=token or "",
                platform_type=PlatformType.TTC,
                user_ttc=assigned_user_ttc,
                pass_ttc=assigned_pass_ttc,
                proxy=eff_proxy or "",
                user_agent=eff_ua,
                status_fb="Live",
                status_platform=status_plat,
                current_status="San sang",
                current_job="---",
                coin=0,
                category="cay_xu",
                notes=f"TTC gan FB moi [{uid}] (khong trung thoi diem)"
            )
            db.save_account(cay_xu_acc)

        self._log(log_callback, f"[{uid}] Da dong bo vao danh muc Cay Xu voi TTC [{assigned_user_ttc}]")
        return True, cay_xu_acc, f"Da gan thanh cong vao TTC [{assigned_user_ttc}]"

    # =========================================================================
    # BUOC 4: TIEN HANH CAY XU THEO DUNG SETTING CUA TTC PRO
    # =========================================================================
    def start_farming_account(self, acc: Any, log_callback: Optional[Callable] = None):
        """Khoi chay luong cay xu doc lap cho tai khoan vua gan, tuan thu 100% cau hinh top_config_panel."""
        if not acc or not acc.uid_fb:
            return

        if acc.uid_fb in self._running_farm_uids or acc.user_ttc in self._running_farm_ttc_users:
            self._log(log_callback, f"[{acc.uid_fb}] Tai khoan da co tien trinh cay xu dang chay tai thoi diem nay.")
            return

        db = self.get_db()
        cfg_raw = db.get_setting("top_config_panel", "{}")
        cfg = {}
        try:
            cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else (cfg_raw or {})
        except Exception:
            cfg = {}

        self._farming_executor.submit(self._run_farming_loop, acc, cfg, log_callback)

    def _run_farming_loop(self, acc: Any, cfg: Dict[str, Any], log_callback: Optional[Callable] = None):
        """Worker thuc thi cac job TTC theo dung cau hinh he thong TTC PRO."""
        uid = str(acc.uid_fb or acc.id)
        user_ttc = str(acc.user_ttc or "")
        self._running_farm_uids.add(uid)
        if user_ttc:
            self._running_farm_ttc_users.add(user_ttc)
        db = self.get_db()

        try:
            self._log(log_callback, f"[{uid}] Bat dau chu trinh Cay Xu TTC ({user_ttc})...")
            db.update_account_field_sync(acc.id, "current_status", "Dang khoi dong cay xu...")

            from tuongtaccheo import Tuongtaccheo
            from FacebookAPI import FacebookAPI

            eff_proxy = acc.proxy.strip() if acc.proxy and acc.proxy.strip() else None
            eff_ua = acc.user_agent.strip() if acc.user_agent and acc.user_agent.strip() else None

            # 1. Dang nhap TuongTacCheo
            ttc = Tuongtaccheo(
                token=acc.token_platform,
                proxy=eff_proxy,
                user_agent=eff_ua,
                username=acc.user_ttc,
                password=acc.pass_ttc
            )
            login_res = ttc.login()
            login_ok = bool(getattr(login_res, "success", False) or getattr(login_res, "status", False))
            if not login_ok and eff_proxy:
                self._log(log_callback, f"[{uid}] Login TTC qua proxy loi -> Doi Direct IP...", "warning")
                ttc = Tuongtaccheo(
                    token=acc.token_platform,
                    proxy=None,
                    user_agent=eff_ua,
                    username=acc.user_ttc,
                    password=acc.pass_ttc
                )
                login_res = ttc.login()
                login_ok = bool(getattr(login_res, "success", False) or getattr(login_res, "status", False))

            if not login_ok:
                err_login = getattr(login_res, "error", "") or getattr(login_res, "msg", "") or "Sai thong tin TTC"
                self._log(log_callback, f"[{uid}] Dang nhap TTC that bai: {err_login}", "error")
                db.update_account_field_sync(acc.id, "current_status", f"Loi login TTC: {err_login}")
                return

            init_coin = ttc.get_balance()
            if init_coin >= 0:
                acc.coin = init_coin
                db.update_account_field_sync(acc.id, "coin", init_coin)

            # 2. Khoi tao Facebook API va dat nick chay
            fb = FacebookAPI(cookie=acc.cookie_fb, proxy=eff_proxy, user_agent=eff_ua)
            cfg_res = ttc.config(uid)
            cfg_is_ok = bool(getattr(cfg_res, "success", False) or getattr(cfg_res, "status", False))
            if not cfg_is_ok:
                adapter = self.get_adapter()
                adapter.config_facebook_id_ttc_web(uid, acc.user_ttc, acc.pass_ttc, proxy=eff_proxy, user_agent=eff_ua)
                time.sleep(1.0)
                ttc.config(uid)

            # 3. Doc danh sach job trong top_config_panel
            jobs_cfg = cfg.get("jobs", {})
            max_job_total = _safe_int(cfg.get("max_job", 2000), 2000)
            max_xu_total = _safe_int(cfg.get("max_xu", 100000000), 100000000)
            delay_get = float(cfg.get("delay_get", 0.0) or 0.0)
            delay_claim = float(cfg.get("delay_claim", 0.5) or 0.5)

            candidate_tasks = [
                ("likepostvipcheo", "Like bai VIP"),
                ("camxucvipcheo", "Cam xuc VIP"),
                ("likepostvipre", "Like VIP Re"),
                ("camxucvipre", "Cam xuc VIP Re"),
                ("camxuccheobinhluan", "Cam xuc cmt"),
                ("subcheo", "Theo doi"),
                ("subcheofbvip", "Follow VIP"),
                ("likepagecheo", "Like Page"),
                ("sharecheokemnoidung", "Share kem nd"),
                ("thamgianhomcheo", "Tham gia nhom"),
                ("cmtcheo", "Binh luan"),
                ("danhgiapage", "Danh gia Page"),
                ("sharecheo", "Chia se")
            ]

            active_tasks = []
            for t_key, t_name in candidate_tasks:
                j_info = jobs_cfg.get(t_key, {})
                if isinstance(j_info, dict) and j_info.get("checked", True):
                    active_tasks.append((t_key, t_name, j_info))
                elif not jobs_cfg:
                    active_tasks.append((t_key, t_name, {"from": 0, "to": 0, "max": 50, "fail": 5}))

            if not active_tasks:
                self._log(log_callback, f"[{uid}] Khong co loai nhiem vu nao duoc chon trong Cai dat Cay Xu!", "warning")
                db.update_account_field_sync(acc.id, "current_status", "Chua bat loai job nao")
                return

            total_done = 0
            fail_streak = 0
            stop_fail_limit = _safe_int(cfg.get("stop_fail_limit", 15), 15)
            mgr = self.get_kiot_manager()
            refresh_sec = float(getattr(mgr, "refresh_interval_min", 3) or 3) * 60.0 if mgr else 180.0
            last_proxy_refresh = time.time()

            self._log(log_callback, f"[{uid}] Bat dau vong lap kiem xu (Toi da: {max_job_total} jobs | Muc tieu xu: {max_xu_total:,})")

            while not self._stop_farming_flag and total_done < max_job_total:
                # Tu dong kiem tra va cap nhat Proxy Kiot hien tai dinh ky
                if (time.time() - last_proxy_refresh) >= refresh_sec:
                    last_proxy_refresh = time.time()
                    try:
                        k_px_curr, _, _ = self.get_kiot_current_proxy(uid, max_age_seconds=refresh_sec)
                        if k_px_curr and k_px_curr != eff_proxy:
                            self._log(log_callback, f"[{uid}] 🔄 KiotProxy tu dong cap nhat IP hien tai: {eff_proxy} -> {k_px_curr}")
                            eff_proxy = k_px_curr
                            acc.proxy = eff_proxy
                            db.update_account_field_sync(acc.id, "proxy", eff_proxy)
                            from app.utils.proxy_formatter import format_proxy_dict
                            fb.proxies = format_proxy_dict(eff_proxy)
                            if hasattr(fb, "session") and hasattr(fb.session, "proxies"):
                                fb.session.proxies = fb.proxies
                    except Exception as ex_k:
                        self._log(log_callback, f"[{uid}] Loi kiem tra proxy Kiot dinh ky: {ex_k}", "warning")
                if acc.coin >= max_xu_total:
                    self._log(log_callback, f"[{uid}] Da dat muc tieu xu ({acc.coin:,} >= {max_xu_total:,})!")
                    break

                task_progress = False

                for t_key, t_name, t_cfg in active_tasks:
                    if self._stop_farming_flag or total_done >= max_job_total:
                        break

                    db.update_account_field_sync(acc.id, "current_status", f"Dang lay job {t_name}...")
                    if delay_get > 0:
                        time.sleep(delay_get)

                    job_res = ttc.get_job(t_key)
                    job_ok = bool(getattr(job_res, "success", False) or getattr(job_res, "status", False))
                    if not job_ok or not getattr(job_res, "data", None):
                        continue

                    jobs_list = job_res.data if isinstance(job_res.data, list) else [job_res.data]
                    if not jobs_list:
                        continue

                    task_progress = True
                    for job in jobs_list:
                        if self._stop_farming_flag or total_done >= max_job_total:
                            break

                        job_id = getattr(job, "id", None) or getattr(job, "idJob", None) or (job.get("id") if isinstance(job, dict) else str(job))
                        if not job_id:
                            continue

                        db.update_account_field_sync(acc.id, "current_job", f"{t_name} ({job_id})")
                        db.update_account_field_sync(acc.id, "current_status", f"Dang lam {t_name}: {job_id}...")

                        action_ok = False
                        try:
                            if "like" in t_key or "vip" in t_key:
                                action_ok = fb.reaction(job_id, "LIKE")
                            elif "camxuc" in t_key:
                                r_type = getattr(job, "type", "LIKE") or getattr(job, "typeExecute", "LIKE") or "LIKE"
                                action_ok = fb.reaction(job_id, str(r_type).upper())
                            elif "sub" in t_key or "follow" in t_key:
                                action_ok = fb.follow(job_id)
                            elif "page" in t_key:
                                action_ok = fb.like_page(job_id)
                            elif "share" in t_key:
                                action_ok = fb.share(job_id)
                            elif "nhom" in t_key or "group" in t_key:
                                action_ok = fb.join_page(job_id)
                            elif "cmt" in t_key or "comment" in t_key:
                                cmt_msg = getattr(job, "message", "Tuyet voi!") or getattr(job, "msgExecute", "Tuyet voi!") or "Tuyet voi!"
                                action_ok = fb.comment(job_id, cmt_msg)
                            else:
                                action_ok = fb.reaction(job_id, "LIKE")
                        except Exception:
                            action_ok = False

                        min_d = float(t_cfg.get("from", 0.0) or 0.0)
                        max_d = float(t_cfg.get("to", 0.0) or 0.0)
                        delay_action = _calculate_humanized_delay(min_d, max_d, fallback=0.5)
                        if delay_action > 0:
                            time.sleep(delay_action)

                        if action_ok:
                            fail_streak = 0
                            if delay_claim > 0:
                                time.sleep(delay_claim)

                            rx_res = ttc.receive_coin(job)
                            rx_ok = bool(getattr(rx_res, "success", False) or getattr(rx_res, "status", False))
                            if rx_ok:
                                total_done += 1
                                rx_data = getattr(rx_res, "data", None)
                                earned = _safe_int(getattr(rx_data, "coin", 0) or getattr(rx_data, "xu", 0) or getattr(rx_res, "coin", 0), 0)
                                if earned > 0:
                                    acc.coin += earned
                                else:
                                    cur_bal = ttc.get_balance()
                                    if cur_bal > 0:
                                        acc.coin = cur_bal

                                acc.success_count = getattr(acc, "success_count", 0) + 1
                                self._log(log_callback, f"[{uid}] {t_name} #{total_done} thanh cong! +{earned} xu (Tong: {acc.coin:,})")
                                db.update_account_field_sync(acc.id, "coin", acc.coin)
                                db.update_account_field_sync(acc.id, "success_count", acc.success_count)
                                db.update_account_field_sync(acc.id, "current_status", f"Da xong {t_name} | Xu: {acc.coin:,}")
                            else:
                                total_done += 1
                                db.update_account_field_sync(acc.id, "current_status", f"Lam xong {t_name} (cho nhan xu)")
                        else:
                            fail_streak += 1
                            acc.fail_count = getattr(acc, "fail_count", 0) + 1
                            db.update_account_field_sync(acc.id, "fail_count", acc.fail_count)
                            db.update_account_field_sync(acc.id, "current_status", f"Loi lam {t_name} ({fail_streak}/{stop_fail_limit})")

                            if cfg.get("stop_fail_series", False) and fail_streak >= stop_fail_limit:
                                self._log(log_callback, f"[{uid}] Da cham nguong {fail_streak} loi lien tiep -> Dung cay xu cho FB nay!", "warning")
                                db.update_account_field_sync(acc.id, "current_status", f"Dung: {fail_streak} loi lien tiep")
                                db.update_account_field_sync(acc.id, "is_stopped", 1)
                                return

                if not task_progress:
                    time.sleep(3.0)

            db.update_account_field_sync(acc.id, "current_status", f"Hoan thanh phien cay | Tong xu: {acc.coin:,}")
            self._log(log_callback, f"[{uid}] Hoan tat phien cay xu. Tong xu tich luy: {acc.coin:,}")

        except Exception as e:
            err_str = f"[{uid}] Loi trong luong cay xu: {e}"
            self._log(log_callback, err_str, "error")
            db.update_account_field_sync(acc.id, "current_status", f"Loi cay xu: {str(e)[:30]}")

        finally:
            self._running_farm_uids.discard(uid)
            if user_ttc:
                self._running_farm_ttc_users.discard(user_ttc)
                self._claimed_ttc_users.discard(user_ttc)

    # =========================================================================
    # DIEU PHOI TOAN BO QUY TRINH (MAIN ENTRY POINT CHO LIVE FB ACCOUNT)
    # =========================================================================
    def enqueue_live_account_for_ttc(
        self,
        result: Any,
        proxy_str: str = "",
        log_callback: Optional[Callable] = None
    ) -> bool:
        """
        BÀN GIAO SIÊU TỐC CHO TTC PRO (NON-BLOCKING / ZERO-OVERHEAD):
        - Chỉ ghi trực tiếp thông tin nick Live vào SQLite app_data.db (danh mục 'cay_xu').
        - Trạng thái: 'Chờ xử lý (TTC PRO)' (is_stopped = 0, status_fb = 'Live').
        - Thời gian thực thi cực nhanh: < 5ms.
        - Tool Reg HOÀN TOÀN KHÔNG PHẢI chạy change info, KHÔNG gọi web TTC, KHÔNG cày xu.
        - Tool Reg giữ 100% tài nguyên CPU/RAM/Thread để tiếp tục reg acc với tốc độ tối đa!
        - TTC PRO (giao diện đang mở) sẽ tự động quét thấy nick sau 2s và đảm nhiệm toàn bộ:
          Đổi Avatar/Bìa -> Gán TTC -> Cấu hình Web -> Cày Xu.
        """
        if isinstance(result, dict):
            uid = str(result.get("uid") or "").strip()
            pwd = str(result.get("password") or "").strip()
            two_fa = str(result.get("two_factor_secret") or result.get("2fa") or "").strip()
            cookie = str(result.get("cookie_string") or result.get("cookie") or "").strip()
            token = str(result.get("token") or "").strip()
        else:
            uid = str(getattr(result, "uid", "") or "").strip()
            pwd = str(getattr(result, "password", "") or "").strip()
            two_fa = str(getattr(result, "two_factor_secret", "") or getattr(result, "two_fa", "") or "").strip()
            cookie = str(getattr(result, "cookie_string", "") or getattr(result, "cookie", "") or "").strip()
            token = str(getattr(result, "token", "") or "").strip()

        if not uid and "c_user=" in cookie:
            import re
            m = re.search(r"c_user=(\d+)", cookie)
            if m:
                uid = m.group(1)

        if not uid or not cookie:
            self._log(log_callback, "[Pipeline] Bỏ qua vì tài khoản không có UID hoặc Cookie hợp lệ.", "warning")
            return False

        # Kiểm tra cấu hình: Nếu người dùng KHÔNG tích chọn tự chạy xu thì tuyệt đối không bàn giao
        try:
            cfg_p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
            if os.path.exists(cfg_p):
                with open(cfg_p, "r", encoding="utf-8-sig") as f_cfg:
                    cfg_d = json.load(f_cfg)
                    if not cfg_d.get("auto_ttc_pipeline", False):
                        self._log(log_callback, f"[{uid}] ⏸️ Chế độ tự chạy xu khi reg xong đang TẮT -> Bỏ qua không cày xu.")
                        return False
        except Exception:
            pass

        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.execute("PRAGMA busy_timeout = 30000;")
            cur = conn.cursor()
            now_ts = time.time()
            acc_id = str(uuid.uuid4())[:8]

            cur.execute("SELECT id FROM accounts WHERE uid_fb = ? AND category = 'cay_xu'", (uid,))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE accounts
                    SET pass_fb = ?, two_fa_fb = ?, cookie_fb = ?, token_platform = ?,
                        proxy = ?, status_fb = 'Live', status_platform = 'Chờ xử lý (TTC PRO)',
                        current_status = 'Chờ xử lý (TTC PRO)', is_stopped = 0, updated_at = ?
                    WHERE uid_fb = ? AND category = 'cay_xu'
                """, (pwd, two_fa, cookie, token or "", proxy_str or "", now_ts, uid))
            else:
                cur.execute("""
                    INSERT INTO accounts (
                        id, selected, uid_fb, pass_fb, two_fa_fb, cookie_fb, token_platform,
                        platform_type, user_ttc, pass_ttc, proxy, user_agent,
                        status_fb, status_platform, current_status, current_job,
                        coin, success_count, fail_count, is_stopped, category, notes,
                        created_at, updated_at
                    ) VALUES (
                        ?, 1, ?, ?, ?, ?, ?,
                        'ttc', '', '', ?, '',
                        'Live', 'Chờ xử lý (TTC PRO)', 'Chờ xử lý (TTC PRO)', '---',
                        0, 0, 0, 0, 'cay_xu', 'Nick Live từ Tool Reg - Chờ TTC PRO xử lý',
                        ?, ?
                    )
                """, (
                    acc_id, uid, pwd, two_fa, cookie, token or "",
                    proxy_str or "", now_ts, now_ts
                ))
            conn.commit()
            conn.close()

            self._log(log_callback, f"[{uid}] ⚡ Đã bàn giao sang CSDL TTC PRO thành công! (TTC PRO sẽ tự động Đổi Info ➔ Gán TTC ➔ Cày Xu)")
            return True
        except Exception as e:
            self._log(log_callback, f"[{uid}] Lỗi bàn giao sang DB TTC PRO: {e}", "error")
            return False

    def process_live_account(
        self,
        result: Any,
        proxy_str: str = "",
        log_callback: Optional[Callable] = None
    ) -> bool:
        """Bàn giao siêu tốc nick Live sang CSDL TTC PRO (app_data.db)."""
        return self.enqueue_live_account_for_ttc(result, proxy_str=proxy_str, log_callback=log_callback)

    def process_live_account_async(
        self,
        result: Any,
        proxy_str: str = "",
        log_callback: Optional[Callable] = None
    ):
        """Chay bat dong bo trong ThreadPool de khong lam block giao dien hay luong Reg."""
        self._pipeline_executor.submit(
            self.process_live_account,
            result,
            proxy_str,
            log_callback
        )

    def stop_all_farming(self):
        """Dung tat ca cac luong cay xu dang hoat dong."""
        self._stop_farming_flag = True
