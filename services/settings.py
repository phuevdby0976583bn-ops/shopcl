import logging
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import config
from models.system_setting import SystemSetting

logger = logging.getLogger(__name__)

SUPPORTED_SETTING_KEYS = [
    "BINANCE_UID",
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "KRYPTO_EXPRESS_API_KEY",
    "KRYPTO_EXPRESS_API_SECRET",
    "KRYPTO_EXPRESS_API_URL",
    "CRYPTO_FORWARDING_MODE",
    "BNB_FORWARDING_ADDRESS",
    "SOL_FORWARDING_ADDRESS",
    "SUPPORT_LINK",
]


class SettingsService:
    @staticmethod
    async def load_settings_into_config(session: AsyncSession):
        """Doc tat ca cai dat tu database Supabase va cap nhat vao in-memory config."""
        try:
            stmt = select(SystemSetting)
            result = await session.execute(stmt)
            settings = result.scalars().all()
            loaded_count = 0
            for item in settings:
                if not item.key or item.value is None:
                    continue
                k = item.key.strip()
                v = item.value.strip()

                if k == "CRYPTO_FORWARDING_MODE":
                    config.CRYPTO_FORWARDING_MODE = v.lower() in ("true", "1", "yes")
                    loaded_count += 1
                elif hasattr(config, k):
                    setattr(config, k, v)
                    loaded_count += 1

            if loaded_count > 0:
                logger.info(f"Loaded {loaded_count} settings from database into config.")
        except Exception as e:
            logger.warning(f"Error loading settings from database: {e}")

    @staticmethod
    async def get_all_settings(session: AsyncSession) -> dict:
        """Lay gia tri hien tai cua tat ca cai dat tu database (hoac fallback config)."""
        db_settings = {}
        try:
            stmt = select(SystemSetting)
            result = await session.execute(stmt)
            for item in result.scalars().all():
                if item.key:
                    db_settings[item.key.strip()] = item.value
        except Exception as e:
            logger.warning(f"Error fetching settings: {e}")

        res = {
            "BINANCE_UID": db_settings.get("BINANCE_UID") or getattr(config, "BINANCE_UID", "805398854") or "805398854",
            "BINANCE_API_KEY": db_settings.get("BINANCE_API_KEY") or getattr(config, "BINANCE_API_KEY", "") or "",
            "BINANCE_API_SECRET": db_settings.get("BINANCE_API_SECRET") or getattr(config, "BINANCE_API_SECRET", "") or "",
            "KRYPTO_EXPRESS_API_KEY": db_settings.get("KRYPTO_EXPRESS_API_KEY") or getattr(config, "KRYPTO_EXPRESS_API_KEY", "") or "",
            "KRYPTO_EXPRESS_API_SECRET": db_settings.get("KRYPTO_EXPRESS_API_SECRET") or getattr(config, "KRYPTO_EXPRESS_API_SECRET", "") or "",
            "KRYPTO_EXPRESS_API_URL": db_settings.get("KRYPTO_EXPRESS_API_URL") or getattr(config, "KRYPTO_EXPRESS_API_URL", "https://kryptoexpress.pro/api") or "https://kryptoexpress.pro/api",
            "CRYPTO_FORWARDING_MODE": (
                db_settings.get("CRYPTO_FORWARDING_MODE", "").lower() in ("true", "1", "yes")
                if "CRYPTO_FORWARDING_MODE" in db_settings
                else getattr(config, "CRYPTO_FORWARDING_MODE", False)
            ),
            "BNB_FORWARDING_ADDRESS": db_settings.get("BNB_FORWARDING_ADDRESS") or getattr(config, "BNB_FORWARDING_ADDRESS", "") or "",
            "SOL_FORWARDING_ADDRESS": db_settings.get("SOL_FORWARDING_ADDRESS") or getattr(config, "SOL_FORWARDING_ADDRESS", "") or "",
            "SUPPORT_LINK": db_settings.get("SUPPORT_LINK") or getattr(config, "SUPPORT_LINK", "https://t.me/truongdvfb") or "https://t.me/truongdvfb",
        }
        return res

    @staticmethod
    async def save_settings(data: dict, session: AsyncSession) -> dict:
        """Luu cac cai dat vao Supabase va cap nhat config ngay lap tuc."""
        saved_keys = []
        for k, v in data.items():
            if k not in SUPPORTED_SETTING_KEYS:
                continue
            str_val = str(v).strip() if v is not None else ""
            sql = text("""
                INSERT INTO system_settings (key, value, updated_at)
                VALUES (:k, :v, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
            """)
            await session.execute(sql, {"k": k, "v": str_val})

            # Cap nhat config in-memory ngay lap tuc
            if k == "CRYPTO_FORWARDING_MODE":
                config.CRYPTO_FORWARDING_MODE = str_val.lower() in ("true", "1", "yes")
            elif hasattr(config, k):
                setattr(config, k, str_val)

            saved_keys.append(k)

        await session.commit()
        return {"status": "success", "saved_keys": saved_keys}
