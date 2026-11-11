"""
Capa de controladores (la entrada HTTP de la API, todo bajo /api/).

Cada controlador: lee la petición -> arma el DTO de entrada -> llama al servicio ->
responde con el DTO de salida convertido a JSON. No tiene reglas de negocio ni SQL.

- estado.py     health, login, refresh/logout (simplejwt) y "quién soy".
- alumnos.py    /api/students/ y /api/students/<código>/
- sesiones.py   /api/sessions/, /api/sessions/<id>/, import/ e ingest/ (Unity)
- errores.py    convierte DatosInvalidos / NoEncontrado en respuestas 400 / 404.

Quién puede entrar (ver lab/auth.py):
- Sin token: health, login, refresh, logout.
- Solo con la llave de Unity (X-Api-Key): POST /api/sessions/ingest/.
- Todo lo demás: token JWT del profesor.
"""
