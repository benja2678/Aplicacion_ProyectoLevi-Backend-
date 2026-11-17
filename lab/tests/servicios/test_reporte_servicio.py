"""Tests unitarios de lab/servicios/reporte_servicio.py y reporte_excel.py (el DAO se simula: sin base de datos)."""

from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.test import SimpleTestCase
from openpyxl import load_workbook

from lab.dto.reporte import AlumnoResumenDTO, RangoFechasDTO
from lab.servicios import reporte_excel, reporte_servicio

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


class ResumenPorAlumnoTests(BaseReporteTest):
    def setUp(self):
        super().setUp()
        primera = self.dao.sesiones.return_value[0]
        segunda = dict(primera, inicio=datetime(2026, 11, 6, 9, 0), correctas=6, duracion_s=Decimal('600'),
                       ayudas=0, n_sesion=2)
        sin_alumno = dict(primera, codigo='A030', alumno='', asignatura='', tareas=0, correctas=0,
                          duracion_s=Decimal('-5.2'))  # negativa: error del registro
        # Llegan desordenadas: el servicio las ordena por código y por fecha.
        self.dao.sesiones.return_value = [sin_alumno, segunda, primera]

    def alumnos(self):
        return reporte_servicio.resumir_por_alumno(
            self.dao.sesiones.return_value, self.dao.mediciones.return_value, self.dao.incidentes.return_value)

    def test_agrupa_por_codigo_y_numera_las_sesiones(self):
        camila, sin_registrar = self.alumnos()
        self.assertEqual((camila.codigo, camila.nombre, camila.asignatura), ('A001', 'Camila Rojas', 'Electrónica Digital'))
        self.assertEqual([(s.numero, s.inicio) for s in camila.sesiones], [(1, INICIO), (2, datetime(2026, 11, 6, 9, 0))])
        self.assertEqual(camila.sesiones[0].etiqueta, 'Sesión 1 · N1')
        self.assertEqual(sin_registrar.nombre, 'Sin registrar (A030)')

    def test_cuenta_los_incidentes_de_cada_sesion(self):
        camila = self.alumnos()[0]
        primera, segunda = camila.sesiones
        self.assertEqual((primera.fallas, primera.mal_uso), (1, 1))  # se cruzan por código + experimento + inicio
        self.assertEqual((segunda.fallas, segunda.mal_uso), (0, 0))
        self.assertEqual(len(camila.incidentes), 2)
        self.assertEqual(len(camila.mediciones), 1)

    def test_metricas_del_alumno(self):
        camila, sin_registrar = self.alumnos()
        self.assertEqual((camila.correctas, camila.total_mediciones), (7, 12))
        self.assertAlmostEqual(camila.aciertos, 7 / 12)
        self.assertAlmostEqual(camila.tiempo_promedio_min, (830.5 + 600) / 2 / 60)
        self.assertEqual((camila.completadas, camila.ayudas), (2, 1))
        self.assertEqual(camila.ultima_sesion, datetime(2026, 11, 6, 9, 0))
        self.assertAlmostEqual(camila.sesiones[1].aciertos, 1.0)
        # Sin mediciones ni una duración válida: queda vacío, no 0 % ni un tiempo negativo.
        self.assertIsNone(sin_registrar.aciertos)
        self.assertIsNone(sin_registrar.tiempo_promedio_min)

    def test_sin_sesiones_no_hay_alumnos(self):
        self.assertEqual(reporte_servicio.resumir_por_alumno([], [], []), [])


class ExcelTests(BaseReporteTest):
    def excel(self, rango=None):
        contenido, nombre = reporte_servicio.generar_excel(rango or RangoFechasDTO(date(2026, 11, 1), date(2026, 11, 30)))
        return load_workbook(BytesIO(contenido)), nombre

    def test_hojas_en_orden(self):
        libro, nombre = self.excel()
        self.assertEqual(nombre, 'laboratorio_vr_2026-11-01_a_2026-11-30.xlsx')
        self.assertEqual(libro.sheetnames, ['Inicio', 'Resumen', 'A001 Camila Rojas', 'Sesiones', 'Mediciones', 'Incidentes'])
        self.assertEqual(libro.active.title, 'Inicio')  # se abre en la hoja de instrucciones

    def test_inicio_explica_y_enlaza_a_cada_alumno(self):
        hoja = self.excel()[0]['Inicio']
        self.assertIn('Cómo usar este archivo', [c.value for c in hoja['A']])
        self.assertIn('Período: Del 01-11-2026 al 30-11-2026', hoja['A3'].value)
        enlaces = {c.value: c.hyperlink.location for fila in hoja.iter_rows() for c in fila if c.hyperlink}
        self.assertEqual(enlaces['Ver su hoja →'], "'A001 Camila Rojas'!A1")
        self.assertEqual(enlaces['Resumen →'], "'Resumen'!A1")

    def test_resumen_con_todos_los_alumnos_y_graficos(self):
        hoja = self.excel()[0]['Resumen']
        self.assertEqual(hoja['A6'].value, 1)  # tarjeta "Alumnos"
        self.assertEqual(hoja['D5'].value, '% de aciertos del grupo')
        self.assertAlmostEqual(hoja['D6'].value, 1 / 6)
        fila = [c.value for c in hoja[10]]
        self.assertEqual(fila[:4], ['Camila Rojas', 'A001', 'Electrónica Digital', 1])
        self.assertEqual(fila[9:11], [1, 1])  # fallas del circuito, multímetro mal usado
        self.assertEqual(len(hoja._charts), 4)  # aciertos, incidentes y tiempo por alumno + torta por tipo
        self.assertEqual(len(hoja.tables), 2)  # alumnos e incidentes por tipo

    def test_hoja_del_alumno(self):
        hoja = self.excel()[0]['A001 Camila Rojas']
        self.assertEqual(hoja['A1'].hyperlink.location, "'Inicio'!A1")
        self.assertEqual(hoja['A2'].value, 'Camila Rojas')
        self.assertEqual([hoja.cell(5, c).value for c in range(1, 4)], ['Sesiones', 'Completadas', '% de aciertos'])
        self.assertEqual(len(hoja._charts), 2)
        self.assertEqual(len(hoja.tables), 3)  # sesiones, mediciones e incidentes
        valores = [c.value for fila in hoja.iter_rows() for c in fila]
        self.assertIn('Sesión 1 · N1', valores)
        self.assertIn('Correcta', valores)
        self.assertIn('Potencia excesiva en un componente', valores)

    def test_hojas_de_datos_completos(self):
        libro = self.excel()[0]
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

    def test_deja_fuera_los_codigos_sin_alumno(self):
        sesion = self.dao.sesiones.return_value[0]
        self.dao.sesiones.return_value.append(dict(sesion, codigo='A030', alumno='', asignatura=''))
        self.dao.mediciones.return_value.append(dict(self.dao.mediciones.return_value[0], codigo='A030', alumno=''))
        self.dao.incidentes.return_value.append(dict(incidente('rechazo', 'MeterOff'), codigo='EDITOR', alumno=''))
        libro = self.excel()[0]
        self.assertEqual(libro.sheetnames, ['Inicio', 'Resumen', 'A001 Camila Rojas', 'Sesiones', 'Mediciones', 'Incidentes'])
        for hoja in ['Sesiones', 'Mediciones', 'Incidentes']:
            with self.subTest(hoja):
                codigos = {fila[0] for fila in list(libro[hoja].values)[1:]}
                self.assertEqual(codigos, {'A001'})
        self.assertEqual(libro['Resumen']['A6'].value, 1)  # un solo alumno
        # La pantalla de incidentes del panel sigue mostrando todo.
        self.assertEqual(len(reporte_servicio.listar_incidentes(RangoFechasDTO())), 3)

    def test_sin_datos_igual_genera_el_archivo(self):
        self.dao.incidentes.return_value = []
        self.dao.sesiones.return_value = []
        self.dao.mediciones.return_value = []
        libro, nombre = self.excel(RangoFechasDTO())
        self.assertEqual(nombre, 'laboratorio_vr_todo.xlsx')
        self.assertEqual(libro.sheetnames, ['Inicio', 'Resumen', 'Sesiones', 'Mediciones', 'Incidentes'])
        self.assertIn('Todas las fechas', libro['Inicio']['A3'].value)
        self.assertEqual(libro['Sesiones']['A2'].value, 'No hay datos en este rango.')
        self.assertEqual(len(libro['Resumen']._charts), 0)


class NombreDeHojaTests(SimpleTestCase):
    def test_quita_caracteres_prohibidos_corta_y_no_repite(self):
        usados = {'inicio'}
        alumno = AlumnoResumenDTO('A001', "María José O'Higgins [Pérez]: Fuentealba", '')
        nombre = reporte_excel._nombre_de_hoja(alumno, usados)
        self.assertEqual(nombre, 'A001 María José OHiggins Pérez')
        self.assertLessEqual(len(nombre), 31)
        self.assertEqual(reporte_excel._nombre_de_hoja(alumno, usados), 'A001 María José OHiggins Pé (2)')
        self.assertEqual(reporte_excel._nombre_de_hoja(AlumnoResumenDTO('A030', '', ''), usados), 'A030')
