import pytest
import time
from unittest.mock import AsyncMock, MagicMock
from enums.bot_entity import BotEntity
from enums.keyboard_button import KeyboardButton
from enums.language import Language
from middleware.throttling_middleware import ThrottlingMiddleware, ThrottleManager
from models.button_media import ButtonMediaDTO
from models.category import CategoryDTO
from models.subcategory import SubcategoryDTO
from repositories.button_media import ButtonMediaRepository, _button_media_cache, clear_button_media_cache
from repositories.category import CategoryRepository, _category_by_id_cache, clear_category_cache
from repositories.subcategory import SubcategoryRepository, _subcategory_by_id_cache, clear_subcategory_cache
from utils.custom_filters import (
    IsUserExistFilter,
    IsUserBannedFilter,
    cache_user_exists,
    cache_user_banned,
    invalidate_user_cache,
    _user_exist_cache,
    _user_banned_cache,
)
from utils.localizator import Localizator
from utils.utils import get_bot_photo_id, _bot_photo_id_cached
import utils.utils as utils_mod


@pytest.mark.asyncio
async def test_throttling_middleware_rate_limit():
    tm = ThrottlingMiddleware()
    assert tm.rate_limit <= 0.15, "Rate limit should be 0.15s or lower to avoid user lag"

    mgr = ThrottleManager()
    # First call: OK
    res1 = await mgr.throttle("test_key", rate=0.15, user_id=999991)
    assert res1 is True

    # Call after 0.2s: OK (no throttling)
    time.sleep(0.16)
    res2 = await mgr.throttle("test_key", rate=0.15, user_id=999991)
    assert res2 is True


def test_bot_photo_id_cached(monkeypatch):
    utils_mod._bot_photo_id_cached = "cached_media_id_123"
    result = get_bot_photo_id()
    assert result == "cached_media_id_123"
    # Reset
    utils_mod._bot_photo_id_cached = ""


def test_localizator_all_texts_cache():
    Localizator.clear_cache()
    assert len(Localizator._all_texts_cache) == 0

    texts1 = Localizator.get_all_texts(BotEntity.COMMON, "cancel")
    assert "❌ Cancel" in texts1
    assert (BotEntity.COMMON, "cancel") in Localizator._all_texts_cache

    texts2 = Localizator.get_all_texts(BotEntity.COMMON, "cancel")
    assert texts1 == texts2

    Localizator.clear_cache()
    assert len(Localizator._all_texts_cache) == 0


@pytest.mark.asyncio
async def test_user_filters_and_cache():
    user_id = 88812345
    invalidate_user_cache(user_id)
    assert user_id not in _user_exist_cache
    assert user_id not in _user_banned_cache

    # Warm cache
    cache_user_exists(user_id, ttl=1800)
    cache_user_banned(user_id, is_banned=False, ttl=1800)

    assert _user_exist_cache[user_id] > time.time()
    assert _user_banned_cache[user_id][0] is False

    mock_event = MagicMock()
    mock_event.from_user.id = user_id

    # Filter should return True from RAM without touching DB session
    exist_filter = IsUserExistFilter()
    assert await exist_filter(mock_event) is True

    banned_filter = IsUserBannedFilter()
    assert await banned_filter(mock_event) is False

    # Invalidate cache
    invalidate_user_cache(user_id)
    assert user_id not in _user_exist_cache
    assert user_id not in _user_banned_cache


@pytest.mark.asyncio
async def test_button_media_cache():
    clear_button_media_cache()
    assert len(_button_media_cache) == 0

    mock_dto = ButtonMediaDTO(media_id="media_btn_test", button=KeyboardButton.ALL_CATEGORIES)
    _button_media_cache[KeyboardButton.ALL_CATEGORIES] = mock_dto

    mock_session = AsyncMock()
    # Call get_by_button should return cached without executing SQL
    result = await ButtonMediaRepository.get_by_button(KeyboardButton.ALL_CATEGORIES, mock_session)
    assert result.media_id == "media_btn_test"
    mock_session.execute.assert_not_called()

    clear_button_media_cache()
    assert len(_button_media_cache) == 0


@pytest.mark.asyncio
async def test_category_and_subcategory_cache():
    clear_category_cache()
    clear_subcategory_cache()

    cat_dto = CategoryDTO(id=42, name="Test Cat", media_id="media_42")
    _category_by_id_cache[42] = (cat_dto, time.time() + 300)

    mock_session = AsyncMock()
    res_cat = await CategoryRepository.get_by_id(42, mock_session)
    assert res_cat.id == 42
    assert res_cat.name == "Test Cat"
    mock_session.execute.assert_not_called()

    sub_dto = SubcategoryDTO(id=84, name="Test Sub", category_id=42, media_id="media_84")
    _subcategory_by_id_cache[84] = (sub_dto, time.time() + 300)
    res_sub = await SubcategoryRepository.get_by_id(84, mock_session)
    assert res_sub.id == 84
    assert res_sub.name == "Test Sub"
    mock_session.execute.assert_not_called()

    clear_category_cache()
    clear_subcategory_cache()
