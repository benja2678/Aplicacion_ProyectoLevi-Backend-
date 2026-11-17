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

from collections import defaultdict
from datetime import timedelta

from ..dao import reporte_dao
from ..dto.fechas import texto_del_visor
from ..dto.reporte import AlumnoResumenDTO, IncidenteDTO, RangoFechasDTO, SesionResumenDTO
from . import reporte_excel


# ------------------------------------------------------------------ #
# Incidentes


def _categoria(tipo: str, detalle: str) -> str:
    if tipo == 'diagnostico':
        return detalle.split(':', 1)[0].strip()
    return detalle.strip()


def _incidente(f: dict) -> IncidenteDTO:
    return IncidenteDTO(
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


def listar_incidentes(rango: RangoFechasDTO) -> list[IncidenteDTO]:
    return [_incidente(f) for f in reporte_dao.incidentes(rango.inicio, rango.fin)]


# ------------------------------------------------------------------ #
# Resumen por alumno


def _duracion(segundos) -> float | None:
    """Una duración negativa es un error del registro (pasa con pruebas desde el editor de Unity):
    se deja vacía para que no arruine el tiempo promedio. La hoja "Sesiones" igual muestra el dato original."""
    if segundos is None or segundos < 0:
        return None
    return float(segundos)


def resumir_por_alumno(sesiones: list[dict], mediciones: list[dict], incidentes: list[dict]) -> list[AlumnoResumenDTO]:
    """Agrupa por código del visor las sesiones, mediciones e incidentes, y calcula sus métricas.

    Una sesión se reconoce por (código, experimento, inicio): así se cruzan las tres consultas.
    Solo aparecen los alumnos que tienen sesiones en el rango, ordenados por código.
    """
    conteo: dict[tuple, dict[str, int]] = defaultdict(lambda: {'diagnostico': 0, 'rechazo': 0})
    incidentes_de: dict[str, list[IncidenteDTO]] = defaultdict(list)
    for f in incidentes:
        conteo[(f['codigo'], f['experimento_id'], f['inicio'])][f['tipo']] += 1
        incidentes_de[f['codigo']].append(_incidente(f))

    mediciones_de: dict[str, list[dict]] = defaultdict(list)
    for f in mediciones:
        mediciones_de[f['codigo']].append(f)

    sesiones_de: dict[str, list[dict]] = defaultdict(list)
    for f in sesiones:
        sesiones_de[f['codigo']].append(f)

    alumnos = []
    for codigo in sorted(sesiones_de):
        filas = sorted(sesiones_de[codigo], key=lambda f: f['inicio'])
        resumen = []
        for numero, f in enumerate(filas, start=1):
            c = conteo[(codigo, f['experiment_id'], f['inicio'])]
            resumen.append(SesionResumenDTO(
                numero=numero,
                experimento_id=f['experiment_id'],
                experimento=f['experimento'],
                inicio=f['inicio'],
                completada=bool(f['completada']),
                duracion_s=_duracion(f['duracion_s']),
                correctas=f['correctas'] or 0,
                mediciones=f['tareas'] or 0,
                fallas=c['diagnostico'],
                mal_uso=c['rechazo'],
                ayudas=f['ayudas'] or 0,
                intento=f['n_sesion'],
            ))
        alumnos.append(AlumnoResumenDTO(
            codigo=codigo,
            alumno=filas[0]['alumno'] or '',
            asignatura=filas[0]['asignatura'] or '',
            sesiones=resumen,
            mediciones=mediciones_de[codigo],
            incidentes=incidentes_de[codigo],
        ))
    return alumnos


# ------------------------------------------------------------------ #
# Excel


def _solo_de_alumnos(filas: list[dict]) -> list[dict]:
    """Deja fuera lo de los códigos que no son de ningún alumno (pruebas, EDITOR, códigos sin registrar)."""
    return [f for f in filas if f['alumno']]


def generar_excel(rango: RangoFechasDTO) -> tuple[bytes, str]:
    """Devuelve (contenido del .xlsx, nombre del archivo).

    Solo incluye las sesiones de alumnos registrados en el panel. La pantalla de
    incidentes (listar_incidentes) sigue mostrando todo.
    """
    sesiones = _solo_de_alumnos(reporte_dao.sesiones(rango.inicio, rango.fin))
    mediciones = _solo_de_alumnos(reporte_dao.mediciones(rango.inicio, rango.fin))
    incidentes = _solo_de_alumnos(reporte_dao.incidentes(rango.inicio, rango.fin))
    contenido = reporte_excel.construir(
        rango=rango.descripcion(),
        alumnos=resumir_por_alumno(sesiones, mediciones, incidentes),
        sesiones=sesiones,
        mediciones=mediciones,
        incidentes=[_incidente(f) for f in incidentes],
    )
    return contenido, f'laboratorio_vr_{rango.en_texto()}.xlsx'
