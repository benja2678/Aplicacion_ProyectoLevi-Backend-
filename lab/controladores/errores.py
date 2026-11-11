"""Convierte los errores del negocio en respuestas HTTP (settings: EXCEPTION_HANDLER)."""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from ..utils.errores import DatosInvalidos, NoAutorizado, NoEncontrado


def manejar_errores(exc, context):
    if isinstance(exc, DatosInvalidos):
        return Response(exc.como_respuesta(), status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, NoAutorizado):
        return Response({'detail': str(exc)}, status=status.HTTP_401_UNAUTHORIZED)
    if isinstance(exc, NoEncontrado):
        return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    # Lo demás (sin token, sin permiso, método no permitido…) lo responde DRF como siempre.
    return exception_handler(exc, context)
