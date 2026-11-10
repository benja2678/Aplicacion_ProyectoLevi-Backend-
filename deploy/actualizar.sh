#!/bin/sh
# ------------------------------------------------------------------
# Actualiza el sistema con lo último que hay en GitHub.
#
# Uso (en el servidor):
#   sh proyecto-backend/deploy/actualizar.sh
#
#   1. Descarga los cambios de los 3 repositorios (git pull).
#   2. Hace un respaldo de la base de datos (por si una migración sale mal).
#   3. Reconstruye y reinicia solo los contenedores que cambiaron.
#      Los datos NO se pierden: viven en el volumen de la base de datos.
# ------------------------------------------------------------------
set -e

# Todo va dentro de main(): así el script se lee completo antes de ejecutarse,
# aunque el propio git pull lo modifique a mitad de camino.
main() {
    cd "$(dirname "$0")"
    base=../..

    for repo in proyecto-backend proyecto-db Aplicacion_tesis; do
        echo "== Descargando cambios de $repo"
        git -C "$base/$repo" pull --ff-only
    done

    if [ -n "$(docker compose ps --status running -q db 2>/dev/null)" ]; then
        echo "== Respaldo de la base de datos antes de actualizar"
        sh "$base/proyecto-db/scripts/respaldar.sh"
    fi

    echo "== Reconstruyendo y reiniciando los contenedores"
    docker compose up -d --build

    # Borra las imágenes viejas que quedaron sin usar (no toca los datos).
    docker image prune -f >/dev/null

    echo
    docker compose ps
    echo
    echo "Actualización terminada."
}

main "$@"
exit
