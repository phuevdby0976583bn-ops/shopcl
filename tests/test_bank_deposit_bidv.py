from models.item import Item
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from models.buy import Buy
from models.subcategory import Subcategory
from models.category import Category
from models.buyItem import BuyItem
from models.deposit import Deposit
from models.button_media import ButtonMedia
from models.payment import Payment
from models.coupon import Coupon
from models.shipping_option import ShippingOption
from models.review import Review
from models.referral import ReferralBonus
from models.binance_pay import BinancePayOrder
from models.bank_order import BankDepositOrder

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from enums.language import Language
from services.bank_deposit import (
    crc16_ccitt,
    build_vietqr_emvco_payload,
    BankDepositService
)


def test_crc16_ccitt_standard():
    test_str = "00020101021238540010A00000072701240006970418011088801178690208QRIBFTTA53037045405520005802VN62180814NAP 51942208156304"
    crc = crc16_ccitt(test_str.encode("ascii"))
    assert len(crc) == 4
    assert all(c in "0123456789ABCDEF" for c in crc)


def test_build_vietqr_emvco_payload():
    payload = build_vietqr_emvco_payload(
        bin_code="970418",
        account_no="8880117869",
        amount_vnd=52000,
        memo="NAP 5194220815"
    )
    assert payload.startswith("000201")
    assert "970418" in payload
    assert "8880117869" in payload
    assert "NAP 5194220815" in payload
    assert len(payload) > 50


def test_generate_vietqr_image():
    buf = BankDepositService.generate_vietqr_image(
        bin_code="970418",
        account_no="8880117869",
        amount_vnd=52000,
        memo="NAP 5194220815",
        bank_code="BIDV"
    )
    assert buf is not None
    assert len(buf.data) > 1000
    assert buf.filename.startswith("vietqr_NAP_5194220815")


@pytest.mark.asyncio
async def test_create_bank_invoice_mock():
    mock_user = User(id=1, telegram_id=5194220815, top_up_amount=0.0)
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result

    qr_file, text, kb, order = await BankDepositService.create_bank_invoice(
        telegram_id=5194220815,
        base_amount_usd=2.0,
        session=mock_session,
        language=Language.VI
    )
    assert qr_file is not None
    assert "8880117869" in text
    assert "BIDV" in text
    assert "NAP 5194220815" in text
    assert order.amount_vnd == 52000.0
    assert order.memo == "NAP 5194220815"


@pytest.mark.asyncio
async def test_process_and_credit_transactions_logic():
    mock_user = User(id=1, telegram_id=5194220815, top_up_amount=5.0, consume_records=0.0)
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    mock_res_exist = MagicMock()
    mock_res_exist.scalar_one_or_none.return_value = None

    mock_res_user = MagicMock()
    mock_res_user.scalar_one_or_none.return_value = mock_user

    mock_res_pending = MagicMock()
    mock_res_pending.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_res_exist, mock_res_user, mock_res_pending]

    mock_api_resp = {
        "status": "success",
        "transactions": [
            {
                "transactionID": "BIDV-TX-9999",
                "amount": 52000,
                "description": "NAP 5194220815 Nguyen Van A chuyen khoan",
                "type": "IN"
            }
        ]
    }

    class MockClientResponse:
        status = 200
        async def json(self):
            return mock_api_resp
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockSession:
        def get(self, url, **kwargs):
            return MockClientResponse()
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    dummy_bot = AsyncMock()
    import config
    config.BANK_BIDV_TOKEN = "5bba49041ff9263b6e9aa1cde25c72de"

    mock_res_exp = MagicMock()
    mock_session.execute.side_effect = [mock_res_exist, mock_res_user, mock_res_pending, mock_res_exp]

    with patch("aiohttp.ClientSession", return_value=MockSession()):
        credited = await BankDepositService.process_and_credit_transactions(dummy_bot, mock_session)
        assert len(credited) == 1
        assert credited[0]["telegram_id"] == 5194220815
        assert credited[0]["amount_vnd"] == 52000.0
        assert credited[0]["amount_usd"] == 2.0
        assert mock_user.top_up_amount == 7.0

def test_anti_spam_deposit_check_rate_limit():
    from handlers.user.deposit import check_deposit_rate_limit, _check_deposit_cooldowns
    _check_deposit_cooldowns.clear()

    # Lan 1: Cho phep
    allowed, remaining = check_deposit_rate_limit(user_id=99999, action_type="bank")
    assert allowed is True
    assert remaining == 0.0

    # Lan 2 (ngay lap tuc): Bi chan (Rate limited)
    allowed, remaining = check_deposit_rate_limit(user_id=99999, action_type="bank")
    assert allowed is False
    assert remaining > 0.0

    # User khac: Khong bi anh huong
    allowed, remaining = check_deposit_rate_limit(user_id=88888, action_type="bank")
    assert allowed is True


import os
import subprocess

@pytest.mark.asyncio
async def test_min_deposit_vnd_settings_service_and_config():
    import config
    from services.settings import SettingsService, SUPPORTED_SETTING_KEYS

    assert "MIN_DEPOSIT_VND" in SUPPORTED_SETTING_KEYS

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    # Save MIN_DEPOSIT_VND
    res = await SettingsService.save_settings({"MIN_DEPOSIT_VND": "30000"}, mock_session)
    assert res["status"] == "success"
    assert "MIN_DEPOSIT_VND" in res["saved_keys"]
    assert config.MIN_DEPOSIT_VND == 30000.0


@pytest.mark.asyncio
async def test_admin_settings_html_contains_vnd_field_and_valid_js():
    from admin_settings_view import render_unified_settings_page
    from unittest.mock import MagicMock, patch

    req = MagicMock()
    req.session = {"token": "valid_mock_token"}
    req.query_params = {}

    with patch("admin_settings_view.decode_token", return_value={"sub": "admin"}),          patch("db.get_db_session") as mock_db:
        mock_session = MagicMock()
        mock_db.return_value.__aenter__.return_value = mock_session
        with patch("services.settings.SettingsService.get_all_settings", return_value={"MIN_DEPOSIT_VND": 25000.0, "MIN_DEPOSIT_USDT": 1.0}):
            resp = await render_unified_settings_page(req)
            html = resp.body.decode("utf-8")

            # Verify HTML input fields
            assert 'id="bank_min_deposit_vnd"' in html
            assert 'id="bank_min_deposit"' in html
            assert 'onMinVndChange' in html
            assert 'saveBankSettings' in html

            # Extract inline JS script and verify syntax via Node.js
            s_idx = html.find("<script>")
            e_idx = html.find("</script>", s_idx)
            assert s_idx != -1 and e_idx != -1
            script = html[s_idx + 8:e_idx]

            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
                tmp.write(script)
                tmp_path = tmp.name

            try:
                proc = subprocess.run(["node", "--check", tmp_path], capture_output=True, text=True)
                assert proc.returncode == 0, f"JS Syntax Error: {proc.stderr}"
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_receive_bank_amount_validation_min_vnd():
    import config
    from handlers.user.deposit import receive_bank_amount
    from aiogram.fsm.context import FSMContext
    from aiogram.types import Message, User, Chat

    config.BANK_EXCHANGE_RATE = 25000.0
    config.MIN_DEPOSIT_VND = 25000.0
    config.MIN_DEPOSIT_USDT = 1.0

    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()
    msg.from_user = User(id=12345678, is_bot=False, first_name="Tester")
    msg.chat = Chat(id=12345678, type="private")
    state = AsyncMock(spec=FSMContext)
    mock_session = AsyncMock()

    # Case 1: user enters 10000 VND (< 25000 VND) -> Rejected
    msg.text = "10000"
    await receive_bank_amount(msg, state, mock_session, Language.VI)
    assert msg.answer.called
    call_args = msg.answer.call_args[0][0]
    assert "tối thiểu" in call_args.lower()
    assert "25,000" in call_args

    # Case 2: user enters 10k (< 25k) -> Rejected
    msg.answer.reset_mock()
    msg.text = "10k"
    await receive_bank_amount(msg, state, mock_session, Language.VI)
    assert msg.answer.called
    call_args = msg.answer.call_args[0][0]
    assert "25,000" in call_args
