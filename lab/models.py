"""
Modelos de Django SOLO para el panel /admin/.

Las tablas del laboratorio las crean los scripts de levi-db-scripts, no Django:
por eso estos modelos son `managed = False` (Django nunca las crea, cambia ni borra).
La API no usa estos modelos: lee y escribe con SQL en la capa DAO (lab/dao/).

Django sí crea sus propias tablas (usuarios, tokens invalidados, caché del login,
panel admin) con `python manage.py migrate`.
"""

from django.db import models


class Participante(models.Model):
    """Tabla participante: un código de visor y, si es un alumno, sus datos."""

    codigo = models.CharField('código', primary_key=True, max_length=50)
    visor = models.TextField(blank=True, null=True)
    nombre = models.CharField(max_length=200, blank=True, null=True)
    apellido = models.CharField(max_length=200, blank=True, null=True)
    asignatura = models.CharField(max_length=200, blank=True, null=True)
    registrado = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'participante'
        ordering = ['registrado']
        verbose_name = 'participante (alumno)'
        verbose_name_plural = 'participantes (alumnos)'

    def __str__(self) -> str:
        return f'{self.nombre} ({self.codigo})' if self.nombre else self.codigo


class Sesion(models.Model):
    """Tabla sesion: el resumen de cada sesión. El detalle está en otras tablas."""

    id = models.BigIntegerField(primary_key=True)
    participante = models.ForeignKey(
        Participante, models.DO_NOTHING, db_column='participante_id', related_name='sesiones'
    )
    experimento_id = models.TextField('experimento')
    inicio = models.DateTimeField()
    termino = models.DateTimeField('término', blank=True, null=True)
    completada = models.BooleanField()
    duracion_s = models.DecimalField('duración (s)', max_digits=9, decimal_places=2, blank=True, null=True)
    correctas = models.IntegerField()
    tareas_total = models.IntegerField('tareas')
    version_app = models.TextField('versión de la app', blank=True, null=True)
    visor_modelo = models.TextField('visor', blank=True, null=True)
    origen = models.TextField()
    recibida_en = models.DateTimeField('recibida')

    class Meta:
        managed = False
        db_table = 'sesion'
        ordering = ['-recibida_en']
        verbose_name = 'sesión'
        verbose_name_plural = 'sesiones'

    def __str__(self) -> str:
        return f'{self.participante_id} · {self.experimento_id} · {self.inicio}'
