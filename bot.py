import utils.multipart_fix  # noqa: F401 - Patch Starlette 1024KB limit
import asyncio

import logging

import sys

import traceback

from contextlib import asynccontextmanager

from pathlib import Path

from aiogram.fsm.storage.redis import RedisStorage

from aiogram.types import BufferedInputFile, URLInputFile, Update, BotCommand, MenuButtonCommands

from redis.asyncio import Redis

from sqladmin import Admin



import config

from aiogram import Dispatcher

from fastapi import FastAPI, Request, status, HTTPException

from fastapi.responses import JSONResponse



from admin import authentication_backend

from db import create_db_and_tables, engine, get_db_session

import uvicorn

from enums.cryptocurrency import Cryptocurrency

from models.buy import BuyAdmin

from models.buyItem import BuyItemAdmin

from models.category import CategoryAdmin

from models.coupon import CouponAdmin

from models.deposit import DepositAdmin

from models.item import ItemAdmin

from models.payment import PaymentAdmin

from models.referral import ReferralBonusAdmin

from models.review import ReviewAdmin

from models.shipping_option import ShippingOptionAdmin

from models.subcategory import SubcategoryAdmin

from models.user import UserAdmin

from processing.processing import processing_router

from repositories.button_media import ButtonMediaRepository

from services.media import MediaService

from services.notification import NotificationService

from services.wallet import WalletService

from utils.telegram import create_bot, create_telegram_session

from utils.utils import validate_i18n



redis = Redis(
    host=config.REDIS_HOST,
    port=config.REDIS_PORT,
    password=config.REDIS_PASSWORD,
    ssl=config.REDIS_SSL,
    socket_timeout=3.0,
    socket_connect_timeout=3.0,
    retry_on_timeout=True
)

session = create_telegram_session()

bot = create_bot(config.TOKEN, session)

dp = Dispatcher(storage=RedisStorage(redis))





binance_task = None
bank_task = None
keep_alive_task = None
facebook_cron_task = None


async def facebook_stock_cron_worker():
    """Tự động quét và loại bỏ clone Facebook DIE trong kho định kỳ sau mỗi XX phút."""
    await asyncio.sleep(60)
    from services.facebook import scan_facebook_inventory

    while True:
        try:
            interval_minutes = int(getattr(config, "FB_CRON_CHECK_INTERVAL_MINUTES", 0) or 0)
            if interval_minutes <= 0:
                # TẮT QUÉT ĐỊNH KỲ MẶC ĐỊNH để tiết kiệm 100% băng thông và tránh bị Facebook chặn IP
                await asyncio.sleep(600)
                continue

            async with get_db_session() as session:
                res = await scan_facebook_inventory(session, auto_delete_die=True, max_items_to_scan=100)
                total = res.get("total_scanned", 0)
                live = res.get("live_count", 0)
                die = res.get("die_count", 0)
                deleted = res.get("deleted_count", 0)

                logging.info(f"Cron check live: Quét {total} clone | Live: {live} | Die đã xóa: {deleted}")

                notify_admin = getattr(config, "FB_CRON_NOTIFY_ADMIN", True)
                if notify_admin and total > 0 and (die > 0 or interval_minutes >= 60):
                    alert_text = (
                        f"🔔 <b>[CRON TỰ ĐỘNG CHECK LIVE KHO]</b>\n\n"
                        f"⏱️ <i>Chu kỳ: Mỗi {interval_minutes} phút</i>\n"
                        f"• Tổng clone kiểm tra: <b>{total}</b>\n"
                        f"• Hoạt động (LIVE): <b>{live}</b> ✅\n"
                        f"• Tài khoản DIE phát hiện: <b>{die}</b> ❌\n"
                    )
                    if deleted > 0:
                        alert_text += f"⚡ <b>Đã tự động loại bỏ {deleted} nick DIE khỏi kho hàng!</b>"
                    else:
                        alert_text += "✨ <i>Kho hàng 100% clone Live ổn định!</i>"

                    for admin_id in getattr(config, "ADMIN_ID_LIST", []):
                        try:
                            await bot.send_message(chat_id=admin_id, text=alert_text, parse_mode="HTML")
                        except Exception as e:
                            logging.debug(f"Failed to send cron check live notification to admin {admin_id}: {e}")

            await asyncio.sleep(interval_minutes * 60)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"Error in facebook_stock_cron_worker: {e}")
            await asyncio.sleep(300)


async def keep_alive_background_worker():
    """Tu dong ping /health moi 8 phut de Render Free Service khong bao gio bi ngu (spin-down)."""
    await asyncio.sleep(60)
    import aiohttp
    while True:
        try:
            url = getattr(config, "WEBHOOK_HOST", "")
            if url and ("onrender.com" in url or "render" in url):
                health_url = f"{url.rstrip('/')}/health"
                async with aiohttp.ClientSession() as s:
                    async with s.get(health_url, timeout=10) as resp:
                        logging.debug(f"Keep-alive ping /health: status {resp.status}")
        except Exception as e:
            logging.debug(f"Keep-alive ping note: {e}")
        await asyncio.sleep(720)






async def bank_deposit_background_worker():
    await asyncio.sleep(20)
    while True:
        try:
            token = getattr(config, "BANK_BIDV_TOKEN", "") or ""
            auto_check = getattr(config, "BANK_AUTO_CHECK", True)
            if token and auto_check:
                from services.bank_deposit import BankDepositService
                async with get_db_session() as session:
                    await BankDepositService.process_and_credit_transactions(bot, session)
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"Error in bank_deposit_background_worker: {e}")
            await asyncio.sleep(30)


async def binance_pay_background_worker():
    await asyncio.sleep(25)
    while True:
        try:
            if config.BINANCE_API_KEY and config.BINANCE_API_SECRET:
                from services.binance_pay import BinancePayService
                async with get_db_session() as session:
                    await BinancePayService.process_and_credit_transactions(bot, session)
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.warning(f"Error in binance_pay_background_worker: {e}")
            await asyncio.sleep(30)


async def _startup() -> None:
    # 1. Khởi tạo Database an toàn, không làm sập ASGI app nếu mạng chập chờn
    try:
        await create_db_and_tables()
        async with get_db_session() as db_sess:
            from services.settings import SettingsService
            await SettingsService.load_settings_into_config(db_sess)

            # Kiểm tra xem migration đã chạy lần đầu chưa để tránh lặp lại mỗi lần server restart
            from sqlalchemy import text
            try:
                res_mig = await db_sess.execute(text("SELECT value FROM system_settings WHERE key = 'schema_v4_migrated'"))
                migrated = res_mig.scalar_one_or_none()
            except Exception:
                migrated = None

            if not migrated:
                schema_cmds = [
                    "ALTER TABLE subcategories ADD COLUMN IF NOT EXISTS price FLOAT DEFAULT 0.0",
                    "ALTER TABLE subcategories ADD COLUMN IF NOT EXISTS description VARCHAR DEFAULT ''",
                    "ALTER TABLE items ALTER COLUMN price DROP NOT NULL",
                    "ALTER TABLE items ALTER COLUMN description DROP NOT NULL",
                    "ALTER TABLE binance_pay_orders ADD COLUMN IF NOT EXISTS chat_id BIGINT",
                    "ALTER TABLE binance_pay_orders ADD COLUMN IF NOT EXISTS message_id BIGINT",
                    "ALTER TABLE bank_deposit_orders ADD COLUMN IF NOT EXISTS chat_id BIGINT",
                    "ALTER TABLE bank_deposit_orders ADD COLUMN IF NOT EXISTS message_id BIGINT",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS web_username VARCHAR",
                    "ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL",
                    "UPDATE items SET is_new = FALSE WHERE is_sold = TRUE",
                    """
                    UPDATE subcategories s
                    SET price = sub.item_price
                    FROM (
                        SELECT subcategory_id, MAX(price) AS item_price
                        FROM items
                        WHERE price IS NOT NULL AND price > 0
                        GROUP BY subcategory_id
                    ) sub
                    WHERE s.id = sub.subcategory_id AND (s.price IS NULL OR s.price = 0)
                    """,
                    """
                    UPDATE subcategories s
                    SET description = sub.item_desc
                    FROM (
                        SELECT subcategory_id, MAX(description) AS item_desc
                        FROM items
                        WHERE description IS NOT NULL AND description != ''
                        GROUP BY subcategory_id
                    ) sub
                    WHERE s.id = sub.subcategory_id AND (s.description IS NULL OR s.description = '')
                    """
                ]
                for cmd in schema_cmds:
                    try:
                        await db_sess.execute(text(cmd.strip()))
                    except Exception:
                        pass
                try:
                    await db_sess.execute(text("INSERT INTO system_settings (key, value) VALUES ('schema_v4_migrated', 'true') ON CONFLICT (key) DO NOTHING;"))
                except Exception:
                    pass
                await db_sess.commit()
                logging.info("Migrated initial database schema successfully.")
    except Exception as e:
        logging.error(f"Database initialization note (will connect on demand): {e}")

    # 2. Khởi tạo Telegram Bot an toàn (không bao giờ quăng exception làm sập web)
    if config.TOKEN:
        webhook_url = f"{config.WEBHOOK_HOST}{config.WEBHOOK_PATH}"
        logging.info(f"Setting Telegram webhook to: {webhook_url}")
        try:
            await bot.set_webhook(
                url=webhook_url,
                secret_token=config.WEBHOOK_SECRET_TOKEN if config.WEBHOOK_SECRET_TOKEN else None,
                drop_pending_updates=False
            )
            logging.info(f"Webhook set successfully to {webhook_url}")
        except Exception as e:
            logging.warning(f"Error setting webhook: {e}")

        commands = [
            BotCommand(command="menu", description="Mở Menu chính (Main Menu)"),
            BotCommand(command="start", description="Trang chủ (Home)"),
            BotCommand(command="products", description="Xem sản phẩm (Products)"),
            BotCommand(command="orders", description="Đơn hàng đã mua (Orders)"),
            BotCommand(command="wallet", description="Ví & Nạp tiền (Wallet)"),
            BotCommand(command="support", description="Hỗ trợ, Bảo hành & API"),
            BotCommand(command="language", description="Đổi ngôn ngữ (Language)"),
        ]
        try:
            await bot.set_my_commands(commands)
        except Exception as e:
            logging.warning(f"Failed to set bot commands: {e}")

        try:
            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            logging.info("Set chat menu button to MenuButtonCommands successfully")
        except Exception as e:
            logging.warning(f"Failed to set chat menu button: {e}")

        try:
            static = Path("static")
            if not static.exists():
                static.mkdir()
            me = await bot.get_me()
            photos = await bot.get_user_profile_photos(me.id)
            if photos.total_count == 0:
                photo_id_list = []
                for admin_id in config.ADMIN_ID_LIST:
                    try:
                        msg = await bot.send_photo(
                            chat_id=admin_id,
                            photo=URLInputFile(url="https://img.freepik.com/premium-vector/no-photo-available-vector-icon-default-image-symbol-picture-coming-soon-web-site-mobile-app_87543-18055.jpg", filename="no_image.png")
                        )
                        bot_photo_id = msg.photo[-1].file_id
                        photo_id_list.append(bot_photo_id)
                    except Exception:
                        pass
                bot_photo_id = photo_id_list[0] if photo_id_list else "no_image_default"
            else:
                bot_photo_id = photos.photos[0][-1].file_id

            with open("static/no_image.jpeg", "w") as f:
                f.write(bot_photo_id)

            await MediaService.update_inaccessible_media(bot)
        except Exception as e:
            logging.warning(f"Note on bot profile photo/media: {e}")

        try:
            validate_i18n()
            await ButtonMediaRepository.init_buttons_media()
        except Exception as e:
            logging.warning(f"Note on button media init: {e}")

        for admin in getattr(config, "ADMIN_ID_LIST", []):
            try:
                await bot.send_message(admin, 'Bot is working')
            except Exception as e:
                logging.debug(e)

    # 3. Kích hoạt các background worker
    global binance_task, bank_task, keep_alive_task, facebook_cron_task

    binance_task = asyncio.create_task(binance_pay_background_worker())
    bank_task = asyncio.create_task(bank_deposit_background_worker())
    keep_alive_task = asyncio.create_task(keep_alive_background_worker())
    facebook_cron_task = asyncio.create_task(facebook_stock_cron_worker())


async def _shutdown() -> None:

    logging.warning('Shutting down..')

    global binance_task, bank_task, keep_alive_task, facebook_cron_task

    if binance_task:
        binance_task.cancel()
    if bank_task:
        bank_task.cancel()
    if keep_alive_task:
        keep_alive_task.cancel()
    if facebook_cron_task:
        facebook_cron_task.cancel()

    await dp.storage.close()

    await bot.session.close()

    logging.warning('Bye!')





@asynccontextmanager

async def lifespan(app: FastAPI):

    await _startup()

    try:

        yield

    finally:

        await _shutdown()





from middleware.anti_ddos import AntiDDoSMiddleware



app = FastAPI(lifespan=lifespan)

from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(SessionMiddleware, secret_key=config.JWT_SECRET_KEY)
app.add_middleware(AntiDDoSMiddleware, max_requests_per_minute=120)



@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok", "message": "AiogramShopBot is running", "version": "v5_debug_login"}

@app.post("/api/debug-login")
async def debug_login(request: Request):
    import traceback
    try:
        form = await request.form()
        un = form.get("username")
        pw = form.get("password")
        from admin import authentication_backend
        ok = await authentication_backend.login(request)
        return {
            "form_keys": list(form.keys()),
            "un": un,
            "pw_len": len(pw) if pw else 0,
            "login_ok": ok,
            "session_in_scope": "session" in request.scope,
            "sqladmin_pw": getattr(config, "SQLADMIN_RAW_PASSWORD", None),
        }
    except Exception as e:
        return {"error": str(e), "tb": traceback.format_exc()}


@app.get("/cron/check-live")
@app.post("/cron/check-live")
async def top_level_cron_check_live(request: Request):
    from processing.api_items import cron_check_live_endpoint
    return await cron_check_live_endpoint(request)



admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend, title="🦐 Bubba Gump")

admin.add_model_view(UserAdmin)

admin.add_model_view(BuyAdmin)


admin.add_model_view(CouponAdmin)

admin.add_model_view(CategoryAdmin)

admin.add_model_view(SubcategoryAdmin)

admin.add_model_view(ItemAdmin)

admin.add_model_view(DepositAdmin)

admin.add_model_view(BuyItemAdmin)

admin.add_model_view(PaymentAdmin)

admin.add_model_view(ReferralBonusAdmin)

admin.add_model_view(ReviewAdmin)



from models.binance_pay import BinancePayOrderAdmin

admin.add_model_view(BinancePayOrderAdmin)

from models.bank_order import BankDepositOrderAdmin
admin.add_model_view(BankDepositOrderAdmin)



from admin_settings_view import PaymentApiConfigView

admin.add_base_view(PaymentApiConfigView)

from admin_policy_view import WarrantyPolicyAdminView
admin.add_base_view(WarrantyPolicyAdminView)

from bulk_upload_view import BulkUploadAdminView
admin.add_base_view(BulkUploadAdminView)



from processing.api_items import api_router



app.include_router(processing_router)

app.include_router(api_router)
from web_shop import web_router
app.include_router(web_router)





@app.post(config.WEBHOOK_PATH)

async def webhook(request: Request):

    if config.WEBHOOK_SECRET_TOKEN:
        secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if not secret_token or secret_token != config.WEBHOOK_SECRET_TOKEN:
            logging.warning("Unauthorized webhook request: missing or invalid secret token")
            return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden: invalid secret token"})



    try:

        update_data = await request.json()

        telegram_update = Update.model_validate(update_data, context={"bot": bot})

        asyncio.create_task(dp.feed_update(bot=bot, update=telegram_update))
        return {"status": "ok"}

    except Exception as e:

        tb = traceback.format_exc()

        logging.error(f"Error processing webhook: {tb}")

        return JSONResponse(status_code=500, content={"status": "error", "error": str(e), "traceback": tb})





@app.exception_handler(Exception)

async def exception_handler(request: Request, exc: Exception):

    traceback_str = traceback.format_exc()

    admin_notification = (

        f"Critical error caused by {exc}\n\n"

        f"Stack trace:\n{traceback_str}"

    )

    if len(admin_notification) > 4096:

        byte_array = bytearray(admin_notification, 'utf-8')

        admin_notification = BufferedInputFile(byte_array, "exception.txt")

    await NotificationService.send_to_admins(admin_notification, None)

    return JSONResponse(

        status_code=500,

        content={"message": f"An error occurred: {str(exc)}"},

    )





def main() -> None:

    uvicorn.run(

        app,

        host=config.WEBAPP_HOST,

        port=config.WEBAPP_PORT,

        proxy_headers=True,

        forwarded_allow_ips="*",

    )

