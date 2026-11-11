"""Tests de lab/dao/token_dao.py contra el PostgreSQL de prueba (tabla token_revocado, v2.5)."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from lab.dao import token_dao

from ..ayudas import contar


class TokenDaoTests(TestCase):
    def test_revocar_y_consultar(self):
        self.assertFalse(token_dao.esta_revocado('jti-1'))
        token_dao.revocar('jti-1', timezone.now() + timedelta(hours=8))
        self.assertTrue(token_dao.esta_revocado('jti-1'))

    def test_revocar_dos_veces_no_falla(self):
        expira = timezone.now() + timedelta(hours=8)
        token_dao.revocar('jti-1', expira)
        token_dao.revocar('jti-1', expira)
        self.assertEqual(contar('token_revocado'), 1)

    def test_al_revocar_se_borran_los_vencidos(self):
        token_dao.revocar('viejo', timezone.now() - timedelta(minutes=1))
        token_dao.revocar('nuevo', timezone.now() + timedelta(hours=8))
        self.assertFalse(token_dao.esta_revocado('viejo'))
        self.assertEqual(contar('token_revocado'), 1)
