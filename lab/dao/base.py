"""Ayudas para ejecutar SQL con la conexión de Django (la misma que usa el login)."""

from collections.abc import Iterable, Sequence
from typing import Any

from django.db import connection


def consultar(sql: str, parametros: Sequence[Any] = ()) -> list[dict]:
    """Ejecuta un SELECT (o un INSERT ... RETURNING) y devuelve las filas como diccionarios."""
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        columnas = [c[0] for c in cursor.description]
        return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def consultar_uno(sql: str, parametros: Sequence[Any] = ()) -> dict | None:
    filas = consultar(sql, parametros)
    return filas[0] if filas else None


def ejecutar(sql: str, parametros: Sequence[Any] = ()) -> int:
    """Ejecuta un INSERT/UPDATE/DELETE y devuelve cuántas filas cambió."""
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        return cursor.rowcount


def ejecutar_varios(sql: str, filas: Iterable[Sequence[Any]]) -> None:
    """Ejecuta el mismo INSERT para muchas filas de una vez."""
    filas = list(filas)
    if filas:
        with connection.cursor() as cursor:
            cursor.executemany(sql, filas)
