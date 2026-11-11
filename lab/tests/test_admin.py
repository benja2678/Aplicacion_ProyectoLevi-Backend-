"""Tests del panel /admin/: sigue mostrando alumnos y sesiones, y usa los mismos servicios."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from lab.dto.sesion import ORIGEN_VISOR, SesionLogDTO
from lab.servicios import sesion_servicio

from .utils import contar, session_log, sql_uno


class AdminTests(TestCase):
    def setUp(self):
        # ensure_teacher crea la cuenta del profesor como superusuario.
        get_user_model().objects.create_superuser('profesor', password='Clave-Del-Profesor-2026')
        self.client.login(username='profesor', password='Clave-Del-Profesor-2026')
        sesion_servicio.guardar(SesionLogDTO.desde_json(session_log('A001')), ORIGEN_VISOR)
        self.numero = sql_uno('select id from sesion')

    def test_las_paginas_abren(self):
        for url in ['/admin/', '/admin/lab/participante/', '/admin/lab/participante/A001/change/',
                    '/admin/lab/sesion/', f'/admin/lab/sesion/{self.numero}/change/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_registrar_alumno_desde_el_admin(self):
        r = self.client.post('/admin/lab/participante/A001/change/',
                             {'nombre': 'Camila', 'apellido': 'Rojas', 'asignatura': 'Electrónica Digital'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sql_uno("select nombre || ' ' || apellido from participante where codigo = 'A001'"),
                         'Camila Rojas')

    def test_borrar_sesion_desde_el_admin(self):
        r = self.client.post(f'/admin/lab/sesion/{self.numero}/delete/', {'post': 'yes'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(contar('sesion'), 0)
        self.assertEqual(contar('evento'), 0)
