# Puesta en marcha en el servidor

Guía paso a paso para instalar el panel docente en el servidor del profesor.
No hace falta saber de servidores: cada comando se copia y se pega tal cual.
Lo que está en `MAYÚSCULAS` (por ejemplo `IP-DEL-SERVIDOR`) se reemplaza por el dato real.

Al terminar, el servidor tendrá 3 contenedores de Docker:

```
  Navegador del profesor ─┐
                          ├──►  :80  Nginx (frontend) ──► backend (Django) ──► db (PostgreSQL)
  Visores Meta Quest ─────┘          página web           /api/  /admin/        datos en un volumen
```

Solo el puerto 80 queda abierto. La base de datos no se puede alcanzar desde fuera.

---

## 0. Qué pedirle al profesor

- [ ] **Dirección del servidor**: IP (ej. `203.0.113.10`) o dominio (ej. `laboratorio.uta.cl`).
- [ ] **Usuario y contraseña SSH** (o una llave SSH) para entrar al servidor.
- [ ] Que ese usuario tenga permiso de administrador (`sudo`) o, al menos, de usar Docker.
- [ ] Que el **puerto 80** esté libre y abierto desde la red donde están los visores
      (si el 80 está ocupado, se puede usar otro, ver paso 4).
- [ ] Si el servidor tiene o tendrá **https** (certificado). Ver la sección 12.

Se asume un servidor Linux (Ubuntu o Debian). Con 2 GB de RAM y 10 GB de disco libres alcanza.

## 1. Entrar al servidor (SSH)

Desde tu PC, en PowerShell:

```powershell
ssh USUARIO@IP-DEL-SERVIDOR
```

- La primera vez pregunta si confías en el servidor: escribe `yes` y Enter.
- Al escribir la contraseña **no aparece nada en pantalla**; es normal. Escríbela y Enter.
- Para salir del servidor: `exit`.

Todos los comandos siguientes se escriben **dentro del servidor**.

## 2. Revisar Docker y git

```sh
docker --version
docker compose version
git --version
```

Si los 3 responden con un número de versión, salta al paso 3.

Si falta alguno (y el profesor está de acuerdo en instalarlo):

```sh
sudo apt update && sudo apt install -y git
curl -fsSL https://get.docker.com | sudo sh        # instalador oficial de Docker
sudo usermod -aG docker $USER                      # permite usar docker sin sudo
exit                                               # sal y vuelve a entrar con ssh
```

Después de volver a entrar, `docker ps` debe responder sin error.

## 3. Descargar los 3 repositorios

Van en una misma carpeta y **con estos nombres exactos** (los scripts los buscan así):

```sh
mkdir -p ~/laboratorio && cd ~/laboratorio
git clone https://github.com/benja2678/Aplicacion_ProyectoLevi-Backend-.git  proyecto-backend
git clone https://github.com/benja2678/Aplicacion_ProyectoLevi-Db-.git       proyecto-db
git clone https://github.com/benja2678/Aplicacion_ProyectoLevi-Frontend-.git Aplicacion_tesis
ls
```

`ls` debe mostrar: `Aplicacion_tesis  proyecto-backend  proyecto-db`.

## 4. Crear el archivo de configuración (`.env`)

Aquí van las contraseñas y llaves. Este archivo **nunca** se sube a GitHub.

```sh
cd ~/laboratorio/proyecto-backend/deploy
cp .env.example .env

# Llena automáticamente las llaves con valores aleatorios:
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=$(openssl rand -hex 32)/" .env
sed -i "s/^UNITY_API_KEY=.*/UNITY_API_KEY=$(openssl rand -hex 24)/" .env
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
chmod 600 .env                                     # solo tu usuario puede leerlo

nano .env                                          # abre el archivo para editarlo
```

En `nano` cambia estas 2 líneas (muévete con las flechas):

```
ALLOWED_HOSTS=localhost,127.0.0.1,IP-DEL-SERVIDOR
TEACHER_PASSWORD=LA-CLAVE-DEL-PROFESOR
```

- `ALLOWED_HOSTS`: agrega la IP o el dominio del servidor (separados por comas, sin espacios).
  Si falta, el navegador mostrará **Bad Request (400)**.
- `TEACHER_PASSWORD`: la clave con la que el profesor entrará al panel. Mínimo 10
  caracteres; que no sea solo números ni una clave común. Evita los símbolos `$` y `#`.
- Si el puerto 80 está ocupado, cambia también `HTTP_PORT=8080` (u otro número).

Para guardar: **Ctrl+O** y Enter. Para salir: **Ctrl+X**.

> `POSTGRES_PASSWORD` solo se usa la **primera vez** que se crea la base de datos.
> No la cambies después: el backend ya no podría conectarse.

## 5. Encender

```sh
sh ~/laboratorio/proyecto-backend/deploy/iniciar.sh
```

La primera vez tarda varios minutos (descarga y construye todo). El script revisa antes
que no falte nada y, si algo está mal, dice qué arreglar.

Al final muestra el estado de los contenedores. Los 3 deben decir `Up`, y `db` además
`(healthy)`. Los contenedores se reinician solos si el servidor se reinicia.

## 6. Comprobar que funciona

1. En el navegador de tu PC abre `http://IP-DEL-SERVIDOR/` (o `http://IP-DEL-SERVIDOR:8080/`
   si cambiaste el puerto). Debe aparecer la pantalla de login.
2. Entra con `profesor` y la clave que pusiste en `TEACHER_PASSWORD`.
3. En el servidor, `curl http://localhost/api/health/` debe responder `{"status":"ok"}`.
   (Si usas otro puerto: `curl http://localhost:8080/api/health/`.)

## 7. La cuenta del profesor

Se crea **sola** en el primer arranque con `TEACHER_USERNAME` y `TEACHER_PASSWORD`.
Para confirmarlo:

```sh
cd ~/laboratorio/proyecto-backend/deploy
docker compose logs backend | grep -i "profesor"
```

| Mensaje | Qué significa |
|---|---|
| `Cuenta del profesor "profesor" creada.` | listo |
| `La cuenta "profesor" ya existe` | ya estaba creada; no se cambió su clave |
| `AVISO: no se creó la cuenta del profesor` | la clave era muy débil. Cámbiala en `.env` y ejecuta `docker compose up -d` |

Otros comandos útiles (desde `~/laboratorio/proyecto-backend/deploy`):

```sh
docker compose exec backend python manage.py changepassword profesor   # cambiar la clave
docker compose exec backend python manage.py createsuperuser           # crear otra cuenta
```

Una vez creada la cuenta, puedes borrar el valor de `TEACHER_PASSWORD` en `.env`
(deja la línea como `TEACHER_PASSWORD=`): la cuenta sigue existiendo en la base de datos.

## 8. Ver lo que pasa (logs)

Siempre desde `~/laboratorio/proyecto-backend/deploy`:

```sh
docker compose ps                      # estado de los 3 contenedores
docker compose logs -f backend         # mensajes del backend en vivo (Ctrl+C para salir)
docker compose logs --tail 50 frontend # últimas 50 visitas (Nginx)
docker compose logs --tail 50 db       # mensajes de PostgreSQL
```

Cuando un visor envía una sesión, en el backend aparece una línea como:

```
"POST /api/sessions/ingest/ HTTP/1.0" 201     (201 = nueva, 409 = ya existía)
```

## 9. Actualizar a una versión nueva

Cuando subas cambios a GitHub desde tu PC, en el servidor ejecuta:

```sh
sh ~/laboratorio/proyecto-backend/deploy/actualizar.sh
```

Descarga los cambios de los 3 repositorios, hace un respaldo de la base de datos y
reconstruye solo lo que cambió. **Los datos no se pierden.**

## 10. Respaldos de la base de datos

```sh
sh ~/laboratorio/proyecto-db/scripts/respaldar.sh       # crea proyecto-db/backups/laboratorio_FECHA.sql.gz
sh ~/laboratorio/proyecto-db/scripts/restaurar.sh ~/laboratorio/proyecto-db/backups/ARCHIVO.sql.gz
```

**Respaldo automático todos los días a las 3:00** (recomendado):

```sh
crontab -e          # si pregunta qué editor usar, elige nano (1)
```

Agrega al final estas 2 líneas (la segunda borra respaldos de más de 30 días) y guarda:

```
0 3 * * * sh $HOME/laboratorio/proyecto-db/scripts/respaldar.sh >> $HOME/laboratorio/respaldos.log 2>&1
30 3 * * * find $HOME/laboratorio/proyecto-db/backups -name '*.sql.gz' -mtime +30 -delete
```

Para copiar los respaldos a tu PC (en PowerShell de tu PC, no en el servidor):

```powershell
scp "USUARIO@IP-DEL-SERVIDOR:laboratorio/proyecto-db/backups/*.sql.gz" .
```

Los respaldos tienen datos de alumnos: guárdalos en un lugar seguro.

## 11. Conectar los visores

Ver [UNITY.md](UNITY.md): qué dirección y qué llave poner en el asset `EnvioSesiones`.

La llave es el valor de `UNITY_API_KEY`:

```sh
grep UNITY_API_KEY ~/laboratorio/proyecto-backend/deploy/.env
```

## 12. HTTPS (opcional)

Sin https, la clave del profesor y la llave de Unity viajan **sin cifrar** por la red.
Funciona, pero lo ideal es tener https. Lo más común es que la institución ya tenga un
proxy con certificado delante de sus servidores. En ese caso:

1. Pide que el dominio (ej. `https://laboratorio.uta.cl`) apunte a `http://IP-DEL-SERVIDOR:80`.
2. En `.env` agrega o cambia:

   ```
   ALLOWED_HOSTS=localhost,127.0.0.1,laboratorio.uta.cl
   CSRF_TRUSTED_ORIGINS=https://laboratorio.uta.cl
   HTTPS=true
   NUM_PROXIES=2
   ```

3. Ejecuta `docker compose up -d` (desde `deploy/`).
4. En Unity usa `https://laboratorio.uta.cl/api/sessions/ingest/`.

Si no hay proxy y hay que instalar el certificado en este mismo servidor, se debe
agregar a la configuración de Nginx (no está incluido todavía).

## Problemas frecuentes

| Qué pasa | Qué hacer |
|---|---|
| El navegador muestra **Bad Request (400)** | Falta la IP o el dominio en `ALLOWED_HOSTS`. Corrige `.env` y `docker compose up -d` |
| La página no carga (se queda esperando) | `docker compose ps` para ver si están encendidos. Si lo están, el puerto 80 está bloqueado por un firewall: pídele al profesor que lo abra. Si el servidor usa `ufw`: `sudo ufw allow 80/tcp` |
| **502 Bad Gateway** | El backend está arrancando o falló. Espera 30 s; si sigue, `docker compose logs --tail 50 backend` |
| El backend se reinicia una y otra vez | Mira `docker compose logs --tail 50 backend`. Lo más común: se cambió `POSTGRES_PASSWORD` después de crear la base |
| `permission denied ... docker.sock` | Tu usuario no puede usar Docker: `sudo usermod -aG docker $USER`, sal y vuelve a entrar |
| "Demasiados intentos" al iniciar sesión | Hubo 5 intentos fallidos en 1 minuto. Espera un minuto |
| Los visores no envían sesiones | Ver la sección "Si algo falla" de [UNITY.md](UNITY.md) |

## Resumen de comandos

| Para… | Comando |
|---|---|
| Encender (o aplicar cambios del `.env`) | `sh ~/laboratorio/proyecto-backend/deploy/iniciar.sh` |
| Actualizar desde GitHub | `sh ~/laboratorio/proyecto-backend/deploy/actualizar.sh` |
| Ver el estado | `cd ~/laboratorio/proyecto-backend/deploy && docker compose ps` |
| Ver mensajes del backend | `cd ~/laboratorio/proyecto-backend/deploy && docker compose logs -f backend` |
| Apagar (los datos se conservan) | `cd ~/laboratorio/proyecto-backend/deploy && docker compose down` |
| Respaldo | `sh ~/laboratorio/proyecto-db/scripts/respaldar.sh` |

> ⚠️ **Nunca** uses `docker compose down -v`: la `-v` borra la base de datos.
