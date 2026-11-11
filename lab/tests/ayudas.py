"""Datos y ayudas comunes para los tests."""

import json
from pathlib import Path

from django.contrib.auth.models import User
from django.db import connection

from lab.dto.lector import LectorAutenticado

DATOS = Path(__file__).resolve().parent / 'datos'
TEST_API_KEY = 'llave-de-prueba-unity-123'

# Títulos del catálogo (levi-db-scripts v2.1): el panel recibe el título de la base.
TITULOS = {
    'T0': 'Tutorial: controles y primer circuito',
    'N1D': 'Ley de Ohm en un circuito mixto (armado desde cero)',
    'N1': 'Ley de Ohm en un circuito mixto',
}


# ------------------------------------------------------------------ #
# Sesiones con la misma forma que genera Unity (SessionLog.cs)


def evento(t, tipo, task='', detail='', **extra):
    """Un evento con todos sus campos (los que no aplican, en cero o vacíos, como Unity)."""
    e = {'t': t, 'type': tipo, 'task': task, 'detail': detail, 'measured': 0.0, 'expected': 0.0,
         'verdict': '', 'attempt': 0, 'selector': '', 'jack': ''}
    e.update(extra)
    return e


def tarea(codigo, final='SinRegistrar', attempts=0, rejected=0, first_correct=0, first_reading=-1.0, first_ok=-1.0):
    return {'id': codigo, 'attempts': attempts, 'rejected': rejected, 'finalVerdict': final,
            'firstCorrectAttempt': first_correct, 'firstReadingSeconds': first_reading,
            'firstCorrectSeconds': first_ok}


def session_log(code='A001', experiment='N1', started='2026-11-05T10:31:12', **extra):
    """Una sesión de N1 con cada clase de dato que va a una tabla distinta: lectura,
    rechazo, paso del tutorial y pizarra (etiqueta), diagnóstico y etapas."""
    log = {
        'participantCode': code,
        'experimentId': experiment,
        'experimentTitle': TITULOS.get(experiment, ''),
        'appVersion': '0.9-feria',
        'device': 'Meta Quest 3S',
        'startedAt': started,
        'finishedAt': '2026-11-05T10:45:02',
        'completed': True,
        'durationSeconds': 830.5,
        'laboratorySeconds': 700.25,
        'correctCount': 1,
        'taskCount': 6,
        'events': [
            evento(0.0, 'etapa', detail='Briefing'),
            evento(0.43, 'recentrado', detail='inicio'),
            evento(5.5, 'vista', task='pizarra', detail='esquema'),
            evento(9.0, 'tutorial', task='selector', detail='cumplido'),
            evento(26.86, 'diagnostico', detail="ExcessivePower: 'R2' disipa 0,4236 W frente a 0,25 W nominales."),
            evento(44.26, 'etapa', detail='Laboratory'),
            evento(47.65, 'lectura', task='V1', measured=4.98, expected=4.98400921069464, verdict='Correct',
                   attempt=1, selector='20 V', jack='VoltOhmMilliamp'),
            evento(50.0, 'rechazo', task='V2', detail='OverRange', selector='200m V', jack='VoltOhmMilliamp'),
            evento(830.5, 'etapa', detail='Results'),
        ],
        'tasks': [
            tarea('V1', 'Correct', attempts=1, first_correct=1, first_reading=47.65, first_ok=47.65),
            tarea('V2', rejected=1),
            tarea('V3'), tarea('I_total'), tarea('I_R2'), tarea('I_R4'),
        ],
    }
    log.update(extra)
    return log


def session_log_t0(code='A001', started='2026-11-04T09:15:00'):
    """Una sesión del tutorial T0 (una sola medición, V_R1)."""
    return {
        'participantCode': code,
        'experimentId': 'T0',
        'experimentTitle': TITULOS['T0'],
        'appVersion': '0.9-feria',
        'device': 'Meta Quest 3S',
        'startedAt': started,
        'finishedAt': '2026-11-04T09:15:35',
        'completed': True,
        'durationSeconds': 35.0,
        'laboratorySeconds': 15.0,
        'correctCount': 1,
        'taskCount': 1,
        'events': [
            evento(0.0, 'etapa', detail='Briefing'),
            evento(3.2, 'tutorial', task='comenzar', detail='cumplido'),
            evento(8.75, 'tutorial', task='tomar', detail='cumplido'),
            evento(15.1, 'tutorial', task='selector', detail='cumplido'),
            evento(20.0, 'etapa', detail='Laboratory'),
            evento(24.5, 'rechazo', task='V_R1', detail='MeterOff', selector='OFF', jack='VoltOhmMilliamp'),
            evento(30.25, 'lectura', task='V_R1', measured=2.5, expected=2.4876, verdict='Correct', attempt=1,
                   selector='20 V', jack='VoltOhmMilliamp'),
            evento(35.0, 'etapa', detail='Results'),
        ],
        'tasks': [tarea('V_R1', 'Correct', attempts=1, rejected=1, first_correct=1, first_reading=30.25, first_ok=30.25)],
    }


def sesion_real_del_visor() -> dict:
    """El JSON que envió un visor de verdad (A015, experimento N1)."""
    return json.loads((DATOS / 'A015_N1_20261110_230751.json').read_text(encoding='utf-8'))


# ------------------------------------------------------------------ #
# Otros


def lector_sin_base(rol='docente') -> LectorAutenticado:
    """Un lector conectado (docente o equipo), sin tocar la base (para tests unitarios)."""
    return LectorAutenticado(correo='docente@ejemplo.cl', nombre='Docente de prueba', rol=rol)


def usuario_django_sin_base() -> User:
    """Un usuario de Django (de /admin/): NO es un lector, así que no puede usar la API."""
    return User(id=1, username='admin', is_staff=True, is_superuser=True, is_active=True)


def sql_uno(sql, parametros=()):
    """Primera columna de la primera fila (para revisar la base en los tests del DAO)."""
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        fila = cursor.fetchone()
    return fila[0] if fila else None


def contar(tabla: str, donde: str = 'true', parametros=()) -> int:
    return sql_uno(f'select count(*) from {tabla} where {donde}', parametros)
