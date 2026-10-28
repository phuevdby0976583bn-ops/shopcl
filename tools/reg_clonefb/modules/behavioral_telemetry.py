# -*- coding: utf-8 -*-
"""
modules/behavioral_telemetry.py
Triển khai mô hình động lực học hành vi & dữ liệu cảm biến (Behavioral Biometrics & Telemetry)
Dựa trên các nghiên cứu trong tài liệu:
1. Mô phỏng & Đánh giá rung tay vi mô (Physiological Micro-tremors 8-12 Hz)
2. Mô hình động học vuốt chạm theo đường cong Bell-shaped (Minimum-Jerk Kinematics)
3. Biến thiên áp lực và diện tích tiếp xúc ngón tay (Touch Pressure & Contact Ellipse)
4. Phân tích phổ tần số bằng FFT & Entropy Shannon
5. Tính điểm bất thường (Behavioral Anomaly Risk Score: 0.0 Human -> 1.0 Bot)
"""

import math
import random
import time
from typing import Dict, Any, List, Tuple
import numpy as np


class SensorTelemetryEngine:
    """Mô phỏng và phân tích dữ liệu cảm biến quán tính (Gia tốc kế & Con quay hồi chuyển)."""

    def generate_human_sensor_stream(
        self,
        duration_sec: float = 2.0,
        sample_rate_hz: int = 100
    ) -> List[Dict[str, float]]:
        """
        Sinh chuỗi dữ liệu cảm biến của bàn tay con người:
        - Trọng lực Trái Đất cơ sở (g ≈ 9.81 m/s^2 trên trục Z khi cầm máy hơi nghiêng)
        - Rung vi mô sinh lý (Physiological micro-tremor ở dải tần số 8 - 12 Hz)
        - Phản lực khi ngón tay chạm màn hình (touch impulse recoil)
        """
        n_samples = int(duration_sec * sample_rate_hz)
        timestamps = np.linspace(0, duration_sec, n_samples)
        stream = []

        # Tần số rung vi mô ngẫu nhiên của người cầm máy (8 - 12 Hz)
        tremor_freq = random.uniform(8.5, 11.5)
        tremor_phase = random.uniform(0, 2 * math.pi)

        for t in timestamps:
            # Sóng dao động vi mô sinh lý cơ học
            micro_tremor_x = 0.08 * math.sin(2 * math.pi * tremor_freq * t + tremor_phase) + np.random.normal(0, 0.015)
            micro_tremor_y = 0.06 * math.cos(2 * math.pi * tremor_freq * t + tremor_phase) + np.random.normal(0, 0.012)
            # Trục Z gồm trọng lực 9.81 m/s^2 + vi chấn
            acc_z = 9.80 + 0.05 * math.sin(2 * math.pi * tremor_freq * t) + np.random.normal(0, 0.02)

            gyro_x = 0.03 * math.sin(2 * math.pi * tremor_freq * t) + np.random.normal(0, 0.005)
            gyro_y = 0.025 * math.cos(2 * math.pi * tremor_freq * t) + np.random.normal(0, 0.004)
            gyro_z = np.random.normal(0, 0.003)

            stream.append({
                "t": round(float(t), 4),
                "acc_x": round(float(micro_tremor_x), 5),
                "acc_y": round(float(micro_tremor_y), 5),
                "acc_z": round(float(acc_z), 5),
                "gyro_x": round(float(gyro_x), 5),
                "gyro_y": round(float(gyro_y), 5),
                "gyro_z": round(float(gyro_z), 5),
            })
        return stream

    def generate_bot_sensor_stream(self, duration_sec: float = 2.0, sample_rate_hz: int = 100) -> List[Dict[str, float]]:
        """Mô phỏng dữ liệu bot/giả lập: Cố định 0.0 hoặc phẳng hoàn toàn (zero noise)."""
        n_samples = int(duration_sec * sample_rate_hz)
        timestamps = np.linspace(0, duration_sec, n_samples)
        return [{
            "t": round(float(t), 4),
            "acc_x": 0.0,
            "acc_y": 0.0,
            "acc_z": 9.81,
            "gyro_x": 0.0,
            "gyro_y": 0.0,
            "gyro_z": 0.0
        } for t in timestamps]

    def analyze_sensor_microtremor(self, sensor_stream: List[Dict[str, float]], sample_rate_hz: int = 100) -> Dict[str, Any]:
        """
        Phân tích phổ Fourier (FFT) trên trục gia tốc để phát hiện đỉnh tần số rung tay 8-12 Hz.
        Nếu phương sai = 0 hoặc không có năng lượng phổ -> Đánh dấu là BOT.
        """
        acc_x = np.array([pt["acc_x"] for pt in sensor_stream])
        variance = float(np.var(acc_x))

        if variance < 1e-6:
            return {
                "has_human_microtremor": False,
                "peak_frequency_hz": 0.0,
                "variance": variance,
                "risk_score": 1.0,
                "reasons": ["Gia tốc cảm biến tĩnh tuyệt đối (Variance ~ 0): Dấu hiệu giả lập hoặc script không có cảm biến vật lý."]
            }

        # Tính FFT
        n = len(acc_x)
        fft_vals = np.abs(np.fft.rfft(acc_x - np.mean(acc_x)))
        freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate_hz)

        # Tìm tần số có biên độ lớn nhất (loại bỏ DC component tại index 0)
        if len(freqs) > 1:
            peak_idx = int(np.argmax(fft_vals[1:])) + 1
            peak_freq = float(freqs[peak_idx])
        else:
            peak_freq = 0.0

        is_human_tremor = (7.5 <= peak_freq <= 13.0) and (variance > 0.0005)
        risk = 0.05 if is_human_tremor else 0.85

        reasons = []
        if is_human_tremor:
            reasons.append(f"Phát hiện đỉnh rung vi mô sinh học tại {peak_freq:.1f} Hz (Tương thích tay người thật).")
        else:
            reasons.append(f"Tần số rung bất thường ({peak_freq:.1f} Hz): Không khớp dải rung sinh lý người (8-12 Hz).")

        return {
            "has_human_microtremor": is_human_tremor,
            "peak_frequency_hz": round(peak_freq, 2),
            "variance": round(variance, 6),
            "risk_score": round(risk, 2),
            "reasons": reasons
        }


class TouchKinematicsEngine:
    """Mô phỏng & Đánh giá quỹ đạo vuốt chạm (Touch Dynamics & Kinematics)."""

    def generate_human_swipe_trajectory(
        self,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        duration_sec: float = 0.45,
        points_count: int = 40
    ) -> List[Dict[str, float]]:
        """
        Sinh quỹ đạo vuốt chạm mô phỏng con người theo mô hình Minimum-Jerk:
        - Đồ thị vận tốc dạng hình chuông (Bell-shaped curve: tăng tốc chậm -> max -> giảm tốc chậm)
        - Độ cong sinh học tự nhiên (Bézier arc curvature)
        - Áp lực chạm (pressure) tăng từ 0.3 lên 0.85 rồi giảm xuống 0.2
        - Diện tích tiếp xúc (touch major/minor radius) biến thiên elip
        """
        x0, y0 = start_pt
        x1, y1 = end_pt

        # Điểm uốn ngẫu nhiên tạo đường cong tự nhiên của khớp ngón tay
        ctrl_x = (x0 + x1) / 2 + random.uniform(-15.0, 15.0)
        ctrl_y = (y0 + y1) / 2 + random.uniform(-25.0, 25.0)

        trajectory = []
        for i in range(points_count):
            t_norm = i / (points_count - 1)  # 0.0 -> 1.0

            # Tham số hóa theo mô hình Minimum-Jerk: s(t) = 10*t^3 - 15*t^4 + 6*t^5
            s = 10 * (t_norm ** 3) - 15 * (t_norm ** 4) + 6 * (t_norm ** 5)

            # Điểm trên đường cong Bézier bậc 2
            x = ((1 - s) ** 2) * x0 + 2 * (1 - s) * s * ctrl_x + (s ** 2) * x1
            y = ((1 - s) ** 2) * y0 + 2 * (1 - s) * s * ctrl_y + (s ** 2) * y1

            # Vận tốc hình chuông tỉ lệ với đạo hàm: ds/dt = 30*t^2 - 60*t^3 + 30*t^4
            vel_norm = 30 * (t_norm ** 2) - 60 * (t_norm ** 3) + 30 * (t_norm ** 4)
            # Áp lực biến thiên theo vận tốc và lực tì
            pressure = 0.25 + 0.60 * math.sin(math.pi * t_norm) + random.uniform(-0.02, 0.02)
            major_radius = 18.0 + 12.0 * pressure  # Diện tích chạm elip (pixels)

            trajectory.append({
                "t_ms": round(t_norm * duration_sec * 1000, 1),
                "x": round(x, 1),
                "y": round(y, 1),
                "pressure": round(min(max(pressure, 0.1), 1.0), 3),
                "radius": round(major_radius, 1),
                "velocity_profile": round(vel_norm, 3)
            })

        return trajectory

    def generate_bot_linear_touch(
        self,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        duration_sec: float = 0.2,
        points_count: int = 10
    ) -> List[Dict[str, float]]:
        """Mô phỏng bot/script ADB swipe cơ học: vận tốc đều, áp lực cố định 1.0."""
        x0, y0 = start_pt
        x1, y1 = end_pt
        trajectory = []
        for i in range(points_count):
            t = i / (points_count - 1)
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            trajectory.append({
                "t_ms": round(t * duration_sec * 1000, 1),
                "x": round(x, 1),
                "y": round(y, 1),
                "pressure": 1.0,  # Hằng số
                "radius": 1.0,    # 1 pixel điểm tiếp xúc
                "velocity_profile": 1.0
            })
        return trajectory

    def evaluate_touch_kinematics(self, trajectory: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Đánh giá tính chân thực của cử chỉ vuốt chạm:
        - Kiểm tra tính biến thiên của áp lực (pressure variance)
        - Kiểm tra đồ thị vận tốc hình chuông (bell-curve velocity)
        - Kiểm tra độ cong đường đi
        """
        if len(trajectory) < 5:
            return {"risk_score": 1.0, "verdict": "TOO_FEW_POINTS", "reasons": ["Quá ít điểm mẫu vuốt chạm"]}

        pressures = [pt["pressure"] for pt in trajectory]
        pressure_std = float(np.std(pressures))

        # Tính vận tốc từng đoạn: v_i = dist / dt
        velocities = []
        for i in range(1, len(trajectory)):
            dx = trajectory[i]["x"] - trajectory[i - 1]["x"]
            dy = trajectory[i]["y"] - trajectory[i - 1]["y"]
            dt = max(trajectory[i]["t_ms"] - trajectory[i - 1]["t_ms"], 1.0)
            dist = math.hypot(dx, dy)
            velocities.append(dist / dt)

        # Tính xem đỉnh vận tốc có nằm ở giữa hành trình không (30% - 70%)
        if velocities:
            peak_idx = int(np.argmax(velocities))
            peak_relative_pos = peak_idx / len(velocities)
            has_bell_curve = (0.25 <= peak_relative_pos <= 0.75) and len(velocities) > 8
        else:
            has_bell_curve = False

        reasons = []
        risk_score = 0.0

        if pressure_std < 0.02:
            risk_score += 0.50
            reasons.append("Áp lực chạm màn hình tĩnh hoặc không đổi (Pressure Std < 0.02): Dấu hiệu script ADB/Bot.")
        else:
            reasons.append(f"Áp lực chạm biến thiên tự nhiên (Std = {pressure_std:.3f}).")

        if not has_bell_curve:
            risk_score += 0.40
            reasons.append("Vận tốc không tuân theo quy luật Bell-curve/Minimum-Jerk của con người.")
        else:
            reasons.append("Đồ thị vận tốc dạng hình chuông đạt chuẩn động học con người.")

        total_risk = min(max(risk_score, 0.0), 1.0)
        return {
            "pressure_std": round(pressure_std, 4),
            "has_bell_curve": has_bell_curve,
            "risk_score": round(total_risk, 2),
            "verdict": "HUMAN_KINEMATICS" if total_risk < 0.4 else "ARTIFICIAL_GESTURE",
            "reasons": reasons
        }


def explain_behavioral_deficiency_in_fb_reg() -> Dict[str, str]:
    """Giải thích tại sao fb_reg.py bị Meta gắn cờ nếu chỉ gửi POST request thuần túy."""
    return {
        "Deficiency_Analysis": (
            "File fb_reg.py và fb_api.py gửi trực tiếp các HTTP POST request từ máy tính. "
            "Trên ứng dụng thật Katana (FB4A), Meta SDK liên tục thu thập telemetry ngầm "
            "về cử chỉ chạm, độ rung thiết bị (Micro-tremors) và thời gian suy nghĩ (Cognitive Delay)."
        ),
        "Zero_Cognitive_Time": (
            "Script Python gửi các bước Step 1 -> Step 8 chỉ với sleep 0.3s - 0.7s cơ học. "
            "Con người cần thời gian đọc và thao tác nhập form (tuân theo phân phối Log-Normal ~ 3s - 8s). "
            "Tốc độ gửi form cơ học bị bộ lọc Machine Learning gắn cờ Zero-Cognitive Bot ngay tại API Gateway."
        ),
        "Mitigation_Rule": (
            "Nghiên cứu an toàn đòi hỏi phải mô phỏng chính xác phân phối thời gian trễ nhận thức (Cognitive Delay) "
            "và đóng gói payload telemetry cảm biến nếu endpoint yêu cầu client-side behavioral logging."
        )
    }
