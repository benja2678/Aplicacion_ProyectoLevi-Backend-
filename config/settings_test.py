"""
Configuración para los tests. `python manage.py test` la usa sola (ver manage.py).

- No lee .env.dev ni .env.prod: los tests no dependen de tus credenciales.
- Nunca se conecta a las bases de dev o prod: la base de prueba la crea el
  ejecutor de tests en Docker (lab/tests/runner.py).
"""

import os

os.environ['ENTORNO'] = 'test'                          # no hay .env.test: no se lee ningún archivo
os.environ['POSTGRES_HOST'] = 'la-define-el-ejecutor-de-tests'
os.environ['SECRET_KEY'] = 'llave-solo-para-los-tests-de-32-caracteres-o-mas'  # firma los tokens

from .settings import *  # noqa: E402,F403

TEST_RUNNER = 'lab.tests.runner.LeviTestRunner'

UNITY_API_KEY = 'llave-de-prueba-unity-123'

# Guardar contraseñas con el método rápido: los tests corren varias veces más rápido.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Los tests provocan a propósito respuestas 400/401/403/404: no se muestran como avisos.
LOGGING['loggers']['django.request'] = {'handlers': ['console'], 'level': 'ERROR', 'propagate': False}  # noqa: F405
