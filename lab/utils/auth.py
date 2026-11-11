"""
Reglas de acceso a la API.

1. Lectores (panel web): inician sesión con correo y contraseña de la tabla `lector`
   y reciben tokens JWT. En cada petición se revisa que sigan habilitados en la base
   (ver servicios/acceso_servicio.py). Pueden entrar los roles docente y equipo.
2. Unity (Meta Quest): no inicia sesión. Envía la llave fija UNITY_API_KEY en el
   encabezado X-Api-Key, y esa llave SOLO sirve para enviar sesiones.
"""

import hmac

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission
from rest_framework_simplejwt.authentication import JWTAuthentication

from ..dto.lector import ROLES_CON_ACCESO, LectorAutenticado


class JWTLectorAuthentication(JWTAuthentication):
    """Lee el token "Authorization: Bearer ..." y busca a su lector en la tabla `lector`
    (en vez de en los usuarios de Django)."""

    def get_user(self, validated_token):
        from ..servicios import acceso_servicio  # aquí, para no crear un ciclo de imports

        lector = acceso_servicio.lector_del_token(validated_token)
        if lector is None:
            raise AuthenticationFailed('Tu acceso ya no es válido. Vuelve a iniciar sesión.', code='sin_acceso')
        return lector


class EsLector(BasePermission):
    """Permite la petición solo a un lector conectado con rol docente o equipo."""

    def has_permission(self, request, view) -> bool:
        usuario = request.user
        return isinstance(usuario, LectorAutenticado) and usuario.rol in ROLES_CON_ACCESO


class HasUnityApiKey(BasePermission):
    """Permite la petición solo si trae X-Api-Key igual a UNITY_API_KEY."""

    message = 'Llave de Unity inválida o ausente (encabezado X-Api-Key).'

    def has_permission(self, request, view) -> bool:
        expected = settings.UNITY_API_KEY
        given = request.headers.get('X-Api-Key', '')
        if not expected or not given:
            return False
        # compare_digest compara en tiempo constante (evita adivinar la llave midiendo tiempos).
        return hmac.compare_digest(given.encode(), expected.encode())
