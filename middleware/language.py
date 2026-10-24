from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from db import get_db_session
from enums.language import Language
from repositories.user import UserRepository

# Cache ngon ngu trong RAM (0.001ms), tranh truy van DB vao Supabase moi lan bam nut
_user_language_cache: dict[int, Language] = {}


def set_cached_user_language(telegram_id: int, language: Language) -> None:
    _user_language_cache[telegram_id] = language


class I18nMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: Dict[str, Any]
    ) -> Awaitable[Any]:
        user = getattr(event, "from_user", None)
        if not user:
            data["language"] = Language.VI
            return await handler(event, data)

        # 1. Kiem tra cache sieu toc trong RAM
        cached_lang = _user_language_cache.get(user.id)
        if cached_lang:
            data["language"] = cached_lang
            return await handler(event, data)

        # 2. Neu chua co cache, tai tu session da duoc DBSessionMiddleware tao san
        existing_session = data.get("session")
        if existing_session:
            user_dto = await UserRepository.get_by_tgid(user.id, existing_session)
            lang = (user_dto.language if user_dto else None) or Language.from_locale(user.language_code) or Language.VI
            _user_language_cache[user.id] = lang
            data["language"] = lang
            return await handler(event, data)

        # 3. Fallback phong truong hop khong co session
        async with get_db_session() as session:
            user_dto = await UserRepository.get_by_tgid(user.id, session)
            lang = (user_dto.language if user_dto else None) or Language.from_locale(user.language_code) or Language.VI
            _user_language_cache[user.id] = lang
            data["language"] = lang
            return await handler(event, data)
