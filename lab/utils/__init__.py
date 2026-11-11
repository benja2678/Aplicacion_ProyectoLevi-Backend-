"""
Utilidades que usan varias capas de la aplicación:

- auth.py       reglas de acceso: solo el profesor recibe tokens y la llave de Unity
                (X-Api-Key) solo sirve para enviar sesiones.
- errores.py    errores del negocio: DatosInvalidos (400) y NoEncontrado (404).
- renderers.py  respuestas JSON con charset=utf-8 (para que las tildes se vean bien).
"""
