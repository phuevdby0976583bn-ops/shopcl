# -*- coding: utf-8 -*-
"""
modules/network_risk_profiler.py
Triển khai hệ thống đánh giá rủi ro mạng (Network & IP Risk Profiler)
Dựa trên các tiêu chuẩn trong tài liệu nghiên cứu:
1. Phân loại ASN (Datacenter / Hosting vs Mobile Carrier / Residential)
2. Nhận diện TCP/IP Stack Fingerprint (MTU, MSS, TCP Window, TTL)
3. Phát hiện đặc trưng CGNAT của mạng di động (Carrier-Grade NAT)
4. Đo lường & phân tích Độ trễ (RTT) và Biến thiên độ trễ (Jitter)
5. Tính tổng điểm rủi ro mạng (Network Anomaly Risk Score: 0.0 - 1.0)
"""

import time
import socket
import random
import statistics
from typing import Dict, Any, List, Optional, Tuple


# Danh sách các dải ASN máy chủ lưu trữ (Datacenter / Cloud / Hosting) phổ biến
KNOWN_DATACENTER_ASNS = {
    "AS16509", "AS14618",  # Amazon AWS
    "AS15169", "AS396982", # Google Cloud
    "AS8075",              # Microsoft Azure
    "AS14061",             # DigitalOcean
    "AS63949",             # Linode / Akamai
    "AS20473",             # Choopa / Vultr
    "AS16276",             # OVH SAS
    "AS24940",             # Hetzner Online
    "AS51167",             # Contabo
    "AS13335"              # Cloudflare
}

# Các ASN mạng di động thật (Mobile Carriers) tại Việt Nam
VIETNAM_MOBILE_ASNS = {
    "AS7552",  # Viettel Group
    "AS45899", # VNPT / Vinaphone Mobile
    "AS45544", # MobiFone Telecommunications
    "AS24086", # Vietnamobile
}


class NetworkRiskProfiler:
    """Hệ thống phân tích rủi ro hạ tầng mạng và dấu vân tay giao thức mạng."""

    def __init__(self):
        pass

    def evaluate_tcp_fingerprint(
        self,
        claimed_os: str = "Android",
        claimed_network: str = "4G_LTE",
        measured_mss: int = 1460,
        measured_ttl: int = 128,
        measured_window_size: int = 65535
    ) -> Dict[str, Any]:
        """
        Đối chiếu dấu vân tay TCP/IP với thông số khai báo từ User-Agent / Headers:
        - Android chạy nhân Linux (Kernel mặc định initial TTL = 64). Nếu TTL = 128 -> Windows PC!
        - Mạng di động (4G/5G) có GTP Tunnel overhead nên MSS thường là 1360 - 1400 (MTU 1400 - 1440).
          Nếu MSS = 1460 chuẩn Ethernet -> Nghi vấn mạng cáp quang / Datacenter.
        """
        anomalies = []
        risk_score = 0.0

        # 1. Kiểm tra TTL đối chiếu với OS
        if "android" in claimed_os.lower():
            if measured_ttl > 64 and measured_ttl <= 128:
                anomalies.append("TTL Mismatch: Khai báo Android (Linux TTL=64) nhưng phản hồi TTL=128 (Windows Desktop stack).")
                risk_score += 0.45
            elif measured_ttl <= 64:
                # TTL gần 64 (qua router còn 50-63)
                pass

        # 2. Kiểm tra MSS / MTU đối chiếu với Mobile Cellular
        if "4g" in claimed_network.lower() or "5g" in claimed_network.lower():
            if measured_mss >= 1460:
                anomalies.append("MSS Anomaly: Khai báo 4G/LTE nhưng MSS = 1460 (Chuẩn cáp quang Ethernet Datacenter không có GTP header encapsulation).")
                risk_score += 0.30

        return {
            "claimed_os": claimed_os,
            "claimed_network": claimed_network,
            "measured_mss": measured_mss,
            "measured_ttl": measured_ttl,
            "anomalies": anomalies,
            "risk_score": min(risk_score, 1.0)
        }

    def analyze_latency_and_jitter(self, rtt_samples: List[float]) -> Dict[str, Any]:
        """
        Phân tích độ trễ (RTT) và biến thiên độ trễ (Jitter):
        - Datacenter Fiber: Jitter cực thấp (<1.0ms), RTT phẳng.
        - Mobile 4G/5G Radio Link: Jitter tự nhiên cao (10ms - 40ms) do fading vô tuyến và chuyển trạm phát sóng (handover).
        """
        if not rtt_samples or len(rtt_samples) < 3:
            return {"error": "Cần tối thiểu 3 mẫu RTT để tính toán Jitter"}

        mean_rtt = statistics.mean(rtt_samples)
        # Tính jitter theo chuẩn RFC 3550: trung bình độ lệch giữa các mẫu liên tiếp
        diffs = [abs(rtt_samples[i] - rtt_samples[i - 1]) for i in range(1, len(rtt_samples))]
        jitter = statistics.mean(diffs)
        std_dev = statistics.stdev(rtt_samples)

        is_datacenter_profile = (jitter < 1.5 and std_dev < 1.0)
        is_mobile_profile = (jitter >= 8.0 or std_dev >= 7.0)

        risk_score = 0.0
        reasons = []

        if is_datacenter_profile:
            risk_score += 0.40
            reasons.append(f"Jitter bất thường thấp ({jitter:.2f}ms): Đặc trưng đường truyền cáp quang máy chủ (Datacenter Fiber), không tương thích với 4G vô tuyến.")
        elif is_mobile_profile:
            reasons.append(f"Jitter tự nhiên ({jitter:.2f}ms): Tương thích với môi trường vô tuyến di động (Cellular RF noise).")

        return {
            "mean_rtt_ms": round(mean_rtt, 2),
            "jitter_ms": round(jitter, 2),
            "std_dev_ms": round(std_dev, 2),
            "is_datacenter_profile": is_datacenter_profile,
            "is_mobile_profile": is_mobile_profile,
            "risk_score": round(risk_score, 2),
            "reasons": reasons
        }

    def assess_ip_reputation(
        self,
        ip: str,
        asn: str = "AS16509",
        usage_type: str = "Datacenter/Hosting"
    ) -> Dict[str, Any]:
        """
        Đánh giá điểm rủi ro ASN và loại hình kết nối:
        - Datacenter / Hosting: Risk cao (0.85 - 1.0)
        - Residential ISP: Risk thấp (0.10)
        - Mobile Carrier (CGNAT): Risk rất thấp / Tin cậy (0.05)
        """
        asn_clean = asn.upper().strip()
        risk_score = 0.0
        reasons = []

        if asn_clean in KNOWN_DATACENTER_ASNS or "datacenter" in usage_type.lower() or "hosting" in usage_type.lower():
            risk_score = 0.90
            reasons.append(f"ASN {asn_clean} thuộc nhà cung cấp Cloud / Datacenter (Hosting/Proxy IP).")
        elif asn_clean in VIETNAM_MOBILE_ASNS or "mobile" in usage_type.lower() or "cellular" in usage_type.lower():
            risk_score = 0.05
            reasons.append(f"ASN {asn_clean} là hạ tầng di động chính hãng (Carrier CGNAT).")
        else:
            risk_score = 0.30
            reasons.append(f"ASN {asn_clean} là mạng dân dụng hoặc nhà mạng khác (Residential / Mixed).")

        return {
            "ip": ip,
            "asn": asn_clean,
            "usage_type": usage_type,
            "risk_score": round(risk_score, 2),
            "is_datacenter": (risk_score >= 0.70),
            "reasons": reasons
        }

    def full_network_audit(
        self,
        ip: str,
        asn: str,
        usage_type: str,
        rtt_samples: List[float],
        tcp_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Tổng hợp toàn diện điểm rủi ro hạ tầng mạng (Total Network Risk Score)."""
        asn_res = self.assess_ip_reputation(ip, asn, usage_type)
        rtt_res = self.analyze_latency_and_jitter(rtt_samples)
        tcp_res = self.evaluate_tcp_fingerprint(**tcp_params)

        # Trọng số: ASN (50%), TCP Stack Fingerprint (30%), Latency/Jitter (20%)
        total_score = (
            asn_res["risk_score"] * 0.50 +
            tcp_res["risk_score"] * 0.30 +
            rtt_res["risk_score"] * 0.20
        )
        total_score = min(max(total_score, 0.0), 1.0)

        all_reasons = asn_res["reasons"] + tcp_res["anomalies"] + rtt_res["reasons"]
        verdict = "HIGH_RISK_DATACENTER_OR_PROXY" if total_score >= 0.50 else "ACCEPTABLE_MOBILE_CLIENT"

        return {
            "ip": ip,
            "total_risk_score": round(total_score, 2),
            "verdict": verdict,
            "asn_assessment": asn_res,
            "tcp_fingerprint": tcp_res,
            "latency_jitter": rtt_res,
            "all_flags": all_reasons
        }
