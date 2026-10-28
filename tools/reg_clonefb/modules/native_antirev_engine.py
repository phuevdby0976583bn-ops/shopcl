# -*- coding: utf-8 -*-
"""
modules/native_antirev_engine.py
Nghiên cứu & thẩm định cơ chế chống đảo ngược mã nguồn Native (Anti-Reverse Engineering):
1. Gọi hệ thống trực tiếp (Inline Direct Syscall): Vượt qua hook libc của Frida (svc #0).
2. Phát hiện điểm ngắt phần mềm (Software Breakpoint Detection: BKPT 0, BRK #0).
3. Quét luồng nền & bộ nhớ động (Anti-Frida Agent, gum-js-loop, /proc/self/maps).
4. Đánh giá tính toàn vẹn Native (Native Integrity Risk Score: 0.0 -> 1.0).
"""

import hashlib
import struct
import time
from typing import Dict, Any, List, Optional, Tuple


class DirectSyscallEngine:
    """Mô phỏng cơ chế Direct Syscall (gọi trực tiếp kernel qua mã máy asm svc #0)."""

    # Bảng số hiệu Syscall chuẩn trên nhân Linux ARM64 (aarch64)
    ARM64_SYSCALL_TABLE = {
        "openat": 56,
        "read": 63,
        "write": 64,
        "close": 57,
        "ptrace": 117,
        "kill": 129,
        "getpid": 172,
        "nanosleep": 101,
        "exit_group": 94,
    }

    # Bảng số hiệu Syscall trên Linux ARM32 (EABI)
    ARM32_SYSCALL_TABLE = {
        "open": 5,
        "read": 3,
        "write": 4,
        "close": 6,
        "ptrace": 26,
        "kill": 37,
        "getpid": 20,
    }

    @classmethod
    def get_inline_syscall_stub(cls, syscall_name: str, arch: str = "arm64") -> Dict[str, Any]:
        """
        Mô phỏng đoạn mã assembly chèn trực tiếp vào hàm native C/C++:
        ARM64:
            mov x8, #<syscall_num>
            svc #0
        Kỹ thuật này đi tắt qua kernel, không gọi tới biểu tượng trong libc.so.
        """
        if arch == "arm64":
            sc_num = cls.ARM64_SYSCALL_TABLE.get(syscall_name, 0)
            # Opcode mã máy ARM64: svc #0 là 0xD4000001 (little endian: 01 00 00 d4)
            assembly = f"mov x8, #{sc_num}\nsvc #0"
            bypasses_libc_hook = True
        else:
            sc_num = cls.ARM32_SYSCALL_TABLE.get(syscall_name, 0)
            assembly = f"mov r7, #{sc_num}\nsvc 0"
            bypasses_libc_hook = True

        return {
            "syscall_name": syscall_name,
            "syscall_number": sc_num,
            "architecture": arch,
            "assembly_instruction": assembly,
            "bypasses_libc_interceptor": bypasses_libc_hook,
            "defense_mechanism": "Inline Assembly Syscall prevents Frida Interceptor.attach on libc.so symbols."
        }


class BreakpointAuditor:
    """Phát hiện các điểm ngắt phần mềm (Software Breakpoints) do Debugger hoặc Dynamic Hooks cấy vào."""

    # Mã máy Opcode của lệnh ngắt trên các kiến trúc vi xử lý
    BREAKPOINT_OPCODES = {
        "arm64": [
            b"\x00\x00\x20\xd4",  # BRK #0 (0xD4200000)
            b"\x00\xf0\x3e\xd4",  # BRK #0xF000 (GDB ARM64)
        ],
        "arm32": [
            b"\x70\x00\x20\xe1",  # BKPT 0 (0xE1200070)
        ],
        "thumb": [
            b"\x00\xbe",          # BKPT 0 (0xBE00)
        ],
        "x86": [
            b"\xcc",              # INT 3 (0xCC)
        ]
    }

    @classmethod
    def scan_memory_opcodes(cls, code_bytes: bytes, arch: str = "arm64") -> Dict[str, Any]:
        """
        Quét trang bộ nhớ .text của thư viện ELF (.so) tìm opcode ngắt phần mềm.
        Nếu phát hiện byte opcode ngắt -> Ứng dụng đang bị gắn Debugger hoặc Frida inline patch.
        """
        target_opcodes = cls.BREAKPOINT_OPCODES.get(arch, cls.BREAKPOINT_OPCODES["arm64"])
        detected_offsets = []

        for bp in target_opcodes:
            start = 0
            while True:
                idx = code_bytes.find(bp, start)
                if idx == -1:
                    break
                detected_offsets.append({
                    "offset": hex(idx),
                    "opcode_hex": bp.hex(),
                    "arch": arch
                })
                start = idx + len(bp)

        is_tampered = len(detected_offsets) > 0
        return {
            "has_software_breakpoints": is_tampered,
            "detected_breakpoints": detected_offsets,
            "risk_score": 0.85 if is_tampered else 0.0,
            "verdict": "CODE_INTEGRITY_COMPROMISED" if is_tampered else "CODE_INTEGRITY_CLEAN"
        }

    @classmethod
    def verify_function_prologue_checksum(
        cls,
        current_prologue: bytes,
        reference_checksum: str
    ) -> bool:
        """Kiểm tra mã băm SHA-256 phần mở đầu hàm native (Function Prologue Integrity)."""
        current_hash = hashlib.sha256(current_prologue).hexdigest()
        return current_hash == reference_checksum


class AntiFridaAuditor:
    """Quét các dấu hiệu đặc trưng của công cụ Frida Dynamic Instrumentation."""

    FRIDA_THREAD_NAMES = [
        "gum-js-loop",
        "gmain",
        "gdbus",
        "pool-frida",
        "frida-gadget",
        "lin.frida",
    ]

    SUSPICIOUS_LIBRARIES = [
        "frida-agent.so",
        "frida-gadget.so",
        "libxposed.so",
        "libsandhook.so",
        "libsubstrate.so",
        "libepic.so",
        "libmemtracer.so",
    ]

    FRIDA_PORTS = [27042, 27043, 27044]

    @classmethod
    def scan_runtime_threads(cls, thread_names: List[str]) -> List[str]:
        """Quét danh sách các thread nền trong /proc/self/task/."""
        found = []
        for th in thread_names:
            th_clean = th.strip().lower()
            for bad_th in cls.FRIDA_THREAD_NAMES:
                if bad_th in th_clean:
                    found.append(th)
        return found

    @classmethod
    def scan_memory_maps(cls, maps_content: str) -> List[str]:
        """Quét tập tin /proc/self/maps tìm các thư viện can thiệp inject vào bộ nhớ."""
        found = []
        for line in maps_content.splitlines():
            line_clean = line.strip().lower()
            for lib in cls.SUSPICIOUS_LIBRARIES:
                if lib in line_clean:
                    found.append(lib)
        return sorted(list(set(found)))

    @classmethod
    def audit_native_environment(
        cls,
        threads: Optional[List[str]] = None,
        maps_text: str = "",
        open_ports: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Đánh giá toàn diện rủi ro can thiệp native Frida & hooking."""
        threads = threads or []
        open_ports = open_ports or []

        detected_threads = cls.scan_runtime_threads(threads)
        detected_libs = cls.scan_memory_maps(maps_text)
        detected_ports = [p for p in open_ports if p in cls.FRIDA_PORTS]

        threats = []
        risk_score = 0.0

        if detected_threads:
            threats.extend([f"FRIDA_THREAD_{t}" for t in detected_threads])
            risk_score += 0.50
        if detected_libs:
            threats.extend([f"INJECTED_LIB_{l}" for l in detected_libs])
            risk_score += 0.50
        if detected_ports:
            threats.extend([f"FRIDA_SERVER_PORT_{p}" for p in detected_ports])
            risk_score += 0.30

        total_risk = min(1.0, round(risk_score, 2))
        is_secure = total_risk < 0.20

        return {
            "is_native_secure": is_secure,
            "risk_score": total_risk,
            "detected_threats": threats,
            "verdict": "NATIVE_ENVIRONMENT_SECURE" if is_secure else "ACTIVE_HOOK_DETECTION_TRIGGERED"
        }


class NativeIntegrityAuditor:
    """Bộ giải pháp kết hợp toàn diện kiểm định Native (Syscall, Breakpoint & Anti-Frida)."""

    @classmethod
    def get_genuine_native_report(cls) -> Dict[str, Any]:
        """Tạo báo cáo kiểm định sạch cho thiết bị thật không can thiệp."""
        return {
            "syscall_mode": "DIRECT_SVC_HARDENED",
            "breakpoints_detected": 0,
            "frida_threads_detected": 0,
            "injected_libraries": 0,
            "native_risk_score": 0.0,
            "verdict": "SECURE"
        }

    @classmethod
    def evaluate_process_integrity(
        cls,
        threads: Optional[List[str]] = None,
        maps_text: str = "",
        code_segment: Optional[bytes] = None,
        open_ports: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Đánh giá tổng hợp tính toàn vẹn của mã nhị phân native và tiến trình."""
        frida_res = AntiFridaAuditor.audit_native_environment(threads, maps_text, open_ports)

        bp_res = {"has_software_breakpoints": False, "risk_score": 0.0}
        if code_segment:
            bp_res = BreakpointAuditor.scan_memory_opcodes(code_segment, arch="arm64")

        composite_risk = max(frida_res["risk_score"], bp_res["risk_score"])
        is_clean = composite_risk < 0.20

        return {
            "is_tamper_free": is_clean,
            "composite_risk_score": composite_risk,
            "frida_audit": frida_res,
            "breakpoint_audit": bp_res,
            "verdict": "NATIVE_SHIELD_INTACT" if is_clean else "HOOK_OR_DEBUGGER_COMPROMISED"
        }

class SeccompSandboxAuditor:
    """Mô phỏng bộ lọc Seccomp-BPF (Secure Computing) chặn syscall nguy hiểm & tiến trình cô lập."""

    BLOCKED_DEBUG_SYSCALLS = [
        "ptrace",              # __NR_ptrace (117)
        "process_vm_readv",    # __NR_process_vm_readv (270)
        "process_vm_writev",   # __NR_process_vm_writev (271)
    ]

    @classmethod
    def get_seccomp_bpf_policy(cls) -> Dict[str, Any]:
        """Tạo chính sách BPF filter cấu hình trong nhân Linux."""
        return {
            "mode": "SECCOMP_MODE_FILTER",
            "blocked_syscalls": cls.BLOCKED_DEBUG_SYSCALLS,
            "action_on_violation": "SECCOMP_RET_KILL_PROCESS (SIGSYS)",
            "is_memory_sealed": True,
            "isolated_process_enabled": True
        }

    @classmethod
    def audit_process_sandbox(cls, invoked_syscalls: List[str], has_isolated_process: bool = True) -> Dict[str, Any]:
        """Thẩm định xem có syscall nguy hiểm cố tình đọc bộ nhớ app hay không."""
        violations = []
        for sc in invoked_syscalls:
            if sc in cls.BLOCKED_DEBUG_SYSCALLS:
                violations.append(f"BLOCKED_SYSCALL_TRIGGERED_{sc.upper()}")

        if not has_isolated_process:
            violations.append("NO_ISOLATED_PROCESS_SANDBOX")

        is_safe = len(violations) == 0
        return {
            "is_sandbox_intact": is_safe,
            "violations": violations,
            "risk_score": 0.0 if is_safe else 0.75,
            "verdict": "SECCOMP_BPF_ACTIVE_SECURE" if is_safe else "SANDBOX_BREACH_DETECTED"
        }
