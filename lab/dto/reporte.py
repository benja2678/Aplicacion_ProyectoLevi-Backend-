"""
DTO de los reportes (incidentes y exportación a Excel).

    RangoFechasDTO   el rango pedido: ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD (los dos opcionales,
                     y "hasta" incluye ese día completo). Se compara con el inicio de la sesión.
    IncidenteDTO     un incidente de una sesión: falla del circuito (evento 'diagnostico') o
                     registro rechazado por usar mal el multímetro (evento 'rechazo').
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from ..utils.errores import DatosInvalidos
from .fechas import texto_del_visor

# Nombres en español de cada tipo de incidente (los códigos son los que escribe Unity).
CATEGORIAS = {
    # Fallas del circuito (evento 'diagnostico')
    'ShortCircuit': 'Cortocircuito',
    'ExcessivePower': 'Potencia excesiva en un componente',
    'ConflictingSources': 'Fuentes en conflicto',
    'LedOvercurrent': 'Corriente excesiva en el LED',
    'LedReverseOverVoltage': 'LED con tensión inversa excesiva',
    # Registros rechazados (evento 'rechazo')
    'WrongPhase': 'Registro fuera de la etapa de laboratorio',
    'MeterOff': 'Multímetro apagado',
    'WrongMode': 'Multímetro en el modo incorrecto',
    'ProbesDisconnected': 'Puntas desconectadas',
    'RedProbeDisconnected': 'Punta roja desconectada',
    'BlackProbeDisconnected': 'Punta negra desconectada',
    'OverRange': 'Fuera de la escala del multímetro',
}

TIPOS = {'diagnostico': 'Falla del circuito', 'rechazo': 'Multímetro mal usado'}


def _fecha(datos: Any, campo: str) -> date | None:
    valor = datos.get(campo) if hasattr(datos, 'get') else None
    if valor in (None, ''):
        return None
    try:
        return date.fromisoformat(str(valor).strip())
    except ValueError:
        raise DatosInvalidos(campos={campo: ['Usa el formato AAAA-MM-DD (por ejemplo 2026-11-05).']}) from None


@dataclass(frozen=True)
class RangoFechasDTO:
    desde: date | None = None
    hasta: date | None = None

    @classmethod
    def desde_query(cls, datos: Any) -> 'RangoFechasDTO':
        rango = cls(desde=_fecha(datos, 'desde'), hasta=_fecha(datos, 'hasta'))
        if rango.desde and rango.hasta and rango.desde > rango.hasta:
            raise DatosInvalidos(campos={'hasta': ['"Hasta" no puede ser anterior a "desde".']})
        return rango

    @property
    def inicio(self) -> datetime | None:
        """Desde el comienzo del día "desde"."""
        return datetime.combine(self.desde, datetime.min.time()) if self.desde else None

    @property
    def fin(self) -> datetime | None:
        """Hasta el comienzo del día SIGUIENTE a "hasta" (sin incluirlo): así "hasta" cuenta completo."""
        return datetime.combine(self.hasta + timedelta(days=1), datetime.min.time()) if self.hasta else None

    def en_texto(self) -> str:
        """Para el nombre del archivo: "2026-11-01_a_2026-11-30", "desde_2026-11-01", "todo"."""
        if self.desde and self.hasta:
            return f'{self.desde.isoformat()}_a_{self.hasta.isoformat()}'
        if self.desde:
            return f'desde_{self.desde.isoformat()}'
        if self.hasta:
            return f'hasta_{self.hasta.isoformat()}'
        return 'todo'


@dataclass(frozen=True)
class IncidenteDTO:
    id_sesion: str           # el mismo id que usa el panel: participantCode_experimentId_startedAt
    codigo: str              # código del visor (A001…)
    alumno: str              # nombre y apellido, o '' si el código no es de ningún alumno
    experimento_id: str
    experimento: str
    momento: datetime        # inicio de la sesión + segundos del evento
    segundo: float           # segundos desde el inicio de la sesión
    tipo: str                # diagnostico | rechazo
    categoria: str           # ShortCircuit, OverRange…
    medicion: str            # tarea afectada (solo rechazos), ej. V2
    detalle: str             # texto completo que escribió el visor

    @property
    def tipo_texto(self) -> str:
        return TIPOS.get(self.tipo, self.tipo)

    @property
    def categoria_texto(self) -> str:
        return CATEGORIAS.get(self.categoria, self.categoria)

    def a_json(self) -> dict:
        return {
            'sessionId': self.id_sesion,
            'participantCode': self.codigo,
            'student': self.alumno,
            'experimentId': self.experimento_id,
            'experiment': self.experimento,
            'at': texto_del_visor(self.momento),
            'second': self.segundo,
            'type': self.tipo,
            'typeLabel': self.tipo_texto,
            'category': self.categoria,
            'categoryLabel': self.categoria_texto,
            'task': self.medicion,
            'detail': self.detalle,
        }
