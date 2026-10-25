# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import Message
from enums.language import Language
from models.shipping_option import ShippingOptionAdmin


def test_shipping_option_admin_is_hidden():
    """Ensure ShippingOptionAdmin is marked not visible and not accessible."""
    view = ShippingOptionAdmin()
    assert view.is_visible(None) is False
    assert view.is_accessible(None) is False


@pytest.mark.asyncio
async def test_admin_telegram_menu_has_no_shipping():
    """Ensure the Telegram Admin inline keyboard no longer contains shipping management button."""
    from handlers.admin.admin import admin
    mock_message = MagicMock(spec=Message)
    mock_message.answer = AsyncMock()
    mock_state = AsyncMock()

    await admin(message=mock_message, state=mock_state, language=Language.VI)
    mock_message.answer.assert_called_once()
    _, kwargs = mock_message.answer.call_args
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None

    all_callbacks = [
        btn.callback_data for row in reply_markup.inline_keyboard for btn in row if btn.callback_data
    ]
    # Verify no callback contains ShippingManagementCallback
    assert not any("shipping_management" in cb for cb in all_callbacks)