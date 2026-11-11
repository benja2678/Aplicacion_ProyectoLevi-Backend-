"""Tests unitarios de lab/servicios/acceso_servicio.py.

Los DAO (lector, token, intento_login) se simulan con mocks: sin base de datos.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.hashers import make_password
from django.test import SimpleTestCase, override_settings
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from lab.dto.lector import CredencialesDTO, LectorAutenticado
from lab.servicios import acceso_servicio
from lab.utils.errores import DatosInvalidos, NoAutorizado

CLAVE = 'Clave-Del-Docente-2026'
MODULO = 'lab.servicios.acceso_servicio'


class BaseAccesoTest(SimpleTestCase):
    def setUp(self):
        self.dao = mock.patch(f'{MODULO}.lector_dao').start()
        self.tokens = mock.patch(f'{MODULO}.token_dao').start()
        self.intentos = mock.patch(f'{MODULO}.intento_login_dao').start()
        self.addCleanup(mock.patch.stopall)
        self.lectores = {
            'docente@uta.cl': {'email': 'docente@uta.cl', 'nombre': 'Docente', 'rol': 'docente',
                               'clave': make_password(CLAVE)},
            'sinclave@uta.cl': {'email': 'sinclave@uta.cl', 'nombre': 'Sin clave', 'rol': 'equipo', 'clave': None},
        }
        self.dao.obtener.side_effect = lambda correo: self.lectores.get(correo.lower())
        # Tabla token_revocado simulada.
        self.revocados = set()
        self.tokens.revocar.side_effect = lambda jti, expira: self.revocados.add(jti)
        self.tokens.esta_revocado.side_effect = lambda jti: jti in self.revocados

    def entrar(self, correo='docente@uta.cl', clave=CLAVE):
        return acceso_servicio.iniciar_sesion(CredencialesDTO(correo=correo, clave=clave))


class IniciarSesionTests(BaseAccesoTest):
    def test_entrega_tokens_con_el_correo_del_lector(self):
        tokens = self.entrar()
        self.assertEqual(set(tokens), {'access', 'refresh'})
        self.assertEqual(AccessToken(tokens['access'])['lector'], 'docente@uta.cl')
        self.assertEqual(RefreshToken(tokens['refresh'])['lector'], 'docente@uta.cl')

    def test_mismo_mensaje_para_cualquier_error(self):
        for correo, clave in [('docente@uta.cl', 'otra-clave'), ('nadie@uta.cl', CLAVE), ('sinclave@uta.cl', '')]:
            with self.subTest(correo), self.assertRaises(NoAutorizado) as ctx:
                self.entrar(correo, clave)
            self.assertEqual(str(ctx.exception), 'Correo o contraseña incorrectos.')

    def test_rol_sin_acceso(self):
        self.lectores['docente@uta.cl']['rol'] = 'otro'
        with self.assertRaises(NoAutorizado):
            self.entrar()


class TokensTests(BaseAccesoTest):
    def test_lector_del_token(self):
        access = AccessToken(self.entrar()['access'])
        self.assertEqual(acceso_servicio.lector_del_token(access),
                         LectorAutenticado(correo='docente@uta.cl', nombre='Docente', rol='docente'))

    def test_quitar_la_fila_o_la_clave_corta_el_acceso_de_inmediato(self):
        access = AccessToken(self.entrar()['access'])
        self.lectores['docente@uta.cl']['clave'] = None
        self.assertIsNone(acceso_servicio.lector_del_token(access))
        del self.lectores['docente@uta.cl']
        self.assertIsNone(acceso_servicio.lector_del_token(access))

    def test_token_sin_lector(self):
        self.assertIsNone(acceso_servicio.lector_del_token(AccessToken()))

    def test_renovar(self):
        nuevo = acceso_servicio.renovar(self.entrar()['refresh'])
        self.assertEqual(AccessToken(nuevo['access'])['lector'], 'docente@uta.cl')

    def test_renovar_sin_acceso_o_con_token_malo(self):
        refresh = self.entrar()['refresh']
        with self.assertRaises(DatosInvalidos):
            acceso_servicio.renovar(None)
        with self.assertRaises(NoAutorizado):
            acceso_servicio.renovar('esto-no-es-un-token')
        with self.assertRaises(NoAutorizado):
            acceso_servicio.renovar(self.entrar()['access'])  # un access no sirve como refresh
        self.lectores['docente@uta.cl']['clave'] = None
        with self.assertRaises(NoAutorizado):
            acceso_servicio.renovar(refresh)

    def test_cerrar_sesion_revoca_el_refresh(self):
        refresh = self.entrar()['refresh']
        acceso_servicio.cerrar_sesion(refresh)
        jti, expira = self.tokens.revocar.call_args.args
        self.assertEqual(jti, RefreshToken(refresh)['jti'])
        self.assertGreater(expira, timezone.now())  # se guarda hasta que el token vence
        with self.assertRaises(NoAutorizado):
            acceso_servicio.renovar(refresh)
        with self.assertRaises(NoAutorizado):
            acceso_servicio.cerrar_sesion(refresh)  # ya estaba cerrada
        with self.assertRaises(NoAutorizado):
            acceso_servicio.cerrar_sesion('esto-no-es-un-token')


@override_settings(LOGIN_RATE='3/min')
class LimiteDeIntentosTests(BaseAccesoTest):
    def test_permite_y_anota_mientras_no_se_pase(self):
        self.intentos.momentos_recientes.return_value = [timezone.now()] * 2
        self.assertIsNone(acceso_servicio.registrar_intento_login('1.2.3.4'))
        self.intentos.momentos_recientes.assert_called_once_with('1.2.3.4', 60)
        self.intentos.registrar.assert_called_once_with('1.2.3.4')
        self.intentos.borrar_viejos.assert_called_once_with(60)

    def test_bloquea_y_dice_cuanto_esperar(self):
        ahora = timezone.now()
        self.intentos.momentos_recientes.return_value = [ahora - timedelta(seconds=s) for s in (50, 20, 10)]
        espera = acceso_servicio.registrar_intento_login('1.2.3.4')
        self.assertIn(espera, (10, 11))  # el más antiguo (hace 50 s) sale del minuto en ~10 s
        self.intentos.registrar.assert_not_called()

    @override_settings(LOGIN_RATE='20/h')
    def test_otros_periodos(self):
        self.intentos.momentos_recientes.return_value = []
        acceso_servicio.registrar_intento_login('1.2.3.4')
        self.intentos.momentos_recientes.assert_called_once_with('1.2.3.4', 3600)


class AsignarClaveTests(BaseAccesoTest):
    def test_cambia_la_clave_cifrada(self):
        self.dao.guardar_clave.return_value = 1
        lector = acceso_servicio.asignar_clave(' Docente@UTA.cl ', 'Otra-Clave-Larga-2026')
        correo, cifrada = self.dao.guardar_clave.call_args.args
        self.assertEqual(correo, 'docente@uta.cl')
        self.assertNotIn('Otra-Clave', cifrada)  # nunca en texto plano
        self.assertEqual(lector.correo, 'docente@uta.cl')
        self.dao.crear.assert_not_called()

    def test_agrega_al_lector_si_no_estaba_y_se_da_el_nombre(self):
        self.dao.guardar_clave.return_value = 0
        self.dao.crear.side_effect = lambda c, n, r, h: self.lectores.setdefault(
            c, {'email': c, 'nombre': n, 'rol': r, 'clave': h})
        lector = acceso_servicio.asignar_clave('nuevo@uta.cl', 'Otra-Clave-Larga-2026', 'Ana Pérez', 'equipo')
        self.assertEqual((lector.nombre, lector.rol), ('Ana Pérez', 'equipo'))

    def test_errores(self):
        self.dao.guardar_clave.return_value = 0
        casos = {
            'no está en la tabla lector': ('nuevo@uta.cl', 'Otra-Clave-Larga-2026', None, 'docente'),
            'demasiado corta': ('docente@uta.cl', 'corta', None, 'docente'),
            'El rol debe ser': ('docente@uta.cl', 'Otra-Clave-Larga-2026', None, 'alumno'),
        }
        for texto, argumentos in casos.items():
            with self.subTest(texto), self.assertRaises(DatosInvalidos) as ctx:
                acceso_servicio.asignar_clave(*argumentos)
            self.assertIn(texto, str(ctx.exception))
