"""Ayudas comunes para los tests."""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

TEST_API_KEY = 'llave-de-prueba-unity-123'
TEACHER_PASSWORD = 'Clave-Del-Profesor-2026'
DATOS = Path(__file__).resolve().parent / 'datos'

# Títulos del catálogo (levi-db-scripts v2.1): el panel recibe el título de la base.
TITULOS = {
    'T0': 'Tutorial: controles y primer circuito',
    'N1D': 'Ley de Ohm en un circuito mixto (armado desde cero)',
    'N1': 'Ley de Ohm en un circuito mixto',
}


def evento(t, tipo, task='', detail='', **extra):
    """Un evento con todos sus campos, como los escribe Unity (los que no aplican en cero)."""
    e = {'t': t, 'type': tipo, 'task': task, 'detail': detail, 'measured': 0.0, 'expected': 0.0,
         'verdict': '', 'attempt': 0, 'selector': '', 'jack': ''}
    e.update(extra)
    return e


def tarea(codigo, final='SinRegistrar', attempts=0, rejected=0, first_correct=0, first_reading=-1.0, first_ok=-1.0):
    return {'id': codigo, 'attempts': attempts, 'rejected': rejected, 'finalVerdict': final,
            'firstCorrectAttempt': first_correct, 'firstReadingSeconds': first_reading,
            'firstCorrectSeconds': first_ok}


def session_log(code='A001', experiment='N1', started='2026-11-05T10:31:12', **extra):
    """Un SessionLog de N1 con la misma forma que genera Unity (SessionLog.cs).
    Incluye cada clase de dato que se guarda en una tabla distinta: lectura, rechazo,
    paso del tutorial y pizarra (etiqueta), diagnóstico y etapas."""
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


def sesion_real_del_visor() -> dict:
    """El JSON que envió un visor de verdad (lo entregó el equipo de Unity)."""
    return json.loads((DATOS / 'A015_N1_20261110_230751.json').read_text(encoding='utf-8'))


def sql_uno(sql, parametros=()):
    """Primera columna de la primera fila (para revisar la base en los tests)."""
    with connection.cursor() as cursor:
        cursor.execute(sql, parametros)
        fila = cursor.fetchone()
    return fila[0] if fila else None


def contar(tabla: str) -> int:
    return sql_uno(f'select count(*) from {tabla}')


@override_settings(UNITY_API_KEY=TEST_API_KEY)
class BaseApiTest(APITestCase):
    def setUp(self):
        cache.clear()  # reinicia el contador de intentos de login
        User = get_user_model()
        self.teacher = User.objects.create_user('profesor', password=TEACHER_PASSWORD, is_staff=True)

    def login_as_teacher(self):
        """Pone en el cliente un token válido del profesor (sin pasar por /login/)."""
        access = RefreshToken.for_user(self.teacher).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def use_unity_key(self, key=TEST_API_KEY):
        self.client.credentials(HTTP_X_API_KEY=key)

    def ingest(self, log, key=TEST_API_KEY):
        """Envía una sesión como lo hace Unity, sin tocar las credenciales del cliente."""
        return self.client.generic('POST', '/api/sessions/ingest/', json.dumps(log),
                                   content_type='application/json', HTTP_X_API_KEY=key)
