"""Tests unitarios de lab/controladores/alumnos.py.

El servicio se reemplaza por un simulacro (mock) y el profesor se "autentica" sin base de
datos: se prueban las rutas, los permisos, los códigos HTTP y la forma del JSON.
"""

from datetime import UTC, datetime
from unittest import mock

from rest_framework.test import APISimpleTestCase

from lab.dto.alumno import AlumnoDTO, AlumnoEntradaDTO
from lab.utils.errores import DatosInvalidos, NoEncontrado

from ..ayudas import profesor_sin_base

CAMILA = AlumnoDTO(codigo='A001', nombre='Camila', apellido='Rojas', asignatura='Electrónica Digital',
                   registrado=datetime(2026, 11, 3, 15, 0, tzinfo=UTC))
CAMILA_JSON = {'id': 'A001', 'nombre': 'Camila', 'apellido': 'Rojas', 'asignatura': 'Electrónica Digital',
               'codigoParticipante': 'A001', 'creadoEn': '2026-11-03T12:00:00'}


class AlumnosControladorTests(APISimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.controladores.alumnos.alumno_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.client.force_authenticate(user=profesor_sin_base())

    def test_listar(self):
        self.servicio.listar.return_value = [CAMILA]
        r = self.client.get('/api/students/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [CAMILA_JSON])

    def test_crear(self):
        self.servicio.crear.return_value = CAMILA
        r = self.client.post('/api/students/', {'nombre': 'Camila', 'asignatura': 'Electrónica Digital',
                                                'codigoParticipante': 'a001'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json(), CAMILA_JSON)
        self.servicio.crear.assert_called_once_with(
            AlumnoEntradaDTO(nombre='Camila', asignatura='Electrónica Digital', codigo='A001'))

    def test_crear_con_datos_invalidos_no_llama_al_servicio(self):
        r = self.client.post('/api/students/', {'nombre': ''}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json(), {'nombre': ['Escribe el nombre del alumno.'],
                                    'codigoParticipante': ['Escribe el código del visor.']})
        self.servicio.crear.assert_not_called()

    def test_crear_con_codigo_ocupado(self):
        self.servicio.crear.side_effect = DatosInvalidos(
            campos={'codigoParticipante': ['El código A001 ya está asignado a otro alumno.']})
        r = self.client.post('/api/students/', {'nombre': 'Otro', 'codigoParticipante': 'A001'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['codigoParticipante'], ['El código A001 ya está asignado a otro alumno.'])

    def test_obtener_editar_y_quitar(self):
        self.servicio.obtener.return_value = CAMILA
        self.servicio.actualizar.return_value = CAMILA
        self.assertEqual(self.client.get('/api/students/A001/').json(), CAMILA_JSON)

        r = self.client.put('/api/students/A001/', {'nombre': 'Camila', 'codigoParticipante': 'A009'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.servicio.actualizar.assert_called_once_with('A001', AlumnoEntradaDTO('Camila', '', 'A009'))

        r = self.client.delete('/api/students/A001/')
        self.assertEqual(r.status_code, 204)
        self.servicio.eliminar.assert_called_once_with('A001')

    def test_alumno_que_no_existe(self):
        self.servicio.obtener.side_effect = NoEncontrado()
        self.servicio.eliminar.side_effect = NoEncontrado()
        self.assertEqual(self.client.get('/api/students/Z999/').status_code, 404)
        self.assertEqual(self.client.delete('/api/students/Z999/').json(), {'detail': 'No encontrado.'})

    def test_metodo_no_permitido(self):
        self.assertEqual(self.client.patch('/api/students/A001/', {}, format='json').status_code, 405)

    def test_sin_profesor_no_se_puede_entrar(self):
        self.client = self.client_class()  # cliente nuevo, sin usuario
        self.assertEqual(self.client.get('/api/students/').status_code, 401)
        alumno = profesor_sin_base()
        alumno.is_staff = False
        self.client.force_authenticate(user=alumno)
        self.assertEqual(self.client.get('/api/students/').status_code, 403)
        self.servicio.listar.assert_not_called()
