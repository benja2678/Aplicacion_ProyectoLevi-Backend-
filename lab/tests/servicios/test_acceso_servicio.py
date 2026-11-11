"""Tests de lab/servicios/acceso_servicio.py.

El DAO de lectores se simula (mock). Se usa TestCase (base de prueba en Docker) solo
porque cerrar sesión guarda el token en la lista negra de simplejwt, que es una tabla.
"""

from unittest import mock

from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from lab.dto.lector import CredencialesDTO, LectorAutenticado
from lab.servicios import acceso_servicio
from lab.utils.errores import DatosInvalidos, NoAutorizado

CLAVE = 'Clave-Del-Docente-2026'


class BaseAccesoTest(TestCase):
    def setUp(self):
        self.dao = mock.patch('lab.servicios.acceso_servicio.lector_dao').start()
        self.addCleanup(mock.patch.stopall)
        self.lectores = {
            'docente@uta.cl': {'email': 'docente@uta.cl', 'nombre': 'Docente', 'rol': 'docente',
                               'clave': make_password(CLAVE)},
            'sinclave@uta.cl': {'email': 'sinclave@uta.cl', 'nombre': 'Sin clave', 'rol': 'equipo', 'clave': None},
        }
        self.dao.obtener.side_effect = lambda correo: self.lectores.get(correo.lower())

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
        refresh = self.entrar()['refresh']
        nuevo = acceso_servicio.renovar(refresh)
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

    def test_cerrar_sesion_invalida_el_refresh(self):
        refresh = self.entrar()['refresh']
        acceso_servicio.cerrar_sesion(refresh)
        with self.assertRaises(NoAutorizado):
            acceso_servicio.renovar(refresh)
        with self.assertRaises(NoAutorizado):
            acceso_servicio.cerrar_sesion('esto-no-es-un-token')


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
