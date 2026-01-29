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
        
        # 🆕 Usar .get() para evitar KeyError si no hay timestamp
        timestamp = estado.get("timestamp")
        if not timestamp:
            # Si no hay timestamp, el estado es inválido, limpiar
            print(f"[CONVERSACION]  Estado sin timestamp para usuario: {user_id}, limpiando...")
            self.limpiar_estado(user_id)
            return False
        
        # Verificar si ha expirado
        if datetime.now() - timestamp > timedelta(minutes=self.timeout_minutes):
            print(f"[CONVERSACION] ⏰ Estado expirado para usuario: {user_id}")
            self.limpiar_estado(user_id)
            return False
        
        return estado.get("tipo") in ["desambiguacion_proyecto", "info_incompleta"]
    
    def guardar_desambiguacion(self, user_id, nombre_proyecto, coincidencias, comando_original, indice_orden=0, respuestas_acumuladas=None, texto_original=None):
        """
        Guarda el estado de una pregunta de desambiguación pendiente.
        
        Args:
            user_id: ID del usuario
            nombre_proyecto: Nombre del proyecto con múltiples coincidencias
            coincidencias: Lista de coincidencias de buscar_proyectos_duplicados()
            comando_original: Comando original del usuario para reejecutar después
            indice_orden: Índice de la orden que causó la desambiguación (para continuar después)
            respuestas_acumuladas: Lista de respuestas ya generadas antes de la desambiguación
            texto_original: Texto original completo del comando del usuario
        """
        self.estados[user_id] = {
            "tipo": "desambiguacion_proyecto",
            "nombre_proyecto": nombre_proyecto,
            "coincidencias": coincidencias,
            "comando_original": comando_original,
            "indice_orden": indice_orden,
            "respuestas_acumuladas": respuestas_acumuladas or [],  # 🆕 Guardar respuestas previas
            "texto_original": texto_original,  # 🆕 Guardar texto original completo
            "timestamp": datetime.now()
        }
        
        print(f"[CONVERSACION] 💾 Guardado estado de desambiguación para: {user_id}")
        print(f"[CONVERSACION]    Proyecto: {nombre_proyecto}")
        print(f"[CONVERSACION]    Coincidencias: {len(coincidencias)}")
        print(f"[CONVERSACION]    Índice orden: {indice_orden}")
        print(f"[CONVERSACION]    Respuestas acumuladas: {len(respuestas_acumuladas or [])}")
    
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
    
    def guardar_info_incompleta(self, user_id, info_parcial, que_falta):
        """
        Guarda información parcial cuando el usuario proporciona datos incompletos.
        
        Args:
            user_id: ID del usuario
            info_parcial: Dict con la información que el usuario YA proporcionó
                         Ejemplo: {'proyecto': 'Desarrollo'} o {'horas': 3, 'dia': 'hoy'}
            que_falta: Qué información falta ('proyecto', 'horas', 'dia', etc.)
        """
        self.estados[user_id] = {
            "tipo": "info_incompleta",
            "info_parcial": info_parcial,
            "que_falta": que_falta,
            "timestamp": datetime.now()
        }
        
        print(f"[CONVERSACION] 💾 Guardada info incompleta para: {user_id}")
        print(f"[CONVERSACION]    Info parcial: {info_parcial}")
        print(f"[CONVERSACION]    Falta: {que_falta}")
    
    def obtener_info_incompleta(self, user_id):
        """
        Obtiene la información parcial guardada de un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            dict: Info parcial guardada o None si no existe
        """
        if user_id not in self.estados:
            return None
        
        estado = self.estados[user_id]
        if estado.get("tipo") != "info_incompleta":
            return None
        
        return estado
    
    def guardar_ultimo_proyecto(self, user_id, nombre_proyecto, nodo_padre=None, dia=None):
        """
        Guarda el último proyecto usado por el usuario para referencia futura.
        
        Args:
            user_id: ID del usuario
            nombre_proyecto: Nombre del proyecto
            nodo_padre: Nodo padre del proyecto (opcional)
            dia: Día imputado (opcional, ej: "viernes", "lunes")
        """
        if user_id not in self.estados:
            self.estados[user_id] = {}
        
        # Actualizar solo el campo de último proyecto sin borrar otros estados
        self.estados[user_id]["ultimo_proyecto"] = {
            "nombre": nombre_proyecto,
            "nodo_padre": nodo_padre,
            "dia": dia,  # 🆕 NUEVO
            "timestamp": datetime.now()
        }
        
        print(f"[CONVERSACION] 💾 Guardado último proyecto para {user_id}: {nombre_proyecto}")
        if dia:
            print(f"[CONVERSACION]    Día: {dia}")
    
    def obtener_ultimo_proyecto(self, user_id):
        """
        Obtiene el último proyecto usado por el usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            dict: {'nombre': str, 'nodo_padre': str} o None
        """
        if user_id not in self.estados:
            return None
        
        ultimo = self.estados[user_id].get("ultimo_proyecto")
        if not ultimo:
            return None
        
        # 🆕 Verificar que tenga timestamp antes de comparar
        timestamp = ultimo.get("timestamp")
        if not timestamp:
            print(f"[CONVERSACION]  Último proyecto sin timestamp para {user_id}")
            return None
        
        # Verificar si no ha expirado (15 minutos)
        if datetime.now() - timestamp > timedelta(minutes=15):
            print(f"[CONVERSACION] ⏰ Último proyecto expirado para {user_id}")
            return None
        
        return ultimo
    
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
            if estado.get("timestamp") and ahora - estado["timestamp"] > timedelta(minutes=self.timeout_minutes)
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
