from types import SimpleNamespace
import pytest
from services.facebook import (
    check_uid_live,
    check_uid_live_async,
    extract_uid,
    is_facebook_clone,
    filter_live_facebook_items
)


def test_extract_uid():
    assert extract_uid("100088912345678|pass123|2FAKEY|mail@gmail.com") == "100088912345678"
    assert extract_uid("1000123456789:password123") == "1000123456789"
    assert extract_uid("4|password") == "4"
    assert extract_uid("c_user=1000999999999; xs=abcd;") == "1000999999999"
    assert extract_uid("https://facebook.com/1000555555555|pass") == "1000555555555"
    assert extract_uid("https://facebook.com/profile.php?id=1000777777777") == "1000777777777"
    assert extract_uid("NON_FB_KEY_ABCD_1234") is None
    assert extract_uid("") is None
    assert extract_uid(None) is None


def test_is_facebook_clone():
    assert is_facebook_clone("100088912345678|password") is True
    assert is_facebook_clone("STEAM-KEY-1234-ABCD") is False
    assert is_facebook_clone("") is False
    assert is_facebook_clone(None) is False


def test_check_uid_live_sync():
    res_live = check_uid_live("4")
    assert res_live == "LIVE"

    res_die = check_uid_live("100000000000001")
    assert res_die == "DIE"


@pytest.mark.asyncio
async def test_check_uid_live_async():
    res_live = await check_uid_live_async("4")
    assert res_live == "LIVE"

    res_die = await check_uid_live_async("100000000000001")
    assert res_die == "DIE"


@pytest.mark.asyncio
async def test_filter_live_facebook_items():
    # 1 live account (UID 4), 2 dead accounts
    items = [
        SimpleNamespace(id=1, private_data="100000000000001|pass1"),
        SimpleNamespace(id=2, private_data="4|pass2"),
        SimpleNamespace(id=3, private_data="100000000000002|pass3"),
    ]
    live, dead = await filter_live_facebook_items(items, required_qty=1)
    assert len(live) == 1
    assert live[0].id == 2
    assert any(d.id == 1 for d in dead)

def test_extract_uid_email_first():
    assert extract_uid("user@gmail.com|mypassword|100088912345678|2FAKEY") == "100088912345678"


def test_is_facebook_product():
    from services.facebook import is_facebook_product
    assert is_facebook_product(category_name="Clone Facebook Nuôi") is True
    assert is_facebook_product(subcategory_name="Via Cổ 2FA") is True
    assert is_facebook_product(private_data="100088912345678|pass|2fa") is True
    assert is_facebook_product(category_name="Tài khoản Telegram", subcategory_name="Session+Json") is False


@pytest.mark.asyncio
async def test_scan_and_filter_facebook_raw_lines():
    from services.facebook import scan_and_filter_facebook_raw_lines
    lines = [
        "100000000000001|die_pass",
        "4|live_pass",
        "100000000000002|die_pass2"
    ]
    # Delete DIE enabled
    kept, dead, stats = await scan_and_filter_facebook_raw_lines(lines, check_live=True, delete_die=True)
    assert len(kept) == 1
    assert "4|live_pass" in kept
    assert len(dead) == 2
    assert stats["live"] == 1
    assert stats["die"] == 2
    assert stats["deleted"] == 2

    # Delete DIE disabled
    kept_all, dead2, stats2 = await scan_and_filter_facebook_raw_lines(lines, check_live=True, delete_die=False)
    assert len(kept_all) == 3
    assert len(dead2) == 2
    assert stats2["deleted"] == 0


@pytest.mark.asyncio
async def test_deduplicate_facebook_raw_lines():
    from services.facebook import deduplicate_facebook_raw_lines
    lines = [
        "100088912345678|pass1|2FA",
        "100088912345678|pass2|2FA",  # internal duplicate
        "100099999999999|pass3|2FA",  # already in DB
        "100077777777777|pass4|2FA",  # new unique
    ]
    existing = {"100099999999999"}
    unique, dups, stats = await deduplicate_facebook_raw_lines(
        lines, existing_uids=existing, check_db=False
    )
    assert len(unique) == 2
    assert len(dups) == 2
    assert "100088912345678|pass1|2FA" in unique
    assert "100077777777777|pass4|2FA" in unique
    assert stats["duplicates"] == 2
    assert stats["internal_duplicates"] == 1
    assert stats["db_duplicates"] == 1


@pytest.mark.asyncio
async def test_scan_and_filter_with_duplicates():
    from services.facebook import scan_and_filter_facebook_raw_lines
    lines = [
        "4|live1",
        "4|live1_duplicate",
        "100000000000001|die1"
    ]
    kept, dead, stats = await scan_and_filter_facebook_raw_lines(
        lines, check_live=True, delete_die=True, filter_duplicates=True
    )
    # Only 1 live (UID 4), 1 duplicate removed, 1 die removed
    assert len(kept) == 1
    assert "4|live1" in kept
    assert stats["duplicates"] == 1
    assert stats["die"] == 1
