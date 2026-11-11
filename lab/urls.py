"""Rutas de la API. Todas quedan bajo /api/ (ver config/urls.py)."""

from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .controladores import alumnos, estado, sesiones

urlpatterns = [
    path('health/', estado.HealthControlador.as_view(), name='health'),
    path('auth/login/', estado.LoginControlador.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('auth/me/', estado.YoControlador.as_view(), name='me'),

    path('students/', alumnos.AlumnosControlador.as_view(), name='alumnos'),
    path('students/<str:codigo>/', alumnos.AlumnoControlador.as_view(), name='alumno'),

    # Estas dos van ANTES de sessions/<id>/ para que no se confundan con un id.
    path('sessions/ingest/', sesiones.RecibirSesionControlador.as_view(), name='session-ingest'),
    path('sessions/import/', sesiones.ImportarSesionesControlador.as_view(), name='session-import'),
    path('sessions/', sesiones.SesionesControlador.as_view(), name='sesiones'),
    # El id lleva ":" (de startedAt); <str:...> acepta todo menos "/".
    path('sessions/<str:id_sesion>/', sesiones.SesionControlador.as_view(), name='sesion'),
]
