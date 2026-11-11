"""
Tabla participante (levi-db-scripts v2.0 + v2.2).

Una fila por código de visor (A001, B003…). Si tiene nombre, es un ALUMNO que el
profesor registró en el panel; si no, es un código cuyas sesiones llegaron antes de
que se registrara al alumno.
"""

from datetime import datetime

from .base import consultar, consultar_uno, ejecutar

_COLUMNAS = 'codigo, visor, nombre, apellido, asignatura, registrado'


def listar_alumnos() -> list[dict]:
    return consultar(
        f"""
        select {_COLUMNAS}
          from participante
         where nombre is not null
         order by registrado, codigo
        """
    )


def obtener(codigo: str, bloquear: bool = False) -> dict | None:
    """Una fila por su código. Con `bloquear`, la reserva hasta el fin de la transacción
    (evita que dos peticiones al mismo tiempo asignen el mismo código)."""
    return consultar_uno(
        f"""
        select {_COLUMNAS}
          from participante
         where codigo = %s
        {'for update' if bloquear else ''}
        """,
        [codigo],
    )


def crear_si_no_existe(codigo: str, visor: str | None) -> None:
    """La crea sin datos de alumno (lo usa el envío de sesiones)."""
    ejecutar(
        """
        insert into participante (codigo, visor)
        values (%s, %s)
        on conflict (codigo) do nothing
        """,
        [codigo, visor],
    )


def crear_alumno(codigo: str, visor: str | None, nombre: str, apellido: str, asignatura: str,
                 registrado: datetime | None = None) -> None:
    ejecutar(
        """
        insert into participante (codigo, visor, nombre, apellido, asignatura, registrado)
        values (%s, %s, %s, %s, %s, coalesce(%s, now()))
        """,
        [codigo, visor, nombre, apellido, asignatura, registrado],
    )


def guardar_datos_alumno(codigo: str, nombre: str, apellido: str, asignatura: str,
                         registrado: datetime | None = None) -> None:
    """Escribe nombre, apellido y asignatura. `registrado` solo cambia si se indica."""
    ejecutar(
        """
        update participante
           set nombre = %s,
               apellido = %s,
               asignatura = %s,
               registrado = coalesce(%s, registrado)
         where codigo = %s
        """,
        [nombre, apellido, asignatura, registrado, codigo],
    )


def quitar_datos_alumno(codigo: str) -> None:
    """El código deja de ser de un alumno (sus sesiones se conservan)."""
    ejecutar(
        """
        update participante
           set nombre = null, apellido = null, asignatura = null
         where codigo = %s
        """,
        [codigo],
    )


def borrar_si_sobra(codigo: str) -> int:
    """Borra la fila si ya no sirve: no es de un alumno y no tiene sesiones."""
    return ejecutar(
        """
        delete from participante p
         where p.codigo = %s
           and p.nombre is null
           and not exists (select 1 from sesion s where s.participante_id = p.codigo)
        """,
        [codigo],
    )
