# -*- coding: utf-8 -*-
import pytest
from unittest.mock import AsyncMock, MagicMock
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse
from models.item import Item, ItemAdmin
from enums.item_type import ItemType


def test_item_admin_page_size_and_options():
    """Verify page_size and page_size_options are properly set for large inventory."""
    admin_view = ItemAdmin()
    assert admin_view.page_size == 50
    assert 10 in admin_view.page_size_options
    assert 50 in admin_view.page_size_options
    assert 500 in admin_view.page_size_options
    assert 2500 in admin_view.page_size_options


@pytest.mark.asyncio
async def test_item_admin_actions_bulk_reset_and_delete():
    """Verify ItemAdmin custom actions for bulk delete, reset, and mark sold."""
    admin_view = ItemAdmin()

    # Mock session_maker
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    admin_view.session_maker = lambda: FakeSessionContext()

    # 1. Test delete_selected
    mock_request = MagicMock()
    mock_request.query_params = {"pks": "20,21,22"}
    mock_request.headers = {"Referer": "/admin/item/list"}
    resp = await admin_view.delete_selected(mock_request)
    assert isinstance(resp, RedirectResponse)
    assert resp.headers["location"] == "/admin/item/list"
    assert mock_session.execute.called
    assert mock_session.commit.called

    # 2. Test mark_as_new (selected)
    mock_session.execute.reset_mock()
    resp_new = await admin_view.mark_as_new(mock_request)
    assert isinstance(resp_new, RedirectResponse)
    assert mock_session.execute.called

    # 3. Test mark_as_sold (selected)
    mock_session.execute.reset_mock()
    resp_sold = await admin_view.mark_as_sold(mock_request)
    assert isinstance(resp_sold, RedirectResponse)
    assert mock_session.execute.called

    # 4. Test reset_all_unsold (entire inventory)
    mock_session.execute.reset_mock()
    resp_all_unsold = await admin_view.reset_all_unsold(mock_request)
    assert isinstance(resp_all_unsold, RedirectResponse)
    assert mock_session.execute.called

    # 5. Test mark_all_sold (entire inventory)
    mock_session.execute.reset_mock()
    resp_all_sold = await admin_view.mark_all_sold(mock_request)
    assert isinstance(resp_all_sold, RedirectResponse)
    assert mock_session.execute.called

    # 6. Test delete_all_sold
    mock_session.execute.reset_mock()
    resp_del_sold = await admin_view.delete_all_sold(mock_request)
    assert isinstance(resp_del_sold, RedirectResponse)
    assert mock_session.execute.called

    # 7. Test delete_all_inventory
    mock_session.execute.reset_mock()
    resp_del_all = await admin_view.delete_all_inventory(mock_request)
    assert isinstance(resp_del_all, RedirectResponse)
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_item_admin_view_all_uids_html():
    """Verify view_all_uids returns HTMLResponse with extracted UIDs."""
    admin_view = ItemAdmin()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    # Mock database containing 3 Facebook clones
    mock_result.scalars.return_value.all.return_value = [
        "61595538173674|pass1|2fa1",
        "61595394900431|pass2|2fa2",
        "61595420189208|pass3|2fa3"
    ]
    mock_session.execute.return_value = mock_result

    class FakeSessionContext:
        async def __aenter__(self):
            return mock_session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    admin_view.session_maker = lambda: FakeSessionContext()

    mock_request = MagicMock()
    resp = await admin_view.view_all_uids(mock_request)
    assert isinstance(resp, HTMLResponse)
    content = resp.body.decode("utf-8")
    assert "61595538173674" in content
    assert "61595394900431" in content
    assert "61595420189208" in content
    assert "Sao chép tất cả" in content