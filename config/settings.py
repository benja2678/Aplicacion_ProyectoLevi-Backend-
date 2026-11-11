"""
Configuración de Django para el backend del Laboratorio VR.

Todo lo que cambia entre entornos (contraseñas, llaves, base de datos) se lee de
VARIABLES DE ENTORNO. Nada secreto se escribe en este archivo.

Dos entornos, cada uno con su archivo (copias de los .example, NO se suben a git):
- ENTORNO=dev  (por defecto) -> lee `.env.dev`   base de datos de desarrollo
- ENTORNO=prod               -> lee `.env.prod`  base de datos de producción
En Docker no hay archivos .env dentro de la imagen: las variables las entrega
docker-compose y tienen prioridad.

La base de datos es SIEMPRE PostgreSQL, con las tablas de levi-db-scripts.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

ENTORNO = os.environ.get('ENTORNO', 'dev').strip().lower()
if ENTORNO not in ('dev', 'prod', 'test'):  # 'test' lo fija config/settings_test.py
    raise ImproperlyConfigured('ENTORNO debe ser "dev" o "prod".')

# Carga .env.dev o .env.prod si existe. Las variables que ya existen en el sistema
# no se pisan (así funcionan Docker y las pruebas).
ENV_FILE = BASE_DIR / f'.env.{ENTORNO}'
load_dotenv(ENV_FILE)


def env(name: str, default: str = '') -> str:
    return os.environ.get(name, default).strip()


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in ('1', 'true', 'yes', 'si', 'sí', 'on')


def env_list(name: str, default: str = '') -> list[str]:
    return [x.strip() for x in env(name, default).split(',') if x.strip()]


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError as exc:
        raise ImproperlyConfigured(f'La variable {name} debe ser un número entero.') from exc


# ------------------------------------------------------------------ #
# Seguridad básica

DEBUG = env_bool('DEBUG', False)

SECRET_KEY = env('SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Solo para desarrollo: nunca se usa en el servidor porque ahí DEBUG=false.
        SECRET_KEY = 'solo-para-desarrollo-no-usar-en-el-servidor'
    else:
        raise ImproperlyConfigured('Falta la variable de entorno SECRET_KEY.')

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')

# Necesario para el panel /admin/ cuando el sitio se usa con https o con un puerto
# distinto, por ejemplo: CSRF_TRUSTED_ORIGINS=https://mi-dominio.cl
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')

# Llave fija que usa Unity (Meta Quest) para ENVIAR sesiones. Solo sirve para eso.
# Si está vacía, el envío desde Unity queda desactivado.
UNITY_API_KEY = env('UNITY_API_KEY')

# Nginx avisa con este encabezado si la conexión original era https.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Activar solo cuando el servidor tenga https (certificado). Con http debe quedar en false.
if env_bool('HTTPS', False):
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'


# ------------------------------------------------------------------ #
# Aplicaciones

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',  # permite invalidar tokens al cerrar sesión
    'lab',  # API del laboratorio: controladores, servicios, DAO y DTO
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # sirve el CSS/JS del panel /admin/
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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


# ------------------------------------------------------------------ #
# Base de datos

# PostgreSQL con las tablas de levi-db-scripts (las crean esos scripts, no Django).
if not env('POSTGRES_HOST'):
    raise ImproperlyConfigured(
        f'Falta POSTGRES_HOST (dirección de la base de datos). Revisa el archivo {ENV_FILE.name} '
        f'(cópialo desde {ENV_FILE.name}.example si no existe).'
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': env('POSTGRES_HOST'),
        'PORT': env('POSTGRES_PORT', '5432'),
        'NAME': env('POSTGRES_DB', 'laboratorio'),
        'USER': env('POSTGRES_USER', 'laboratorio'),
        'PASSWORD': env('POSTGRES_PASSWORD'),
        # Reutiliza la conexión hasta 60 s, pero antes revisa que siga viva
        # (por ejemplo, si PostgreSQL se reinició).
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}
# Cifrado de la conexión, si el servidor lo pide (disable, require, verify-full…).
if env('POSTGRES_SSLMODE'):
    DATABASES['default']['OPTIONS'] = {'sslmode': env('POSTGRES_SSLMODE')}

# Los tests usan config/settings_test.py y una base propia en Docker (lab/tests/runner.py).

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Caché guardada en la base de datos: la usa el límite de intentos de login,
# así el conteo es el mismo para todos los procesos de gunicorn.
# La tabla se crea sola con `migrate` (ver lab/migrations/0002_cache_table.py).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}


# ------------------------------------------------------------------ #
# Contraseñas

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ------------------------------------------------------------------ #
# Idioma y hora

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = env('TIME_ZONE', 'America/Santiago')
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------------ #
# Archivos estáticos (solo los del panel /admin/; el frontend lo sirve Nginx)

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
if DEBUG:
    STORAGES['staticfiles'] = {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}


# ------------------------------------------------------------------ #
# Tamaño máximo de las peticiones.
# Un JSON de sesión puede ser grande (muchos eventos) y "Cargar sesiones" puede
# subir varios archivos juntos. Debe coincidir con client_max_body_size de Nginx.

MAX_UPLOAD_MB = env_int('MAX_UPLOAD_MB', 50)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE


# ------------------------------------------------------------------ #
# API (Django REST Framework) y tokens JWT

REST_FRAMEWORK = {
    # Por defecto, TODA la API exige un token JWT de un usuario "staff" (el profesor).
    # Las únicas excepciones (login y envío de Unity) lo indican en su vista.
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAdminUser'],
    'DEFAULT_RENDERER_CLASSES': ['lab.renderers.UTF8JSONRenderer'],  # JSON con charset=utf-8
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    # Los errores del negocio (lab/errores.py) se responden como 400 / 404.
    'EXCEPTION_HANDLER': 'lab.controladores.errores.manejar_errores',
    # Límite de intentos de login por dirección IP.
    'DEFAULT_THROTTLE_RATES': {'login': env('LOGIN_RATE', '5/min')},
    # Cuántos proxies hay delante de Django (1 = Nginx). Sirve para saber la IP real
    # del cliente al limitar los intentos de login. En tu PC (sin Nginx) es 0.
    'NUM_PROXIES': env_int('NUM_PROXIES', 0),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env_int('JWT_ACCESS_MINUTES', 30)),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=env_int('JWT_REFRESH_HOURS', 8)),
    'ROTATE_REFRESH_TOKENS': False,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    # Solo cuentas activas de tipo staff (el profesor) reciben tokens.
    'USER_AUTHENTICATION_RULE': 'lab.auth.teacher_can_login',
}


# ------------------------------------------------------------------ #
# Registros (logs): todo a la consola, para verlo con `docker compose logs backend`.

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '[{levelname}] {name}: {message}', 'style': '{'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', 'INFO'), 'propagate': False},
    },
}
