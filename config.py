import os
from dotenv import load_dotenv

from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment
from utils.utils import get_sslipio_external_url, start_ngrok, hash_password

load_dotenv()
load_dotenv('.env.bot.dev')

# Lay Webhook Host tu bien moi truong (Render hoac domain rieng)
WEBHOOK_HOST = os.environ.get('WEBHOOK_HOST')
if not WEBHOOK_HOST:
    runtime_env_str = os.environ.get('RUNTIME_ENVIRONMENT', 'PROD').upper()
    try:
        RUNTIME_ENVIRONMENT = RuntimeEnvironment(runtime_env_str)
    except Exception:
        RUNTIME_ENVIRONMENT = RuntimeEnvironment.PROD
    if RUNTIME_ENVIRONMENT == RuntimeEnvironment.DEV:
        WEBHOOK_HOST = start_ngrok()
    else:
        WEBHOOK_HOST = get_sslipio_external_url()
else:
    WEBHOOK_HOST = WEBHOOK_HOST.rstrip('/')

WEBHOOK_PATH = os.environ.get('WEBHOOK_PATH', '/')
WEBAPP_HOST = os.environ.get('WEBAPP_HOST', '0.0.0.0')
# Render cap cong thong qua bien PORT
WEBAPP_PORT = int(os.environ.get('PORT', os.environ.get('WEBAPP_PORT', '5000')))
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'
TOKEN = os.environ.get('TOKEN')

admin_id_raw = os.environ.get('ADMIN_ID_LIST', '')
ADMIN_ID_LIST = [int(admin_id.strip()) for admin_id in admin_id_raw.split(',') if admin_id.strip().isdigit()]
SUPPORT_LINK = os.environ.get('SUPPORT_LINK', 'https://t.me/')

# POSTGRESQL / SUPABASE
DB_USER = os.environ.get('POSTGRES_USER', 'postgres')
DB_PASS = os.environ.get('POSTGRES_PASSWORD', '')
DB_PORT = int(os.environ.get('DB_PORT', '5432'))
DB_HOST = os.environ.get('DB_HOST', 'postgres')
DB_NAME = os.environ.get('POSTGRES_DB', 'aiogram-shop-bot')

PAGE_ENTRIES = int(os.environ.get('PAGE_ENTRIES', '8'))
MULTIBOT = os.environ.get('MULTIBOT', 'false').lower() == 'true'
try:
    CURRENCY = Currency(os.environ.get('CURRENCY', 'USD'))
except Exception:
    CURRENCY = Currency.USD

KRYPTO_EXPRESS_API_KEY = os.environ.get('KRYPTO_EXPRESS_API_KEY')
KRYPTO_EXPRESS_API_URL = os.environ.get('KRYPTO_EXPRESS_API_URL', 'https://kryptoexpress.pro/api')
KRYPTO_EXPRESS_API_SECRET = os.environ.get('KRYPTO_EXPRESS_API_SECRET')
WEBHOOK_SECRET_TOKEN = os.environ.get('WEBHOOK_SECRET_TOKEN', 'shopbot_secret_token')

# REDIS / UPSTASH
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis')
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD') or None
REDIS_SSL = os.environ.get('REDIS_SSL', '').lower() in ('true', '1', 'yes') or 'upstash.io' in REDIS_HOST

TELEGRAM_PROXY_URL = os.environ.get('TELEGRAM_PROXY_URL')
# VARIABLES FOR CRYPTO FORWARDING
CRYPTO_FORWARDING_MODE = os.environ.get('CRYPTO_FORWARDING_MODE', 'false').lower() == 'true'
BTC_FORWARDING_ADDRESS = os.environ.get('BTC_FORWARDING_ADDRESS')
LTC_FORWARDING_ADDRESS = os.environ.get('LTC_FORWARDING_ADDRESS')
ETH_FORWARDING_ADDRESS = os.environ.get('ETH_FORWARDING_ADDRESS')
SOL_FORWARDING_ADDRESS = os.environ.get('SOL_FORWARDING_ADDRESS')
BNB_FORWARDING_ADDRESS = os.environ.get('BNB_FORWARDING_ADDRESS')
DOGE_FORWARDING_ADDRESS = os.environ.get('DOGE_FORWARDING_ADDRESS')

# VARIABLES FOR THE REFERRAL SYSTEM
MIN_REFERRER_TOTAL_DEPOSIT = int(os.environ.get('MIN_REFERRER_TOTAL_DEPOSIT', '500'))
REFERRAL_BONUS_PERCENT = float(os.environ.get('REFERRAL_BONUS_PERCENT', '5'))
REFERRAL_BONUS_DEPOSIT_LIMIT = int(os.environ.get('REFERRAL_BONUS_DEPOSIT_LIMIT', '3'))
REFERRER_BONUS_PERCENT = float(os.environ.get('REFERRER_BONUS_PERCENT', '3'))
REFERRER_BONUS_DEPOSIT_LIMIT = int(os.environ.get('REFERRER_BONUS_DEPOSIT_LIMIT', '5'))
REFERRAL_BONUS_CAP_PERCENT = float(os.environ.get('REFERRAL_BONUS_CAP_PERCENT', '7'))
REFERRER_BONUS_CAP_PERCENT = float(os.environ.get('REFERRER_BONUS_CAP_PERCENT', '7'))
TOTAL_BONUS_CAP_PERCENT = float(os.environ.get('TOTAL_BONUS_CAP_PERCENT', '12'))

# SQLADMIN
SQLADMIN_RAW_PASSWORD = os.environ.get('SQLADMIN_RAW_PASSWORD', 'admin123')
SQLADMIN_HASHED_PASSWORD = hash_password(SQLADMIN_RAW_PASSWORD)
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '30'))
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key_123')
