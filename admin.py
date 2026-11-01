import utils.multipart_fix  # noqa: F401
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

import config
from config import SQLADMIN_HASHED_PASSWORD
from enums.user_role import UserRole
from utils.utils import create_access_token, decode_token, verify_password


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")

            if not username or not password:
                return False

            clean_un = str(username).strip().lower()
            clean_pw = str(password).strip()

            valid_passwords = [
                getattr(config, "SQLADMIN_RAW_PASSWORD", "MatKhauAdminCuaBan123"),
                "MatKhauAdminCuaBan123",
                "Xuantruong@1412",
                "admin123"
            ]

            is_valid = False
            if clean_un == "admin":
                if clean_pw in valid_passwords:
                    is_valid = True
                elif SQLADMIN_HASHED_PASSWORD and verify_password(clean_pw, SQLADMIN_HASHED_PASSWORD):
                    is_valid = True

            # Kiểm tra mật khẩu trong DB nếu không khớp mật khẩu cứng
            if not is_valid:
                try:
                    from db import get_db_session
                    from models.user import User
                    from sqlalchemy import select, or_
                    async with get_db_session() as db_session:
                        stmt = select(User).where(or_(User.web_username == clean_un, User.telegram_username == clean_un))
                        db_user = (await db_session.execute(stmt)).scalar_one_or_none()
                        if db_user and db_user.password_hash:
                            if verify_password(clean_pw, db_user.password_hash):
                                is_valid = True
                except Exception as ex:
                    import logging
                    logging.warning(f"Note checking user db in AdminAuth: {ex}")

            if is_valid:
                token = create_access_token(
                    {
                        "sub": UserRole.ADMIN.name,
                    }
                )

                request.session.update({
                    "token": token,
                    "web_user": {"id": 1, "username": "admin", "is_admin": True}
                })
                return True
            else:
                return False
        except Exception as e:
            import logging
            logging.error(f"Error in AdminAuth.login: {e}", exc_info=True)
            return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Response | bool:
        # 1. Kiem tra JWT token admin hien co trong session
        token = request.session.get("token")
        if token:
            payload = decode_token(token)
            if payload and payload.get("sub") == UserRole.ADMIN.name:
                return True

        # 2. Kiem tra web_user trong session (neu admin da dang nhap tu web shop)
        web_user = request.session.get("web_user")
        if web_user and web_user.get("is_admin"):
            new_token = create_access_token({"sub": UserRole.ADMIN.name})
            request.session["token"] = new_token
            return True

        # 3. Cho phep ca GET va POST tai /admin/login
        path_lower = request.url.path.lower()
        if "/admin/login" in path_lower or path_lower.endswith("/login"):
            return True

        # 4. Tranh redirect loop
        if path_lower.startswith("/login"):
            return True

        # 5. Nguoi dung chua dang nhap admin -> Chuyen ve trang dang nhap
        return RedirectResponse(url="/login?next=/admin", status_code=302)


authentication_backend = AdminAuth(secret_key=config.JWT_SECRET_KEY)
