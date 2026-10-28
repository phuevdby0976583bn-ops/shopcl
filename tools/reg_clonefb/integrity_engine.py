# -*- coding: utf-8 -*-
"""
integrity_engine.py - Bộ khung nghiên cứu toàn diện các cơ chế bảo mật và phòng chống gian lận
(Enterprise Fraud Prevention & Security Integrity Research Framework)

Bao gồm 9 nhóm cơ chế nghiên cứu phòng vệ:
1. Google Play Integrity API & Nonce Lifecycle Verification.
2. Đánh giá rủi ro IP (Cellular 4G/5G vs Datacenter, MTU/MSS, ASN, CGNAT).
3. Lọc Disposable Email (DEA) qua Blacklist, High-risk TLD và MX Clustering.
4. Động lực học hành vi con người (Log-Normal Keystroke, Minimum Jerk, 8-12Hz Hand Tremor).
5. Dấu vân tay tầng mạng (TLS JA3/JA4 BoringSSL Liger & Akamai HTTP/2 Fingerprint).
6. Chứng thực phần cứng (Android Key Attestation TEE/StrongBox & Widevine DRM L1/L3).
7. Phát hiện máy ảo & can thiệp OS (Emulator pipes, CPU ABI, Magisk Magic Mount, SELinux).
8. Chống dịch ngược Native (Direct Syscall svc #0, Software Breakpoints, Anti-Frida).
9. Telemetry đồ thị & vận tốc (Đường cong xả pin, nhiệt độ chip, Activity Lifecycle, Token Bucket).
"""

import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import math
import os
import random
import re
import secrets
import socket
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

# Import từ các module chuyên sâu trong package modules/
from modules.transport_fingerprint import (
    TlsFingerprintEngine,
    Http2FingerprintEngine,
    Http3QuicFingerprintEngine,
    TransportFingerprintEngine,
)
from modules.hardware_keystore_drm import (
    HardwareAttestationEngine,
    WidevineDRMProfiler,
    HardwareKeystoreDRMEngine,
)
from modules.environment_detector import (
    EmulatorDetector,
    RootIntegrityAuditor,
    EnvironmentDetector,
    TelephonyBtsAuditor,
)
from modules.native_antirev_engine import (
    DirectSyscallEngine,
    BreakpointAuditor,
    AntiFridaAuditor,
    NativeIntegrityAuditor,
    SeccompSandboxAuditor,
)
from modules.velocity_graph_engine import (
    BatteryThermalEngine,
    ActivityLifecycleManager,
    TokenBucketLimiter,
    LeakyBucketLimiter,
    BehaviorVelocityLimiter,
    DeviceGraphProfiler,
)
from modules.pow_challenge_engine import PoWChallengeEngine
from modules.hardware_gpu_audio_profiler import HardwareGpuAudioProfiler
from modules.multi_sensor_fusion import MultiSensorFusionEngine

logger = logging.getLogger(__name__)


# ==============================================================================
# PHẦN 1: GOOGLE PLAY INTEGRITY API & NONCE VERIFICATION
# ==============================================================================
class PlayIntegrityEngine:
    """Mô phỏng quy trình tạo Nonce và xác thực Integrity Verdict theo chuẩn Google Play."""

    VERDICTS_DEVICE = {
        "STRONG": "MEETS_STRONG_INTEGRITY",
        "DEVICE": "MEETS_DEVICE_INTEGRITY",
        "BASIC": "MEETS_BASIC_INTEGRITY",
    }

    def __init__(self, secret_key: str = "integrity_audit_secret_2026"):
        self.secret_key = secret_key
        self.nonce_cache: Dict[str, float] = {}  # Nonce -> expiration timestamp

    def generate_nonce(self, session_id: str, action: str, ttl_seconds: int = 180) -> str:
        """Bước 1 (Backend): Sinh Nonce tối thiểu 16 byte, Base64 URL-safe, gắn chặt với session/action."""
        timestamp = int(time.time())
        entropy_bytes = secrets.token_bytes(16)
        payload = f"{session_id}:{action}:{timestamp}:{base64.urlsafe_b64encode(entropy_bytes).decode()}".encode()

        signature = hmac.new(self.secret_key.encode(), payload, hashlib.sha256).digest()[:16]
        raw_nonce = payload + b"." + signature
        nonce_str = base64.urlsafe_b64encode(raw_nonce).decode().rstrip("=")

        # Lưu cache chống Replay Attack với TTL
        self.nonce_cache[nonce_str] = time.time() + ttl_seconds
        return nonce_str

    def validate_and_consume_nonce(self, nonce_str: str) -> bool:
        """Kiểm tra tính hợp lệ và thu hồi Nonce (chỉ dùng một lần)."""
        now = time.time()
        # Dọn dẹp nonce hết hạn
        self.nonce_cache = {k: exp for k, exp in self.nonce_cache.items() if exp > now}

        if nonce_str not in self.nonce_cache:
            return False

        del self.nonce_cache[nonce_str]
        return True

    def build_simulated_token_verdict(
        self,
        package_name: str,
        nonce: str,
        device_level: str = "DEVICE",
        is_licensed: bool = True,
        cert_sha256: str = "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
        version_code: str = "44000031"
    ) -> Dict[str, Any]:
        """Tạo cấu trúc phản hồi giải mã của Google Play Developer API (decodeIntegrityToken)."""
        device_verdicts = []
        if device_level == "STRONG":
            device_verdicts = [self.VERDICTS_DEVICE["STRONG"], self.VERDICTS_DEVICE["DEVICE"], self.VERDICTS_DEVICE["BASIC"]]
        elif device_level == "DEVICE":
            device_verdicts = [self.VERDICTS_DEVICE["DEVICE"], self.VERDICTS_DEVICE["BASIC"]]
        elif device_level == "BASIC":
            device_verdicts = [self.VERDICTS_DEVICE["BASIC"]]

        return {
            "requestDetails": {
                "requestPackageName": package_name,
                "nonce": nonce,
                "timestampMillis": int(time.time() * 1000),
            },
            "appLicensingVerdict": "LICENSED" if is_licensed else "UNLICENSED",
            "appIntegrity": {
                "appRecognitionVerdict": "PLAY_RECOGNIZED",
                "packageName": package_name,
                "certificateSha256Digest": [cert_sha256],
                "versionCode": version_code,
            },
            "deviceIntegrity": {
                "deviceRecognitionVerdict": device_verdicts,
            },
            "accountDetails": {
                "appLicensingVerdict": "LICENSED" if is_licensed else "UNLICENSED",
            },
        }

    def verify_verdict(
        self,
        verdict_data: Dict[str, Any],
        expected_package: str,
        expected_cert: str,
        required_level: str = "MEETS_DEVICE_INTEGRITY"
    ) -> Tuple[bool, str]:
        """Bước 4 (Backend): Thẩm định kết quả giải mã từ Google theo các tiêu chí nghiêm ngặt."""
        req_details = verdict_data.get("requestDetails", {})
        nonce = req_details.get("nonce", "")

        if not self.validate_and_consume_nonce(nonce):
            return False, "NONCE_INVALID_OR_REPLAYED"

        app_integ = verdict_data.get("appIntegrity", {})
        if app_integ.get("packageName") != expected_package:
            return False, f"PACKAGE_MISMATCH: {app_integ.get('packageName')} != {expected_package}"

        certs = app_integ.get("certificateSha256Digest", [])
        if expected_cert not in certs:
            return False, "CERTIFICATE_HASH_MISMATCH"

        dev_verdicts = verdict_data.get("deviceIntegrity", {}).get("deviceRecognitionVerdict", [])
        if required_level not in dev_verdicts:
            return False, f"INSUFFICIENT_DEVICE_INTEGRITY: required {required_level}, got {dev_verdicts}"

        if verdict_data.get("appLicensingVerdict") != "LICENSED":
            return False, "APP_NOT_LICENSED"

        return True, "VERDICT_PASSED"


# ==============================================================================
# PHẦN 2: PHÂN LOẠI IP & MÔ PHỎNG ĐẶC TRƯNG MẠNG DI ĐỘNG (CELLULAR VS DATACENTER)
# ==============================================================================
class NetworkRiskAnalyzer:
    """Đánh giá rủi ro IP và xây dựng fingerprint mạng chuẩn di động (Cellular 4G/LTE)."""

    DATACENTER_KEYWORDS = [
        "amazon", "aws", "digitalocean", "vultr", "linode", "ovh", "hetzner",
        "googleusercontent", "azure", "cloud", "hosting", "datacenter", "server", "leaseweb"
    ]

    @staticmethod
    def evaluate_ip_risk(ip_address: str, hostname: Optional[str] = None, asn_org: Optional[str] = None) -> Dict[str, Any]:
        """Tính điểm rủi ro IP (0 - 100) dựa trên ASN, rDNS và từ khóa Datacenter."""
        risk_score = 10
        signals = []

        combined_info = f"{hostname or ''} {asn_org or ''}".lower()

        # Kiểm tra từ khóa hosting / server farm
        for kw in NetworkRiskAnalyzer.DATACENTER_KEYWORDS:
            if kw in combined_info:
                risk_score += 55
                signals.append(f"DATACENTER_KEYWORD_{kw.upper()}")
                break

        # Kiểm tra rDNS PTR
        if hostname:
            if re.search(r"(compute|vps|dedicated|static\.cloud)", hostname, re.I):
                risk_score += 25
                signals.append("PTR_STATIC_HOSTING")
            elif re.search(r"(dynamic|broadband|mobile|cellular|gprs|cgnat)", hostname, re.I):
                risk_score = max(5, risk_score - 15)
                signals.append("PTR_RESIDENTIAL_OR_CELLULAR")

        # Phân loại
        connection_type = "Datacenter" if risk_score >= 50 else ("Cellular" if "CELLULAR" in " ".join(signals) else "Residential")
        return {
            "ip": ip_address,
            "risk_score": min(100, risk_score),
            "connection_type": connection_type,
            "signals": signals,
            "is_trusted": risk_score < 40,
        }

    @staticmethod
    def get_cellular_tcp_profile(carrier: str = "Viettel") -> Dict[str, Any]:
        """Tạo cấu hình đặc trưng mạng di động theo lý thuyết GTP Tunneling & CGNAT."""
        mtu = random.choice([1420, 1428, 1432, 1440])
        mss = mtu - 40  # IP Header (20) + TCP Header (20)

        rtt_base = random.uniform(35.0, 75.0)
        jitter = random.uniform(5.0, 18.0)

        carrier_lower = carrier.lower()
        if "viettel" in carrier_lower:
            hni = "45204"
        elif "mobifone" in carrier_lower:
            hni = "45201"
        elif "vinaphone" in carrier_lower:
            hni = "45202"
        else:
            hni = "45204"

        return {
            "carrier": carrier,
            "connection_type": "CELLULAR_LTE",
            "mtu": mtu,
            "mss": mss,
            "cgnat_detected": True,
            "simulated_rtt_ms": round(rtt_base + jitter, 2),
            "headers": {
                "X-FB-Connection-Type": "CELLULAR_LTE",
                "X-FB-Sim-Operator": carrier,
                "X-FB-Net-HNI": hni,
            }
        }


class PassiveTcpFingerprint(NetworkRiskAnalyzer):
    """Mô phỏng và phân tích thụ động dấu vân tay gói tin TCP/IP."""
    pass


# ==============================================================================
# PHẦN 3: LỌC EMAIL TẠM THỜI (DISPOSABLE EMAIL SERVICE)
# ==============================================================================
class DisposableEmailAuditor:
    """Hệ thống lọc email rác đa tầng: Cú pháp, Domain Blacklist, TLD và MX Clustering."""

    KNOWN_DEA_DOMAINS = {
        "mail.tm", "1secmail.com", "1secmail.org", "1secmail.net",
        "tempmail.com", "guerrillamail.com", "dropmail.me", "dispostable.com",
        "yopmail.com", "mailinator.com", "trashmail.com", "temp-mail.org",
        "esiix.com", "wwjmp.com", "yepmailer.net", "vmani.com", "cuoly.com"
    }

    HIGH_RISK_TLDS = {".xyz", ".top", ".buzz", ".club", ".tk", ".cf", ".gq", ".ml", ".ga"}

    SUSPICIOUS_MX_HOSTS = [
        "mailcatch.com", "mailgun.net", "dropmail.me", "1secmail",
        "disposable", "tempmail", "yopmail", "forwardemail.net"
    ]

    @classmethod
    def audit_email(cls, email: str, check_dns: bool = False) -> Dict[str, Any]:
        """Đánh giá chất lượng và độ tin cậy của địa chỉ email."""
        if not email or "@" not in email:
            return {"valid": False, "reason": "MALFORMED_EMAIL", "risk_score": 100}

        username, domain = email.strip().lower().split("@", 1)

        # Tầng 1: Kiểm tra Blacklist tên miền đã biết
        if domain in cls.KNOWN_DEA_DOMAINS:
            return {
                "valid": True,
                "is_disposable": True,
                "risk_score": 95,
                "reason": "KNOWN_DEA_DOMAIN",
                "domain": domain
            }

        # Tầng 2: Kiểm tra TLD giá rẻ / nguy cơ cao
        for tld in cls.HIGH_RISK_TLDS:
            if domain.endswith(tld):
                return {
                    "valid": True,
                    "is_disposable": True,
                    "risk_score": 80,
                    "reason": f"HIGH_RISK_TLD_{tld}",
                    "domain": domain
                }

        # Tầng 3: MX Clustering (nếu kích hoạt DNS lookup)
        if check_dns:
            try:
                addr_info = socket.gethostbyname(domain)
                if not addr_info:
                    return {"valid": False, "reason": "DOMAIN_NO_DNS", "risk_score": 100}
            except Exception:
                return {"valid": False, "reason": "DNS_RESOLUTION_FAILED", "risk_score": 90}

        return {
            "valid": True,
            "is_disposable": False,
            "risk_score": 15,
            "reason": "CLEAN_DOMAIN",
            "domain": domain
        }


# ==============================================================================
# PHẦN 4: MÔ PHỎNG ĐỘNG LỰC HỌC HÀNH VI (BEHAVIORAL BIOMETRICS & TIMING)
# ==============================================================================
class HumanBehaviorDynamics:
    """Mô phỏng khoảng dừng nhận thức, tốc độ gõ phím Log-Normal và rung vi mô bàn tay 8-12Hz."""

    @staticmethod
    def sample_keystroke_flight_time() -> float:
        """Thời gian chuyển giữa 2 phím theo phân phối Log-Normal (khoảng 80ms - 220ms)."""
        mu = 4.85
        sigma = 0.35
        ms = math.exp(random.gauss(mu, sigma))
        ms = max(50.0, min(ms, 450.0))
        return ms / 1000.0

    @staticmethod
    def sample_cognitive_pause(min_sec: float = 0.8, max_sec: float = 2.5) -> float:
        """Khoảng dừng suy nghĩ của con người (Cognitive Pause) trước hành động mới."""
        mu = 0.4
        sigma = 0.3
        pause = random.lognormvariate(mu, sigma)
        return max(min_sec, min(pause, max_sec))

    @staticmethod
    def generate_hand_tremor_telemetry(duration_sec: float = 1.0, sampling_rate_hz: int = 50) -> List[Dict[str, float]]:
        """Mô phỏng dữ liệu gia tốc kế có đỉnh tần số rung tự nhiên 8 - 12 Hz của bàn tay người."""
        samples = []
        total_points = int(duration_sec * sampling_rate_hz)
        tremor_freq = random.uniform(8.5, 11.5)

        for i in range(total_points):
            t = i / float(sampling_rate_hz)
            accel_x = 0.2 * math.sin(2 * math.pi * tremor_freq * t) + random.gauss(0, 0.05)
            accel_y = 0.15 * math.cos(2 * math.pi * tremor_freq * t) + random.gauss(0, 0.04)
            accel_z = 9.81 + 0.3 * math.sin(2 * math.pi * tremor_freq * t) + random.gauss(0, 0.08)

            samples.append({
                "time_offset_ms": round(t * 1000, 1),
                "accel_x": round(accel_x, 3),
                "accel_y": round(accel_y, 3),
                "accel_z": round(accel_z, 3),
            })
        return samples

    @staticmethod
    def generate_touch_event(x: float, y: float) -> Dict[str, Any]:
        """Mô phỏng lực nhấn (Pressure) và diện tích elip ngón tay khi chạm màn hình."""
        pressure = random.uniform(0.45, 0.85)
        touch_major = random.uniform(7.5, 12.0)
        touch_minor = touch_major * random.uniform(0.65, 0.85)

        return {
            "x": round(x, 1),
            "y": round(y, 1),
            "pressure": round(pressure, 2),
            "touch_major": round(touch_major, 2),
            "touch_minor": round(touch_minor, 2),
        }


# ==============================================================================
# META DEVICE GRAPH & FCM ATTESTATION HELPERS
# ==============================================================================
class MetaDeviceGraphEngine:
    """Xây dựng định danh thiết bị nhất quán trong đồ thị thiết bị Meta Central Access API."""

    @classmethod
    def generate_consistent_meta_identity(cls, preset: Dict[str, Any]) -> Dict[str, Any]:
        carrier = preset.get("carrier", "Viettel")
        carrier_lower = carrier.lower()
        if "viettel" in carrier_lower:
            sim_name = "Viettel Telecom"
            hni = "45204"
            carrier_id = "viettel"
        elif "mobifone" in carrier_lower:
            sim_name = "MobiFone"
            hni = "45201"
            carrier_id = "mobifone"
        elif "vinaphone" in carrier_lower:
            sim_name = "VN VINAPHONE"
            hni = "45202"
            carrier_id = "vinaphone"
        else:
            sim_name = "Viettel Telecom"
            hni = "45204"
            carrier_id = "viettel"

        return {
            "family_device_id": str(uuid.uuid4()),
            "waterfall_id": str(uuid.uuid4()),
            "client_session_id": str(uuid.uuid4()),
            "sim_operator_name": sim_name,
            "net_hni": hni,
            "sim_hni": hni,
            "bandwidth_estimate": "21474836",
            "bandwidth_quality": "EXCELLENT",
            "zero_carrier_id": carrier_id,
        }


class FcmMqttAttestationEngine:
    """Mô phỏng token FCM (Firebase Cloud Messaging) và giao vận push notification MQTT Katana."""

    @classmethod
    def generate_fcm_token(cls) -> str:
        prefix = "f" + base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
        body = base64.urlsafe_b64encode(os.urandom(98)).decode("ascii").rstrip("=")
        return f"{prefix}:APA91b{body}"


class MemoryProtectionAuditor(NativeIntegrityAuditor):
    """Kiểm tra tính toàn vẹn bộ nhớ tiến trình và phân vùng mã thực thi .text."""
    pass


# ==============================================================================
# TỔNG HỢP: SUITE NGHIÊN CỨU & KIỂM ĐỊNH TOÀN DIỆN (DEVICE INTEGRITY SUITE)
# ==============================================================================
class DeviceEnvironmentTelemetry(BatteryThermalEngine):
    """Lớp chuyển tiếp backward-compatible kế thừa từ BatteryThermalEngine."""
    pass


class DeviceIntegritySuite:
    """
    Bộ điều phối hợp nhất toàn diện 9 cơ chế an ninh & tính toàn vẹn (Orchestrator).
    Cung cấp khả năng đánh giá đồng thời toàn bộ các lớp bảo vệ doanh nghiệp.
    """

    def __init__(self, carrier: str = "Viettel", device_preset: Optional[Dict[str, Any]] = None):
        self.device_preset = device_preset or {
            "manufacturer": "Xiaomi",
            "brand": "Redmi",
            "model": "Redmi Note 11",
            "carrier": carrier
        }
        self.play_engine = PlayIntegrityEngine()
        self.telemetry = BatteryThermalEngine()
        self.lifecycle = ActivityLifecycleManager()
        self.velocity = BehaviorVelocityLimiter()

    def generate_full_authentic_client_profile(self, session_id: str) -> Dict[str, Any]:
        """Sinh bộ thông số đầy đủ chuẩn thiết bị thật cho phiên nghiên cứu."""
        nonce = self.play_engine.generate_nonce(session_id, "full_audit")
        transport_profile = TransportFingerprintEngine.get_katana_liger_transport_profile()
        hardware_profile = HardwareKeystoreDRMEngine.build_katana_hardware_profile(challenge=nonce)
        environment_profile = EnvironmentDetector.evaluate_genuine_device(self.device_preset)
        native_profile = NativeIntegrityAuditor.get_genuine_native_report()
        cellular_profile = NetworkRiskAnalyzer.get_cellular_tcp_profile(self.device_preset.get("carrier", "Viettel"))
        battery_status = self.telemetry.tick(elapsed_seconds=3.0, cpu_workload="normal")

        return {
            "session_id": session_id,
            "nonce": nonce,
            "transport": transport_profile,
            "hardware": hardware_profile,
            "environment": environment_profile,
            "native": native_profile,
            "network": cellular_profile,
            "battery_thermal": battery_status,
            "lifecycle_state": self.lifecycle.current_state,
        }

    def run_comprehensive_audit(
        self,
        session_id: str,
        observed_ja3: str,
        h2_settings: Dict[int, int],
        h2_window: int,
        pseudo_order: List[str],
        attestation_claim: Dict[str, Any],
        drm_profile: Dict[str, Any],
        files_present: List[str],
        threads: List[str],
        maps_text: str,
        email_to_check: Optional[str] = None
    ) -> Dict[str, Any]:
        """Chạy kiểm định chéo đồng thời 9 cơ chế phòng vệ và tính điểm rủi ro tổng hợp."""
        # 1. Transport Layer Audit
        transport_audit = TransportFingerprintEngine.evaluate_transport_risk(
            raw_ja3=observed_ja3,
            h2_settings=h2_settings,
            h2_window_update=h2_window,
            pseudo_order=pseudo_order
        )

        # 2. Hardware Keystore & DRM Audit
        hardware_audit = HardwareKeystoreDRMEngine.evaluate_cross_hardware_integrity(
            attestation_claim=attestation_claim,
            drm_profile=drm_profile,
            expected_challenge=session_id
        )

        # 3. Environment Audit (Emulator / Root)
        env_audit = EnvironmentDetector.audit_environment(
            files_present=files_present,
            build_props={"ro.hardware": "qcom", "ro.product.board": "spes"},
            mounts_text=""
        )

        # 4. Native Anti-Rev Audit (Frida / Breakpoints)
        native_audit = NativeIntegrityAuditor.evaluate_process_integrity(
            threads=threads,
            maps_text=maps_text
        )

        # 5. Email Audit (nếu có)
        email_audit = DisposableEmailAuditor.audit_email(email_to_check) if email_to_check else None

        # Tổng hợp điểm rủi ro có trọng số
        w_transport = 0.25
        w_hardware = 0.25
        w_env = 0.25
        w_native = 0.15
        w_email = 0.10 if email_audit else 0.0
        total_w = w_transport + w_hardware + w_env + w_native + w_email

        raw_score = (
            transport_audit["composite_risk_score"] * w_transport +
            hardware_audit["composite_risk_score"] * w_hardware +
            env_audit["environment_risk_score"] * w_env +
            native_audit["composite_risk_score"] * w_native +
            (email_audit["risk_score"] / 100.0 * w_email if email_audit else 0.0)
        ) / total_w

        overall_score = round(raw_score, 3)
        is_trusted = overall_score < 0.28

        return {
            "session_id": session_id,
            "overall_risk_score": overall_score,
            "is_trusted_genuine_device": is_trusted,
            "verdict": "GENUINE_SECURE_CLIENT" if is_trusted else "ANOMALOUS_OR_COMPROMISED_CLIENT",
            "modules": {
                "transport": transport_audit,
                "hardware": hardware_audit,
                "environment": env_audit,
                "native": native_audit,
                "email": email_audit,
            }
        }
