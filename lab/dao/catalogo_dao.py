"""Catálogo de experimentos y sus tareas (levi-db-scripts v2.0 y v2.1). Solo lectura."""

from .base import consultar, consultar_uno


def obtener_experimento(experimento_id: str) -> dict | None:
    return consultar_uno(
        """
        select id, titulo
          from experimento
         where id = %s
        """,
        [experimento_id],
    )


def tareas_del_experimento(experimento_id: str) -> dict[str, int]:
    """{código de la tarea: id} de las mediciones del experimento (V1 -> 7, ...)."""
    filas = consultar(
        """
        select id, codigo
          from tarea
         where experimento_id = %s
         order by orden
        """,
        [experimento_id],
    )
    return {f['codigo']: f['id'] for f in filas}
