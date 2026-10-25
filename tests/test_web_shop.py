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
        self.subcategories = subcategories or [SimpleNamespace(id=1, name="Clone Nu?i 2FA", price=0.05, description="Acc live", media_id="sub1")]

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
