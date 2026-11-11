"""Tests unitarios de lab/auth.py (sin base de datos)."""

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from lab.auth import HasUnityApiKey, teacher_can_login

from .utils import profesor_sin_base


class TeacherCanLoginTests(SimpleTestCase):
    def test_solo_cuentas_activas_de_profesor(self):
        profesor = profesor_sin_base()
        self.assertTrue(teacher_can_login(profesor))
        profesor.is_active = False
        self.assertFalse(teacher_can_login(profesor))
        otro = profesor_sin_base()
        otro.is_staff = False
        self.assertFalse(teacher_can_login(otro))
        self.assertFalse(teacher_can_login(None))


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
