"""
Capa DTO (objetos de transferencia de datos).

Definen la FORMA de los datos que entran y salen de la API, y validan lo que llega:
- alumno.py:  el alumno tal como lo ve el panel web (src/types.ts → Student).
- sesion.py:  el registro de sesión que envía el visor (SessionLog.cs de Unity) y
              la sesión guardada que se le devuelve al panel (StoredSession).
- fechas.py:  cómo se escriben y leen las fechas (hora local, sin zona).

No consultan la base de datos ni conocen HTTP.
"""
