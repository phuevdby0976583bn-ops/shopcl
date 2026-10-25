import os
from dotenv import load_dotenv

from enums.currency import Currency
from enums.runtime_environment import RuntimeEnvironment
from utils.utils import get_sslipio_external_url, start_ngrok, hash_password

load_dotenv()
load_dotenv('.env.bot.dev')

# Lay Webhook Host tu bien moi truong (Render hoac domain rieng)
WEBHOOK_HOST = (
    os.environ.get('WEBHOOK_HOST')
    or os.environ.get('RENDER_EXTERNAL_URL')
    or "https://shopcl.onrender.com"
).strip().strip('"').strip("'").rstrip('/')

WEBHOOK_PATH = os.environ.get('WEBHOOK_PATH', '/').strip().strip('"').strip("'")
WEBAPP_HOST = os.environ.get('WEBAPP_HOST', '0.0.0.0').strip().strip('"').strip("'")
# Render cap cong thong qua bien PORT
WEBAPP_PORT = int(os.environ.get('PORT', os.environ.get('WEBAPP_PORT', '5000')))
WEBHOOK_URL = f'{WEBHOOK_HOST}{WEBHOOK_PATH}'
TOKEN = os.environ.get('TOKEN', '').strip().strip('"').strip("'")

admin_id_raw = os.environ.get('ADMIN_ID_LIST', '').strip().strip('"').strip("'")
ADMIN_ID_LIST = [int(admin_id.strip()) for admin_id in admin_id_raw.split(',') if admin_id.strip().isdigit()]
raw_support = os.environ.get('SUPPORT_LINK', '').strip().strip('"').strip("'")
if not raw_support or raw_support.rstrip('/') == 'https://t.me':
    SUPPORT_LINK = 'https://t.me/truongdvfb'
else:
    SUPPORT_LINK = raw_support

# POSTGRESQL / SUPABASE
DB_USER = os.environ.get('POSTGRES_USER', 'postgres').strip().strip('"').strip("'")
DB_PASS = os.environ.get('POSTGRES_PASSWORD', '').strip().strip('"').strip("'")
DB_PORT = int(os.environ.get('DB_PORT', '5432'))
DB_HOST = os.environ.get('DB_HOST', 'postgres').strip().strip('"').strip("'")
DB_NAME = os.environ.get('POSTGRES_DB', 'aiogram-shop-bot').strip().strip('"').strip("'")

PAGE_ENTRIES = int(os.environ.get('PAGE_ENTRIES', '8'))
MULTIBOT = os.environ.get('MULTIBOT', 'false').lower() == 'true'
try:
    CURRENCY = Currency(os.environ.get('CURRENCY', 'USD'))
except Exception:
    CURRENCY = Currency.USD

KRYPTO_EXPRESS_API_KEY = os.environ.get('KRYPTO_EXPRESS_API_KEY')
KRYPTO_EXPRESS_API_URL = os.environ.get('KRYPTO_EXPRESS_API_URL', 'https://kryptoexpress.pro/api')
KRYPTO_EXPRESS_API_SECRET = os.environ.get('KRYPTO_EXPRESS_API_SECRET')
WEBHOOK_SECRET_TOKEN = os.environ.get('WEBHOOK_SECRET_TOKEN', 'shopbot_secret_token').strip().strip('"').strip("'")

# REDIS / UPSTASH
REDIS_HOST = os.environ.get('REDIS_HOST', 'redis').strip().strip('"').strip("'")
REDIS_PORT = int(os.environ.get('REDIS_PORT', '6379'))
REDIS_PASSWORD = (os.environ.get('REDIS_PASSWORD') or '').strip().strip('"').strip("'") or None
REDIS_SSL = os.environ.get('REDIS_SSL', '').lower() in ('true', '1', 'yes') or 'upstash.io' in REDIS_HOST

TELEGRAM_PROXY_URL = os.environ.get('TELEGRAM_PROXY_URL')

# BINANCE PAY CONFIGURATION (0% PHÍ CHUYỂN NỘI BỘ BINANCE)
BINANCE_UID = (os.environ.get('BINANCE_UID') or os.environ.get('BINANCE_PAY_UID') or '805398854').strip().strip('"').strip("'")
BINANCE_API_KEY = (os.environ.get('BINANCE_API_KEY') or '').strip().strip('"').strip("'")
BINANCE_API_SECRET = (os.environ.get('BINANCE_API_SECRET') or os.environ.get('BINANCE_SECRET_KEY') or '').strip().strip('"').strip("'")
# VARIABLES FOR CRYPTO FORWARDING
CRYPTO_FORWARDING_MODE = os.environ.get('CRYPTO_FORWARDING_MODE', 'false').lower() == 'true'
BTC_FORWARDING_ADDRESS = os.environ.get('BTC_FORWARDING_ADDRESS')
LTC_FORWARDING_ADDRESS = os.environ.get('LTC_FORWARDING_ADDRESS')
ETH_FORWARDING_ADDRESS = os.environ.get('ETH_FORWARDING_ADDRESS')
SOL_FORWARDING_ADDRESS = os.environ.get('SOL_FORWARDING_ADDRESS')
BNB_FORWARDING_ADDRESS = os.environ.get('BNB_FORWARDING_ADDRESS')
DOGE_FORWARDING_ADDRESS = os.environ.get('DOGE_FORWARDING_ADDRESS')
ONLY_USDT_MODE = os.environ.get('ONLY_USDT_MODE', 'false').lower() in ('true', '1', 'yes')

# VARIABLES FOR THE REFERRAL SYSTEM
MIN_REFERRER_TOTAL_DEPOSIT = int(os.environ.get('MIN_REFERRER_TOTAL_DEPOSIT', '500'))
REFERRAL_BONUS_PERCENT = float(os.environ.get('REFERRAL_BONUS_PERCENT', '5'))
REFERRAL_BONUS_DEPOSIT_LIMIT = int(os.environ.get('REFERRAL_BONUS_DEPOSIT_LIMIT', '3'))
REFERRER_BONUS_PERCENT = float(os.environ.get('REFERRER_BONUS_PERCENT', '3'))
REFERRER_BONUS_DEPOSIT_LIMIT = int(os.environ.get('REFERRER_BONUS_DEPOSIT_LIMIT', '5'))
REFERRAL_BONUS_CAP_PERCENT = float(os.environ.get('REFERRAL_BONUS_CAP_PERCENT', '7'))
REFERRER_BONUS_CAP_PERCENT = float(os.environ.get('REFERRER_BONUS_CAP_PERCENT', '7'))
TOTAL_BONUS_CAP_PERCENT = float(os.environ.get('TOTAL_BONUS_CAP_PERCENT', '12'))


# VIETNAMESE BANK (BIDV / THUEAPI.PRO) CONFIGURATION
BANK_BIDV_TOKEN = (os.environ.get('BANK_BIDV_TOKEN') or '5bba49041ff9263b6e9aa1cde25c72de').strip().strip('"').strip("'")
BANK_ACCOUNT_NUMBER = (os.environ.get('BANK_ACCOUNT_NUMBER') or '8880117869').strip().strip('"').strip("'")
BANK_ACCOUNT_NAME = (os.environ.get('BANK_ACCOUNT_NAME') or 'CHU TAI KHOAN').strip().strip('"').strip("'")
BANK_CODE = (os.environ.get('BANK_CODE') or 'BIDV').strip().strip('"').strip("'")
BANK_EXCHANGE_RATE = float(os.environ.get('BANK_EXCHANGE_RATE', '26000'))
MIN_DEPOSIT_USDT = float(os.environ.get('MIN_DEPOSIT_USDT', '1.0'))
BANK_AUTO_CHECK = os.environ.get('BANK_AUTO_CHECK', 'true').lower() in ('true', '1', 'yes')

# DEPOSIT PROMOTION / BONUS CONFIGURATION
DEPOSIT_BONUS_ENABLED = os.environ.get('DEPOSIT_BONUS_ENABLED', 'false').lower() in ('true', '1', 'yes')
DEPOSIT_BONUS_TIERS = os.environ.get('DEPOSIT_BONUS_TIERS', '100:2,200:5,300:6,500:7,1000:8').strip().strip('"').strip("'")

# SQLADMIN
SQLADMIN_RAW_PASSWORD = os.environ.get('SQLADMIN_RAW_PASSWORD', 'admin123').strip().strip('"').strip("'")
SQLADMIN_HASHED_PASSWORD = hash_password(SQLADMIN_RAW_PASSWORD)
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '30'))
JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key_123').strip().strip('"').strip("'")

# FACEBOOK CLONE SETTINGS (CHECK LIVE & TU DONG XOA DIE)
FB_FILTER_DUPLICATE_UIDS = os.environ.get('FB_FILTER_DUPLICATE_UIDS', 'true').lower() in ('true', '1', 'yes')
FB_AUTO_CHECK_ON_UPLOAD = os.environ.get('FB_AUTO_CHECK_ON_UPLOAD', 'true').lower() in ('true', '1', 'yes')
FB_AUTO_DELETE_DIE_ON_UPLOAD = os.environ.get('FB_AUTO_DELETE_DIE_ON_UPLOAD', 'true').lower() in ('true', '1', 'yes')
FB_CHECK_LIVE_BEFORE_DELIVERY = os.environ.get('FB_CHECK_LIVE_BEFORE_DELIVERY', 'true').lower() in ('true', '1', 'yes')
FB_AUTO_DELETE_DIE_ON_DELIVERY = os.environ.get('FB_AUTO_DELETE_DIE_ON_DELIVERY', 'true').lower() in ('true', '1', 'yes')
FB_CATEGORY_KEYWORDS = os.environ.get('FB_CATEGORY_KEYWORDS', 'facebook, fb, clone, via, bm').strip()
FB_CRON_CHECK_INTERVAL_MINUTES = int(os.environ.get('FB_CRON_CHECK_INTERVAL_MINUTES', '30'))
FB_CRON_NOTIFY_ADMIN = os.environ.get('FB_CRON_NOTIFY_ADMIN', 'true').lower() in ('true', '1', 'yes')


# CHINH SACH BAO HANH & DIEU KHOAN PHAP LY (VIET NAM)
from services.policy_defaults import DEFAULT_WARRANTY_LEGAL_POLICY, DEFAULT_WARRANTY_SHORT_SUMMARY
WARRANTY_LEGAL_POLICY = (os.environ.get('WARRANTY_LEGAL_POLICY') or '').strip() or DEFAULT_WARRANTY_LEGAL_POLICY
WARRANTY_SHORT_SUMMARY = (os.environ.get('WARRANTY_SHORT_SUMMARY') or '').strip() or DEFAULT_WARRANTY_SHORT_SUMMARY
