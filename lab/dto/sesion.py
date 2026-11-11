"""
DTO de la sesión.

    SesionLogDTO           el registro que envía el visor (SessionLog.cs de Unity),
                           con sus eventos (EventoDTO) y su resumen por tarea
                           (TareaResumenDTO). `desde_json` lo valida; `a_json` lo vuelve
                           a escribir con la misma forma y el mismo orden de campos.
    SesionGuardadaDTO      lo que la API le devuelve al panel: {id, log, source, receivedAt}.
    ResultadoImportacionDTO resultado del botón "Cargar sesiones".

Las reglas siguen las restricciones de la base (levi-db-scripts v2.0 y v2.3): tipos de
evento y veredictos permitidos, números que caben en numeric(9,2), etc. Así un dato
inválido se rechaza con un mensaje claro en vez de un error de la base de datos.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..utils.errores import DatosInvalidos
from .fechas import a_hora_local, leer_fecha_del_visor, texto_del_visor

# Mismos valores que EventTypes en SessionLog.cs y que el CHECK de la tabla evento.
TIPOS_EVENTO = (
    'etapa', 'lectura', 'rechazo', 'toma', 'suelta', 'diagnostico',
    'selector', 'borne', 'vista', 'tutorial', 'recentrado',
)
LECTURA = 'lectura'
RECHAZO = 'rechazo'
VEREDICTOS = ('Correct', 'OutOfTolerance', 'ReversedPolarity')
VEREDICTOS_FINALES = (*VEREDICTOS, 'SinRegistrar')

ORIGEN_VISOR = 'visor'
ORIGEN_IMPORTADA = 'importada'

# Largo máximo de los campos que forman el identificador de la sesión.
LARGOS = {'participantCode': 50, 'experimentId': 50, 'startedAt': 40}
# Lo máximo que cabe en una columna numeric(9,2) (segundos).
MAX_SEGUNDOS = 9_999_999.99


class SesionInvalida(DatosInvalidos):
    """El JSON se pudo leer, pero no es un registro de sesión válido."""

    def __init__(self, detalle: str):
        super().__init__(detalle)


# ------------------------------------------------------------------ #
# Lectura del JSON


def leer_json(texto: str | bytes) -> Any:
    """Convierte texto JSON en datos de Python. Lanza ValueError si no es JSON.

    Acepta NaN/Infinity (Unity podría escribirlos en algún número) y los cambia por
    null, porque PostgreSQL no los puede guardar.
    """
    if isinstance(texto, bytes):
        texto = texto.decode('utf-8')
    texto = texto.lstrip('﻿')  # marca BOM que agregan algunos editores
    return _sin_no_finitos(json.loads(texto))


def _sin_no_finitos(valor: Any) -> Any:
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if isinstance(valor, dict):
        return {k: _sin_no_finitos(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_sin_no_finitos(v) for v in valor]
    return valor


# ------------------------------------------------------------------ #
# Ayudas para validar campos


def _es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _texto(datos: dict, campo: str, donde: str) -> str:
    valor = datos.get(campo)
    if valor is None:
        return ''
    if not isinstance(valor, str):
        raise SesionInvalida(f'{donde}: "{campo}" debe ser un texto')
    return valor


def _entero(datos: dict, campo: str, donde: str, defecto: int = 0) -> int:
    valor = datos.get(campo, defecto)
    if valor is None:
        return defecto
    if _es_numero(valor) and float(valor).is_integer():
        return int(valor)
    raise SesionInvalida(f'{donde}: "{campo}" debe ser un número entero')


def _segundos(datos: dict, campo: str, donde: str, obligatorio: bool = False) -> float | None:
    valor = datos.get(campo)
    if valor is None:
        if obligatorio:
            raise SesionInvalida(f'{donde}: falta "{campo}"')
        return None
    if not _es_numero(valor):
        raise SesionInvalida(f'{donde}: "{campo}" debe ser un número')
    if abs(valor) > MAX_SEGUNDOS:
        raise SesionInvalida(f'{donde}: "{campo}" es demasiado grande')
    return float(valor)


def _numero(datos: dict, campo: str, donde: str) -> float:
    valor = datos.get(campo)
    if not _es_numero(valor):
        raise SesionInvalida(f'{donde}: "{campo}" debe ser un número')
    return float(valor)


def _fecha(datos: dict, campo: str, obligatoria: bool) -> datetime | None:
    texto = datos.get(campo)
    if texto is None or (isinstance(texto, str) and not texto.strip()):
        if obligatoria:
            raise SesionInvalida(f'Falta el campo "{campo}"')
        return None
    if not isinstance(texto, str):
        raise SesionInvalida(f'El campo "{campo}" debe ser un texto con fecha y hora')
    try:
        return leer_fecha_del_visor(texto)
    except ValueError:
        raise SesionInvalida(f'El campo "{campo}" no es una fecha y hora local válida ("{texto}")') from None


# ------------------------------------------------------------------ #
# Evento


@dataclass
class EventoDTO:
    t: float
    tipo: str
    tarea: str                 # medición del catálogo, paso del tutorial, 'pizarra' o ''
    detalle: str
    # Solo los usan 'lectura' (todos) y 'rechazo' (selector y borne):
    medido: float = 0.0
    esperado: float = 0.0
    veredicto: str = ''
    intento: int = 0
    selector: str = ''
    borne: str = ''

    @classmethod
    def desde_json(cls, datos: Any, numero: int) -> 'EventoDTO':
        donde = f'Evento {numero}'
        if not isinstance(datos, dict):
            raise SesionInvalida(f'{donde}: no tiene el formato de un evento')
        tipo = _texto(datos, 'type', donde)
        if tipo not in TIPOS_EVENTO:
            raise SesionInvalida(f'{donde}: tipo de evento desconocido "{tipo}"')
        evento = cls(
            t=_segundos(datos, 't', donde, obligatorio=True),
            tipo=tipo,
            tarea=_texto(datos, 'task', donde),
            detalle=_texto(datos, 'detail', donde),
        )
        if tipo in (LECTURA, RECHAZO):
            evento.selector = _texto(datos, 'selector', donde)
            evento.borne = _texto(datos, 'jack', donde)
        if tipo == LECTURA:
            evento.medido = _numero(datos, 'measured', donde)
            evento.esperado = _numero(datos, 'expected', donde)
            evento.veredicto = _texto(datos, 'verdict', donde)
            if evento.veredicto not in VEREDICTOS:
                raise SesionInvalida(f'{donde}: veredicto desconocido "{evento.veredicto}"')
            evento.intento = _entero(datos, 'attempt', donde)
        return evento

    def a_json(self) -> dict:
        # Mismo orden de campos que SessionEvent en Unity.
        return {
            't': self.t,
            'type': self.tipo,
            'task': self.tarea,
            'detail': self.detalle,
            'measured': self.medido,
            'expected': self.esperado,
            'verdict': self.veredicto,
            'attempt': self.intento,
            'selector': self.selector,
            'jack': self.borne,
        }


# ------------------------------------------------------------------ #
# Resumen por tarea


@dataclass
class TareaResumenDTO:
    codigo: str
    intentos: int
    rechazos: int
    veredicto_final: str
    intento_primera_correcta: int        # 0 = nunca fue correcta
    primera_lectura_s: float | None      # None = sin lecturas (Unity escribe -1)
    primera_correcta_s: float | None     # None = nunca correcta (Unity escribe -1)

    @classmethod
    def desde_json(cls, datos: Any, numero: int) -> 'TareaResumenDTO':
        donde = f'Tarea {numero}'
        if not isinstance(datos, dict):
            raise SesionInvalida(f'{donde}: no tiene el formato de un resumen de tarea')
        codigo = _texto(datos, 'id', donde).strip()
        if not codigo:
            raise SesionInvalida(f'{donde}: falta "id"')
        veredicto = _texto(datos, 'finalVerdict', donde) or 'SinRegistrar'
        if veredicto not in VEREDICTOS_FINALES:
            raise SesionInvalida(f'{donde}: veredicto final desconocido "{veredicto}"')
        return cls(
            codigo=codigo,
            intentos=_entero(datos, 'attempts', donde),
            rechazos=_entero(datos, 'rejected', donde),
            veredicto_final=veredicto,
            intento_primera_correcta=_entero(datos, 'firstCorrectAttempt', donde),
            primera_lectura_s=_sin_marca(_segundos(datos, 'firstReadingSeconds', donde)),
            primera_correcta_s=_sin_marca(_segundos(datos, 'firstCorrectSeconds', donde)),
        )

    def a_json(self) -> dict:
        return {
            'id': self.codigo,
            'attempts': self.intentos,
            'rejected': self.rechazos,
            'finalVerdict': self.veredicto_final,
            'firstCorrectAttempt': self.intento_primera_correcta,
            'firstReadingSeconds': -1.0 if self.primera_lectura_s is None else self.primera_lectura_s,
            'firstCorrectSeconds': -1.0 if self.primera_correcta_s is None else self.primera_correcta_s,
        }


def _sin_marca(segundos: float | None) -> float | None:
    """Unity usa -1 para "no ocurrió"; en la base se guarda como NULL."""
    return None if segundos is None or segundos < 0 else segundos


# ------------------------------------------------------------------ #
# Sesión completa


@dataclass
class SesionLogDTO:
    codigo_participante: str
    experimento_id: str
    titulo_experimento: str
    version_app: str
    visor_modelo: str
    inicio: datetime
    termino: datetime | None
    completada: bool
    duracion_s: float | None
    laboratorio_s: float | None
    correctas: int
    tareas_total: int
    eventos: list[EventoDTO] = field(default_factory=list)
    tareas: list[TareaResumenDTO] = field(default_factory=list)

    @property
    def id(self) -> str:
        """participantCode_experimentId_startedAt: el identificador que usa el panel."""
        return f'{self.codigo_participante}_{self.experimento_id}_{texto_del_visor(self.inicio)}'

    @classmethod
    def desde_json(cls, datos: Any) -> 'SesionLogDTO':
        if not isinstance(datos, dict):
            raise SesionInvalida('No tiene el formato de registro de sesión')
        for campo, largo in LARGOS.items():
            valor = datos.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                raise SesionInvalida(f'Falta el campo "{campo}"')
            if len(valor) > largo:
                raise SesionInvalida(f'El campo "{campo}" es demasiado largo')
        if not isinstance(datos.get('events'), list):
            raise SesionInvalida('Falta la lista "events"')
        tareas = datos.get('tasks') or []
        if not isinstance(tareas, list):
            raise SesionInvalida('"tasks" debe ser una lista')
        completada = datos.get('completed', False)
        if not isinstance(completada, bool):
            raise SesionInvalida('"completed" debe ser true o false')

        sesion = cls(
            codigo_participante=datos['participantCode'],
            experimento_id=datos['experimentId'],
            titulo_experimento=_texto(datos, 'experimentTitle', 'Sesión'),
            version_app=_texto(datos, 'appVersion', 'Sesión'),
            visor_modelo=_texto(datos, 'device', 'Sesión'),
            inicio=_fecha(datos, 'startedAt', obligatoria=True),
            termino=_fecha(datos, 'finishedAt', obligatoria=False),
            completada=completada,
            duracion_s=_segundos(datos, 'durationSeconds', 'Sesión'),
            laboratorio_s=_segundos(datos, 'laboratorySeconds', 'Sesión'),
            correctas=_entero(datos, 'correctCount', 'Sesión'),
            tareas_total=_entero(datos, 'taskCount', 'Sesión'),
            eventos=[EventoDTO.desde_json(e, n) for n, e in enumerate(datos['events'], start=1)],
            tareas=[TareaResumenDTO.desde_json(t, n) for n, t in enumerate(tareas, start=1)],
        )
        codigos = [t.codigo for t in sesion.tareas]
        repetidas = sorted({c for c in codigos if codigos.count(c) > 1})
        if repetidas:
            raise SesionInvalida(f'La tarea "{repetidas[0]}" aparece más de una vez en "tasks"')
        return sesion

    def a_json(self) -> dict:
        # Mismo orden de campos que SessionLog en Unity.
        return {
            'participantCode': self.codigo_participante,
            'experimentId': self.experimento_id,
            'experimentTitle': self.titulo_experimento,
            'appVersion': self.version_app,
            'device': self.visor_modelo,
            'startedAt': texto_del_visor(self.inicio),
            'finishedAt': texto_del_visor(self.termino) if self.termino else '',
            'completed': self.completada,
            'durationSeconds': self.duracion_s,
            'laboratorySeconds': self.laboratorio_s,
            'correctCount': self.correctas,
            'taskCount': self.tareas_total,
            'events': [e.a_json() for e in self.eventos],
            'tasks': [t.a_json() for t in self.tareas],
        }


@dataclass
class SesionGuardadaDTO:
    log: SesionLogDTO
    origen: str
    recibida_en: datetime

    def a_json(self) -> dict:
        return {
            'id': self.log.id,
            'log': self.log.a_json(),
            'source': self.origen,
            'receivedAt': a_hora_local(self.recibida_en),
        }


@dataclass
class ResultadoImportacionDTO:
    agregadas: int = 0
    repetidas: int = 0
    invalidas: list[tuple[str, str]] = field(default_factory=list)  # (archivo, motivo)

    def a_json(self) -> dict:
        return {
            'added': self.agregadas,
            'duplicated': self.repetidas,
            'invalid': [{'file': archivo, 'reason': motivo} for archivo, motivo in self.invalidas],
        }
