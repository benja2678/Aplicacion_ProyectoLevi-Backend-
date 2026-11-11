"""Tests unitarios de lab/renderers.py."""

from django.test import SimpleTestCase

from lab.renderers import UTF8JSONRenderer


class UTF8JSONRendererTests(SimpleTestCase):
    def test_declara_utf8_y_escribe_las_tildes_tal_cual(self):
        # Sin charset, PowerShell 5.1 mostraba "SesiÃ³n guardada."
        renderer = UTF8JSONRenderer()
        self.assertEqual(renderer.charset, 'utf-8')
        self.assertEqual(renderer.render({'detail': 'Sesión guardada.'}), '{"detail":"Sesión guardada."}'.encode())
