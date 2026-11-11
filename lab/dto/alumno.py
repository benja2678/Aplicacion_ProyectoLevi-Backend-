"""
DTO del alumno.

En la base de datos un alumno es una fila de `participante` CON nombre
(ver levi-db-scripts, v2.2). El código del visor es la llave de esa fila, por eso
también es el `id` que ve el panel web.

    AlumnoDTO        -> lo que la API devuelve:
                        {id, nombre, apellido, asignatura, codigoParticipante, creadoEn}
    AlumnoEntradaDTO -> lo que el panel envía al crear o editar.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..utils.errores import DatosInvalidos
from .fechas import a_hora_local

LARGO_TEXTO = 200
LARGO_CODIGO = 50


@dataclass(frozen=True)
class AlumnoDTO:
    codigo: str
    nombre: str
    apellido: str
    asignatura: str
    registrado: datetime

    @classmethod
    def desde_fila(cls, fila: dict) -> 'AlumnoDTO':
        return cls(
            codigo=fila['codigo'],
            nombre=fila['nombre'] or '',
            apellido=fila['apellido'] or '',
            asignatura=fila['asignatura'] or '',
            registrado=fila['registrado'],
        )

    def a_json(self) -> dict:
        return {
            'id': self.codigo,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'asignatura': self.asignatura,
            'codigoParticipante': self.codigo,
            'creadoEn': a_hora_local(self.registrado),
        }


@dataclass(frozen=True)
class AlumnoEntradaDTO:
    nombre: str
    asignatura: str
    codigo: str
    # None = la petición no trajo "apellido" (el panel todavía no tiene ese campo):
    # al editar se conserva el que ya estaba guardado.
    apellido: str | None = None

    @classmethod
    def desde_json(cls, datos: Any) -> 'AlumnoEntradaDTO':
        if not isinstance(datos, dict):
            raise DatosInvalidos('Se esperaba un objeto JSON con los datos del alumno.')
        errores: dict[str, list[str]] = {}

        def texto(campo: str, largo: int, obligatorio: str | None = None) -> str:
            valor = datos.get(campo, '')
            if valor is None:
                valor = ''
            if not isinstance(valor, str):
                errores[campo] = ['Debe ser un texto.']
                return ''
            valor = valor.strip()
            if obligatorio and not valor:
                errores[campo] = [obligatorio]
            elif len(valor) > largo:
                errores[campo] = [f'No puede tener más de {largo} caracteres.']
            return valor

        nombre = texto('nombre', LARGO_TEXTO, obligatorio='Escribe el nombre del alumno.')
        asignatura = texto('asignatura', LARGO_TEXTO)
        codigo = texto('codigoParticipante', LARGO_CODIGO, obligatorio='Escribe el código del visor.').upper()
        apellido = texto('apellido', LARGO_TEXTO) if 'apellido' in datos else None

        if errores:
            raise DatosInvalidos(campos=errores)
        return cls(nombre=nombre, asignatura=asignatura, codigo=codigo, apellido=apellido)
