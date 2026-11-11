"""
Prueba rápida de un backend que YA está corriendo (en tu PC o en el servidor).

Revisa: que responde, que sin token no se puede entrar, el login del profesor,
que Unity puede enviar una sesión (201) y que al reenviarla responde 409, que la
llave de Unity no sirve para leer datos, y el cierre de sesión.
Al final borra la sesión de prueba que creó.

Uso (desde la carpeta proyecto-backend):
    .venv\\Scripts\\python scripts\\probar_api.py
    .venv\\Scripts\\python scripts\\probar_api.py --url http://IP-DEL-SERVIDOR

Lee TEACHER_USERNAME, TEACHER_PASSWORD y UNITY_API_KEY del archivo .env.dev
(o del que indiques con --env, por ejemplo deploy/.env).
Solo usa la librería estándar de Python.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def read_env(path: Path) -> dict:
    env = {}
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    return env


def call(base, method, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode('utf-8') if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            text = r.read().decode('utf-8')
            return r.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'replace')
        try:
            return e.code, json.loads(text) if text else None
        except ValueError:
            return e.code, text[:200]


def main() -> int:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description='Prueba rápida de la API del laboratorio.')
    parser.add_argument('--url', default='http://127.0.0.1:8000', help='dirección del backend o del servidor')
    parser.add_argument('--env', default=str(here / '.env.dev'), help='archivo .env con las credenciales (por defecto .env.dev)')
    args = parser.parse_args()

    env = read_env(Path(args.env))
    user, password, key = env.get('TEACHER_USERNAME'), env.get('TEACHER_PASSWORD'), env.get('UNITY_API_KEY')
    if not (user and password and key):
        print(f'Faltan TEACHER_USERNAME, TEACHER_PASSWORD o UNITY_API_KEY en {args.env}')
        return 1

    api = args.url.rstrip('/') + '/api'
    ok = True

    def check(name, got, expected):
        nonlocal ok
        good = got == expected
        ok &= good
        print(f'  [{"OK" if good else "FALLA"}] {name}: {got} (esperado {expected})')

    print(f'Probando {api}')
    try:
        status, _ = call(api, 'GET', '/health/')
    except urllib.error.URLError as exc:
        print(f'  No se pudo conectar: {exc.reason}. ¿Está corriendo el backend?')
        return 1
    check('El backend responde', status, 200)

    status, _ = call(api, 'GET', '/students/')
    check('Sin token no se puede ver alumnos', status, 401)

    status, tokens = call(api, 'POST', '/auth/login/', {'username': user, 'password': password})
    check('Login del profesor', status, 200)
    if status != 200:
        print('  Respuesta:', tokens)
        return 1
    teacher = {'Authorization': f'Bearer {tokens["access"]}'}

    status, me = call(api, 'GET', '/auth/me/', headers=teacher)
    check(f'Token válido (usuario "{(me or {}).get("username")}")', status, 200)

    started = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    log = {
        'participantCode': 'PRUEBA', 'experimentId': 'T0', 'experimentTitle': 'Sesión de prueba',
        'appVersion': 'script', 'device': 'probar_api.py', 'startedAt': started, 'finishedAt': started,
        'completed': True, 'durationSeconds': 1, 'laboratorySeconds': 1, 'correctCount': 0, 'taskCount': 0,
        'events': [], 'tasks': [],
    }
    unity = {'X-Api-Key': key}
    status, body = call(api, 'POST', '/sessions/ingest/', log, headers=unity)
    check('Unity envía una sesión nueva', status, 201)
    session_id = (body or {}).get('id', '')
    status, _ = call(api, 'POST', '/sessions/ingest/', log, headers=unity)
    check('Unity reenvía la misma sesión', status, 409)
    status, _ = call(api, 'POST', '/sessions/ingest/', log, headers={'X-Api-Key': 'llave-falsa'})
    check('Llave incorrecta rechazada', status, 403)
    status, _ = call(api, 'GET', '/sessions/', headers=unity)
    check('La llave de Unity NO sirve para leer', status, 401)

    status, sessions = call(api, 'GET', '/sessions/', headers=teacher)
    check('El profesor ve la sesión enviada', any(s['id'] == session_id for s in sessions or []), True)

    from urllib.parse import quote
    status, _ = call(api, 'DELETE', f'/sessions/{quote(session_id, safe="")}/', headers=teacher)
    check('Borrar la sesión de prueba', status, 204)

    status, _ = call(api, 'POST', '/auth/logout/', {'refresh': tokens['refresh']})
    check('Cerrar sesión', status, 200)
    status, _ = call(api, 'POST', '/auth/refresh/', {'refresh': tokens['refresh']})
    check('Tras cerrar sesión el token ya no se puede renovar', status, 401)

    print('\nTodo bien ✔' if ok else '\nHay pruebas que fallaron ✘')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
