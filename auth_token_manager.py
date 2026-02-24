"""
Gestión de tokens temporales para login via enlace web.
Genera URLs únicas que caducan en 15 minutos, vinculadas al wa_id del usuario.
"""

import secrets
import threading
from datetime import datetime, timedelta


class AuthTokenManager:
    """Gestiona tokens temporales para autenticación vía enlace web"""

    def __init__(self, expiry_minutes: int = 15):
        self.expiry_minutes = expiry_minutes
        # token -> {"wa_id": str, "created": datetime}
        self._tokens = {}
        self._lock = threading.Lock()

    def generar_token(self, wa_id: str) -> str:
        """
        Genera un token único vinculado a un wa_id.
        Si ya existe uno vigente para ese wa_id, lo invalida y crea uno nuevo.
        """
        with self._lock:
            # Invalidar tokens previos de este wa_id
            tokens_a_borrar = [
                t for t, data in self._tokens.items()
                if data["wa_id"] == wa_id
            ]
            for t in tokens_a_borrar:
                del self._tokens[t]

            # Generar nuevo token
            token = secrets.token_urlsafe(32)
            self._tokens[token] = {
                "wa_id": wa_id,
                "created": datetime.utcnow()
            }

            # Limpiar tokens expirados aprovechando
            self._limpiar_expirados()

            return token

    def validar_token(self, token: str) -> dict | None:
        """
        Valida un token y devuelve sus datos si es válido.

        Returns:
            {"wa_id": str, "seconds_left": int} o None si inválido/expirado
        """
        with self._lock:
            data = self._tokens.get(token)
            if not data:
                return None

            elapsed = (datetime.utcnow() - data["created"]).total_seconds()
            max_seconds = self.expiry_minutes * 60

            if elapsed > max_seconds:
                del self._tokens[token]
                return None

            return {
                "wa_id": data["wa_id"],
                "seconds_left": int(max_seconds - elapsed)
            }

    def consumir_token(self, token: str) -> str | None:
        """
        Valida y consume un token (uso único tras login exitoso).

        Returns:
            wa_id si válido, None si inválido
        """
        with self._lock:
            data = self._tokens.get(token)
            if not data:
                return None

            elapsed = (datetime.utcnow() - data["created"]).total_seconds()
            if elapsed > self.expiry_minutes * 60:
                del self._tokens[token]
                return None

            wa_id = data["wa_id"]
            del self._tokens[token]
            return wa_id

    def _limpiar_expirados(self):
        """Limpia tokens expirados (llamar dentro del lock)"""
        ahora = datetime.utcnow()
        limite = timedelta(minutes=self.expiry_minutes)
        expirados = [
            t for t, data in self._tokens.items()
            if (ahora - data["created"]) > limite
        ]
        for t in expirados:
            del self._tokens[t]


# Instancia global
auth_token_manager = AuthTokenManager(expiry_minutes=15)
