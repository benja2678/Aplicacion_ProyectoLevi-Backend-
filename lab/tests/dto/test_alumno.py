"""Tests unitarios de lab/dto/alumno.py (sin base de datos)."""

from datetime import UTC, datetime

from django.test import SimpleTestCase

from lab.dto.alumno import AlumnoDTO, AlumnoEntradaDTO
from lab.utils.errores import DatosInvalidos


class AlumnoEntradaDTOTests(SimpleTestCase):
    def test_limpia_espacios_y_pone_el_codigo_en_mayusculas(self):
        e = AlumnoEntradaDTO.desde_json(
            {'nombre': '  Camila ', 'asignatura': ' Electrónica Digital ', 'codigoParticipante': ' a001 '}
        )
        self.assertEqual(e, AlumnoEntradaDTO(nombre='Camila', asignatura='Electrónica Digital', codigo='A001'))

    def test_apellido_none_si_no_viene_y_texto_si_viene(self):
        sin = AlumnoEntradaDTO.desde_json({'nombre': 'Ana', 'codigoParticipante': 'A1'})
        con = AlumnoEntradaDTO.desde_json({'nombre': 'Ana', 'apellido': ' Soto ', 'codigoParticipante': 'A1'})
        vacio = AlumnoEntradaDTO.desde_json({'nombre': 'Ana', 'apellido': None, 'codigoParticipante': 'A1'})
        self.assertIsNone(sin.apellido)
        self.assertEqual(con.apellido, 'Soto')
        self.assertEqual(vacio.apellido, '')

    def test_asignatura_opcional(self):
        self.assertEqual(AlumnoEntradaDTO.desde_json({'nombre': 'Ana', 'codigoParticipante': 'A1'}).asignatura, '')

    def test_faltan_nombre_y_codigo(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            AlumnoEntradaDTO.desde_json({'nombre': ' ', 'codigoParticipante': ''})
        self.assertEqual(ctx.exception.campos, {
            'nombre': ['Escribe el nombre del alumno.'],
            'codigoParticipante': ['Escribe el código del visor.'],
        })

    def test_largo_maximo(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            AlumnoEntradaDTO.desde_json({'nombre': 'x' * 201, 'codigoParticipante': 'C' * 51})
        self.assertEqual(set(ctx.exception.campos), {'nombre', 'codigoParticipante'})

    def test_tipos_incorrectos(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            AlumnoEntradaDTO.desde_json({'nombre': 5, 'codigoParticipante': 'A1'})
        self.assertEqual(ctx.exception.campos, {'nombre': ['Debe ser un texto.']})

    def test_no_es_un_objeto(self):
        with self.assertRaises(DatosInvalidos) as ctx:
            AlumnoEntradaDTO.desde_json(['Ana'])
        self.assertEqual(ctx.exception.como_respuesta(),
                         {'detail': 'Se esperaba un objeto JSON con los datos del alumno.'})


class AlumnoDTOTests(SimpleTestCase):
    def test_desde_fila_y_a_json_con_la_forma_del_frontend(self):
        fila = {'codigo': 'A001', 'visor': 'A', 'nombre': 'Camila', 'apellido': None, 'asignatura': None,
                'registrado': datetime(2026, 11, 3, 15, 0, tzinfo=UTC)}
        self.assertEqual(AlumnoDTO.desde_fila(fila).a_json(), {
            'id': 'A001',
            'nombre': 'Camila',
            'apellido': '',
            'asignatura': '',
            'codigoParticipante': 'A001',
            'creadoEn': '2026-11-03T12:00:00',
        })
