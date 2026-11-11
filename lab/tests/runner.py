"""
Ejecutor de los tests (lo activa config/settings_test.py).

- Los tests que NO usan base de datos (DTO, servicios, controladores, admin…) corren
  solos: no se levanta nada.
- Si algún test usa la base (DAO, login), el ejecutor:
    1. levanta un PostgreSQL 16 NUEVO en Docker (solo en 127.0.0.1, puerto al azar,
       usuario y clave al azar);
    2. Django crea ahí la base de prueba y sus propias tablas (usuarios, tokens…);
    3. carga lab/tests/datos/base_pruebas.sql (tablas del laboratorio + datos de prueba);
    4. corren los tests;
    5. borra el contenedor con todo lo que tenía, aunque algún test falle.

Nunca se conecta a las bases de dev ni de prod. Requiere Docker Desktop encendido.
"""

import secrets
import subprocess
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner

IMAGEN = 'postgres:16'
ARCHIVO_SQL = Path(__file__).resolve().parent / 'datos' / 'base_pruebas.sql'
ESPERA_MAXIMA_S = 90


class PostgresEnDocker:
    """Un PostgreSQL desechable dentro de un contenedor de Docker."""

    def __init__(self):
        self.contenedor = f'levi-tests-{uuid.uuid4().hex[:8]}'
        self.usuario = 'levi'
        self.clave = secrets.token_hex(16)
        self.base = 'levi'
        self.puerto: int | None = None

    def iniciar(self) -> None:
        print(f'[tests] Levantando PostgreSQL en Docker ({self.contenedor})...')
        _docker('run', '-d', '--rm', '--name', self.contenedor,
                '-e', f'POSTGRES_USER={self.usuario}', '-e', f'POSTGRES_PASSWORD={self.clave}',
                '-e', f'POSTGRES_DB={self.base}', '-p', '127.0.0.1::5432', IMAGEN)
        # "127.0.0.1:54321" -> 54321 (el puerto lo elige Docker para no chocar con nada)
        self.puerto = int(_docker('port', self.contenedor, '5432/tcp').splitlines()[0].rsplit(':', 1)[1])

        limite = time.monotonic() + ESPERA_MAXIMA_S
        while time.monotonic() < limite:
            listo = subprocess.run(
                ['docker', 'exec', self.contenedor, 'pg_isready', '-q', '-h', '127.0.0.1', '-U', self.usuario],
                capture_output=True,
            )
            if listo.returncode == 0:
                return
            time.sleep(0.5)
        raise RuntimeError(f'PostgreSQL no respondió en {ESPERA_MAXIMA_S} s.')

    def datos_de_conexion(self) -> dict:
        return {'HOST': '127.0.0.1', 'PORT': str(self.puerto), 'NAME': self.base,
                'USER': self.usuario, 'PASSWORD': self.clave}

    def cargar_sql(self, base: str, archivo: Path) -> None:
        print(f'[tests] Cargando {archivo.name} en la base "{base}"...')
        with archivo.open('rb') as sql:
            resultado = subprocess.run(
                ['docker', 'exec', '-i', self.contenedor, 'psql', '-q', '-v', 'ON_ERROR_STOP=1',
                 '-U', self.usuario, '-d', base],
                stdin=sql, capture_output=True,
            )
        if resultado.returncode != 0:
            raise RuntimeError(f'No se pudo cargar {archivo.name}:\n{resultado.stderr.decode("utf-8", "replace")}')

    def detener(self) -> None:
        subprocess.run(['docker', 'rm', '-f', '-v', self.contenedor], capture_output=True)
        print(f'[tests] Contenedor {self.contenedor} borrado.')


def _docker(*argumentos: str) -> str:
    try:
        resultado = subprocess.run(['docker', *argumentos], capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError('No se encontró el comando "docker". ¿Está instalado Docker Desktop?') from None
    if resultado.returncode != 0:
        raise RuntimeError(
            f'Docker falló ({" ".join(argumentos[:2])}). ¿Está abierto Docker Desktop?\n{resultado.stderr.strip()}'
        )
    return resultado.stdout.strip()


class LeviTestRunner(DiscoverRunner):
    postgres: PostgresEnDocker | None = None

    def setup_databases(self, aliases=None, **kwargs):
        if aliases:  # algún test necesita la base de datos
            self.postgres = PostgresEnDocker()
            self.postgres.iniciar()
            conexion = connections['default']
            conexion.close()
            for datos in (settings.DATABASES['default'], conexion.settings_dict):
                datos.update(self.postgres.datos_de_conexion())
        configuracion = super().setup_databases(aliases=aliases, **kwargs)
        if self.postgres:
            # Django ya creó la base de prueba (test_levi) con sus tablas; se agregan las del laboratorio.
            self.postgres.cargar_sql(connections['default'].settings_dict['NAME'], ARCHIVO_SQL)
        return configuracion

    def run_tests(self, *args, **kwargs):
        try:
            return super().run_tests(*args, **kwargs)
        finally:
            # Se borra SIEMPRE, aunque falle un test o se interrumpa la ejecución.
            if self.postgres:
                self.postgres.detener()
                self.postgres = None
