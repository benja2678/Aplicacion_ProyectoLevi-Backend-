"""Comandos que se ejecutan al arrancar el contenedor (entrypoint.sh)."""

import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import TestCase

WAIT = 'lab.management.commands.wait_for_db'


class WaitForDbTests(TestCase):
    def test_base_lista(self):
        out = StringIO()
        call_command('wait_for_db', '--timeout', '1', stdout=out)
        self.assertIn('Base de datos lista', out.getvalue())

    def test_reintenta_hasta_que_responde(self):
        with mock.patch(f'{WAIT}.connections') as conns, mock.patch(f'{WAIT}.time.sleep') as sleep:
            conns.__getitem__.return_value.ensure_connection.side_effect = [
                OperationalError('todavía no'), OperationalError('todavía no'), None,
            ]
            call_command('wait_for_db', stdout=StringIO())
        self.assertEqual(sleep.call_count, 2)

    def test_se_rinde_al_vencer_el_plazo(self):
        with mock.patch(f'{WAIT}.connections') as conns, mock.patch(f'{WAIT}.time.sleep'):
            conns.__getitem__.return_value.ensure_connection.side_effect = OperationalError('apagada')
            with self.assertRaises(CommandError):
                call_command('wait_for_db', '--timeout', '0', stdout=StringIO())


class EnsureTeacherTests(TestCase):
    PASSWORD = 'clave-larga-de-prueba-123'

    def run_command(self, **env):
        with mock.patch.dict(os.environ, env):
            call_command('ensure_teacher', stdout=StringIO())

    def test_crea_la_cuenta_del_profesor(self):
        self.run_command(TEACHER_USERNAME='profe', TEACHER_PASSWORD=self.PASSWORD, TEACHER_EMAIL='')
        user = get_user_model().objects.get(username='profe')
        self.assertTrue(user.is_staff and user.is_active)
        self.assertTrue(user.check_password(self.PASSWORD))

    def test_si_ya_existe_no_cambia_la_clave(self):
        get_user_model().objects.create_superuser('profe', '', self.PASSWORD)
        self.run_command(TEACHER_USERNAME='profe', TEACHER_PASSWORD='otra-clave-larga-456', TEACHER_EMAIL='')
        self.assertTrue(get_user_model().objects.get(username='profe').check_password(self.PASSWORD))

    def test_clave_debil_no_crea_nada(self):
        with self.assertRaises(CommandError):
            self.run_command(TEACHER_USERNAME='profe', TEACHER_PASSWORD='12345', TEACHER_EMAIL='')
        self.assertFalse(get_user_model().objects.exists())

    def test_sin_variables_no_crea_nada(self):
        self.run_command(TEACHER_USERNAME='', TEACHER_PASSWORD='')
        self.assertFalse(get_user_model().objects.exists())
