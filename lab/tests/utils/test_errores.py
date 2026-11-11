"""Tests unitarios de lab/utils/errores.py."""

from django.test import SimpleTestCase

from lab.utils.errores import DatosInvalidos, NoEncontrado


class ErroresTests(SimpleTestCase):
    def test_como_respuesta(self):
        self.assertEqual(DatosInvalidos('Mensaje').como_respuesta(), {'detail': 'Mensaje'})
        self.assertEqual(DatosInvalidos(campos={'a': ['Uno.']}).como_respuesta(), {'a': ['Uno.']})

    def test_texto_del_error(self):
        self.assertEqual(str(DatosInvalidos('Mensaje')), 'Mensaje')
        self.assertEqual(str(DatosInvalidos(campos={'a': ['Uno.'], 'b': ['Dos.']})), 'Uno. Dos.')
        self.assertEqual(str(NoEncontrado()), 'No encontrado.')
