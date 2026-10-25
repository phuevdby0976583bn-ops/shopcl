import os
import pytest
from unittest.mock import AsyncMock, MagicMock
from types import SimpleNamespace

from services.deposit_bonus import DepositBonusService
import config


def test_deposit_bonus_disabled_by_default():
    setattr(config, "DEPOSIT_BONUS_ENABLED", False)
    assert DepositBonusService.is_enabled() is False
    assert DepositBonusService.get_bonus_display_text() == ""
    assert DepositBonusService.get_bonus_rate(100.0) == 0.0
    assert DepositBonusService.calculate_bonus(100.0) == (0.0, 0.0)


def test_deposit_bonus_enabled_tiers():
    setattr(config, "DEPOSIT_BONUS_ENABLED", True)
    setattr(config, "DEPOSIT_BONUS_TIERS", "100:2, 200:5, 300:6, 500:7, 1000:8")
    assert DepositBonusService.is_enabled() is True

    # 50 -> 0%
    assert DepositBonusService.get_bonus_rate(50.0) == 0.0
    # 100 -> 2%
    assert DepositBonusService.get_bonus_rate(100.0) == 2.0
    assert DepositBonusService.calculate_bonus(100.0) == (2.0, 2.0)
    # 250 -> 5%
    assert DepositBonusService.get_bonus_rate(250.0) == 5.0
    assert DepositBonusService.calculate_bonus(250.0) == (12.5, 5.0)
    # 1200 -> 8%
    assert DepositBonusService.get_bonus_rate(1200.0) == 8.0
    assert DepositBonusService.calculate_bonus(1000.0) == (80.0, 8.0)

    # Display text contains formatted tiers
    text = DepositBonusService.get_bonus_display_text()
    assert "Thưởng nạp qua bot" in text
    assert "+2%" in text
    assert "+8%" in text


def test_deposit_bonus_disabled_returns_empty_prompt():
    setattr(config, "DEPOSIT_BONUS_ENABLED", False)
    text = DepositBonusService.get_bonus_display_text()
    assert text == ""


def test_deposit_bonus_custom_tiers_and_delimiters():
    setattr(config, "DEPOSIT_BONUS_ENABLED", True)
    setattr(config, "DEPOSIT_BONUS_TIERS", "50:1\n100:3;500:10")
    tiers = DepositBonusService.parse_tiers()
    assert tiers == [(50.0, 1.0), (100.0, 3.0), (500.0, 10.0)]
    assert DepositBonusService.get_bonus_rate(40.0) == 0.0
    assert DepositBonusService.get_bonus_rate(50.0) == 1.0
    assert DepositBonusService.get_bonus_rate(200.0) == 3.0
    assert DepositBonusService.get_bonus_rate(1000.0) == 10.0


@pytest.mark.asyncio
async def test_admin_settings_view_tab_bonus_rendered(monkeypatch):
    from admin_settings_view import PaymentApiConfigView
    from utils.utils import create_access_token
    from starlette.requests import Request

    view = PaymentApiConfigView()
    token = create_access_token({"sub": "admin"})

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/settings",
        "headers": [],
        "session": {"token": token}
    }
    req = Request(scope)

    # Mock DB settings
    async def fake_get_all_settings(session):
        return {
            "DEPOSIT_BONUS_ENABLED": True,
            "DEPOSIT_BONUS_TIERS": "100:2,200:5,500:10"
        }

    monkeypatch.setattr("services.settings.SettingsService.get_all_settings", fake_get_all_settings)

    resp = await view.settings_page(req)
    assert resp.status_code == 200
    html_body = resp.body.decode("utf-8")
    assert "tab-bonus" in html_body
    assert "Khuyến Mãi Nạp Tiền" in html_body
    assert "deposit_bonus_enabled" in html_body
    assert "deposit_bonus_tiers" in html_body
    assert "saveBonusSettings" in html_body

    # Test MIN_DEPOSIT_USDT inputs rendered in HTML
    assert "binance_min_deposit" in html_body
    assert "krypto_min_deposit" in html_body
    assert "bank_min_deposit" in html_body
    assert "syncMinDepositInputs" in html_body
    assert "Số Tiền Nạp Tối Thiểu" in html_body


@pytest.mark.asyncio
async def test_save_min_deposit_setting():
    from services.settings import SettingsService
    from unittest.mock import AsyncMock

    session = AsyncMock()
    res = await SettingsService.save_settings({"MIN_DEPOSIT_USDT": "2.5"}, session)
    assert "MIN_DEPOSIT_USDT" in res["saved_keys"]
    assert config.MIN_DEPOSIT_USDT == 2.5

    # Reset back to default
    await SettingsService.save_settings({"MIN_DEPOSIT_USDT": "1.0"}, session)
    assert config.MIN_DEPOSIT_USDT == 1.0

