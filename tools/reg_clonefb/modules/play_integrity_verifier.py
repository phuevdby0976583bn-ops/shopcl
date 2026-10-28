# -*- coding: utf-8 -*-
"""
modules/play_integrity_verifier.py
Triển khai mô hình xác thực Google Play Integrity API / SafetyNet (Chuẩn 4 bước)
Dùng để nghiên cứu, giả lập và đánh giá độ tin cậy thiết bị & token.
"""

import time
import base64
import os
import json
import hashlib
import hmac
from typing import Dict, Any, Optional, List, Tuple


class PlayIntegrityNonceManager:
    """
    Bước 1: Quản lý Nonce chống tấn công phát lại (Replay Attack).
    - Độ dài tối thiểu 16 bytes, mã hóa Base64 URL-safe.
    - Gắn với action/session và có TTL ngắn (1-3 phút).
    - Chỉ được sử dụng đúng 1 lần (Single-use).
    """

    def __init__(self, ttl_seconds: int = 180, secret_key: Optional[str] = None):
        self.ttl = ttl_seconds
        self.secret_key = secret_key or base64.b64encode(os.urandom(32)).decode("ascii")
        # Bộ nhớ lưu nonce tạm thời: {nonce_str: {"timestamp": float, "action": str, "used": bool}}
        self._nonce_cache: Dict[str, Dict[str, Any]] = {}

    def generate_nonce(self, session_id: str, action: str) -> str:
        """Sinh nonce an toàn kết hợp timestamp và chữ ký HMAC."""
        timestamp = time.time()
        raw_payload = f"{session_id}:{action}:{timestamp}:{os.urandom(16).hex()}"
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            raw_payload.encode("utf-8"),
            hashlib.sha256
        ).digest()
        # Ghép raw + signature rồi encode base64 url-safe
        combined = raw_payload.encode("utf-8") + b"::" + signature
        nonce = base64.urlsafe_b64encode(combined).decode("ascii").rstrip("=")
        
        # Lưu vào cache với TTL
        self._nonce_cache[nonce] = {
            "timestamp": timestamp,
            "session_id": session_id,
            "action": action,
            "used": False
        }
        self._clean_expired()
        return nonce

    def validate_and_consume_nonce(self, nonce: str, expected_action: Optional[str] = None) -> Tuple[bool, str]:
        """Xác thực nonce: Kiểm tra tồn tại, hạn dùng và trạng thái tiêu thụ."""
        self._clean_expired()
        if nonce not in self._nonce_cache:
            return False, "Nonce không tồn tại hoặc đã hết hạn"

        entry = self._nonce_cache[nonce]
        if entry["used"]:
            return False, "Replay Attack: Nonce đã được sử dụng trước đó"

        if time.time() - entry["timestamp"] > self.ttl:
            del self._nonce_cache[nonce]
            return False, "Nonce đã quá thời gian sống (TTL expired)"

        if expected_action and entry["action"] != expected_action:
            return False, f"Hành động không khớp: mong đợi {expected_action}, nhận {entry['action']}"

        # Đánh dấu đã dùng
        entry["used"] = True
        return True, "Nonce hợp lệ"

    def _clean_expired(self):
        now = time.time()
        expired = [k for k, v in self._nonce_cache.items() if now - v["timestamp"] > self.ttl * 2]
        for k in expired:
            del self._nonce_cache[k]


class GooglePlayIntegrityVerifier:
    """
    Bước 4: Backend giải mã & thẩm định Integrity Token theo quy chuẩn Google Play Console API.
    Endpoint mô phỏng: https://playintegrity.googleapis.com/v1/{packageName}:decodeIntegrityToken
    """

    OFFICIAL_FB4A_PACKAGE = "com.facebook.katana"
    # Cert SHA256 digest chính thức của Facebook Katana release APK
    OFFICIAL_FB4A_CERT_DIGESTS = [
        "8a3f342bb301646fb3e61f54e858dbd1e54e3e19298e09ce29f471a64ec61f2c",
        "ba3e4c760822607198f3780a40f1a92a7e78051752b12cf2fa8bf7d2d3851532"
    ]

    def __init__(self, nonce_manager: PlayIntegrityNonceManager, expected_package: str = OFFICIAL_FB4A_PACKAGE):
        self.nonce_manager = nonce_manager
        self.expected_package = expected_package

    def evaluate_verdict(self, payload: Dict[str, Any], expected_action: Optional[str] = None) -> Dict[str, Any]:
        """
        Thẩm định chi tiết 4 tiêu chuẩn bắt buộc:
        1. Nonce khớp & chưa từng dùng
        2. Package name khớp
        3. Chữ ký chứng chỉ (Certificate digest) khớp
        4. deviceRecognitionVerdict đạt chuẩn (MEETS_DEVICE_INTEGRITY / MEETS_STRONG_INTEGRITY)
        """
        results = {
            "is_valid": False,
            "risk_level": "CRITICAL",
            "checks": {},
            "verdict_details": payload,
            "reasons": []
        }

        # 1. Kiểm tra Nonce
        req_details = payload.get("requestDetails", {})
        nonce = req_details.get("nonce", "")
        nonce_valid, nonce_msg = self.nonce_manager.validate_and_consume_nonce(nonce, expected_action)
        results["checks"]["nonce_verification"] = {
            "passed": nonce_valid,
            "message": nonce_msg
        }
        if not nonce_valid:
            results["reasons"].append(f"Nonce thất bại: {nonce_msg}")

        # 2. Kiểm tra Package Name
        pkg_name = req_details.get("requestPackageName", "")
        pkg_match = (pkg_name == self.expected_package)
        results["checks"]["package_name_match"] = {
            "passed": pkg_match,
            "expected": self.expected_package,
            "actual": pkg_name
        }
        if not pkg_match:
            results["reasons"].append(f"Sai Package Name: mong đợi {self.expected_package}, nhận {pkg_name}")

        # 3. Kiểm tra Chữ ký Chứng chỉ App (App Integrity)
        app_integrity = payload.get("appIntegrity", {})
        app_verdict = app_integrity.get("appRecognitionVerdict", "")
        certs = [c.lower() for c in app_integrity.get("certificateSha256Digest", [])]
        
        cert_matched = any(c in [digest.lower() for digest in self.OFFICIAL_FB4A_CERT_DIGESTS] for c in certs)
        results["checks"]["app_integrity"] = {
            "app_verdict": app_verdict,
            "cert_matched": cert_matched,
            "is_play_recognized": (app_verdict == "PLAY_RECOGNIZED")
        }
        if app_verdict != "PLAY_RECOGNIZED":
            results["reasons"].append(f"App không phải bản phân phối chính hãng Google Play: {app_verdict}")
        if not cert_matched and self.expected_package == self.OFFICIAL_FB4A_PACKAGE:
            results["reasons"].append("Chứng chỉ SHA256 không khớp với bản phát hành gốc (nghi vấn bị Mod/Re-sign)")

        # 4. Kiểm tra Độ tin cậy Thiết bị (Device Integrity)
        device_integrity = payload.get("deviceIntegrity", {})
        verdicts: List[str] = device_integrity.get("deviceRecognitionVerdict", [])
        
        meets_basic = "MEETS_BASIC_INTEGRITY" in verdicts
        meets_device = "MEETS_DEVICE_INTEGRITY" in verdicts
        meets_strong = "MEETS_STRONG_INTEGRITY" in verdicts

        results["checks"]["device_integrity"] = {
            "verdicts": verdicts,
            "meets_basic": meets_basic,
            "meets_device": meets_device,
            "meets_strong": meets_strong
        }

        if not verdicts:
            results["risk_level"] = "CRITICAL"
            results["reasons"].append("Thiết bị không được nhận diện (Giả lập không bản quyền, môi trường debug/hook)")
        elif not meets_device and not meets_strong:
            results["risk_level"] = "HIGH"
            results["reasons"].append("Thiết bị chỉ đạt BASIC_INTEGRITY (Nghi vấn đã Root, Mở Bootloader hoặc Magisk/Xposed)")
        elif meets_strong:
            results["risk_level"] = "TRUSTED"
        elif meets_device:
            results["risk_level"] = "LOW"

        # 5. Quyết định cuối cùng
        has_critical_error = bool(results["reasons"])
        results["is_valid"] = not has_critical_error and (meets_device or meets_strong)
        if results["is_valid"]:
            results["decision"] = "ALLOW_REQUEST"
        else:
            results["decision"] = "REJECT_OR_CHALLENGE"

        return results


def explain_standalone_script_vulnerability() -> Dict[str, str]:
    """
    Giải thích kỹ thuật: Tại sao một script Python ngoài (như fb_reg.py hiện tại)
    không thể tự sinh Token Play Integrity hợp lệ?
    """
    return {
        "Hardware_Root_Of_Trust": (
            "Google Play Services tương tác trực tiếp với TEE (Trusted Execution Environment) "
            "hoặc chip StrongBox/KeyMint trên thiết bị vật lý để ký số qua private key được nhúng "
            "tại nhà máy. Python chạy trên máy tính hoàn toàn không có quyền truy cập phần cứng này."
        ),
        "Google_Server_Signature": (
            "Integrity Token trả về là một JWT được ký số bằng private key độc quyền của Google "
            "(Google Cloud KMS). Server của đối tác (Meta) sẽ giải mã trực tiếp qua Google API, "
            "bất kỳ token nào do script tự 'bịa' chuỗi base64 sẽ bị Google từ chối ngay lập tức."
        ),
        "Nonce_Anti_Replay": (
            "Token không thể dùng lại (re-use) giữa các máy hoặc từ lần đăng ký trước, "
            "vì mỗi token gắn chặt với Nonce ngẫu nhiên do backend cấp có thời hạn 1-3 phút."
        ),
        "Impact_On_Reg_Tool": (
            "Dự án fb_reg.py hiện tại chỉ tạo chuỗi giả lập (mock strings) cho AAC token và reg_context. "
            "Nếu Facebook áp dụng Play Integrity kiểm tra tại bước đăng ký CAA, request script thuần "
            "sẽ bị chặn 100% tại Gateway nếu không có thiết bị Android thật thực hiện attestation."
        )
    }
