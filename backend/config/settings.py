"""Django settings for config project."""

from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'

# En desarrollo basta con vacío (DEBUG=True). Para producción: ALLOWED_HOSTS=midominio.com,otro.com en el .env
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rol',
    'usuarios',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'usuarios.middleware.ForzarCambioPasswordMiddleware',   # obliga a cambiar la contraseña inicial
    'django.middleware.common.CommonMiddleware',
    #'django.middleware.csrf.CsrfViewMiddleware', 
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR.parent / 'frontend' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database (PostgreSQL en Azure)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',
            'connect_timeout': 10,
        },
        # Reutiliza la conexión 60 s en lugar de abrir una nueva a Azure en cada petición
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,   # revisa que la conexión siga viva antes de reutilizarla
    }
}

# Sesión: lee de memoria y solo consulta la base cuando hace falta (ahorra viajes a Azure)
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'es'                 # español (mensajes de Django, fechas, formatos)
TIME_ZONE = 'America/La_Paz'         # hora de Bolivia
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR.parent / 'frontend' / 'static',   # CSS
    BASE_DIR.parent / 'frontend' / 'image',    # Imágenes
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Log de consultas SQL: solo si lo activas en el .env con LOG_SQL=True
if os.getenv('LOG_SQL', 'False') == 'True':
    LOGGING = {
        'version': 1,
        'handlers': {'console': {'class': 'logging.StreamHandler'}},
        'loggers': {'django.db.backends': {'handlers': ['console'], 'level': 'DEBUG'}},
    }