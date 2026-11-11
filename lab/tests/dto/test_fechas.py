"""Tests unitarios de lab/dto/fechas.py (sin base de datos)."""

from datetime import UTC, datetime, timedelta, timezone

from django.test import SimpleTestCase

from lab.dto.fechas import a_hora_local, leer_fecha_del_visor, texto_del_visor


class TextoDelVisorTests(SimpleTestCase):
    def test_segundos_enteros_como_unity(self):
        self.assertEqual(texto_del_visor(datetime(2026, 11, 10, 23, 7, 51)), '2026-11-10T23:07:51')

    def test_conserva_milisegundos(self):
        self.assertEqual(texto_del_visor(datetime(2026, 11, 5, 10, 31, 12, 250000)), '2026-11-05T10:31:12.250')

    def test_conserva_microsegundos(self):
        self.assertEqual(texto_del_visor(datetime(2026, 11, 5, 10, 31, 12, 250001)), '2026-11-05T10:31:12.250001')


class LeerFechaDelVisorTests(SimpleTestCase):
    def test_fecha_valida(self):
        self.assertEqual(leer_fecha_del_visor(' 2026-11-10T23:07:51 '), datetime(2026, 11, 10, 23, 7, 51))

    def test_ida_y_vuelta(self):
        for texto in ['2026-11-10T23:07:51', '2026-11-05T10:31:12.250']:
            with self.subTest(texto):
                self.assertEqual(texto_del_visor(leer_fecha_del_visor(texto)), texto)

    def test_rechaza_zona_horaria(self):
        with self.assertRaises(ValueError):
            leer_fecha_del_visor('2026-11-10T23:07:51+00:00')

    def test_rechaza_texto_que_no_es_fecha(self):
        with self.assertRaises(ValueError):
            leer_fecha_del_visor('ayer')


class AHoraLocalTests(SimpleTestCase):
    def test_convierte_a_hora_de_chile_sin_zona(self):
        # En noviembre Chile está en UTC-3.
        self.assertEqual(a_hora_local(datetime(2026, 11, 5, 13, 46, tzinfo=UTC)), '2026-11-05T10:46:00')

    def test_acepta_cualquier_zona(self):
        momento = datetime(2026, 11, 5, 15, 46, tzinfo=timezone(timedelta(hours=2)))
        self.assertEqual(a_hora_local(momento), '2026-11-05T10:46:00')
