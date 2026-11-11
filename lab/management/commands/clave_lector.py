"""
Pone o cambia la contraseña de un lector (tabla `lector`) para que pueda entrar al
panel web. La contraseña se pide por teclado (no se ve al escribirla) y se guarda
cifrada.

    python manage.py clave_lector docente@uta.cl
    python manage.py clave_lector nuevo@uta.cl --nombre "Ana Pérez" --rol equipo   # si no estaba

En el servidor con Docker (desde proyecto-backend/deploy):
    docker compose exec backend python manage.py clave_lector docente@uta.cl
"""

from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from lab.dto.lector import ROLES_CON_ACCESO
from lab.servicios import acceso_servicio
from lab.utils.errores import DatosInvalidos


class Command(BaseCommand):
    help = 'Pone o cambia la contraseña de un lector (docente o equipo) para entrar al panel web.'

    def add_arguments(self, parser):
        parser.add_argument('correo', help='correo del lector (tabla lector)')
        parser.add_argument('--nombre', help='solo si el correo no está en la tabla: lo agrega con este nombre')
        parser.add_argument('--rol', choices=ROLES_CON_ACCESO, default='docente',
                            help='solo al agregarlo (por defecto: docente)')

    def handle(self, *args, **opciones):
        clave = getpass('Contraseña nueva: ')
        if clave != getpass('Repite la contraseña: '):
            raise CommandError('Las contraseñas no coinciden. No se cambió nada.')
        try:
            lector = acceso_servicio.asignar_clave(opciones['correo'], clave, opciones['nombre'], opciones['rol'])
        except DatosInvalidos as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(self.style.SUCCESS(
            f'Listo: {lector.nombre} <{lector.correo}> ({lector.rol}) ya puede entrar al panel.'))
