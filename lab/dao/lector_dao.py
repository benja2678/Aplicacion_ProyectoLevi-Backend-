"""
Tabla lector (levi-db-scripts v2.0 + v2.4): quién puede entrar al panel web.

    email   correo (llave)        nombre   nombre para mostrar
    rol     docente | equipo      clave    hash de la contraseña (NULL = sin acceso)
"""

from .base import consultar_uno, ejecutar

_COLUMNAS = 'email, nombre, rol, clave'


def obtener(correo: str) -> dict | None:
    """El lector con ese correo (sin importar mayúsculas), o None."""
    return consultar_uno(
        f"""
        select {_COLUMNAS}
          from lector
         where lower(email) = lower(%s)
        """,
        [correo],
    )


def crear(correo: str, nombre: str, rol: str, clave_cifrada: str) -> None:
    ejecutar(
        """
        insert into lector (email, nombre, rol, clave)
        values (%s, %s, %s, %s)
        """,
        [correo, nombre, rol, clave_cifrada],
    )


def guardar_clave(correo: str, clave_cifrada: str) -> int:
    """Cambia la clave (ya cifrada). Devuelve cuántas filas cambió (0 si no existe)."""
    return ejecutar(
        """
        update lector
           set clave = %s
         where lower(email) = lower(%s)
        """,
        [clave_cifrada, correo],
    )
