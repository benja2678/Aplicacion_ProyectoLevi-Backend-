"""
Estado del backend y sesión del lector (docente o equipo).

    GET  /api/health/        público                   {"status": "ok"}
    POST /api/auth/login/    público (con límite)      {email|username, password} -> {access, refresh}
    POST /api/auth/refresh/  público                   {refresh} -> {access}
    POST /api/auth/logout/   público                   {refresh} -> lo invalida
    GET  /api/auth/me/       con token                 {username, nombre, rol}
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from ..dto.lector import CredencialesDTO
from ..servicios import acceso_servicio


class PublicoControlador(APIView):
    """Base de los endpoints que no piden token."""

    authentication_classes = []
    permission_classes = [AllowAny]


def _refresh_de(request):
    return request.data.get('refresh') if isinstance(request.data, dict) else None


class HealthControlador(PublicoControlador):
    def get(self, request):
        return Response({'status': 'ok'})


class LoginControlador(PublicoControlador):
    """Limita los intentos por IP (LOGIN_RATE, por defecto 5 por minuto)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        return Response(acceso_servicio.iniciar_sesion(CredencialesDTO.desde_json(request.data)))


class RenovarControlador(PublicoControlador):
    def post(self, request):
        return Response(acceso_servicio.renovar(_refresh_de(request)))


class CerrarSesionControlador(PublicoControlador):
    def post(self, request):
        acceso_servicio.cerrar_sesion(_refresh_de(request))
        return Response({})


class YoControlador(APIView):
    def get(self, request):
        return Response(request.user.a_json())
