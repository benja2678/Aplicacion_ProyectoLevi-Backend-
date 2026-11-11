"""
Acceso al panel web, controlado por la tabla `lector` de la base del servidor.

- Entra quien esté en `lector`, con rol docente o equipo, y tenga clave.
- La clave se guarda cifrada (hash de Django) y se compara cifrada: nunca se guarda
  ni se compara en texto plano.
- Al entrar se entregan dos tokens JWT (access 30 min, refresh 8 h) que llevan el
  correo del lector. En CADA petición se vuelve a revisar la tabla: si se borra al
  lector o se deja su clave en NULL, pierde el acceso de inmediato.
- Cerrar sesión revoca el token refresh (tabla token_revocado).
- El login tiene un límite de intentos por IP (tabla intento_login, LOGIN_RATE).
"""

import math
from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken, Token

from ..dao import intento_login_dao, lector_dao, token_dao
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
    """Revoca el refresh: ya no sirve para pedir tokens nuevos."""
    refresh = _leer_refresh(refresh_texto)
    token_dao.revocar(refresh['jti'], datetime.fromtimestamp(refresh['exp'], tz=UTC))


def lector_del_token(token: Token) -> LectorAutenticado | None:
    """El lector dueño de un token, si todavía puede entrar (se revisa la base)."""
    return _lector_habilitado(token.get(RECLAMO_LECTOR))


def _leer_refresh(texto) -> RefreshToken:
    if not isinstance(texto, str) or not texto:
        raise DatosInvalidos(campos={'refresh': ['Falta el token "refresh".']})
    try:
        refresh = RefreshToken(texto)  # revisa firma, tipo y vencimiento
    except TokenError:
        raise NoAutorizado(SESION_NO_VALIDA) from None
    if token_dao.esta_revocado(refresh['jti']):  # se cerró esa sesión
        raise NoAutorizado(SESION_NO_VALIDA)
    return refresh


def _lector_habilitado(correo) -> LectorAutenticado | None:
    if not isinstance(correo, str) or not correo:
        return None
    lector = _buscar(correo)
    if lector is None or not lector.puede_entrar:
        return None
    return LectorAutenticado(correo=lector.correo, nombre=lector.nombre, rol=lector.rol)


# ------------------------------------------------------------------ #
# Límite de intentos de login


_UNIDADES = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}


def _limite_login() -> tuple[int, int]:
    """LOGIN_RATE "5/min" -> (5 intentos, 60 segundos)."""
    cantidad, periodo = settings.LOGIN_RATE.split('/')
    return int(cantidad), _UNIDADES[periodo.strip()[0]]


def registrar_intento_login(ip: str) -> int | None:
    """Anota un intento de login de esa IP. Devuelve None si puede intentar, o cuántos
    segundos debe esperar si ya usó todos los intentos del período."""
    limite, ventana = _limite_login()
    recientes = intento_login_dao.momentos_recientes(ip, ventana)
    if len(recientes) >= limite:
        # Puede volver a intentar cuando el más antiguo de los últimos `limite` salga del período.
        libera = recientes[-limite]
        return max(1, math.ceil(ventana - (timezone.now() - libera).total_seconds()))
    intento_login_dao.registrar(ip)
    intento_login_dao.borrar_viejos(ventana)
    return None


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
