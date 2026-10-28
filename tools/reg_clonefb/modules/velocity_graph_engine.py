# -*- coding: utf-8 -*-
"""
modules/velocity_graph_engine.py
Nghiên cứu & đo đạc đồ thị thiết bị & vận tốc hành động (Velocity & Graph Analysis):
1. Quy luật xả pin & nhiệt độ CPU/cảm biến vật lý (Battery Discharge & Thermal Fluctuation).
2. Vòng đời ứng dụng Android (Activity Lifecycle: onResume, onPause, onStop).
3. Kiểm soát vận tốc hành động (Token Bucket & Leaky Bucket Rate Limiting).
4. Phân tích đồ thị liên kết thiết bị & cụm IP (Device Graph & Sybil Cluster Analysis).
"""

import math
import random
import time
from typing import Dict, Any, List, Optional, Tuple


class BatteryThermalEngine:
    """Mô phỏng và thẩm định dữ liệu xả pin, nhiệt độ và cảm biến môi trường vật lý."""

    def __init__(self, initial_battery: Optional[float] = None, initial_temp: float = 33.2):
        self.battery_level = initial_battery if initial_battery is not None else round(random.uniform(62.0, 89.0), 1)
        self.temperature = initial_temp
        self.start_timestamp = time.time()
        self.last_update = self.start_timestamp
        self.is_charging = False
        self.ambient_lux = random.uniform(180.0, 360.0)

    def tick(self, elapsed_seconds: float = 2.0, cpu_workload: str = "normal") -> Dict[str, Any]:
        """
        Cập nhật trạng thái hao pin và biến thiên nhiệt độ:
        - cpu_workload == "heavy" (ví dụ: mã hóa RSA-2048, bắt tay TLS): Tăng nhiệt độ và tiêu tốn pin nhanh hơn.
        """
        now = time.time()
        # Mức hao pin cơ bản: 0.1% mỗi phút khi sáng màn hình
        base_drain_per_sec = (random.uniform(0.08, 0.14) / 60.0)
        if cpu_workload == "heavy":
            base_drain_per_sec *= 2.5
            temp_delta = random.uniform(0.15, 0.45)
        else:
            temp_delta = random.uniform(-0.08, 0.12)

        drain = base_drain_per_sec * elapsed_seconds
        self.battery_level = max(5.0, round(self.battery_level - drain, 2))

        # Dao động nhiệt độ tự nhiên (31.0°C - 39.5°C)
        self.temperature = round(max(31.0, min(39.5, self.temperature + temp_delta)), 1)

        # Cảm biến ánh sáng dao động nhẹ theo môi trường
        self.ambient_lux = round(max(20.0, self.ambient_lux + random.uniform(-8.0, 8.0)), 1)
        self.last_update = now

        # Điện áp pin theo đường cong hóa học Li-ion (3.65V đến 4.35V)
        voltage_mv = int(3650 + (self.battery_level / 100.0) * 650)


        return {
            "battery_percent": self.battery_level,
            "battery_temp_celsius": self.temperature,
            "battery_voltage_mv": voltage_mv,
            "charging_status": "CHARGING" if self.is_charging else "DISCHARGING",
            "ambient_light_lux": self.ambient_lux,
            "proximity_distance_cm": 5.0,  # 5.0 cm = không che cảm biến tiệm cận
            "cpu_workload": cpu_workload,
        }

    def tick_elapsed(self, elapsed_minutes: float = 1.0, cpu_workload: str = "normal") -> Dict[str, Any]:
        return self.tick(elapsed_seconds=elapsed_minutes * 60.0, cpu_workload=cpu_workload)

    @classmethod
    def audit_telemetry_authenticity(cls, telemetry_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Phát hiện bot/máy ảo dựa trên sự thiếu tự nhiên của telemetry:
        - Máy ảo hoặc tool giả lập thường báo cố định 100% pin, nhiệt độ 25.0°C hoặc 0.0°C không đổi.
        - Không có bất kỳ độ biến thiên (variance = 0) nào về ánh sáng hoặc nhiệt độ.
        """
        if len(telemetry_history) < 2:
            return {"is_authentic": True, "risk_score": 0.0, "reason": "INSUFFICIENT_DATA"}

        battery_vals = [p.get("battery_percent", 100.0) for p in telemetry_history]
        temp_vals = [p.get("battery_temp_celsius", 25.0) for p in telemetry_history]
        lux_vals = [p.get("ambient_light_lux", 100.0) for p in telemetry_history]

        violations = []
        risk_score = 0.0

        # Kiểm tra pin luôn 100% không đổi
        if all(b == 100.0 for b in battery_vals):
            violations.append("STATIC_100_PERCENT_BATTERY")
            risk_score += 0.45

        # Kiểm tra nhiệt độ phẳng (variance == 0)
        temp_variance = max(temp_vals) - min(temp_vals)
        if temp_variance == 0.0:
            violations.append("ZERO_THERMAL_VARIANCE")
            risk_score += 0.35

        # Kiểm tra cảm biến ánh sáng phẳng
        lux_variance = max(lux_vals) - min(lux_vals)
        if lux_variance == 0.0:
            violations.append("ZERO_LIGHT_SENSOR_VARIANCE")
            risk_score += 0.30

        total_risk = min(1.0, round(risk_score, 2))
        is_clean = total_risk < 0.35

        return {
            "is_authentic": is_clean,
            "risk_score": total_risk,
            "violations": violations,
            "verdict": "REAL_PHYSICAL_BATTERY" if is_clean else "VIRTUAL_OR_STATIC_TELEMETRY"
        }


class ActivityLifecycleManager:
    """Mô phỏng máy trạng thái Vòng đời ứng dụng Android (Activity Lifecycle State Machine)."""

    STATES = ["INITIALIZED", "CREATED", "STARTED", "RESUMED", "PAUSED", "STOPPED", "DESTROYED"]

    def __init__(self):
        self.current_state = "INITIALIZED"
        self.history: List[Dict[str, Any]] = []
        self._record_transition("INITIALIZED")

    def _record_transition(self, new_state: str, context_note: str = ""):
        self.current_state = new_state
        self.history.append({
            "timestamp": time.time(),
            "state": new_state,
            "context": context_note
        })

    def on_create(self, note: str = "App Cold Start"):
        self._record_transition("CREATED", note)

    def on_start(self, note: str = "Screen Displayed"):
        self._record_transition("STARTED", note)

    def on_resume(self, note: str = "Active User Interaction"):
        self._record_transition("RESUMED", note)

    def on_pause(self, note: str = "Backgrounded for External App / OTP check"):
        self._record_transition("PAUSED", note)

    def on_stop(self, note: str = "Activity Fully Hidden"):
        self._record_transition("STOPPED", note)

    def on_destroy(self, note: str = "Process Terminated"):
        self._record_transition("DESTROYED", note)

    def get_lifecycle_summary(self) -> Dict[str, Any]:
        """Tóm tắt lịch sử chuyển đổi trạng thái giao diện."""
        return {
            "current_state": self.current_state,
            "total_transitions": len(self.history),
            "has_pause_resume_cycle": any(h["state"] == "PAUSED" for h in self.history),
            "recent_events": self.history[-5:]
        }


class TokenBucketLimiter:
    """Thuật toán Token Bucket kiểm soát tần suất và cho phép các đợt bùng nổ ngắn hợp lệ."""

    def __init__(self, capacity: int = 8, refill_rate: float = 1.0):
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = refill_rate  # Số token nạp lại mỗi giây
        self.last_refill = time.time()

    def consume(self, tokens: float = 1.0) -> Tuple[bool, float]:
        """Cố gắng tiêu thụ token. Trả về (cho_phép, thời_gian_chờ_cần_thiết)."""
        now = time.time()
        elapsed = now - self.last_refill
        self.last_refill = now

        # Nạp lại token theo thời gian trôi qua
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, 0.0

        wait_time = (tokens - self.tokens) / self.refill_rate
        return False, round(wait_time, 2)


class LeakyBucketLimiter:
    """Thuật toán Leaky Bucket làm mịn lưu lượng và đẩy ra theo tốc độ cố định."""

    def __init__(self, capacity: int = 10, leak_rate: float = 1.5):
        self.capacity = float(capacity)
        self.water = 0.0
        self.leak_rate = leak_rate  # Lượng xả mỗi giây
        self.last_leak = time.time()

    def add_drop(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = now - self.last_leak
        self.last_leak = now

        # Xả nước
        self.water = max(0.0, self.water - elapsed * self.leak_rate)

        if self.water + amount <= self.capacity:
            self.water += amount
            return True

        return False  # Tràn bucket (bị chặn)


class BehaviorVelocityLimiter:
    """Bộ kiểm soát vận tốc sinh học & phân tích tần suất tương tác."""

    MIN_HUMAN_INTERVAL_SEC = 0.18  # 180ms: Giới hạn sinh học phản xạ thị giác/ngón tay nhanh nhất

    def __init__(self, capacity: int = 8, refill_rate: float = 1.2):
        self.token_bucket = TokenBucketLimiter(capacity, refill_rate)
        self.leaky_bucket = LeakyBucketLimiter(capacity=capacity * 2, leak_rate=refill_rate * 1.5)
        self.timestamps: List[float] = []

    def check_and_record_action(self, action_name: str = "reg_step") -> Dict[str, Any]:
        """Kiểm tra xem hành động có tuân thủ giới hạn vận tốc người thật hay không."""
        now = time.time()
        interval = (now - self.timestamps[-1]) if self.timestamps else 1.0
        self.timestamps.append(now)

        # Giữ lại trong 30 giây gần nhất
        self.timestamps = [t for t in self.timestamps if now - t <= 30.0]

        # Kiểm tra token bucket
        tb_allowed, tb_wait = self.token_bucket.consume(1.0)
        lb_allowed = self.leaky_bucket.add_drop(1.0)

        # Tính vận tốc (requests/second)
        recent_count = len(self.timestamps)
        velocity_rps = round(recent_count / 30.0, 2) if recent_count > 1 else 0.5

        is_superhuman = interval < self.MIN_HUMAN_INTERVAL_SEC
        is_allowed = tb_allowed and lb_allowed and not is_superhuman

        risk_score = 0.0
        if is_superhuman:
            risk_score += 0.60
        if not tb_allowed or not lb_allowed:
            risk_score += 0.40

        return {
            "is_biologically_valid": is_allowed,
            "interval_sec": round(interval, 3),
            "velocity_rps": velocity_rps,
            "required_cooldown_sec": tb_wait if not is_allowed else 0.0,
            "risk_score": min(1.0, round(risk_score, 2)),
            "verdict": "NATURAL_HUMAN_PACING" if is_allowed else "SUSPICIOUS_HIGH_VELOCITY_BURST"
        }


    def allow_action(self, cost: float = 1.0) -> Tuple[bool, float]:
        res = self.check_and_record_action()
        return res["is_biologically_valid"], res["required_cooldown_sec"]


class DeviceGraphProfiler:
    """Phân tích đồ thị liên kết thiết bị và phát hiện Bot Farm / Sybil Cluster."""

    @classmethod
    def evaluate_cluster_risk(
        cls,
        ip_address: str,
        device_id: str,
        advertising_id: str,
        session_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Đánh giá mật độ liên kết trên đồ thị:
        - Cùng dải Subnet /24 đăng ký dồn dập trong khoảng thời gian ngắn
        - Tái sử dụng Advertising ID hoặc Hardware Fingerprint giữa nhiều tài khoản.
        """
        subnet_24 = ".".join(ip_address.split(".")[:3]) if "." in ip_address else ip_address

        subnet_collisions = 0
        device_id_reuses = 0
        now = time.time()

        for sess in session_history:
            prev_ip = sess.get("ip", "")
            prev_dev = sess.get("device_id", "")
            prev_time = sess.get("timestamp", 0)

            if prev_ip.startswith(subnet_24) and (now - prev_time) < 300:
                subnet_collisions += 1
            if prev_dev == device_id and (now - prev_time) < 3600:
                device_id_reuses += 1

        risk_score = 0.0
        if device_id_reuses > 0:
            risk_score += 0.65
        if subnet_collisions > 3:
            risk_score += 0.35

        total_risk = min(1.0, round(risk_score, 2))
        return {
            "cluster_risk_score": total_risk,
            "subnet_collisions": subnet_collisions,
            "device_id_reuses": device_id_reuses,
            "is_cluster_anomaly": total_risk >= 0.50,
            "verdict": "ISOLATED_CLEAN_NODE" if total_risk < 0.50 else "DETECTED_SYBIL_FARM_NODE"
        }
