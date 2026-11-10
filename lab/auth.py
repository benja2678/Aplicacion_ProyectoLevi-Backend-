"""
Reglas de acceso.

1. Profesor (web): inicia sesión con usuario y contraseña y recibe tokens JWT.
   Solo pueden entrar usuarios activos marcados como "staff" (la cuenta del profesor).
2. Unity (Meta Quest): no inicia sesión. Envía la llave fija UNITY_API_KEY en el
   encabezado X-Api-Key, y esa llave SOLO sirve para enviar sesiones.
"""

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission


def teacher_can_login(user) -> bool:
    """Quién puede recibir un token: solo cuentas activas de tipo staff (el profesor).
    Se usa en SIMPLE_JWT['USER_AUTHENTICATION_RULE']."""
    return user is not None and user.is_active and user.is_staff


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
