"""Tests unitarios de lab/dto/lector.py (sin base de datos)."""

from django.test import SimpleTestCase

from lab.dto.lector import CredencialesDTO, LectorAutenticado, LectorDTO
from lab.utils.errores import DatosInvalidos


class CredencialesDTOTests(SimpleTestCase):
    def test_correo_en_minusculas_y_sin_espacios(self):
        c = CredencialesDTO.desde_json({'email': ' Docente@UTA.cl ', 'password': 'clave'})
        self.assertEqual(c, CredencialesDTO(correo='docente@uta.cl', clave='clave'))

    def test_acepta_username_como_lo_envia_el_panel(self):
        c = CredencialesDTO.desde_json({'username': 'docente@uta.cl', 'password': 'clave'})
        self.assertEqual(c.correo, 'docente@uta.cl')

    def test_faltan_datos(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            CredencialesDTO.desde_json({'username': ' ', 'password': ''})
        self.assertEqual(ctx.exception.campos, {'username': ['Escribe tu correo.'], 'password': ['Escribe tu contraseña.']})
        with self.assertRaises(DatosInvalidos):
            CredencialesDTO.desde_json('docente@uta.cl')


class LectorDTOTests(SimpleTestCase):
    def fila(self, rol='docente', clave='hash'):
        return {'email': 'docente@uta.cl', 'nombre': 'Docente', 'rol': rol, 'clave': clave}

    def test_puede_entrar_solo_con_clave_y_rol_permitido(self):
        self.assertTrue(LectorDTO.desde_fila(self.fila()).puede_entrar)
        self.assertTrue(LectorDTO.desde_fila(self.fila(rol='equipo')).puede_entrar)
        self.assertFalse(LectorDTO.desde_fila(self.fila(clave=None)).puede_entrar)
        self.assertFalse(LectorDTO.desde_fila(self.fila(rol='otro')).puede_entrar)


class LectorAutenticadoTests(SimpleTestCase):
    def test_se_comporta_como_usuario_conectado(self):
        lector = LectorAutenticado(correo='docente@uta.cl', nombre='Docente', rol='docente')
        self.assertTrue(lector.is_authenticated)
        self.assertFalse(lector.is_anonymous)
        self.assertEqual(lector.a_json(), {'username': 'docente@uta.cl', 'nombre': 'Docente', 'rol': 'docente'})
