"""
Reportes (solo lectores conectados: docente o equipo).

    GET /api/reports/incidents/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD
        -> [{sessionId, participantCode, student, experimentId, experiment, at, second,
             type, typeLabel, category, categoryLabel, task, detail}]
    GET /api/reports/export/?desde=AAAA-MM-DD&hasta=AAAA-MM-DD
        -> archivo Excel (.xlsx) con 3 hojas: Sesiones, Mediciones e Incidentes

Las dos fechas son opcionales; "hasta" incluye ese día completo.
"""

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from ..dto.reporte import RangoFechasDTO
from ..servicios import reporte_servicio

TIPO_EXCEL = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class IncidentesControlador(APIView):
    def get(self, request):
        rango = RangoFechasDTO.desde_query(request.query_params)
        return Response([i.a_json() for i in reporte_servicio.listar_incidentes(rango)])


class ExportarControlador(APIView):
    def get(self, request):
        rango = RangoFechasDTO.desde_query(request.query_params)
        contenido, nombre = reporte_servicio.generar_excel(rango)
        respuesta = HttpResponse(contenido, content_type=TIPO_EXCEL)
        # "attachment" hace que el navegador lo descargue con ese nombre.
        respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
        return respuesta
