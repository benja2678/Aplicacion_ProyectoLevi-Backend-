"""
Acceso al panel web, controlado por la tabla `lector` de la base del servidor.

- Entra quien esté en `lector`, con rol docente o equipo, y tenga clave.
- La clave se guarda cifrada (hash de Django) y se compara cifrada: nunca se guarda
  ni se compara en texto plano.
- Al entrar se entregan dos tokens JWT (access 30 min, refresh 8 h) que llevan el
  correo del lector. En CADA petición se vuelve a revisar la tabla: si se borra al
  lector o se deja su clave en NULL, pierde el acceso de inmediato.
- Cerrar sesión invalida el token refresh (lista negra de simplejwt).
"""

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken, Token

from ..dao import lector_dao
from ..dto.lector import ROLES_CON_ACCESO, CredencialesDTO, LectorAutenticado, LectorDTO, normalizar_correo
from ..utils.errores import DatosInvalidos, NoAutorizado

# Nombre del dato del token que guarda el correo del lector.
RECLAMO_LECTOR = 'lector'

CREDENCIALES_INCORRECTAS = 'Correo o contraseña incorrectos.'
SESION_NO_VALIDA = 'La sesión venció o se cerró. Vuelve a iniciar sesión.'


def _buscar(correo: str) -> LectorDTO | None:
    fila = lector_dao.obtener(correo)
    return LectorDTO.desde_fila(fila) if fila else None


# ------------------------------------------------------------------ #
# Sesión


def iniciar_sesion(credenciales: CredencialesDTO) -> dict:
    """Devuelve {"access": ..., "refresh": ...} o lanza NoAutorizado."""
    lector = _buscar(credenciales.correo)
    if lector is None or not lector.clave_cifrada:
        # Se cifra igual, para tardar lo mismo y no revelar qué correos existen.
        make_password(credenciales.clave)
        raise NoAutorizado(CREDENCIALES_INCORRECTAS)
    if not check_password(credenciales.clave, lector.clave_cifrada) or not lector.puede_entrar:
        raise NoAutorizado(CREDENCIALES_INCORRECTAS)

    refresh = RefreshToken()
    refresh[RECLAMO_LECTOR] = lector.correo
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


def renovar(refresh_texto) -> dict:
    """Con un refresh válido entrega un access nuevo: {"access": ...}."""
    refresh = _leer_refresh(refresh_texto)
    if _lector_habilitado(refresh.get(RECLAMO_LECTOR)) is None:
        raise NoAutorizado(SESION_NO_VALIDA)
    return {'access': str(refresh.access_token)}


def cerrar_sesion(refresh_texto) -> None:
    """Invalida el refresh: ya no sirve para pedir tokens nuevos."""
    _leer_refresh(refresh_texto).blacklist()


def lector_del_token(token: Token) -> LectorAutenticado | None:
    """El lector dueño de un token, si todavía puede entrar (se revisa la base)."""
    return _lector_habilitado(token.get(RECLAMO_LECTOR))


def _leer_refresh(texto) -> RefreshToken:
    if not isinstance(texto, str) or not texto:
        raise DatosInvalidos(campos={'refresh': ['Falta el token "refresh".']})
    try:
        return RefreshToken(texto)  # revisa firma, vencimiento y lista negra
    except TokenError:
        raise NoAutorizado(SESION_NO_VALIDA) from None


def _lector_habilitado(correo) -> LectorAutenticado | None:
    if not isinstance(correo, str) or not correo:
        return None
    lector = _buscar(correo)
    if lector is None or not lector.puede_entrar:
        return None
    return LectorAutenticado(correo=lector.correo, nombre=lector.nombre, rol=lector.rol)


# ------------------------------------------------------------------ #
# Claves (comando clave_lector)


def asignar_clave(correo: str, clave: str, nombre: str | None = None, rol: str = 'docente') -> LectorDTO:
    """Pone (o cambia) la clave de un lector. Si el correo no está en la tabla y se
    indica un nombre, lo agrega con ese rol."""
    correo = normalizar_correo(correo)
    if rol not in ROLES_CON_ACCESO:
        raise DatosInvalidos(f'El rol debe ser uno de: {", ".join(ROLES_CON_ACCESO)}.')
    try:
        validate_password(clave)
    except ValidationError as exc:
        raise DatosInvalidos(' '.join(exc.messages)) from None

    cifrada = make_password(clave)
    if lector_dao.guardar_clave(correo, cifrada) == 0:
        if not nombre:
            raise DatosInvalidos(
                f'El correo {correo} no está en la tabla lector. Para agregarlo, indica también su nombre.'
            )
        lector_dao.crear(correo, nombre.strip(), rol, cifrada)
    return _buscar(correo)
