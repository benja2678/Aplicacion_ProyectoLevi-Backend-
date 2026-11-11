# Laboratorio VR · Backend (Django)

API del panel docente del simulador de electrónica en realidad virtual (Unity, Meta Quest 3S).
Recibe las sesiones que envían los visores y se las muestra **solo al profesor**.

Va junto a los otros repositorios del proyecto:

```
carpeta/
├── Aplicacion_tesis/     frontend (React) + Nginx
├── proyecto-backend/     este repositorio (Django + Docker Compose en deploy/)
├── levi-db-scripts/      scripts SQL de la base de datos, por versión (tablas, catálogo, cambios)
└── proyecto-db/          imagen de PostgreSQL para Docker + respaldos
```

## Cómo está organizado: 4 capas

```
petición HTTP
   │
   ▼
controladores/   lee la petición y responde (sin reglas ni SQL)
   │   DTO        forma de los datos que entran y salen, y su validación
   ▼
servicios/       reglas: catálogo, duplicados, alumnos, transacciones
   │
   ▼
dao/             consultas SQL escritas a mano (la única capa que toca la base)
   │
   ▼
PostgreSQL       tablas de levi-db-scripts
```

Las tablas del laboratorio (`participante`, `sesion`, `evento`, `lectura`, `rechazo`,
`sesion_tarea`, `experimento`, `tarea`…) **las crean los scripts de `levi-db-scripts`,
no Django**. Django solo crea las suyas: usuarios, tokens invalidados y la caché del login.

## Cómo se protege el acceso

| Quién | Cómo entra | Qué puede hacer |
|---|---|---|
| Profesor (web) | usuario + contraseña → **token JWT** (dura 30 min y se renueva hasta 8 h) | todo |
| Unity (Meta Quest) | llave fija en el encabezado `X-Api-Key` | **solo** enviar sesiones |
| Cualquier otro | — | nada (401/403) |

- No existe registro público: la cuenta del profesor se crea con un comando.
- El login permite 5 intentos por minuto por IP; con más, responde 429.
- Al cerrar sesión, el token de renovación queda invalidado.

## Endpoints (todos bajo `/api/`)

| Método y ruta | Acceso | Para qué |
|---|---|---|
| `GET health/` | público | saber si el backend está vivo |
| `POST auth/login/` | público (con límite) | `{username, password}` → `{access, refresh}` |
| `POST auth/refresh/` | público | `{refresh}` → `{access}` nuevo |
| `POST auth/logout/` | público | `{refresh}` → lo invalida |
| `GET auth/me/` | token | datos del usuario conectado |
| `GET, POST students/` | token | listar / crear alumnos |
| `GET, PUT, DELETE students/<código>/` | token | ver / editar / quitar un alumno (sus sesiones se conservan). El `id` de un alumno es su código |
| `GET sessions/` | token | listar sesiones |
| `DELETE sessions/<id>/` | token | borrar una sesión |
| `POST sessions/import/` | token | botón "Cargar sesiones": `{files: [{name, text}]}` → `{added, duplicated, invalid}` |
| `POST sessions/ingest/` | **llave Unity** | el JSON de la sesión tal cual → **201** nueva / **409** ya existía / **400** inválida o fuera del catálogo |

Solo se aceptan sesiones de experimentos y mediciones que estén en el catálogo de la base
(tablas `experimento` y `tarea`). Si no, la respuesta es 400 y el visor conserva la sesión
para reintentarla cuando se agregue al catálogo.

El JSON que devuelve la API tiene exactamente la forma de `src/types.ts` del frontend
(`codigoParticipante`, `creadoEn`, `receivedAt`, …).

## Entornos: `.env.dev` y `.env.prod`

Las credenciales (base de datos, llaves, cuenta del profesor) van en un archivo por
entorno. **Ninguno se sube a git.**

| Archivo | Cuándo se usa | Plantilla |
|---|---|---|
| `.env.dev` | siempre, salvo que digas otra cosa | `.env.dev.example` |
| `.env.prod` | con `ENTORNO=prod` | `.env.prod.example` |

```powershell
.venv\Scripts\python manage.py runserver                          # usa .env.dev
$env:ENTORNO = 'prod'; .venv\Scripts\python manage.py runserver   # usa .env.prod
Remove-Item Env:ENTORNO                                           # vuelve a dev
```

La base de datos de cada entorno debe tener los scripts de `levi-db-scripts` aplicados,
en orden: `Version_2.0.0/levidb.sql`, `Version_2.1.0/insert_datosbase.sql`,
`Version_2.2.0/alter_nombre_asign.sql` y `Version_2.3.0/alter_datos_visor.sql`.

## Usar en tu PC (sin Docker)

En PowerShell, dentro de la carpeta `proyecto-backend`:

```powershell
py -m venv .venv                                   # 1. crea el entorno de Python (una vez)
.venv\Scripts\python -m pip install -r requirements.txt   # 2. instala las librerías
copy .env.dev.example .env.dev                     # 3. crea tu .env.dev y complétalo
.venv\Scripts\python manage.py migrate             # 4. crea las tablas de Django (usuarios, tokens)
.venv\Scripts\python manage.py ensure_teacher      # 5. crea la cuenta del profesor (desde .env.dev)
.venv\Scripts\python manage.py runserver           # 6. arranca en http://localhost:8000
```

> Se usa `.venv\Scripts\python` directamente para no tener que "activar" el entorno
> (en algunos PC PowerShell bloquea el script de activación).

Otros comandos útiles:

```powershell
.venv\Scripts\python manage.py test lab                 # tests automáticos (ver abajo)
.venv\Scripts\python scripts\probar_api.py              # prueba el backend encendido
.venv\Scripts\python manage.py changepassword profesor  # cambiar la contraseña del profesor
.venv\Scripts\python manage.py createsuperuser          # otra forma de crear la cuenta
```

### Tests

`manage.py test lab` crea una base de prueba aparte (`test_<POSTGRES_DB>`), le aplica
los scripts de `levi-db-scripts` (lista en `lab/tests/runner.py`) y la borra al terminar.
Necesita:

- que el usuario de PostgreSQL pueda crear bases (permiso `CREATEDB`);
- la carpeta `levi-db-scripts` junto a este repositorio (o su ruta en `LEVI_DB_SCRIPTS`).

Panel de Django: http://localhost:8000/admin/ (con la cuenta del profesor).

## Con Docker (el sistema completo)

> ⚠️ **Pendiente de adaptar a `levi-db-scripts`.** El PostgreSQL de Docker todavía no
> recibe esos scripts, así que con esta versión del backend la API no encuentra sus
> tablas. No uses `actualizar.sh` en el servidor hasta adaptarlo.

Lo mismo que correrá en el servidor: PostgreSQL + backend + Nginx con la página web.
Necesita Docker Desktop encendido y los 3 repositorios uno al lado del otro.

```powershell
cd deploy
copy .env.example .env          # 1. completa los valores (ver los comentarios del archivo)
docker compose up -d --build    # 2. construye y enciende los 3 contenedores
docker compose ps               # 3. los 3 deben aparecer "Up" (db además "healthy")
```

Luego abre http://localhost/ (o `http://localhost:PUERTO/` si cambiaste `HTTP_PORT`).

| Comando (desde `deploy/`) | Qué hace |
|---|---|
| `docker compose logs -f backend` | ver los mensajes del backend (Ctrl+C para salir) |
| `docker compose down` | apagar todo (**los datos se conservan**) |
| `docker compose exec backend python manage.py changepassword profesor` | cambiar la clave del profesor |
| `docker compose exec backend python manage.py test lab` | tests dentro de Docker (con PostgreSQL) |

> ⚠️ `docker compose down -v` (con `-v`) **borra la base de datos**. No lo uses en el servidor.

## En el servidor

- **[DEPLOY.md](DEPLOY.md)**: instalación paso a paso (SSH, clonar, `.env`, encender,
  cuenta del profesor, logs, actualizar, respaldos, https).
- **[UNITY.md](UNITY.md)**: cómo configurar el asset `EnvioSesiones` de Unity para que
  los visores envíen las sesiones.

## Archivos principales

| Archivo | Para qué sirve |
|---|---|
| `config/settings.py` | configuración; elige `.env.dev` o `.env.prod` y lee todo lo secreto de ahí |
| `config/urls.py` | rutas principales: `/api/` y `/admin/` |
| `lab/urls.py` | rutas de la API: qué controlador atiende cada dirección |
| `lab/controladores/` | **capa controlador**: `alumnos.py`, `sesiones.py`, `estado.py` (health, login) y `errores.py` (400/404) |
| `lab/dto/` | **capa DTO**: `alumno.py`, `sesion.py` (valida el JSON del visor y lo vuelve a armar igual) y `fechas.py` |
| `lab/servicios/` | **capa servicio**: `alumno_servicio.py` y `sesion_servicio.py` (reglas y transacciones) |
| `lab/dao/` | **capa DAO**: consultas SQL de `participante`, `sesion` (+ detalle) y catálogo |
| `lab/errores.py` | errores del negocio: `DatosInvalidos` (400) y `NoEncontrado` (404) |
| `lab/models.py` | modelos solo para el panel `/admin/` (`managed = False`: Django no toca esas tablas) |
| `lab/admin.py` | panel `/admin/`: alumnos y sesiones, usando los mismos servicios |
| `lab/auth.py` | reglas de acceso: solo el profesor recibe tokens y la llave de Unity |
| `lab/renderers.py` | respuestas JSON con `charset=utf-8` (para que las tildes se vean bien en cualquier cliente) |
| `lab/management/commands/ensure_teacher.py` | crea la cuenta del profesor desde `.env.dev` / `.env.prod` |
| `lab/tests/` | tests: login, acceso sin token, llave de Unity, duplicados (409), catálogo, admin… |
| `lab/tests/runner.py` | crea las tablas de `levi-db-scripts` en la base de prueba |
| `lab/tests/datos/` | un JSON real enviado por un visor (A015), usado en los tests |
| `scripts/probar_api.py` | prueba un backend encendido (tu PC o el servidor) |
| `ejemplos/sesion-ejemplo.json` | una sesión con el formato de Unity, para probar "Cargar sesiones" |
| `.env.dev.example` / `.env.prod.example` | plantillas de variables de cada entorno |
| `Dockerfile` | imagen del backend: Python 3.13 + gunicorn en el puerto 8000 |
| `entrypoint.sh` | al arrancar el contenedor: espera la BD, migra, crea al profesor y arranca |
| `.dockerignore` | lo que nunca entra a la imagen (`.env`, `deploy/`, venv, respaldos) |
| `lab/management/commands/wait_for_db.py` | espera a que PostgreSQL acepte conexiones |
| `deploy/docker-compose.yml` | los 3 contenedores juntos: `db`, `backend` y `frontend` (Nginx, puerto 80) |
| `deploy/.env.example` | plantilla de variables para Docker (servidor) |
| `deploy/iniciar.sh` | revisa que todo esté en su lugar y enciende el sistema |
| `deploy/actualizar.sh` | `git pull` de los 3 repos + respaldo de la BD + reconstruir |
| `DEPLOY.md` | guía de instalación en el servidor |
| `UNITY.md` | guía para configurar el envío desde Unity |
