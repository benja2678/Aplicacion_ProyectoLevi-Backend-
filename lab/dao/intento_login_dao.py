"""
Tabla intento_login (levi-db-scripts v2.5): intentos de inicio de sesión por IP.
"""

from datetime import datetime

from .base import consultar, ejecutar


def momentos_recientes(ip: str, segundos: int) -> list[datetime]:
    """Momentos de los intentos de esa IP en los últimos `segundos`, del más antiguo al más nuevo."""
    filas = consultar(
        """
        select momento
          from intento_login
         where ip = %s
           and momento > now() - make_interval(secs => %s)
         order by momento
        """,
        [ip, segundos],
    )
    return [f['momento'] for f in filas]


def registrar(ip: str) -> None:
    ejecutar('insert into intento_login (ip) values (%s)', [ip])


def borrar_viejos(segundos: int) -> int:
    """Borra los intentos (de cualquier IP) más antiguos que `segundos`."""
    return ejecutar('delete from intento_login where momento < now() - make_interval(secs => %s)', [segundos])
