import pytest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from callbacks import AllCategoriesCallback
from enums.language import Language
from enums.item_type import ItemType
from services.subcategory import SubcategoryService

@pytest.mark.asyncio
async def test_instant_buy_confirmation_sufficient_balance():
    user = SimpleNamespace(top_up_amount=100.0, consume_records=20.0)
    cb_data = AllCategoriesCallback.create(level=4, item_type=ItemType.DIGITAL, category_id=1, subcategory_id=1, quantity=2)
    with patch('services.subcategory.ItemRepository.get_single', new_callable=AsyncMock) as mock_item, patch('services.subcategory.CategoryRepository.get_by_id', new_callable=AsyncMock) as mock_cat, patch('services.subcategory.SubcategoryRepository.get_by_id', new_callable=AsyncMock) as mock_subcat:
        mock_item.return_value = SimpleNamespace(price=10.0, description='Clone 2FA')
        mock_cat.return_value = SimpleNamespace(name='Facebook Clone')
        mock_subcat.return_value = SimpleNamespace(name='Clone Nuôi')
        session = AsyncMock()
        msg, kb = await SubcategoryService.get_instant_buy_confirmation(cb_data, user, session, Language.VI)
        assert 'TỔNG THANH TOÁN' in msg
        assert '20.00' in msg
        assert '80.00' in msg
        assert 'Số dư ví đủ thanh toán' in msg
        buttons = [b.text for row in kb.export() for b in row]
        assert any('MUA NGAY' in b for b in buttons)

@pytest.mark.asyncio
async def test_instant_buy_confirmation_insufficient_balance():
    user = SimpleNamespace(top_up_amount=5.0, consume_records=0.0)
    cb_data = AllCategoriesCallback.create(level=4, item_type=ItemType.DIGITAL, category_id=1, subcategory_id=1, quantity=2)
    with patch('services.subcategory.ItemRepository.get_single', new_callable=AsyncMock) as mock_item, patch('services.subcategory.CategoryRepository.get_by_id', new_callable=AsyncMock) as mock_cat, patch('services.subcategory.SubcategoryRepository.get_by_id', new_callable=AsyncMock) as mock_subcat:
        mock_item.return_value = SimpleNamespace(price=10.0, description='Clone 2FA')
        mock_cat.return_value = SimpleNamespace(name='Facebook Clone')
        mock_subcat.return_value = SimpleNamespace(name='Clone Nuôi')
        session = AsyncMock()
        msg, kb = await SubcategoryService.get_instant_buy_confirmation(cb_data, user, session, Language.VI)
        assert 'Số dư ví không đủ!' in msg
        assert '15.00' in msg
        buttons = [b.text for row in kb.export() for b in row]
        assert any('Binance Pay' in b for b in buttons)

def test_sqladmin_cart_views_removed():
    with open('bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert 'admin.add_model_view(CartAdmin)' not in content
    assert 'admin.add_model_view(CartItemAdmin)' not in content
