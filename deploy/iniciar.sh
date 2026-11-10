#!/bin/sh
# ------------------------------------------------------------------
# Enciende todo el sistema (base de datos + backend + página web).
#
# Uso (en el servidor, desde cualquier carpeta):
#   sh proyecto-backend/deploy/iniciar.sh
#
# Antes revisa que todo esté en su lugar: Docker instalado, deploy/.env completo
# y los 3 repositorios uno al lado del otro. Se puede ejecutar las veces que
# quieras: si ya está encendido, solo aplica los cambios que haya.
# ------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

fail() {
    echo "ERROR: $1" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "no encuentro Docker. Instálalo primero (ver DEPLOY.md)."

[ -f .env ] || fail "falta el archivo deploy/.env
  Créalo con:   cp .env.example .env
  y completa los valores (ver los comentarios dentro del archivo)."

if grep -q '=cambia-esto' .env; then
    echo "ERROR: deploy/.env todavía tiene valores de ejemplo (cambia-esto) en:" >&2
    grep '=cambia-esto' .env | cut -d= -f1 | sed 's/^/  - /' >&2
    exit 1
fi

for var in SECRET_KEY UNITY_API_KEY POSTGRES_PASSWORD ALLOWED_HOSTS; do
    grep -Eq "^${var}=.+" .env || fail "falta un valor para $var en deploy/.env"
done

for dir in ../../proyecto-db ../../Aplicacion_tesis/frontend; do
    [ -d "$dir" ] || fail "no encuentro la carpeta $dir
  Los 3 repositorios deben estar juntos: proyecto-backend, proyecto-db y Aplicacion_tesis."
done

echo "== Construyendo y encendiendo los contenedores (la primera vez tarda varios minutos)..."
docker compose up -d --build

echo
docker compose ps

PORT=$(grep -E '^HTTP_PORT=' .env | cut -d= -f2 | tr -d '\r')
PORT=${PORT:-80}
echo
echo "Listo. Abre en el navegador:  http://IP-DEL-SERVIDOR:$PORT/"
echo "Para ver los mensajes del backend:  docker compose -f $(pwd)/docker-compose.yml logs -f backend"
