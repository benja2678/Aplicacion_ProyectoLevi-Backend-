#!/bin/sh
# ------------------------------------------------------------------
# Script de arranque del contenedor del backend (lo ejecuta Docker).
#
#   1. Espera a que PostgreSQL esté listo.
#   2. Aplica las migraciones (crea o actualiza las tablas).
#   3. Arranca gunicorn, el servidor web de Django, en el puerto 8000.
#
# Si un paso importante falla (1 o 2), el contenedor se detiene y Docker lo
# vuelve a intentar. Ver los mensajes con: docker compose logs backend
# ------------------------------------------------------------------
set -e

echo "[inicio] Esperando la base de datos..."
python manage.py wait_for_db --timeout 60

echo "[inicio] Aplicando migraciones..."
python manage.py migrate --noinput

echo "[inicio] Arrancando el servidor en el puerto 8000..."
# exec: gunicorn reemplaza a este script, así recibe directo la señal de apagado.
exec "$@"
