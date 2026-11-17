"""Tests unitarios de lab/controladores/reportes.py (el servicio se simula: sin base de datos)."""

from datetime import date, datetime
from unittest import mock

from rest_framework.test import APISimpleTestCase

from lab.dto.reporte import IncidenteDTO, RangoFechasDTO

from ..ayudas import lector_sin_base

INCIDENTE = IncidenteDTO('A001_N1_2026-11-05T10:31:12', 'A001', 'Camila Rojas', 'N1', 'Ley de Ohm',
                         datetime(2026, 11, 5, 10, 32, 2), 50.0, 'rechazo', 'OverRange', 'V2', 'OverRange')


class ReportesControladorTests(APISimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.controladores.reportes.reporte_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.client.force_authenticate(user=lector_sin_base())

    def test_incidentes(self):
        self.servicio.listar_incidentes.return_value = [INCIDENTE]
        r = self.client.get('/api/reports/incidents/?desde=2026-11-01&hasta=2026-11-30')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [INCIDENTE.a_json()])
        self.servicio.listar_incidentes.assert_called_once_with(RangoFechasDTO(date(2026, 11, 1), date(2026, 11, 30)))

    def test_fecha_mal_escrita_400(self):
        r = self.client.get('/api/reports/incidents/?desde=ayer')
        self.assertEqual(r.status_code, 400)
        self.assertIn('desde', r.json())
        self.servicio.listar_incidentes.assert_not_called()

    def test_exportar_descarga_un_excel(self):
        self.servicio.generar_excel.return_value = (b'contenido-xlsx', 'laboratorio_vr_todo.xlsx')
        r = self.client.get('/api/reports/export/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertEqual(r['Content-Disposition'], 'attachment; filename="laboratorio_vr_todo.xlsx"')
        self.assertEqual(r.content, b'contenido-xlsx')
        self.servicio.generar_excel.assert_called_once_with(RangoFechasDTO())

    def test_sin_token_no_se_puede(self):
        self.client = self.client_class()
        for url in ['/api/reports/incidents/', '/api/reports/export/']:
            with self.subTest(url):
                self.assertEqual(self.client.get(url).status_code, 401)
        self.servicio.generar_excel.assert_not_called()
