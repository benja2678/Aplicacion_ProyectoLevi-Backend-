"""Tests unitarios de lab/servicios/reporte_servicio.py (el DAO se simula: sin base de datos)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase
from openpyxl import load_workbook

from lab.dto.reporte import RangoFechasDTO
from lab.servicios import reporte_servicio

INICIO = datetime(2026, 11, 5, 10, 31, 12)


def incidente(tipo, detalle, medicion='', alumno='Camila Rojas', t_s='50.00'):
    return {'codigo': 'A001', 'alumno': alumno, 'experimento_id': 'N1', 'experimento': 'Ley de Ohm',
            'inicio': INICIO, 'orden': 1, 't_s': Decimal(t_s), 'tipo': tipo, 'medicion': medicion, 'detalle': detalle}


class BaseReporteTest(SimpleTestCase):
    def setUp(self):
        self.dao = mock.patch('lab.servicios.reporte_servicio.reporte_dao').start()
        self.addCleanup(mock.patch.stopall)
        self.dao.incidentes.return_value = [
            incidente('diagnostico', "ExcessivePower: 'R2' disipa 0,42 W.", t_s='26.86'),
            incidente('rechazo', 'OverRange', medicion='V2'),
        ]
        self.dao.sesiones.return_value = [{
            'codigo': 'A001', 'alumno': 'Camila Rojas', 'asignatura': 'Electrónica Digital', 'experiment_id': 'N1',
            'experimento': 'Ley de Ohm', 'inicio': INICIO, 'termino': None, 'completada': True,
            'duracion_s': Decimal('830.50'), 'laboratorio_s': Decimal('700.25'), 'correctas': 1, 'tareas': 6,
            'rechazos': 1, 'ayudas': 1, 'recentrados': 0, 'n_sesion': 1, 'cuenta': True, 'origen': 'visor',
            'recibida_en': datetime(2026, 11, 5, 13, 46, tzinfo=UTC),
        }]
        self.dao.mediciones.return_value = [{
            'codigo': 'A001', 'alumno': 'Camila Rojas', 'experiment_id': 'N1', 'inicio': INICIO, 'tarea': 'V1',
            'magnitud': 'tension', 'intentos': 1, 'rechazos': 0, 'veredicto_final': 'Correct',
            'intento_primera_correcta': 1, 'primera_lectura_s': Decimal('47.65'), 'primera_correcta_s': Decimal('47.65'),
        }]


class IncidentesTests(BaseReporteTest):
    def test_arma_cada_incidente(self):
        rango = RangoFechasDTO(date(2026, 11, 5), date(2026, 11, 5))
        falla, rechazo = reporte_servicio.listar_incidentes(rango)
        self.dao.incidentes.assert_called_once_with(datetime(2026, 11, 5), datetime(2026, 11, 6))
        self.assertEqual(falla.id_sesion, 'A001_N1_2026-11-05T10:31:12')
        self.assertEqual(falla.categoria, 'ExcessivePower')  # lo que está antes de ":"
        self.assertEqual(falla.momento, datetime(2026, 11, 5, 10, 31, 38, 860000))  # inicio + 26,86 s
        self.assertEqual((rechazo.categoria, rechazo.medicion, rechazo.segundo), ('OverRange', 'V2', 50.0))


class ExcelTests(BaseReporteTest):
    def test_tres_hojas_con_encabezado_y_datos(self):
        contenido, nombre = reporte_servicio.generar_excel(RangoFechasDTO(date(2026, 11, 1), date(2026, 11, 30)))
        self.assertEqual(nombre, 'laboratorio_vr_2026-11-01_a_2026-11-30.xlsx')
        libro = load_workbook(BytesIO(contenido))
        self.assertEqual(libro.sheetnames, ['Sesiones', 'Mediciones', 'Incidentes'])

        sesiones = list(libro['Sesiones'].values)
        self.assertEqual(sesiones[0][:3], ('Código', 'Alumno', 'Asignatura'))
        fila = dict(zip(sesiones[0], sesiones[1]))
        self.assertEqual(fila['Completada'], 'Sí')
        self.assertEqual(fila['Duración (s)'], 830.5)
        self.assertEqual(fila['Inicio'], INICIO)
        self.assertEqual(fila['Recibida'], datetime(2026, 11, 5, 10, 46))  # hora de Chile, sin zona

        medicion = dict(zip(*list(libro['Mediciones'].values)))
        self.assertEqual((medicion['Medición'], medicion['Resultado']), ('V1', 'Correcta'))

        incidentes = list(libro['Incidentes'].values)
        self.assertEqual(len(incidentes), 3)  # encabezado + 2
        self.assertEqual(incidentes[1][5:7], ('Falla del circuito', 'Potencia excesiva en un componente'))
        self.assertEqual(incidentes[2][5:8], ('Multímetro mal usado', 'Fuera de la escala del multímetro', 'V2'))

    def test_sin_datos_igual_genera_el_archivo(self):
        self.dao.incidentes.return_value = []
        self.dao.sesiones.return_value = []
        self.dao.mediciones.return_value = []
        contenido, nombre = reporte_servicio.generar_excel(RangoFechasDTO())
        self.assertEqual(nombre, 'laboratorio_vr_todo.xlsx')
        libro = load_workbook(BytesIO(contenido))
        self.assertEqual([libro[h].max_row for h in libro.sheetnames], [1, 1, 1])  # solo encabezados
