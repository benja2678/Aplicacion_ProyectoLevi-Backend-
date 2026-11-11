"""Rutas principales: todo está bajo /api/ (la API del laboratorio)."""

from django.urls import include, path

urlpatterns = [
    path('api/', include('lab.urls')),
]
