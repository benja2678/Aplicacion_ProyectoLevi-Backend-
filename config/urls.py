"""Rutas principales: /api/ (la API del laboratorio) y /admin/ (panel de Django)."""

from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Laboratorio VR · Administración'
admin.site.site_title = 'Laboratorio VR'
admin.site.index_title = 'Datos del laboratorio'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('lab.urls')),
]
