from __future__ import annotations
from typing import *
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
import redis.asyncio.client
import time
import config

_local_throttle_cache: dict[str, dict] = {}


def rate_limit(limit: int, key=None):
    """
    Decorator for configuring rate limit and key in different functions.
    """
    def decorator(func):
        setattr(func, 'throttling_rate_limit', limit)
        if key:
            setattr(func, 'throttling_key', key)
        return func

    return decorator


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: redis.asyncio.client.Redis = None, limit=0.5, key_prefix='antiflood_'):
        self.rate_limit = limit
        self.prefix = key_prefix
        self.throttle_manager = ThrottleManager(redis=redis)
        super(ThrottlingMiddleware, self).__init__()

    async def __call__(
            self,
            handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
            event: Message,
            data: Dict[str, Any]
    ) -> Any:
        try:
            await self.on_process_event(event, data)
        except CancelHandler:
            return

        result = await handler(event, data)
        return result

    async def on_process_event(
            self,
            event: Message,
            data: Dict[str, Any],
    ) -> Any:
        # Neu la Admin thi tuyet doi KHONG BAO GIO bi throttle
        user = getattr(event, 'from_user', None)
        if user and user.id in getattr(config, 'ADMIN_ID_LIST', []):
            return

        limit = getattr(data["handler"].callback, "throttling_rate_limit", self.rate_limit)
        key = getattr(data["handler"].callback, "throttling_key", f"{self.prefix}_message")

        try:
            await self.throttle_manager.throttle(key, rate=limit, user_id=event.from_user.id)
        except Throttled as t:
            await self.event_throttled(event, t)
            raise CancelHandler()

    async def event_throttled(self, event: Message, throttled: Throttled):
        delta = throttled.rate - throttled.delta
        msg = f'⚡ Thao tác quá nhanh! Vui lòng đợi {delta:.1f}s.'
        if throttled.exceeded_count <= 2 and isinstance(event, Message):
            await event.answer(msg)
        elif throttled.exceeded_count <= 2 and isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=False)


class ThrottleManager:
    bucket_keys = [
        "RATE_LIMIT", "DELTA",
        "LAST_CALL", "EXCEEDED_COUNT"
    ]

    def __init__(self, redis: redis.asyncio.client.Redis = None):
        self.redis = redis

    async def throttle(self, key: str, rate: float, user_id: int):
        now = time.time()
        bucket_name = f'throttle_{key}_{user_id}'

        # Xu ly cuc bo trong RAM (0.001ms), tranh blocking boi do tre mang Redis
        data = _local_throttle_cache.get(bucket_name)
        if not data:
            data = {"LAST_CALL": now, "EXCEEDED_COUNT": 0, "DELTA": 0.0, "RATE_LIMIT": rate}
            _local_throttle_cache[bucket_name] = data
            return True

        called = data.get("LAST_CALL", now)
        delta = now - called
        result = delta >= rate or delta <= 0

        data["RATE_LIMIT"] = rate
        data["LAST_CALL"] = now
        data["DELTA"] = delta
        if not result:
            data["EXCEEDED_COUNT"] = data.get("EXCEEDED_COUNT", 0) + 1
        else:
            data["EXCEEDED_COUNT"] = 1

        _local_throttle_cache[bucket_name] = data

        if len(_local_throttle_cache) > 5000:
            expired_keys = [k for k, v in _local_throttle_cache.items() if now - v.get("LAST_CALL", 0) > 60]
            for k in expired_keys:
                _local_throttle_cache.pop(k, None)

        if not result:
            raise Throttled(key=key, user=user_id, **data)

        return result


class Throttled(Exception):
    def __init__(self, **kwargs):
        self.key = kwargs.pop("key", '<None>')
        self.called_at = kwargs.pop("LAST_CALL", time.time())
        self.rate = kwargs.pop("RATE_LIMIT", None)
        self.exceeded_count = kwargs.pop("EXCEEDED_COUNT", 0)
        self.delta = kwargs.pop("DELTA", 0)
        self.user = kwargs.pop('user', None)

    def __str__(self):
        return f"Rate limit exceeded! (Limit: {self.rate} s, " \
               f"exceeded: {self.exceeded_count}, " \
               f"time delta: {round(self.delta, 3)} s)"


class CancelHandler(Exception):
    pass
