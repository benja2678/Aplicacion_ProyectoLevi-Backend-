"""
Formato de las respuestas de la API.

El JSON siempre va en UTF-8, pero DRF no lo dice en el encabezado Content-Type.
Algunos programas (por ejemplo Windows PowerShell 5.1) entonces suponen otra
codificación y muestran "SesiÃ³n" en vez de "Sesión". Indicarlo lo evita.
"""

from rest_framework.renderers import JSONRenderer


class UTF8JSONRenderer(JSONRenderer):
    """JSONRenderer que responde `Content-Type: application/json; charset=utf-8`."""

    charset = 'utf-8'
