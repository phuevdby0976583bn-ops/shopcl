# -*- coding: utf-8 -*-
"""
modules/multi_sensor_fusion.py
Nghiên cứu & mô phỏng Tương quan Đa Cảm biến (Multi-Sensor Fusion & Gravity Tilt):
1. Mô-men xoắn khi gõ phím: Liên kết giữa lực chạm màn hình (Touch Impact) và Vận tốc góc Con quay hồi chuyển (Gyroscope).
2. Góc nghiêng trọng lực tự nhiên (Gravity Pitch & Roll: 30° - 55° góc cầm tay người thật).
3. Phát hiện Phone Farm đặt trên giá cố định (0° nằm phẳng, 90° dựng đứng, Gyroscope variance = 0).
"""

import math
import random
import time
from typing import Dict, Any, List, Optional, Tuple


class MultiSensorFusionEngine:
    """Mô phỏng và thẩm định dữ liệu tương quan giữa Gia tốc kế, Con quay hồi chuyển và Trọng lực."""

    @classmethod
    def generate_coupled_touch_sensor_frame(
        cls,
        touch_x: float,
        touch_y: float,
        screen_width
        : float = 1080.0,
        screen_height: float = 2400.0,
        pressure: float = 0.65
    ) -> Dict[str, Any]:
        """
        Mô phỏng sự va đập lực khi ngón tay nhấn vào màn hình:
        - Lực ấn tạo gia tốc Z đột ngột (-0.2 m/s^2 đến -0.6 m/s^2).
        - Khoảng cách từ tâm màn hình đến điểm chạm tạo mô-men lực quay (Torque) làm máy chao đảo nhẹ trên Gyroscope.
        """
        # Tọa độ chuẩn hóa so với tâm máy (-1.0 đến +1.0)
        norm_x = (touch_x - (screen_width / 2.0)) / (screen_width / 2.0)
        norm_y = (touch_y - (screen_height / 2.0)) / (screen_height / 2.0)

        # Mô-men xoắn tạo vận tốc góc (rad/s)
        gyro_x = -norm_y * pressure * random.uniform(0.12, 0.28)
        gyro_y = norm_x * pressure * random.uniform(0.15, 0.32)
        gyro_z = random.gauss(0.0, 0.02)

        # Góc cầm tay tự nhiên của con người (Pitch: 32° - 50°, Roll: -8° đến +8°)
        pitch_deg = random.gauss(38.0, 4.0)
        roll_deg = random.gauss(3.5, 2.5)

        # Phân rã trọng lực g = 9.81 m/s^2 theo góc nghiêng
        pitch_rad = math.radians(pitch_deg)
        roll_rad = math.radians(roll_deg)

        grav_x = 9.81 * math.sin(roll_rad)
        grav_y = 9.81 * math.sin(pitch_rad) * math.cos(roll_rad)
        grav_z = 9.81 * math.cos(pitch_rad) * math.cos(roll_rad)

        # Gia tốc khi chạm (kết hợp trọng lực + xung lực chạm)
        acc_x = grav_x + random.gauss(0.0, 0.04)
        acc_y = grav_y + random.gauss(0.0, 0.04)
        acc_z = grav_z + (pressure * -0.35) + random.gauss(0.0, 0.03)

        return {
            "touch_point": {"x": round(touch_x, 1), "y": round(touch_y, 1), "pressure": round(pressure, 2)},
            "accelerometer": {"x": round(acc_x, 3), "y": round(acc_y, 3), "z": round(acc_z, 3)},
            "gyroscope": {"x": round(gyro_x, 4), "y": round(gyro_y, 4), "z": round(gyro_z, 4)},
            "posture": {
                "pitch_degrees": round(pitch_deg, 1),
                "roll_degrees": round(roll_deg, 1),
                "device_orientation": "NATURAL_HANDHELD"
            }
        }

    @classmethod
    def audit_sensor_fusion_authenticity(
        cls,
        frames: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Thẩm định tính tương quan chéo giữa các cảm biến:
        - Nếu có sự kiện chạm (Touch) nhưng Gyroscope variance = 0 -> Chèn cảm biến giả (Bot injection).
        - Nếu góc Pitch luôn = 0° (nằm bẹp trên bàn) hoặc 90° (dựng đứng giá treo Phone Farm liên tục) -> Nghi vấn bot farm.
        """
        if not frames:
            return {"is_authentic": True, "risk_score": 0.0}

        gyro_magnitudes = []
        pitches = []

        for f in frames:
            g = f.get("gyroscope", {})
            mag = math.sqrt(g.get("x", 0)**2 + g.get("y", 0)**2 + g.get("z", 0)**2)
            gyro_magnitudes.append(mag)
            p = f.get("posture", {}).get("pitch_degrees", 40.0)
            pitches.append(p)

        avg_pitch = sum(pitches) / len(pitches)
        gyro_variance = max(gyro_magnitudes) - min(gyro_magnitudes)

        violations = []
        risk_score = 0.0

        # Kiểm tra con quay hồi chuyển bị chết/đứng yên khi đang gõ
        if gyro_variance < 0.01:
            violations.append("ZERO_GYROSCOPE_REACTION_ON_TOUCH")
            risk_score += 0.60

        # Kiểm tra góc cầm máy phi tự nhiên (Phone farm giá đỡ hoặc máy nằm phẳng)
        if avg_pitch < 10.0 or avg_pitch > 85.0:
            violations.append(f"UNNATURAL_HOLDING_ANGLE_PITCH_{round(avg_pitch, 1)}_DEG")
            risk_score += 0.40

        total_risk = min(1.0, round(risk_score, 2))
        is_clean = total_risk < 0.30

        return {
            "is_authentic_fusion": is_clean,
            "risk_score": total_risk,
            "violations": violations,
            "avg_pitch_deg": round(avg_pitch, 1),
            "gyro_variance": round(gyro_variance, 4),
            "verdict": "GENUINE_HUMAN_SENSOR_FUSION" if is_clean else "INJECTED_OR_RACK_MOUNTED_DEVICE"
        }
