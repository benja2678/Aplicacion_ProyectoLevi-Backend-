"""
Tablas de la base de datos.

- students: alumnos que el profesor registra en la web.
- sessions: sesiones que llegan desde Unity (Meta Quest) o que se cargan a mano.

Un alumno se une a sus sesiones por el CÓDIGO DE PARTICIPANTE (A001, B002...).
No hay llave foránea entre las tablas porque una sesión puede llegar antes de que
el profesor cree al alumno; la unión se hace al mostrar los datos.
"""

import uuid

from django.db import models


class Student(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nombre = models.CharField(max_length=200)
    asignatura = models.CharField(max_length=200, blank=True, default='')
    # Se guarda siempre en MAYÚSCULAS, así "a001" y "A001" son el mismo código.
    codigo_participante = models.CharField(max_length=50, unique=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'students'
        ordering = ['creado_en']
        verbose_name = 'alumno'
        verbose_name_plural = 'alumnos'

    def __str__(self) -> str:
        return f'{self.nombre} ({self.codigo_participante})'

    def save(self, *args, **kwargs):
        # Misma regla en la API y en el panel /admin/: sin espacios y en mayúsculas.
        self.codigo_participante = self.codigo_participante.strip().upper()
        super().save(*args, **kwargs)


class Session(models.Model):
    SOURCE_VISOR = 'visor'
    SOURCE_IMPORTADA = 'importada'
    SOURCE_CHOICES = [
        (SOURCE_VISOR, 'Enviada por el visor'),
        (SOURCE_IMPORTADA, 'Cargada a mano'),
    ]

    # Identificador = participantCode_experimentId_startedAt (igual que en el frontend).
    id = models.CharField(primary_key=True, max_length=255)
    # Copias de 3 campos del JSON en columnas propias, para buscar y evitar duplicados.
    participant_code = models.CharField(max_length=50, db_index=True)
    experiment_id = models.CharField(max_length=50)
    # Texto TAL CUAL llega de Unity (hora local sin zona). No se convierte a fecha
    # a propósito: es parte del identificador de la sesión.
    started_at = models.CharField(max_length=40)
    # El registro completo de Unity (SessionLog), sin modificar.
    log = models.JSONField()
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sessions'
        ordering = ['received_at']
        verbose_name = 'sesión'
        verbose_name_plural = 'sesiones'
        constraints = [
            # Una misma sesión no puede guardarse dos veces (Unity puede reenviarla).
            models.UniqueConstraint(
                fields=['participant_code', 'experiment_id', 'started_at'],
                name='unique_session',
            ),
        ]

    def __str__(self) -> str:
        return self.id

    @staticmethod
    def make_id(participant_code: str, experiment_id: str, started_at: str) -> str:
        return f'{participant_code}_{experiment_id}_{started_at}'
