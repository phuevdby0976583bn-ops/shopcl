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
