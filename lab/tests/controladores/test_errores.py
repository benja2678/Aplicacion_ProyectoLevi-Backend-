"""Tests unitarios de lab/controladores/errores.py."""

from django.test import SimpleTestCase
from rest_framework.exceptions import NotAuthenticated

from lab.controladores.errores import manejar_errores
from lab.utils.errores import DatosInvalidos, NoEncontrado


class ManejarErroresTests(SimpleTestCase):
    def test_datos_invalidos_con_mensaje_general_400(self):
        r = manejar_errores(DatosInvalidos('Algo está mal'), {})
        self.assertEqual((r.status_code, r.data), (400, {'detail': 'Algo está mal'}))

    def test_datos_invalidos_por_campo_400(self):
        r = manejar_errores(DatosInvalidos(campos={'nombre': ['Escribe el nombre del alumno.']}), {})
        self.assertEqual((r.status_code, r.data), (400, {'nombre': ['Escribe el nombre del alumno.']}))

    def test_no_encontrado_404(self):
        r = manejar_errores(NoEncontrado(), {})
        self.assertEqual((r.status_code, r.data), (404, {'detail': 'No encontrado.'}))

    def test_lo_demas_lo_responde_drf(self):
        self.assertEqual(manejar_errores(NotAuthenticated(), {}).status_code, 401)
        self.assertIsNone(manejar_errores(ValueError('error del programa'), {}))  # -> 500

