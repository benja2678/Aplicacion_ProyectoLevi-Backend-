"""
Lectura, validación y guardado de los registros de sesión (SessionLog) de Unity.

Lo usan dos caminos:
- POST /api/sessions/ingest/  (Unity envía una sesión con la llave X-Api-Key)
- POST /api/sessions/import/  (el profesor sube archivos .json con "Cargar sesiones")
"""

import json
import math
from typing import Any

from django.db import IntegrityError, transaction

from .models import Session

# Largo máximo de los campos que se copian a columnas propias (ver models.py).
REQUIRED_TEXT_FIELDS = {'participantCode': 50, 'experimentId': 50, 'startedAt': 40}


class InvalidSessionLog(ValueError):
    """El JSON se pudo leer, pero no tiene la forma de un SessionLog."""


def parse_json(raw: str | bytes) -> Any:
    """Convierte texto JSON en datos de Python.

    Acepta NaN/Infinity (Unity podría escribirlos en algún número) y los cambia por
    null, porque PostgreSQL no los acepta dentro de un JSON.
    Lanza ValueError si el texto no es JSON.
    """
    if isinstance(raw, str):
        raw = raw.lstrip('﻿')  # marca BOM que agregan algunos editores
    return _replace_non_finite(json.loads(raw))


def _replace_non_finite(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _replace_non_finite(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_replace_non_finite(v) for v in value]
    return value


def validate_log(data: Any) -> dict:
    """Revisa lo mínimo para poder guardar la sesión (igual que isSessionLog del frontend,
    más startedAt, que es parte del identificador)."""
    if not isinstance(data, dict):
        raise InvalidSessionLog('No tiene el formato de registro de sesión')
    for field, max_len in REQUIRED_TEXT_FIELDS.items():
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise InvalidSessionLog(f'Falta el campo "{field}"')
        if len(value) > max_len:
            raise InvalidSessionLog(f'El campo "{field}" es demasiado largo')
    if not isinstance(data.get('events'), list):
        raise InvalidSessionLog('Falta la lista "events"')
    return data


def save_session(log: dict, source: str) -> tuple[str, bool]:
    """Guarda la sesión si no existía.

    Devuelve (id, creada). `creada` es False si la sesión ya estaba guardada
    (mismo participantCode + experimentId + startedAt).
    """
    code, experiment, started = log['participantCode'], log['experimentId'], log['startedAt']
    session_id = Session.make_id(code, experiment, started)

    if Session.objects.filter(participant_code=code, experiment_id=experiment, started_at=started).exists():
        return session_id, False
    try:
        with transaction.atomic():
            Session.objects.create(
                id=session_id,
                participant_code=code,
                experiment_id=experiment,
                started_at=started,  # texto tal cual, sin convertir zona horaria
                log=log,
                source=source,
            )
    except IntegrityError:
        # Llegó la misma sesión dos veces al mismo tiempo: la otra petición ya la guardó.
        return session_id, False
    return session_id, True
