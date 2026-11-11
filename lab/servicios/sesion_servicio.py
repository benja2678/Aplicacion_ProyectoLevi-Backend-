"""
Sesiones.

Lo usan tres caminos:
- POST /api/sessions/ingest/  el visor envía una sesión con la llave X-Api-Key.
- POST /api/sessions/import/  el profesor sube archivos .json ("Cargar sesiones").
- GET y DELETE /api/sessions/ el panel lista y borra sesiones.

Reglas:
- Una sesión se identifica por participante + experimento + inicio. Si llega dos
  veces, no se duplica (el visor recibe 409 y la da por entregada).
- Solo se aceptan experimentos y mediciones que estén en el catálogo de la base
  (tablas experimento y tarea). Si no, la sesión se rechaza con un mensaje claro y el
  visor la conserva para reintentarla más tarde.
- El JSON se reparte en tablas (sesion, sesion_tarea, evento, lectura, rechazo) y al
  leerlo se vuelve a armar con la misma forma que lo envió Unity.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db import DataError, transaction

from ..dao import catalogo_dao, participante_dao, sesion_dao
from ..dto.fechas import leer_fecha_del_visor
from ..dto.sesion import (
    LECTURA,
    ORIGEN_IMPORTADA,
    ORIGEN_VISOR,
    RECHAZO,
    EventoDTO,
    ResultadoImportacionDTO,
    SesionGuardadaDTO,
    SesionInvalida,
    SesionLogDTO,
    TareaResumenDTO,
    leer_json,
)
from ..errores import DatosInvalidos, NoEncontrado
from . import letra_del_visor

# ------------------------------------------------------------------ #
# Recibir


def recibir_del_visor(cuerpo: bytes) -> tuple[str, bool]:
    """Guarda la sesión que envía el visor. Devuelve (id, creada)."""
    try:
        datos = leer_json(cuerpo)
    except (ValueError, UnicodeDecodeError):
        raise SesionInvalida('El cuerpo no es un JSON válido.') from None
    return guardar(SesionLogDTO.desde_json(datos), ORIGEN_VISOR)


def importar(archivos: Any) -> ResultadoImportacionDTO:
    """Botón "Cargar sesiones": [{"name": ..., "text": ...}]. Cada archivo puede traer
    una sesión o una lista de sesiones. Un archivo malo no detiene a los demás."""
    if not isinstance(archivos, list):
        raise DatosInvalidos('Se esperaba {"files": [{"name": ..., "text": ...}]}.')

    resultado = ResultadoImportacionDTO()
    for archivo in archivos:
        nombre = str(archivo.get('name') or 'archivo') if isinstance(archivo, dict) else 'archivo'
        texto = archivo.get('text') if isinstance(archivo, dict) else None
        if not isinstance(texto, str):
            resultado.invalidas.append((nombre, 'Archivo vacío o ilegible'))
            continue
        try:
            datos = leer_json(texto)
        except ValueError:
            resultado.invalidas.append((nombre, 'No es un JSON válido'))
            continue

        for item in datos if isinstance(datos, list) else [datos]:
            try:
                _, creada = guardar(SesionLogDTO.desde_json(item), ORIGEN_IMPORTADA)
            except DatosInvalidos as exc:
                resultado.invalidas.append((nombre, str(exc)))
                continue
            if creada:
                resultado.agregadas += 1
            else:
                resultado.repetidas += 1
    return resultado


def guardar(log: SesionLogDTO, origen: str) -> tuple[str, bool]:
    """Guarda la sesión con todo su detalle, o nada si algo falla. Devuelve (id, creada)."""
    if catalogo_dao.obtener_experimento(log.experimento_id) is None:
        raise SesionInvalida(f'El experimento "{log.experimento_id}" no está en el catálogo de la base de datos')
    tareas = catalogo_dao.tareas_del_experimento(log.experimento_id)
    _revisar_tareas(log, tareas)

    try:
        with transaction.atomic():
            participante_dao.crear_si_no_existe(log.codigo_participante, letra_del_visor(log.codigo_participante))
            sesion_id = sesion_dao.insertar(
                log.codigo_participante, log.experimento_id, log.inicio, log.termino, log.completada,
                log.duracion_s, log.laboratorio_s, log.correctas, log.tareas_total,
                log.version_app or None, log.visor_modelo or None, origen,
            )
            if sesion_id is None:
                return log.id, False  # ya estaba guardada

            sesion_dao.insertar_tareas(
                (sesion_id, tareas[t.codigo], t.intentos, t.rechazos, t.veredicto_final,
                 t.intento_primera_correcta or None, t.primera_lectura_s, t.primera_correcta_s)
                for t in log.tareas
            )
            eventos, lecturas, rechazos = [], [], []
            for orden, e in enumerate(log.eventos, start=1):
                tarea_id = tareas.get(e.tarea)
                etiqueta = e.tarea if (tarea_id is None and e.tarea) else None
                eventos.append((sesion_id, orden, e.t, e.tipo, tarea_id, etiqueta, e.detalle or None))
                if e.tipo == LECTURA:
                    lecturas.append((sesion_id, orden, e.medido, e.esperado, e.veredicto, e.intento,
                                     e.selector or None, e.borne or None))
                elif e.tipo == RECHAZO:
                    rechazos.append((sesion_id, orden, e.selector or None, e.borne or None))
            sesion_dao.insertar_eventos(eventos)
            sesion_dao.insertar_lecturas(lecturas)
            sesion_dao.insertar_rechazos(rechazos)
    except DataError:
        raise SesionInvalida('Un valor de la sesión no se puede guardar en la base de datos') from None
    return log.id, True


def _revisar_tareas(log: SesionLogDTO, tareas: dict[str, int]) -> None:
    """Las mediciones del resumen, de las lecturas y de los rechazos deben ser del catálogo."""
    usadas = [t.codigo for t in log.tareas]
    usadas += [e.tarea for e in log.eventos if e.tipo in (LECTURA, RECHAZO) and e.tarea]
    for codigo in usadas:
        if codigo not in tareas:
            raise SesionInvalida(
                f'La medición "{codigo}" no está en el catálogo del experimento {log.experimento_id}'
            )


# ------------------------------------------------------------------ #
# Listar


def listar() -> list[SesionGuardadaDTO]:
    eventos_por_sesion: dict[int, list[EventoDTO]] = defaultdict(list)
    for f in sesion_dao.listar_eventos():
        evento = EventoDTO(t=_flotante(f['t_s']), tipo=f['tipo'], tarea=f['tarea'], detalle=f['detalle'],
                           selector=f['selector'], borne=f['borne'])
        if f['tipo'] == LECTURA:
            evento.medido, evento.esperado = f['medido'], f['esperado']
            evento.veredicto, evento.intento = f['veredicto'], f['intento']
        eventos_por_sesion[f['sesion_id']].append(evento)

    tareas_por_sesion: dict[int, list[TareaResumenDTO]] = defaultdict(list)
    for f in sesion_dao.listar_tareas():
        tareas_por_sesion[f['sesion_id']].append(TareaResumenDTO(
            codigo=f['codigo'],
            intentos=f['intentos'],
            rechazos=f['rechazos'],
            veredicto_final=f['veredicto_final'],
            intento_primera_correcta=f['intento_primera_correcta'] or 0,
            primera_lectura_s=_flotante(f['primera_lectura_s']),
            primera_correcta_s=_flotante(f['primera_correcta_s']),
        ))

    return [
        SesionGuardadaDTO(
            log=SesionLogDTO(
                codigo_participante=s['participante_id'],
                experimento_id=s['experimento_id'],
                titulo_experimento=s['titulo'],
                version_app=s['version_app'] or '',
                visor_modelo=s['visor_modelo'] or '',
                inicio=s['inicio'],
                termino=s['termino'],
                completada=s['completada'],
                duracion_s=_flotante(s['duracion_s']),
                laboratorio_s=_flotante(s['laboratorio_s']),
                correctas=s['correctas'],
                tareas_total=s['tareas_total'],
                eventos=eventos_por_sesion[s['id']],
                tareas=tareas_por_sesion[s['id']],
            ),
            origen=s['origen'],
            recibida_en=s['recibida_en'],
        )
        for s in sesion_dao.listar()
    ]


def _flotante(valor: Decimal | float | None) -> float | None:
    """numeric de PostgreSQL -> número de JSON."""
    return None if valor is None else float(valor)


# ------------------------------------------------------------------ #
# Borrar


def eliminar(id_sesion: str) -> None:
    """Borra por el id del panel: participantCode_experimentId_startedAt."""
    partes = id_sesion.rsplit('_', 2)
    if len(partes) != 3:
        raise NoEncontrado()
    codigo, experimento_id, inicio_texto = partes
    try:
        inicio = leer_fecha_del_visor(inicio_texto)
    except ValueError:
        raise NoEncontrado() from None
    fila = sesion_dao.buscar(codigo, experimento_id, inicio)
    if fila is None:
        raise NoEncontrado()
    _borrar(fila)


def eliminar_por_numero(sesion_id: int) -> None:
    """Borra por el número interno de la tabla sesion (lo usa el panel /admin/)."""
    fila = sesion_dao.obtener(sesion_id)
    if fila is None:
        raise NoEncontrado()
    _borrar(fila)


def _borrar(fila: dict) -> None:
    with transaction.atomic():
        sesion_dao.borrar(fila['id'])
        # Si era la última sesión de un código sin alumno, el código ya no se necesita.
        participante_dao.borrar_si_sobra(fila['participante_id'])
