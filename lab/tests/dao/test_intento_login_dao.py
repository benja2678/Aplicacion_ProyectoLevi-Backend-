"""Tests de lab/dao/intento_login_dao.py contra el PostgreSQL de prueba (tabla intento_login, v2.5)."""

from django.test import TestCase

from lab.dao import intento_login_dao

from ..ayudas import contar, sql_uno


class IntentoLoginDaoTests(TestCase):
    def test_registrar_y_contar_por_ip(self):
        for _ in range(3):
            intento_login_dao.registrar('1.1.1.1')
        intento_login_dao.registrar('2.2.2.2')
        recientes = intento_login_dao.momentos_recientes('1.1.1.1', 60)
        self.assertEqual(len(recientes), 3)
        self.assertEqual(recientes, sorted(recientes))  # del más antiguo al más nuevo

    def test_solo_cuenta_los_del_periodo(self):
        intento_login_dao.registrar('1.1.1.1')
        sql_uno("update intento_login set momento = now() - interval '2 minutes' returning id")
        intento_login_dao.registrar('1.1.1.1')
        self.assertEqual(len(intento_login_dao.momentos_recientes('1.1.1.1', 60)), 1)

    def test_borrar_viejos(self):
        intento_login_dao.registrar('1.1.1.1')
        sql_uno("update intento_login set momento = now() - interval '2 minutes' returning id")
        intento_login_dao.registrar('2.2.2.2')
        self.assertEqual(intento_login_dao.borrar_viejos(60), 1)
        self.assertEqual(contar('intento_login'), 1)
