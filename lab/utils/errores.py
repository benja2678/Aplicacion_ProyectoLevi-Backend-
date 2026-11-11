"""
Errores del negocio.

Los lanzan los DTO (al validar lo que llega) y los servicios (al aplicar las reglas).
Ninguna de esas capas sabe de HTTP: el controlador los convierte en la respuesta
correspondiente (ver controladores/errores.py).

    DatosInvalidos -> 400 Bad Request
    NoAutorizado   -> 401 Unauthorized
    NoEncontrado   -> 404 Not Found
"""


class ErrorDeNegocio(Exception):
    """Base de los errores que se le pueden mostrar al usuario tal cual."""


class DatosInvalidos(ErrorDeNegocio):
    """Lo recibido no cumple las reglas.

    - `detalle`: un mensaje general, se responde como {"detail": "..."}.
    - `campos`:  mensajes por campo, se responde como {"campo": ["..."]}
                 (la misma forma que usaba Django REST Framework; el frontend la entiende).
    """

    def __init__(self, detalle: str = '', campos: dict[str, list[str]] | None = None):
        self.detalle = detalle
        self.campos = campos or {}
        texto = detalle or ' '.join(m for mensajes in self.campos.values() for m in mensajes)
        super().__init__(texto)

    def como_respuesta(self) -> dict:
        return dict(self.campos) if self.campos else {'detail': self.detalle}


class NoAutorizado(ErrorDeNegocio):
    """Correo o contraseña incorrectos, o sesión vencida / cerrada."""


class NoEncontrado(ErrorDeNegocio):
    """El alumno o la sesión pedida no existe."""

    def __init__(self, detalle: str = 'No encontrado.'):
        super().__init__(detalle)
