"""Tests de lab/dao/reporte_dao.py contra el PostgreSQL de prueba (Docker + base_pruebas.sql).

Incidentes en base_pruebas.sql:
    sesion 1 · A001 · T0 · 2026-11-04 · 1 rechazo (MeterOff, V_R1)
    sesion 2 · A001 · N1 · 2026-11-05 · 1 diagnóstico (ExcessivePower) + 1 rechazo (OverRange, V2)
    sesion 3 · A015 · N1 · 2026-11-10 · 2 diagnósticos (ExcessivePower)   ← A015 no es alumno
"""

from datetime import datetime

from django.test import TestCase

from lab.dao import reporte_dao

DIA_5 = (datetime(2026, 11, 5), datetime(2026, 11, 6))


class IncidentesTests(TestCase):
    def test_todos_en_orden(self):
        filas = reporte_dao.incidentes(None, None)
        self.assertEqual([(f['codigo'], f['experimento_id'], f['tipo']) for f in filas], [
            ('A001', 'T0', 'rechazo'),
            ('A001', 'N1', 'diagnostico'), ('A001', 'N1', 'rechazo'),
            ('A015', 'N1', 'diagnostico'), ('A015', 'N1', 'diagnostico'),
        ])

    def test_datos_de_cada_incidente(self):
        rechazo = reporte_dao.incidentes(*DIA_5)[1]
        self.assertEqual((rechazo['alumno'], rechazo['medicion'], rechazo['detalle']), ('Camila Rojas', 'V2', 'OverRange'))
        self.assertEqual(rechazo['inicio'], datetime(2026, 11, 5, 10, 31, 12))
        sin_alumno = reporte_dao.incidentes(datetime(2026, 11, 10), None)[0]
        self.assertEqual((sin_alumno['alumno'], sin_alumno['medicion']), ('', ''))
        self.assertTrue(sin_alumno['detalle'].startswith('ExcessivePower:'))

    def test_rango_de_fechas(self):
        self.assertEqual(len(reporte_dao.incidentes(*DIA_5)), 2)
        self.assertEqual(len(reporte_dao.incidentes(datetime(2026, 11, 5), None)), 4)
        self.assertEqual(len(reporte_dao.incidentes(None, datetime(2026, 11, 5))), 1)
        self.assertEqual(reporte_dao.incidentes(datetime(2027, 1, 1), None), [])


class SesionesYMedicionesTests(TestCase):
    def test_sesiones(self):
        filas = reporte_dao.sesiones(None, None)
        self.assertEqual([(f['codigo'], f['experiment_id']) for f in filas], [('A001', 'T0'), ('A001', 'N1'), ('A015', 'N1')])
        self.assertEqual((filas[1]['alumno'], filas[1]['asignatura'], filas[1]['origen']), ('Camila Rojas', 'Electrónica Digital', 'visor'))
        self.assertEqual(len(reporte_dao.sesiones(*DIA_5)), 1)

    def test_mediciones_en_el_orden_del_catalogo(self):
        self.assertEqual(len(reporte_dao.mediciones(None, None)), 13)
        filas = reporte_dao.mediciones(*DIA_5)
        self.assertEqual([f['tarea'] for f in filas], ['V1', 'V2', 'V3', 'I_total', 'I_R2', 'I_R4'])
        self.assertEqual((filas[0]['veredicto_final'], filas[0]['magnitud']), ('Correct', 'tension'))
