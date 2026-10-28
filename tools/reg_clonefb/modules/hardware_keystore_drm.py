# -*- coding: utf-8 -*-
"""
modules/hardware_keystore_drm.py
Nghiên cứu & thẩm định chứng thực phần cứng độc lập:
1. Android Key Attestation (TEE / StrongBox & OID 1.3.6.1.4.1.11129.2.1.17).
2. Widevine DRM Security Level (L1 Hardware TEE vs L3 Software Emulation).
3. Thẩm định tính nhất quán giữa Key Attestation và DRM (Cross-Verification).
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple


class HardwareAttestationEngine:
    """Mô phỏng và thẩm định cấu trúc Android Key Attestation Extension."""

    # OID chuẩn của Google Key Attestation Extension trong chứng chỉ X.509
    ATTESTATION_EXTENSION_OID = "1.3.6.1.4.1.11129.2.1.17"

    # Định nghĩa cấp độ bảo mật phần cứng
    SECURITY_LEVEL_SOFTWARE = 0
    SECURITY_LEVEL_TRUSTED_ENVIRONMENT = 1
    SECURITY_LEVEL_STRONGBOX = 2

    # Trạng thái Verified Boot
    BOOT_STATE_VERIFIED = 0    # Khóa gốc OEM, chưa can thiệp (Xanh lá)
    BOOT_STATE_SELFSIGNED = 1  # Đã mở khóa và ký bằng khóa riêng (Vàng)
    BOOT_STATE_UNVERIFIED = 2  # Bỏ qua xác thực boot (Cam)
    BOOT_STATE_FAILED = 3      # Xác thực thất bại (Đỏ)

    @classmethod
    def build_attestation_claim(
        cls,
        challenge: str,
        package_name: str = "com.facebook.katana",
        security_level: int = SECURITY_LEVEL_TRUSTED_ENVIRONMENT,
        device_locked: bool = True,
        verified_boot_state: int = BOOT_STATE_VERIFIED,
        cert_sha256: str = "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
        version_code: int = 44000031,
        os_version: int = 130000,
        os_patch_level: int = 202310
    ) -> Dict[str, Any]:
        """Tạo cấu trúc giải mã ASN.1 KeyDescription mô phỏng thiết bị Android thật."""
        sec_level_str = (
            "StrongBox" if security_level == cls.SECURITY_LEVEL_STRONGBOX
            else ("TrustedEnvironment" if security_level == cls.SECURITY_LEVEL_TRUSTED_ENVIRONMENT else "Software")
        )

        boot_state_names = {0: "Verified", 1: "SelfSigned", 2: "Unverified", 3: "Failed"}
        boot_state_str = boot_state_names.get(verified_boot_state, "Unverified")

        return {
            "extensionOid": cls.ATTESTATION_EXTENSION_OID,
            "attestationVersion": 300,  # KeyMint v3
            "attestationSecurityLevel": sec_level_str,
            "keymasterVersion": 300,
            "attestationChallenge": challenge,
            "uniqueId": hashlib.sha256(challenge.encode()).hexdigest()[:32],
            "softwareEnforced": {
                "creationDateTime": int(time.time() * 1000),
                "attestationApplicationId": {
                    "packageInfo": [
                        {
                            "packageName": package_name,
                            "version": version_code
                        }
                    ],
                    "signatureDigests": [cert_sha256]
                }
            },
            "teeEnforced": {
                "purpose": [2, 3],  # 2: Sign, 3: Verify
                "algorithm": 1,     # 1: RSA, 3: EC
                "keySize": 2048,
                "digest": [4],      # 4: SHA-256
                "osVersion": os_version,
                "osPatchLevel": os_patch_level,
                "rootOfTrust": {
                    "verifiedBootKey": hashlib.sha256(b"Google_OEM_Hardware_Root_Key").hexdigest(),
                    "deviceLocked": device_locked,
                    "verifiedBootState": verified_boot_state,
                    "bootStateName": boot_state_str,
                },
                "origin": 0         # 0: KM_ORIGIN_GENERATED (tạo bên trong enclave bảo mật)
            }
        }

    @classmethod
    def verify_attestation_claim(
        cls,
        claim: Dict[str, Any],
        expected_challenge: str,
        expected_package: str = "com.facebook.katana",
        expected_cert_hash: Optional[str] = None,
        require_hardware: bool = True
    ) -> Dict[str, Any]:
        """Thẩm định tính toàn vẹn của Key Attestation theo tiêu chuẩn Zero Trust."""
        violations = []
        risk_score = 0.0

        # 1. Kiểm tra Challenge Nonce
        if claim.get("attestationChallenge") != expected_challenge:
            violations.append("CHALLENGE_MISMATCH_OR_REPLAYED")
            risk_score += 0.50

        # 2. Kiểm tra Cấp độ bảo mật (attestationSecurityLevel)
        sec_level = claim.get("attestationSecurityLevel", "Software")
        if require_hardware and sec_level not in ("TrustedEnvironment", "StrongBox"):
            violations.append(f"UNTRUSTED_SECURITY_LEVEL_{sec_level.upper()}")
            risk_score += 0.45

        # 3. Kiểm tra Trạng thái Bootloader (deviceLocked)
        tee_enforced = claim.get("teeEnforced", {})
        root_of_trust = tee_enforced.get("rootOfTrust", {})
        if not root_of_trust.get("deviceLocked", False):
            violations.append("BOOTLOADER_UNLOCKED")
            risk_score += 0.35

        # 4. Kiểm tra Trạng thái Khởi động An toàn (verifiedBootState)
        boot_state = root_of_trust.get("verifiedBootState", cls.BOOT_STATE_UNVERIFIED)
        if boot_state != cls.BOOT_STATE_VERIFIED:
            violations.append(f"TAMPERED_BOOT_STATE_{root_of_trust.get('bootStateName', 'UNKNOWN')}")
            risk_score += 0.40

        # 5. Kiểm tra Package Name & Signature Digest
        app_id_info = claim.get("softwareEnforced", {}).get("attestationApplicationId", {})
        packages = [p.get("packageName") for p in app_id_info.get("packageInfo", [])]
        if expected_package not in packages:
            violations.append(f"PACKAGE_NAME_MISMATCH: expected {expected_package}, got {packages}")
            risk_score += 0.50

        if expected_cert_hash:
            certs = app_id_info.get("signatureDigests", [])
            if expected_cert_hash not in certs:
                violations.append("APP_SIGNATURE_MISMATCH")
                risk_score += 0.50

        is_passed = len(violations) == 0
        return {
            "passed": is_passed,
            "violations": violations,
            "security_level": sec_level,
            "bootloader_locked": root_of_trust.get("deviceLocked", False),
            "boot_state": root_of_trust.get("bootStateName", "Unknown"),
            "risk_score": min(1.0, round(risk_score, 2)),
            "verdict": "HARDWARE_ATTESTATION_PASSED" if is_passed else "ATTESTATION_FAILED"
        }


class WidevineDRMProfiler:
    """Mô phỏng và đối chiếu cấp độ bảo mật Widevine DRM (L1 vs L3)."""

    # UUID chuẩn quốc tế của hệ thống Widevine Modular DRM
    WIDEVINE_SCHEME_UUID = "edef8ba9-79d6-4ace-a3c8-27dcd51d21ed"

    @classmethod
    def get_drm_profile(
        cls,
        security_level: str = "L1",
        device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Tạo cấu trúc phản hồi MediaDrm.getPropertyString của Android."""
        dev_id = device_id or hashlib.sha256(b"device_entropy_katana").hexdigest()[:32]

        if security_level == "L1":
            return {
                "scheme_uuid": cls.WIDEVINE_SCHEME_UUID,
                "vendor": "Google",
                "version": "16.1.0",
                "description": "Widevine CDM with Hardware Root of Trust",
                "security_level": "L1",
                "system_id": 16342,
                "hdcp_level": "HDCP-2.2",
                "device_unique_id": dev_id,
                "is_hardware_backed": True,
                "is_genuine": True,
            }
        else:
            return {
                "scheme_uuid": cls.WIDEVINE_SCHEME_UUID,
                "vendor": "Google",
                "version": "1.0.0",
                "description": "Widevine Software CDM (Emulator / Custom ROM Fallback)",
                "security_level": "L3",
                "system_id": 9999,
                "hdcp_level": "Unprotected",
                "device_unique_id": dev_id,
                "is_hardware_backed": False,
                "is_genuine": False,
            }

    @classmethod
    def audit_drm_integrity(
        cls,
        drm_profile: Dict[str, Any],
        expected_level: str = "L1"
    ) -> Dict[str, Any]:
        """Đánh giá tính hợp lệ của Widevine DRM."""
        actual_level = drm_profile.get("security_level", "L3")
        is_hardware = drm_profile.get("is_hardware_backed", False)

        violations = []
        risk_score = 0.0

        if actual_level != expected_level:
            violations.append(f"DRM_LEVEL_MISMATCH: expected {expected_level}, got {actual_level}")
            risk_score += 0.40

        if expected_level == "L1" and not is_hardware:
            violations.append("DRM_LACKS_HARDWARE_DECRYPTION")
            risk_score += 0.50

        is_passed = len(violations) == 0
        return {
            "passed": is_passed,
            "actual_security_level": actual_level,
            "violations": violations,
            "risk_score": min(1.0, round(risk_score, 2)),
            "verdict": "GENUINE_WIDEVINE_L1" if actual_level == "L1" and is_passed else "SUSPICIOUS_WIDEVINE_L3"
        }


class HardwareKeystoreDRMEngine:
    """Bộ giải pháp đồng bộ kết hợp Key Attestation và Widevine DRM."""

    @classmethod
    def build_katana_hardware_profile(
        cls,
        challenge: str,
        package_name: str = "com.facebook.katana",
        security_level: str = "L1"
    ) -> Dict[str, Any]:
        """Tạo trọn bộ profile phần cứng chuẩn cho Android Katana."""
        sec_enum = (
            HardwareAttestationEngine.SECURITY_LEVEL_TRUSTED_ENVIRONMENT
            if security_level == "L1"
            else HardwareAttestationEngine.SECURITY_LEVEL_SOFTWARE
        )
        claim = HardwareAttestationEngine.build_attestation_claim(
            challenge=challenge,
            package_name=package_name,
            security_level=sec_enum,
            device_locked=True,
            verified_boot_state=HardwareAttestationEngine.BOOT_STATE_VERIFIED
        )
        drm = WidevineDRMProfiler.get_drm_profile(security_level=security_level)

        return {
            "attestation_claim": claim,
            "widevine_drm": drm,
            "hardware_rating": "TEE_L1_AUTHENTIC" if security_level == "L1" else "SOFTWARE_L3_VIRTUAL"
        }

    @classmethod
    def evaluate_cross_hardware_integrity(
        cls,
        attestation_claim: Dict[str, Any],
        drm_profile: Dict[str, Any],
        expected_challenge: str
    ) -> Dict[str, Any]:
        """
        Đối chiếu chéo (Cross-Verification):
        Nếu Key Attestation báo TEE nhưng Widevine báo L3 -> Phát hiện bất thường (Unlocked Bootloader).
        """
        att_res = HardwareAttestationEngine.verify_attestation_claim(
            attestation_claim, expected_challenge=expected_challenge
        )
        drm_res = WidevineDRMProfiler.audit_drm_integrity(drm_profile, expected_level="L1")

        cross_violations = []
        is_tee = att_res["security_level"] in ("TrustedEnvironment", "StrongBox")
        is_l1 = drm_res["actual_security_level"] == "L1"

        if is_tee and not is_l1:
            cross_violations.append("INCONSISTENCY: TEE_PRESENT_BUT_WIDEVINE_L3")
        elif not is_tee and is_l1:
            cross_violations.append("INCONSISTENCY: SOFTWARE_ATTESTATION_BUT_WIDEVINE_L1")

        composite_risk = (att_res["risk_score"] * 0.55) + (drm_res["risk_score"] * 0.35)
        if cross_violations:
            composite_risk += 0.20
        composite_risk = min(1.0, round(composite_risk, 3))

        return {
            "composite_risk_score": composite_risk,
            "is_hardware_trusted": composite_risk < 0.30,
            "attestation": att_res,
            "drm": drm_res,
            "cross_violations": cross_violations,
            "summary": "HARDWARE_SECURE_TEE_L1" if composite_risk < 0.30 else "HARDWARE_INTEGRITY_COMPROMISED"
        }
