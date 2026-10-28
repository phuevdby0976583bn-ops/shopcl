# -*- coding: utf-8 -*-
"""
modules/__init__.py
Cung cấp toàn bộ 16 cơ chế nghiên cứu phòng vệ & phân tích tính toàn vẹn (Full Enterprise Security Suite):
--- Nhóm nền tảng ---
1. PlayIntegrityVerifier (Google Play Integrity & SafetyNet)
2. NetworkRiskProfiler (ASN, CGNAT, MTU/MSS, Cellular vs Datacenter)
3. EmailIntegrityGuard (Disposable Email Address / DEA Detection)
4. BehavioralTelemetry (Micro-tremors 8-12Hz, Minimum Jerk, Pressure)
--- 5 Nhóm chuyên sâu doanh nghiệp ---
5. TransportFingerprint (TLS JA3/JA4, BoringSSL Liger, Akamai H2, HTTP/3 QUIC)
6. HardwareKeystoreDRM (Android Key Attestation TEE OID 1.3.6.1.4.1.11129.2.1.17, Widevine L1 vs L3)
7. EnvironmentDetector (Emulator Artifacts, Magisk/KernelSU, Mount Namespaces, SELinux, Telephony BTS)
8. NativeAntiRevEngine (Direct Syscall svc #0, Software Breakpoints, Anti-Frida, Seccomp-BPF)
9. VelocityGraphEngine (Battery Discharge, Thermal Fluctuation, Activity Lifecycle, Token Bucket, Device Graph)
--- 6 Nhóm mở rộng nâng cao ---
10. PoWChallengeEngine (Proof of Work Hashcash & Dynamic Client Puzzle)
11. HardwareGpuAudioProfiler (EGL OpenGL ES Adreno/Mali, Vulkan & Audio DAC Frame Buffer)
12. MultiSensorFusionEngine (Gyroscope Angular Velocity & Accelerometer Touch Torque Fusion)
"""

from .play_integrity_verifier import PlayIntegrityNonceManager, GooglePlayIntegrityVerifier
from .network_risk_profiler import NetworkRiskProfiler
from .email_integrity_guard import EmailIntegrityGuard
from .behavioral_telemetry import SensorTelemetryEngine, TouchKinematicsEngine

from .transport_fingerprint import (
    TlsFingerprintEngine,
    Http2FingerprintEngine,
    Http3QuicFingerprintEngine,
    TransportFingerprintEngine,
)
from .hardware_keystore_drm import (
    HardwareAttestationEngine,
    WidevineDRMProfiler,
    HardwareKeystoreDRMEngine,
)
from .environment_detector import (
    EmulatorDetector,
    RootIntegrityAuditor,
    EnvironmentDetector,
    TelephonyBtsAuditor,
)
from .native_antirev_engine import (
    DirectSyscallEngine,
    BreakpointAuditor,
    AntiFridaAuditor,
    NativeIntegrityAuditor,
    SeccompSandboxAuditor,
)
from .velocity_graph_engine import (
    BatteryThermalEngine,
    ActivityLifecycleManager,
    TokenBucketLimiter,
    LeakyBucketLimiter,
    BehaviorVelocityLimiter,
    DeviceGraphProfiler,
)
from .pow_challenge_engine import PoWChallengeEngine
from .hardware_gpu_audio_profiler import HardwareGpuAudioProfiler
from .multi_sensor_fusion import MultiSensorFusionEngine

__all__ = [
    # Nhóm nền tảng
    "PlayIntegrityNonceManager",
    "GooglePlayIntegrityVerifier",
    "NetworkRiskProfiler",
    "EmailIntegrityGuard",
    "SensorTelemetryEngine",
    "TouchKinematicsEngine",
    # Nhóm chuyên sâu
    "TlsFingerprintEngine",
    "Http2FingerprintEngine",
    "Http3QuicFingerprintEngine",
    "TransportFingerprintEngine",
    "HardwareAttestationEngine",
    "WidevineDRMProfiler",
    "HardwareKeystoreDRMEngine",
    "EmulatorDetector",
    "RootIntegrityAuditor",
    "EnvironmentDetector",
    "TelephonyBtsAuditor",
    "DirectSyscallEngine",
    "BreakpointAuditor",
    "AntiFridaAuditor",
    "NativeIntegrityAuditor",
    "SeccompSandboxAuditor",
    "BatteryThermalEngine",
    "ActivityLifecycleManager",
    "TokenBucketLimiter",
    "LeakyBucketLimiter",
    "BehaviorVelocityLimiter",
    "DeviceGraphProfiler",
    # Nhóm mở rộng nâng cao
    "PoWChallengeEngine",
    "HardwareGpuAudioProfiler",
    "MultiSensorFusionEngine",
]
