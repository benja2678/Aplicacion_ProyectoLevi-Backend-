"""Tests unitarios de lab/dto/sesion.py (sin base de datos)."""

import json
from datetime import UTC, datetime

from django.test import SimpleTestCase

from lab.dto.sesion import (
    ResultadoImportacionDTO,
    SesionGuardadaDTO,
    SesionInvalida,
    SesionLogDTO,
    TareaResumenDTO,
    leer_json,
)

from ..ayudas import evento, session_log, sesion_real_del_visor


class LeerJsonTests(SimpleTestCase):
    def test_texto_y_bytes(self):
        self.assertEqual(leer_json('{"a": 1}'), {'a': 1})
        self.assertEqual(leer_json('{"a": "ñ"}'.encode()), {'a': 'ñ'})

    def test_quita_la_marca_bom(self):
        self.assertEqual(leer_json('﻿{"a": 1}'), {'a': 1})

    def test_nan_e_infinito_pasan_a_null(self):
        self.assertEqual(leer_json('{"a": NaN, "b": [Infinity, 1.5]}'), {'a': None, 'b': [None, 1.5]})

    def test_texto_que_no_es_json(self):
        with self.assertRaises(ValueError):
            leer_json('{ no es json')


class SesionLogDTOTests(SimpleTestCase):
    def test_ida_y_vuelta_igual_y_en_el_mismo_orden(self):
        log = session_log()
        resultado = SesionLogDTO.desde_json(log).a_json()
        self.assertEqual(resultado, log)
        self.assertEqual(list(resultado), list(log))
        self.assertEqual(list(resultado['events'][0]), list(log['events'][0]))

    def test_json_real_de_un_visor(self):
        original = sesion_real_del_visor()
        dto = SesionLogDTO.desde_json(original)
        self.assertEqual(dto.id, 'A015_N1_2026-11-10T23:07:51')
        self.assertEqual(len(dto.eventos), 21)
        self.assertEqual(dto.a_json(), original)

    def test_id_y_fechas(self):
        dto = SesionLogDTO.desde_json(session_log(started='2026-11-05T10:31:12.250'))
        self.assertEqual(dto.inicio, datetime(2026, 11, 5, 10, 31, 12, 250000))
        self.assertEqual(dto.id, 'A001_N1_2026-11-05T10:31:12.250')
        self.assertEqual(dto.termino, datetime(2026, 11, 5, 10, 45, 2))

    def test_campos_opcionales(self):
        log = session_log(finishedAt='', tasks=None, appVersion=None)
        del log['completed']
        dto = SesionLogDTO.desde_json(log)
        self.assertIsNone(dto.termino)
        self.assertEqual(dto.tareas, [])
        self.assertFalse(dto.completada)
        self.assertEqual(dto.a_json()['finishedAt'], '')
        self.assertEqual(dto.a_json()['appVersion'], '')

    def test_solo_lectura_y_rechazo_guardan_el_multimetro(self):
        log = session_log(events=[
            evento(1.0, 'selector', detail='20 V', selector='no aplica'),
            evento(2.0, 'rechazo', task='V2', detail='OverRange', selector='200m V', jack='VoltOhmMilliamp',
                   measured=9.9),
        ])
        selector, rechazo = SesionLogDTO.desde_json(log).eventos
        self.assertEqual(selector.selector, '')
        self.assertEqual((rechazo.selector, rechazo.borne, rechazo.medido), ('200m V', 'VoltOhmMilliamp', 0.0))

    def test_errores_con_mensaje_claro(self):
        casos = {
            'No tiene el formato de registro de sesión': [],
            'Falta el campo "participantCode"': {'hola': 1},
        }
        for mensaje, datos in casos.items():
            with self.subTest(mensaje), self.assertRaises(SesionInvalida) as ctx:
                SesionLogDTO.desde_json(datos)
            self.assertEqual(str(ctx.exception), mensaje)

        cambios = {
            'Falta el campo "startedAt"': {'startedAt': ''},
            'El campo "experimentId" es demasiado largo': {'experimentId': 'N' * 51},
            'Falta la lista "events"': {'events': 'nada'},
            '"tasks" debe ser una lista': {'tasks': 'nada'},
            '"completed" debe ser true o false': {'completed': 'sí'},
            'El campo "startedAt" no es una fecha y hora local válida ("ayer")': {'startedAt': 'ayer'},
            'Evento 1: tipo de evento desconocido "saltar"': {'events': [{'t': 1, 'type': 'saltar'}]},
            'Evento 1: falta "t"': {'events': [{'type': 'etapa'}]},
            'Evento 1: "t" es demasiado grande': {'events': [{'t': 1e8, 'type': 'etapa'}]},
            'Evento 1: "measured" debe ser un número': {
                'events': [{'t': 1, 'type': 'lectura', 'task': 'V1', 'expected': 1, 'verdict': 'Correct'}]},
            'Evento 1: veredicto desconocido "Casi"': {
                'events': [{'t': 1, 'type': 'lectura', 'task': 'V1', 'measured': 1, 'expected': 1, 'verdict': 'Casi'}]},
            'Tarea 1: falta "id"': {'tasks': [{'attempts': 1}]},
            'Tarea 1: veredicto final desconocido "Bien"': {'tasks': [{'id': 'V1', 'finalVerdict': 'Bien'}]},
            'Tarea 1: "attempts" debe ser un número entero': {'tasks': [{'id': 'V1', 'attempts': 1.5}]},
            'La tarea "V1" aparece más de una vez en "tasks"': {'tasks': [{'id': 'V1'}, {'id': 'V1'}]},
        }
        for mensaje, cambio in cambios.items():
            with self.subTest(mensaje), self.assertRaises(SesionInvalida) as ctx:
                SesionLogDTO.desde_json(session_log(**cambio))
            self.assertEqual(str(ctx.exception), mensaje)


class TareaResumenDTOTests(SimpleTestCase):
    def test_menos_uno_significa_que_no_ocurrio(self):
        t = TareaResumenDTO.desde_json({'id': 'V3', 'firstReadingSeconds': -1.0, 'firstCorrectSeconds': -1}, 1)
        self.assertIsNone(t.primera_lectura_s)
        self.assertIsNone(t.primera_correcta_s)
        self.assertEqual(t.veredicto_final, 'SinRegistrar')
        self.assertEqual(t.a_json()['firstReadingSeconds'], -1.0)


class SalidasTests(SimpleTestCase):
    def test_sesion_guardada_con_la_forma_del_frontend(self):
        dto = SesionGuardadaDTO(log=SesionLogDTO.desde_json(session_log()), origen='visor',
                                recibida_en=datetime(2026, 11, 5, 13, 46, tzinfo=UTC))
        salida = dto.a_json()
        self.assertEqual(set(salida), {'id', 'log', 'source', 'receivedAt'})
        self.assertEqual(salida['id'], 'A001_N1_2026-11-05T10:31:12')
        self.assertEqual(salida['source'], 'visor')
        self.assertEqual(salida['receivedAt'], '2026-11-05T10:46:00')
        json.dumps(salida)  # se puede convertir a JSON

    def test_resultado_de_importacion(self):
        r = ResultadoImportacionDTO(agregadas=2, repetidas=1, invalidas=[('a.json', 'No es un JSON válido')])
        self.assertEqual(r.a_json(), {'added': 2, 'duplicated': 1,
                                      'invalid': [{'file': 'a.json', 'reason': 'No es un JSON válido'}]})
