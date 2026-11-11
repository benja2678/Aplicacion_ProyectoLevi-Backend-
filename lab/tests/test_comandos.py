"""Tests unitarios de los comandos de lab/management/commands/ (sin base de datos).

- wait_for_db: lo ejecuta entrypoint.sh al arrancar. La conexión se simula.
- clave_lector: pone la contraseña de un lector. El servicio y el teclado se simulan.
"""

from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import OperationalError
from django.test import SimpleTestCase

from lab.dto.lector import LectorDTO
from lab.utils.errores import DatosInvalidos

WAIT = 'lab.management.commands.wait_for_db'
CLAVE = 'lab.management.commands.clave_lector'


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


class ClaveLectorTests(SimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch(f'{CLAVE}.acceso_servicio').start()
        self.teclado = mock.patch(f'{CLAVE}.getpass').start()
        self.addCleanup(mock.patch.stopall)
        self.servicio.asignar_clave.return_value = LectorDTO('docente@uta.cl', 'Docente', 'docente', 'hash')

    def test_pone_la_clave(self):
        self.teclado.side_effect = ['Clave-Larga-2026', 'Clave-Larga-2026']
        salida = StringIO()
        call_command('clave_lector', 'docente@uta.cl', stdout=salida)
        self.servicio.asignar_clave.assert_called_once_with('docente@uta.cl', 'Clave-Larga-2026', None, 'docente')
        self.assertIn('ya puede entrar al panel', salida.getvalue())

    def test_agrega_un_lector_nuevo(self):
        self.teclado.side_effect = ['Clave-Larga-2026', 'Clave-Larga-2026']
        call_command('clave_lector', 'nuevo@uta.cl', '--nombre', 'Ana', '--rol', 'equipo', stdout=StringIO())
        self.servicio.asignar_clave.assert_called_once_with('nuevo@uta.cl', 'Clave-Larga-2026', 'Ana', 'equipo')

    def test_las_claves_no_coinciden(self):
        self.teclado.side_effect = ['Clave-Larga-2026', 'Otra-Clave-2026']
        with self.assertRaises(CommandError):
            call_command('clave_lector', 'docente@uta.cl', stdout=StringIO())
        self.servicio.asignar_clave.assert_not_called()

    def test_error_del_servicio(self):
        self.teclado.side_effect = ['corta', 'corta']
        self.servicio.asignar_clave.side_effect = DatosInvalidos('Esta contraseña es demasiado corta.')
        with self.assertRaises(CommandError) as ctx:
            call_command('clave_lector', 'docente@uta.cl', stdout=StringIO())
        self.assertIn('demasiado corta', str(ctx.exception))
