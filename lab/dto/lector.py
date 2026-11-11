"""
DTO de los lectores: las personas que pueden entrar al panel web
(tabla `lector` de levi-db-scripts, v2.0 + v2.4).

    CredencialesDTO     lo que envía la pantalla de login: correo y contraseña.
    LectorDTO           un lector tal como está en la base (sin mostrar su clave).
    LectorAutenticado   el lector conectado (request.user en los controladores).
"""

from dataclasses import dataclass
from typing import Any

from ..utils.errores import DatosInvalidos

# Roles de la tabla lector que pueden entrar al panel web.
ROLES_CON_ACCESO = ('docente', 'equipo')


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


@dataclass(frozen=True)
class CredencialesDTO:
    correo: str
    clave: str

    @classmethod
    def desde_json(cls, datos: Any) -> 'CredencialesDTO':
        """Acepta {"email", "password"} y también {"username", "password"}, que es lo
        que envía la pantalla de login del panel."""
        if not isinstance(datos, dict):
            raise DatosInvalidos('Se esperaba un objeto JSON con el correo y la contraseña.')
        campo = 'email' if 'email' in datos else 'username'
        correo, clave = datos.get(campo), datos.get('password')
        errores = {}
        if not isinstance(correo, str) or not correo.strip():
            errores[campo] = ['Escribe tu correo.']
        if not isinstance(clave, str) or not clave:
            errores['password'] = ['Escribe tu contraseña.']
        if errores:
            raise DatosInvalidos(campos=errores)
        return cls(correo=normalizar_correo(correo), clave=clave)


@dataclass(frozen=True)
class LectorDTO:
    correo: str
    nombre: str
    rol: str
    clave_cifrada: str | None  # hash de la clave; None = no tiene clave (no puede entrar)

    @classmethod
    def desde_fila(cls, fila: dict) -> 'LectorDTO':
        return cls(correo=fila['email'], nombre=fila['nombre'], rol=fila['rol'], clave_cifrada=fila['clave'])

    @property
    def puede_entrar(self) -> bool:
        return bool(self.clave_cifrada) and self.rol in ROLES_CON_ACCESO


@dataclass(frozen=True)
class LectorAutenticado:
    """El lector conectado. Django REST Framework lo usa como `request.user`."""

    correo: str
    nombre: str
    rol: str

    is_authenticated = True
    is_anonymous = False
    is_active = True

    @property
    def pk(self) -> str:
        return self.correo

    def a_json(self) -> dict:
        # "username" es el nombre que espera el panel (src/data/AuthContext.tsx).
        return {'username': self.correo, 'nombre': self.nombre, 'rol': self.rol}
