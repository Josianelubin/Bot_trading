import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("KPS_DEBUG", True)

SECRET_KEY = os.environ.get("KPS_SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-key"
    else:
        raise RuntimeError("KPS_SECRET_KEY est obligatoire hors mode DEBUG.")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("KPS_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
CSRF_TRUSTED_ORIGINS = [f"https://{_render_host}"] if _render_host else []
CSRF_TRUSTED_ORIGINS += [o.strip() for o in os.environ.get("KPS_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.accounts",
    "apps.dashboard",
    "apps.market_scanner",
    "apps.market_data",
    "apps.technical_analysis",
    "apps.smart_money",
    "apps.fundamental_analysis",
    "apps.sentiment_analysis",
    "apps.ai_engine",
    "apps.decision_engine",
    "apps.trading",
    "apps.risk_management",
    "apps.trade_approval",
    "apps.trade_history",
    "apps.notifications",
    "apps.audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.dashboard.context_processors.kps_mode",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Base de donnees : DATABASE_URL choisit SQLite (local) ou PostgreSQL (Render) :
#   sqlite:///db.sqlite3
#   postgres://utilisateur:motdepasse@hote:5432/nombase   (KPS_DB_SSL=true si connexion externe)
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600,
        ssl_require=env_bool("KPS_DB_SSL", False),
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# --- Securite ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]

# --- KPS : mode de trading ---
TRADING_MODE = os.environ.get("KPS_TRADING_MODE", "DEMO").upper()
ALLOW_LIVE = env_bool("KPS_ALLOW_LIVE", False)
# Le REEL n'est jamais actif sans autorisation explicite.
if TRADING_MODE not in ("DEMO", "REAL") or (TRADING_MODE == "REAL" and not ALLOW_LIVE):
    TRADING_MODE = "DEMO"
MARGIN_MODE = "ISOLATED"  # constante : jamais modifiable

# --- Telegram (optionnel) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Liste de depart : le scanner (Phase 3) la verifie sur Gate.io
# et remplace tout contrat suspendu ou trop peu liquide.
DEFAULT_WATCHLIST = [
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX", "LINK", "LTC",
    "DOT", "TRX", "BCH", "SUI", "APT", "NEAR", "TON", "UNI", "OP", "ARB",
]

# --- Bot : parametres (tous modifiables par variables d'environnement) ---
def _num(name, default, cast=float):
    try:
        return cast(os.environ.get(name, default))
    except ValueError:
        return cast(default)


KPS_MIN_TECH_SCORE = _num("KPS_MIN_TECH_SCORE", 24, int)          # sur 40
KPS_REWARD_RISK = _num("KPS_REWARD_RISK", 2.0)
KPS_DEFAULT_LEVERAGE = _num("KPS_DEFAULT_LEVERAGE", 5, int)
KPS_MAX_LEVERAGE = _num("KPS_MAX_LEVERAGE", 10, int)
KPS_DEFAULT_CAPITAL_USDT = _num("KPS_DEFAULT_CAPITAL_USDT", 20.0)
KPS_DEMO_EQUITY_USDT = _num("KPS_DEMO_EQUITY_USDT", 1000.0)
KPS_PROPOSAL_TTL_MINUTES = _num("KPS_PROPOSAL_TTL_MINUTES", 30, int)
KPS_SCAN_INTERVAL_SECONDS = _num("KPS_SCAN_INTERVAL_SECONDS", 900, int)
KPS_RISK_PER_TRADE_PCT = _num("KPS_RISK_PER_TRADE_PCT", 1.0)
KPS_MAX_DAILY_LOSS_PCT = _num("KPS_MAX_DAILY_LOSS_PCT", 3.0)

# --- Gate.io (cles uniquement via variables d'environnement) ---
GATEIO_API_KEY = os.environ.get("GATEIO_API_KEY", "")
GATEIO_API_SECRET = os.environ.get("GATEIO_API_SECRET", "")
GATEIO_TESTNET_API_KEY = os.environ.get("GATEIO_TESTNET_API_KEY", "")
GATEIO_TESTNET_API_SECRET = os.environ.get("GATEIO_TESTNET_API_SECRET", "")
# A VERIFIER dans la documentation officielle Gate.io avant usage :
GATEIO_TESTNET_BASE_URL = os.environ.get("GATEIO_TESTNET_BASE_URL", "https://fx-api-testnet.gateio.ws/api/v4")
KPS_MAX_SLIPPAGE_PCT = _num("KPS_MAX_SLIPPAGE_PCT", 0.5)
KPS_PUBLIC_URL = os.environ.get("KPS_PUBLIC_URL", "").rstrip("/")

# --- Actualites, or, rapports ---
KPS_EXTRA_SYMBOLS = [x.strip() for x in os.environ.get("KPS_EXTRA_SYMBOLS", "XAUT_USDT").split(",") if x.strip()]
KPS_REQUIRE_NEWS = env_bool("KPS_REQUIRE_NEWS", True)
KPS_NEWS_MAX_AGE_HOURS = _num("KPS_NEWS_MAX_AGE_HOURS", 48, int)
KPS_NEWS_PER_CYCLE = _num("KPS_NEWS_PER_CYCLE", 10, int)
KPS_REPORT_ALL_CHARTS = env_bool("KPS_REPORT_ALL_CHARTS", False)
CRYPTOPANIC_API_KEY = os.environ.get("CRYPTOPANIC_API_KEY", "")
CRYPTOPANIC_PLAN = os.environ.get("CRYPTOPANIC_PLAN", "developer")

# --- NewsAPI (plan gratuit : limite quotidienne, usage developpement) ---
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
KPS_NEWSAPI_DAILY_LIMIT = _num("KPS_NEWSAPI_DAILY_LIMIT", 90, int)
KPS_NEWSAPI_REFRESH_MINUTES = _num("KPS_NEWSAPI_REFRESH_MINUTES", 360, int)

# --- NewsData.io (gratuit, remplace CryptoPanic) ---
NEWSDATA_API_KEY = os.environ.get("NEWSDATA_API_KEY", "")
KPS_NEWSDATA_DAILY_LIMIT = _num("KPS_NEWSDATA_DAILY_LIMIT", 150, int)
KPS_NEWSDATA_REFRESH_MINUTES = _num("KPS_NEWSDATA_REFRESH_MINUTES", 240, int)
