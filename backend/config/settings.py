from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = True

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if h.strip()
]


# Application definition

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rol',
    'usuarios',

    'rest_framework',
    'cursos',
    'actividades',
    'asistencia',
    'materiales',
    'notificaciones',
    'comunicacion',
    'asistente_ia',   
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'usuarios.middleware.ForzarCambioPasswordMiddleware',  
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware', #
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}

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
                'notificaciones.context_processors.no_leidas',
            ],
        },
    },
]

#WSGI_APPLICATION = 'config.wsgi.application'


# Database (PostgreSQL en Azure; requiere SSL)

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
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,   
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'es'                 # español (mensajes de Django, fechas, formatos)
TIME_ZONE = 'America/La_Paz'         # hora de Bolivia
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = 'static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR.parent / 'media'

STATICFILES_DIRS = [
    path for path in (
        BASE_DIR.parent / 'frontend' / 'static',
        BASE_DIR.parent / 'frontend' / 'image',
    ) if path.exists()
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

# livekit
LIVEKIT_URL = os.getenv('LIVEKIT_URL', '')
LIVEKIT_API_KEY = os.getenv('LIVEKIT_API_KEY', '')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', '')

ASGI_APPLICATION = 'config.asgi.application'

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
ASISTENTE_IA_MAX_INTENTOS = 3
ASISTENTE_IA_GUARDAR = False   # ver punto 6

# Configuración de Google Apps Script 
GOOGLE_SCRIPT_URL = os.getenv('GOOGLE_SCRIPT_URL', '')
GOOGLE_SCRIPT_SECRET = os.getenv('GOOGLE_SCRIPT_SECRET', '')