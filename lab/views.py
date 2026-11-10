"""
Endpoints de la API (todos bajo /api/).

Sin token:
    GET  /api/health/              ¿está vivo el backend? (lo usa Docker)
    POST /api/auth/login/          usuario + contraseña -> tokens (con límite de intentos)
    POST /api/auth/refresh/        token refresh -> nuevo token access
    POST /api/auth/logout/         invalida el token refresh
Con la llave de Unity (X-Api-Key), y nada más:
    POST /api/sessions/ingest/     guarda una sesión: 201 nueva / 409 ya existía
Con token del profesor (todo lo demás):
    GET  /api/auth/me/
    GET/POST        /api/students/
    PUT/DELETE      /api/students/<id>/
    GET             /api/sessions/
    DELETE          /api/sessions/<id>/
    POST            /api/sessions/import/
"""

from django.db import IntegrityError, transaction
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .auth import HasUnityApiKey
from .models import Session, Student
from .serializers import SessionSerializer, StudentSerializer, TeacherTokenSerializer
from .session_logs import InvalidSessionLog, parse_json, save_session, validate_log

# ------------------------------------------------------------------ #
# Estado y autenticación


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'status': 'ok'})


class LoginView(TokenObtainPairView):
    """Entrega {access, refresh}. Limita los intentos por IP (LOGIN_RATE, por defecto 5/min)."""

    serializer_class = TeacherTokenSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class MeView(APIView):
    def get(self, request):
        user = request.user
        return Response({'username': user.get_username(), 'nombre': user.get_full_name()})


# ------------------------------------------------------------------ #
# Alumnos


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    http_method_names = ['get', 'post', 'put', 'delete', 'head', 'options']

    def perform_create(self, serializer):
        self._save(serializer)

    def perform_update(self, serializer):
        self._save(serializer)

    @staticmethod
    def _save(serializer):
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            # Dos peticiones con el mismo código al mismo tiempo.
            raise ValidationError({'codigoParticipante': ['Ese código ya está asignado a otro alumno.']})


# ------------------------------------------------------------------ #
# Sesiones


class SessionViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    queryset = Session.objects.all()
    serializer_class = SessionSerializer
    # El id lleva ":" (de startedAt) y podría llevar "."; se acepta todo menos "/".
    lookup_value_regex = '[^/]+'


class ImportSessionsView(APIView):
    """Botón "Cargar sesiones". Recibe {"files": [{"name": "...", "text": "<contenido .json>"}]}.

    Cada archivo puede traer una sesión o una lista de sesiones.
    Responde {"added": n, "duplicated": n, "invalid": [{"file", "reason"}]}.
    """

    def post(self, request):
        files = request.data.get('files') if isinstance(request.data, dict) else None
        if not isinstance(files, list):
            raise ValidationError({'detail': 'Se esperaba {"files": [{"name": ..., "text": ...}]}.'})

        result = {'added': 0, 'duplicated': 0, 'invalid': []}
        for f in files:
            name = str(f.get('name') or 'archivo') if isinstance(f, dict) else 'archivo'
            text = f.get('text') if isinstance(f, dict) else None
            if not isinstance(text, str):
                result['invalid'].append({'file': name, 'reason': 'Archivo vacío o ilegible'})
                continue
            try:
                data = parse_json(text)
            except ValueError:
                result['invalid'].append({'file': name, 'reason': 'No es un JSON válido'})
                continue

            for item in data if isinstance(data, list) else [data]:
                try:
                    log = validate_log(item)
                except InvalidSessionLog as exc:
                    result['invalid'].append({'file': name, 'reason': str(exc)})
                    continue
                _, created = save_session(log, Session.SOURCE_IMPORTADA)
                result['added' if created else 'duplicated'] += 1
        return Response(result)


class IngestSessionView(APIView):
    """Envío automático desde Unity (SessionUploader).

    - Autenticación: SOLO la llave X-Api-Key (no usa tokens de usuario).
    - Cuerpo: el JSON del SessionLog tal cual (BodyTemplate = {session}).
      Se lee directamente, así funciona aunque Unity no envíe Content-Type: application/json.
    - Respuestas: 201 sesión nueva · 409 ya existía · 400 JSON inválido · 403 llave incorrecta.
      Unity da la sesión por entregada con 2xx o 409.
    """

    authentication_classes = []
    permission_classes = [HasUnityApiKey]

    def post(self, request):
        try:
            data = parse_json(request.body)
        except (ValueError, UnicodeDecodeError):
            return Response({'detail': 'El cuerpo no es un JSON válido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            log = validate_log(data)
        except InvalidSessionLog as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        session_id, created = save_session(log, Session.SOURCE_VISOR)
        if created:
            return Response({'id': session_id, 'detail': 'Sesión guardada.'}, status=status.HTTP_201_CREATED)
        return Response({'id': session_id, 'detail': 'La sesión ya existía.'}, status=status.HTTP_409_CONFLICT)
