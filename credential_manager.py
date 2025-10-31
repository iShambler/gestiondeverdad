# credential_manager.py
"""
Gestor de credenciales con capacidad de actualización
"""
from sqlalchemy.orm import Session
from db import Usuario, obtener_usuario_por_origen, cifrar


class CredentialManager:
    """Maneja la actualización y corrección de credenciales"""
    
    def __init__(self):
        # Diccionario: user_id -> {"esperando_confirmacion": bool, "nuevo_username": str, "esperando": "username"|"password"}
        self.usuarios_cambiando_credenciales = {}
    
    def iniciar_cambio_credenciales(self, user_id: str):
        """Inicia el proceso de cambio de credenciales"""
        self.usuarios_cambiando_credenciales[user_id] = {
            "esperando": "ambas"  # Ahora siempre pedimos ambas a la vez
        }
    
    def esta_cambiando_credenciales(self, user_id: str) -> bool:
        """Verifica si un usuario está en proceso de cambiar credenciales"""
        return user_id in self.usuarios_cambiando_credenciales
    
    def procesar_nueva_credencial(self, db: Session, user_id: str, texto: str, canal: str = "webapp"):
        """
        Procesa el username y password nuevos que el usuario está proporcionando.
        Ahora siempre espera AMBAS credenciales juntas.
        
        Returns:
            (completado, mensaje)
        """
        estado = self.usuarios_cambiando_credenciales.get(user_id)
        
        if not estado:
            return True, None
        
        # Obtener usuario
        if canal == "slack":
            usuario = obtener_usuario_por_origen(db, slack_id=user_id)
        elif canal == "whatsapp":
            usuario = obtener_usuario_por_origen(db, wa_id=user_id)
        else:
            usuario = obtener_usuario_por_origen(db, app_id=user_id)
        
        if not usuario:
            self.finalizar_cambio(user_id)
            return True, "⚠️ Error al cambiar credenciales. Intenta de nuevo."
        
        # Usar la misma función de extracción que auth_handler
        from auth_handler import extraer_credenciales_con_gpt
        
        credenciales = extraer_credenciales_con_gpt(texto)
        
        username = credenciales.get("username")
        password = credenciales.get("password")
        
        # Validar que tengamos AMBAS credenciales
        if not credenciales["ambos"]:
            mensaje_incompleto = (
                "⚠️ Necesito AMBAS credenciales para continuar.\n\n"
                "📝 **Envíamelas así:**\n"
                "```\n"
                "Usuario: tu_usuario\n"
                "Contraseña: tu_contraseña\n"
                "```"
            )
            return False, mensaje_incompleto
        
        # Validar longitud mínima
        if not username or len(username) < 3:
            return False, "❌ El nombre de usuario debe tener al menos 3 caracteres. Inténtalo de nuevo."
        
        if not password or len(password) < 4:
            return False, "❌ La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo."
        
        # Guardar nuevas credenciales
        usuario.username_intranet = username
        usuario.password_intranet = cifrar(password)
        db.commit()
        
        # Finalizar proceso
        self.finalizar_cambio(user_id)
        
        return True, f"🎉 ¡Credenciales actualizadas correctamente!\n\n✅ Usuario: **{username}**\n✅ Contraseña: ******\n\nYa puedes volver a usar el servicio normalmente."
    
    def finalizar_cambio(self, user_id: str):
        """Finaliza el proceso de cambio de credenciales"""
        if user_id in self.usuarios_cambiando_credenciales:
            del self.usuarios_cambiando_credenciales[user_id]


# Instancia global
credential_manager = CredentialManager()
