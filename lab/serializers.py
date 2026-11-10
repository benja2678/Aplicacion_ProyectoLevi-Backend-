"""
Serializadores: convierten las filas de la base de datos al JSON que espera el
frontend (src/types.ts), con los mismos nombres en camelCase.

    Student       -> { id, nombre, asignatura, codigoParticipante, creadoEn }
    StoredSession -> { id, log, source, receivedAt }

Las fechas se entregan como hora local sin zona ("2026-11-05T10:31:12"), igual
que las genera el frontend y Unity.
"""

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Session, Student

LOCAL_DATETIME = '%Y-%m-%dT%H:%M:%S'


class StudentSerializer(serializers.ModelSerializer):
    codigoParticipante = serializers.CharField(source='codigo_participante', max_length=50)
    creadoEn = serializers.DateTimeField(source='creado_en', read_only=True, format=LOCAL_DATETIME)

    class Meta:
        model = Student
        fields = ['id', 'nombre', 'asignatura', 'codigoParticipante', 'creadoEn']
        read_only_fields = ['id']
        extra_kwargs = {'asignatura': {'required': False, 'allow_blank': True}}

    def validate_nombre(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Escribe el nombre del alumno.')
        return value

    def validate_asignatura(self, value: str) -> str:
        return value.strip()

    def validate_codigoParticipante(self, value: str) -> str:
        code = value.strip().upper()
        if not code:
            raise serializers.ValidationError('Escribe el código del visor.')
        others = Student.objects.filter(codigo_participante=code)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError(f'El código {code} ya está asignado a otro alumno.')
        return code


class SessionSerializer(serializers.ModelSerializer):
    receivedAt = serializers.DateTimeField(source='received_at', read_only=True, format=LOCAL_DATETIME)

    class Meta:
        model = Session
        fields = ['id', 'log', 'source', 'receivedAt']
        read_only_fields = fields


class TeacherTokenSerializer(TokenObtainPairSerializer):
    """Login del profesor con un mensaje de error claro y en español."""

    default_error_messages = {'no_active_account': 'Usuario o contraseña incorrectos.'}
