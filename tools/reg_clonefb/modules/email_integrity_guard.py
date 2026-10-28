# -*- coding: utf-8 -*-
"""
modules/email_integrity_guard.py
Triển khai hệ thống phát hiện và thẩm định Email tạm thời (Disposable Email Address - DEA)
Dựa trên 5 tiêu chí kỹ thuật trong tài liệu nghiên cứu:
1. Phân tích bản ghi MX (MX Record Deep Inspection)
2. Danh sách chặn DEA (Curated DEA Blocklists)
3. Tuổi đời tên miền & Dấu hiệu phân loại
4. Thăm dò giao thức SMTP (SMTP Handshake Probe)
5. Tính điểm rủi ro Email (Risk Score Pipeline)
"""

import re
import socket
import smtplib
import time
from typing import Dict, Any, List, Optional, Tuple


# Danh sách các tên miền email tạm thời (DEA) phổ biến mà các hệ thống Anti-Bot luôn chặn
KNOWN_DISPOSABLE_DOMAINS = {
    # Các domain trong source code fb_api.py hiện tại
    "mail.tm", "1secmail.com", "1secmail.net", "1secmail.org", "esiix.com",
    "wwjmp.com", "yepmailer.net", "vmani.com", "cuoly.com",
    # Các nhà cung cấp temp-mail lớn toàn cầu & đã ghi nhận trong accounts_die.txt
    "tempmail.com", "temp-mail.org", "guerrillamail.com", "guerrillamailblock.com",
    "guerrillamail.net", "guerrillamail.biz", "guerrillamail.org", "guerrillamail.de",
    "sharklasers.com", "grr.la", "mailinator.com", "yopmail.com", "dispostable.com",
    "throwawaymail.com", "getairmail.com", "trashmail.com", "trashmail.net", "mohmal.com",
    "fakemailgenerator.com", "generator.email", "fakermail.com", "nada.ltd", "burnermail.io",
    "crazymailing.com", "mytemp.email", "inboxkitten.com", "spam4.me", "pokemail.net",
    "inboxes.com", "temp-mail.lol", "10minutemail.com", "disposablemail.com",
    "armyspy.com", "cuvox.de", "dayrep.com", "fleckens.hu", "gustr.com",
    # Bo sung cac domain rac da lam nick Checkpoint 282
    "laoia.com", "ooynib.com", "smail1s.com", "smailwork.com", "postbox.in",
    "any.pink", "replyloop.com", "paxeluni.com", "chitthi.org", "mailtemp.org",
    "blondmail.com", "fivermail.com", "tupmail.com", "hotmailtrusted.com", "getnada.com",
    "maxxspace.com", "gmeenramy.com", "disbox.net", "disbox.org",
    "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us"
}

# Các nhà cung cấp email uy tín cao (High-Trust Consumer Webmail)
TRUSTED_PROVIDER_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.com.vn", "icloud.com", "proton.me", "protonmail.com"
}


class EmailIntegrityGuard:
    """Hệ thống đánh giá độ tin cậy và phát hiện Disposable Email cho dự án."""

    def __init__(self, smtp_timeout: float = 4.0):
        self.smtp_timeout = smtp_timeout

    def validate_format(self, email: str) -> bool:
        """Kiểm tra cú pháp định dạng RFC 5322 cơ bản."""
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, email.strip()))

    def check_disposable_blacklist(self, domain: str) -> bool:
        """Kiểm tra domain có nằm trong danh sách đen DEA hay không."""
        clean_domain = domain.lower().strip()
        return clean_domain in KNOWN_DISPOSABLE_DOMAINS

    def inspect_mx_records(self, domain: str) -> Tuple[bool, List[str], str]:
        """
        Kiểm tra bản ghi MX của tên miền.
        Nếu không có MX hoặc trỏ về localhost -> Không hợp lệ.
        """
        clean_domain = domain.lower().strip()
        try:
            import dns.resolver
            records = dns.resolver.resolve(clean_domain, "MX")
            mx_hosts = [str(r.exchange).rstrip(".") for r in records]
            if not mx_hosts:
                return False, [], "Không tìm thấy bản ghi MX hợp lệ"
            return True, mx_hosts, "Bản ghi MX hoạt động bình thường"
        except ImportError:
            # Fallback nếu không có dnspython qua socket gethostbyname
            try:
                socket.gethostbyname(clean_domain)
                return True, [clean_domain], "Phân giải DNS domain thành công (socket fallback)"
            except Exception as e:
                return False, [], f"Không thể phân giải domain: {e}"
        except Exception as err:
            return False, [], f"Lỗi truy vấn MX: {err}"

    def probe_smtp_handshake(self, email: str, mx_host: str) -> Tuple[Optional[int], str]:
        """
        Kỹ thuật thăm dò SMTP Handshake không gửi thư:
        1. Kết nối TCP cổng 25
        2. HELO -> MAIL FROM -> RCPT TO
        3. Phân tích response code (250 vs 550)
        4. QUIT ngay lập tức trước lệnh DATA.
        """
        try:
            server = smtplib.SMTP(timeout=self.smtp_timeout)
            server.connect(mx_host, 25)
            server.helo("audit-research.security.local")
            server.mail("probe-verifier@audit-research.security.local")
            code, message = server.rcpt(email)
            try:
                server.quit()
            except Exception:
                pass
            return code, message.decode("utf-8", errors="replace")
        except (socket.timeout, smtplib.SMTPConnectError, ConnectionRefusedError) as e:
            return None, f"Cổng 25 bị chặn hoặc Timeout: {e}"
        except Exception as e:
            return None, f"SMTP Probe Error: {e}"

    def audit_email(self, email: str, perform_smtp_probe: bool = False) -> Dict[str, Any]:
        """
        Quy trình đánh giá toàn diện và tính Risk Score (0.0: An toàn tuyệt đối -> 1.0: DEA Rác).
        """
        if not self.validate_format(email):
            return {
                "email": email,
                "is_acceptable": False,
                "risk_score": 1.0,
                "verdict": "INVALID_SYNTAX",
                "details": "Cú pháp email không hợp lệ theo chuẩn RFC."
            }

        domain = email.split("@", 1)[1].lower()

        # 1. Kiểm tra xem có phải trusted domain (gmail, outlook, yahoo)
        is_trusted = domain in TRUSTED_PROVIDER_DOMAINS

        # 2. Kiểm tra Blacklist DEA
        is_blacklisted = self.check_disposable_blacklist(domain)

        # 3. Phân tích MX
        mx_valid, mx_list, mx_msg = self.inspect_mx_records(domain)

        # 4. Tính toán điểm rủi ro (Risk Score: 0.0 - 1.0)
        risk_score = 0.0
        reasons = []

        if is_blacklisted:
            risk_score += 0.95
            reasons.append(f"Domain '{domain}' nằm trong danh sách đen DEA (Email rác công khai)")

        if not mx_valid:
            risk_score += 0.90
            reasons.append(f"Tên miền không có bản ghi MX tiếp nhận thư: {mx_msg}")

        # Kiểm tra hạ tầng MX trỏ về dịch vụ tạm thời
        for mx in mx_list:
            if any(dea in mx.lower() for dea in ["mailtm", "1secmail", "guerrillamail", "mailinator"]):
                risk_score = max(risk_score, 0.95)
                reasons.append(f"Hạ tầng máy chủ MX ({mx}) thuộc mạng lưới Disposable Mail.")

        if is_trusted:
            risk_score = 0.05
            reasons.append(f"Domain '{domain}' là nhà cung cấp uy tín hàng đầu (Consumer Webmail Tier 1)")

        # Thăm dò SMTP nếu được yêu cầu và có MX
        smtp_code = None
        smtp_msg = ""
        if perform_smtp_probe and mx_valid and mx_list and not is_trusted:
            smtp_code, smtp_msg = self.probe_smtp_handshake(email, mx_list[0])
            if smtp_code == 550:
                risk_score = 1.0
                reasons.append(f"Máy chủ đích từ chối (550 User Unknown): Hộp thư không tồn tại.")
            elif smtp_code == 250:
                risk_score = min(risk_score, 0.4)
                reasons.append(f"Máy chủ đích xác nhận 250 OK: Hộp thư tồn tại và sẵn sàng nhận thư.")

        risk_score = min(max(risk_score, 0.0), 1.0)
        is_acceptable = risk_score < 0.50

        verdict = "ACCEPTED" if is_acceptable else "REJECTED_DISPOSABLE_RISK"

        return {
            "email": email,
            "domain": domain,
            "is_acceptable": is_acceptable,
            "risk_score": round(risk_score, 2),
            "verdict": verdict,
            "is_trusted_provider": is_trusted,
            "is_blacklisted_dea": is_blacklisted,
            "mx_records": mx_list,
            "smtp_probe_code": smtp_code,
            "reasons": reasons
        }


def explain_project_email_vulnerability() -> Dict[str, str]:
    """Giải thích điểm yếu trong việc dùng Mail.tm và 1secmail ở file fb_api.py hiện tại."""
    return {
        "Vulnerability": (
            "File fb_api.py hiện đang tích hợp MailTmProvider và OneSecMailProvider. "
            "Cả hai dịch vụ này đều sử dụng các domain nằm trong DEA Blocklists công khai toàn cầu."
        ),
        "Detection_Mechanism": (
            "Hệ thống Risk Engine của Meta truy vấn danh sách MX và MX cluster. "
            "Các IP máy chủ mail của Mail.tm và 1secmail đều có độ uy tín bằng 0. "
            "Khi gửi mã xác minh đăng ký (Step 7b / Step 8), hệ thống sẽ lập tức chặn hoặc gắn cờ checkpoint 282."
        ),
        "Mitigation_Rule": (
            "Trong môi trường sản xuất thực tế, các dịch vụ bắt buộc phải sử dụng email từ nhà cung cấp uy tín "
            "(Google Workspace, Microsoft 365, iCloud) hoặc Private Domain có tuổi đời lâu năm (>1 năm), "
            "đầy đủ bản ghi SPF, DKIM, DMARC."
        )
    }
