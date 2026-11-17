"""Tests unitarios de lab/dto/reporte.py (sin base de datos)."""

from datetime import date, datetime

from django.test import SimpleTestCase

from lab.dto.reporte import IncidenteDTO, RangoFechasDTO
from lab.utils.errores import DatosInvalidos


class RangoFechasDTOTests(SimpleTestCase):
    def test_lee_las_fechas(self):
        rango = RangoFechasDTO.desde_query({'desde': '2026-11-01', 'hasta': ' 2026-11-30 '})
        self.assertEqual(rango, RangoFechasDTO(date(2026, 11, 1), date(2026, 11, 30)))

    def test_las_dos_son_opcionales(self):
        self.assertEqual(RangoFechasDTO.desde_query({}), RangoFechasDTO())
        self.assertEqual(RangoFechasDTO.desde_query({'desde': '', 'hasta': None}), RangoFechasDTO())

    def test_hasta_incluye_el_dia_completo(self):
        rango = RangoFechasDTO(date(2026, 11, 5), date(2026, 11, 5))
        self.assertEqual(rango.inicio, datetime(2026, 11, 5, 0, 0))
        self.assertEqual(rango.fin, datetime(2026, 11, 6, 0, 0))  # sin incluir el 6
        self.assertIsNone(RangoFechasDTO().inicio)
        self.assertIsNone(RangoFechasDTO().fin)

    def test_formato_incorrecto(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            RangoFechasDTO.desde_query({'desde': '05/11/2026'})
        self.assertEqual(ctx.exception.campos, {'desde': ['Usa el formato AAAA-MM-DD (por ejemplo 2026-11-05).']})

    def test_hasta_antes_que_desde(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            RangoFechasDTO.desde_query({'desde': '2026-11-10', 'hasta': '2026-11-01'})
        self.assertIn('hasta', ctx.exception.campos)

    def test_texto_para_el_nombre_del_archivo(self):
        d1, d2 = date(2026, 11, 1), date(2026, 11, 30)
        self.assertEqual(RangoFechasDTO(d1, d2).en_texto(), '2026-11-01_a_2026-11-30')
        self.assertEqual(RangoFechasDTO(desde=d1).en_texto(), 'desde_2026-11-01')
        self.assertEqual(RangoFechasDTO(hasta=d2).en_texto(), 'hasta_2026-11-30')
        self.assertEqual(RangoFechasDTO().en_texto(), 'todo')

    def test_descripcion_para_leer_en_el_excel(self):
        d1, d2 = date(2026, 11, 1), date(2026, 11, 30)
        self.assertEqual(RangoFechasDTO(d1, d2).descripcion(), 'Del 01-11-2026 al 30-11-2026')
        self.assertEqual(RangoFechasDTO(desde=d1).descripcion(), 'Desde el 01-11-2026')
        self.assertEqual(RangoFechasDTO(hasta=d2).descripcion(), 'Hasta el 30-11-2026')
        self.assertEqual(RangoFechasDTO().descripcion(), 'Todas las fechas')


class IncidenteDTOTests(SimpleTestCase):
    def test_a_json_con_nombres_en_espanol(self):
        i = IncidenteDTO(id_sesion='A001_N1_2026-11-05T10:31:12', codigo='A001', alumno='Camila Rojas',
                         experimento_id='N1', experimento='Ley de Ohm', momento=datetime(2026, 11, 5, 10, 32, 2),
                         segundo=50.0, tipo='rechazo', categoria='OverRange', medicion='V2', detalle='OverRange')
        self.assertEqual(i.a_json(), {
            'sessionId': 'A001_N1_2026-11-05T10:31:12', 'participantCode': 'A001', 'student': 'Camila Rojas',
            'experimentId': 'N1', 'experiment': 'Ley de Ohm', 'at': '2026-11-05T10:32:02', 'second': 50.0,
            'type': 'rechazo', 'typeLabel': 'Multímetro mal usado', 'category': 'OverRange',
            'categoryLabel': 'Fuera de la escala del multímetro', 'task': 'V2', 'detail': 'OverRange',
        })

    def test_categoria_desconocida_queda_tal_cual(self):
        i = IncidenteDTO('x', 'A001', '', 'N1', '', datetime(2026, 1, 1), 0.0, 'diagnostico', 'Nueva', '', 'Nueva: algo')
        self.assertEqual((i.tipo_texto, i.categoria_texto), ('Falla del circuito', 'Nueva'))
