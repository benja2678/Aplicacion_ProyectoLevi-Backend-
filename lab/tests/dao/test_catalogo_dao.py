"""Tests de lab/dao/catalogo_dao.py contra el PostgreSQL de prueba (Docker + base_pruebas.sql)."""

from django.test import TestCase

from lab.dao import catalogo_dao


class CatalogoDaoTests(TestCase):
    def test_obtener_experimento(self):
        self.assertEqual(catalogo_dao.obtener_experimento('N1D'),
                         {'id': 'N1D', 'titulo': 'Ley de Ohm en un circuito mixto (armado desde cero)'})

    def test_experimento_que_no_esta_en_el_catalogo(self):
        self.assertIsNone(catalogo_dao.obtener_experimento('N2'))

    def test_tareas_en_el_orden_del_catalogo(self):
        tareas = catalogo_dao.tareas_del_experimento('N1')
        self.assertEqual(list(tareas), ['V1', 'V2', 'V3', 'I_total', 'I_R2', 'I_R4'])
        self.assertEqual(len(set(tareas.values())), 6)  # cada una con su id
        self.assertEqual(list(catalogo_dao.tareas_del_experimento('T0')), ['V_R1'])
        self.assertEqual(catalogo_dao.tareas_del_experimento('N2'), {})
