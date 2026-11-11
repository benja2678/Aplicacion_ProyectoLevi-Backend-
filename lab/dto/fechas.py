"""
Fechas en el formato que usan Unity y el panel web: hora local SIN zona horaria
("2026-11-05T10:31:12").
"""

from datetime import datetime

from django.utils import timezone

FORMATO_LOCAL = '%Y-%m-%dT%H:%M:%S'


def a_hora_local(momento: datetime) -> str:
    """Un instante guardado con zona (timestamptz) escrito en hora de Chile, sin zona."""
    return timezone.localtime(momento).strftime(FORMATO_LOCAL)


def texto_del_visor(fecha: datetime) -> str:
    """Una fecha del visor (timestamp sin zona) escrita igual que la envía Unity.

    Unity manda segundos enteros ("2026-11-10T23:07:51"). Si un archivo cargado a mano
    traía fracciones de segundo, se conservan (".250").
    """
    if fecha.microsecond == 0:
        return fecha.strftime(FORMATO_LOCAL)
    if fecha.microsecond % 1000 == 0:
        return fecha.isoformat(timespec='milliseconds')
    return fecha.isoformat()


def leer_fecha_del_visor(texto: str) -> datetime:
    """Convierte "2026-11-10T23:07:51" en fecha. Lanza ValueError si no es una fecha
    válida o si trae zona horaria (el visor siempre usa hora local)."""
    fecha = datetime.fromisoformat(texto.strip())
    if fecha.tzinfo is not None:
        raise ValueError('con zona horaria')
    return fecha
