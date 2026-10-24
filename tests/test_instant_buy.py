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

from handlers.user.all_categories import execute_instant_buy
from models.buy import BuyDTO
from models.buyItem import BuyItemDTO

@pytest.mark.asyncio
async def test_execute_instant_buy_delivery_document_caption_limit():
    callback = AsyncMock()
    callback.from_user.id = 123456
    callback.message = AsyncMock()
    callback.message.caption = None
    callback.message.answer_document = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    cb_data = AllCategoriesCallback.create(
        level=5,
        item_type=ItemType.DIGITAL,
        category_id=1,
        subcategory_id=1,
        quantity=3,
        confirmation=True
    )
    mock_user = SimpleNamespace(id=1, telegram_id=123456, top_up_amount=10.0, consume_records=0.0)
    mock_cat = SimpleNamespace(id=1, name='Facebook Clone')
    mock_subcat = SimpleNamespace(id=1, name='Clone Via', price=0.02)
    mock_item = SimpleNamespace(id=10, price=0.02, description='Clone')

    # 3 live items with long cookie private_data
    live_items = [
        SimpleNamespace(id=1, private_data='61595790991123|Pass123|COOKIE_VERY_LONG_' + 'A' * 400, is_sold=False),
        SimpleNamespace(id=2, private_data='61595633317880|Pass456|COOKIE_VERY_LONG_' + 'B' * 400, is_sold=False),
        SimpleNamespace(id=3, private_data='4|Pass789|COOKIE_VERY_LONG_' + 'C' * 400, is_sold=False),
    ]

    session = AsyncMock()
    with patch('handlers.user.all_categories.UserRepository.get_by_tgid', new_callable=AsyncMock) as p_user, \
         patch('handlers.user.all_categories.CategoryRepository.get_by_id', new_callable=AsyncMock) as p_cat, \
         patch('handlers.user.all_categories.SubcategoryRepository.get_by_id', new_callable=AsyncMock) as p_subcat, \
         patch('handlers.user.all_categories.ItemRepository.get_single', new_callable=AsyncMock) as p_item, \
         patch('handlers.user.all_categories.ItemRepository.get_unsold_candidates', new_callable=AsyncMock) as p_cand, \
         patch('handlers.user.all_categories.filter_live_facebook_items', new_callable=AsyncMock) as p_filter, \
         patch('handlers.user.all_categories.UserRepository.update', new_callable=AsyncMock) as p_uupd, \
         patch('handlers.user.all_categories.ItemRepository.update', new_callable=AsyncMock) as p_iupd, \
         patch('handlers.user.all_categories.BuyRepository.create', new_callable=AsyncMock) as p_buy, \
         patch('handlers.user.all_categories.BuyItemRepository.create_single', new_callable=AsyncMock) as p_buy_item, \
         patch('handlers.user.all_categories.session_commit', new_callable=AsyncMock), \
         patch('handlers.user.all_categories.NotificationService.new_buy', new_callable=AsyncMock):

        p_user.return_value = mock_user
        p_cat.return_value = mock_cat
        p_subcat.return_value = mock_subcat
        p_item.return_value = mock_item
        p_cand.return_value = live_items
        p_filter.return_value = (live_items, [])
        p_buy.return_value = BuyDTO(id=99, buyer_id=1, total_price=0.06, status='COMPLETED', shipping_option_id=None)

        await execute_instant_buy(
            callback=callback,
            callback_data=cb_data,
            session=session,
            language=Language.VI
        )

        assert callback.message.answer_document.called
        call_kwargs = callback.message.answer_document.call_args.kwargs
        caption = call_kwargs.get('caption', '')
        assert len(caption) <= 1024, f"Caption too long! Length: {len(caption)}"
        assert "#99" in caption
        assert mock_user.consume_records == 0.06

@pytest.mark.asyncio
async def test_execute_instant_buy_insufficient_live_accounts():
    callback = AsyncMock()
    callback.from_user.id = 123456
    callback.message = AsyncMock()
    callback.message.caption = None
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    cb_data = AllCategoriesCallback.create(
        level=5,
        item_type=ItemType.DIGITAL,
        category_id=1,
        subcategory_id=1,
        quantity=3,
        confirmation=True
    )
    mock_user = SimpleNamespace(id=1, telegram_id=123456, top_up_amount=10.0, consume_records=0.0)
    mock_cat = SimpleNamespace(id=1, name='Facebook Clone')
    mock_subcat = SimpleNamespace(id=1, name='Clone Via', price=0.02)
    mock_item = SimpleNamespace(id=10, price=0.02, description='Clone')

    # Only 2 live items, 1 die item
    live_items = [
        SimpleNamespace(id=1, private_data='61595790991123|Pass123|Cookie1', is_sold=False),
        SimpleNamespace(id=2, private_data='61595633317880|Pass456|Cookie2', is_sold=False)
    ]
    dead_items = [
        SimpleNamespace(id=3, private_data='61595933155279|Pass789|Cookie3', is_sold=False)
    ]

    session = AsyncMock()
    with patch('handlers.user.all_categories.UserRepository.get_by_tgid', new_callable=AsyncMock) as p_user, \
         patch('handlers.user.all_categories.CategoryRepository.get_by_id', new_callable=AsyncMock) as p_cat, \
         patch('handlers.user.all_categories.SubcategoryRepository.get_by_id', new_callable=AsyncMock) as p_subcat, \
         patch('handlers.user.all_categories.ItemRepository.get_single', new_callable=AsyncMock) as p_item, \
         patch('handlers.user.all_categories.ItemRepository.get_unsold_candidates', new_callable=AsyncMock) as p_cand, \
         patch('handlers.user.all_categories.filter_live_facebook_items', new_callable=AsyncMock) as p_filter, \
         patch('handlers.user.all_categories.ItemRepository.delete_items_by_ids', new_callable=AsyncMock) as p_del, \
         patch('handlers.user.all_categories.session_commit', new_callable=AsyncMock):

        p_user.return_value = mock_user
        p_cat.return_value = mock_cat
        p_subcat.return_value = mock_subcat
        p_item.return_value = mock_item
        p_cand.return_value = live_items + dead_items
        p_filter.return_value = (live_items, dead_items)

        await execute_instant_buy(
            callback=callback,
            callback_data=cb_data,
            session=session,
            language=Language.VI
        )

        # Money must NOT be deducted
        assert mock_user.consume_records == 0.0
        # User is prompted with option to buy remaining 2 live accounts
        assert callback.message.edit_text.called
        call_kwargs = callback.message.edit_text.call_args.kwargs
        assert 'Kho không đủ số lượng tài khoản LIVE' in call_kwargs.get('text', '')
        assert '2' in call_kwargs.get('text', '')
