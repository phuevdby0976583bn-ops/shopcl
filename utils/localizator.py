import json
from pathlib import Path
from typing import Any

from enums.bot_entity import BotEntity
from enums.language import Language


class Localizator:
    _i18n_dir = Path("./i18n")
    _cache: dict[Language, dict] = {}
    _all_texts_cache: dict[tuple[BotEntity, str], set[str]] = {}

    @classmethod
    def _normalize_language(cls, language: Any) -> Language:
        if isinstance(language, Language):
            return language
        if isinstance(language, str):
            try:
                return Language(language.lower())
            except ValueError:
                return Language.from_locale(language)
        return Language.VI

    @classmethod
    def _load_language(cls, language: Any) -> dict:
        lang_enum = cls._normalize_language(language)
        cached = cls._cache.get(lang_enum)
        if cached is not None:
            return cached
        path = cls._i18n_dir / f"{lang_enum.value}.json"
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        cls._cache[lang_enum] = data
        return data

    @classmethod
    def get_text(cls, language: Any, entity: BotEntity, key: str) -> str:
        lang_enum = cls._normalize_language(language)
        try:
            language_payload = cls._load_language(lang_enum)
            return language_payload[entity.name.lower()][key]
        except (KeyError, Exception):
            if lang_enum == Language.EN:
                raise
            return cls.get_text(Language.EN, entity, key)

    @classmethod
    def get_all_texts(cls, entity: BotEntity, key: str) -> set[str]:
        cache_key = (entity, key)
        if cache_key in cls._all_texts_cache:
            return cls._all_texts_cache[cache_key]

        localized_texts = set()
        for locale_file in cls._i18n_dir.glob("*.json"):
            try:
                language = Language(locale_file.stem)
            except ValueError:
                continue
            localized_texts.add(cls.get_text(language, entity, key))
        cls._all_texts_cache[cache_key] = localized_texts
        return localized_texts

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()
        cls._all_texts_cache.clear()
