import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.requests import Request
from starlette.datastructures import Headers
import config
from admin import AdminAuth
from middleware.anti_ddos import AntiDDoSMiddleware
from repositories.user import UserRepository
from processing.processing import fetch_crypto_event
from models.payment import ProcessingPaymentDTO
from enums.payment import PaymentType
from enums.currency import Currency
from enums.cryptocurrency import Cryptocurrency


@pytest.mark.asyncio
async def test_admin_login_null_safe():
    auth = AdminAuth(secret_key="test_secret")
    
    # 1. Empty form (None username/password)
    req1 = MagicMock(spec=Request)
    req1.form = AsyncMock(return_value={})
    assert await auth.login(req1) is False

    # 2. None values
    req2 = MagicMock(spec=Request)
    req2.form = AsyncMock(return_value={"username": None, "password": None})
    assert await auth.login(req2) is False

    # 3. Wrong credentials
    req3 = MagicMock(spec=Request)
    req3.form = AsyncMock(return_value={"username": "wrong", "password": "bad"})
    assert await auth.login(req3) is False


@pytest.mark.asyncio
async def test_anti_ddos_content_length_error_handling():
    app = MagicMock()
    middleware = AntiDDoSMiddleware(app)

    # Malformed Content-Length (string)
    req = MagicMock(spec=Request)
    req.url.path = "/api/test"
    req.headers = Headers({"content-length": "not-a-number"})
    req.client = MagicMock(host="1.2.3.4")

    call_next = AsyncMock()
    resp = await middleware.dispatch(req, call_next)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_processing_payment_null_safe():
    payment_dto = ProcessingPaymentDTO(
        id=999999,
        paymentType=PaymentType.PAYMENT,
        fiatCurrency=Currency.USD,
        cryptoCurrency=Cryptocurrency.USDT_BEP20,
        fiatAmount=10.0,
        isPaid=True
    )
    req = MagicMock(spec=Request)
    req.headers = {"X-Signature": "sig"}
    req.body = AsyncMock(return_value=b"{}")

    with patch("processing.processing.__security_check", return_value=True), \
         patch("processing.processing.PaymentRepository.get_user_by_payment_id", return_value=None), \
         patch("processing.processing.PaymentRepository.get_by_processing_payment_id", return_value=None):
        result = await fetch_crypto_event(payment_dto, req)
        assert result == "Payment or user not found"


@pytest.mark.asyncio
async def test_user_repository_get_by_tgid_for_update(monkeypatch):
    captured_stmt = []

    class _ScalarResult:
        def scalar(self):
            return None

    async def fake_session_execute(stmt, session):
        captured_stmt.append(stmt)
        return _ScalarResult()

    monkeypatch.setattr("repositories.user.session_execute", fake_session_execute)

    # Test with for_update=True
    res = await UserRepository.get_by_tgid(12345678, session=None, for_update=True)
    assert res is None
    assert len(captured_stmt) == 1
    assert captured_stmt[0]._for_update_arg is not None


def test_sqladmin_list_template_actions_script():
    with open("templates/sqladmin/list.html", "r", encoding="utf-8") as f:
        content = f.read()
    assert "dropdownMenuButton" in content
    assert "action-delete" in content
    assert "action-custom-modal-" in content
    assert "select-box:checked" in content
