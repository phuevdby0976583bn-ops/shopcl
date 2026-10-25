from unittest.mock import patch, AsyncMock
import models.cartItem
from types import SimpleNamespace

import pytest

from enums.announcement_type import AnnouncementType
from enums.language import Language
from services.item import ItemService


def _build_item(category_id: int, subcategory_id: int, price: float = 10.0):
    return SimpleNamespace(category_id=category_id, subcategory_id=subcategory_id, price=price)


@pytest.mark.asyncio
async def test_create_announcement_message_returns_single_chunk_for_short_content(monkeypatch):
    async def _fake_get_items(session):
        return [
            _build_item(1, 10),
            _build_item(1, 11),
        ]

    async def _fake_get_categories(ids, session):
        return [SimpleNamespace(id=1, name="Category 1")]

    async def _fake_get_subcategories(ids, session):
        return [
            SimpleNamespace(id=10, name="Sub 1"),
            SimpleNamespace(id=11, name="Sub 2"),
        ]

    monkeypatch.setattr("services.item.ItemRepository.get_in_stock", _fake_get_items)
    monkeypatch.setattr("services.item.CategoryRepository.get_by_ids", _fake_get_categories)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_by_ids", _fake_get_subcategories)

    messages = await ItemService.create_announcement_message(
        AnnouncementType.CURRENT_STOCK,
        session=None,
        language=Language.EN
    )

    assert len(messages) == 1
    assert messages[0].startswith("<b>")
    assert "Category 1" in messages[0]


@pytest.mark.asyncio
async def test_create_announcement_message_splits_long_content_by_category(monkeypatch):
    async def _fake_get_items(session):
        return [_build_item(category_id=index, subcategory_id=index) for index in range(1, 60)]

    async def _fake_get_categories(ids, session):
        return [SimpleNamespace(id=index, name=f"Category {index} {'X' * 80}") for index in ids]

    async def _fake_get_subcategories(ids, session):
        return [SimpleNamespace(id=index, name=f"Subcategory {index} {'Y' * 60}") for index in ids]

    monkeypatch.setattr("services.item.ItemRepository.get_in_stock", _fake_get_items)
    monkeypatch.setattr("services.item.CategoryRepository.get_by_ids", _fake_get_categories)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_by_ids", _fake_get_subcategories)

    messages = await ItemService.create_announcement_message(
        AnnouncementType.CURRENT_STOCK,
        session=None,
        language=Language.EN
    )

    assert len(messages) > 1
    assert all(len(message) < ItemService.ANNOUNCEMENT_MESSAGE_LIMIT for message in messages)
    assert "Category 1" in messages[0]


@pytest.mark.asyncio
async def test_create_announcement_message_splits_large_single_category_without_losing_header(monkeypatch):
    async def _fake_get_items(session):
        return [_build_item(category_id=1, subcategory_id=index) for index in range(1, 80)]

    async def _fake_get_categories(ids, session):
        return [SimpleNamespace(id=1, name="Single Category")]

    async def _fake_get_subcategories(ids, session):
        return [SimpleNamespace(id=index, name=f"Subcategory {index} {'Z' * 70}") for index in ids]

    monkeypatch.setattr("services.item.ItemRepository.get_new", _fake_get_items)
    monkeypatch.setattr("services.item.CategoryRepository.get_by_ids", _fake_get_categories)
    monkeypatch.setattr("services.item.SubcategoryRepository.get_by_ids", _fake_get_subcategories)

    messages = await ItemService.create_announcement_message(
        AnnouncementType.RESTOCKING,
        session=None,
        language=Language.EN
    )

    assert len(messages) > 1
    assert all("Single Category" in message for message in messages)
    assert all(len(message) < ItemService.ANNOUNCEMENT_MESSAGE_LIMIT for message in messages)


def test_item_admin_list_and_count_query_filter_status():
    import models.cart
    import models.cartItem
    from models.item import Item, ItemAdmin
    admin_view = ItemAdmin()

    req_sold = SimpleNamespace(query_params={"status": "sold"})
    q_sold = admin_view.list_query(req_sold)
    assert any("is_sold = true" in str(crit).lower() or "is_sold = :is_sold_1" in str(crit).lower() for crit in q_sold._where_criteria)

    req_new = SimpleNamespace(query_params={"status": "new"})
    q_new = admin_view.list_query(req_new)
    assert any("is_sold = false" in str(crit).lower() or "is_sold = :is_sold_1" in str(crit).lower() for crit in q_new._where_criteria)

    req_all = SimpleNamespace(query_params={})
    q_all = admin_view.list_query(req_all)
    assert len(q_all._where_criteria) == 0


@pytest.mark.asyncio
async def test_item_admin_update_model_consistency():
    from models.item import Item, ItemAdmin
    admin_view = ItemAdmin()
    ItemAdmin.__bases__[0].update_model = AsyncMock()

    # Neu danh dau is_sold = True, thi is_new bat buoc = False
    data1 = {"is_sold": True, "is_new": True}
    await admin_view.update_model(None, "1", data1)
    assert data1["is_sold"] is True
    assert data1["is_new"] is False

    # Neu danh dau is_new = True va is_sold khong True, thi is_sold = False
    data2 = {"is_sold": False, "is_new": True}
    await admin_view.update_model(None, "1", data2)
    assert data2["is_sold"] is False
    assert data2["is_new"] is True


def test_item_admin_column_formatters():
    from models.item import Item, ItemAdmin
    admin_view = ItemAdmin()

    item_sold = SimpleNamespace(id=1, private_data="1000|Pass|2FA", is_sold=True, is_new=False, description="Test")
    fmt_sold = admin_view.column_formatters[Item.is_sold](item_sold, "is_sold")
    fmt_new1 = admin_view.column_formatters[Item.is_new](item_sold, "is_new")
    assert "bg-danger" in str(fmt_sold)
    assert "bg-secondary" in str(fmt_new1)

    item_unsold = SimpleNamespace(id=2, private_data="1000|Pass|2FA", is_sold=False, is_new=True, description="Test")
    fmt_unsold = admin_view.column_formatters[Item.is_sold](item_unsold, "is_sold")
    fmt_new2 = admin_view.column_formatters[Item.is_new](item_unsold, "is_new")
    assert "bg-success" in str(fmt_unsold)
    assert "bg-primary" in str(fmt_new2)

    # Test Price Formatter: Khi subcategory co gia $0.04 ma item.price luu 0.02, item chua ban phai hien thi theo $0.04
    subcat_4c = SimpleNamespace(id=10, name="Aged FB Clones", price=0.04)
    item_desynced = SimpleNamespace(id=13, private_data="999999", price=0.02, subcategory=subcat_4c, is_sold=False, is_new=True, description="Test")
    fmt_price = admin_view.column_formatters[Item.price](item_desynced, "price")
    assert "$0.04" in str(fmt_price)

    # khi item da ban (is_sold=True), hien thi dung gia luc ban (item.price = 0.02)
    item_sold_price = SimpleNamespace(id=7, private_data="999999", price=0.02, subcategory=subcat_4c, is_sold=True, is_new=False, description="Test")
    fmt_sold_price = admin_view.column_formatters[Item.price](item_sold_price, "price")
    assert "$0.02" in str(fmt_sold_price)
