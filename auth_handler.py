# auth_handler.py
"""
Maneja la autenticación y solicitud de credenciales a nuevos usuarios
"""
from sqlalchemy.orm import Session
from db import Usuario, obtener_usuario_por_origen, crear_usuario
import re


class EstadoAutenticacion:
    """
    Mantiene el estado de autenticación de usuarios que están
    en proceso de proporcionar sus credenciales.
    """
    def __init__(self):
        # Diccionario: user_id -> {"esperando": "username" | "password", "username_temporal": "..."}
        self.usuarios_en_proceso = {}
    
    def iniciar_proceso(self, user_id: str):
        """Inicia el proceso de solicitud de credenciales."""
        self.usuarios_en_proceso[user_id] = {
            "esperando": "username",
            "username_temporal": None
        }
    
    def esta_en_proceso(self, user_id: str) -> bool:
        """Verifica si un usuario está en proceso de autenticación."""
        return user_id in self.usuarios_en_proceso
    
    def obtener_estado(self, user_id: str):
        """Obtiene el estado actual del proceso."""
        return self.usuarios_en_proceso.get(user_id)
    
    def guardar_username(self, user_id: str, username: str):
        """Guarda el username temporal y marca que ahora esperamos la contraseña."""
        if user_id in self.usuarios_en_proceso:
            self.usuarios_en_proceso[user_id]["username_temporal"] = username
            self.usuarios_en_proceso[user_id]["esperando"] = "password"
    
    def finalizar_proceso(self, user_id: str):
        """Elimina el usuario del proceso de autenticación."""
        if user_id in self.usuarios_en_proceso:
            del self.usuarios_en_proceso[user_id]


# Instancia global para mantener el estado
estado_auth = EstadoAutenticacion()


def verificar_y_solicitar_credenciales(db: Session, user_id: str, canal: str = "webapp") -> tuple[Usuario, str]:
    """
    Verifica si un usuario tiene credenciales guardadas.
    
    Returns:
        (usuario, mensaje): 
            - Si tiene credenciales: (usuario, None)
            - Si necesita credenciales: (usuario, mensaje_solicitando_credenciales)
    """
    # Determinar el tipo de ID según el canal
    if canal == "slack":
        usuario = obtener_usuario_por_origen(db, slack_id=user_id)
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)
    
    # Si el usuario no existe, crearlo
    if not usuario:
        if canal == "slack":
            usuario = crear_usuario(db, slack_id=user_id, canal=canal)
        else:
            usuario = crear_usuario(db, app_id=user_id, canal=canal)
    
    # Verificar si tiene credenciales
    if not usuario.username_intranet or not usuario.password_intranet:
        estado_auth.iniciar_proceso(user_id)
        mensaje = (
            "👋 **¡Hola!** Para ayudarte con la imputación de horas, necesito tus credenciales de GestiónITT.\n\n"
            "🔑 Por favor, envíame tu **nombre de usuario** de la intranet.\n\n"
            "🔒 Tus credenciales se guardarán cifradas y solo se usarán para automatizar tus imputaciones."
        )
        return usuario, mensaje
    
    return usuario, None


def extraer_credenciales_con_gpt(texto: str) -> dict:
    """
    Usa GPT para extraer username y password de un texto en lenguaje natural.
    
    Returns:
        {"username": "...", "password": "...", "ambos": bool}
    """
    from openai import OpenAI
    import os
    import json
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Extrae el usuario y/o contraseña del siguiente texto.

Texto: "{texto}"

Devuelve SOLO un JSON con este formato:
{{
  "username": "usuario_extraido" o null,
  "password": "contraseña_extraida" o null
}}

Ejemplos:
- "Mi usuario es pablo.solis" → {{"username": "pablo.solis", "password": null}}
- "La contraseña es AreLance25k." → {{"username": null, "password": "AreLance25k."}}
- "Mi usuario es pablo.solis y mi contraseña es AreLance25k." → {{"username": "pablo.solis", "password": "AreLance25k."}}
- "pablo.solis" → {{"username": "pablo.solis", "password": null}}
- "AreLance25k." → {{"username": null, "password": "AreLance25k."}}

Respuesta:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un extractor de credenciales. Devuelves solo JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        resultado = json.loads(response.choices[0].message.content.strip())
        resultado["ambos"] = resultado.get("username") and resultado.get("password")
        return resultado
    
    except Exception as e:
        print(f"[ERROR] Error extrayendo credenciales con GPT: {e}")
        # Fallback: asumir que el texto es el username o password directo
        return {"username": texto.strip() if len(texto.strip()) > 0 else None, "password": None, "ambos": False}


def procesar_credencial(db: Session, user_id: str, texto: str, canal: str = "webapp") -> tuple[bool, str]:
    """
    Procesa las credenciales que el usuario está proporcionando.
    Usa GPT para extraer username y password del texto en lenguaje natural.
    
    Returns:
        (completado, mensaje):
            - completado: True si ya tiene ambas credenciales guardadas
            - mensaje: Respuesta para el usuario
    """
    estado = estado_auth.obtener_estado(user_id)
    
    if not estado:
        return True, None  # No está en proceso de autenticación
    
    # Determinar el tipo de ID según el canal
    if canal == "slack":
        usuario = obtener_usuario_por_origen(db, slack_id=user_id)
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)
    
    if not usuario:
        estado_auth.finalizar_proceso(user_id)
        return True, "⚠️ Ha ocurrido un error. Por favor, intenta de nuevo."
    
    # 🧠 Extraer credenciales con GPT
    # Pero primero, validar que no sean saludos o mensajes muy cortos
    texto_lower = texto.lower().strip()
    saludos = ['hola', 'hi', 'hey', 'buenos dias', 'buenas tardes', 'buenas noches', 'ola', 'holi']
    
    if texto_lower in saludos:
        # Es un saludo, no credenciales
        if estado["esperando"] == "username":
            return False, "❌ Por favor, envíame tu **nombre de usuario** de GestiónITT (no un saludo 😄):"
        else:
            return False, "❌ Por favor, envíame tu **contraseña** de GestiónITT:"
    
    if len(texto.strip()) < 3:
        return False, "❌ El texto es demasiado corto. Por favor, envíame tus credenciales:"
    
    credenciales = extraer_credenciales_con_gpt(texto)
    
    # Procesar según lo que estemos esperando
    if estado["esperando"] == "username":
        username = credenciales.get("username")
        password = credenciales.get("password")
        
        # Si nos dio ambas credenciales de una vez
        if credenciales["ambos"]:
            if not username or len(username) < 3:
                return False, "❌ El nombre de usuario debe tener al menos 3 caracteres. Inténtalo de nuevo:"
            
            if not password or len(password) < 4:
                return False, "❌ La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo:"
            
            # Guardar ambas credenciales directamente
            usuario.establecer_credenciales_intranet(username, password)
            db.commit()
            estado_auth.finalizar_proceso(user_id)
            
            # Mensaje temporal (será reemplazado por el de verificación)
            mensaje = "🔄 Verificando tus credenciales..."
            return True, mensaje
        
        # Solo nos dio el username
        elif username:
            if len(username) < 3:
                return False, "❌ El nombre de usuario debe tener al menos 3 caracteres. Inténtalo de nuevo:"
            
            estado_auth.guardar_username(user_id, username)
            
            mensaje = (
                f"✅ Usuario recibido: **{username}**\n\n"
                "🔑 Ahora envíame tu **contraseña** de GestiónITT."
            )
            return False, mensaje
        
        else:
            return False, "❌ No he podido extraer el nombre de usuario. Por favor, envíamelo de nuevo:"
    
    elif estado["esperando"] == "password":
        # Intentar extraer password primero
        password = credenciales.get("password")
        
        # Si no encontró password explícito, el texto completo es la password
        if not password:
            password = texto.strip()
        
        if not password or len(password) < 4:
            return False, "❌ La contraseña debe tener al menos 4 caracteres. Inténtalo de nuevo:"
        
        # Guardar credenciales en la base de datos (cifradas)
        username = estado["username_temporal"]
        usuario.establecer_credenciales_intranet(username, password)
        db.commit()
        
        # Finalizar proceso (la verificación se hará en server.py)
        estado_auth.finalizar_proceso(user_id)
        
        # Mensaje temporal (será reemplazado por el de verificación)
        mensaje = "🔄 Verificando tus credenciales..."
        return True, mensaje
    
    return True, None


def obtener_credenciales(db: Session, user_id: str, canal: str = "webapp") -> tuple[str, str]:
    """
    Obtiene las credenciales de un usuario.
    
    Returns:
        (username, password): Credenciales descifradas o (None, None) si no existen
    """
    if canal == "slack":
        usuario = obtener_usuario_por_origen(db, slack_id=user_id)
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)
    
    if not usuario:
        return None, None
    
    username = usuario.username_intranet
    password = usuario.obtener_password_intranet()
    
    return username, password
