"""
Consultas de los reportes. Solo LEEN: usan las tablas y vistas que ya existen
(evento, sesion, v_sesiones, v_tareas…); no crean ni cambian nada en la base.

Todas filtran por el inicio de la sesión: desde `inicio` (incluido) hasta `fin`
(sin incluir). Si alguno es None, ese lado del rango no se filtra.
"""

from datetime import datetime

from .base import consultar

# Rango sobre una columna de fecha. Cada %s se repite: una vez para saber si es NULL
# y otra para comparar (PostgreSQL necesita el tipo explícito para el NULL).
_RANGO = """
       (cast(%s as timestamp) is null or {col} >= %s)
   and (cast(%s as timestamp) is null or {col} <  %s)
"""


def _rango(columna: str) -> str:
    return _RANGO.format(col=columna)


def _parametros(inicio: datetime | None, fin: datetime | None) -> list:
    return [inicio, inicio, fin, fin]


def incidentes(inicio: datetime | None, fin: datetime | None) -> list[dict]:
    """Fallas del circuito ('diagnostico') y registros rechazados ('rechazo') de las sesiones del rango."""
    return consultar(
        f"""
        select s.participante_id                              as codigo,
               trim(concat_ws(' ', p.nombre, p.apellido))     as alumno,
               s.experimento_id,
               e.titulo                                       as experimento,
               s.inicio,
               ev.orden,
               ev.t_s,
               ev.tipo,
               coalesce(t.codigo, '')                         as medicion,
               coalesce(ev.detalle, '')                       as detalle
          from evento ev
          join sesion s         on s.id = ev.sesion_id
          join experimento e    on e.id = s.experimento_id
          left join participante p on p.codigo = s.participante_id
          left join tarea t        on t.id = ev.tarea_id
         where ev.tipo in ('diagnostico', 'rechazo')
           and {_rango('s.inicio')}
         order by s.inicio, s.id, ev.orden
        """,
        _parametros(inicio, fin),
    )


def sesiones(inicio: datetime | None, fin: datetime | None) -> list[dict]:
    """Resumen de cada sesión del rango (vista v_sesiones) con el nombre del alumno."""
    return consultar(
        f"""
        select v.participant_code                             as codigo,
               trim(concat_ws(' ', p.nombre, p.apellido))     as alumno,
               coalesce(p.asignatura, '')                     as asignatura,
               v.experiment_id,
               v.experimento,
               v.inicio, v.termino, v.completada,
               v.duracion_s, v.laboratorio_s,
               v.correctas, v.tareas,
               v.rechazos, v.ayudas, v.recentrados,
               v.n_sesion, v.cuenta, v.origen, v.recibida_en
          from v_sesiones v
          left join participante p on p.codigo = v.participant_code
         where {_rango('v.inicio')}
         order by v.inicio, v.sesion_id
        """,
        _parametros(inicio, fin),
    )


def mediciones(inicio: datetime | None, fin: datetime | None) -> list[dict]:
    """Resultado de cada medición (vista v_tareas) de las sesiones del rango, en el orden del catálogo."""
    return consultar(
        f"""
        select vt.participant_code                            as codigo,
               trim(concat_ws(' ', p.nombre, p.apellido))     as alumno,
               vt.experiment_id,
               s.inicio,
               vt.tarea, vt.magnitud,
               vt.intentos, vt.rechazos, vt.veredicto_final,
               vt.intento_primera_correcta,
               vt.primera_lectura_s, vt.primera_correcta_s
          from v_tareas vt
          join sesion s on s.id = vt.sesion_id
          join tarea t  on t.experimento_id = vt.experiment_id and t.codigo = vt.tarea
          left join participante p on p.codigo = vt.participant_code
         where {_rango('s.inicio')}
         order by s.inicio, s.id, t.orden
        """,
        _parametros(inicio, fin),
    )
