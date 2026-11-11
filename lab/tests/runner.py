"""
Ejecutor de tests: después de que Django crea la base de prueba (test_<base>), le
aplica los scripts de levi-db-scripts para crear las tablas del laboratorio.

Así los tests usan EXACTAMENTE el mismo esquema que el servidor.
Cuando se agregue una versión nueva en levi-db-scripts, se suma aquí al final.
"""

from django.conf import settings
from django.db import connections
from django.test.runner import DiscoverRunner

# En orden. Los "drop" no se ejecutan.
SCRIPTS = [
    'Version_2.0.0/levidb.sql',              # tablas y vistas
    'Version_2.1.0/insert_datosbase.sql',    # catálogo de experimentos y tareas
    'Version_2.2.0/alter_nombre_asign.sql',  # nombre, apellido y asignatura del alumno
    'Version_2.3.0/alter_datos_visor.sql',   # origen, etiqueta, rechazos
]


class LeviTestRunner(DiscoverRunner):
    def setup_databases(self, **kwargs):
        configuracion = super().setup_databases(**kwargs)
        aplicar_scripts(connections['default'])
        return configuracion


def aplicar_scripts(conexion) -> None:
    carpeta = settings.LEVI_DB_SCRIPTS
    with conexion.cursor() as cursor:
        cursor.execute("select to_regclass('public.sesion') is not null")
        if cursor.fetchone()[0]:
            return  # ya estaban (por ejemplo, con --keepdb)
        for nombre in SCRIPTS:
            ruta = carpeta / nombre
            if not ruta.is_file():
                raise RuntimeError(
                    f'No se encontró {ruta}. Clona levi-db-scripts junto a proyecto-backend '
                    'o indica su carpeta en LEVI_DB_SCRIPTS.'
                )
            sql = ruta.read_text(encoding='utf-8-sig')
            if not sql.strip():
                raise RuntimeError(f'El script {ruta} está vacío: no se pueden crear las tablas.')
            cursor.execute(sql)
