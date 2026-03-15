from .base import *  # noqa

DEBUG = True

INSTALLED_APPS += ["django_extensions"]  # noqa

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
