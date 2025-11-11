"""
Constantes utilizadas en toda la aplicación
"""
from datetime import datetime


class Constants:
    """Constantes del negocio y mapeos"""
    
    # ========================================
    # 📅 MAPEO DE DÍAS
    # ========================================
    DIAS_KEYS = {
        "lunes": "h1",
        "martes": "h2",
        "miércoles": "h3",
        "miercoles": "h3",  # Sin acento también
        "jueves": "h4",
        "viernes": "h5",
    }
    
    DIAS_NOMBRES = ["lunes", "martes", "miércoles", "jueves", "viernes"]
    
    DIAS_EN_INGLES_MAP = {
        "monday": "lunes",
        "tuesday": "martes",
        "wednesday": "miércoles",
        "thursday": "jueves",
        "friday": "viernes",
    }
    
    # ========================================
    # ⏰ HORAS SEMANALES POR DEFECTO
    # ========================================
    HORAS_SEMANA_DEFAULT = {
        "lunes": "8.5",
        "martes": "8.5",
        "miércoles": "8.5",
        "jueves": "8.5",
        "viernes": "6.5",
    }
    
    # ========================================
    # 📆 MESES
    # ========================================
    MESES_ESPANOL = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    
    # ========================================
    # 🤖 CLASIFICACIÓN DE MENSAJES
    # ========================================
    TIPO_COMANDO = "comando"
    TIPO_CONSULTA = "consulta"
    TIPO_CONVERSACION = "conversacion"
    
    # Keywords para detección rápida
    KEYWORDS_JORNADA = [
        "iniciar jornada", "empezar jornada", "comenzar jornada", "inicia jornada",
        "finalizar jornada", "terminar jornada", "acabar jornada", "finaliza jornada", 
        "termina jornada", "acaba jornada",
        "finaliza el dia", "termina el dia", "acaba el dia",
        "finalizar el dia", "terminar el dia", "acabar el dia",
        "fin de jornada", "cierra jornada"
    ]
    
    KEYWORDS_IMPUTACION = [
        "imput", "pon", "añade", "agrega", "quita", "resta", "borra",
        "horas", "proyecto", "guardar", "emitir"
    ]
    
    KEYWORDS_CONSULTA = [
        "qué tengo", "que tengo", "dime", "qué he imputado", "que he imputado",
        "cuántas", "cuantas", "cuántas horas", "cuantas horas",
        "ver", "mostrar", "dame", "info", "consulta", 
        "resumen", "resume", "resumíme", "qué hice", "que hice",
        "he hecho", "tengo hecho"
    ]
    
    # ========================================
    # 📊 ESTADOS Y MODOS
    # ========================================
    MODO_SUMAR = "sumar"
    MODO_ESTABLECER = "establecer"
    
    ESTADO_OK = "ok"
    ESTADO_ERROR = "error"
    ESTADO_CREDENCIALES_INVALIDAS = "credenciales_invalidas"
    
    # ========================================
    # 🔧 UTILIDADES
    # ========================================
    @staticmethod
    def get_fecha_hoy() -> datetime:
        """Devuelve la fecha de hoy"""
        return datetime.now()
    
    @staticmethod
    def get_fecha_hoy_str() -> str:
        """Devuelve la fecha de hoy en formato ISO"""
        return datetime.now().strftime("%Y-%m-%d")
    
    @staticmethod
    def get_dia_semana_str() -> str:
        """Devuelve el día de la semana en español"""
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        return dias[datetime.now().weekday()]
    
    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """Normaliza texto quitando acentos y pasando a minúsculas"""
        import unicodedata
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto.lower())
            if unicodedata.category(c) != 'Mn'
        )


# Instancia global de constantes
constants = Constants()
