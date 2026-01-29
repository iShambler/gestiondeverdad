# credential_manager.py
"""
Gestor de credenciales con capacidad de actualización.
Verifica login antes de guardar (mismo flujo que primera vez).
"""
from sqlalchemy.orm import Session
from db import Usuario, obtener_usuario_por_origen, cifrar


class CredentialManager:
    """Maneja la actualización y corrección de credenciales"""
    
    def __init__(self):
        # Diccionario: user_id -> {"estado": str}
        self.usuarios_cambiando_credenciales = {}
    
    def iniciar_cambio_credenciales(self, user_id: str):
        """Inicia el proceso de cambio de credenciales"""
        self.usuarios_cambiando_credenciales[user_id] = {
            "estado": "esperando_credenciales"
        }
    
    def esta_cambiando_credenciales(self, user_id: str) -> bool:
        """Verifica si un usuario está en proceso de cambiar credenciales"""
        return user_id in self.usuarios_cambiando_credenciales
    
    def procesar_nueva_credencial(self, db: Session, user_id: str, texto: str, canal: str = "webapp"):
        """
        Procesa las nuevas credenciales del usuario.
        
        FLUJO (igual que primera vez):
        1. Extraer credenciales del texto
        2. Si no se extraen → pedir de nuevo
        3. Si se extraen → devolver para que server.py haga login y guarde
        
        Returns:
            (necesita_login, mensaje, credenciales)
            - necesita_login=True → server.py debe hacer login con las credenciales
            - necesita_login=False → hubo error o cancelación
        """
        estado = self.usuarios_cambiando_credenciales.get(user_id)
        
        if not estado:
            return (False, None, None)
        
        # Manejar cancelación
        texto_lower = texto.lower().strip()
        if texto_lower in ['cancelar', 'cancel', 'no', 'salir']:
            self.finalizar_cambio(user_id)
            return (False, " Cambio de credenciales cancelado.", None)
        
        # Extraer credenciales (misma función que primera vez)
        from auth_handler import extraer_credenciales_con_gpt
        credenciales = extraer_credenciales_con_gpt(texto)
        
        username = credenciales.get("username")
        password = credenciales.get("password")
        
        # Validar que tengamos AMBAS credenciales
        if not credenciales["ambos"]:
            mensaje_incompleto = (
                " No he podido extraer las credenciales.\n\n"
                " *Envíamelas así:*\n"
                "```\n"
                "Usuario: tu_usuario  Contraseña: tu_contraseña\n"
                "```\n\n"
                " Escribe *'cancelar'* para salir."
            )
            return (False, mensaje_incompleto, None)
        
        # Validar longitud mínima
        if len(username) < 3:
            return (False, " El usuario debe tener al menos 3 caracteres. Inténtalo de nuevo.", None)
        
        if len(password) < 4:
            return (False, " La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo.", None)
        
        # Credenciales extraídas OK → devolver para que server.py haga login
        return (True, None, {"username": username, "password": password})
    
    def guardar_credenciales(self, db: Session, user_id: str, username: str, password: str, canal: str = "webapp"):
        """
        Guarda las credenciales después de verificar login exitoso.
        Llamado por server.py después de hacer login OK.
        """
        # Obtener usuario
        if canal == "slack":
            usuario = obtener_usuario_por_origen(db, slack_id=user_id)
        elif canal == "whatsapp":
            usuario = obtener_usuario_por_origen(db, wa_id=user_id)
        else:
            usuario = obtener_usuario_por_origen(db, app_id=user_id)
        
        if not usuario:
            return False, " Error: usuario no encontrado."
        
        # Guardar credenciales cifradas
        usuario.username_intranet = username
        usuario.password_intranet = cifrar(password)
        db.commit()
        
        # Finalizar proceso
        self.finalizar_cambio(user_id)
        
        return True, f"🎉 *¡Credenciales actualizadas!*\n\n Usuario: *{username}*\n Contraseña: ******\n\n Ya puedes seguir usando el bot."
    
    def finalizar_cambio(self, user_id: str):
        """Finaliza el proceso de cambio de credenciales"""
        if user_id in self.usuarios_cambiando_credenciales:
            del self.usuarios_cambiando_credenciales[user_id]


# Instancia global
credential_manager = CredentialManager()
