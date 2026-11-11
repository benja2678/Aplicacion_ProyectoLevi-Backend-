# ------------------------------------------------------------------
# Imagen de Docker del backend: Django + gunicorn en el puerto 8000.
#
# No se usa sola: la arranca docker compose (ver deploy/docker-compose.yml),
# que le entrega las variables de entorno (contraseñas, llaves, base de datos).
# ------------------------------------------------------------------
FROM python:3.13-slim

# - No crear archivos .pyc y mostrar los mensajes al instante en los logs.
# - WEB_CONCURRENCY: cuántos procesos de gunicorn atienden peticiones a la vez.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    WEB_CONCURRENCY=3

# Usuario sin privilegios para ejecutar la aplicación (más seguro que root).
RUN useradd --create-home --shell /usr/sbin/nologin app

WORKDIR /app

# Primero solo las librerías: si requirements.txt no cambia, Docker reutiliza
# este paso y las siguientes construcciones son mucho más rápidas.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Luego el código (lo que excluye .dockerignore no se copia: .env, venv, etc.).
COPY . .

USER app

EXPOSE 8000

ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--timeout", "120", "--access-logfile", "-"]
