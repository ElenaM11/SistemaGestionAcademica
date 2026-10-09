"""Ajusto la configuración para ejecutar pruebas aisladas en SQLite."""

from .settings import *


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

SECRET_KEY = 'clave-de-prueba-no-usar-en-produccion'
