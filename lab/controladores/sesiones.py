"""
Sesiones.

Con token del profesor:
    GET    /api/sessions/          lista [{id, log, source, receivedAt}]
    DELETE /api/sessions/<id>/     borrar (id = participantCode_experimentId_startedAt)
    POST   /api/sessions/import/   "Cargar sesiones": {"files": [{name, text}]}
                                   -> {added, duplicated, invalid: [{file, reason}]}
Solo con la llave de Unity (X-Api-Key):
    POST   /api/sessions/ingest/   el JSON de la sesión tal cual
                                   -> 201 nueva / 409 ya existía / 400 inválida / 403 llave
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..utils.auth import HasUnityApiKey
from ..servicios import sesion_servicio


class SesionesControlador(APIView):
    def get(self, request):
        return Response([s.a_json() for s in sesion_servicio.listar()])


class SesionControlador(APIView):
    def delete(self, request, id_sesion: str):
        sesion_servicio.eliminar(id_sesion)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImportarSesionesControlador(APIView):
    def post(self, request):
        archivos = request.data.get('files') if isinstance(request.data, dict) else None
        return Response(sesion_servicio.importar(archivos).a_json())


class RecibirSesionControlador(APIView):
    """Envío automático desde Unity (SessionUploader).

    - Solo la llave X-Api-Key (no usa tokens de usuario).
    - El cuerpo se lee directo, así funciona aunque Unity no envíe
      Content-Type: application/json.
    - Unity da la sesión por entregada con 2xx o 409.
    """

    authentication_classes = []
    permission_classes = [HasUnityApiKey]

    def post(self, request):
        id_sesion, creada = sesion_servicio.recibir_del_visor(request.body)
        if creada:
            return Response({'id': id_sesion, 'detail': 'Sesión guardada.'}, status=status.HTTP_201_CREATED)
        return Response({'id': id_sesion, 'detail': 'La sesión ya existía.'}, status=status.HTTP_409_CONFLICT)
