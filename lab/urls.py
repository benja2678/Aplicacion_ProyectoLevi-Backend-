"""Rutas de la API. Todas quedan bajo /api/ (ver config/urls.py)."""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from . import views

router = DefaultRouter()
router.include_root_view = False  # sin página índice de la API
router.register('students', views.StudentViewSet, basename='student')
router.register('sessions', views.SessionViewSet, basename='session')

urlpatterns = [
    path('health/', views.HealthView.as_view(), name='health'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/logout/', TokenBlacklistView.as_view(), name='logout'),
    path('auth/me/', views.MeView.as_view(), name='me'),
    # Estas dos van ANTES del router para que no se confundan con /sessions/<id>/.
    path('sessions/ingest/', views.IngestSessionView.as_view(), name='session-ingest'),
    path('sessions/import/', views.ImportSessionsView.as_view(), name='session-import'),
    path('', include(router.urls)),
]
