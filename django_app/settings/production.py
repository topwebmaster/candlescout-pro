from .base import *  # noqa

DEBUG = False

SECURITY_HSTS_SECONDS           = 31536000
SECURITY_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT             = False  # handled by reverse proxy
SESSION_COOKIE_SECURE           = True
CSRF_COOKIE_SECURE              = True
