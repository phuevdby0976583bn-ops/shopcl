import asyncio

import logging

import sys

import traceback

from contextlib import asynccontextmanager

from pathlib import Path

from aiogram.fsm.storage.redis import RedisStorage

from aiogram.types import BufferedInputFile, URLInputFile, Update, BotCommand

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

from models.cart import CartAdmin

from models.cartItem import CartItemAdmin

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
keep_alive_task = None


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
        await asyncio.sleep(480)






async def binance_pay_background_worker():

    while True:

        try:

            await asyncio.sleep(25)

            if config.BINANCE_API_KEY and config.BINANCE_API_SECRET:

                from services.binance_pay import BinancePayService

                async with get_db_session() as session:

                    await BinancePayService.process_and_credit_transactions(bot, session)

        except asyncio.CancelledError:

            break

        except Exception as e:

            logging.warning(f"Error in binance_pay_background_worker: {e}")





async def _startup() -> None:

    await create_db_and_tables()
    async with get_db_session() as db_sess:
        from services.settings import SettingsService
        await SettingsService.load_settings_into_config(db_sess)
        try:
            from sqlalchemy import update, or_
            from models.user import User
            await db_sess.execute(
                update(User)
                .where(or_(User.language == Language.EN, User.language.is_(None)))
                .values(language=Language.VI)
            )
            await db_sess.commit()
            logging.info("Synced users language to Vietnamese (VI)")
        except Exception as e:
            logging.warning(f"Note on user language sync: {e}")

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



    static = Path("static")

    if static.exists() is False:

        static.mkdir()

    me = await bot.get_me()

    photos = await bot.get_user_profile_photos(me.id)

    if photos.total_count == 0:

        photo_id_list = []

        for admin_id in config.ADMIN_ID_LIST:

            try:

                msg = await bot.send_photo(chat_id=admin_id,

                                           photo=URLInputFile(url="https://img.freepik.com/premium-vector/no-photo-available-vector-icon-default-image-symbol-picture-coming-soon-web-site-mobile-app_87543-18055.jpg",

                                                              filename="no_image.png"))

                bot_photo_id = msg.photo[-1].file_id

                photo_id_list.append(bot_photo_id)

            except Exception as _:

                pass

        bot_photo_id = photo_id_list[0] if photo_id_list else "no_image_default"

    else:

        bot_photo_id = photos.photos[0][-1].file_id

    with open("static/no_image.jpeg", "w") as f:

        f.write(bot_photo_id)

    await MediaService.update_inaccessible_media(bot)

    validate_i18n()

    await ButtonMediaRepository.init_buttons_media()

    if config.CRYPTO_FORWARDING_MODE:

        for cryptocurrency in Cryptocurrency:

            forwarding_address = cryptocurrency.get_forwarding_address()

            if forwarding_address:

                is_addr_valid = WalletService.validate_withdrawal_address(forwarding_address, cryptocurrency)

                if is_addr_valid is False:

                    logging.warning(

                        "Your withdrawal address for %s cryptocurrency is not configured correctly: %s",

                        cryptocurrency.name,

                        forwarding_address

                    )

                else:

                    logging.info("Crypto forwarding configured for %s: %s", cryptocurrency.name, forwarding_address)

    for admin in config.ADMIN_ID_LIST:

        try:

            await bot.send_message(admin, 'Bot is working')

        except Exception as e:

            logging.warning(e)



    global binance_task, keep_alive_task

    binance_task = asyncio.create_task(binance_pay_background_worker())
    keep_alive_task = asyncio.create_task(keep_alive_background_worker())





async def _shutdown() -> None:

    logging.warning('Shutting down..')

    global binance_task, keep_alive_task

    if binance_task:
        binance_task.cancel()
    if keep_alive_task:
        keep_alive_task.cancel()

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



@app.get("/")

@app.get("/health")

async def health_check():

    return {"status": "ok", "message": "AiogramShopBot is running"}



admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend, title="🦐 Bubba Gump")

admin.add_model_view(UserAdmin)

admin.add_model_view(BuyAdmin)

admin.add_model_view(ShippingOptionAdmin)

admin.add_model_view(CouponAdmin)

admin.add_model_view(CategoryAdmin)

admin.add_model_view(SubcategoryAdmin)

admin.add_model_view(ItemAdmin)
from bulk_upload_view import BulkUploadAdminView
admin.add_base_view(BulkUploadAdminView)

admin.add_model_view(DepositAdmin)

admin.add_model_view(BuyItemAdmin)

admin.add_model_view(PaymentAdmin)

admin.add_model_view(CartAdmin)

admin.add_model_view(CartItemAdmin)

admin.add_model_view(ReferralBonusAdmin)

admin.add_model_view(ReviewAdmin)



from models.binance_pay import BinancePayOrderAdmin

admin.add_model_view(BinancePayOrderAdmin)



from admin_settings_view import PaymentApiConfigView

admin.add_base_view(PaymentApiConfigView)



from processing.api_items import api_router



app.include_router(processing_router)

app.include_router(api_router)





@app.post(config.WEBHOOK_PATH)

async def webhook(request: Request):

    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")

    if config.WEBHOOK_SECRET_TOKEN and secret_token:

        if secret_token != config.WEBHOOK_SECRET_TOKEN:

            logging.warning(f"Webhook secret token mismatch: {secret_token} != {config.WEBHOOK_SECRET_TOKEN}")



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

