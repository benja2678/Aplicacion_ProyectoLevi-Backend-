"""
Capa DAO (acceso a datos).

Es la ÚNICA capa que habla con PostgreSQL, y lo hace con consultas SQL escritas a
mano sobre las tablas de levi-db-scripts:

- base.py               ayudas para ejecutar SQL y recibir filas como diccionarios.
- catalogo_dao.py       experimento y tarea (catálogo, solo lectura).
- participante_dao.py   participante (código del visor + datos del alumno).
- sesion_dao.py         sesion, sesion_tarea, evento, lectura y rechazo.

No valida reglas de negocio (eso es del servicio): solo guarda y lee.
Los parámetros siempre van como %s (nunca pegados al texto), así no hay inyección SQL.
"""
