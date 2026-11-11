"""Tests de alumnos y sesiones: que el JSON tenga la forma de src/types.ts del frontend
y que los datos queden bien repartidos en las tablas de levi-db-scripts."""

import json
import re
from urllib.parse import quote

from .utils import BaseApiTest, contar, session_log, sql_uno

LOCAL_ISO = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')  # sin zona horaria


class StudentTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login_as_teacher()

    def create(self, nombre='Camila Rojas', codigo='a001', asignatura='Electrónica Digital', **extra):
        datos = {'nombre': nombre, 'asignatura': asignatura, 'codigoParticipante': codigo, **extra}
        return self.client.post('/api/students/', datos, format='json')

    def test_crear_alumno_con_forma_del_frontend(self):
        r = self.create(nombre='  Camila Rojas ')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(set(r.data), {'id', 'nombre', 'apellido', 'asignatura', 'codigoParticipante', 'creadoEn'})
        self.assertEqual(r.data['nombre'], 'Camila Rojas')
        self.assertEqual(r.data['apellido'], '')
        self.assertEqual(r.data['codigoParticipante'], 'A001')  # en mayúsculas
        self.assertEqual(r.data['id'], 'A001')                  # el código es la llave de participante
        self.assertRegex(r.data['creadoEn'], LOCAL_ISO)
        self.assertEqual(sql_uno("select visor from participante where codigo = 'A001'"), 'A')

    def test_faltan_datos(self):
        r = self.create(nombre=' ', codigo='')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['nombre'], ['Escribe el nombre del alumno.'])
        self.assertEqual(r.data['codigoParticipante'], ['Escribe el código del visor.'])

    def test_codigo_repetido_rechazado(self):
        self.create(codigo='A001')
        r = self.create(nombre='Otro', codigo='a001')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data['codigoParticipante'][0], 'El código A001 ya está asignado a otro alumno.')

    def test_listar_obtener_editar_y_borrar(self):
        sid = self.create().data['id']
        self.create(nombre='Matías', codigo='A002')
        self.assertEqual([a['codigoParticipante'] for a in self.client.get('/api/students/').data], ['A001', 'A002'])
        self.assertEqual(self.client.get(f'/api/students/{sid}/').data['nombre'], 'Camila Rojas')

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
        self.assertEqual(len(self.client.get('/api/students/').data), 1)
        self.assertEqual(self.client.get(f'/api/students/{sid}/').status_code, 404)
        self.assertEqual(self.client.delete(f'/api/students/{sid}/').status_code, 404)

    def test_apellido_opcional_y_se_conserva_si_no_viene(self):
        sid = self.create(apellido='Rojas Díaz').data['id']
        # El panel actual no envía "apellido": al editar no se borra.
        r = self.client.put(f'/api/students/{sid}/',
                            {'nombre': 'Camila', 'asignatura': 'X', 'codigoParticipante': 'A001'}, format='json')
        self.assertEqual(r.data['apellido'], 'Rojas Díaz')
        r = self.client.put(f'/api/students/{sid}/', {'nombre': 'Camila', 'apellido': '', 'asignatura': 'X',
                                                      'codigoParticipante': 'A001'}, format='json')
        self.assertEqual(r.data['apellido'], '')

    def test_borrar_alumno_no_borra_sus_sesiones(self):
        sid = self.create().data['id']
        self.assertEqual(self.ingest(session_log('A001')).status_code, 201)
        self.client.delete(f'/api/students/{sid}/')
        self.assertEqual(contar('sesion'), 1)
        # El código sigue existiendo, ahora sin alumno.
        self.assertIsNone(sql_uno("select nombre from participante where codigo = 'A001'"))

    def test_borrar_alumno_sin_sesiones_borra_el_codigo(self):
        sid = self.create().data['id']
        self.client.delete(f'/api/students/{sid}/')
        self.assertEqual(contar('participante'), 0)

    def test_registrar_un_codigo_que_ya_tenia_sesiones(self):
        self.ingest(session_log('B007'))
        self.assertEqual(self.client.get('/api/students/').data, [])  # todavía no es un alumno
        r = self.create(nombre='Ana', codigo='b007')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['id'], 'B007')

    def test_cambiar_el_codigo_mueve_al_alumno(self):
        self.create(codigo='A001')
        self.ingest(session_log('A001'))
        r = self.client.put('/api/students/A001/',
                            {'nombre': 'Camila Rojas', 'asignatura': 'X', 'codigoParticipante': 'A009'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['id'], 'A009')
        self.assertEqual([a['id'] for a in self.client.get('/api/students/').data], ['A009'])
        # La sesión sigue siendo del código que registró el visor, ahora sin alumno.
        self.assertIsNone(sql_uno("select nombre from participante where codigo = 'A001'"))
        self.assertEqual(sql_uno("select participante_id from sesion"), 'A001')


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
        self.assertEqual(s['id'], 'A001_N1_2026-11-05T10:31:12')
        self.assertEqual(s['source'], 'importada')
        self.assertEqual(s['log'], log)  # el registro de Unity vuelve idéntico (armado desde las tablas)
        self.assertEqual(list(s['log']), list(log))  # y con los campos en el mismo orden
        self.assertRegex(s['receivedAt'], LOCAL_ISO)

    def test_los_datos_quedan_repartidos_en_las_tablas(self):
        self.ingest(session_log())
        self.assertEqual(contar('sesion'), 1)
        self.assertEqual(contar('evento'), 9)
        self.assertEqual(contar('lectura'), 1)
        self.assertEqual(contar('rechazo'), 1)
        self.assertEqual(contar('sesion_tarea'), 6)
        self.assertEqual(sql_uno("select origen from sesion"), 'visor')
        # Lo que no es una medición del catálogo queda como etiqueta.
        self.assertEqual(sql_uno("select etiqueta from evento where tipo = 'vista'"), 'pizarra')
        self.assertEqual(sql_uno("select etiqueta from evento where tipo = 'tutorial'"), 'selector')
        # Las vistas de análisis de levi-db-scripts ven los datos.
        self.assertEqual(sql_uno("select selector from v_eventos where tipo = 'rechazo'"), '200m V')
        self.assertEqual(sql_uno("select tarea from v_eventos where tipo = 'rechazo'"), 'V2')
        self.assertEqual(sql_uno("select rechazos from v_sesiones"), 1)
        self.assertTrue(sql_uno("select cuenta from v_sesiones"))

    def test_importar_informa_nuevas_repetidas_e_invalidas(self):
        r = self.import_files(
            ('uno.json', json.dumps(session_log('A001'))),
            ('uno-copia.json', json.dumps(session_log('A001'))),  # repetida
            ('varias.json', json.dumps([session_log('A002'), session_log('A003', 'N1D')])),  # lista de sesiones
            ('roto.json', '{ no es json'),
            ('otro.json', json.dumps({'nombre': 'no es una sesión'})),
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['added'], 3)
        self.assertEqual(r.data['duplicated'], 1)
        self.assertEqual([i['file'] for i in r.data['invalid']], ['roto.json', 'otro.json'])
        self.assertEqual(contar('sesion'), 3)

    def test_importar_una_sesion_ya_enviada_por_unity_cuenta_como_repetida(self):
        self.ingest(session_log())
        r = self.import_files(('a.json', json.dumps(session_log())))
        self.assertEqual((r.data['added'], r.data['duplicated']), (0, 1))

    def test_experimento_o_medicion_fuera_del_catalogo(self):
        r = self.import_files(
            ('n2.json', json.dumps(session_log(experiment='N2'))),
            ('t0.json', json.dumps(session_log(experiment='T0'))),  # T0 no tiene la medición V1
        )
        self.assertEqual(r.data['added'], 0)
        motivos = [i['reason'] for i in r.data['invalid']]
        self.assertEqual(motivos[0], 'El experimento "N2" no está en el catálogo de la base de datos')
        self.assertEqual(motivos[1], 'La medición "V1" no está en el catálogo del experimento T0')
        self.assertEqual(contar('sesion'), 0)
        self.assertEqual(contar('participante'), 0)  # no queda nada a medias

    def test_started_at_con_fracciones_de_segundo(self):
        self.import_files(('a.json', json.dumps(session_log(started='2026-11-05T10:31:12.250'))))
        s = self.client.get('/api/sessions/').data[0]
        self.assertEqual(s['log']['startedAt'], '2026-11-05T10:31:12.250')
        self.assertEqual(s['id'], 'A001_N1_2026-11-05T10:31:12.250')

    def test_borrar_sesion_por_id(self):
        self.import_files(('a.json', json.dumps(session_log(started='2026-11-05T10:31:12.250'))))
        sid = 'A001_N1_2026-11-05T10:31:12.250'
        r = self.client.delete(f'/api/sessions/{quote(sid, safe="")}/')
        self.assertEqual(r.status_code, 204)
        self.assertEqual(contar('sesion'), 0)
        self.assertEqual(contar('evento'), 0)  # el detalle se borra en cascada
        self.assertEqual(contar('participante'), 0)  # el código sin alumno ya no se necesita
        self.assertEqual(self.client.delete(f'/api/sessions/{quote(sid, safe="")}/').status_code, 404)
        self.assertEqual(self.client.delete('/api/sessions/no-es-un-id/').status_code, 404)

    def test_borrar_sesion_no_borra_al_alumno(self):
        self.client.post('/api/students/', {'nombre': 'Ana', 'codigoParticipante': 'A001'}, format='json')
        self.ingest(session_log('A001'))
        self.client.delete(f'/api/sessions/{quote("A001_N1_2026-11-05T10:31:12", safe="")}/')
        self.assertEqual(len(self.client.get('/api/students/').data), 1)

    def test_importar_con_formato_incorrecto(self):
        r = self.client.post('/api/sessions/import/', {'archivos': []}, format='json')
        self.assertEqual(r.status_code, 400)
