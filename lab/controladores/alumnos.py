"""
Alumnos (solo el profesor, con token).

    GET    /api/students/            lista
    POST   /api/students/            crear     {nombre, apellido?, asignatura, codigoParticipante}
    GET    /api/students/<código>/   uno
    PUT    /api/students/<código>/   editar    (si cambia el código, cambia también el id)
    DELETE /api/students/<código>/   quitar    (sus sesiones se conservan)
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..dto.alumno import AlumnoEntradaDTO
from ..servicios import alumno_servicio


class AlumnosControlador(APIView):
    def get(self, request):
        return Response([a.a_json() for a in alumno_servicio.listar()])

    def post(self, request):
        entrada = AlumnoEntradaDTO.desde_json(request.data)
        alumno = alumno_servicio.crear(entrada)
        return Response(alumno.a_json(), status=status.HTTP_201_CREATED)


class AlumnoControlador(APIView):
    def get(self, request, codigo: str):
        return Response(alumno_servicio.obtener(codigo).a_json())

    def put(self, request, codigo: str):
        entrada = AlumnoEntradaDTO.desde_json(request.data)
        return Response(alumno_servicio.actualizar(codigo, entrada).a_json())

    def delete(self, request, codigo: str):
        alumno_servicio.eliminar(codigo)
        return Response(status=status.HTTP_204_NO_CONTENT)
