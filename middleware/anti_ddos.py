from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import time
import logging

# Luu tru so request trong bo nho de phan hoi sieu toc
_ip_requests = {}
_ip_banned_until = {}

# Cac duong dan bot scan doc hai can chan ngay lap tuc
SUSPICIOUS_PATHS = [
    "/.env", "/wp-admin", "/phpmyadmin", "/.git", "/xmlrpc.php", 
    "/actuator", "/console", "/cgi-bin", "/shell"
]

class AntiDDoSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests_per_minute: int = 120, max_body_size_mb: int = 10):
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute
        self.max_body_size = max_body_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        # 1. Lay dia chi IP thuc te (Render / Cloudflare)
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        now = time.time()

        # 2. Kiem tra xem IP co dang bi khoa tam thoi khong
        if client_ip in _ip_banned_until:
            if now < _ip_banned_until[client_ip]:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "IP cua ban da bi tam khoa do gui qua nhieu request! Vui long thu lai sau 1 phut."}
                )
            else:
                del _ip_banned_until[client_ip]

        # 3. Chan bot quet lo hong web pho bien
        path_lower = request.url.path.lower()
        if any(sp in path_lower for sp in SUSPICIOUS_PATHS):
            _ip_banned_until[client_ip] = now + 300 # Khoa 5 phut
            logging.warning(f"AntiDDoS: Chặn IP nghi ngờ tấn công {client_ip} truy cập {request.url.path}")
            return JSONResponse(status_code=403, content={"detail": "Truy cap bi tu choi do vi pham bao mat!"})

        # 4. Kiem tra kich thuoc Payload (chong tan cong lam day RAM)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return JSONResponse(status_code=413, content={"detail": "Payload qua lon! Toi da 10MB."})

        # 5. Rate Limiting (Gioi han tan suat request)
        # Neu la trang dang nhap Admin, gioi han chat hon (toi da 15 req/phut)
        is_login = "/admin/login" in path_lower
        limit = 15 if is_login else self.max_requests_per_minute

        requests_history = _ip_requests.get(client_ip, [])
        # Loc cac request trong 60 giay qua
        requests_history = [t for t in requests_history if now - t < 60]

        if len(requests_history) >= limit:
            _ip_banned_until[client_ip] = now + 60 # Khoa 60 giay
            _ip_requests[client_ip] = []
            logging.warning(f"AntiDDoS: Rate limit vuot nguong cho IP {client_ip} ({len(requests_history)} req/m)")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests! He thong dang bao ve chong spam, vui long doi 1 phut."}
            )

        requests_history.append(now)
        _ip_requests[client_ip] = requests_history

        # 6. Thuc thi Request
        response = await call_next(request)

        # 7. Gan cac Security Headers chong tan cong
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Server"] = "Bubba-Gump-Secure"

        return response
