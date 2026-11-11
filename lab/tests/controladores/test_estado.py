"""Tests unitarios de lab/controladores/estado.py (health, login, refresh, logout, me).
El servicio de acceso se simula (mock): sin base de datos.
"""

from unittest import mock

from rest_framework.test import APISimpleTestCase

from lab.dto.lector import CredencialesDTO
from lab.utils.errores import NoAutorizado

from ..ayudas import lector_sin_base

SERVICIO = 'lab.controladores.estado.acceso_servicio'
TOKENS = {'access': 'aaa', 'refresh': 'rrr'}


class EstadoTests(APISimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch(SERVICIO).start()
        self.addCleanup(mock.patch.stopall)

    def test_health_es_publico(self):
        r = self.client.get('/api/health/')
        self.assertEqual((r.status_code, r.json()), (200, {'status': 'ok'}))

    def test_quien_soy(self):
        self.client.force_authenticate(user=lector_sin_base())
        self.assertEqual(self.client.get('/api/auth/me/').json(),
                         {'username': 'docente@ejemplo.cl', 'nombre': 'Docente de prueba', 'rol': 'docente'})

    def test_quien_soy_sin_token_o_con_token_falso(self):
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer esto-no-es-un-token')
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_token_valido_de_un_lector_que_ya_no_tiene_acceso(self):
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken()
        token['lector'] = 'docente@ejemplo.cl'
        with mock.patch('lab.servicios.acceso_servicio.lector_del_token', return_value=None):
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            r = self.client.get('/api/auth/me/')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json()['detail'], 'Tu acceso ya no es válido. Vuelve a iniciar sesión.')


class SesionTests(APISimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch(SERVICIO).start()
        self.addCleanup(mock.patch.stopall)
        # El login tiene límite de intentos (usa la caché de la base): aquí se desactiva.
        mock.patch('lab.controladores.estado.LoginControlador.throttle_classes', []).start()

    def test_login_correcto(self):
        self.servicio.iniciar_sesion.return_value = TOKENS
        r = self.client.post('/api/auth/login/', {'username': 'Docente@ejemplo.cl', 'password': 'x'}, format='json')
        self.assertEqual((r.status_code, r.json()), (200, TOKENS))
        self.servicio.iniciar_sesion.assert_called_once_with(CredencialesDTO('docente@ejemplo.cl', 'x'))

    def test_login_incorrecto_401(self):
        self.servicio.iniciar_sesion.side_effect = NoAutorizado('Correo o contraseña incorrectos.')
        r = self.client.post('/api/auth/login/', {'email': 'a@b.cl', 'password': 'x'}, format='json')
        self.assertEqual((r.status_code, r.json()), (401, {'detail': 'Correo o contraseña incorrectos.'}))

    def test_login_sin_datos_400(self):
        r = self.client.post('/api/auth/login/', {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.servicio.iniciar_sesion.assert_not_called()

    def test_renovar(self):
        self.servicio.renovar.return_value = {'access': 'nuevo'}
        r = self.client.post('/api/auth/refresh/', {'refresh': 'rrr'}, format='json')
        self.assertEqual((r.status_code, r.json()), (200, {'access': 'nuevo'}))
        self.servicio.renovar.assert_called_once_with('rrr')

    def test_renovar_vencido_401(self):
        self.servicio.renovar.side_effect = NoAutorizado('La sesión venció o se cerró. Vuelve a iniciar sesión.')
        self.assertEqual(self.client.post('/api/auth/refresh/', {'refresh': 'x'}, format='json').status_code, 401)

    def test_cerrar_sesion(self):
        r = self.client.post('/api/auth/logout/', {'refresh': 'rrr'}, format='json')
        self.assertEqual((r.status_code, r.json()), (200, {}))
        self.servicio.cerrar_sesion.assert_called_once_with('rrr')


class LimiteDeIntentosTests(APISimpleTestCase):
    def setUp(self):
        servicio = mock.patch(SERVICIO).start()
        self.addCleanup(mock.patch.stopall)
        servicio.iniciar_sesion.side_effect = NoAutorizado('Correo o contraseña incorrectos.')
        # 5 intentos permitidos; el sexto, bloqueado por 42 segundos.
        mock.patch('lab.servicios.acceso_servicio.registrar_intento_login', side_effect=[None] * 5 + [42]).start()

    def test_sexto_intento_del_minuto_bloqueado(self):
        for _ in range(5):
            r = self.client.post('/api/auth/login/', {'email': 'a@b.cl', 'password': 'mal'}, format='json')
            self.assertEqual(r.status_code, 401)
        r = self.client.post('/api/auth/login/', {'email': 'a@b.cl', 'password': 'mal'}, format='json')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r['Retry-After'], '42')
