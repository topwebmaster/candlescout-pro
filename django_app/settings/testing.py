from .base import *  # noqa

DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     "test_candlescout",
        "USER":     "postgres",
        "PASSWORD": "postgres",
        "HOST":     "localhost",
        "PORT":     "5432",
        "TEST":     {"NAME": "test_candlescout"},
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
