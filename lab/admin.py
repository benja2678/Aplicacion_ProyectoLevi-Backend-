"""Panel /admin/ de Django: permite al profesor ver los datos guardados y cambiar su contraseña."""

from django.contrib import admin

from .models import Session, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo_participante', 'asignatura', 'creado_en')
    search_fields = ('nombre', 'codigo_participante')
    ordering = ('nombre',)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('participant_code', 'experiment_id', 'started_at', 'source', 'received_at')
    list_filter = ('source', 'experiment_id')
    search_fields = ('participant_code', 'experiment_id')
    ordering = ('-received_at',)
    # Las sesiones vienen de Unity: se pueden ver y borrar, pero no editar.
    readonly_fields = ('id', 'participant_code', 'experiment_id', 'started_at', 'source', 'received_at', 'log')

    def has_add_permission(self, request):
        return False
