# recovery_handler.py
"""
Maneja recuperación de errores y refresh del navegador
"""
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from datetime import datetime


class RecoveryHandler:
    """
    Maneja la recuperación automática cuando el navegador se queda pillado
    """
    
    def __init__(self):
        self.errores_por_usuario = {}  # user_id -> contador de errores
        self.max_intentos = 2  # Número máximo de intentos antes de refresh
    
    def registrar_error(self, user_id: str):
        """Registra un error para un usuario"""
        if user_id not in self.errores_por_usuario:
            self.errores_por_usuario[user_id] = 0
        self.errores_por_usuario[user_id] += 1
        
        return self.errores_por_usuario[user_id]
    
    def limpiar_errores(self, user_id: str):
        """Limpia el contador de errores tras éxito"""
        if user_id in self.errores_por_usuario:
            del self.errores_por_usuario[user_id]
    
    def necesita_refresh(self, user_id: str) -> bool:
        """Determina si necesita hacer refresh del navegador"""
        return self.errores_por_usuario.get(user_id, 0) >= self.max_intentos
    
    def intentar_recuperacion(self, session, username, password):
        """
        Intenta recuperar una sesión haciendo refresh y re-login
        
        Returns:
            tuple: (success: bool, mensaje: str)
        """
        try:
            print(f"[RECOVERY] 🔄 Intentando recuperar sesión...")
            
            # Refresh del navegador
            session.driver.refresh()
            
            # Esperar a que cargue
            import time
            time.sleep(2)
            
            # Hacer login de nuevo
            from main_script import hacer_login
            success, mensaje = hacer_login(session.driver, session.wait, username, password)
            
            if success:
                session.is_logged_in = True
                print(f"[RECOVERY] ✅ Sesión recuperada exitosamente")
                return True, "Sesión recuperada"
            else:
                print(f"[RECOVERY] ❌ No se pudo recuperar la sesión")
                return False, "Error en recuperación"
                
        except Exception as e:
            print(f"[RECOVERY] ❌ Error en recuperación: {e}")
            return False, str(e)


# Instancia global
recovery_handler = RecoveryHandler()
