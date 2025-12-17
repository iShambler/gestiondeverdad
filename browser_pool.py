# browser_pool.py
"""
Gestor de pool de navegadores para múltiples usuarios concurrentes.
Cada usuario obtiene su propio navegador Chrome.
"""

import platform
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from datetime import datetime, timedelta
import threading
import time


def get_chrome_service():
    """
    Devuelve un ChromeService adecuado según el sistema operativo.
    - En Linux usa /usr/bin/chromedriver (como en tu servidor)
    - En Windows usa Selenium Manager automáticamente (sin ruta)
    """
    system = platform.system()

    if system == "Linux":
        return ChromeService(executable_path="/usr/bin/chromedriver")

    elif system == "Windows":
        # Selenium Manager resolverá el driver automáticamente
        return ChromeService()

    else:
        raise Exception(f"Sistema operativo no soportado: {system}")


class BrowserSession:
    """Representa una sesión de navegador para un usuario específico."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.driver = None
        self.wait = None
        self.last_activity = datetime.now()
        self.is_logged_in = False
        self.contexto = {"fila_actual": None, "proyecto_actual": None}
        self.lock = threading.Lock()  # Para operaciones thread-safe
        
    def initialize(self):
        """Inicializa el navegador Chrome."""
        try:
            service = get_chrome_service()
            options = webdriver.ChromeOptions()

            # MODO HEADLESS
            options.add_argument('--headless=new')  # 🔥 CRÍTICO: Modo headless
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')

            # Solo Linux
            if platform.system() == "Linux":
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-extensions')
                options.add_argument('--disable-infobars')
                options.add_argument('--remote-debugging-port=0')  # Puerto aleatorio
                options.add_argument('--single-process')  # Reduce memoria

            self.driver = webdriver.Chrome(service=service, options=options)
            self.wait = WebDriverWait(self.driver, 15)
            self.last_activity = datetime.now()
            print(f"[BROWSER POOL] ✅ Navegador iniciado para usuario: {self.user_id}")
            return True

        except Exception as e:
            print(f"[BROWSER POOL] ❌ Error iniciando navegador para {self.user_id}: {e}")
            return False
    
    def update_activity(self):
        """Actualiza el timestamp de última actividad."""
        self.last_activity = datetime.now()
    
    def is_expired(self, timeout_minutes: int = 3) -> bool:
        """Verifica si la sesión ha expirado por inactividad."""
        return datetime.now() - self.last_activity > timedelta(minutes=timeout_minutes)
    
    def close(self):
        """Cierra el navegador y libera recursos."""
        try:
            if self.driver:
                self.driver.quit()
                print(f"[BROWSER POOL] 🔒 Navegador cerrado para usuario: {self.user_id}")
        except Exception as e:
            print(f"[BROWSER POOL] ⚠️ Error cerrando navegador para {self.user_id}: {e}")
        finally:
            self.driver = None
            self.wait = None
            self.is_logged_in = False


class BrowserPool:
    """
    Pool de navegadores que gestiona sesiones para múltiples usuarios.
    """
    
    def __init__(self, max_sessions: int = 10, session_timeout_minutes: int = 3):
        self.sessions = {}  # user_id -> BrowserSession
        self.max_sessions = max_sessions
        self.session_timeout_minutes = session_timeout_minutes
        self.lock = threading.Lock()
        
        # Iniciar thread de limpieza de sesiones inactivas
        self.cleanup_thread = threading.Thread(target=self._cleanup_expired_sessions, daemon=True)
        self.cleanup_thread.start()
        print(f"[BROWSER POOL] 🚀 Pool inicializado (max: {max_sessions}, timeout: {session_timeout_minutes}min)")
    
    def get_session(self, user_id: str) -> BrowserSession:
        """Obtiene o crea una sesión de navegador para un usuario."""
        with self.lock:
            if user_id in self.sessions:
                session = self.sessions[user_id]
                session.update_activity()
                return session
            
            # Limpiar si se alcanzó el límite
            if len(self.sessions) >= self.max_sessions:
                self._force_cleanup()
                
                if len(self.sessions) >= self.max_sessions:
                    print(f"[BROWSER POOL] ⚠️ Límite de sesiones alcanzado ({self.max_sessions})")
                    oldest_user = min(self.sessions.keys(), 
                                    key=lambda k: self.sessions[k].last_activity)
                    self.close_session(oldest_user)
            
            session = BrowserSession(user_id)
            if session.initialize():
                self.sessions[user_id] = session
                print(f"[BROWSER POOL] 📊 Sesiones activas: {len(self.sessions)}/{self.max_sessions}")
                return session
            else:
                return None
    
    def close_session(self, user_id: str):
        """Cierra la sesión de un usuario específico."""
        with self.lock:
            if user_id in self.sessions:
                self.sessions[user_id].close()
                del self.sessions[user_id]
                print(f"[BROWSER POOL] 📊 Sesiones activas: {len(self.sessions)}/{self.max_sessions}")
    
    def _force_cleanup(self):
        """Limpia forzosamente sesiones expiradas."""
        expired = [
            user_id for user_id, session in self.sessions.items()
            if session.is_expired(self.session_timeout_minutes)
        ]
        
        for user_id in expired:
            print(f"[BROWSER POOL] 🧹 Cerrando sesión expirada: {user_id}")
            self.sessions[user_id].close()
            del self.sessions[user_id]
    
    def _cleanup_expired_sessions(self):
        """Thread que limpia sesiones expiradas periódicamente."""
        while True:
            time.sleep(30)
            with self.lock:
                expired = [
                    user_id for user_id, session in self.sessions.items()
                    if session.is_expired(self.session_timeout_minutes)
                ]
                
                if expired:
                    print(f"[BROWSER POOL] 🧹 Limpiando {len(expired)} sesiones expiradas...")
                    for user_id in expired:
                        self.sessions[user_id].close()
                        del self.sessions[user_id]
                    print(f"[BROWSER POOL] 📊 Sesiones activas: {len(self.sessions)}/{self.max_sessions}")
    
    def close_all(self):
        """Cierra todas las sesiones activas."""
        with self.lock:
            print(f"[BROWSER POOL] 🛑 Cerrando todas las sesiones ({len(self.sessions)})...")
            for session in self.sessions.values():
                session.close()
            self.sessions.clear()
            print("[BROWSER POOL] ✅ Todas las sesiones cerradas")
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del pool."""
        with self.lock:
            return {
                "active_sessions": len(self.sessions),
                "max_sessions": self.max_sessions,
                "users": list(self.sessions.keys())
            }


# Instancia global del pool
# 🔥 Timeout de 30 min para evitar re-logins frecuentes
browser_pool = BrowserPool(max_sessions=50, session_timeout_minutes=30)
