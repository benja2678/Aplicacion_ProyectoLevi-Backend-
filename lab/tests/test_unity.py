"""Tests del envío desde Unity con la llave X-Api-Key."""

import json
from datetime import datetime

from django.test import override_settings

from .utils import BaseApiTest, contar, session_log, sesion_real_del_visor, sql_uno

INGEST = '/api/sessions/ingest/'

# Columnas numeric(9,2): se guardan con 2 decimales (Unity ya redondea el tiempo a 2).
CON_DOS_DECIMALES = {'t', 'durationSeconds', 'laboratorySeconds', 'firstReadingSeconds', 'firstCorrectSeconds'}


def redondeado(valor, clave=None):
    if isinstance(valor, dict):
        return {k: redondeado(v, k) for k, v in valor.items()}
    if isinstance(valor, list):
        return [redondeado(v) for v in valor]
    if clave in CON_DOS_DECIMALES and isinstance(valor, float):
        return round(valor, 2)
    return valor


class IngestTests(BaseApiTest):
    def post_raw(self, body, content_type='application/json'):
        return self.client.generic('POST', INGEST, body, content_type=content_type)

    def test_sesion_nueva_responde_201(self):
        self.use_unity_key()
        r = self.post_raw(json.dumps(session_log()))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['id'], 'A001_N1_2026-11-05T10:31:12')
        self.assertEqual(sql_uno('select origen from sesion'), 'visor')
        self.assertEqual(sql_uno('select inicio from sesion'), datetime(2026, 11, 5, 10, 31, 12))  # sin zona

    def test_respuesta_declara_utf8(self):
        # Sin charset, PowerShell 5.1 mostraba "SesiÃ³n guardada."
        self.use_unity_key()
        r = self.post_raw(json.dumps(session_log()))
        self.assertEqual(r['Content-Type'], 'application/json; charset=utf-8')
        self.assertEqual(r.content.decode('utf-8'), json.dumps(r.json(), ensure_ascii=False, separators=(',', ':')))
        self.assertEqual(r.json()['detail'], 'Sesión guardada.')

    def test_sesion_duplicada_responde_409(self):
        self.use_unity_key()
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 201)
        r = self.post_raw(json.dumps(session_log()))
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['id'], 'A001_N1_2026-11-05T10:31:12')
        self.assertEqual(contar('sesion'), 1)
        self.assertEqual(contar('evento'), 9)  # el detalle tampoco se duplica

    def test_sin_llave_o_llave_incorrecta_rechazado(self):
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)
        self.use_unity_key('llave-equivocada')
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)
        self.assertEqual(contar('sesion'), 0)

    @override_settings(UNITY_API_KEY='')
    def test_sin_llave_configurada_el_envio_queda_desactivado(self):
        self.use_unity_key('')
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)

    def test_la_llave_solo_sirve_para_enviar(self):
        self.use_unity_key()
        self.post_raw(json.dumps(session_log()))
        not_allowed = [
            ('get', '/api/students/'),
            ('post', '/api/students/'),
            ('get', '/api/students/A001/'),
            ('get', '/api/sessions/'),
            ('delete', '/api/sessions/A001_N1_2026-11-05T10:31:12/'),
            ('post', '/api/sessions/import/'),
            ('get', '/api/auth/me/'),
        ]
        for method, url in not_allowed:
            with self.subTest(method=method, url=url):
                r = getattr(self.client, method)(url, {}, format='json')
                self.assertEqual(r.status_code, 401)
        # Tampoco puede leer por el mismo endpoint de envío.
        self.assertEqual(self.client.get(INGEST).status_code, 405)
        self.assertEqual(contar('sesion'), 1)

    def test_el_token_del_profesor_no_reemplaza_la_llave(self):
        self.login_as_teacher()
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)

    def test_acepta_json_aunque_no_venga_content_type_json(self):
        self.use_unity_key()
        r = self.post_raw(json.dumps(session_log()), content_type='text/plain')
        self.assertEqual(r.status_code, 201)

    def test_json_invalido_responde_400(self):
        self.use_unity_key()
        self.assertEqual(self.post_raw('{esto no es json').status_code, 400)
        self.assertEqual(self.post_raw(json.dumps({'hola': 1})).status_code, 400)
        self.assertEqual(self.post_raw(json.dumps(session_log(startedAt=''))).status_code, 400)
        r = self.post_raw(json.dumps(session_log(startedAt='ayer')))
        self.assertEqual(r.status_code, 400)
        self.assertIn('startedAt', r.json()['detail'])

    def test_datos_fuera_de_las_reglas_de_la_base_responden_400(self):
        self.use_unity_key()
        malos = {
            'tipo de evento': {'events': [{'t': 1, 'type': 'saltar'}]},
            'veredicto': {'events': [{'t': 1, 'type': 'lectura', 'task': 'V1', 'measured': 1, 'expected': 1,
                                      'verdict': 'Casi', 'attempt': 1}]},
            'lectura sin valor': {'events': [{'t': 1, 'type': 'lectura', 'task': 'V1', 'verdict': 'Correct'}]},
            'tarea repetida': {'tasks': [{'id': 'V1'}, {'id': 'V1'}]},
            'experimento fuera del catálogo': {'experimentId': 'N2'},
        }
        for nombre, cambio in malos.items():
            with self.subTest(nombre):
                r = self.post_raw(json.dumps(session_log(**cambio)))
                self.assertEqual(r.status_code, 400)
                self.assertTrue(r.json()['detail'])
        self.assertEqual(contar('sesion'), 0)

    def test_nan_se_guarda_como_null(self):
        self.use_unity_key()
        body = json.dumps(session_log()).replace('830.5,', 'NaN,', 1)
        self.assertEqual(self.post_raw(body).status_code, 201)
        self.login_as_teacher()
        self.assertIsNone(self.client.get('/api/sessions/').data[0]['log']['durationSeconds'])

    def test_sesion_real_enviada_por_un_visor(self):
        """El JSON que entregó el equipo de Unity (A015, experimento N1)."""
        original = sesion_real_del_visor()
        self.use_unity_key()
        r = self.post_raw(json.dumps(original))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['id'], 'A015_N1_2026-11-10T23:07:51')

        self.assertEqual(sql_uno("select visor from participante where codigo = 'A015'"), 'A')
        self.assertEqual(contar('evento'), 21)
        self.assertEqual(contar('lectura'), 2)
        self.assertEqual(contar('sesion_tarea'), 6)
        self.assertEqual(sql_uno("select count(*) from evento where tipo = 'diagnostico'"), 2)

        self.login_as_teacher()
        guardada = self.client.get('/api/sessions/').data[0]['log']
        # Vuelve igual que llegó; los tiempos, con 2 decimales.
        self.assertEqual(guardada, redondeado(original))
