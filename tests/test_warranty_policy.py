import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from enums.language import Language
from services.policy_defaults import (
    DEFAULT_WARRANTY_LEGAL_POLICY,
    DEFAULT_WARRANTY_SHORT_SUMMARY,
    split_message_text,
    get_default_policy,
    get_default_summary
)
import config


def test_default_warranty_policy_content():
    policy = DEFAULT_WARRANTY_LEGAL_POLICY
    assert "Luật An ninh mạng" in policy
    assert "Nghị định 15/2020/NĐ-CP" in policy
    assert "Facebook" in policy
    assert "ChatGPT" in policy
    assert "CapCut" in policy
    assert "VPN" in policy
    assert "MIỄN TRỪ" in policy
    assert "24 giờ" in policy
    assert "@truongdvfb" in policy


def test_default_summary_content():
    summary = DEFAULT_WARRANTY_SHORT_SUMMARY
    assert "Luật An ninh mạng" in summary
    assert "1 đổi 1 trong 24h" in summary
    assert "Facebook" in summary
    assert "@truongdvfb" in summary


def test_split_message_text():
    short_text = "This is a short message"
    chunks = split_message_text(short_text, max_length=100)
    assert len(chunks) == 1
    assert chunks[0] == short_text

    long_text = "\n".join([f"Line number {i} - some sample text for testing" for i in range(200)])
    chunks = split_message_text(long_text, max_length=500)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 500


@pytest.mark.asyncio
async def test_settings_service_policy_integration():
    from services.settings import SettingsService
    session = AsyncMock()

    # Test get_all_settings with default
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    settings = await SettingsService.get_all_settings(session)
    assert "WARRANTY_LEGAL_POLICY" in settings
    assert "WARRANTY_SHORT_SUMMARY" in settings
    assert "Luật An ninh mạng" in settings["WARRANTY_LEGAL_POLICY"]

    # Test save_settings
    new_policy = "Chính sách bảo hành mới 123"
    new_summary = "Tóm tắt bảo hành mới 456"
    res = await SettingsService.save_settings({
        "WARRANTY_LEGAL_POLICY": new_policy,
        "WARRANTY_SHORT_SUMMARY": new_summary
    }, session)

    assert "WARRANTY_LEGAL_POLICY" in res["saved_keys"]
    assert "WARRANTY_SHORT_SUMMARY" in res["saved_keys"]
    assert config.WARRANTY_LEGAL_POLICY == new_policy
    assert config.WARRANTY_SHORT_SUMMARY == new_summary


def test_admin_policy_view_metadata():
    from admin_policy_view import WarrantyPolicyAdminView
    view = WarrantyPolicyAdminView()
    assert "Chính sách & Bảo hành" in view.name
    assert "fa-shield-halved" in view.icon


def test_bot_registered_warranty_policy_view():
    with open("bot.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "from admin_policy_view import WarrantyPolicyAdminView" in content
    assert "admin.add_base_view(WarrantyPolicyAdminView)" in content


def test_run_py_has_warranty_and_policy_handlers():
    with open("run.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Command(\"policy\")" in content
    assert "Command(\"warranty\")" in content
    assert "Command(\"dieukhoan\")" in content
    assert "Command(\"baohanh\")" in content
    assert "view_full_policy" in content
    assert "handle_full_policy" in content
    assert "handle_unified_support" in content
