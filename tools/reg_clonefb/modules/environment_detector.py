# -*- coding: utf-8 -*-
"""
modules/environment_detector.py
Nghiên cứu & thẩm định môi trường hệ điều hành và thiết bị (Environment & OS Integrity):
1. Dấu hiệu máy ảo (Emulator Artifacts): QEMU/Goldfish pipes, vboxguest, CPU ABI, ro.hardware.
2. Dấu hiệu can thiệp hệ thống (Root / Magisk / KernelSU): su, busybox, mount namespaces, SELinux.
3. Đánh giá tính toàn vẹn môi trường (Environment Integrity Risk Score: 0.0 -> 1.0).
"""

import re
import time
from typing import Dict, Any, List, Optional, Tuple


class EmulatorDetector:
    """Phát hiện các tệp tin, trình điều khiển và thông số Build đặc trưng của máy ảo Android."""

    EMULATOR_DEVICE_FILES = [
        "/dev/qemu_pipe",
        "/dev/socket/qemud",
        "/dev/goldfish_pipe",
        "/dev/vboxguest",
        "/dev/vboxuser",
        "/sys/qemu_trace",
        "/dev/ldplayer_pipe",
        "/dev/nox_guest",
        "/system/lib/libc_malloc_debug_qemu.so",
        "/system/bin/nox-prop",
    ]

    SUSPICIOUS_HARDWARE_NAMES = [
        "goldfish", "ranchu", "vbox86", "vbox", "nox",
        "ttvm_x86", "andy", "bluestacks", "genymotion"
    ]

    SUSPICIOUS_CPU_FEATURES = ["hypervisor", "qemu", "intel", "amd"]

    @classmethod
    def audit_filesystem_pipes(cls, existing_files: List[str]) -> List[str]:
        """Quét sự xuất hiện của file thiết bị máy ảo trong hệ thống tập tin."""
        found = []
        for path in existing_files:
            clean_path = path.strip().lower()
            for emu_file in cls.EMULATOR_DEVICE_FILES:
                if emu_file.lower() == clean_path:
                    found.append(emu_file)
        return found

    @classmethod
    def audit_build_properties(cls, build_props: Dict[str, str]) -> Dict[str, Any]:
        """Kiểm tra tính nhất quán của build properties (ro.hardware, ro.product.board...)."""
        flags = []
        hw = build_props.get("ro.hardware", "").lower()
        board = build_props.get("ro.product.board", "").lower()
        brand = build_props.get("ro.product.brand", "").lower()
        model = build_props.get("ro.product.model", "").lower()
        fingerprint = build_props.get("ro.build.fingerprint", "").lower()

        # Kiểm tra phần cứng
        for bad_hw in cls.SUSPICIOUS_HARDWARE_NAMES:
            if bad_hw in hw or bad_hw in board:
                flags.append(f"EMULATOR_HARDWARE_{bad_hw.upper()}")

        # Kiểm tra fingerprint chứa dấu hiệu generic/test-keys
        if "generic" in fingerprint or "test-keys" in fingerprint or "vbox" in fingerprint:
            flags.append("GENERIC_EMULATOR_FINGERPRINT")

        # Kiểm tra thương hiệu generic
        if brand in ("generic", "android") or model in ("sdk", "emulator", "google_sdk"):
            flags.append("GENERIC_SDK_MODEL_BRAND")

        return {
            "has_emulator_props": len(flags) > 0,
            "flags": flags,
        }

    @classmethod
    def audit_cpu_abi_consistency(cls, declared_abi: str, cpu_model_string: str) -> Dict[str, Any]:
        """
        Kiểm tra độ vênh giữa CPU thật và ABI khai báo:
        Máy ảo chạy trên PC x86/x86_64 thường dùng libndk/Houdini dịch mã ARM.
        Nếu app khai báo arm64-v8a nhưng CPU model báo Intel/AMD/hypervisor -> Bất thường.
        """
        cpu_lower = cpu_model_string.lower()
        is_x86_host = any(feat in cpu_lower for feat in cls.SUSPICIOUS_CPU_FEATURES)

        is_arm_declared = "arm" in declared_abi.lower()
        mismatch = is_x86_host and is_arm_declared

        return {
            "is_abi_consistent": not mismatch,
            "declared_abi": declared_abi,
            "cpu_host": cpu_model_string,
            "translated_execution_detected": mismatch
        }


class RootIntegrityAuditor:
    """Phát hiện can thiệp Superuser, Magic Mount của Magisk/KernelSU và chế độ SELinux."""

    KNOWN_SU_PATHS = [
        "/sbin/su",
        "/system/bin/su",
        "/system/xbin/su",
        "/data/local/xbin/su",
        "/data/local/bin/su",
        "/system/sd/xbin/su",
        "/system/bin/failsafe/su",
        "/data/local/su",
        "/system/bin/busybox",
        "/system/xbin/busybox",
        "/system/bin/magisk",
    ]

    ROOT_PACKAGES = [
        "com.topjohnwu.magisk",
        "me.weishu.kernelsu",
        "io.github.a13e300.ksu",
        "eu.chainfire.supersu",
        "com.koushikdutta.superuser"
    ]

    @classmethod
    def audit_su_binaries(cls, existing_binaries: List[str]) -> List[str]:
        """Quét tìm nhị phân su / busybox trong các đường dẫn chuẩn."""
        found = []
        for path in existing_binaries:
            clean = path.strip().lower()
            for su_path in cls.KNOWN_SU_PATHS:
                if su_path.lower() == clean:
                    found.append(su_path)
        return found

    @classmethod
    def audit_mount_namespaces(cls, proc_mounts_content: str) -> Dict[str, Any]:
        """
        Đọc /proc/self/mounts phát hiện kỹ thuật che giấu của Magisk:
        - Magic Mount (gắn kết /system lặp)
        - overlayfs gắn đè lên /system hoặc /vendor
        - Gắn kết thư mục mirror (/sbin/.magisk/mirror)
        """
        suspicious_mounts = []
        for line in proc_mounts_content.splitlines():
            line_lower = line.strip().lower()
            if not line_lower:
                continue

            # Phát hiện Magisk mirror / worker
            if "magisk" in line_lower:
                suspicious_mounts.append("MAGISK_MAGIC_MOUNT")
            # Phát hiện overlayfs trên phân vùng read-only của hệ thống
            if "overlay" in line_lower and ("/system" in line_lower or "/vendor" in line_lower or "/product" in line_lower):
                suspicious_mounts.append("SYSTEMLESS_OVERLAYFS_ON_SYSTEM")
            # Phát hiện KSU (KernelSU) mount
            if "kernelsu" in line_lower or "/data/adb" in line_lower:
                suspicious_mounts.append("KERNELSU_DATA_MOUNT")

        unique_suspicious = sorted(list(set(suspicious_mounts)))
        return {
            "has_mount_tampering": len(unique_suspicious) > 0,
            "detected_mounts": unique_suspicious
        }

    @classmethod
    def audit_selinux_mode(cls, selinux_enforce_val: int) -> Dict[str, Any]:
        """
        SELinux Enforcing (1) là bắt buộc trên thiết bị Android chuẩn.
        Permissive (0) hoặc Disabled (-1) là dấu hiệu ROM độ hoặc máy đã can thiệp root.
        """
        is_enforcing = selinux_enforce_val == 1
        return {
            "is_enforcing": is_enforcing,
            "mode_name": "Enforcing" if is_enforcing else ("Permissive" if selinux_enforce_val == 0 else "Disabled"),
            "risk_score": 0.0 if is_enforcing else 0.50
        }


class EnvironmentDetector:
    """Bộ giải pháp toàn diện đánh giá môi trường thực thi (Genuine Phone vs Emulator/Root)."""

    @classmethod
    def evaluate_genuine_device(cls, device_preset: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo profile môi trường sạch, chuẩn phần cứng thật cho thiết bị nghiên cứu."""
        return {
            "is_genuine_hardware": True,
            "device_brand": device_preset.get("brand", "Xiaomi"),
            "device_model": device_preset.get("model", "Redmi Note 11"),
            "cpu_architecture": "arm64-v8a",
            "selinux_state": "Enforcing",
            "root_status": "NOT_ROOTED",
            "emulator_status": "PHYSICAL_DEVICE",
            "environment_risk_score": 0.0,
            "passed": True
        }

    @classmethod
    def audit_environment(
        cls,
        files_present: Optional[List[str]] = None,
        build_props: Optional[Dict[str, str]] = None,
        cpu_model: str = "ARMv8 Processor rev 4 (v8l)",
        declared_abi: str = "arm64-v8a",
        mounts_text: str = "",
        selinux_val: int = 1
    ) -> Dict[str, Any]:
        """Đánh giá toàn diện rủi ro môi trường thực thi."""
        files = files_present or []
        props = build_props or {
            "ro.hardware": "qcom",
            "ro.product.board": "spes",
            "ro.product.brand": "Xiaomi",
            "ro.product.model": "2201117TY",
            "ro.build.fingerprint": "Xiaomi/spes_eea/spes:12/SKQ1.211103.001/V13.0.5.0.SKCEUXM:user/release-keys"
        }

        # 1. Quét Emulator
        emu_files = EmulatorDetector.audit_filesystem_pipes(files)
        emu_props = EmulatorDetector.audit_build_properties(props)
        cpu_check = EmulatorDetector.audit_cpu_abi_consistency(declared_abi, cpu_model)

        # 2. Quét Root
        su_files = RootIntegrityAuditor.audit_su_binaries(files)
        mount_check = RootIntegrityAuditor.audit_mount_namespaces(mounts_text)
        selinux_check = RootIntegrityAuditor.audit_selinux_mode(selinux_val)

        # Tính điểm rủi ro
        risk_score = 0.0
        threats = []

        if emu_files:
            threats.extend(emu_files)
            risk_score += 0.50
        if emu_props["has_emulator_props"]:
            threats.extend(emu_props["flags"])
            risk_score += 0.40
        if cpu_check["translated_execution_detected"]:
            threats.append("ARM_TRANSLATED_ON_X86_CPU")
            risk_score += 0.35

        if su_files:
            threats.extend(su_files)
            risk_score += 0.55
        if mount_check["has_mount_tampering"]:
            threats.extend(mount_check["detected_mounts"])
            risk_score += 0.40
        if not selinux_check["is_enforcing"]:
            threats.append(f"SELINUX_{selinux_check['mode_name'].upper()}")
            risk_score += selinux_check["risk_score"]

        total_risk = min(1.0, round(risk_score, 2))
        is_clean = total_risk < 0.25

        return {
            "is_clean_environment": is_clean,
            "environment_risk_score": total_risk,
            "detected_threats": threats,
            "emulator_report": {
                "detected_files": emu_files,
                "property_flags": emu_props["flags"],
                "cpu_abi_status": cpu_check
            },
            "root_report": {
                "su_binaries": su_files,
                "mount_tampering": mount_check["detected_mounts"],
                "selinux": selinux_check
            },
            "verdict": "GENUINE_SECURE_PHONE" if is_clean else "HOSTILE_ENVIRONMENT_DETECTED"
        }

class TelephonyBtsAuditor:
    """Mô phỏng và thẩm định Trạng thái SIM Vật lý & Trạm phát sóng di động lân cận (BTS Towers)."""

    SIM_STATES = {
        0: "SIM_STATE_UNKNOWN",
        1: "SIM_STATE_ABSENT",
        5: "SIM_STATE_READY",
    }

    @classmethod
    def get_genuine_telephony_profile(cls, carrier: str = "Viettel") -> Dict[str, Any]:
        """Tạo thông số SIM vật lý và 3-5 trạm BTS lân cận chuẩn điện thoại thật."""
        carrier_lower = carrier.lower()
        if "viettel" in carrier_lower:
            op_name = "Viettel"
            mcc_mnc = "45204"
        elif "mobifone" in carrier_lower:
            op_name = "MobiFone"
            mcc_mnc = "45201"
        else:
            op_name = "VN VINAPHONE"
            mcc_mnc = "45202"

        # 3 trạm BTS lân cận với cường độ tín hiệu sóng di động (RSRP: -85 dBm đến -105 dBm)
        towers = [
            {"cell_id": 1402831, "pci": 214, "rsrp_dbm": -88, "rsrq_db": -9, "band": 3},
            {"cell_id": 1402832, "pci": 215, "rsrp_dbm": -96, "rsrq_db": -12, "band": 3},
            {"cell_id": 1405109, "pci": 88,  "rsrp_dbm": -104, "rsrq_db": -14, "band": 8},
        ]

        return {
            "sim_state": "SIM_STATE_READY",
            "sim_state_code": 5,
            "operator_name": op_name,
            "operator_numeric": mcc_mnc,
            "is_roaming": False,
            "neighboring_bts_towers": towers,
            "bts_tower_count": len(towers),
            "primary_cell_id": 1402831
        }

    @classmethod
    def audit_telephony_state(cls, sim_state_code: int, bts_count: int) -> Dict[str, Any]:
        """
        Thẩm định trạng thái sóng di động:
        - Máy ảo hoặc thiết bị chạy script thường không cắm SIM vật lý (SIM_STATE_ABSENT = 1)
        - Thiếu thông tin trạm phát sóng lân cận (bts_count = 0).
        """
        violations = []
        risk_score = 0.0

        if sim_state_code != 5:
            violations.append(f"INACTIVE_SIM_STATE_{cls.SIM_STATES.get(sim_state_code, 'UNKNOWN')}")
            risk_score += 0.40

        if bts_count < 2:
            violations.append("NO_NEIGHBORING_BTS_CELL_TOWERS")
            risk_score += 0.35

        is_genuine = len(violations) == 0
        return {
            "is_genuine_telephony": is_genuine,
            "violations": violations,
            "risk_score": min(1.0, round(risk_score, 2)),
            "verdict": "PHYSICAL_CELLULAR_DEVICE" if is_genuine else "WIFI_ONLY_OR_EMULATOR_WITHOUT_CELLULAR"
        }
