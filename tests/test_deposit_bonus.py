import os
import pytest

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
