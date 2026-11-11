"""Tests unitarios de lab/controladores/sesiones.py (servicio simulado, sin base de datos)."""

import json
from datetime import UTC, datetime
from unittest import mock
from urllib.parse import quote

from rest_framework.test import APISimpleTestCase

from lab.dto.sesion import ResultadoImportacionDTO, SesionGuardadaDTO, SesionInvalida, SesionLogDTO
from lab.utils.errores import DatosInvalidos, NoEncontrado

from ..ayudas import TEST_API_KEY, lector_sin_base, session_log

INGEST = '/api/sessions/ingest/'


class SesionesControladorTests(APISimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.controladores.sesiones.sesion_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.client.force_authenticate(user=lector_sin_base())

    def test_listar_con_la_forma_del_frontend(self):
        log = session_log()
        self.servicio.listar.return_value = [SesionGuardadaDTO(
            log=SesionLogDTO.desde_json(log), origen='importada', recibida_en=datetime(2026, 11, 5, 13, 46, tzinfo=UTC))]
        r = self.client.get('/api/sessions/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [{'id': 'A001_N1_2026-11-05T10:31:12', 'log': log, 'source': 'importada',
                                     'receivedAt': '2026-11-05T10:46:00'}])

    def test_borrar_con_el_id_codificado(self):
        sid = 'A001_N1_2026-11-05T10:31:12.250'
        r = self.client.delete(f'/api/sessions/{quote(sid, safe="")}/')
        self.assertEqual(r.status_code, 204)
        self.servicio.eliminar.assert_called_once_with(sid)

    def test_borrar_una_que_no_existe(self):
        self.servicio.eliminar.side_effect = NoEncontrado()
        self.assertEqual(self.client.delete('/api/sessions/no-existe/').status_code, 404)

    def test_importar(self):
        self.servicio.importar.return_value = ResultadoImportacionDTO(agregadas=1, repetidas=0,
                                                                      invalidas=[('x.json', 'No es un JSON válido')])
        archivos = [{'name': 'a.json', 'text': '{}'}]
        r = self.client.post('/api/sessions/import/', {'files': archivos}, format='json')
        self.assertEqual(r.json(), {'added': 1, 'duplicated': 0, 'invalid': [{'file': 'x.json', 'reason': 'No es un JSON válido'}]})
        self.servicio.importar.assert_called_once_with(archivos)

    def test_importar_con_formato_incorrecto(self):
        self.servicio.importar.side_effect = DatosInvalidos('Se esperaba {"files": [{"name": ..., "text": ...}]}.')
        r = self.client.post('/api/sessions/import/', {'archivos': []}, format='json')
        self.assertEqual(r.status_code, 400)
        self.servicio.importar.assert_called_once_with(None)

    def test_sin_profesor_no_se_puede_entrar(self):
        self.client = self.client_class()  # cliente nuevo, sin usuario
        for metodo, url in [('get', '/api/sessions/'), ('delete', '/api/sessions/x/'), ('post', '/api/sessions/import/')]:
            with self.subTest(metodo=metodo, url=url):
                self.assertEqual(getattr(self.client, metodo)(url, {}, format='json').status_code, 401)


class RecibirSesionControladorTests(APISimpleTestCase):
    """POST /api/sessions/ingest/: solo con la llave de Unity."""

    def setUp(self):
        self.servicio = mock.patch('lab.controladores.sesiones.sesion_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.servicio.recibir_del_visor.return_value = ('A001_N1_2026-11-05T10:31:12', True)

    def enviar(self, cuerpo=None, llave=TEST_API_KEY, content_type='application/json'):
        cuerpo = json.dumps(session_log()) if cuerpo is None else cuerpo
        extra = {'HTTP_X_API_KEY': llave} if llave is not None else {}
        return self.client.generic('POST', INGEST, cuerpo, content_type=content_type, **extra)

    def test_sesion_nueva_201(self):
        r = self.enviar()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), {'id': 'A001_N1_2026-11-05T10:31:12', 'detail': 'Sesión guardada.'})
        self.assertEqual(r['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(self.servicio.recibir_del_visor.call_args.args[0], json.dumps(session_log()).encode())

    def test_sesion_repetida_409(self):
        self.servicio.recibir_del_visor.return_value = ('A001_N1_2026-11-05T10:31:12', False)
        r = self.enviar()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['detail'], 'La sesión ya existía.')

    def test_sesion_invalida_400(self):
        self.servicio.recibir_del_visor.side_effect = SesionInvalida('El cuerpo no es un JSON válido.')
        r = self.enviar('{roto')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'detail': 'El cuerpo no es un JSON válido.'})

    def test_acepta_el_cuerpo_aunque_no_venga_como_json(self):
        self.assertEqual(self.enviar(content_type='text/plain').status_code, 201)

    def test_sin_llave_o_con_llave_incorrecta_403(self):
        self.assertEqual(self.enviar(llave=None).status_code, 403)
        self.assertEqual(self.enviar(llave='llave-equivocada').status_code, 403)
        self.servicio.recibir_del_visor.assert_not_called()

    def test_el_token_del_profesor_no_reemplaza_la_llave(self):
        self.client.force_authenticate(user=lector_sin_base())
        self.assertEqual(self.enviar(llave=None).status_code, 403)

    def test_la_llave_solo_sirve_para_enviar(self):
        self.client.credentials(HTTP_X_API_KEY=TEST_API_KEY)
        for metodo, url in [('get', '/api/students/'), ('post', '/api/students/'), ('get', '/api/students/A001/'),
                            ('get', '/api/sessions/'), ('delete', '/api/sessions/x/'),
                            ('post', '/api/sessions/import/'), ('get', '/api/auth/me/')]:
            with self.subTest(metodo=metodo, url=url):
                self.assertEqual(getattr(self.client, metodo)(url, {}, format='json').status_code, 401)
        self.assertEqual(self.client.get(INGEST).status_code, 405)  # tampoco se puede leer por aquí
