from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import time
import logging
import config

# Luu tru so request trong bo nho de phan hoi sieu toc
_ip_requests = {}
_ip_banned_until = {}

# Cac duong dan bot scan doc hai can chan ngay lap tuc
SUSPICIOUS_PATHS = [
    "/.env", "/wp-admin", "/phpmyadmin", "/.git", "/xmlrpc.php", 
    "/actuator", "/console", "/cgi-bin", "/shell"
]

STATIC_EXTENSIONS = (
    ".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", 
    ".svg", ".woff", ".woff2", ".ttf", ".eot", ".map", ".webp"
)


class AntiDDoSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests_per_minute: int = 300, max_body_size_mb: int = 15):
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute
        self.max_body_size = max_body_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next):
        # 1. Lay dia chi IP thuc te (Render / Cloudflare / Proxy)
        client_ip = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        now = time.time()
        path_lower = request.url.path.lower()

        # 2. MIEN TRU TUYET DOI CHO ADMIN VA HE THONG
        # Admin quan tri, static files, va webhook KHONG BAO GIO bi rate-limit hay ban IP
        x_api_key = request.headers.get("x-api-key")
        valid_keys = [getattr(config, "SQLADMIN_RAW_PASSWORD", None), getattr(config, "JWT_SECRET_KEY", None)]
        is_admin_api = bool(x_api_key and x_api_key in valid_keys)
        is_admin_area = path_lower.startswith("/admin")
        is_static_file = path_lower.startswith(("/admin/statics", "/static")) or path_lower.endswith(STATIC_EXTENSIONS)

        webhook_path = (getattr(config, "WEBHOOK_PATH", None) or "/webhook").lower()
        is_webhook_or_health = (
            path_lower in ["/", "/health", "/cryptoprocessing/event"]
            or path_lower == webhook_path
            or path_lower.startswith("/cryptoprocessing")
        )

        # Neu la Admin hoac tai nguyen hop le -> Bo qua toan bo rate-limit va xoa ban cu (neu co)
        if is_admin_api or is_admin_area or is_static_file or is_webhook_or_health:
            if client_ip in _ip_banned_until:
                del _ip_banned_until[client_ip]
            return await self._execute_and_secure(request, call_next)

        # 3. Kiem tra xem IP la co dang bi tam khoa khong (chi ap dung cho external bots)
        if client_ip in _ip_banned_until:
            if now < _ip_banned_until[client_ip]:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too Many Requests! He thong dang bao ve tai nguyen, vui long thu lai sau 1 phut."}
                )
            else:
                del _ip_banned_until[client_ip]

        # 4. Chan bot quet lo hong web pho bien
        if any(sp in path_lower for sp in SUSPICIOUS_PATHS):
            _ip_banned_until[client_ip] = now + 300 # Khoa 5 phut
            logging.warning(f"AntiDDoS: Chan IP nghi ngo tan cong {client_ip} truy cap {request.url.path}")
            return JSONResponse(status_code=403, content={"detail": "Truy cap bi tu choi do vi pham bao mat!"})

        # 5. Kiem tra kich thuoc Payload (chong tran RAM)
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                cl_int = int(content_length)
                if cl_int > self.max_body_size:
                    return JSONResponse(status_code=413, content={"detail": "Payload qua lon! Toi da 15MB."})
            except (ValueError, TypeError):
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})

        # Don dep RAM dinh ky cho _ip_requests tranh memory leak
        if len(_ip_requests) > 2000:
            stale_ips = [ip for ip, hist in _ip_requests.items() if not hist or now - hist[-1] > 60]
            for ip in stale_ips:
                _ip_requests.pop(ip, None)

        # 6. Rate Limiting cho luu luong cong cong ben ngoai (300 req/phut)
        requests_history = _ip_requests.get(client_ip, [])
        requests_history = [t for t in requests_history if now - t < 60]

        if len(requests_history) >= self.max_requests_per_minute:
            _ip_banned_until[client_ip] = now + 60
            _ip_requests[client_ip] = []
            logging.warning(f"AntiDDoS: Rate limit vuot nguong cho IP {client_ip} ({len(requests_history)} req/m)")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests! Vui long thu lai sau 1 phut."}
            )

        requests_history.append(now)
        _ip_requests[client_ip] = requests_history

        return await self._execute_and_secure(request, call_next)

    async def _execute_and_secure(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Server"] = "Bubba-Gump-Secure"
        return response
