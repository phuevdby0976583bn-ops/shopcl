# -*- coding: utf-8 -*-
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from unittest.mock import AsyncMock, patch, MagicMock
from contextlib import asynccontextmanager
from types import SimpleNamespace

import config
from enums.user_role import UserRole
from web_shop import web_router, get_rate, format_vnd, format_usd


class MockDbResult:
    def __init__(self, items=None):
        self._items = items if items is not None else []

    def scalars(self):
        return self

    def __iter__(self):
        return iter(self._items)

    def all(self):
        return list(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else None


class SmartMockDbSession:
    def __init__(self, user=None, categories=None, subcategories=None):
        self.user = user
        self.categories = categories or [SimpleNamespace(id=1, name="Facebook Clone", media_id="cat1")]
        self.subcategories = subcategories or [SimpleNamespace(id=1, name="Clone Nuôi 2FA", price=0.05, description="Acc live", media_id="sub1")]

    async def execute(self, stmt, *args, **kwargs):
        s_str = str(stmt).lower()
        if "from categories" in s_str:
            return MockDbResult(self.categories)
        elif "from subcategories" in s_str:
            return MockDbResult(self.subcategories)
        elif "from users" in s_str:
            return MockDbResult([self.user] if self.user else [])
        elif "count" in s_str:
            return MockDbResult([(1, 5)])
        elif "distinct" in s_str:
            return MockDbResult([(1, 1)])
        return MockDbResult([])

    async def commit(self): pass
    async def flush(self): pass
    def add(self, item): pass


@pytest.fixture
def test_app():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=config.JWT_SECRET_KEY)
    app.include_router(web_router)
    return app


@pytest.mark.asyncio
async def test_web_home_page_and_head(test_app):
    @asynccontextmanager
    async def home_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", home_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r_home = await ac.get("/")
            assert r_home.status_code == 200
            assert "Bubba Gump" in r_home.text
            assert "globalSearchInput" in r_home.text
            assert "truongdvfb" in r_home.text

            r_head = await ac.head("/")
            assert r_head.status_code == 200


@pytest.mark.asyncio
async def test_web_faq_page(test_app):
    @asynccontextmanager
    async def faq_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", faq_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/faq")
            assert r.status_code == 200
            assert "2fa.live" in r.text
            assert "UID|Pass|2FA" in r.text
            assert "Binance Pay" in r.text


@pytest.mark.asyncio
async def test_web_policy_page(test_app):
    @asynccontextmanager
    async def pol_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", pol_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/policy")
            assert r.status_code == 200
            assert "2018" in r.text
            assert "truongdvfb" in r.text


@pytest.mark.asyncio
async def test_web_recharge_page(test_app):
    @asynccontextmanager
    async def rech_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", rech_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/recharge")
            assert r.status_code == 200
            assert "Binance Pay" in r.text
            assert "805398854" in r.text
            assert "VietQR" in r.text
            assert "BIDV" in r.text
            assert "setFieldVal" in r.text
            assert "getFieldVal" in r.text
            assert "NGUYEN XUAN TRUONG" in r.text
            

@pytest.mark.asyncio
async def test_web_unauth_redirects(test_app):
    @asynccontextmanager
    async def redirect_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", redirect_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r_orders = await ac.get("/orders")
            assert r_orders.status_code == 302
            assert "/login?next=/orders" in r_orders.headers.get("location", "")

            r_bal = await ac.get("/balance-history")
            assert r_bal.status_code == 302
            assert "/login?next=/balance-history" in r_bal.headers.get("location", "")


@pytest.mark.asyncio
async def test_web_admin_login_shows_admin_panel_button(test_app):
    admin_user = SimpleNamespace(
        id=1,
        telegram_id=805398854,
        telegram_username="admin",
        web_username="admin",
        top_up_amount=999.0,
        consume_records=0.0,
        is_banned=False
    )
    @asynccontextmanager
    async def admin_db_ctx(*args, **kwargs):
        yield SmartMockDbSession(user=admin_user)

    with patch("web_shop.get_db_session", admin_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            admin_pw = getattr(config, "SQLADMIN_RAW_PASSWORD", "MatKhauAdminCuaBan123")
            r_login = await ac.post("/login", data={"username": "admin", "password": admin_pw, "next": "/"})
            assert r_login.status_code == 302

            # Check storefront with admin session
            r_home = await ac.get("/")
            assert r_home.status_code == 200
            assert "pulse-admin-btn" in r_home.text
            assert 'href="/admin"' in r_home.text


@pytest.mark.asyncio
async def test_web_buy_unauthenticated(test_app):
    @asynccontextmanager
    async def buy_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", buy_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.post("/api/web/buy", json={"subcategory_id": 1, "quantity": 1})
            assert r.status_code == 401
            data = r.json()
            assert data.get("status") == "error"


@pytest.mark.asyncio
async def test_web_buy_authenticated_invalid_quantity(test_app):
    user = SimpleNamespace(
        id=2,
        telegram_id=12345,
        telegram_username="buyer",
        web_username="buyer",
        top_up_amount=50.0,
        consume_records=0.0,
        is_banned=False
    )
    @asynccontextmanager
    async def user_db_ctx(*args, **kwargs):
        yield SmartMockDbSession(user=user)

    with patch("web_shop.get_db_session", user_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            # Login first
            ac.cookies.set("session", "")
            with patch("web_shop.get_current_user_info", AsyncMock(return_value=(user, 50.0, False))):
                r = await ac.post("/api/web/buy", json={"subcategory_id": 1, "quantity": 0})
                assert r.status_code == 400


@pytest.mark.asyncio
async def test_web_order_detail_api_unauthorized(test_app):
    @asynccontextmanager
    async def order_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", order_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/api/web/order/1")
            assert r.status_code == 401


@pytest.mark.asyncio
async def test_web_recharge_unauthorized_apis(test_app):
    @asynccontextmanager
    async def empty_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", empty_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r1 = await ac.post("/api/web/recharge/create-binance", json={"amount_usd": 10.0})
            assert r1.status_code == 401

            r2 = await ac.post("/api/web/recharge/create-bank", json={"amount_vnd": 50000})
            assert r2.status_code == 401

            r3 = await ac.post("/api/web/recharge/create-onchain", json={"network": "BSC", "amount_usd": 20.0})
            assert r3.status_code == 401


@pytest.mark.asyncio
async def test_web_recharge_authorized_flow(test_app):
    user = SimpleNamespace(
        id=77,
        telegram_id=987654321,
        telegram_username="buyer77",
        web_username="buyer77",
        top_up_amount=100.0,
        consume_records=20.0,
        is_banned=False
    )
    @asynccontextmanager
    async def user_db_ctx(*args, **kwargs):
        yield SmartMockDbSession(user=user)

    with patch("web_shop.get_db_session", user_db_ctx):
        with patch("web_shop.session_commit", AsyncMock()):
            with patch("web_shop.get_current_user_info", AsyncMock(return_value=(user, 80.0, False))):
                async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
                    # 1. Binance Pay Invoice
                    r_bin = await ac.post("/api/web/recharge/create-binance", json={"amount_usd": 15.0})
                    assert r_bin.status_code == 200
                    d_bin = r_bin.json()
                    assert d_bin["status"] == "success"
                    assert "binance_uid" in d_bin
                    assert "NAP 987654321" in d_bin["memo"]
                    assert float(d_bin["exact_amount"]) >= 15.0

                    # 2. Bank VietQR Invoice
                    r_bank = await ac.post("/api/web/recharge/create-bank", json={"amount_vnd": 100000})
                    assert r_bank.status_code == 200
                    d_bank = r_bank.json()
                    assert d_bank["status"] == "success"
                    assert d_bank["exact_vnd"] == 100000
                    assert d_bank["account_number"] == "8880117869"
                    assert d_bank["account_name"] == "NGUYEN XUAN TRUONG"
                    assert "vietqr.io" in d_bank["qr_url"]

                    # 3. On-chain Invoice
                    r_onc = await ac.post("/api/web/recharge/create-onchain", json={"network": "TRX", "amount_usd": 25.0})
                    assert r_onc.status_code == 200
                    d_onc = r_onc.json()
                    assert d_onc["status"] == "success"
                    assert d_onc["network"] == "TRX"
                    assert float(d_onc["exact_amount"]) >= 25.0

                    # 4. Check status pending
                    r_chk = await ac.post("/api/web/recharge/check-status", json={"order_id": 1, "order_type": "binance"})
                    assert r_chk.status_code == 200
                    assert r_chk.json()["status"] == "PENDING"

                    # 5. Cancel invoice
                    r_cnc = await ac.post("/api/web/recharge/cancel", json={"order_id": 1, "order_type": "binance"})
                    assert r_cnc.status_code == 200
                    assert r_cnc.json()["status"] == "success"


@pytest.mark.asyncio
async def test_web_register_page_and_terms_checkbox(test_app):
    @asynccontextmanager
    async def reg_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", reg_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/register")
            assert r.status_code == 200
            # Must NOT contain Telegram ID field
            assert "regTelegramId" not in r.text
            assert "Nhập ID bot để đồng bộ số dư" not in r.text
            # Must contain terms agreement checkbox linking to /policy
            assert "agreeTermsCheck" in r.text
            assert 'href="/policy"' in r.text
            assert "Điều khoản dịch vụ" in r.text

            # Test submit without agreeing to terms -> should fail
            r_no_terms = await ac.post("/register", data={
                "username": "testuser99",
                "password": "password123",
                "confirm_password": "password123"
            })
            assert r_no_terms.status_code == 302
            assert "register?error=" in r_no_terms.headers.get("location", "")

            # Test submit with agreeing to terms
            with patch("web_shop.session_commit", AsyncMock()):
                r_ok = await ac.post("/register", data={
                    "username": "testuser99",
                    "password": "password123",
                    "confirm_password": "password123",
                    "agree_terms": "1"
                })
                assert r_ok.status_code == 302
                assert r_ok.headers.get("location", "") == "/"


@pytest.mark.asyncio
async def test_web_login_page_no_admin_notice(test_app):
    @asynccontextmanager
    async def login_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", login_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/login?next=/")
            assert r.status_code == 200
            # Must NOT contain the admin notice alert box
            assert "Dành cho Admin" not in r.text
            assert "Chuyển sang Admin Panel" not in r.text


@pytest.mark.asyncio
async def test_web_light_dark_mode_and_language_switcher(test_app):
    @asynccontextmanager
    async def home_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", home_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/")
            assert r.status_code == 200

            # 1. Dark mode elements & styles
            assert 'data-bs-theme="light"' in r.text
            assert 'id="themeToggleBtn"' in r.text
            assert 'toggleTheme()' in r.text
            assert '[data-bs-theme="dark"]' in r.text

            # 2. White-on-white text elimination & custom styling
            assert '.balance-badge' in r.text
            assert '.text-purple' in r.text
            assert '.bg-purple' in r.text
            assert '.bg-blue' in r.text
            assert 'color: #4a154b !important;' in r.text

            # 3. Bilingual language switcher (English / Vietnamese)
            assert 'id="langDropdownBtn"' in r.text
            assert "setLanguage('vi')" in r.text
            assert "setLanguage('en')" in r.text
            assert 'data-i18n="top_welcome"' in r.text
            assert 'var I18N = {' in r.text


@pytest.mark.asyncio
async def test_admin_redirect_loop_prevention_and_single_icons(test_app):
    @asynccontextmanager
    async def home_db_ctx(*args, **kwargs):
        yield SmartMockDbSession()

    with patch("web_shop.get_db_session", home_db_ctx):
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
            r = await ac.get("/")
            assert r.status_code == 200

            # 1. Buy button has robust click handler and attributes
            assert "btn-open-buy" in r.text
            assert "handleBuyClick(this)" in r.text
            assert 'id="buyModalGuestStep"' in r.text
            assert "showModalSafe('buyModal')" in r.text

            # 2. Translations do not inject duplicate icons inside buttons with existing icons
            assert "btn_admin_panel: 'Trang Quản trị Admin'" in r.text
            assert "btn_buy_now: 'MUA NGAY'" in r.text
            assert "btn_sold_out: 'TẠM HẾT'" in r.text
            assert "all_cats_label: 'Tất cả sản phẩm'" in r.text

            # 3. Non-admin visiting /login?next=/admin does NOT redirect back to /admin (loop prevention)
            # Create session for normal user
            login_res = await ac.get("/login?next=/admin", follow_redirects=False)
            assert login_res.status_code == 200  # Guest gets login page, no infinite loop

            # 4. Direct AuthenticationBackend auto-renewal & loop prevention test
            from admin import authentication_backend
            from starlette.requests import Request as StarletteRequest

            scope_admin = {"type": "http", "method": "GET", "path": "/admin", "headers": [], "session": {"web_user": {"id": 1, "username": "admin", "is_admin": True}}}
            req_admin = StarletteRequest(scope_admin)
            auth_res = await authentication_backend.authenticate(req_admin)
            assert auth_res is True
            assert "token" in req_admin.session

            # 5. Check no JavaScript syntax errors in HTML scripts
            assert "String.fromCharCode(10)" in r.text
            assert "var usdRate =" in r.text
            assert "bootstrap.bundle.min.js" in r.text
            assert "addEventListener('click'" in r.text
            # Verify no unescaped multiline string literal joins in script tags
            import re
            for m in re.finditer(r'<script[\s\S]*?</script>', r.text):
                assert "join('\n')" not in m.group(0), "Broken unescaped multiline join detected in script tag"
