"""
Reportes: incidentes de las sesiones y exportación a Excel, por rango de fechas.

Solo leen la base (ver dao/reporte_dao.py). Los incidentes son lo que registra el
visor durante la sesión:
- Fallas del circuito (evento 'diagnostico'): cortocircuito, potencia excesiva…
  El detalle llega como "ExcessivePower: 'R2' disipa 0,42 W…": la categoría es lo
  que está antes de los dos puntos.
- Registros rechazados (evento 'rechazo'): multímetro apagado, fuera de escala…
  El detalle es directamente la categoría (OverRange, MeterOff…).
"""

from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from ..dao import reporte_dao
from ..dto.fechas import texto_del_visor
from ..dto.reporte import IncidenteDTO, RangoFechasDTO

VEREDICTOS = {
    'Correct': 'Correcta',
    'OutOfTolerance': 'Valor incorrecto',
    'ReversedPolarity': 'Puntas invertidas',
    'SinRegistrar': 'No la midió',
}


# ------------------------------------------------------------------ #
# Incidentes


def _categoria(tipo: str, detalle: str) -> str:
    if tipo == 'diagnostico':
        return detalle.split(':', 1)[0].strip()
    return detalle.strip()


def listar_incidentes(rango: RangoFechasDTO) -> list[IncidenteDTO]:
    return [
        IncidenteDTO(
            id_sesion=f"{f['codigo']}_{f['experimento_id']}_{texto_del_visor(f['inicio'])}",
            codigo=f['codigo'],
            alumno=f['alumno'] or '',
            experimento_id=f['experimento_id'],
            experimento=f['experimento'],
            momento=f['inicio'] + timedelta(seconds=float(f['t_s'])),
            segundo=float(f['t_s']),
            tipo=f['tipo'],
            categoria=_categoria(f['tipo'], f['detalle']),
            medicion=f['medicion'],
            detalle=f['detalle'],
        )
        for f in reporte_dao.incidentes(rango.inicio, rango.fin)
    ]


# ------------------------------------------------------------------ #
# Excel


def _celda(valor: Any) -> Any:
    """Convierte cada dato a algo que Excel entiende."""
    if isinstance(valor, bool):
        return 'Sí' if valor else 'No'
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, datetime) and valor.tzinfo is not None:
        # Excel no maneja zonas horarias: se escribe en hora de Chile.
        return timezone.localtime(valor).replace(tzinfo=None)
    return valor


def _hoja(libro: Workbook, titulo: str, columnas: list[str], filas: list[list[Any]]) -> None:
    hoja = libro.create_sheet(titulo)
    hoja.append(columnas)
    for celda in hoja[1]:
        celda.font = Font(bold=True)
    for fila in filas:
        hoja.append([_celda(v) for v in fila])
    hoja.freeze_panes = 'A2'  # el encabezado queda fijo al bajar
    hoja.auto_filter.ref = hoja.dimensions  # flechas para filtrar en cada columna
    for i, columna in enumerate(columnas, start=1):
        largo = max([len(columna)] + [len(str(_celda(f[i - 1]) or '')) for f in filas[:200]])
        hoja.column_dimensions[get_column_letter(i)].width = min(max(largo + 2, 10), 60)
        if any(isinstance(f[i - 1], datetime) for f in filas[:5]):
            for celda in hoja[get_column_letter(i)][1:]:
                celda.number_format = 'yyyy-mm-dd hh:mm:ss'


def generar_excel(rango: RangoFechasDTO) -> tuple[bytes, str]:
    """Devuelve (contenido del .xlsx, nombre del archivo)."""
    libro = Workbook()
    libro.remove(libro.active)  # se quita la hoja vacía que trae por defecto

    _hoja(libro, 'Sesiones', [
        'Código', 'Alumno', 'Asignatura', 'Experimento', 'Título', 'Inicio', 'Término', 'Completada',
        'Duración (s)', 'Laboratorio (s)', 'Correctas', 'Mediciones', 'Rechazos', 'Ayudas', 'Recentrados',
        'N.º de intento', 'Cuenta para el análisis', 'Origen', 'Recibida',
    ], [[
        f['codigo'], f['alumno'], f['asignatura'], f['experiment_id'], f['experimento'], f['inicio'], f['termino'],
        f['completada'], f['duracion_s'], f['laboratorio_s'], f['correctas'], f['tareas'], f['rechazos'], f['ayudas'],
        f['recentrados'], f['n_sesion'], f['cuenta'], f['origen'], f['recibida_en'],
    ] for f in reporte_dao.sesiones(rango.inicio, rango.fin)])

    _hoja(libro, 'Mediciones', [
        'Código', 'Alumno', 'Experimento', 'Inicio de la sesión', 'Medición', 'Magnitud', 'Intentos',
        'Rechazos', 'Resultado', 'Intento en que acertó', 'Primera lectura (s)', 'Primera correcta (s)',
    ], [[
        f['codigo'], f['alumno'], f['experiment_id'], f['inicio'], f['tarea'], f['magnitud'], f['intentos'],
        f['rechazos'], VEREDICTOS.get(f['veredicto_final'], f['veredicto_final']), f['intento_primera_correcta'],
        f['primera_lectura_s'], f['primera_correcta_s'],
    ] for f in reporte_dao.mediciones(rango.inicio, rango.fin)])

    _hoja(libro, 'Incidentes', [
        'Código', 'Alumno', 'Experimento', 'Momento', 'Segundo de la sesión', 'Tipo', 'Incidente',
        'Medición', 'Detalle',
    ], [[
        i.codigo, i.alumno, i.experimento_id, i.momento, i.segundo, i.tipo_texto, i.categoria_texto,
        i.medicion, i.detalle,
    ] for i in listar_incidentes(rango)])

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue(), f'laboratorio_vr_{rango.en_texto()}.xlsx'
