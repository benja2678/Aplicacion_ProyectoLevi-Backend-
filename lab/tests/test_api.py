"""Tests de alumnos y sesiones: que el JSON tenga la forma de src/types.ts del frontend."""

import json
import re
from urllib.parse import quote

from lab.models import Session, Student

from .utils import BaseApiTest, session_log

LOCAL_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')  # sin zona horaria


class StudentTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login_as_teacher()

    def create(self, nombre='Camila Rojas', codigo='a001', asignatura='Electrónica Digital'):
        return self.client.post(
            '/api/students/', {'nombre': nombre, 'asignatura': asignatura, 'codigoParticipante': codigo}, format='json'
        )

    def test_crear_alumno_con_forma_del_frontend(self):
        r = self.create(nombre='  Camila Rojas ')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(r.data), {'id', 'nombre', 'asignatura', 'codigoParticipante', 'creadoEn'})
        self.assertEqual(r.data['nombre'], 'Camila Rojas')
        self.assertEqual(r.data['codigoParticipante'], 'A001')  # en mayúsculas
        self.assertIsInstance(r.data['id'], str)
        self.assertRegex(r.data['creadoEn'], LOCAL_ISO)

    def test_codigo_repetido_rechazado(self):
        self.create(codigo='A001')
        r = self.create(nombre='Otro', codigo='a001')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['codigoParticipante'][0], 'El código A001 ya está asignado a otro alumno.')

    def test_listar_editar_y_borrar(self):
        sid = self.create().data['id']
        self.create(nombre='Matías', codigo='A002')
        self.assertEqual(len(self.client.get('/api/students/').data), 2)

        # Editar manteniendo su propio código está permitido.
        r = self.client.put(
            f'/api/students/{sid}/',
            {'nombre': 'Camila R.', 'asignatura': 'Electrónica Digital', 'codigoParticipante': 'A001'},
            format='json',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['nombre'], 'Camila R.')

        # Pero no tomar el código de otro alumno.
        r = self.client.put(
            f'/api/students/{sid}/', {'nombre': 'Camila R.', 'asignatura': '', 'codigoParticipante': 'A002'}, format='json'
        )
        self.assertEqual(r.status_code, 400)

        self.assertEqual(self.client.delete(f'/api/students/{sid}/').status_code, 204)
        self.assertEqual(Student.objects.count(), 1)

    def test_borrar_alumno_no_borra_sus_sesiones(self):
        sid = self.create().data['id']
        Session.objects.create(id='A001_T0_x', participant_code='A001', experiment_id='T0', started_at='x', log={}, source='visor')
        self.client.delete(f'/api/students/{sid}/')
        self.assertEqual(Session.objects.count(), 1)


class SessionTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login_as_teacher()

    def import_files(self, *files):
        return self.client.post(
            '/api/sessions/import/', {'files': [{'name': n, 'text': t} for n, t in files]}, format='json'
        )

    def test_listar_sesiones_con_forma_del_frontend(self):
        log = session_log()
        self.import_files(('a.json', json.dumps(log)))
        r = self.client.get('/api/sessions/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        s = r.data[0]
        self.assertEqual(set(s), {'id', 'log', 'source', 'receivedAt'})
        self.assertEqual(s['id'], 'A001_T0_2026-11-05T10:31:12')
        self.assertEqual(s['source'], 'importada')
        self.assertEqual(s['log'], log)  # el registro de Unity vuelve idéntico
        self.assertRegex(s['receivedAt'], LOCAL_ISO)

    def test_importar_informa_nuevas_repetidas_e_invalidas(self):
        r = self.import_files(
            ('uno.json', json.dumps(session_log('A001'))),
            ('uno-copia.json', json.dumps(session_log('A001'))),  # repetida
            ('varias.json', json.dumps([session_log('A002'), session_log('A003', 'N1')])),  # lista de sesiones
            ('roto.json', '{ no es json'),
            ('otro.json', json.dumps({'nombre': 'no es una sesión'})),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['added'], 3)
        self.assertEqual(r.data['duplicated'], 1)
        self.assertEqual([i['file'] for i in r.data['invalid']], ['roto.json', 'otro.json'])
        self.assertEqual(Session.objects.count(), 3)

    def test_importar_una_sesion_ya_enviada_por_unity_cuenta_como_repetida(self):
        self.client.generic(
            'POST', '/api/sessions/ingest/', json.dumps(session_log()), content_type='application/json',
            HTTP_X_API_KEY='llave-de-prueba-unity-123',
        )
        r = self.import_files(('a.json', json.dumps(session_log())))
        self.assertEqual((r.data['added'], r.data['duplicated']), (0, 1))

    def test_started_at_se_guarda_tal_cual(self):
        self.import_files(('a.json', json.dumps(session_log(started='2026-11-05T10:31:12.250'))))
        s = self.client.get('/api/sessions/').data[0]
        self.assertEqual(s['log']['startedAt'], '2026-11-05T10:31:12.250')
        self.assertEqual(s['id'], 'A001_T0_2026-11-05T10:31:12.250')

    def test_borrar_sesion_por_id(self):
        self.import_files(('a.json', json.dumps(session_log(started='2026-11-05T10:31:12.250'))))
        sid = 'A001_T0_2026-11-05T10:31:12.250'
        r = self.client.delete(f'/api/sessions/{quote(sid, safe="")}/')
        self.assertEqual(r.status_code, 204)
        self.assertEqual(Session.objects.count(), 0)
        self.assertEqual(self.client.delete(f'/api/sessions/{quote(sid, safe="")}/').status_code, 404)

    def test_importar_con_formato_incorrecto(self):
        r = self.client.post('/api/sessions/import/', {'archivos': []}, format='json')
        self.assertEqual(r.status_code, 400)
