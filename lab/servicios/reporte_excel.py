"""
Arma el archivo Excel de los reportes. Solo da formato: los datos llegan ya calculados
desde reporte_servicio.py.

Hojas, en este orden:
    Inicio        cómo usar el archivo y la lista de alumnos, con un enlace a la hoja de cada uno.
    Resumen       todos los alumnos juntos, los incidentes por tipo y los gráficos del grupo.
    A015 Juan…    una hoja por alumno: sus números, gráficos, sesiones, mediciones e incidentes.
    Sesiones, Mediciones, Incidentes
                  los datos completos (una fila por registro) para filtrar o hacer otros cálculos.
"""

import math
import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter, quote_sheetname
from openpyxl.worksheet.hyperlink import Hyperlink
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from ..dto.fechas import texto_del_visor
from ..dto.reporte import AlumnoResumenDTO, IncidenteDTO

VEREDICTOS = {
    'Correct': 'Correcta',
    'OutOfTolerance': 'Valor incorrecto',
    'ReversedPolarity': 'Puntas invertidas',
    'SinRegistrar': 'No la midió',
}

# Colores y formatos
AZUL = '1F4E79'
AZUL_CLARO = 'DDEBF7'
GRIS = '595959'
VERDE_CLARO = 'E2EFDA'
ROJO_CLARO = 'FCE4D6'
FECHA = 'dd-mm-yyyy hh:mm'
PORCENTAJE = '0%'
UN_DECIMAL = '0.0'
DOS_DECIMALES = '0.00'

COLOR_PESTANA = {'inicio': AZUL, 'resumen': '2E75B6', 'alumno': '70AD47', 'datos': 'A6A6A6'}
INICIO = 'Inicio'
RESUMEN = 'Resumen'

# Tamaño aproximado de una columna y una fila de Excel, para ubicar los gráficos sin que se tapen.
CM_POR_ANCHO = 0.2
CM_POR_FILA = 0.53
ALTO_GRAFICO = 7.5  # cm

Columna = tuple[str, str | None]  # (encabezado, formato de número o None)


# ------------------------------------------------------------------ #
# Ayudas de formato


def _valor(valor: Any) -> Any:
    """Convierte cada dato a algo que Excel entiende."""
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime) and valor.tzinfo is not None:
        # Excel no maneja zonas horarias: se escribe en hora de Chile.
        return timezone.localtime(valor).replace(tzinfo=None)
    return valor


def _largo(valor: Any, formato: str | None) -> int:
    """Cuántos caracteres ocupa el dato ya formateado (para el ancho de la columna)."""
    if valor is None:
        return 0
    if isinstance(valor, datetime):
        return 16
    if formato == PORCENTAJE:
        return 5
    if isinstance(valor, float):
        return len(f'{valor:.2f}')
    return len(str(valor))


def _rellenar(celda, color: str) -> None:
    celda.fill = PatternFill('solid', start_color=color, end_color=color)


def _enlace(celda, hoja_destino: str, texto: str) -> None:
    """Hace que la celda lleve a otra hoja del mismo archivo al hacer clic."""
    celda.value = texto
    celda.hyperlink = Hyperlink(ref=celda.coordinate, location=f'{quote_sheetname(hoja_destino)}!A1', display=texto)
    celda.font = Font(color='0563C1', underline='single')


def _nombre_de_hoja(alumno: AlumnoResumenDTO, usados: set[str]) -> str:
    """'A015 Juan Salinas' (Excel permite 31 caracteres y prohíbe []:*?/\\ y ')."""
    base = re.sub(r"[\[\]:*?/\\']", '', f'{alumno.codigo} {alumno.alumno}'.strip())[:31].strip()
    nombre, n = base, 2
    while nombre.lower() in usados:
        sufijo = f' ({n})'
        nombre, n = base[:31 - len(sufijo)] + sufijo, n + 1
    usados.add(nombre.lower())
    return nombre


class _Libro:
    """Un Workbook más lo que hace falta para darle formato (anchos de columna y nombres de tabla)."""

    def __init__(self) -> None:
        self.libro = Workbook()
        self.libro.remove(self.libro.active)  # se quita la hoja vacía que trae por defecto
        self._tablas = 0
        self._anchos: dict[str, dict[int, float]] = {}

    # Hojas

    def hoja(self, titulo: str, tipo: str, cuadricula: bool = False) -> Worksheet:
        hoja = self.libro.create_sheet(titulo)
        hoja.sheet_properties.tabColor = COLOR_PESTANA[tipo]
        hoja.sheet_view.showGridLines = cuadricula
        # Al imprimir: horizontal y todo el ancho en una página.
        hoja.page_setup.orientation = 'landscape'
        hoja.page_setup.fitToWidth = 1
        hoja.page_setup.fitToHeight = 0
        hoja.sheet_properties.pageSetUpPr.fitToPage = True
        self._anchos[titulo] = {}
        return hoja

    def ancho(self, hoja: Worksheet, columna: int, caracteres: float) -> None:
        anchos = self._anchos[hoja.title]
        anchos[columna] = max(anchos.get(columna, 0), caracteres)

    def aplicar_anchos(self, hoja: Worksheet) -> None:
        for columna, caracteres in self._anchos[hoja.title].items():
            hoja.column_dimensions[get_column_letter(columna)].width = min(max(caracteres + 2, 9), 60)

    def columna_libre(self, hoja: Worksheet, desde_cm: float) -> int:
        """La primera columna que empieza después de `desde_cm` (para poner un gráfico al lado de otro)."""
        cm, columna = 0.0, 1
        while cm < desde_cm:
            ancho = hoja.column_dimensions[get_column_letter(columna)].width or 8.43
            cm += ancho * CM_POR_ANCHO
            columna += 1
        return columna

    # Bloques

    def encabezado(self, hoja: Worksheet, titulo: str, subtitulo: str, volver: bool = True) -> None:
        """Fila 1: enlace para volver; fila 2: título grande; fila 3: subtítulo."""
        if volver:
            _enlace(hoja['A1'], INICIO, '← Volver al inicio')
        hoja['A2'] = titulo
        hoja['A2'].font = Font(size=18, bold=True, color=AZUL)
        hoja['A3'] = subtitulo
        hoja['A3'].font = Font(size=11, color=GRIS)
        hoja.row_dimensions[2].height = 28

    def seccion(self, hoja: Worksheet, fila: int, texto: str) -> None:
        hoja.cell(fila, 1, texto).font = Font(size=13, bold=True, color=AZUL)

    def tarjetas(self, hoja: Worksheet, fila: int, tarjetas: list[tuple[str, Any, str | None]]) -> None:
        """Una fila de "tarjetas": arriba el nombre del número y abajo el número grande."""
        borde = Border(left=Side(style='thick', color='FFFFFF'), right=Side(style='thick', color='FFFFFF'))
        for columna, (etiqueta, valor, formato) in enumerate(tarjetas, start=1):
            arriba = hoja.cell(fila, columna, etiqueta)
            arriba.font = Font(size=10, color=GRIS)
            arriba.alignment = Alignment(wrap_text=True, vertical='top')
            abajo = hoja.cell(fila + 1, columna, _valor(valor) if valor is not None else '—')
            abajo.font = Font(size=18, bold=True, color=AZUL)
            abajo.alignment = Alignment(horizontal='left')
            if formato and valor is not None:
                abajo.number_format = formato
            for celda in (arriba, abajo):
                _rellenar(celda, AZUL_CLARO)
                celda.border = borde
            self.ancho(hoja, columna, 13)
        hoja.row_dimensions[fila].height = 28
        hoja.row_dimensions[fila + 1].height = 30

    def tabla(self, hoja: Worksheet, fila: int, columnas: list[Columna], filas: list[list[Any]],
              vacia: str = 'No hay datos en este rango.') -> tuple[int, int]:
        """Escribe una tabla de Excel (encabezado azul, filas alternadas y flechas para filtrar).

        Devuelve (fila del encabezado, última fila escrita).
        """
        for c, (titulo, _) in enumerate(columnas, start=1):
            celda = hoja.cell(fila, c, titulo)
            celda.font = Font(bold=True, color='FFFFFF')
            _rellenar(celda, AZUL)
            celda.alignment = Alignment(vertical='center')
            self.ancho(hoja, c, len(titulo))
        for r, datos in enumerate(filas, start=fila + 1):
            for c, ((_, formato), valor) in enumerate(zip(columnas, datos), start=1):
                celda = hoja.cell(r, c, _valor(valor))
                if formato:
                    celda.number_format = formato
                self.ancho(hoja, c, _largo(celda.value, formato))
        if not filas:
            hoja.cell(fila + 1, 1, vacia).font = Font(italic=True, color=GRIS)
            return fila, fila + 1
        self._tablas += 1
        rango = f'A{fila}:{get_column_letter(len(columnas))}{fila + len(filas)}'
        tabla = Table(displayName=f'Tabla{self._tablas}', ref=rango)
        tabla.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
        hoja.add_table(tabla)
        return fila, fila + len(filas)

    def colorear_porcentajes(self, hoja: Worksheet, columna: int, desde: int, hasta: int) -> None:
        """Rojo = bajo, amarillo = medio, verde = alto."""
        letra = get_column_letter(columna)
        hoja.conditional_formatting.add(f'{letra}{desde}:{letra}{hasta}', ColorScaleRule(
            start_type='num', start_value=0, start_color='F8696B',
            mid_type='num', mid_value=0.5, mid_color='FFEB84',
            end_type='num', end_value=1, end_color='63BE7B',
        ))

    def guardar(self) -> bytes:
        self.libro.active = 0  # se abre en la hoja Inicio
        salida = BytesIO()
        self.libro.save(salida)
        return salida.getvalue()


# ------------------------------------------------------------------ #
# Gráficos


def _etiquetas(valor: bool = False, porcentaje: bool = False) -> DataLabelList:
    """Números sobre el gráfico: solo el valor (o el %), sin repetir el nombre de la serie ni la categoría."""
    return DataLabelList(showVal=valor, showPercent=porcentaje, showSerName=False, showCatName=False,
                         showLegendKey=False, showLeaderLines=False)


def _barras(titulo: str, hoja: Worksheet, columnas: tuple[int, int], categorias: int, filas: tuple[int, int], *,
            horizontal: bool = False, apiladas: bool = False, porcentaje: bool = False) -> BarChart:
    """Gráfico de barras con los datos de una tabla. `filas` = (encabezado, última fila)."""
    encabezado, ultima = filas
    grafico = BarChart()
    grafico.type = 'bar' if horizontal else 'col'
    grafico.title = titulo
    grafico.title.overlay = False  # el título va arriba, sin tapar las barras
    grafico.style = 10
    grafico.varyColors = False
    grafico.add_data(Reference(hoja, min_col=columnas[0], max_col=columnas[1], min_row=encabezado, max_row=ultima),
                     titles_from_data=True)
    grafico.set_categories(Reference(hoja, min_col=categorias, min_row=encabezado + 1, max_row=ultima))
    grafico.x_axis.delete = False
    grafico.y_axis.delete = False
    if horizontal:
        grafico.x_axis.scaling.orientation = 'maxMin'  # el primero de la lista queda arriba…
        grafico.y_axis.crosses = 'max'                 # …y los números del eje quedan abajo
    if apiladas:
        grafico.grouping = 'stacked'
        grafico.overlap = 100
        grafico.legend.position = 'r'
    else:
        grafico.legend = None
        grafico.dataLabels = _etiquetas(valor=True)
    if porcentaje:
        grafico.y_axis.scaling.min = 0
        grafico.y_axis.scaling.max = 1
        grafico.y_axis.number_format = PORCENTAJE
    barras = ultima - encabezado
    grafico.width = 16
    grafico.height = max(ALTO_GRAFICO, 2.5 + 0.9 * barras) if horizontal else ALTO_GRAFICO
    return grafico


def _torta(titulo: str, hoja: Worksheet, datos: int, categorias: int, filas: tuple[int, int]) -> PieChart:
    encabezado, ultima = filas
    grafico = PieChart()
    grafico.title = titulo
    grafico.title.overlay = False
    grafico.add_data(Reference(hoja, min_col=datos, min_row=encabezado, max_row=ultima), titles_from_data=True)
    grafico.set_categories(Reference(hoja, min_col=categorias, min_row=encabezado + 1, max_row=ultima))
    grafico.dataLabels = _etiquetas(porcentaje=True)
    grafico.legend.position = 'r'
    grafico.width = 16
    grafico.height = 9
    return grafico


def _filas_que_ocupa(alto_cm: float) -> int:
    return math.ceil(alto_cm / CM_POR_FILA) + 2


def _ubicar_de_a_dos(libro: _Libro, hoja: Worksheet, fila: int, graficos: list) -> int:
    """Pone los gráficos de a dos por fila. Devuelve la fila siguiente al último."""
    segunda = get_column_letter(libro.columna_libre(hoja, 16.5))
    for i in range(0, len(graficos), 2):
        par = graficos[i:i + 2]
        hoja.add_chart(par[0], f'A{fila}')
        if len(par) == 2:
            hoja.add_chart(par[1], f'{segunda}{fila}')
        fila += max(_filas_que_ocupa(g.height) for g in par)
    return fila


# ------------------------------------------------------------------ #
# Hojas


def _hoja_inicio(libro: _Libro, rango: str, alumnos: list[AlumnoResumenDTO], hojas: dict[str, str]) -> None:
    hoja = libro.hoja(INICIO, 'inicio')
    generado = timezone.localtime(timezone.now()).strftime('%d-%m-%Y %H:%M')
    libro.encabezado(hoja, 'Laboratorio VR · Reporte de resultados', f'Período: {rango}  ·  Generado el {generado}',
                     volver=False)

    libro.seccion(hoja, 5, 'Cómo usar este archivo')
    pasos = [
        '1.  Abajo, en las pestañas de colores, están todas las hojas. También puedes saltar con los enlaces azules.',
        '2.  "Resumen" (pestaña azul) muestra a todos los alumnos juntos y los gráficos del grupo.',
        '3.  Cada alumno tiene su hoja (pestaña verde) con sus números, gráficos, sesiones, mediciones e incidentes.',
        '4.  En las tablas, la flecha ▼ de cada encabezado sirve para ordenar o filtrar (por ejemplo, solo un experimento).',
        '5.  En cada hoja, "← Volver al inicio" (arriba a la izquierda) te trae de vuelta aquí.',
    ]
    for i, paso in enumerate(pasos, start=6):
        hoja.cell(i, 1, paso)

    fila = 6 + len(pasos) + 1
    libro.seccion(hoja, fila, 'Alumnos')
    encabezado, ultima = libro.tabla(hoja, fila + 1, [
        ('Alumno', None), ('Código', None), ('Asignatura', None), ('Sesiones', None),
        ('% de aciertos', PORCENTAJE), ('Ver detalle', None),
    ], [[a.nombre, a.codigo, a.asignatura, len(a.sesiones), a.aciertos, None] for a in alumnos],
        vacia='No hay sesiones en este período.')
    for r, alumno in enumerate(alumnos, start=encabezado + 1):
        _enlace(hoja.cell(r, 6), hojas[alumno.codigo], 'Ver su hoja →')
    if alumnos:
        libro.colorear_porcentajes(hoja, 5, encabezado + 1, ultima)

    fila = ultima + 2
    libro.seccion(hoja, fila, 'Otras hojas')
    otras = [
        (RESUMEN, 'Todos los alumnos juntos, con gráficos.'),
        ('Sesiones', 'Todas las sesiones, una por fila (datos completos).'),
        ('Mediciones', 'El resultado de cada medición de cada sesión.'),
        ('Incidentes', 'Cada falla del circuito y cada uso incorrecto del multímetro.'),
    ]
    for i, (destino, descripcion) in enumerate(otras, start=fila + 1):
        _enlace(hoja.cell(i, 1), destino, f'{destino} →')
        hoja.cell(i, 2, descripcion).font = Font(color=GRIS)

    fila = fila + len(otras) + 2
    libro.seccion(hoja, fila, '¿Qué significa cada número?')
    glosario = [
        ('% de aciertos', 'Mediciones correctas ÷ mediciones pedidas. Verde = bien, amarillo = regular, rojo = bajo.'),
        ('Tiempo promedio', 'Lo que dura en promedio una sesión, en minutos.'),
        ('Fallas del circuito', 'El circuito armado tuvo un problema (cortocircuito, potencia excesiva, LED dañado…).'),
        ('Multímetro mal usado', 'Intentó registrar una medición con el multímetro mal puesto (apagado, modo o escala incorrectos, puntas sueltas…).'),
        ('Ayudas', 'Cuántas veces miró la ayuda dentro del laboratorio.'),
        ('N.º de intento', 'Cuántas veces ha hecho ese experimento (1 = la primera vez).'),
    ]
    for i, (termino, explicacion) in enumerate(glosario, start=fila + 1):
        hoja.cell(i, 1, termino).font = Font(bold=True)
        hoja.cell(i, 2, explicacion)

    hoja.freeze_panes = 'A4'
    libro.aplicar_anchos(hoja)


def _hoja_resumen(libro: _Libro, rango: str, alumnos: list[AlumnoResumenDTO], hojas: dict[str, str]) -> None:
    hoja = libro.hoja(RESUMEN, 'resumen')
    libro.encabezado(hoja, 'Resumen de todos los alumnos', f'Período: {rango}')

    sesiones = [s for a in alumnos for s in a.sesiones]
    correctas = sum(s.correctas for s in sesiones)
    pedidas = sum(s.mediciones for s in sesiones)
    minutos = [s.duracion_min for s in sesiones if s.duracion_min is not None]
    libro.tarjetas(hoja, 5, [
        ('Alumnos', len(alumnos), None),
        ('Sesiones', len(sesiones), None),
        ('Completadas', sum(1 for s in sesiones if s.completada), None),
        ('% de aciertos del grupo', correctas / pedidas if pedidas else None, PORCENTAJE),
        ('Tiempo promedio (min)', sum(minutos) / len(minutos) if minutos else None, UN_DECIMAL),
        ('Fallas del circuito', sum(a.fallas for a in alumnos), None),
        ('Multímetro mal usado', sum(a.mal_uso for a in alumnos), None),
    ])

    libro.seccion(hoja, 8, 'Alumnos')
    tabla_alumnos = libro.tabla(hoja, 9, [
        ('Alumno', None), ('Código', None), ('Asignatura', None), ('Sesiones', None), ('Completadas', None),
        ('Correctas', None), ('Mediciones', None), ('% de aciertos', PORCENTAJE),
        ('Tiempo promedio (min)', UN_DECIMAL), ('Fallas del circuito', None), ('Multímetro mal usado', None),
        ('Ayudas', None), ('Última sesión', FECHA), ('Ver detalle', None),
    ], [[
        a.nombre, a.codigo, a.asignatura, len(a.sesiones), a.completadas, a.correctas, a.total_mediciones,
        a.aciertos, a.tiempo_promedio_min, a.fallas, a.mal_uso, a.ayudas, a.ultima_sesion, None,
    ] for a in alumnos], vacia='No hay sesiones en este período.')
    encabezado, ultima = tabla_alumnos
    for r, alumno in enumerate(alumnos, start=encabezado + 1):
        _enlace(hoja.cell(r, 14), hojas[alumno.codigo], 'Ver su hoja →')

    fila = ultima + 2
    libro.seccion(hoja, fila, 'Incidentes por tipo')
    conteo = Counter((i.categoria_texto, i.tipo_texto) for a in alumnos for i in a.incidentes)
    tabla_tipos = libro.tabla(hoja, fila + 1, [('Incidente', None), ('Tipo', None), ('Cantidad', None)], [
        [incidente, tipo, cantidad] for (incidente, tipo), cantidad in conteo.most_common()
    ], vacia='No hubo incidentes en este período.')

    fila = tabla_tipos[1] + 2
    libro.seccion(hoja, fila, 'Gráficos')
    libro.aplicar_anchos(hoja)
    if not alumnos:
        hoja.cell(fila + 1, 1, 'No hay sesiones en este período, así que no hay gráficos.').font = Font(italic=True, color=GRIS)
        return
    libro.colorear_porcentajes(hoja, 8, encabezado + 1, ultima)
    graficos = [
        _barras('% de aciertos por alumno', hoja, (8, 8), 1, tabla_alumnos, horizontal=True, porcentaje=True),
        _barras('Incidentes por alumno', hoja, (10, 11), 1, tabla_alumnos, horizontal=True, apiladas=True),
        _barras('Tiempo promedio por sesión (minutos)', hoja, (9, 9), 1, tabla_alumnos, horizontal=True),
    ]
    if conteo:
        graficos.append(_torta('Incidentes por tipo', hoja, 3, 1, tabla_tipos))
    _ubicar_de_a_dos(libro, hoja, fila + 1, graficos)


def _hoja_alumno(libro: _Libro, nombre_hoja: str, rango: str, alumno: AlumnoResumenDTO) -> None:
    hoja = libro.hoja(nombre_hoja, 'alumno')
    partes = [f'Código {alumno.codigo}', alumno.asignatura, f'Período: {rango}']
    libro.encabezado(hoja, alumno.nombre, '  ·  '.join(p for p in partes if p))
    libro.tarjetas(hoja, 5, [
        ('Sesiones', len(alumno.sesiones), None),
        ('Completadas', alumno.completadas, None),
        ('% de aciertos', alumno.aciertos, PORCENTAJE),
        ('Tiempo promedio (min)', alumno.tiempo_promedio_min, UN_DECIMAL),
        ('Fallas del circuito', alumno.fallas, None),
        ('Multímetro mal usado', alumno.mal_uso, None),
        ('Ayudas', alumno.ayudas, None),
    ])

    # Los gráficos van justo debajo de las tarjetas; se deja el espacio y se ponen al final,
    # cuando ya se sabe el ancho de las columnas.
    libro.seccion(hoja, 8, 'Gráficos')
    fila = 9 + _filas_que_ocupa(ALTO_GRAFICO) + 1

    # Sesiones
    sesion_de = {f'{alumno.codigo}_{s.experimento_id}_{texto_del_visor(s.inicio)}': s for s in alumno.sesiones}
    etiqueta_de = {(s.experimento_id, s.inicio): s.etiqueta for s in alumno.sesiones}
    libro.seccion(hoja, fila, 'Sesiones')
    tabla_sesiones = libro.tabla(hoja, fila + 1, [
        ('Sesión', None), ('Fecha', FECHA), ('Experimento', None), ('Completada', None),
        ('Duración (min)', UN_DECIMAL), ('Correctas', None), ('Mediciones', None), ('% de aciertos', PORCENTAJE),
        ('Fallas del circuito', None), ('Multímetro mal usado', None), ('Ayudas', None), ('N.º de intento', None),
    ], [[
        s.etiqueta, s.inicio, s.experimento, s.completada, s.duracion_min, s.correctas, s.mediciones, s.aciertos,
        s.fallas, s.mal_uso, s.ayudas, s.intento,
    ] for s in alumno.sesiones])
    libro.colorear_porcentajes(hoja, 8, tabla_sesiones[0] + 1, tabla_sesiones[1])

    # Mediciones
    fila = tabla_sesiones[1] + 2
    libro.seccion(hoja, fila, 'Mediciones')
    encabezado, ultima = libro.tabla(hoja, fila + 1, [
        ('Sesión', None), ('Medición', None), ('Magnitud', None), ('Resultado', None), ('Intentos', None),
        ('Rechazos', None), ('Intento en que acertó', None), ('Primera lectura (s)', DOS_DECIMALES),
        ('Primera correcta (s)', DOS_DECIMALES),
    ], [[
        etiqueta_de.get((m['experiment_id'], m['inicio']), m['experiment_id']), m['tarea'], m['magnitud'],
        VEREDICTOS.get(m['veredicto_final'], m['veredicto_final']), m['intentos'], m['rechazos'],
        m['intento_primera_correcta'], m['primera_lectura_s'], m['primera_correcta_s'],
    ] for m in alumno.mediciones])
    for r, m in enumerate(alumno.mediciones, start=encabezado + 1):
        _rellenar(hoja.cell(r, 4), VERDE_CLARO if m['veredicto_final'] == 'Correct' else ROJO_CLARO)

    # Incidentes
    fila = ultima + 2
    libro.seccion(hoja, fila, 'Incidentes')
    libro.tabla(hoja, fila + 1, [
        ('Sesión', None), ('Momento', FECHA), ('Segundo de la sesión', DOS_DECIMALES), ('Tipo', None),
        ('Incidente', None), ('Medición', None), ('Detalle', None),
    ], [[
        sesion_de[i.id_sesion].etiqueta if i.id_sesion in sesion_de else i.experimento_id, i.momento, i.segundo,
        i.tipo_texto, i.categoria_texto, i.medicion, i.detalle,
    ] for i in alumno.incidentes], vacia='No tuvo incidentes en este período.')

    hoja.freeze_panes = 'A4'
    libro.aplicar_anchos(hoja)
    if alumno.sesiones:
        _ubicar_de_a_dos(libro, hoja, 9, [
            _barras('% de aciertos en cada sesión', hoja, (8, 8), 1, tabla_sesiones, porcentaje=True),
            _barras('Incidentes en cada sesión', hoja, (9, 10), 1, tabla_sesiones, apiladas=True),
        ])


def _hoja_datos(libro: _Libro, titulo: str, columnas: list[Columna], filas: list[list[Any]]) -> None:
    """Hoja de datos completos: la tabla empieza en la fila 1 y el encabezado queda fijo al bajar."""
    hoja = libro.hoja(titulo, 'datos', cuadricula=True)
    libro.tabla(hoja, 1, columnas, filas)
    hoja.freeze_panes = 'A2'
    libro.aplicar_anchos(hoja)


# ------------------------------------------------------------------ #


def construir(rango: str, alumnos: list[AlumnoResumenDTO], sesiones: list[dict], mediciones: list[dict],
              incidentes: list[IncidenteDTO]) -> bytes:
    """Devuelve el contenido del .xlsx. `rango` es el período en palabras ("Del 01-11-2026 al 30-11-2026")."""
    libro = _Libro()
    usados = {INICIO.lower(), RESUMEN.lower(), 'sesiones', 'mediciones', 'incidentes'}
    hojas = {a.codigo: _nombre_de_hoja(a, usados) for a in alumnos}

    _hoja_inicio(libro, rango, alumnos, hojas)
    _hoja_resumen(libro, rango, alumnos, hojas)
    for alumno in alumnos:
        _hoja_alumno(libro, hojas[alumno.codigo], rango, alumno)

    _hoja_datos(libro, 'Sesiones', [
        ('Código', None), ('Alumno', None), ('Asignatura', None), ('Experimento', None), ('Título', None),
        ('Inicio', FECHA), ('Término', FECHA), ('Completada', None), ('Duración (s)', DOS_DECIMALES),
        ('Laboratorio (s)', DOS_DECIMALES), ('Correctas', None), ('Mediciones', None), ('Rechazos', None),
        ('Ayudas', None), ('Recentrados', None), ('N.º de intento', None), ('Cuenta para el análisis', None),
        ('Origen', None), ('Recibida', FECHA),
    ], [[
        f['codigo'], f['alumno'], f['asignatura'], f['experiment_id'], f['experimento'], f['inicio'], f['termino'],
        f['completada'], f['duracion_s'], f['laboratorio_s'], f['correctas'], f['tareas'], f['rechazos'], f['ayudas'],
        f['recentrados'], f['n_sesion'], f['cuenta'], f['origen'], f['recibida_en'],
    ] for f in sesiones])

    _hoja_datos(libro, 'Mediciones', [
        ('Código', None), ('Alumno', None), ('Experimento', None), ('Inicio de la sesión', FECHA),
        ('Medición', None), ('Magnitud', None), ('Intentos', None), ('Rechazos', None), ('Resultado', None),
        ('Intento en que acertó', None), ('Primera lectura (s)', DOS_DECIMALES), ('Primera correcta (s)', DOS_DECIMALES),
    ], [[
        f['codigo'], f['alumno'], f['experiment_id'], f['inicio'], f['tarea'], f['magnitud'], f['intentos'],
        f['rechazos'], VEREDICTOS.get(f['veredicto_final'], f['veredicto_final']), f['intento_primera_correcta'],
        f['primera_lectura_s'], f['primera_correcta_s'],
    ] for f in mediciones])

    _hoja_datos(libro, 'Incidentes', [
        ('Código', None), ('Alumno', None), ('Experimento', None), ('Momento', FECHA),
        ('Segundo de la sesión', DOS_DECIMALES), ('Tipo', None), ('Incidente', None), ('Medición', None),
        ('Detalle', None),
    ], [[
        i.codigo, i.alumno, i.experimento_id, i.momento, i.segundo, i.tipo_texto, i.categoria_texto,
        i.medicion, i.detalle,
    ] for i in incidentes])

    return libro.guardar()
