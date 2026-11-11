"""
Alumnos del panel.

Un alumno es una fila de `participante` con nombre. Reglas (las mismas que antes de
pasar a la nueva base de datos):

- Un código pertenece a un solo alumno.
- Se puede registrar un alumno con un código cuyas sesiones ya llegaron: esas
  sesiones pasan a verse en su ficha.
- Quitar un alumno NO borra sus sesiones: el código vuelve a quedar "sin alumno".
- Cambiar el código de un alumno lo mueve al código nuevo; las sesiones del código
  anterior quedan sin alumno (las sesiones nunca cambian de código: es el que
  registró el visor).
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..dao import participante_dao
from ..dto.alumno import AlumnoDTO, AlumnoEntradaDTO
from ..utils.errores import DatosInvalidos, NoEncontrado
from . import letra_del_visor


def _codigo_ocupado(codigo: str) -> DatosInvalidos:
    return DatosInvalidos(campos={'codigoParticipante': [f'El código {codigo} ya está asignado a otro alumno.']})


def listar() -> list[AlumnoDTO]:
    return [AlumnoDTO.desde_fila(f) for f in participante_dao.listar_alumnos()]


def obtener(codigo: str) -> AlumnoDTO:
    fila = participante_dao.obtener(codigo)
    if fila is None or fila['nombre'] is None:
        raise NoEncontrado()
    return AlumnoDTO.desde_fila(fila)


def codigo_disponible(codigo: str) -> bool:
    fila = participante_dao.obtener(codigo)
    return fila is None or fila['nombre'] is None


def crear(entrada: AlumnoEntradaDTO) -> AlumnoDTO:
    apellido = entrada.apellido or ''
    try:
        with transaction.atomic():
            fila = participante_dao.obtener(entrada.codigo, bloquear=True)
            if fila is None:
                participante_dao.crear_alumno(entrada.codigo, letra_del_visor(entrada.codigo),
                                              entrada.nombre, apellido, entrada.asignatura)
            elif fila['nombre'] is not None:
                raise _codigo_ocupado(entrada.codigo)
            else:
                # El código ya tenía sesiones: desde ahora es de este alumno.
                participante_dao.guardar_datos_alumno(entrada.codigo, entrada.nombre, apellido,
                                                      entrada.asignatura, registrado=timezone.now())
    except IntegrityError:
        # Otra petición creó el mismo código en el mismo instante.
        raise _codigo_ocupado(entrada.codigo) from None
    return obtener(entrada.codigo)


def actualizar(codigo_actual: str, entrada: AlumnoEntradaDTO) -> AlumnoDTO:
    try:
        with transaction.atomic():
            actual = participante_dao.obtener(codigo_actual, bloquear=True)
            if actual is None or actual['nombre'] is None:
                raise NoEncontrado()
            # Si el panel no envió apellido, se conserva el guardado.
            apellido = entrada.apellido if entrada.apellido is not None else (actual['apellido'] or '')

            if entrada.codigo == codigo_actual:
                participante_dao.guardar_datos_alumno(codigo_actual, entrada.nombre, apellido, entrada.asignatura)
            else:
                destino = participante_dao.obtener(entrada.codigo, bloquear=True)
                if destino is not None and destino['nombre'] is not None:
                    raise _codigo_ocupado(entrada.codigo)
                # Se mantiene la fecha de registro original (el orden de la lista no cambia).
                if destino is None:
                    participante_dao.crear_alumno(entrada.codigo, letra_del_visor(entrada.codigo), entrada.nombre,
                                                  apellido, entrada.asignatura, registrado=actual['registrado'])
                else:
                    participante_dao.guardar_datos_alumno(entrada.codigo, entrada.nombre, apellido,
                                                          entrada.asignatura, registrado=actual['registrado'])
                _liberar(codigo_actual)
    except IntegrityError:
        raise _codigo_ocupado(entrada.codigo) from None
    return obtener(entrada.codigo)


def eliminar(codigo: str) -> None:
    with transaction.atomic():
        fila = participante_dao.obtener(codigo, bloquear=True)
        if fila is None or fila['nombre'] is None:
            raise NoEncontrado()
        _liberar(codigo)


def _liberar(codigo: str) -> None:
    """El código deja de ser de un alumno. Si además no tiene sesiones, se borra la fila."""
    participante_dao.quitar_datos_alumno(codigo)
    participante_dao.borrar_si_sobra(codigo)
