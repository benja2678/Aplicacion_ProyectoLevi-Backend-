"""Tests de lab/dao/lector_dao.py contra el PostgreSQL de prueba.

Datos de base_pruebas.sql: docente@ejemplo.cl (docente) y equipo@ejemplo.cl (equipo), sin clave.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from lab.dao import lector_dao

from ..ayudas import contar


class LectorDaoTests(TestCase):
    def test_obtener_sin_importar_mayusculas(self):
        self.assertEqual(lector_dao.obtener('Docente@Ejemplo.CL'),
                         {'email': 'docente@ejemplo.cl', 'nombre': 'Docente de prueba', 'rol': 'docente', 'clave': None})
        self.assertIsNone(lector_dao.obtener('nadie@ejemplo.cl'))

    def test_guardar_clave(self):
        self.assertEqual(lector_dao.guardar_clave('EQUIPO@ejemplo.cl', 'hash-1'), 1)
        self.assertEqual(lector_dao.obtener('equipo@ejemplo.cl')['clave'], 'hash-1')
        self.assertEqual(lector_dao.guardar_clave('nadie@ejemplo.cl', 'hash-2'), 0)

    def test_crear(self):
        lector_dao.crear('nuevo@ejemplo.cl', 'Nuevo', 'equipo', 'hash-3')
        self.assertEqual(lector_dao.obtener('nuevo@ejemplo.cl')['rol'], 'equipo')
        self.assertEqual(contar('lector'), 3)

    def test_la_base_solo_acepta_los_roles_docente_y_equipo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            lector_dao.crear('otro@ejemplo.cl', 'Otro', 'alumno', 'hash')
