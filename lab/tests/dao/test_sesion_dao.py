"""Tests de lab/dao/sesion_dao.py contra el PostgreSQL de prueba.

Datos de base_pruebas.sql:
    sesion 1: A001 · T0 · 2026-11-04 09:15:00 · importada · 8 eventos (1 lectura, 1 rechazo) · 1 tarea
    sesion 2: A001 · N1 · 2026-11-05 10:31:12 · visor     · 9 eventos (1 lectura, 1 rechazo) · 6 tareas
    sesion 3: A015 · N1 · 2026-11-10 23:07:51 · visor     · 21 eventos (2 lecturas)          · 6 tareas
"""

from datetime import UTC, datetime
from decimal import Decimal

from django.test import TestCase

from lab.dao import catalogo_dao, sesion_dao

from ..ayudas import contar, sql_uno

INICIO_N1 = datetime(2026, 11, 5, 10, 31, 12)


class LeerTests(TestCase):
    def test_listar_en_orden_de_llegada(self):
        sesiones = sesion_dao.listar()
        self.assertEqual([(s['id'], s['participante_id'], s['experimento_id']) for s in sesiones],
                         [(1, 'A001', 'T0'), (2, 'A001', 'N1'), (3, 'A015', 'N1')])
        s = sesiones[1]
        self.assertEqual(s['titulo'], 'Ley de Ohm en un circuito mixto')
        self.assertEqual((s['inicio'], s['termino']), (INICIO_N1, datetime(2026, 11, 5, 10, 45, 2)))
        self.assertEqual((s['duracion_s'], s['laboratorio_s']), (Decimal('830.50'), Decimal('700.25')))
        self.assertEqual((s['completada'], s['correctas'], s['tareas_total']), (True, 1, 6))
        self.assertEqual((s['version_app'], s['visor_modelo'], s['origen']), ('0.9-feria', 'Meta Quest 3S', 'visor'))
        self.assertEqual(s['recibida_en'], datetime(2026, 11, 5, 13, 46, tzinfo=UTC))

    def test_listar_eventos_con_su_lectura_o_rechazo(self):
        eventos = sesion_dao.listar_eventos()
        self.assertEqual(len(eventos), 38)
        de_la_2 = [e for e in eventos if e['sesion_id'] == 2]
        self.assertEqual([e['orden'] for e in de_la_2], list(range(1, 10)))
        vista, lectura, rechazo = de_la_2[2], de_la_2[6], de_la_2[7]
        self.assertEqual((vista['tipo'], vista['tarea'], vista['detalle']), ('vista', 'pizarra', 'esquema'))
        self.assertEqual((lectura['tarea'], lectura['medido'], lectura['esperado'], lectura['veredicto'],
                          lectura['intento'], lectura['selector'], lectura['borne']),
                         ('V1', 4.98, 4.98400921069464, 'Correct', 1, '20 V', 'VoltOhmMilliamp'))
        self.assertEqual((rechazo['tarea'], rechazo['detalle'], rechazo['selector'], rechazo['medido']),
                         ('V2', 'OverRange', '200m V', None))
        # Lo que no aplica llega como texto vacío, no como NULL.
        self.assertEqual((de_la_2[0]['tarea'], de_la_2[0]['selector']), ('', ''))

    def test_listar_tareas_en_el_orden_del_catalogo(self):
        tareas = [t for t in sesion_dao.listar_tareas() if t['sesion_id'] == 2]
        self.assertEqual([t['codigo'] for t in tareas], ['V1', 'V2', 'V3', 'I_total', 'I_R2', 'I_R4'])
        self.assertEqual(tareas[0], {'sesion_id': 2, 'codigo': 'V1', 'intentos': 1, 'rechazos': 0,
                                     'veredicto_final': 'Correct', 'intento_primera_correcta': 1,
                                     'primera_lectura_s': Decimal('47.65'), 'primera_correcta_s': Decimal('47.65')})
        self.assertIsNone(tareas[1]['primera_lectura_s'])
        self.assertEqual(len(sesion_dao.listar_tareas()), 13)

    def test_buscar_y_obtener(self):
        self.assertEqual(sesion_dao.buscar('A001', 'N1', INICIO_N1), {'id': 2, 'participante_id': 'A001'})
        self.assertIsNone(sesion_dao.buscar('A001', 'N1', datetime(2026, 1, 1)))
        self.assertEqual(sesion_dao.obtener(3), {'id': 3, 'participante_id': 'A015'})
        self.assertIsNone(sesion_dao.obtener(99))


class GuardarYBorrarTests(TestCase):
    def nueva(self, inicio=datetime(2026, 11, 12, 8, 0), origen='importada'):
        return sesion_dao.insertar('A002', 'N1', inicio, None, False, 12.345, None, 0, 6, '', None, origen)

    def test_insertar_devuelve_el_id(self):
        sid = self.nueva()
        # Mayor que las 3 de base_pruebas.sql (el número exacto depende de otros tests:
        # PostgreSQL no devuelve los números usados aunque el test se deshaga).
        self.assertGreater(sid, 3)
        self.assertEqual(sql_uno('select origen from sesion where id = %s', [sid]), 'importada')
        self.assertEqual(sql_uno('select duracion_s from sesion where id = %s', [sid]), Decimal('12.35'))  # 2 decimales

    def test_insertar_una_repetida_devuelve_none(self):
        self.assertIsNone(sesion_dao.insertar('A001', 'N1', INICIO_N1, None, True, 1, 1, 0, 6, '', '', 'visor'))
        self.assertEqual(contar('sesion'), 3)

    def test_insertar_el_detalle(self):
        sid = self.nueva()
        v1 = catalogo_dao.tareas_del_experimento('N1')['V1']
        sesion_dao.insertar_eventos([
            (sid, 1, 0.0, 'etapa', None, None, 'Briefing'),
            (sid, 2, 3.5, 'tutorial', None, 'medir', 'cumplido'),
            (sid, 3, 7.25, 'lectura', v1, None, None),
            (sid, 4, 9.0, 'rechazo', v1, None, 'MeterOff'),
        ])
        sesion_dao.insertar_lecturas([(sid, 3, 4.9, 5.0, 'OutOfTolerance', 1, '20 V', None)])
        sesion_dao.insertar_rechazos([(sid, 4, 'OFF', 'VoltOhmMilliamp')])
        sesion_dao.insertar_tareas([(sid, v1, 1, 1, 'OutOfTolerance', None, 7.25, None)])

        eventos = [e for e in sesion_dao.listar_eventos() if e['sesion_id'] == sid]
        self.assertEqual([(e['tipo'], e['tarea']) for e in eventos],
                         [('etapa', ''), ('tutorial', 'medir'), ('lectura', 'V1'), ('rechazo', 'V1')])
        self.assertEqual((eventos[2]['medido'], eventos[2]['borne']), (4.9, ''))
        self.assertEqual(eventos[3]['selector'], 'OFF')
        [t] = [t for t in sesion_dao.listar_tareas() if t['sesion_id'] == sid]
        self.assertEqual((t['codigo'], t['veredicto_final'], t['primera_lectura_s']), ('V1', 'OutOfTolerance', Decimal('7.25')))

    def test_borrar_borra_todo_su_detalle(self):
        self.assertEqual(sesion_dao.borrar(2), 1)
        self.assertEqual(contar('sesion'), 2)
        for tabla in ['evento', 'lectura', 'rechazo', 'sesion_tarea']:
            with self.subTest(tabla):
                self.assertEqual(contar(tabla, 'sesion_id = %s', [2]), 0)
        self.assertEqual(contar('evento'), 29)  # quedan los de las sesiones 1 y 3
        self.assertEqual(sesion_dao.borrar(2), 0)
