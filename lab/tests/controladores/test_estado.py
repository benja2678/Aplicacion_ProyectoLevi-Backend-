"""Tests de lab/controladores/estado.py (health, login, refresh, logout, me).

- Health y "quién soy": unitarios, sin base de datos.
- Login, refresh y logout: usan la base de prueba en Docker, porque los usuarios, los
  tokens invalidados y el contador de intentos se guardan en tablas de Django.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APISimpleTestCase, APITestCase

from ..ayudas import profesor_sin_base

CLAVE = 'Clave-Del-Profesor-2026'


class EstadoSinBaseTests(APISimpleTestCase):
    def test_health_es_publico(self):
        r = self.client.get('/api/health/')
        self.assertEqual((r.status_code, r.json()), (200, {'status': 'ok'}))

    def test_quien_soy(self):
        self.client.force_authenticate(user=profesor_sin_base())
        self.assertEqual(self.client.get('/api/auth/me/').json(), {'username': 'profesor', 'nombre': 'Ana Pérez'})

    def test_quien_soy_sin_token(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_token_falso(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer esto-no-es-un-token')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)


class LoginTests(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia el contador de intentos de login
        get_user_model().objects.create_user('profesor', password=CLAVE, is_staff=True)

    def login(self, usuario='profesor', clave=CLAVE):
        return self.client.post('/api/auth/login/', {'username': usuario, 'password': clave}, format='json')

    def test_login_correcto_entrega_tokens_que_sirven(self):
        r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {'access', 'refresh'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {r.data["access"]}')
        self.assertEqual(self.client.get('/api/auth/me/').data['username'], 'profesor')

    def test_clave_incorrecta(self):
        r = self.login(clave='otra')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['detail'], 'Usuario o contraseña incorrectos.')

    def test_usuario_que_no_es_profesor_no_puede_entrar(self):
        get_user_model().objects.create_user('alumno', password='Clave-Del-Alumno-2026', is_staff=False)
        self.assertEqual(self.login('alumno', 'Clave-Del-Alumno-2026').status_code, 401)

    def test_limite_de_intentos(self):
        for _ in range(5):
            self.assertEqual(self.login(clave='mal').status_code, 401)
        # El sexto intento del mismo minuto se bloquea, aunque la clave sea correcta.
        self.assertEqual(self.login().status_code, 429)

    def test_refresh_entrega_un_access_nuevo(self):
        r = self.client.post('/api/auth/refresh/', {'refresh': self.login().data['refresh']}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)

    def test_logout_invalida_el_refresh(self):
        refresh = self.login().data['refresh']
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': refresh}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': refresh}, format='json').status_code, 401)
