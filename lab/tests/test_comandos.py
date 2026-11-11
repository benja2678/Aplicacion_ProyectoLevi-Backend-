"""Tests de los comandos que se ejecutan al arrancar el contenedor (entrypoint.sh).

- wait_for_db: unitario, la conexión se simula.
- ensure_teacher: usa la base de prueba en Docker (crea un usuario de Django).
"""

import os
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase

WAIT = 'lab.management.commands.wait_for_db'


class WaitForDbTests(SimpleTestCase):
    def esperar(self, respuestas, *argumentos):
        salida = StringIO()
        with mock.patch(f'{WAIT}.connections') as conexiones, mock.patch(f'{WAIT}.time.sleep') as dormir:
            conexiones.__getitem__.return_value.ensure_connection.side_effect = respuestas
            call_command('wait_for_db', *argumentos, stdout=salida)
        return salida.getvalue(), dormir.call_count

    def test_base_lista(self):
        salida, esperas = self.esperar([None])
        self.assertIn('Base de datos lista', salida)
        self.assertEqual(esperas, 0)

    def test_reintenta_hasta_que_responde(self):
        _, esperas = self.esperar([OperationalError('todavía no'), OperationalError('todavía no'), None])
        self.assertEqual(esperas, 2)

    def test_se_rinde_al_vencer_el_plazo(self):
        with self.assertRaises(CommandError):
            self.esperar(OperationalError('apagada'), '--timeout', '0')


class EnsureTeacherTests(TestCase):
    CLAVE = 'clave-larga-de-prueba-123'

    def ejecutar(self, **variables):
        with mock.patch.dict(os.environ, variables):
            call_command('ensure_teacher', stdout=StringIO())

    def test_crea_la_cuenta_del_profesor(self):
        self.ejecutar(TEACHER_USERNAME='profe', TEACHER_PASSWORD=self.CLAVE, TEACHER_EMAIL='')
        usuario = get_user_model().objects.get(username='profe')
        self.assertTrue(usuario.is_staff and usuario.is_active and usuario.is_superuser)
        self.assertTrue(usuario.check_password(self.CLAVE))

    def test_si_ya_existe_no_cambia_la_clave(self):
        get_user_model().objects.create_superuser('profe', '', self.CLAVE)
        self.ejecutar(TEACHER_USERNAME='profe', TEACHER_PASSWORD='otra-clave-larga-456', TEACHER_EMAIL='')
        self.assertTrue(get_user_model().objects.get(username='profe').check_password(self.CLAVE))

    def test_clave_debil_no_crea_nada(self):
        with self.assertRaises(CommandError):
            self.ejecutar(TEACHER_USERNAME='profe', TEACHER_PASSWORD='12345', TEACHER_EMAIL='')
        self.assertFalse(get_user_model().objects.exists())

    def test_sin_variables_no_crea_nada(self):
        self.ejecutar(TEACHER_USERNAME='', TEACHER_PASSWORD='')
        self.assertFalse(get_user_model().objects.exists())
