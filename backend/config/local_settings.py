"""Configuro una base SQLite local para probar sin conectarme a Azure."""

from .settings import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'local.sqlite3',
    }
}

DEBUG = True
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
