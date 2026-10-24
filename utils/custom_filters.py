import time
from typing import Union
from aiogram import types
from aiogram.filters import BaseFilter

from config import ADMIN_ID_LIST
from db import get_db_session
from models.user import UserDTO
from repositories.user import UserRepository
from services.user import UserService

# Cache trong bo nho RAM de phan hoi tuc thi 0.001ms, loai bo hang ngan truy van DB khong can thiet
_user_exist_cache: dict[int, float] = {}
_user_banned_cache: dict[int, tuple[bool, float]] = {}


def cache_user_exists(telegram_id: int, ttl: int = 600) -> None:
    _user_exist_cache[telegram_id] = time.time() + ttl


def invalidate_user_cache(telegram_id: int) -> None:
    _user_exist_cache.pop(telegram_id, None)
    _user_banned_cache.pop(telegram_id, None)


class AdminIdFilter(BaseFilter):
    async def __call__(self, event: Union[types.Message, types.CallbackQuery, types.TelegramObject]) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in ADMIN_ID_LIST


class IsUserExistFilter(BaseFilter):
    async def __call__(self, event: Union[types.Message, types.CallbackQuery, types.TelegramObject]) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False

        now = time.time()
        # Neu da ton tai trong cache (10 phut), tra ve True ngay lap tuc ma khong can goi DB
        if _user_exist_cache.get(user.id, 0) > now:
            return True

        async with get_db_session() as session:
            is_exist = await UserService.get(UserDTO(telegram_id=user.id), session)
            if is_exist is not None:
                _user_exist_cache[user.id] = now + 600
                return True
            return False


class IsUserBannedFilter(BaseFilter):
    async def __call__(self, event: Union[types.Message, types.CallbackQuery, types.TelegramObject]) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False

        # Admin tuyet doi khong bao gio bi ban
        if user.id in ADMIN_ID_LIST:
            return False

        now = time.time()
        cached = _user_banned_cache.get(user.id)
        if cached and cached[1] > now:
            return cached[0]

        async with get_db_session() as session:
            user_dto = await UserRepository.get_by_tgid(user.id, session)
            if user_dto:
                is_banned = bool(user_dto.is_banned and not getattr(user_dto, "is_admin", False))
                _user_banned_cache[user.id] = (is_banned, now + 120)
                _user_exist_cache[user.id] = now + 600
                return is_banned
            else:
                return False
