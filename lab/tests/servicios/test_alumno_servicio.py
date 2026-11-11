"""Tests unitarios de lab/servicios/alumno_servicio.py.

El DAO se reemplaza por un simulacro (mock): se prueban solo las reglas, sin base de datos.
"""

from contextlib import nullcontext
from datetime import UTC, datetime
from unittest import mock

from django.db import IntegrityError
from django.test import SimpleTestCase

from lab.dto.alumno import AlumnoEntradaDTO
from lab.errores import DatosInvalidos, NoEncontrado
from lab.servicios import alumno_servicio, letra_del_visor

REGISTRADO = datetime(2026, 11, 3, 15, 0, tzinfo=UTC)


def fila(codigo='A001', nombre='Camila', apellido='Rojas', asignatura='Electrónica Digital'):
    return {'codigo': codigo, 'visor': 'A', 'nombre': nombre, 'apellido': apellido,
            'asignatura': asignatura, 'registrado': REGISTRADO}


def entrada(codigo='A001', nombre='Camila', apellido=None, asignatura='Electrónica Digital'):
    return AlumnoEntradaDTO(nombre=nombre, apellido=apellido, asignatura=asignatura, codigo=codigo)


class BaseServicioTest(SimpleTestCase):
    def setUp(self):
        parche_dao = mock.patch('lab.servicios.alumno_servicio.participante_dao')
        parche_tx = mock.patch('lab.servicios.alumno_servicio.transaction.atomic',
                               side_effect=lambda *a, **k: nullcontext())
        self.dao = parche_dao.start()
        parche_tx.start()
        self.addCleanup(mock.patch.stopall)

    def filas(self, **por_codigo):
        """Lo que devuelve dao.obtener(codigo): una fila, o None si el código no existe."""
        self.dao.obtener.side_effect = lambda codigo, bloquear=False: por_codigo.get(codigo)


class LetraDelVisorTests(SimpleTestCase):
    def test_letra(self):
        self.assertEqual(letra_del_visor('A015'), 'A')
        self.assertEqual(letra_del_visor('B3'), 'B')
        self.assertIsNone(letra_del_visor('EDITOR'))
        self.assertIsNone(letra_del_visor('a001'))


class ListarYObtenerTests(BaseServicioTest):
    def test_listar(self):
        self.dao.listar_alumnos.return_value = [fila('A001'), fila('A002', 'Matías', None, None)]
        alumnos = alumno_servicio.listar()
        self.assertEqual([a.codigo for a in alumnos], ['A001', 'A002'])
        self.assertEqual(alumnos[1].apellido, '')

    def test_obtener(self):
        self.filas(A001=fila(), A015=fila('A015', None, None, None))
        self.assertEqual(alumno_servicio.obtener('A001').nombre, 'Camila')
        with self.assertRaises(NoEncontrado):
            alumno_servicio.obtener('A015')  # código sin alumno
        with self.assertRaises(NoEncontrado):
            alumno_servicio.obtener('Z999')

    def test_codigo_disponible(self):
        self.filas(A001=fila(), A015=fila('A015', None, None, None))
        self.assertFalse(alumno_servicio.codigo_disponible('A001'))
        self.assertTrue(alumno_servicio.codigo_disponible('A015'))
        self.assertTrue(alumno_servicio.codigo_disponible('Z999'))


class CrearTests(BaseServicioTest):
    def test_codigo_nuevo(self):
        creado = {}
        self.dao.obtener.side_effect = lambda c, bloquear=False: creado.get(c)
        self.dao.crear_alumno.side_effect = lambda c, *a, **k: creado.setdefault(c, fila(c))
        alumno = alumno_servicio.crear(entrada('B003', apellido='Rojas'))
        self.dao.crear_alumno.assert_called_once_with('B003', 'B', 'Camila', 'Rojas', 'Electrónica Digital')
        self.assertEqual(alumno.codigo, 'B003')

    def test_codigo_que_ya_tenia_sesiones(self):
        sin_alumno = fila('A015', None, None, None)
        self.filas(A015=sin_alumno)
        self.dao.guardar_datos_alumno.side_effect = lambda c, n, a, s, registrado=None: sin_alumno.update(nombre=n)
        alumno_servicio.crear(entrada('A015'))
        args, kwargs = self.dao.guardar_datos_alumno.call_args
        self.assertEqual(args, ('A015', 'Camila', '', 'Electrónica Digital'))
        self.assertIsNotNone(kwargs['registrado'])  # desde ahora es alumno
        self.dao.crear_alumno.assert_not_called()

    def test_codigo_de_otro_alumno(self):
        self.filas(A001=fila())
        with self.assertRaises(DatosInvalidos) as ctx:
            alumno_servicio.crear(entrada('A001'))
        self.assertEqual(ctx.exception.campos,
                         {'codigoParticipante': ['El código A001 ya está asignado a otro alumno.']})

    def test_dos_peticiones_al_mismo_tiempo(self):
        self.filas()
        self.dao.crear_alumno.side_effect = IntegrityError('duplicada')
        with self.assertRaises(DatosInvalidos):
            alumno_servicio.crear(entrada('A001'))


class ActualizarTests(BaseServicioTest):
    def test_mismo_codigo_conserva_el_apellido_si_no_viene(self):
        self.filas(A001=fila())
        alumno_servicio.actualizar('A001', entrada('A001', nombre='Camila R.'))
        self.dao.guardar_datos_alumno.assert_called_once_with('A001', 'Camila R.', 'Rojas', 'Electrónica Digital')

    def test_mismo_codigo_con_apellido_nuevo(self):
        self.filas(A001=fila())
        alumno_servicio.actualizar('A001', entrada('A001', apellido=''))
        self.dao.guardar_datos_alumno.assert_called_once_with('A001', 'Camila', '', 'Electrónica Digital')

    def test_cambiar_a_un_codigo_libre(self):
        filas = {'A001': fila()}
        self.dao.obtener.side_effect = lambda c, bloquear=False: filas.get(c)
        self.dao.crear_alumno.side_effect = lambda c, *a, **k: filas.setdefault(c, fila(c))
        alumno = alumno_servicio.actualizar('A001', entrada('A009'))
        self.dao.crear_alumno.assert_called_once_with('A009', 'A', 'Camila', 'Rojas', 'Electrónica Digital',
                                                      registrado=REGISTRADO)  # mantiene su fecha de registro
        self.dao.quitar_datos_alumno.assert_called_once_with('A001')
        self.dao.borrar_si_sobra.assert_called_once_with('A001')
        self.assertEqual(alumno.codigo, 'A009')

    def test_cambiar_a_un_codigo_que_tenia_sesiones(self):
        self.filas(A001=fila(), A015=fila('A015', None, None, None))
        self.dao.guardar_datos_alumno.side_effect = None
        with mock.patch.object(alumno_servicio, 'obtener') as obtener:
            alumno_servicio.actualizar('A001', entrada('A015'))
        self.dao.guardar_datos_alumno.assert_called_once_with('A015', 'Camila', 'Rojas', 'Electrónica Digital',
                                                              registrado=REGISTRADO)
        obtener.assert_called_once_with('A015')

    def test_cambiar_al_codigo_de_otro_alumno(self):
        self.filas(A001=fila(), A002=fila('A002', 'Matías'))
        with self.assertRaises(DatosInvalidos):
            alumno_servicio.actualizar('A001', entrada('A002'))
        self.dao.quitar_datos_alumno.assert_not_called()

    def test_alumno_que_no_existe(self):
        self.filas(A015=fila('A015', None, None, None))
        for codigo in ['Z999', 'A015']:
            with self.subTest(codigo), self.assertRaises(NoEncontrado):
                alumno_servicio.actualizar(codigo, entrada(codigo))


class EliminarTests(BaseServicioTest):
    def test_quita_al_alumno_y_borra_el_codigo_si_sobra(self):
        self.filas(A001=fila())
        alumno_servicio.eliminar('A001')
        self.dao.quitar_datos_alumno.assert_called_once_with('A001')
        self.dao.borrar_si_sobra.assert_called_once_with('A001')

    def test_alumno_que_no_existe(self):
        self.filas(A015=fila('A015', None, None, None))
        for codigo in ['Z999', 'A015']:
            with self.subTest(codigo), self.assertRaises(NoEncontrado):
                alumno_servicio.eliminar(codigo)
        self.dao.quitar_datos_alumno.assert_not_called()
