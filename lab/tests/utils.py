"""Ayudas comunes para los tests."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

TEST_API_KEY = 'llave-de-prueba-unity-123'
TEACHER_PASSWORD = 'Clave-Del-Profesor-2026'


def session_log(code='A001', experiment='T0', started='2026-11-05T10:31:12', **extra):
    """Un SessionLog con la misma forma que genera Unity (SessionLog.cs)."""
    log = {
        'participantCode': code,
        'experimentId': experiment,
        'experimentTitle': 'Uso del multímetro',
        'appVersion': '1.0.0',
        'device': 'Meta Quest 3S',
        'startedAt': started,
        'finishedAt': '2026-11-05T10:45:02',
        'completed': True,
        'durationSeconds': 830.5,
        'laboratorySeconds': 700.25,
        'correctCount': 1,
        'taskCount': 2,
        'events': [
            {
                't': 12.5, 'type': 'lectura', 'task': 'V1', 'detail': '', 'measured': 4.98,
                'expected': 5.0, 'verdict': 'Correct', 'attempt': 1, 'selector': 'VDC', 'jack': 'VOmA',
            },
            {
                't': 40.0, 'type': 'rechazo', 'task': 'V2', 'detail': 'MeterOff', 'measured': 0,
                'expected': 3.3, 'verdict': '', 'attempt': 0, 'selector': 'OFF', 'jack': '',
            },
        ],
        'tasks': [
            {'id': 'V1', 'attempts': 1, 'rejected': 0, 'finalVerdict': 'Correct', 'firstCorrectAttempt': 1,
             'firstReadingSeconds': 12.5, 'firstCorrectSeconds': 12.5},
            {'id': 'V2', 'attempts': 0, 'rejected': 1, 'finalVerdict': 'SinRegistrar', 'firstCorrectAttempt': 0,
             'firstReadingSeconds': -1, 'firstCorrectSeconds': -1},
        ],
    }
    log.update(extra)
    return log


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
