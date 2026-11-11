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

# Intentos de login permitidos por IP (ver lab/utils/limite_login.py). Ej: 5/min, 20/h.
LOGIN_RATE = env('LOGIN_RATE', '5/min')

# Llave fija que usa Unity (Meta Quest) para ENVIAR sesiones. Solo sirve para eso.
# Si está vacía, el envío desde Unity queda desactivado.
UNITY_API_KEY = env('UNITY_API_KEY')

# El servidor web de delante avisa con este encabezado si la conexión original era https.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'


# ------------------------------------------------------------------ #
# Aplicaciones

# El backend NO crea tablas: todas están en levi-db-scripts (no se usa `migrate`).
# auth y contenttypes quedan instaladas solo porque las piden las librerías
# (cifrado de claves y tokens JWT); sus tablas no existen ni se usan.
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'lab',  # API del laboratorio: controladores, servicios, DAO y DTO
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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
# Tamaño máximo de las peticiones.
# Un JSON de sesión puede ser grande (muchos eventos) y "Cargar sesiones" puede
# subir varios archivos juntos. Debe coincidir con el límite del servidor web de delante.

MAX_UPLOAD_MB = env_int('MAX_UPLOAD_MB', 50)
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE


# ------------------------------------------------------------------ #
# API (Django REST Framework) y tokens JWT

REST_FRAMEWORK = {
    # Por defecto, TODA la API exige el token JWT de un lector (tabla `lector` de la
    # base: docente o equipo). Las excepciones (health, login, refresh, logout y el
    # envío de Unity) lo indican en su controlador. Ver lab/utils/auth.py.
    'DEFAULT_AUTHENTICATION_CLASSES': ['lab.utils.auth.JWTLectorAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['lab.utils.auth.EsLector'],
    'DEFAULT_RENDERER_CLASSES': ['lab.utils.renderers.UTF8JSONRenderer'],  # JSON con charset=utf-8
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    # Los errores del negocio (lab/utils/errores.py) se responden como 400 / 401 / 404.
    'EXCEPTION_HANDLER': 'lab.controladores.errores.manejar_errores',
    # Cuántos proxies hay delante de Django (1 = el servidor web). Sirve para saber la IP
    # real del cliente al limitar los intentos de login. En tu PC (sin proxy) es 0.
    'NUM_PROXIES': env_int('NUM_PROXIES', 0),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env_int('JWT_ACCESS_MINUTES', 30)),
    'REFRESH_TOKEN_LIFETIME': timedelta(hours=env_int('JWT_REFRESH_HOURS', 8)),
    'ROTATE_REFRESH_TOKENS': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    # Los tokens los crea lab/servicios/acceso_servicio.py con el correo del lector;
    # no se usan los usuarios de Django.
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
