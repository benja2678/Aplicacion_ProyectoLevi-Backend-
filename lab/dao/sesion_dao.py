"""
Sesiones y su detalle (levi-db-scripts v2.0 + v2.3):

    sesion        una fila por sesión (resumen)
    sesion_tarea  resultado de cada medición de la sesión
    evento        línea de tiempo: una fila por acción del alumno
    lectura       detalle de los eventos 'lectura' (valor medido y esperado)
    rechazo       detalle de los eventos 'rechazo' (selector y borne)

Al borrar una sesión, la base borra sola su detalle (on delete cascade).
"""

from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from .base import consultar, consultar_uno, ejecutar, ejecutar_varios

Fila = Sequence[Any]


# ------------------------------------------------------------------ #
# Guardar


def insertar(codigo: str, experimento_id: str, inicio: datetime, termino: datetime | None,
             completada: bool, duracion_s: float | None, laboratorio_s: float | None,
             correctas: int, tareas_total: int, version_app: str, visor_modelo: str,
             origen: str) -> int | None:
    """Inserta la sesión y devuelve su id, o None si ya existía
    (mismo participante + experimento + inicio)."""
    fila = consultar_uno(
        """
        insert into sesion (participante_id, experimento_id, inicio, termino, completada,
                            duracion_s, laboratorio_s, correctas, tareas_total,
                            version_app, visor_modelo, origen)
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (participante_id, experimento_id, inicio) do nothing
        returning id
        """,
        [codigo, experimento_id, inicio, termino, completada, duracion_s, laboratorio_s,
         correctas, tareas_total, version_app, visor_modelo, origen],
    )
    return fila['id'] if fila else None


def insertar_tareas(filas: Iterable[Fila]) -> None:
    """Cada fila: (sesion_id, tarea_id, intentos, rechazos, veredicto_final,
    intento_primera_correcta, primera_lectura_s, primera_correcta_s)."""
    ejecutar_varios(
        """
        insert into sesion_tarea (sesion_id, tarea_id, intentos, rechazos, veredicto_final,
                                  intento_primera_correcta, primera_lectura_s, primera_correcta_s)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        filas,
    )


def insertar_eventos(filas: Iterable[Fila]) -> None:
    """Cada fila: (sesion_id, orden, t_s, tipo, tarea_id, etiqueta, detalle)."""
    ejecutar_varios(
        """
        insert into evento (sesion_id, orden, t_s, tipo, tarea_id, etiqueta, detalle)
        values (%s, %s, %s, %s, %s, %s, %s)
        """,
        filas,
    )


def insertar_lecturas(filas: Iterable[Fila]) -> None:
    """Cada fila: (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne)."""
    ejecutar_varios(
        """
        insert into lectura (sesion_id, orden, medido, esperado, veredicto, intento, selector, borne)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        filas,
    )


def insertar_rechazos(filas: Iterable[Fila]) -> None:
    """Cada fila: (sesion_id, orden, selector, borne)."""
    ejecutar_varios(
        """
        insert into rechazo (sesion_id, orden, selector, borne)
        values (%s, %s, %s, %s)
        """,
        filas,
    )


# ------------------------------------------------------------------ #
# Leer


def listar() -> list[dict]:
    """Todas las sesiones, en el orden en que llegaron."""
    return consultar(
        """
        select s.id, s.participante_id, s.experimento_id, e.titulo,
               s.inicio, s.termino, s.completada, s.duracion_s, s.laboratorio_s,
               s.correctas, s.tareas_total, s.version_app, s.visor_modelo,
               s.origen, s.recibida_en
          from sesion s
          join experimento e on e.id = s.experimento_id
         order by s.recibida_en, s.id
        """
    )


def listar_eventos() -> list[dict]:
    """Los eventos de todas las sesiones, con su lectura o rechazo si corresponde."""
    return consultar(
        """
        select ev.sesion_id, ev.orden, ev.t_s, ev.tipo,
               coalesce(t.codigo, ev.etiqueta, '') as tarea,
               coalesce(ev.detalle, '')            as detalle,
               l.medido, l.esperado, l.veredicto, l.intento,
               coalesce(l.selector, r.selector, '') as selector,
               coalesce(l.borne, r.borne, '')       as borne
          from evento ev
          left join tarea   t on t.id = ev.tarea_id
          left join lectura l on l.sesion_id = ev.sesion_id and l.orden = ev.orden
          left join rechazo r on r.sesion_id = ev.sesion_id and r.orden = ev.orden
         order by ev.sesion_id, ev.orden
        """
    )


def listar_tareas() -> list[dict]:
    """El resumen por tarea de todas las sesiones, en el orden del catálogo."""
    return consultar(
        """
        select st.sesion_id, t.codigo, st.intentos, st.rechazos, st.veredicto_final,
               st.intento_primera_correcta, st.primera_lectura_s, st.primera_correcta_s
          from sesion_tarea st
          join tarea t on t.id = st.tarea_id
         order by st.sesion_id, t.orden, t.id
        """
    )


def buscar(codigo: str, experimento_id: str, inicio: datetime) -> dict | None:
    return consultar_uno(
        """
        select id, participante_id
          from sesion
         where participante_id = %s and experimento_id = %s and inicio = %s
        """,
        [codigo, experimento_id, inicio],
    )


# ------------------------------------------------------------------ #
# Borrar


def borrar(sesion_id: int) -> int:
    """Borra la sesión; sus tareas, eventos, lecturas y rechazos se borran en cascada."""
    return ejecutar('delete from sesion where id = %s', [sesion_id])
