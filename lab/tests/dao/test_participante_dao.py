"""Tests de lab/dao/participante_dao.py contra el PostgreSQL de prueba.

Datos de base_pruebas.sql: A001 Camila Rojas y A002 Matías Soto (alumnos), A015 (sin alumno,
con una sesión). A001 tiene 2 sesiones; A002 ninguna.
"""

from datetime import UTC, datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from lab.dao import participante_dao

from ..utils import contar


class ParticipanteDaoTests(TestCase):
    def test_listar_alumnos_solo_con_nombre_y_por_fecha_de_registro(self):
        alumnos = participante_dao.listar_alumnos()
        self.assertEqual([a['codigo'] for a in alumnos], ['A001', 'A002'])
        self.assertEqual(alumnos[0], {
            'codigo': 'A001', 'visor': 'A', 'nombre': 'Camila', 'apellido': 'Rojas',
            'asignatura': 'Electrónica Digital', 'registrado': datetime(2026, 11, 3, 15, 0, tzinfo=UTC),
        })

    def test_obtener(self):
        self.assertIsNone(participante_dao.obtener('A015')['nombre'])
        self.assertIsNone(participante_dao.obtener('Z999'))
        with transaction.atomic():
            self.assertEqual(participante_dao.obtener('A001', bloquear=True)['nombre'], 'Camila')

    def test_crear_si_no_existe(self):
        participante_dao.crear_si_no_existe('B003', 'B')
        participante_dao.crear_si_no_existe('A001', 'X')  # ya existe: no cambia nada
        self.assertEqual(participante_dao.obtener('B003')['visor'], 'B')
        self.assertEqual(participante_dao.obtener('A001')['visor'], 'A')
        self.assertEqual(participante_dao.obtener('A001')['nombre'], 'Camila')

    def test_crear_alumno(self):
        participante_dao.crear_alumno('B003', 'B', 'Ana', 'Soto', 'Electrónica Digital')
        fila = participante_dao.obtener('B003')
        self.assertEqual((fila['nombre'], fila['apellido'], fila['asignatura']), ('Ana', 'Soto', 'Electrónica Digital'))
        self.assertIsNotNone(fila['registrado'])  # now()

    def test_crear_alumno_con_fecha_de_registro(self):
        fecha = datetime(2026, 1, 1, tzinfo=UTC)
        participante_dao.crear_alumno('B003', 'B', 'Ana', '', '', registrado=fecha)
        self.assertEqual(participante_dao.obtener('B003')['registrado'], fecha)

    def test_crear_alumno_con_codigo_existente_falla(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            participante_dao.crear_alumno('A001', 'A', 'Otra', '', '')

    def test_guardar_datos_alumno(self):
        antes = participante_dao.obtener('A001')['registrado']
        participante_dao.guardar_datos_alumno('A001', 'Camila', 'Rojas Díaz', 'Física')
        fila = participante_dao.obtener('A001')
        self.assertEqual((fila['apellido'], fila['asignatura'], fila['registrado']), ('Rojas Díaz', 'Física', antes))

        fecha = datetime(2026, 11, 11, tzinfo=UTC)
        participante_dao.guardar_datos_alumno('A015', 'Pedro', '', '', registrado=fecha)
        self.assertEqual(participante_dao.obtener('A015')['registrado'], fecha)

    def test_quitar_datos_alumno(self):
        participante_dao.quitar_datos_alumno('A001')
        fila = participante_dao.obtener('A001')
        self.assertEqual((fila['nombre'], fila['apellido'], fila['asignatura']), (None, None, None))

    def test_borrar_si_sobra(self):
        self.assertEqual(participante_dao.borrar_si_sobra('A002'), 0)  # tiene nombre: es un alumno
        self.assertEqual(participante_dao.borrar_si_sobra('A015'), 0)  # tiene una sesión
        participante_dao.quitar_datos_alumno('A002')
        self.assertEqual(participante_dao.borrar_si_sobra('A002'), 1)  # sin nombre y sin sesiones
        self.assertEqual(contar('participante'), 2)
