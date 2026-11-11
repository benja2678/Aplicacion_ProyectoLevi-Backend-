"""
Tabla token_revocado (levi-db-scripts v2.5): tokens "refresh" de sesiones cerradas.
"""

from datetime import datetime

from .base import consultar_uno, ejecutar


def revocar(jti: str, expira: datetime) -> None:
    """Anota el token como revocado y, de paso, borra los que ya vencieron."""
    ejecutar(
        """
        insert into token_revocado (jti, expira)
        values (%s, %s)
        on conflict (jti) do nothing
        """,
        [jti, expira],
    )
    ejecutar('delete from token_revocado where expira < now()')


def esta_revocado(jti: str) -> bool:
    fila = consultar_uno('select 1 as si from token_revocado where jti = %s', [jti])
    return fila is not None
