"""
Panel /admin/ de Django: el profesor puede ver los datos guardados y cambiar su contraseña.

Para no tener dos lugares con reglas distintas, crear, editar y borrar pasan por los
mismos servicios que usa la API (lab/servicios/).
"""

from django import forms
from django.contrib import admin

from .dto.alumno import AlumnoEntradaDTO
from .errores import DatosInvalidos
from .models import Participante, Sesion
from .servicios import alumno_servicio, sesion_servicio


class ParticipanteForm(forms.ModelForm):
    class Meta:
        model = Participante
        fields = ['codigo', 'nombre', 'apellido', 'asignatura']

    def validate_unique(self):
        # Un código que ya tiene sesiones (fila sin nombre) sí se puede registrar
        # como alumno: lo decide el servicio, no la llave primaria.
        pass

    def clean(self):
        datos = super().clean()
        codigo = datos.get('codigo') or (self.instance.codigo if self.instance else '')
        try:
            entrada = AlumnoEntradaDTO.desde_json({
                'nombre': datos.get('nombre') or '',
                'apellido': datos.get('apellido') or '',
                'asignatura': datos.get('asignatura') or '',
                'codigoParticipante': codigo,
            })
        except DatosInvalidos as exc:
            raise forms.ValidationError(str(exc)) from None
        es_nuevo = self.instance._state.adding or not self.initial.get('nombre')
        if es_nuevo and not alumno_servicio.codigo_disponible(entrada.codigo):
            raise forms.ValidationError(f'El código {entrada.codigo} ya está asignado a otro alumno.')
        self.entrada = entrada
        return datos


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    form = ParticipanteForm
    list_display = ('codigo', 'nombre', 'apellido', 'asignatura', 'visor', 'registrado')
    search_fields = ('codigo', 'nombre', 'apellido')
    ordering = ('codigo',)

    def get_readonly_fields(self, request, obj=None):
        # El código es la llave: se cambia desde el panel web (mueve al alumno).
        return ('codigo', 'visor', 'registrado') if obj else ('visor', 'registrado')

    def save_model(self, request, obj, form, change):
        entrada = form.entrada
        if change and form.initial.get('nombre'):
            alumno_servicio.actualizar(obj.codigo, entrada)
        else:
            alumno_servicio.crear(entrada)

    def has_delete_permission(self, request, obj=None):
        # Solo se "borra" un alumno (sus sesiones se conservan); un código sin alumno
        # desaparece solo cuando se borran sus sesiones.
        return obj is None or bool(obj.nombre)

    def delete_model(self, request, obj):
        if obj.nombre:
            alumno_servicio.eliminar(obj.codigo)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)


@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ('participante_id', 'experimento_id', 'inicio', 'completada', 'correctas', 'origen', 'recibida_en')
    list_filter = ('origen', 'experimento_id', 'completada')
    search_fields = ('participante__codigo', 'experimento_id')

    # Las sesiones vienen del visor: se pueden ver y borrar, pero no crear ni editar.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def delete_model(self, request, obj):
        sesion_servicio.eliminar_por_numero(obj.id)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)
