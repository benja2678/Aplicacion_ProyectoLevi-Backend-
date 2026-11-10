"""Tests del acceso del profesor: login, tokens, límite de intentos y cierre de sesión."""

from django.contrib.auth import get_user_model

from .utils import TEACHER_PASSWORD, BaseApiTest

PROTECTED = [
    ('get', '/api/students/'),
    ('post', '/api/students/'),
    ('get', '/api/sessions/'),
    ('post', '/api/sessions/import/'),
    ('delete', '/api/sessions/A001_T0_2026-11-05T10:31:12/'),
    ('get', '/api/auth/me/'),
]


class LoginTests(BaseApiTest):
    def test_login_correcto_entrega_tokens(self):
        r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': TEACHER_PASSWORD}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertIn('access', r.data)
        self.assertIn('refresh', r.data)

        # Con ese token se puede usar la API.
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {r.data["access"]}')
        self.assertEqual(self.client.get('/api/students/').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').data['username'], 'profesor')

    def test_login_con_clave_incorrecta_rechazado(self):
        r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': 'otra'}, format='json')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data['detail'], 'Usuario o contraseña incorrectos.')

    def test_usuario_que_no_es_profesor_no_puede_entrar(self):
        get_user_model().objects.create_user('alumno', password='Clave-Del-Alumno-2026', is_staff=False)
        r = self.client.post('/api/auth/login/', {'username': 'alumno', 'password': 'Clave-Del-Alumno-2026'}, format='json')
        self.assertEqual(r.status_code, 401)

    def test_limite_de_intentos_de_login(self):
        for _ in range(5):
            r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': 'mal'}, format='json')
            self.assertEqual(r.status_code, 401)
        # El sexto intento dentro del mismo minuto se bloquea, aunque la clave sea correcta.
        r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': TEACHER_PASSWORD}, format='json')
        self.assertEqual(r.status_code, 429)

    def test_refresh_entrega_un_nuevo_access(self):
        r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': TEACHER_PASSWORD}, format='json')
        r2 = self.client.post('/api/auth/refresh/', {'refresh': r.data['refresh']}, format='json')
        self.assertEqual(r2.status_code, 200)
        self.assertIn('access', r2.data)

    def test_logout_invalida_el_refresh(self):
        r = self.client.post('/api/auth/login/', {'username': 'profesor', 'password': TEACHER_PASSWORD}, format='json')
        refresh = r.data['refresh']
        self.assertEqual(self.client.post('/api/auth/logout/', {'refresh': refresh}, format='json').status_code, 200)
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': refresh}, format='json').status_code, 401)


class AccessWithoutTokenTests(BaseApiTest):
    def test_sin_token_todo_rechazado(self):
        for method, url in PROTECTED:
            with self.subTest(method=method, url=url):
                r = getattr(self.client, method)(url, {}, format='json')
                self.assertEqual(r.status_code, 401)

    def test_token_falso_rechazado(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer esto-no-es-un-token')
        self.assertEqual(self.client.get('/api/students/').status_code, 401)

    def test_token_de_usuario_no_profesor_rechazado(self):
        from rest_framework_simplejwt.tokens import RefreshToken

        other = get_user_model().objects.create_user('otro', password='Clave-Del-Otro-2026', is_staff=False)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(other).access_token}')
        self.assertEqual(self.client.get('/api/students/').status_code, 403)

    def test_health_es_publico(self):
        self.assertEqual(self.client.get('/api/health/').status_code, 200)
