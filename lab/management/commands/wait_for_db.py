"""
Espera a que la base de datos acepte conexiones.

Uso:  python manage.py wait_for_db --timeout 60
Lo usa entrypoint.sh al arrancar el contenedor: PostgreSQL tarda unos segundos en
estar listo y, si Django intentara migrar antes, el contenedor se caería.
"""

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = 'Espera a que la base de datos acepte conexiones (por defecto, hasta 60 segundos).'

    def add_arguments(self, parser):
        parser.add_argument('--timeout', type=int, default=60, help='segundos máximos de espera')

    def handle(self, *args, **options):
        timeout = options['timeout']
        deadline = time.monotonic() + timeout
        connection = connections['default']

        while True:
            try:
                connection.ensure_connection()
                break
            except OperationalError as exc:
                if time.monotonic() >= deadline:
                    raise CommandError(f'La base de datos no respondió en {timeout} segundos: {exc}') from exc
                self.stdout.write('La base de datos todavía no está lista; reintentando en 2 segundos...')
                time.sleep(2)

        self.stdout.write(self.style.SUCCESS('Base de datos lista.'))
