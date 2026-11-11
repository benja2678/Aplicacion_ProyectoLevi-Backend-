# Configurar Unity para enviar las sesiones al servidor

Guía para quien compila el simulador ([SimuladorVR](https://github.com/FUKARLOS/SimuladorVR),
Unity 6.3) para los Meta Quest. **No hay que cambiar código**: solo el asset
`EnvioSesiones` y, si el servidor no tiene https, una opción de Player Settings.

## Cómo funciona el envío (ya está programado en Unity)

1. El visor guarda cada sesión como un archivo `.json` en su memoria (nunca se borra).
2. `SessionUploader` envía los que faltan: al abrir la app, al terminar cada sesión y
   cada 2 minutos. Usa un `POST` con el JSON tal cual y los encabezados del asset.
3. Si el servidor responde **201** (nueva) o **409** (ya existía), la anota como enviada
   en `enviadas.txt` y no la vuelve a mandar.
4. Si no hay red o el servidor la rechaza, la sesión **queda pendiente** y se reintenta
   después. No se pierde nada. El menú del visor muestra cuántas quedan: "N por enviar".

## 1. Datos que necesitas

| Dato | De dónde sale |
|---|---|
| Dirección del servidor | IP o dominio (ej. `203.0.113.10`) |
| Llave de Unity | en el servidor: `grep UNITY_API_KEY ~/laboratorio/proyecto-backend/deploy/.env` |

## 2. Probar desde tu PC antes de tocar Unity

En PowerShell (cambia la IP y pega la llave). Se envía una sesión real que grabó un
visor (código A015), guardada junto a los tests:

```powershell
cd C:\Users\Usuario\Desktop\Proyecto_levi\proyecto-backend
$key = 'PEGA-AQUI-LA-LLAVE'
Invoke-RestMethod -Method Post -Uri http://IP-DEL-SERVIDOR/api/sessions/ingest/ -Headers @{ 'X-Api-Key' = $key } -ContentType 'application/json' -InFile lab\tests\datos\A015_N1_20261110_230751.json
```

Debe responder `Sesión guardada.` (o un error **409 Conflict** si ya la habías enviado:
también está bien). Si esto funciona, el servidor está listo para los visores.
Después puedes borrar esa sesión de prueba desde la ficha del alumno A015 en la página (botón "Eliminar sesión").

## 3. Configurar el asset `EnvioSesiones`

En Unity, ventana *Project*: `Assets/_Project/Resources/EnvioSesiones`. Selecciónalo y
en el *Inspector* deja:

| Campo | Valor |
|---|---|
| **Enabled** | ✔ (marcado) |
| **Endpoint** | `http://IP-DEL-SERVIDOR/api/sessions/ingest/` |
| **Headers** | 1 elemento → **Name:** `X-Api-Key` · **Value:** la llave |
| **Body Template** | `{session}` (ya viene así; no cambiar) |
| Timeout Seconds | `15` (sube a `30` si la red es lenta) |
| Retry Minutes | `2` |

- El Endpoint debe terminar en **`/`** (`.../ingest/`). Sin la barra final el envío falla.
- Si el servidor usa otro puerto: `http://IP-DEL-SERVIDOR:8080/api/sessions/ingest/`.
- Con https: `https://DOMINIO/api/sessions/ingest/`.
- **No** agregues `Content-Type` en Headers: Unity ya lo pone.

## 4. ⚠️ Si el servidor NO tiene https: permitir HTTP

Hoy el proyecto **bloquea** las conexiones `http://` (`Allow downloads over HTTP` está en
*Not allowed*). Con un Endpoint `http://` el visor no podrá enviar nada: las sesiones
quedarán "por enviar" y en el log de Unity aparecerá `Insecure connection not allowed`.

Para permitirlo: **Edit → Project Settings → Player → pestaña Android → Other Settings →
Allow downloads over HTTP → Always allowed**.

Ten en cuenta que sin https la llave y los datos de las sesiones viajan **sin cifrar**:
alguien en la misma red podría leer la llave. Con ella solo se pueden *enviar* sesiones
(no ver ni borrar datos), pero lo ideal es tener https (ver DEPLOY.md, sección 12).
Con https no hace falta cambiar esta opción.

## 5. ⚠️ No subir la llave a GitHub

`EnvioSesiones.asset` es un archivo de texto dentro del repositorio: si se hace commit
con la llave puesta, cualquiera con acceso al repositorio la puede ver. **Más aún si el
repositorio es o llega a ser público.**

Forma simple de evitarlo: después de configurar el asset, dile a git que ignore los
cambios locales de ese archivo (en la carpeta del proyecto Unity):

```sh
git update-index --skip-worktree Assets/_Project/Resources/EnvioSesiones.asset
```

Así el archivo queda configurado en tu PC para compilar, pero git no lo mostrará como
modificado ni lo subirá. Para deshacerlo: `--no-skip-worktree` en vez de `--skip-worktree`.

Aun así, la llave queda dentro del APK instalado en los visores. Si sospechas que se
filtró, cámbiala (ver "Cambiar la llave", al final).

## 6. Compilar, instalar y comprobar

1. Compila e instala el APK en el visor como siempre.
2. Haz una sesión corta y termínala.
3. En el menú del visor, "N por enviar" debe bajar a 0 (o no aparecer).
4. En el panel web, la sesión aparece en la ficha del alumno con ese código.
5. En el servidor (desde `~/laboratorio/proyecto-backend/deploy`):
   `docker compose logs --tail 20 backend` debe mostrar `"POST /api/sessions/ingest/ HTTP/1.0" 201`.

El visor debe estar en una red desde la que se llegue al servidor (por ejemplo, el
Wi-Fi de la universidad si el servidor está en su red interna).

## Si algo falla

Lo que el servidor respondió aparece en el log de Unity como
`[Envío] el servidor rechazó ARCHIVO (CÓDIGO)` y en `docker compose logs backend`.

| Qué se ve | Causa | Solución |
|---|---|---|
| "por enviar" no baja y no llega nada al servidor | el visor no llega al servidor | revisa la red del visor, la IP del Endpoint y el puerto 80 abierto |
| `Insecure connection not allowed` | Endpoint `http://` bloqueado | paso 4 |
| **403** (`Forbidden` en el log del backend) | llave incorrecta o vacía | revisa *Name* `X-Api-Key` y *Value* contra `UNITY_API_KEY` |
| **400** con `Bad Request` en HTML | falta la IP en `ALLOWED_HOSTS` del servidor | agrégala en `deploy/.env` y `docker compose up -d` |
| **400** con un mensaje en JSON | el archivo de sesión está dañado | revisa ese `.json` en el visor |
| **405** o **301** | falta la `/` al final del Endpoint | paso 3 |
| **413** | sesión de más de 50 MB | poco probable; avisar |
| **502** | el backend del servidor está apagado o reiniciándose | `docker compose ps` en el servidor |

Las sesiones rechazadas **no se pierden**: siguen en el visor y se reintentan cada
2 minutos. Apenas se corrige el problema, llegan solas.

## Cambiar la llave

1. En el servidor, pon un valor nuevo en `UNITY_API_KEY` (`openssl rand -hex 24`) en
   `deploy/.env` y ejecuta `docker compose up -d` desde `deploy/`.
2. Pon la llave nueva en el asset `EnvioSesiones`, recompila e instala en todos los visores.

Mientras un visor tenga la llave vieja, sus sesiones quedan pendientes (403) y llegan
solas cuando se instala el APK con la llave nueva.
