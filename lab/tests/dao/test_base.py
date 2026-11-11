"""Tests de lab/dao/base.py contra el PostgreSQL de prueba (Docker + base_pruebas.sql)."""

from django.test import TestCase

from lab.dao.base import consultar, consultar_uno, ejecutar, ejecutar_varios

from ..ayudas import contar


class BaseDaoTests(TestCase):
    def test_consultar_devuelve_diccionarios(self):
        filas = consultar('select id, titulo from experimento where id in (%s, %s) order by id', ['N1', 'T0'])
        self.assertEqual(filas, [{'id': 'N1', 'titulo': 'Ley de Ohm en un circuito mixto'},
                                 {'id': 'T0', 'titulo': 'Tutorial: controles y primer circuito'}])

    def test_consultar_uno(self):
        self.assertEqual(consultar_uno('select codigo from participante where codigo = %s', ['A001']),
                         {'codigo': 'A001'})
        self.assertIsNone(consultar_uno('select codigo from participante where codigo = %s', ['Z999']))

    def test_ejecutar_devuelve_filas_cambiadas(self):
        self.assertEqual(ejecutar("update participante set visor = 'Z' where nombre is not null"), 2)

    def test_ejecutar_varios(self):
        ejecutar_varios('insert into participante (codigo) values (%s)', [('Z1',), ('Z2',)])
        ejecutar_varios('insert into participante (codigo) values (%s)', [])  # sin filas: no hace nada
        self.assertEqual(contar('participante'), 5)

    def test_los_parametros_no_se_ejecutan_como_sql(self):
        self.assertIsNone(consultar_uno('select codigo from participante where codigo = %s',
                                        ["A001' or '1'='1"]))
