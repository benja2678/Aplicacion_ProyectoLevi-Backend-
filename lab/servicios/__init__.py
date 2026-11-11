"""
Capa de servicios (reglas del negocio).

- alumno_servicio.py   registrar, editar y quitar alumnos (sobre la tabla participante).
- sesion_servicio.py   recibir sesiones del visor, importarlas a mano, listarlas y borrarlas.

Reciben y devuelven DTO, usan los DAO para leer y guardar, y deciden las
transacciones (todo o nada). No conocen HTTP: los errores se lanzan como
DatosInvalidos o NoEncontrado (lab/utils/errores.py).
"""

import re

_CODIGO_CON_LETRA = re.compile(r'^([A-Z])\d+$')


def letra_del_visor(codigo: str) -> str | None:
    """A015 -> 'A'. La letra identifica al visor que asigna los códigos.
    Para códigos con otra forma (por ejemplo EDITOR) no hay letra."""
    coincide = _CODIGO_CON_LETRA.match(codigo)
    return coincide.group(1) if coincide else None
