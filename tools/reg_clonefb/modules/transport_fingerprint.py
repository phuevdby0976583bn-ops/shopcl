# -*- coding: utf-8 -*-
"""
modules/transport_fingerprint.py
Nghiên cứu & thẩm định dấu vân tay tầng mạng (Transport Layer Fingerprinting):
1. TLS Fingerprint (JA3 / JA4): So khớp BoringSSL / Liger (Android Katana) vs Python/urllib3/cURL.
2. HTTP/2 Frame Fingerprint (Akamai H2): SETTINGS, WINDOW_UPDATE, PRIORITY và thứ tự pseudo-headers.
3. Đánh giá độ lệch bất thường (Transport Anomaly Risk Score: 0.0 -> 1.0).
"""

import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple


class TlsFingerprintEngine:
    """Mô phỏng và đối chiếu dấu vân tay TLS Client Hello (JA3 & JA4)."""

    # Danh sách chuẩn Cipher Suites của Android FB4A Katana (nhân BoringSSL / Liger)
    # Loại trừ mã GREASE (0x?a?a) theo RFC chuẩn hóa JA3
    KATANA_BORINGSSL_CIPHERS = [
        0x1301,  # TLS_AES_128_GCM_SHA256 (TLS 1.3)
        0x1302,  # TLS_AES_256_GCM_SHA384 (TLS 1.3)
        0x1303,  # TLS_CHACHA20_POLY1305_SHA256 (TLS 1.3)
        0xC02B,  # TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
        0xC02F,  # TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        0xC02C,  # TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
        0xC030,  # TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        0xCCA9,  # TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256
        0xCCA8,  # TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256
    ]

    # Danh sách Extension chuẩn của BoringSSL Katana
    KATANA_EXTENSIONS = [
        0,      # server_name (SNI)
        23,     # extended_master_secret
        65281,  # renegotiation_info
        10,     # supported_groups (Elliptic Curves)
        11,     # ec_point_formats
        35,     # session_ticket
        16,     # application_layer_protocol_negotiation (ALPN)
        5,      # status_request (OCSP stapling)
        13,     # signature_algorithms
        43,     # supported_versions (TLS 1.3, TLS 1.2)
        51,     # key_share
        45      # psk_key_exchange_modes
    ]

    # Các đường cong Elliptic (Supported Groups)
    KATANA_CURVES = [29, 23, 24]  # X25519 (29), secp256r1 (23), secp384r1 (24)
    KATANA_POINT_FORMATS = [0]     # uncompressed (0)

    # Thư viện Python requests / urllib3 / OpenSSL mặc định thường gửi bộ cipher/extensions rất khác
    PYTHON_URLLIB3_CIPHERS = [
        0xC02B, 0xC02F, 0xC00A, 0xC009, 0xC013, 0xC014, 0xC02C, 0xC030,
        0x009C, 0x009D, 0x002F, 0x0035, 0x000A
    ]
    PYTHON_URLLIB3_EXTENSIONS = [0, 23, 65281, 10, 11, 35, 13]

    @classmethod
    def calculate_ja3(
        cls,
        tls_version: int = 771,  # 0x0303 = TLS 1.2 trong ClientHello Record
        ciphers: Optional[List[int]] = None,
        extensions: Optional[List[int]] = None,
        curves: Optional[List[int]] = None,
        point_formats: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Tính chuỗi JA3 thô và mã băm MD5 theo chuẩn Salesforce JA3:
        Format: SSLVersion,CipherSuites,Extensions,SupportedGroups,ECPointFormats
        """
        ciphers = ciphers or cls.KATANA_BORINGSSL_CIPHERS
        extensions = extensions or cls.KATANA_EXTENSIONS
        curves = curves or cls.KATANA_CURVES
        point_formats = point_formats or cls.KATANA_POINT_FORMATS

        ciphers_str = "-".join(str(c) for c in ciphers)
        ext_str = "-".join(str(e) for e in extensions)
        curves_str = "-".join(str(c) for c in curves)
        formats_str = "-".join(str(f) for f in point_formats)

        raw_ja3 = f"{tls_version},{ciphers_str},{ext_str},{curves_str},{formats_str}"
        ja3_hash = hashlib.md5(raw_ja3.encode("utf-8")).hexdigest()

        return {
            "tls_version": tls_version,
            "raw_ja3": raw_ja3,
            "ja3_hash": ja3_hash,
            "cipher_count": len(ciphers),
            "extension_count": len(extensions),
        }

    @classmethod
    def calculate_ja4(
        cls,
        protocol: str = "t",           # t = TCP, q = QUIC
        tls_version: str = "13",       # 13 = TLS 1.3, 12 = TLS 1.2
        has_sni: bool = True,          # d = Domain (SNI), i = IP address
        ciphers: Optional[List[int]] = None,
        extensions: Optional[List[int]] = None,
        alpn: str = "h2",              # h2, h1, 00
    ) -> Dict[str, str]:
        """
        Tính chuẩn JA4 Fingerprint thế hệ mới của FoxIO:
        Format: {a}_{b}_{c}
        a: {protocol}{version}{sni}{cipher_count:02d}{ext_count:02d}{alpn_first_last}
        b: truncated SHA256 (12 chars) của sorted ciphers hex
        c: truncated SHA256 (12 chars) của sorted extensions hex
        """
        ciphers = ciphers or cls.KATANA_BORINGSSL_CIPHERS
        extensions = extensions or cls.KATANA_EXTENSIONS

        sni_flag = "d" if has_sni else "i"
        cipher_count = min(99, len(ciphers))
        ext_count = min(99, len(extensions))
        alpn_tag = alpn[:2] if alpn else "00"

        part_a = f"{protocol}{tls_version}{sni_flag}{cipher_count:02d}{ext_count:02d}{alpn_tag}"

        # Sắp xếp và hash cipher hex
        ciphers_hex = "_".join(f"{c:04x}" for c in sorted(ciphers))
        part_b = hashlib.sha256(ciphers_hex.encode("utf-8")).hexdigest()[:12]

        # Sắp xếp và hash extensions hex (loại trừ SNI 0x0000 và ALPN 0x0010 theo JA4 spec)
        filtered_exts = [e for e in extensions if e not in (0, 16)]
        exts_hex = "_".join(f"{e:04x}" for e in sorted(filtered_exts))
        part_c = hashlib.sha256(exts_hex.encode("utf-8")).hexdigest()[:12]

        ja4_fingerprint = f"{part_a}_{part_b}_{part_c}"
        return {
            "ja4": ja4_fingerprint,
            "part_a": part_a,
            "part_b": part_b,
            "part_c": part_c,
        }

    @classmethod
    def audit_tls_client(cls, raw_ja3: str) -> Dict[str, Any]:
        """Phát hiện bot / crawler dựa trên đối chiếu JA3 thô với BoringSSL Katana chuẩn."""
        katana_ref = cls.calculate_ja3()
        if raw_ja3 == katana_ref["raw_ja3"]:
            return {
                "is_genuine_katana": True,
                "client_stack": "Android BoringSSL / Liger",
                "risk_score": 0.0,
                "notes": "Matches official FB4A BoringSSL ClientHello signature."
            }

        # Kiểm tra xem có phải Python requests hoặc urllib3 không
        python_ref = cls.calculate_ja3(
            ciphers=cls.PYTHON_URLLIB3_CIPHERS,
            extensions=cls.PYTHON_URLLIB3_EXTENSIONS
        )
        if raw_ja3 == python_ref["raw_ja3"]:
            return {
                "is_genuine_katana": False,
                "client_stack": "Python requests / urllib3 (Detected Bot)",
                "risk_score": 0.95,
                "notes": "Signature matches standard OpenSSL/urllib3 stack, high bot risk."
            }

        return {
            "is_genuine_katana": False,
            "client_stack": "Unknown / Generic TLS Client",
            "risk_score": 0.65,
            "notes": "Non-Katana TLS parameters, possible emulator or custom proxy."
        }


class Http2FingerprintEngine:
    """Mô phỏng & phân tích Frame Fingerprint HTTP/2 (Akamai H2 Fingerprinting)."""

    # Thứ tự & giá trị SETTINGS chuẩn của Android FB4A Katana Liger
    KATANA_H2_SETTINGS = {
        1: 65536,    # HEADER_TABLE_SIZE
        2: 0,        # ENABLE_PUSH (Meta app luôn tắt server push)
        3: 100,      # MAX_CONCURRENT_STREAMS
        4: 6291456,  # INITIAL_WINDOW_SIZE (6MB window)
        5: 16384,    # MAX_FRAME_SIZE
        6: 262144,   # MAX_HEADER_LIST_SIZE
    }

    # Frame WINDOW_UPDATE stream 0: Meta Liger cấp thêm buffer window ban đầu
    KATANA_WINDOW_UPDATE_INCREMENT = 15663105

    # Thứ tự cố định của Pseudo-Headers trong request Katana / OkHttp
    # m = :method, p = :path, a = :authority, s = :scheme
    KATANA_PSEUDO_HEADER_ORDER = ["m", "p", "a", "s"]

    @classmethod
    def calculate_h2_fingerprint(
        cls,
        settings: Optional[Dict[int, int]] = None,
        window_update: Optional[int] = None,
        pseudo_order: Optional[List[str]] = None,
        priority_frame: int = 0
    ) -> Dict[str, Any]:
        """
        Tính Akamai H2 Fingerprint:
        Format: S[settings_str]|WU[window_update]|P[priority]|PH[pseudo_order]
        Ví dụ: 1:65536;2:0;4:6291456;6:262144|15663105|0|m,p,a,s
        """
        settings = settings or cls.KATANA_H2_SETTINGS
        window_update = window_update or cls.KATANA_WINDOW_UPDATE_INCREMENT
        pseudo_order = pseudo_order or cls.KATANA_PSEUDO_HEADER_ORDER

        settings_str = ";".join(f"{k}:{v}" for k, v in sorted(settings.items()))
        pseudo_str = ",".join(pseudo_order)

        raw_h2 = f"{settings_str}|{window_update}|{priority_frame}|{pseudo_str}"
        h2_hash = hashlib.md5(raw_h2.encode("utf-8")).hexdigest()

        return {
            "raw_h2": raw_h2,
            "h2_hash": h2_hash,
            "settings": settings,
            "window_update": window_update,
            "pseudo_order": pseudo_order,
        }

    @classmethod
    def audit_h2_stream(
        cls,
        observed_settings: Dict[int, int],
        observed_window_update: int,
        observed_pseudo_order: List[str]
    ) -> Dict[str, Any]:
        """Thẩm định tính hợp lệ của luồng HTTP/2 từ phía client."""
        violations = []
        risk_score = 0.0

        # 1. Kiểm tra pseudo-headers order
        if observed_pseudo_order != cls.KATANA_PSEUDO_HEADER_ORDER:
            violations.append("NON_STANDARD_PSEUDO_HEADER_ORDER")
            risk_score += 0.40

        # 2. Kiểm tra SETTINGS_ENABLE_PUSH
        if observed_settings.get(2) == 1:
            violations.append("UNEXPECTED_ENABLE_PUSH_ENABLED")
            risk_score += 0.25

        # 3. Kiểm tra INITIAL_WINDOW_SIZE
        init_win = observed_settings.get(4, 65535)
        if init_win < 65535:
            violations.append("SUSPICIOUS_LOW_INITIAL_WINDOW")
            risk_score += 0.20

        # 4. Kiểm tra stream 0 window update
        if observed_window_update <= 0:
            violations.append("MISSING_OR_ZERO_WINDOW_UPDATE")
            risk_score += 0.25

        is_passed = len(violations) == 0
        return {
            "is_genuine_katana_h2": is_passed,
            "violations": violations,
            "risk_score": min(1.0, round(risk_score, 2)),
            "verdict": "GENUINE_LIGER_H2" if is_passed else "ANOMALOUS_H2_CLIENT"
        }


class TransportFingerprintEngine:
    """Bộ giải pháp kết hợp toàn diện Dấu vân tay Tầng mạng (TLS + HTTP/2)."""

    @classmethod
    def get_katana_liger_transport_profile(cls) -> Dict[str, Any]:
        """Tạo trọn bộ thông số dấu vân tay giao vận chuẩn Katana Liger cho thiết bị di động."""
        tls_data = TlsFingerprintEngine.calculate_ja3()
        ja4_data = TlsFingerprintEngine.calculate_ja4()
        h2_data = Http2FingerprintEngine.calculate_h2_fingerprint()

        return {
            "stack_name": "Facebook Katana Liger / BoringSSL",
            "tls": {
                "ja3": tls_data["ja3_hash"],
                "raw_ja3": tls_data["raw_ja3"],
                "ja4": ja4_data["ja4"],
                "alpn": "h2,http/1.1",
            },
            "http2": {
                "h2_hash": h2_data["h2_hash"],
                "raw_h2": h2_data["raw_h2"],
                "pseudo_headers": h2_data["pseudo_order"],
            },
            "client_headers": {
                "X-FB-HTTP-Engine": "Liger",
                "X-FB-Client-IP": "True",
                "X-FB-Server-Cluster": "True",
            }
        }

    @classmethod
    def evaluate_transport_risk(
        cls,
        raw_ja3: str,
        h2_settings: Dict[int, int],
        h2_window_update: int,
        pseudo_order: List[str]
    ) -> Dict[str, Any]:
        """Tính điểm rủi ro tổng thể tầng mạng (Transport Anomaly Score: 0.0 -> 1.0)."""
        tls_audit = TlsFingerprintEngine.audit_tls_client(raw_ja3)
        h2_audit = Http2FingerprintEngine.audit_h2_stream(h2_settings, h2_window_update, pseudo_order)

        # Trọng số: TLS 60%, HTTP/2 40%
        composite_risk = (tls_audit["risk_score"] * 0.6) + (h2_audit["risk_score"] * 0.4)
        composite_risk = round(composite_risk, 3)

        return {
            "composite_risk_score": composite_risk,
            "is_trusted": composite_risk < 0.35,
            "tls_verdict": tls_audit,
            "h2_verdict": h2_audit,
            "summary": "SECURE_MOBILE_TRANSPORT" if composite_risk < 0.35 else "POTENTIAL_AUTOMATED_CLIENT"
        }

class Http3QuicFingerprintEngine:
    """Mô phỏng và đối chiếu Dấu vân tay giao vận HTTP/3 & QUIC (UDP Port 443)."""

    KATANA_QUIC_TRANSPORT_PARAMS = {
        "initial_version": "0x00000001",  # QUIC v1 (RFC 9000)
        "alpn": "h3",
        "initial_max_data": 15728640,     # 15 MB
        "initial_max_stream_data_bidi_local": 524288,  # 512 KB
        "active_connection_id_limit": 4,
        "max_idle_timeout_ms": 30000,
        "disable_active_migration": False,
    }

    @classmethod
    def get_quic_profile(cls) -> Dict[str, Any]:
        return {
            "protocol": "HTTP/3 over QUIC",
            "transport_parameters": cls.KATANA_QUIC_TRANSPORT_PARAMS,
            "supports_udp_443": True,
            "engine": "Meta Liger QUIC",
        }

    @classmethod
    def audit_protocol_capability(cls, protocol_used: str, supports_quic: bool) -> Dict[str, Any]:
        """
        Nếu client khai báo app FB4A Katana mới nhất nhưng chỉ gửi request bằng HTTP/1.1 TCP:
        Đánh cờ nghi vấn script tự động hóa / thư viện cURL không có ngăn xếp QUIC.
        """
        if protocol_used in ("HTTP/3", "h3") and supports_quic:
            return {"is_valid": True, "risk_score": 0.0, "verdict": "GENUINE_QUIC_LIGER"}
        elif protocol_used in ("HTTP/2", "h2"):
            return {"is_valid": True, "risk_score": 0.05, "verdict": "ACCEPTABLE_HTTP2_LIGER"}
        else:
            return {
                "is_valid": False,
                "risk_score": 0.55,
                "verdict": "SUSPICIOUS_HTTP1_ONLY_CLIENT",
                "notes": "Native Katana app defaults to QUIC/H2; HTTP/1.1-only indicates legacy bot or proxy."
            }
