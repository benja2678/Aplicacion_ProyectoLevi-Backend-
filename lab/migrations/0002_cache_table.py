"""Crea la tabla de caché (cache_table) que usa el límite de intentos de login.

Así basta con `python manage.py migrate`; no hay que acordarse de `createcachetable`.
"""

from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    call_command('createcachetable', database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [('lab', '0001_initial')]

    operations = [migrations.RunPython(create_cache_table, migrations.RunPython.noop)]
