import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from types import SimpleNamespace
from enums.language import Language
from enums.item_type import ItemType
from callbacks import AllCategoriesCallback
from handlers.user.constants import UserStates
from services.i18n_messages import get_custom_qty_label, get_custom_qty_prompt
from services.subcategory import SubcategoryService
from handlers.user.all_categories import handle_ask_custom_qty, handle_custom_quantity_input, select_quantity


def test_custom_qty_labels_and_prompts_all_languages():
    for lang in Language:
        label = get_custom_qty_label(lang)
        assert len(label) > 3
        prompt = get_custom_qty_prompt(lang, "Facebook", "Clone US 2FA", 0.20, "$", 7077)
        assert "Facebook" in prompt
        assert "Clone US 2FA" in prompt
        assert "7077" in prompt


@pytest.mark.asyncio
async def test_select_quantity_buttons_includes_custom_qty():
    session = AsyncMock()
    cb = AllCategoriesCallback.create(level=3, category_id=1, subcategory_id=2, item_type=ItemType.DIGITAL)

    with patch("services.subcategory.ItemRepository.get_single", new_callable=AsyncMock) as m_single, \
         patch("services.subcategory.SubcategoryRepository.get_by_id", new_callable=AsyncMock) as m_subcat, \
         patch("services.subcategory.CategoryRepository.get_by_id", new_callable=AsyncMock) as m_cat, \
         patch("services.subcategory.ItemRepository.get_available_qty", new_callable=AsyncMock) as m_qty:

        m_single.return_value = SimpleNamespace(item_type=ItemType.DIGITAL, category_id=1, subcategory_id=2, price=0.20, description="")
        m_subcat.return_value = SimpleNamespace(id=2, name="Clone US", media_id="0xyz")
        m_cat.return_value = SimpleNamespace(id=1, name="Facebook")
        m_qty.return_value = 7077

        media, kb = await SubcategoryService.get_select_quantity_buttons(cb, session, Language.VI)
        markup = kb.as_markup()
        all_btn_texts = [btn.text for row in markup.inline_keyboard for btn in row]

        # Has custom quantity button
        assert any("Tự nhập số lượng" in t for t in all_btn_texts)
        # Has "Tất cả (7077)" button since 7077 > 500
        assert any("7077" in t for t in all_btn_texts)


@pytest.mark.asyncio
async def test_select_quantity_sets_state_custom_buy_quantity():
    cb_query = MagicMock()
    cb_query.from_user = SimpleNamespace(id=123456)
    cb_query.message = MagicMock()
    cb_query.message.caption = None
    cb_query.message.edit_text = AsyncMock()
    cb_query.message.answer = AsyncMock()
    cb_data = AllCategoriesCallback.create(level=3, category_id=1, subcategory_id=2, item_type=ItemType.DIGITAL)
    session = AsyncMock()
    state = AsyncMock()

    with patch("handlers.user.all_categories.SubcategoryService.get_select_quantity_buttons", new_callable=AsyncMock) as m_kb:
        m_kb.return_value = (SimpleNamespace(caption="Choose qty"), MagicMock())
        await select_quantity(callback=cb_query, callback_data=cb_data, session=session, state=state, language=Language.VI)

        state.set_state.assert_called_with(UserStates.custom_buy_quantity)
        state.update_data.assert_called_with(category_id=1, subcategory_id=2, item_type="DIGITAL")


@pytest.mark.asyncio
async def test_handle_custom_quantity_input_valid_33():
    msg = MagicMock()
    msg.text = "33"
    msg.from_user = SimpleNamespace(id=123456)
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {"category_id": 1, "subcategory_id": 2, "item_type": "DIGITAL"}
    session = AsyncMock()

    with patch("handlers.user.all_categories.ItemRepository.get_available_qty", new_callable=AsyncMock) as m_qty, \
         patch("handlers.user.all_categories.instant_buy_confirmation", new_callable=AsyncMock) as m_confirm:

        m_qty.return_value = 7077
        await handle_custom_quantity_input(msg, state, session, Language.VI)

        assert m_confirm.called
        kwargs = m_confirm.call_args.kwargs
        assert kwargs["callback_data"].quantity == 33
        assert kwargs["callback_data"].subcategory_id == 2


@pytest.mark.asyncio
async def test_handle_custom_quantity_input_exceeds_stock():
    msg = MagicMock()
    msg.text = "10000"
    msg.from_user = SimpleNamespace(id=123456)
    msg.answer = AsyncMock()
    state = AsyncMock()
    state.get_data.return_value = {"category_id": 1, "subcategory_id": 2, "item_type": "DIGITAL"}
    session = AsyncMock()

    with patch("handlers.user.all_categories.ItemRepository.get_available_qty", new_callable=AsyncMock) as m_qty:
        m_qty.return_value = 7077
        await handle_custom_quantity_input(msg, state, session, Language.VI)

        assert msg.answer.called
        answer_text = msg.answer.call_args.args[0]
        assert "không đủ" in answer_text
        assert "7077" in answer_text


@pytest.mark.asyncio
async def test_handle_custom_quantity_cancel():
    msg = MagicMock()
    msg.text = "Huỷ"
    msg.from_user = SimpleNamespace(id=123456)
    msg.answer = AsyncMock()
    state = AsyncMock()
    session = AsyncMock()

    await handle_custom_quantity_input(msg, state, session, Language.VI)
    assert state.clear.called
    assert msg.answer.called
    assert "huỷ" in msg.answer.call_args.args[0].lower()
