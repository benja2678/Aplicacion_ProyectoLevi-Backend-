"""Estado del backend y sesión del profesor."""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class HealthControlador(APIView):
    """GET /api/health/ -> {"status": "ok"}. Público (lo usan Docker y las pruebas)."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok'})


class LoginSerializer(TokenObtainPairSerializer):
    """Login del profesor con un mensaje de error claro y en español."""

    default_error_messages = {'no_active_account': 'Usuario o contraseña incorrectos.'}


class LoginControlador(TokenObtainPairView):
    """POST /api/auth/login/ -> {access, refresh}. Limita los intentos por IP (LOGIN_RATE)."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class YoControlador(APIView):
    """GET /api/auth/me/ -> datos del usuario conectado."""

    def get(self, request):
        user = request.user
        return Response({'username': user.get_username(), 'nombre': user.get_full_name()})
