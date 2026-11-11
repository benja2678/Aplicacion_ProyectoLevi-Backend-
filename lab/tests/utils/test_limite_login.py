"""Tests unitarios de lab/utils/limite_login.py (el servicio se simula)."""

from unittest import mock

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from lab.utils.limite_login import LimiteLogin

REGISTRAR = 'lab.servicios.acceso_servicio.registrar_intento_login'


class LimiteLoginTests(SimpleTestCase):
    def peticion(self):
        return APIRequestFactory().post('/api/auth/login/', REMOTE_ADDR='10.0.0.7')

    def test_permite_mientras_el_servicio_lo_permite(self):
        limite = LimiteLogin()
        with mock.patch(REGISTRAR, return_value=None) as registrar:
            self.assertTrue(limite.allow_request(self.peticion(), view=None))
        registrar.assert_called_once_with('10.0.0.7')
        self.assertIsNone(limite.wait())

    def test_bloquea_y_dice_cuanto_esperar(self):
        limite = LimiteLogin()
        with mock.patch(REGISTRAR, return_value=42):
            self.assertFalse(limite.allow_request(self.peticion(), view=None))
        self.assertEqual(limite.wait(), 42)
