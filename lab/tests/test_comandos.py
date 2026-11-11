"""Tests unitarios del comando wait_for_db (lo ejecuta entrypoint.sh al arrancar).
La conexión a la base se simula: no usa base de datos."""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import SimpleTestCase

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

