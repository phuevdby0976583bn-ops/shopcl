# -*- coding: utf-8 -*-
"""
modules/hardware_gpu_audio_profiler.py
Nghiên cứu & thẩm định Dấu vân tay GPU Phần cứng (OpenGL ES / Vulkan) & Audio DAC Latency:
1. Truy vấn ngữ cảnh đồ họa EGL/OpenGL ES (glGetString: GL_RENDERER, GL_VENDOR, GL_VERSION).
2. Phát hiện máy ảo/VPS dựa trên driver phần mềm (llvmpipe, SwiftShader, Mesa DRI, VirtualBox).
3. Đo lường kích thước buffer và độ trễ âm thanh di động (Audio DAC frames per buffer: 192/240/480).
"""

from typing import Dict, Any, List, Optional, Tuple


class HardwareGpuAudioProfiler:
    """Bộ máy phân tích và thẩm định GPU & Audio Subsystem của thiết bị Android."""

    # Danh sách các GPU renderer của máy ảo / PC x86 / phần mềm giả lập
    SUSPICIOUS_GPU_RENDERERS = [
        "llvmpipe",
        "swiftshader",
        "virtualbox",
        "vmware",
        "mesa dri",
        "intel(r) hd graphics",
        "intel(r) uhd graphics",
        "geforce gtx",
        "geforce rtx",
        "radeon rx",
        "microsoft basic render driver"
    ]

    # Danh sách các GPU di động chính hãng phổ biến trên Android
    GENUINE_MOBILE_GPUS = {
        "xiaomi": {"renderer": "Adreno (TM) 610", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0502.0"},
        "redmi": {"renderer": "Mali-G57 MC2", "vendor": "ARM", "version": "OpenGL ES 3.2 v1.r32p0"},
        "poco": {"renderer": "Adreno (TM) 730", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0530.0"},
        "oppo": {"renderer": "Adreno (TM) 619", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0502.0"},
        "samsung": {"renderer": "Mali-G57 MC2", "vendor": "ARM", "version": "OpenGL ES 3.2 v1.r32p0"},
        "vivo": {"renderer": "Adreno (TM) 610", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0502.0"},
        "realme": {"renderer": "Adreno (TM) 610", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0502.0"},
        "google": {"renderer": "Mali-G715", "vendor": "ARM", "version": "OpenGL ES 3.2 v1.r38p0"},
        "oneplus": {"renderer": "Adreno (TM) 740", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0615.0"},
        "sony": {"renderer": "Adreno (TM) 730", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0530.0"},
        "motorola": {"renderer": "Adreno (TM) 642L", "vendor": "Qualcomm", "version": "OpenGL ES 3.2 V@0502.0"},
        "huawei": {"renderer": "Mali-G76", "vendor": "ARM", "version": "OpenGL ES 3.2 v1.r26p0"},
    }

    @classmethod
    def get_genuine_gpu_profile(cls, brand: str = "xiaomi", model_name: str = "") -> Dict[str, Any]:
        """Tạo thông số GPU chuẩn phần cứng thật theo từng dòng máy và phân khúc Flagship/Midrange."""
        brand_key = brand.lower().strip()
        model_lower = model_name.lower().strip()

        # Flagship detection
        if "s24" in model_lower or "fold 5" in model_lower or "flip 5" in model_lower:
            return {
                "gl_renderer": "Adreno (TM) 750",
                "gl_vendor": "Qualcomm",
                "gl_version": "OpenGL ES 3.2 V@0755.0",
                "egl_vendor": "Android",
                "vulkan_supported": True,
                "vulkan_api_version": "1.3.268",
                "audio_frames_per_buffer": 192,
                "audio_sample_rate_hz": 48000,
                "is_hardware_accelerated": True,
            }
        elif "s23" in model_lower or "oneplus 12" in model_lower or "x100" in model_lower:
            return {
                "gl_renderer": "Adreno (TM) 740",
                "gl_vendor": "Qualcomm",
                "gl_version": "OpenGL ES 3.2 V@0615.0",
                "egl_vendor": "Android",
                "vulkan_supported": True,
                "vulkan_api_version": "1.3.243",
                "audio_frames_per_buffer": 192,
                "audio_sample_rate_hz": 48000,
                "is_hardware_accelerated": True,
            }
        elif "pixel 8" in model_lower:
            return {
                "gl_renderer": "Mali-G715",
                "gl_vendor": "ARM",
                "gl_version": "OpenGL ES 3.2 v1.r38p0",
                "egl_vendor": "Android",
                "vulkan_supported": True,
                "vulkan_api_version": "1.3.268",
                "audio_frames_per_buffer": 192,
                "audio_sample_rate_hz": 48000,
                "is_hardware_accelerated": True,
            }
        elif "pixel 7" in model_lower:
            return {
                "gl_renderer": "Mali-G78",
                "gl_vendor": "ARM",
                "gl_version": "OpenGL ES 3.2 v1.r32p0",
                "egl_vendor": "Android",
                "vulkan_supported": True,
                "vulkan_api_version": "1.1.128",
                "audio_frames_per_buffer": 192,
                "audio_sample_rate_hz": 48000,
                "is_hardware_accelerated": True,
            }
        elif "14" in model_lower and ("xiaomi" in brand_key or "poco" in brand_key):
            return {
                "gl_renderer": "Adreno (TM) 750",
                "gl_vendor": "Qualcomm",
                "gl_version": "OpenGL ES 3.2 V@0755.0",
                "egl_vendor": "Android",
                "vulkan_supported": True,
                "vulkan_api_version": "1.3.268",
                "audio_frames_per_buffer": 192,
                "audio_sample_rate_hz": 48000,
                "is_hardware_accelerated": True,
            }

        gpu_info = cls.GENUINE_MOBILE_GPUS.get(brand_key, cls.GENUINE_MOBILE_GPUS["xiaomi"])
        return {
            "gl_renderer": gpu_info["renderer"],
            "gl_vendor": gpu_info["vendor"],
            "gl_version": gpu_info["version"],
            "egl_vendor": "Android",
            "vulkan_supported": True,
            "vulkan_api_version": "1.1.128",
            "audio_frames_per_buffer": 192,
            "audio_sample_rate_hz": 48000,
            "is_hardware_accelerated": True,
        }

    @classmethod
    def audit_gpu_and_audio(
        cls,
        renderer: str,
        vendor: str,
        audio_frames_per_buffer: int = 192,
        declared_brand: str = "xiaomi"
    ) -> Dict[str, Any]:
        """Thẩm định tính hợp lệ của GPU và hệ thống âm thanh."""
        renderer_lower = renderer.lower()
        vendor_lower = vendor.lower()

        violations = []
        risk_score = 0.0

        # 1. Quét dấu hiệu GPU ảo của máy tính / PC
        for bad_rend in cls.SUSPICIOUS_GPU_RENDERERS:
            if bad_rend in renderer_lower:
                violations.append(f"EMULATOR_GPU_RENDERER_{bad_rend.upper()}")
                risk_score += 0.70
                break

        # 2. Kiểm tra vendor bất thường
        if "google inc." in vendor_lower or "vmware" in vendor_lower:
            violations.append("SOFTWARE_GPU_VENDOR")
            risk_score += 0.40

        # 3. Kiểm tra Audio frames per buffer
        # Chip âm thanh Android di động thường có buffer 128, 192, 240, 480 frames
        # Máy ảo/PC Windows thường báo 1024 hoặc 2048
        if audio_frames_per_buffer not in (128, 192, 240, 480):
            violations.append(f"NON_MOBILE_AUDIO_BUFFER_{audio_frames_per_buffer}")
            risk_score += 0.30

        total_risk = min(1.0, round(risk_score, 2))
        is_genuine = total_risk < 0.25

        return {
            "is_genuine_gpu": is_genuine,
            "risk_score": total_risk,
            "violations": violations,
            "renderer": renderer,
            "vendor": vendor,
            "audio_frames_per_buffer": audio_frames_per_buffer,
            "verdict": "PHYSICAL_MOBILE_GPU" if is_genuine else "VIRTUAL_OR_DESKTOP_GPU_DETECTED"
        }
