from models.item import Item
from models.cart import Cart
from models.cartItem import CartItem
from models.user import User
from models.buy import Buy
from models.cartItem import CartItem
from models.item import Item
from models.subcategory import Subcategory
from models.category import Category
from models.buyItem import BuyItem
from models.category import Category
from models.subcategory import Subcategory
from models.deposit import Deposit
from models.button_media import ButtonMedia
from models.payment import Payment
from models.coupon import Coupon
from models.shipping_option import ShippingOption
from models.review import Review
from models.referral import ReferralBonus
from models.binance_pay import BinancePayOrder
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, MagicMock
from enums.language import Language
from services.deposit_flow import DepositFlowService
from services.binance_pay import BinancePayService


class _MockScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return MagicMock(all=lambda: self._value if isinstance(self._value, list) else [])


@pytest.mark.asyncio
async def test_create_binance_invoice_text_table():
    mock_user = SimpleNamespace(id=1, telegram_id=999888, username="test_user")
    session = AsyncMock()

    # Call 1: user lookup -> returns mock_user
    # Call 2: pending amounts lookup -> returns []
    session.execute.side_effect = [
        _MockScalarResult(mock_user),
        _MockScalarResult([])
    ]

    qr_file, caption, kb, order = await DepositFlowService.create_binance_invoice(
        telegram_id=999888,
        base_amount=5.0,
        session=session,
        language=Language.VI
    )

    assert qr_file is not None
    assert "Hoá đơn nạp USDT" in caption
    assert "805398854" in caption
    assert "5.00" in caption
    assert "tỷ giá" in caption
    assert order.status == "PENDING"
    assert order.amount > 5.0
    assert order.telegram_id == 999888

    # Verify buttons
    markup = kb.as_markup()
    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("Sao chép Pay ID" in b for b in buttons)
    assert any("Sao chép số tiền" in b for b in buttons)
    assert any("Kiểm tra giao dịch" in b for b in buttons)
    assert any("Huỷ hoá đơn" in b for b in buttons)


@pytest.mark.asyncio
async def test_binance_auto_credit_by_exact_amount():
    mock_user = SimpleNamespace(id=1, telegram_id=999888, telegram_username="buyer", top_up_amount=0.0, consume_records=0.0)
    pending_order = BinancePayOrder(
        id=123,
        user_id=1,
        telegram_id=999888,
        memo="NAP 999888",
        amount=5.0055,
        status="PENDING",
        chat_id=999888,
        message_id=4567
    )

    session = AsyncMock()
    # Call 1: select pending orders -> [pending_order]
    # Call 2: select check tx_id -> None
    # Call 3: select user -> mock_user
    session.execute.side_effect = [
        _MockScalarResult([pending_order]),
        _MockScalarResult(None),
        _MockScalarResult(mock_user),
    ]

    fake_transactions = [
        {
            "transactionId": "TX_BINANCE_999",
            "orderId": "ORD_123",
            "currency": "USDT",
            "amount": "5.0055",
            "note": ""  # No memo entered by customer!
        }
    ]

    mock_bot = AsyncMock()
    with patch.object(BinancePayService, "fetch_binance_pay_transactions", return_value=fake_transactions):
        credited = await BinancePayService.process_and_credit_transactions(mock_bot, session)

    assert len(credited) == 1
    assert credited[0]["telegram_id"] == 999888
    assert credited[0]["transaction_id"] == "TX_BINANCE_999"

    # Verify order is marked COMPLETED
    assert pending_order.status == "COMPLETED"
    assert pending_order.transaction_id == "TX_BINANCE_999"

    # Verify user balance is credited
    assert mock_user.top_up_amount == 5.01 or mock_user.top_up_amount == 5.0055 or mock_user.top_up_amount == 5.0

    # Verify notification sent and message edited
    assert mock_bot.send_message.called
    assert mock_bot.edit_message_caption.called or mock_bot.edit_message_text.called


@pytest.mark.asyncio
async def test_check_order_status():
    order = BinancePayOrder(
        id=789,
        user_id=1,
        telegram_id=999888,
        memo="NAP 999888",
        amount=10.0033,
        status="COMPLETED",
        transaction_id="TX_ALREADY_PAID"
    )

    session = AsyncMock()
    session.execute.return_value = _MockScalarResult(order)

    mock_bot = AsyncMock()
    is_paid, checked_order = await BinancePayService.check_order_status(789, session, mock_bot)

    assert is_paid is True
    assert checked_order.status == "COMPLETED"
    assert checked_order.transaction_id == "TX_ALREADY_PAID"
