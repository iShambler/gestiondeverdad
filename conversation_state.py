"""
Gestor de estado de conversación para desambiguación interactiva.
Mantiene el contexto de las preguntas pendientes por usuario.
"""

from datetime import datetime, timedelta


class ConversationStateManager:
    """
    Gestiona el estado de conversaciones con preguntas pendientes.
    Almacena contexto por usuario para desambiguación de proyectos.
    """
    
    def __init__(self, timeout_minutes=5):
        """
        Args:
            timeout_minutes: Tiempo en minutos antes de expirar un estado pendiente
        """
        # Diccionario: user_id -> estado
        self.estados = {}
        self.timeout_minutes = timeout_minutes
    
    def tiene_pregunta_pendiente(self, user_id):
        """
        Verifica si un usuario tiene una pregunta de desambiguación pendiente.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            bool: True si hay pregunta pendiente y no ha expirado
        """
        if user_id not in self.estados:
            return False
        
        estado = self.estados[user_id]
        
        # Verificar si ha expirado
        if datetime.now() - estado["timestamp"] > timedelta(minutes=self.timeout_minutes):
            print(f"[CONVERSACION] ⏰ Estado expirado para usuario: {user_id}")
            self.limpiar_estado(user_id)
            return False
        
        return estado.get("tipo") == "desambiguacion_proyecto"
    
    def guardar_desambiguacion(self, user_id, nombre_proyecto, coincidencias, comando_original):
        """
        Guarda el estado de una pregunta de desambiguación pendiente.
        
        Args:
            user_id: ID del usuario
            nombre_proyecto: Nombre del proyecto con múltiples coincidencias
            coincidencias: Lista de coincidencias de buscar_proyectos_duplicados()
            comando_original: Comando original del usuario para reejecutar después
        """
        self.estados[user_id] = {
            "tipo": "desambiguacion_proyecto",
            "nombre_proyecto": nombre_proyecto,
            "coincidencias": coincidencias,
            "comando_original": comando_original,
            "timestamp": datetime.now()
        }
        
        print(f"[CONVERSACION] 💾 Guardado estado de desambiguación para: {user_id}")
        print(f"[CONVERSACION]    Proyecto: {nombre_proyecto}")
        print(f"[CONVERSACION]    Coincidencias: {len(coincidencias)}")
    
    def obtener_desambiguacion(self, user_id):
        """
        Obtiene el estado de desambiguación pendiente de un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            dict: Estado guardado o None si no existe
        """
        if not self.tiene_pregunta_pendiente(user_id):
            return None
        
        return self.estados[user_id]
    
    def limpiar_estado(self, user_id):
        """
        Limpia el estado pendiente de un usuario.
        
        Args:
            user_id: ID del usuario
        """
        if user_id in self.estados:
            print(f"[CONVERSACION] 🧹 Limpiando estado de usuario: {user_id}")
            del self.estados[user_id]
    
    def limpiar_expirados(self):
        """
        Limpia todos los estados que han expirado.
        """
        ahora = datetime.now()
        usuarios_expirados = [
            user_id for user_id, estado in self.estados.items()
            if ahora - estado["timestamp"] > timedelta(minutes=self.timeout_minutes)
        ]
        
        for user_id in usuarios_expirados:
            print(f"[CONVERSACION] 🧹 Limpiando estado expirado: {user_id}")
            del self.estados[user_id]
    
    def get_stats(self):
        """
        Obtiene estadísticas del gestor de estado.
        
        Returns:
            dict: Estadísticas
        """
        return {
            "estados_activos": len(self.estados),
            "usuarios": list(self.estados.keys())
        }


# Instancia global del gestor de estado
conversation_state_manager = ConversationStateManager(timeout_minutes=5)
