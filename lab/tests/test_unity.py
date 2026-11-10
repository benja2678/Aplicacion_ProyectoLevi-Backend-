"""Tests del envío desde Unity con la llave X-Api-Key."""

import json

from django.test import override_settings

from lab.models import Session

from .utils import BaseApiTest, session_log

INGEST = '/api/sessions/ingest/'


class IngestTests(BaseApiTest):
    def post_raw(self, body, content_type='application/json'):
        return self.client.generic('POST', INGEST, body, content_type=content_type)

    def test_sesion_nueva_responde_201(self):
        self.use_unity_key()
        r = self.post_raw(json.dumps(session_log()))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['id'], 'A001_T0_2026-11-05T10:31:12')
        s = Session.objects.get()
        self.assertEqual(s.source, 'visor')
        self.assertEqual(s.started_at, '2026-11-05T10:31:12')  # tal cual, sin zona horaria

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
        self.assertEqual(Session.objects.count(), 1)

    def test_sin_llave_o_llave_incorrecta_rechazado(self):
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)
        self.use_unity_key('llave-equivocada')
        self.assertEqual(self.post_raw(json.dumps(session_log())).status_code, 403)
        self.assertEqual(Session.objects.count(), 0)

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
            ('get', '/api/sessions/'),
            ('delete', '/api/sessions/A001_T0_2026-11-05T10:31:12/'),
            ('post', '/api/sessions/import/'),
            ('get', '/api/auth/me/'),
        ]
        for method, url in not_allowed:
            with self.subTest(method=method, url=url):
                r = getattr(self.client, method)(url, {}, format='json')
                self.assertEqual(r.status_code, 401)
        # Tampoco puede leer por el mismo endpoint de envío.
        self.assertEqual(self.client.get(INGEST).status_code, 405)
        self.assertEqual(Session.objects.count(), 1)

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

    def test_nan_se_guarda_como_null(self):
        self.use_unity_key()
        body = json.dumps(session_log()).replace('830.5', 'NaN')
        self.assertEqual(self.post_raw(body).status_code, 201)
        self.assertIsNone(Session.objects.get().log['durationSeconds'])
