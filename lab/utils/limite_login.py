"""
Límite de intentos de login por IP (LOGIN_RATE, por defecto 5 por minuto).

Los intentos se guardan en la tabla intento_login de la base (ver
servicios/acceso_servicio.py), así el conteo es el mismo para todos los procesos del
servidor. Al pasarse, la API responde 429 con el encabezado Retry-After (segundos).
"""

from rest_framework.throttling import BaseThrottle


class LimiteLogin(BaseThrottle):
    espera: int | None = None

    def allow_request(self, request, view) -> bool:
        from ..servicios import acceso_servicio  # aquí, para no crear un ciclo de imports

        # get_ident: la IP del cliente, considerando el proxy de delante (NUM_PROXIES).
        self.espera = acceso_servicio.registrar_intento_login(self.get_ident(request))
        return self.espera is None

    def wait(self) -> int | None:
        return self.espera
