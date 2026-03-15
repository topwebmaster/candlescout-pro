from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="unsafe-secret-key-change-in-prod")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost", cast=Csv())

FERNET_KEY = config("FERNET_KEY", default="").encode() or None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "django_celery_beat",
    "django_celery_results",
    # Internal apps
    "apps.candles",
    "apps.signals",
    "apps.trading",
    "apps.ml",
    "apps.accounts",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "urls"
AUTH_USER_MODEL = "accounts.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "timescale.db.backends.postgresql",
        "NAME":     config("DB_NAME", default="candlescout"),
        "USER":     config("DB_USER", default="candlescout"),
        "PASSWORD": config("DB_PASSWORD", default="changeme"),
        "HOST":     config("DB_HOST", default="timescaledb"),
        "PORT":     config("DB_PORT", default="5432"),
    }
}

CACHES = {
    "default": {
        "BACKEND":  "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "MAX_ENTRIES":  10000,
            "SOCKET_CONNECT_TIMEOUT": 2,
            "SOCKET_TIMEOUT": 2,
        },
    }
}

# Celery
CELERY_BROKER_URL         = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_RESULT_BACKEND     = config("REDIS_URL", default="redis://redis:6379/0")
CELERY_BEAT_SCHEDULER     = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_SERIALIZER    = "json"
CELERY_RESULT_SERIALIZER  = "json"
CELERY_ACCEPT_CONTENT     = ["json"]
CELERY_TIMEZONE           = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ROUTES = {
    "apps.ml.tasks.*":        {"queue": "ml"},
    "apps.trading.tasks.*":   {"queue": "default"},
    "apps.signals.tasks.*":   {"queue": "default"},
}

LANGUAGE_CODE = "en-us"
TIME_ZONE     = "UTC"
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
