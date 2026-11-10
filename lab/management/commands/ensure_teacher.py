"""
Crea la cuenta del profesor a partir de variables de entorno, si todavía no existe.

    TEACHER_USERNAME=profesor
    TEACHER_PASSWORD=una-clave-larga
    TEACHER_EMAIL=opcional@ejemplo.cl

Uso:  python manage.py ensure_teacher
Se ejecuta solo al arrancar el contenedor del backend. Si la cuenta ya existe NO
cambia su contraseña (para eso: python manage.py changepassword <usuario>).
"""

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea la cuenta del profesor (TEACHER_USERNAME / TEACHER_PASSWORD) si aún no existe.'

    def handle(self, *args, **options):
        username = os.environ.get('TEACHER_USERNAME', '').strip()
        password = os.environ.get('TEACHER_PASSWORD', '')
        email = os.environ.get('TEACHER_EMAIL', '').strip()

        if not username or not password:
            self.stdout.write('TEACHER_USERNAME/TEACHER_PASSWORD no están definidos: no se crea ninguna cuenta.')
            return

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            self.stdout.write(f'La cuenta "{username}" ya existe (no se modifica su contraseña).')
            return

        try:
            validate_password(password, User(username=username, email=email))
        except ValidationError as exc:
            raise CommandError('La contraseña de TEACHER_PASSWORD es muy débil: ' + ' '.join(exc.messages))

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f'Cuenta del profesor "{username}" creada.'))
