# Laboratorio VR · Backend (Django)

API del panel docente del simulador de electrónica en realidad virtual (Unity, Meta Quest 3S).
Recibe las sesiones que envían los visores y se las muestra **solo al profesor**.

Es uno de 3 repositorios que van uno al lado del otro:

```
carpeta/
├── Aplicacion_tesis/     frontend (React) + Nginx
├── proyecto-backend/     este repositorio (Django + Docker Compose en deploy/)
└── proyecto-db/          base de datos (PostgreSQL)
```

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
| `PUT, DELETE students/<id>/` | token | editar / borrar un alumno |
| `GET sessions/` | token | listar sesiones |
| `DELETE sessions/<id>/` | token | borrar una sesión |
| `POST sessions/import/` | token | botón "Cargar sesiones": `{files: [{name, text}]}` → `{added, duplicated, invalid}` |
| `POST sessions/ingest/` | **llave Unity** | el JSON de la sesión tal cual → **201** nueva / **409** ya existía |

El JSON que devuelve la API tiene exactamente la forma de `src/types.ts` del frontend
(`codigoParticipante`, `creadoEn`, `receivedAt`, …).

## Usar en tu PC (sin Docker)

En PowerShell, dentro de la carpeta `proyecto-backend`:

```powershell
py -m venv .venv                                   # 1. crea el entorno de Python (una vez)
.venv\Scripts\python -m pip install -r requirements.txt   # 2. instala las librerías
copy .env.example .env                             # 3. crea tu .env y complétalo
.venv\Scripts\python manage.py migrate             # 4. crea las tablas (SQLite: db.sqlite3)
.venv\Scripts\python manage.py ensure_teacher      # 5. crea la cuenta del profesor (desde .env)
.venv\Scripts\python manage.py runserver           # 6. arranca en http://localhost:8000
```

> Se usa `.venv\Scripts\python` directamente para no tener que "activar" el entorno
> (en algunos PC PowerShell bloquea el script de activación).

Otros comandos útiles:

```powershell
.venv\Scripts\python manage.py test lab                 # tests automáticos
.venv\Scripts\python scripts\probar_api.py              # prueba el backend encendido
.venv\Scripts\python manage.py changepassword profesor  # cambiar la contraseña del profesor
.venv\Scripts\python manage.py createsuperuser          # otra forma de crear la cuenta
```

Panel de Django: http://localhost:8000/admin/ (con la cuenta del profesor).

## Archivos principales

| Archivo | Para qué sirve |
|---|---|
| `config/settings.py` | configuración; todo lo secreto se lee de variables de entorno |
| `config/urls.py` | rutas principales: `/api/` y `/admin/` |
| `lab/models.py` | las tablas `students` y `sessions` |
| `lab/serializers.py` | convierte las tablas al JSON del frontend (camelCase) |
| `lab/views.py` | los endpoints de la API |
| `lab/auth.py` | reglas de acceso: solo el profesor recibe tokens y la llave de Unity |
| `lab/session_logs.py` | lee, valida y guarda los JSON de sesión (sin duplicados) |
| `lab/management/commands/ensure_teacher.py` | crea la cuenta del profesor desde `.env` |
| `lab/tests/` | tests: login, acceso sin token, llave de Unity, duplicados (409)… |
| `scripts/probar_api.py` | prueba un backend encendido (tu PC o el servidor) |
| `ejemplos/sesion-ejemplo.json` | una sesión con el formato de Unity, para probar "Cargar sesiones" |
| `.env.example` | plantilla de variables para tu PC |
