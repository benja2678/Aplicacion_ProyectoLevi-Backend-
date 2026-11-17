"""
DTO de los reportes (incidentes y exportación a Excel).

    RangoFechasDTO   el rango pedido: ?desde=AAAA-MM-DD&hasta=AAAA-MM-DD (los dos opcionales,
                     y "hasta" incluye ese día completo). Se compara con el inicio de la sesión.
    IncidenteDTO     un incidente de una sesión: falla del circuito (evento 'diagnostico') o
                     registro rechazado por usar mal el multímetro (evento 'rechazo').
    SesionResumenDTO las métricas de UNA sesión de un alumno (para su hoja del Excel).
    AlumnoResumenDTO las métricas de un alumno en el rango: sus sesiones, mediciones e incidentes.
"""

from dataclasses import dataclass, field
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

    def descripcion(self) -> str:
        """Para leer en el Excel: "Del 01-11-2026 al 30-11-2026", "Todas las fechas"…"""
        def dia(d: date) -> str:
            return d.strftime('%d-%m-%Y')
        if self.desde and self.hasta:
            return f'Del {dia(self.desde)} al {dia(self.hasta)}'
        if self.desde:
            return f'Desde el {dia(self.desde)}'
        if self.hasta:
            return f'Hasta el {dia(self.hasta)}'
        return 'Todas las fechas'


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


def _porcentaje(parte: int, total: int) -> float | None:
    """0.75 = 75 %. None si no había nada que medir (para no inventar un 0 %)."""
    return parte / total if total else None


@dataclass(frozen=True)
class SesionResumenDTO:
    numero: int                  # 1, 2, 3… en el orden en que el alumno hizo sus sesiones
    experimento_id: str
    experimento: str
    inicio: datetime
    completada: bool
    duracion_s: float | None
    correctas: int
    mediciones: int
    fallas: int                  # fallas del circuito (eventos 'diagnostico')
    mal_uso: int                 # registros rechazados por usar mal el multímetro
    ayudas: int
    intento: int                 # n.º de intento en ese experimento (1 = primera vez)

    @property
    def etiqueta(self) -> str:
        """Nombre corto para los gráficos: "Sesión 1 · N1"."""
        return f'Sesión {self.numero} · {self.experimento_id}'

    @property
    def aciertos(self) -> float | None:
        return _porcentaje(self.correctas, self.mediciones)

    @property
    def duracion_min(self) -> float | None:
        return self.duracion_s / 60 if self.duracion_s is not None else None


@dataclass(frozen=True)
class AlumnoResumenDTO:
    codigo: str
    alumno: str                  # nombre y apellido; '' si el código no es de ningún alumno
    asignatura: str
    sesiones: list[SesionResumenDTO] = field(default_factory=list)
    mediciones: list[dict] = field(default_factory=list)       # filas de reporte_dao.mediciones
    incidentes: list[IncidenteDTO] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        return self.alumno or f'Sin registrar ({self.codigo})'

    @property
    def completadas(self) -> int:
        return sum(1 for s in self.sesiones if s.completada)

    @property
    def correctas(self) -> int:
        return sum(s.correctas for s in self.sesiones)

    @property
    def total_mediciones(self) -> int:
        return sum(s.mediciones for s in self.sesiones)

    @property
    def aciertos(self) -> float | None:
        return _porcentaje(self.correctas, self.total_mediciones)

    @property
    def tiempo_promedio_min(self) -> float | None:
        minutos = [s.duracion_min for s in self.sesiones if s.duracion_min is not None]
        return sum(minutos) / len(minutos) if minutos else None

    @property
    def fallas(self) -> int:
        return sum(s.fallas for s in self.sesiones)

    @property
    def mal_uso(self) -> int:
        return sum(s.mal_uso for s in self.sesiones)

    @property
    def ayudas(self) -> int:
        return sum(s.ayudas for s in self.sesiones)

    @property
    def ultima_sesion(self) -> datetime | None:
        return max((s.inicio for s in self.sesiones), default=None)
