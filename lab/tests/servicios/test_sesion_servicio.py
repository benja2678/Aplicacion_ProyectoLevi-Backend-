"""Tests unitarios de lab/servicios/sesion_servicio.py.

Los DAO se reemplazan por simulacros (mocks): se prueban solo las reglas, sin base de datos.
"""

import json
from contextlib import nullcontext
from datetime import UTC, datetime
from decimal import Decimal
from unittest import mock

from django.db import DataError
from django.test import SimpleTestCase

from lab.dto.sesion import ORIGEN_IMPORTADA, ORIGEN_VISOR, SesionInvalida, SesionLogDTO
from lab.utils.errores import DatosInvalidos, NoEncontrado
from lab.servicios import sesion_servicio

from ..ayudas import session_log, sesion_real_del_visor

# Catálogo de N1 como lo devuelve catalogo_dao.tareas_del_experimento.
TAREAS_N1 = {'V1': 7, 'V2': 8, 'V3': 9, 'I_total': 10, 'I_R2': 11, 'I_R4': 12}
MODULO = 'lab.servicios.sesion_servicio'


class BaseServicioTest(SimpleTestCase):
    def setUp(self):
        self.catalogo = mock.patch(f'{MODULO}.catalogo_dao').start()
        self.participantes = mock.patch(f'{MODULO}.participante_dao').start()
        self.sesiones = mock.patch(f'{MODULO}.sesion_dao').start()
        mock.patch(f'{MODULO}.transaction.atomic', side_effect=lambda *a, **k: nullcontext()).start()
        self.addCleanup(mock.patch.stopall)

        self.catalogo.obtener_experimento.side_effect = (
            lambda e: {'id': e, 'titulo': 'Título'} if e in ('N1', 'T0') else None
        )
        self.catalogo.tareas_del_experimento.side_effect = lambda e: TAREAS_N1 if e == 'N1' else {'V_R1': 1}
        self.sesiones.insertar.return_value = 42

    def filas_insertadas(self, funcion):
        """Las filas que el servicio le pasó a un insertar_* del DAO."""
        return list(funcion.call_args.args[0])


class GuardarTests(BaseServicioTest):
    def test_guarda_la_sesion_repartida_en_tablas(self):
        log = SesionLogDTO.desde_json(session_log())
        self.assertEqual(sesion_servicio.guardar(log, ORIGEN_VISOR), ('A001_N1_2026-11-05T10:31:12', True))

        self.participantes.crear_si_no_existe.assert_called_once_with('A001', 'A')
        self.sesiones.insertar.assert_called_once_with(
            'A001', 'N1', datetime(2026, 11, 5, 10, 31, 12), datetime(2026, 11, 5, 10, 45, 2), True,
            830.5, 700.25, 1, 6, '0.9-feria', 'Meta Quest 3S', 'visor',
        )
        eventos = self.filas_insertadas(self.sesiones.insertar_eventos)
        self.assertEqual(len(eventos), 9)
        # (sesion_id, orden, t_s, tipo, tarea_id, etiqueta, detalle)
        self.assertEqual(eventos[0], (42, 1, 0.0, 'etapa', None, None, 'Briefing'))
        self.assertEqual(eventos[2], (42, 3, 5.5, 'vista', None, 'pizarra', 'esquema'))      # etiqueta
        self.assertEqual(eventos[3], (42, 4, 9.0, 'tutorial', None, 'selector', 'cumplido'))  # etiqueta
        self.assertEqual(eventos[6], (42, 7, 47.65, 'lectura', 7, None, None))               # medición V1
        self.assertEqual(eventos[7], (42, 8, 50.0, 'rechazo', 8, None, 'OverRange'))         # medición V2
        self.assertEqual(self.filas_insertadas(self.sesiones.insertar_lecturas),
                         [(42, 7, 4.98, 4.98400921069464, 'Correct', 1, '20 V', 'VoltOhmMilliamp')])
        self.assertEqual(self.filas_insertadas(self.sesiones.insertar_rechazos),
                         [(42, 8, '200m V', 'VoltOhmMilliamp')])
        tareas = self.filas_insertadas(self.sesiones.insertar_tareas)
        self.assertEqual(tareas[0], (42, 7, 1, 0, 'Correct', 1, 47.65, 47.65))
        self.assertEqual(tareas[1], (42, 8, 0, 1, 'SinRegistrar', None, None, None))  # 0 y -1 -> NULL

    def test_sesion_repetida_no_guarda_el_detalle(self):
        self.sesiones.insertar.return_value = None
        log = SesionLogDTO.desde_json(session_log())
        self.assertEqual(sesion_servicio.guardar(log, ORIGEN_VISOR), ('A001_N1_2026-11-05T10:31:12', False))
        self.sesiones.insertar_eventos.assert_not_called()
        self.sesiones.insertar_tareas.assert_not_called()

    def test_experimento_fuera_del_catalogo(self):
        with self.assertRaises(SesionInvalida) as ctx:
            sesion_servicio.guardar(SesionLogDTO.desde_json(session_log(experiment='N2')), ORIGEN_VISOR)
        self.assertEqual(str(ctx.exception), 'El experimento "N2" no está en el catálogo de la base de datos')
        self.participantes.crear_si_no_existe.assert_not_called()
        self.sesiones.insertar.assert_not_called()

    def test_medicion_fuera_del_catalogo(self):
        with self.assertRaises(SesionInvalida) as ctx:
            sesion_servicio.guardar(SesionLogDTO.desde_json(session_log(experiment='T0')), ORIGEN_VISOR)
        self.assertEqual(str(ctx.exception), 'La medición "V1" no está en el catálogo del experimento T0')
        self.sesiones.insertar.assert_not_called()

    def test_valor_que_la_base_no_acepta(self):
        self.sesiones.insertar_eventos.side_effect = DataError('numeric field overflow')
        with self.assertRaises(SesionInvalida):
            sesion_servicio.guardar(SesionLogDTO.desde_json(session_log()), ORIGEN_VISOR)

    def test_codigo_sin_letra_de_visor(self):
        sesion_servicio.guardar(SesionLogDTO.desde_json(session_log('EDITOR')), ORIGEN_VISOR)
        self.participantes.crear_si_no_existe.assert_called_once_with('EDITOR', None)


class RecibirEImportarTests(BaseServicioTest):
    def test_recibir_del_visor(self):
        with mock.patch(f'{MODULO}.guardar', return_value=('id', True)) as guardar:
            self.assertEqual(sesion_servicio.recibir_del_visor(json.dumps(session_log()).encode()), ('id', True))
        log, origen = guardar.call_args.args
        self.assertEqual((log.codigo_participante, origen), ('A001', ORIGEN_VISOR))

    def test_recibir_algo_que_no_es_json(self):
        for cuerpo in [b'{ no es json', b'\xff\xfe']:
            with self.subTest(cuerpo), self.assertRaises(SesionInvalida) as ctx:
                sesion_servicio.recibir_del_visor(cuerpo)
            self.assertEqual(str(ctx.exception), 'El cuerpo no es un JSON válido.')

    def test_importar_informa_nuevas_repetidas_e_invalidas(self):
        respuestas = iter([('a', True), ('a', False), ('b', True), ('c', True)])
        with mock.patch(f'{MODULO}.guardar', side_effect=lambda log, origen: next(respuestas)) as guardar:
            r = sesion_servicio.importar([
                {'name': 'uno.json', 'text': json.dumps(session_log('A001'))},
                {'name': 'copia.json', 'text': json.dumps(session_log('A001'))},
                {'name': 'varias.json', 'text': json.dumps([session_log('A002'), session_log('A003')])},
                {'name': 'roto.json', 'text': '{ no es json'},
                {'name': 'otro.json', 'text': json.dumps({'nombre': 'no es una sesión'})},
                {'name': 'vacio.json'},
                'no es un archivo',
            ])
        self.assertEqual((r.agregadas, r.repetidas), (3, 1))
        self.assertEqual(r.invalidas, [
            ('roto.json', 'No es un JSON válido'),
            ('otro.json', 'Falta el campo "participantCode"'),
            ('vacio.json', 'Archivo vacío o ilegible'),
            ('archivo', 'Archivo vacío o ilegible'),
        ])
        self.assertTrue(all(c.args[1] == ORIGEN_IMPORTADA for c in guardar.call_args_list))

    def test_importar_una_sesion_rechazada_sigue_con_las_demas(self):
        r = sesion_servicio.importar([
            {'name': 'n2.json', 'text': json.dumps(session_log(experiment='N2'))},
            {'name': 'ok.json', 'text': json.dumps(session_log())},
        ])
        self.assertEqual(r.agregadas, 1)
        self.assertEqual(r.invalidas, [('n2.json', 'El experimento "N2" no está en el catálogo de la base de datos')])

    def test_importar_con_formato_incorrecto(self):
        with self.assertRaises(DatosInvalidos):
            sesion_servicio.importar(None)


class ListarTests(BaseServicioTest):
    def test_arma_el_json_igual_al_que_envio_el_visor(self):
        """Simula las filas que devuelve el DAO para la sesión real A015 y revisa que el
        servicio vuelva a armar el mismo JSON (los tiempos, con 2 decimales)."""
        original = sesion_real_del_visor()
        dos = lambda x: Decimal(str(round(x, 2)))  # noqa: E731 - así devuelve PostgreSQL un numeric(9,2)
        self.sesiones.listar.return_value = [{
            'id': 3, 'participante_id': 'A015', 'experimento_id': 'N1', 'titulo': original['experimentTitle'],
            'inicio': datetime(2026, 11, 10, 23, 7, 51), 'termino': datetime(2026, 11, 10, 23, 8, 46),
            'completada': True, 'duracion_s': dos(original['durationSeconds']),
            'laboratorio_s': dos(original['laboratorySeconds']), 'correctas': 1, 'tareas_total': 6,
            'version_app': '0.9-feria', 'visor_modelo': original['device'], 'origen': 'visor',
            'recibida_en': datetime(2026, 11, 11, 2, 9, tzinfo=UTC),
        }]
        self.sesiones.listar_eventos.return_value = [
            {'sesion_id': 3, 'orden': n, 't_s': dos(e['t']), 'tipo': e['type'], 'tarea': e['task'],
             'detalle': e['detail'], 'selector': e['selector'], 'borne': e['jack'],
             **({'medido': e['measured'], 'esperado': e['expected'], 'veredicto': e['verdict'],
                 'intento': e['attempt']} if e['type'] == 'lectura' else
                {'medido': None, 'esperado': None, 'veredicto': None, 'intento': None})}
            for n, e in enumerate(original['events'], start=1)
        ]
        self.sesiones.listar_tareas.return_value = [
            {'sesion_id': 3, 'codigo': t['id'], 'intentos': t['attempts'], 'rechazos': t['rejected'],
             'veredicto_final': t['finalVerdict'], 'intento_primera_correcta': t['firstCorrectAttempt'] or None,
             'primera_lectura_s': None if t['firstReadingSeconds'] < 0 else dos(t['firstReadingSeconds']),
             'primera_correcta_s': None if t['firstCorrectSeconds'] < 0 else dos(t['firstCorrectSeconds'])}
            for t in original['tasks']
        ]

        [sesion] = sesion_servicio.listar()
        salida = sesion.a_json()
        self.assertEqual(salida['id'], 'A015_N1_2026-11-10T23:07:51')
        self.assertEqual(salida['receivedAt'], '2026-11-10T23:09:00')

        def redondeado(valor, clave=None):
            if isinstance(valor, dict):
                return {k: redondeado(v, k) for k, v in valor.items()}
            if isinstance(valor, list):
                return [redondeado(v) for v in valor]
            if clave in ('t', 'durationSeconds', 'laboratorySeconds', 'firstReadingSeconds', 'firstCorrectSeconds'):
                return round(valor, 2)
            return valor

        self.assertEqual(salida['log'], redondeado(original))

    def test_sin_sesiones(self):
        self.sesiones.listar.return_value = []
        self.sesiones.listar_eventos.return_value = []
        self.sesiones.listar_tareas.return_value = []
        self.assertEqual(sesion_servicio.listar(), [])


class EliminarTests(BaseServicioTest):
    def test_por_id_del_panel(self):
        self.sesiones.buscar.return_value = {'id': 2, 'participante_id': 'A001'}
        sesion_servicio.eliminar('A001_N1_2026-11-05T10:31:12')
        self.sesiones.buscar.assert_called_once_with('A001', 'N1', datetime(2026, 11, 5, 10, 31, 12))
        self.sesiones.borrar.assert_called_once_with(2)
        self.participantes.borrar_si_sobra.assert_called_once_with('A001')

    def test_codigo_con_guion_bajo(self):
        self.sesiones.buscar.return_value = {'id': 9, 'participante_id': 'MI_CODIGO'}
        sesion_servicio.eliminar('MI_CODIGO_N1_2026-11-05T10:31:12')
        self.sesiones.buscar.assert_called_once_with('MI_CODIGO', 'N1', datetime(2026, 11, 5, 10, 31, 12))

    def test_ids_que_no_existen(self):
        self.sesiones.buscar.return_value = None
        for id_sesion in ['no-es-un-id', 'A001_N1_ayer', 'A001_N1_2026-11-05T10:31:12']:
            with self.subTest(id_sesion), self.assertRaises(NoEncontrado):
                sesion_servicio.eliminar(id_sesion)
        self.sesiones.borrar.assert_not_called()

    def test_por_numero_interno(self):
        self.sesiones.obtener.return_value = {'id': 3, 'participante_id': 'A015'}
        sesion_servicio.eliminar_por_numero(3)
        self.sesiones.borrar.assert_called_once_with(3)
        self.participantes.borrar_si_sobra.assert_called_once_with('A015')
        self.sesiones.obtener.return_value = None
        with self.assertRaises(NoEncontrado):
            sesion_servicio.eliminar_por_numero(99)
