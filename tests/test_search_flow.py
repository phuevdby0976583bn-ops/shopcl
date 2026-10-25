import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from types import SimpleNamespace
from aiogram.types import Message
from enums.entity_type import EntityType
from enums.language import Language
from enums.item_type import ItemType
from callbacks import AllCategoriesCallback
from handlers.user.all_categories import parse_entity_type, execute_global_search
from services.subcategory import SubcategoryService

def test_parse_entity_type():
    assert parse_entity_type(EntityType.CATEGORY) == EntityType.CATEGORY
    assert parse_entity_type(1) == EntityType.CATEGORY
    assert parse_entity_type('1') == EntityType.CATEGORY
    assert parse_entity_type('CATEGORY') == EntityType.CATEGORY
    assert parse_entity_type('SUBCATEGORY') == EntityType.SUBCATEGORY
    assert parse_entity_type('unknown') == EntityType.CATEGORY

@pytest.mark.asyncio
async def test_execute_global_search_found():
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()
    session = AsyncMock()
    
    mock_res_cat = MagicMock()
    mock_res_cat.scalars.return_value.all.return_value = [SimpleNamespace(id=1, name='Via FB')]
    
    mock_res_sub = MagicMock()
    mock_res_sub.scalars.return_value.all.return_value = [SimpleNamespace(id=2, name='Clone US', price=0.05)]
    
    mock_cat_id = MagicMock()
    mock_cat_id.scalar_one_or_none.return_value = 1
    
    mock_cnt = MagicMock()
    mock_cnt.scalar.return_value = 5
    
    session.execute.side_effect = [mock_res_cat, mock_res_sub, mock_cat_id, mock_cnt]
    
    await execute_global_search(msg, 'clone', session, Language.VI)
    assert msg.answer.called
    args, kwargs = msg.answer.call_args
    assert 'KẾT QUẢ TÌM KIẾM CHO' in kwargs.get('text', '')

@pytest.mark.asyncio
async def test_execute_global_search_not_found():
    msg = AsyncMock(spec=Message)
    msg.answer = AsyncMock()
    session = AsyncMock()
    
    mock_res_cat = MagicMock()
    mock_res_cat.scalars.return_value.all.return_value = []
    
    mock_res_sub = MagicMock()
    mock_res_sub.scalars.return_value.all.return_value = []
    
    session.execute.side_effect = [mock_res_cat, mock_res_sub]
    
    await execute_global_search(msg, 'notfounditem', session, Language.VI)
    assert msg.answer.called
    args, kwargs = msg.answer.call_args
    assert 'Không tìm thấy sản phẩm nào phù hợp' in kwargs.get('text', '')

@pytest.mark.asyncio
async def test_select_quantity_auto_resolve_category_id():
    session = AsyncMock()
    cb = AllCategoriesCallback.create(level=3, category_id=None, subcategory_id=10, item_type=ItemType.DIGITAL)
    
    mock_cat_id = MagicMock()
    mock_cat_id.scalar_one_or_none.return_value = 5
    session.execute.return_value = mock_cat_id
    
    with patch('services.subcategory.ItemRepository.get_single', new_callable=AsyncMock) as m_single, \
         patch('services.subcategory.SubcategoryRepository.get_by_id', new_callable=AsyncMock) as m_subcat, \
         patch('services.subcategory.CategoryRepository.get_by_id', new_callable=AsyncMock) as m_cat, \
         patch('services.subcategory.ItemRepository.get_available_qty', new_callable=AsyncMock) as m_qty:
        m_single.return_value = SimpleNamespace(item_type=ItemType.DIGITAL, category_id=5, subcategory_id=10, price=0.05, description='Test')
        m_subcat.return_value = SimpleNamespace(id=10, name='Sub 10', media_id='0abc')
        m_cat.return_value = SimpleNamespace(id=5, name='Cat 5')
        m_qty.return_value = 1
        
        media, kb = await SubcategoryService.get_select_quantity_buttons(cb, session, Language.VI)
        assert cb.category_id == 5
