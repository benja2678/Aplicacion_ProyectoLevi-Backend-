"""Tests unitarios de lab/admin.py y lab/models.py.

El panel /admin/ debe usar los mismos servicios que la API: se reemplazan por
simulacros (mocks) y se revisa que se llamen como corresponde. Sin base de datos.
"""

from datetime import UTC, datetime
from unittest import mock

from django.contrib import admin
from django.test import SimpleTestCase

from lab.admin import ParticipanteAdmin, ParticipanteForm, SesionAdmin
from lab.dto.alumno import AlumnoEntradaDTO
from lab.models import Participante, Sesion


def guardado(codigo='A001', nombre='Camila'):
    """Un participante como lo carga el admin desde la base."""
    p = Participante(codigo=codigo, visor='A', nombre=nombre, apellido='Rojas', asignatura='Electrónica Digital',
                     registrado=datetime(2026, 11, 3, 15, 0, tzinfo=UTC))
    p._state.adding = False
    return p


class ParticipanteFormTests(SimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.admin.alumno_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.servicio.codigo_disponible.return_value = True

    def test_alumno_nuevo_valido(self):
        form = ParticipanteForm({'codigo': 'b003', 'nombre': ' Ana ', 'apellido': '', 'asignatura': ''})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.entrada, AlumnoEntradaDTO(nombre='Ana', asignatura='', codigo='B003', apellido=''))
        self.servicio.codigo_disponible.assert_called_once_with('B003')

    def test_codigo_de_otro_alumno(self):
        self.servicio.codigo_disponible.return_value = False
        form = ParticipanteForm({'codigo': 'A001', 'nombre': 'Ana'})
        self.assertFalse(form.is_valid())
        self.assertIn('El código A001 ya está asignado a otro alumno.', form.non_field_errors())

    def test_sin_nombre(self):
        form = ParticipanteForm({'codigo': 'B003', 'nombre': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('Escribe el nombre del alumno.', form.non_field_errors())

    def test_editar_un_alumno_no_revisa_su_propio_codigo(self):
        form = ParticipanteForm({'codigo': 'A001', 'nombre': 'Camila R.'}, instance=guardado())
        self.assertTrue(form.is_valid(), form.errors)
        self.servicio.codigo_disponible.assert_not_called()


class ParticipanteAdminTests(SimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.admin.alumno_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.admin = ParticipanteAdmin(Participante, admin.site)

    def form(self, nombre_inicial):
        form = mock.Mock(initial={'nombre': nombre_inicial})
        form.entrada = AlumnoEntradaDTO(nombre='Camila', asignatura='', codigo='A001', apellido='')
        return form

    def test_guardar_usa_el_servicio(self):
        self.admin.save_model(None, guardado(), self.form('Camila'), change=True)
        self.servicio.actualizar.assert_called_once()
        self.admin.save_model(None, guardado(), self.form(None), change=True)  # código sin alumno -> registrar
        self.admin.save_model(None, Participante(codigo='A001'), self.form(None), change=False)
        self.assertEqual(self.servicio.crear.call_count, 2)

    def test_borrar_solo_alumnos(self):
        self.assertTrue(self.admin.has_delete_permission(None, guardado()))
        self.assertFalse(self.admin.has_delete_permission(None, guardado('A015', nombre=None)))
        self.admin.delete_queryset(None, [guardado('A001'), guardado('A015', nombre=None)])
        self.servicio.eliminar.assert_called_once_with('A001')

    def test_el_codigo_no_se_edita(self):
        self.assertIn('codigo', self.admin.get_readonly_fields(None, guardado()))
        self.assertNotIn('codigo', self.admin.get_readonly_fields(None, None))


class SesionAdminTests(SimpleTestCase):
    def setUp(self):
        self.servicio = mock.patch('lab.admin.sesion_servicio').start()
        self.addCleanup(mock.patch.stopall)
        self.admin = SesionAdmin(Sesion, admin.site)

    def test_solo_ver_y_borrar(self):
        self.assertFalse(self.admin.has_add_permission(None))
        self.assertFalse(self.admin.has_change_permission(None))
        self.admin.delete_queryset(None, [Sesion(id=2), Sesion(id=3)])
        self.assertEqual([c.args for c in self.servicio.eliminar_por_numero.call_args_list], [(2,), (3,)])


class ModelsTests(SimpleTestCase):
    def test_textos(self):
        self.assertEqual(str(guardado()), 'Camila (A001)')
        self.assertEqual(str(guardado('A015', nombre=None)), 'A015')
        sesion = Sesion(id=2, participante_id='A001', experimento_id='N1', inicio=datetime(2026, 11, 5, 10, 31, 12))
        self.assertEqual(str(sesion), 'A001 · N1 · 2026-11-05 10:31:12')

    def test_django_no_administra_esas_tablas(self):
        self.assertFalse(Participante._meta.managed)
        self.assertFalse(Sesion._meta.managed)
