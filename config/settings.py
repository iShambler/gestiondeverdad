"""
Configuración y variables de entorno
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# Cargar variables del .env
load_dotenv()


class Settings:
    """Configuración centralizada de la aplicación"""
    
    # ========================================
    # 🔐 CREDENCIALES Y URLs
    # ========================================
    LOGIN_URL = os.getenv("URL_PRIVADA")
    INTRA_USER = os.getenv("INTRA_USER")
    INTRA_PASS = os.getenv("INTRA_PASS")
    
    # ========================================
    #  OPENAI
    # ========================================
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL_MAIN = "gpt-4o"
    OPENAI_MODEL_MINI = "gpt-4o-mini"
    
    # ========================================
    # 💬 SLACK
    # ========================================
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_API_URL = "https://slack.com/api/chat.postMessage"
    
    # ========================================
    # 🔒 CIFRADO
    # ========================================
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    
    # ========================================
    # 🗄️ BASE DE DATOS
    # ========================================
    DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://agente:1234@localhost:3306/agente_bot")
    
    # ========================================
    # 🌐 BROWSER POOL
    # ========================================
    MAX_BROWSER_SESSIONS = 10
    SESSION_TIMEOUT_MINUTES = 3
    
    # ========================================
    # ⏱️ TIMEOUTS Y ESPERAS
    # ========================================
    WEBDRIVER_TIMEOUT = 15  # segundos
    DEFAULT_WAIT = 2  # segundos
    AFTER_ACTION_WAIT = 0.2  # segundos
    AFTER_SAVE_WAIT = 1.5  # segundos
    AFTER_CALENDAR_CLICK = 0.3  # segundos
    AFTER_DATE_SELECT = 2  # segundos para cargar pantalla de imputación
    
    @classmethod
    def get_openai_client(cls) -> OpenAI:
        """Obtiene una instancia configurada del cliente OpenAI"""
        return OpenAI(api_key=cls.OPENAI_API_KEY)


# Instancia global de configuración
settings = Settings()
