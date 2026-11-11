# Laboratorio VR · Backend (Django)

API del panel docente del simulador de electrónica en realidad virtual (Unity, Meta Quest 3S).
Recibe las sesiones que envían los visores y se las muestra **solo al docente y al equipo** (tabla `lector`).

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
no Django**. El backend **no crea ninguna tabla** (no se usa `migrate`): solo se conecta.
También son de los scripts las de la sesión web: `lector` (quién entra), `token_revocado`
(sesiones cerradas) e `intento_login` (límite de intentos).

## Cómo se protege el acceso

| Quién | Cómo entra | Qué puede hacer |
|---|---|---|
| Lector: docente o equipo (web) | correo + contraseña de la tabla **`lector`** → **token JWT** (dura 30 min y se renueva hasta 8 h) | todo |
| Unity (Meta Quest) | llave fija en el encabezado `X-Api-Key` | **solo** enviar sesiones |
| Cualquier otro | — | nada (401/403) |

- **El acceso se controla en la base del servidor**, tabla `lector` (levi-db-scripts v2.4):
  entra quien esté ahí, con rol `docente` o `equipo` y con clave. La clave se guarda cifrada.
- Para dar acceso o cambiar una clave: `python manage.py clave_lector correo@dominio`
  (pregunta la contraseña; con `--nombre "…" --rol equipo` agrega a alguien que no estaba).
- Para quitar el acceso: borrar su fila de `lector` o dejar su `clave` en NULL. Se revisa
  en cada petición, así que el efecto es **inmediato**.
- No existe registro público. El login permite 5 intentos por minuto por IP (luego 429).
- Al cerrar sesión, el token de renovación queda invalidado.

## Endpoints (todos bajo `/api/`)

| Método y ruta | Acceso | Para qué |
|---|---|---|
| `GET health/` | público | saber si el backend está vivo |
| `POST auth/login/` | público (con límite) | `{username o email, password}` (el correo del lector) → `{access, refresh}` |
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

Las credenciales (base de datos y llaves) van en un archivo por
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
`Version_2.2.0/alter_nombre_asign.sql`, `Version_2.3.0/alter_datos_visor.sql` y
`Version_2.4.0/alter_lector_clave.sql` y `Version_2.5.0/alter_sesion_web.sql`.

## Usar en tu PC (sin Docker)

En PowerShell, dentro de la carpeta `proyecto-backend`:

```powershell
py -m venv .venv                                   # 1. crea el entorno de Python (una vez)
.venv\Scripts\python -m pip install -r requirements.txt   # 2. instala las librerías
copy .env.dev.example .env.dev                     # 3. crea tu .env.dev y complétalo
.venv\Scripts\python manage.py clave_lector TU@CORREO  # 4. clave para entrar a la página (el correo debe estar en la tabla lector)
.venv\Scripts\python manage.py runserver           # 5. arranca en http://localhost:8000
```

> Se usa `.venv\Scripts\python` directamente para no tener que "activar" el entorno
> (en algunos PC PowerShell bloquea el script de activación).

Otros comandos útiles:

```powershell
.venv\Scripts\python manage.py test lab                 # tests unitarios (ver abajo)
.venv\Scripts\python manage.py clave_lector TU@CORREO     # cambiar la contraseña de un lector
```

## Tests unitarios

```powershell
.venv\Scripts\python manage.py test lab                    # todos (necesita Docker Desktop abierto)
.venv\Scripts\python manage.py test lab.tests.dto          # solo una capa (dto, servicios, controladores, dao)
.venv\Scripts\python manage.py test lab.tests.servicios.test_alumno_servicio   # solo un archivo
```

Cada capa de `lab/` tiene sus tests en `lab/tests/`:

| Carpeta | Qué prueba | Base de datos |
|---|---|---|
| `dto/` | validación del JSON y forma de las respuestas | no |
| `servicios/` | reglas del negocio (el DAO se simula con *mocks*) | no |
| `controladores/` | rutas, permisos, códigos HTTP y forma del JSON (el servicio se simula) | no |
| `dao/` | las consultas SQL, contra un PostgreSQL de verdad | **sí** |
| `utils/` | `auth.py`, `errores.py` y `renderers.py` | no |
| `test_comandos.py` | los comandos `wait_for_db` y `clave_lector` | no |

**La base de prueba** (la arma `lab/tests/runner.py`):

1. Si algún test la necesita, se levanta un **PostgreSQL 16 nuevo en Docker** (puerto al azar,
   solo en tu PC). Los tests que no usan base corren sin Docker.
2. Se carga **`lab/tests/datos/base_pruebas.sql`**: el esquema actual de `levi-db-scripts`
   (v2.0 a v2.5) con datos de prueba conocidos. Su encabezado explica qué datos trae.
3. Al terminar, **el contenedor se borra** con todo lo que tenía, aunque algún test falle.

Los tests usan `config/settings_test.py`: nunca leen `.env.dev`/`.env.prod` ni se
conectan a las bases de desarrollo o producción.

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
| `docker compose exec backend python manage.py clave_lector CORREO` | dar o cambiar la clave de un lector |

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
| `config/urls.py` | ruta principal: todo bajo `/api/` |
| `lab/urls.py` | rutas de la API: qué controlador atiende cada dirección |
| `lab/controladores/` | **capa controlador**: `alumnos.py`, `sesiones.py`, `estado.py` (health, login, refresh, logout) y `errores.py` (400/401/404) |
| `lab/dto/` | **capa DTO**: `alumno.py`, `sesion.py` (valida el JSON del visor y lo vuelve a armar igual), `lector.py` (login) y `fechas.py` |
| `lab/servicios/` | **capa servicio**: `alumno_servicio.py`, `sesion_servicio.py` y `acceso_servicio.py` (login con la tabla lector) |
| `lab/dao/` | **capa DAO**: consultas SQL de `participante`, `sesion` (+ detalle), `lector` y catálogo |
| `lab/utils/errores.py` | errores del negocio: `DatosInvalidos` (400), `NoAutorizado` (401) y `NoEncontrado` (404) |
| `lab/utils/auth.py` | reglas de acceso: token de un lector (docente o equipo) y la llave de Unity |
| `lab/management/commands/clave_lector.py` | da o cambia la contraseña de un lector |
| `lab/utils/renderers.py` | respuestas JSON con `charset=utf-8` (para que las tildes se vean bien en cualquier cliente) |
| `config/settings_test.py` | configuración de los tests (no lee `.env.dev`/`.env.prod`) |
| `lab/tests/` | tests unitarios, una carpeta por capa (ver "Tests unitarios") |
| `lab/tests/runner.py` | levanta el PostgreSQL de prueba en Docker y lo borra al terminar |
| `lab/tests/datos/base_pruebas.sql` | la base de prueba: esquema actual + datos de prueba conocidos |
| `lab/tests/datos/A015_…json` | un JSON real enviado por un visor, usado en los tests |
| `.env.dev.example` / `.env.prod.example` | plantillas de variables de cada entorno |
| `Dockerfile` | imagen del backend: Python 3.13 + gunicorn en el puerto 8000 |
| `entrypoint.sh` | al arrancar el contenedor: espera la BD, migra y arranca |
| `.dockerignore` | lo que nunca entra a la imagen (`.env`, `deploy/`, venv, respaldos) |
| `lab/management/commands/wait_for_db.py` | espera a que PostgreSQL acepte conexiones |
| `deploy/docker-compose.yml` | los 3 contenedores juntos: `db`, `backend` y `frontend` (Nginx, puerto 80) |
| `deploy/.env.example` | plantilla de variables para Docker (servidor) |
| `deploy/iniciar.sh` | revisa que todo esté en su lugar y enciende el sistema |
| `deploy/actualizar.sh` | `git pull` de los 3 repos + respaldo de la BD + reconstruir |
| `DEPLOY.md` | guía de instalación en el servidor |
| `UNITY.md` | guía para configurar el envío desde Unity |
