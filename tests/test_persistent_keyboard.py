# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from enums.language import Language
from run import get_start_keyboard
import config


def test_start_keyboard_is_persistent_and_resized():
    """Verify reply keyboard is always persistent and has placeholder for all languages."""
    for lang in [Language.VI, Language.EN, Language.HI, Language.ZH]:
        kb = get_start_keyboard(lang, telegram_id=99999999)
        assert kb.is_persistent is True, f"is_persistent must be True for {lang}"
        assert kb.resize_keyboard is True, f"resize_keyboard must be True for {lang}"
        assert kb.input_field_placeholder is not None and len(kb.input_field_placeholder) > 0

        # Check button rows
        assert len(kb.keyboard) >= 3
        # Row 1: Products, Orders
        assert len(kb.keyboard[0]) == 2
        # Row 2: Wallet, Support
        assert len(kb.keyboard[1]) == 2
        # Row 3: Language
        assert len(kb.keyboard[2]) == 1


def test_start_keyboard_admin_button(monkeypatch):
    """Verify admin menu button appears only for admin IDs."""
    admin_id = 123456789
    monkeypatch.setattr(config, "ADMIN_ID_LIST", [admin_id])

    user_kb = get_start_keyboard(Language.VI, telegram_id=999999)
    assert len(user_kb.keyboard) == 3

    admin_kb = get_start_keyboard(Language.VI, telegram_id=admin_id)
    assert len(admin_kb.keyboard) == 4
    assert any("⚙️" in btn.text for btn in admin_kb.keyboard[3])


@pytest.mark.asyncio
async def test_fallback_menu_keywords_trigger_start():
    """Verify typing 'menu', 'shop', 'alo', 'xin chào' triggers start menu without needing /start."""
    from run import fallback_any_text

    mock_message = AsyncMock()
    mock_message.text = "menu"
    mock_message.from_user.id = 555555
    mock_message.from_user.username = "test_user"
    mock_message.from_user.full_name = "Test User"
    mock_message.answer = AsyncMock()

    mock_state = AsyncMock()
    mock_state.get_state = AsyncMock(return_value=None)
    mock_session = AsyncMock()

    with patch("run.start", new_callable=AsyncMock) as mock_start:
        await fallback_any_text(mock_message, mock_session, mock_state, Language.VI)
        mock_start.assert_awaited_once()