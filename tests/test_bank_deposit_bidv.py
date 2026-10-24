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