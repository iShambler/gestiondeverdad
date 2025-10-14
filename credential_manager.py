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
            "esperando_confirmacion": False,
            "esperando": "username",
            "nuevo_username": None
        }
    
    def esta_cambiando_credenciales(self, user_id: str) -> bool:
        """Verifica si un usuario está en proceso de cambiar credenciales"""
        return user_id in self.usuarios_cambiando_credenciales
    
    def procesar_nueva_credencial(self, db: Session, user_id: str, texto: str, canal: str = "webapp"):
        """
        Procesa el username o password nuevo que el usuario está proporcionando.
        
        Returns:
            (completado, mensaje)
        """
        estado = self.usuarios_cambiando_credenciales.get(user_id)
        
        if not estado:
            return True, None
        
        # Obtener usuario
        if canal == "slack":
            usuario = obtener_usuario_por_origen(db, slack_id=user_id)
        else:
            usuario = obtener_usuario_por_origen(db, app_id=user_id)
        
        if not usuario:
            self.finalizar_cambio(user_id)
            return True, "⚠️ Error al cambiar credenciales. Intenta de nuevo."
        
        # Procesar según lo que estemos esperando
        if estado["esperando"] == "username":
            username = texto.strip()
            
            if len(username) < 3:
                return False, "❌ El nombre de usuario debe tener al menos 3 caracteres. Inténtalo de nuevo:"
            
            # Guardar temporalmente
            estado["nuevo_username"] = username
            estado["esperando"] = "password"
            
            return False, f"✅ Perfecto, nuevo usuario: **{username}**\n\n🔑 Ahora envíame tu **nueva contraseña** de GestiónITT."
        
        elif estado["esperando"] == "password":
            password = texto.strip()
            
            if len(password) < 4:
                return False, "❌ La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo:"
            
            # Guardar nuevas credenciales
            username = estado["nuevo_username"]
            usuario.username_intranet = username
            usuario.password_intranet = cifrar(password)
            db.commit()
            
            # Finalizar proceso
            self.finalizar_cambio(user_id)
            
            return True, f"🎉 ¡Credenciales actualizadas correctamente!\n\n✅ Usuario: **{username}**\n✅ Contraseña: ******\n\nYa puedes volver a usar el servicio normalmente."
        
        return True, None
    
    def finalizar_cambio(self, user_id: str):
        """Finaliza el proceso de cambio de credenciales"""
        if user_id in self.usuarios_cambiando_credenciales:
            del self.usuarios_cambiando_credenciales[user_id]


# Instancia global
credential_manager = CredentialManager()
