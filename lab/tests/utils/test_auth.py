"""Tests unitarios de lab/utils/auth.py (sin base de datos)."""

from unittest import mock

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory
from rest_framework_simplejwt.tokens import AccessToken

from lab.utils.auth import EsLector, HasUnityApiKey, JWTLectorAuthentication

from ..ayudas import lector_sin_base, usuario_django_sin_base


class EsLectorTests(SimpleTestCase):
    def permite(self, usuario):
        return EsLector().has_permission(mock.Mock(user=usuario), view=None)

    def test_docente_y_equipo(self):
        self.assertTrue(self.permite(lector_sin_base('docente')))
        self.assertTrue(self.permite(lector_sin_base('equipo')))

    def test_nadie_mas(self):
        self.assertFalse(self.permite(lector_sin_base('otro')))
        self.assertFalse(self.permite(usuario_django_sin_base()))  # un usuario de Django no sirve
        self.assertFalse(self.permite(AnonymousUser()))


class JWTLectorAuthenticationTests(SimpleTestCase):
    def test_devuelve_el_lector_del_token(self):
        token = AccessToken()
        with mock.patch('lab.servicios.acceso_servicio.lector_del_token', return_value=lector_sin_base()) as buscar:
            self.assertEqual(JWTLectorAuthentication().get_user(token), lector_sin_base())
        buscar.assert_called_once_with(token)

    def test_lector_sin_acceso(self):
        with mock.patch('lab.servicios.acceso_servicio.lector_del_token', return_value=None):
            with self.assertRaises(AuthenticationFailed):
                JWTLectorAuthentication().get_user(AccessToken())


@override_settings(UNITY_API_KEY='llave-correcta')
class HasUnityApiKeyTests(SimpleTestCase):
    def permite(self, **encabezados):
        peticion = APIRequestFactory().post('/api/sessions/ingest/', **encabezados)
        return HasUnityApiKey().has_permission(peticion, view=None)

    def test_llave_correcta(self):
        self.assertTrue(self.permite(HTTP_X_API_KEY='llave-correcta'))

    def test_llave_incorrecta_o_ausente(self):
        self.assertFalse(self.permite(HTTP_X_API_KEY='llave-equivocada'))
        self.assertFalse(self.permite(HTTP_X_API_KEY=''))
        self.assertFalse(self.permite())

    @override_settings(UNITY_API_KEY='')
    def test_sin_llave_configurada_el_envio_queda_desactivado(self):
        self.assertFalse(self.permite(HTTP_X_API_KEY=''))
        self.assertFalse(self.permite(HTTP_X_API_KEY='cualquiera'))
