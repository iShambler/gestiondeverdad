# auth_handler.py
"""
Maneja la verificación de credenciales ya guardadas.
(No solicita ni procesa credenciales por chat)
"""
from sqlalchemy.orm import Session
from db import Usuario, obtener_usuario_por_origen, crear_usuario
import re


def verificar_y_solicitar_credenciales(db: Session, user_id: str, canal: str = "webapp"):
    """
    Verifica si un usuario tiene credenciales guardadas.

    Returns:
        (usuario, mensaje):
            - Si tiene credenciales -> (usuario, None)
            - Si no tiene credenciales -> (usuario, mensaje explicativo)
    """

    # Identificar usuario según canal
    if canal == "slack":
        usuario = obtener_usuario_por_origen(db, slack_id=user_id)
    elif canal == "whatsapp":
        usuario = obtener_usuario_por_origen(db, wa_id=user_id)
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)

    # Crear usuario si no existe
    if not usuario:
        if canal == "slack":
            usuario = crear_usuario(db, slack_id=user_id, canal=canal)
        elif canal == "whatsapp":
            usuario = crear_usuario(db, wa_id=user_id, canal=canal)
        else:
            usuario = crear_usuario(db, app_id=user_id, canal=canal)

    # ✅ Si NO tiene credenciales guardadas → mostrar mensaje
    if not usuario.username_intranet or not usuario.password_intranet:
        # Mensaje diferente para WhatsApp (permite ingresarlas por chat)
        if canal == "whatsapp":
            mensaje = (
                "👋 *¡Hola!* Aún no tengo tus credenciales de GestiónITT.\n\n"
                "📝 Por favor, envíamelas en este formato:\n\n"
                "```\n"
                "Usuario: tu_usuario  Contraseña: tu_contraseña (todo sin tabular)\n"
                "```\n\n"
                "🔒 Tus credenciales se guardan cifradas y seguras."
            )
        else:
            mensaje = (
                "👋 **¡Hola!** Aún no tengo tus credenciales de GestiónITT.\n\n"
                "🔧 Dirígete a **Mi Perfil → Integración con GestiónITT** y configúralas.\n\n"
                "Una vez configuradas, ¡podré ayudarte! 😊"
            )
        return usuario, mensaje

    # ✅ Si las tiene → todo OK
    return usuario, None


def obtener_credenciales(db: Session, user_id: str, canal: str = "webapp") -> tuple[str, str]:
    """
    Devuelve las credenciales guardadas.
    """
    if canal == "slack":
        usuario = obtener_usuario_por_origen(db, slack_id=user_id)
    elif canal == "whatsapp":
        usuario = obtener_usuario_por_origen(db, wa_id=user_id)
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)

    if not usuario:
        return None, None

    username = usuario.username_intranet
    password = usuario.obtener_password_intranet()

    return username, password


def extraer_credenciales_con_gpt(texto: str) -> dict:
    """
    Extrae usuario y contraseña de un texto en formato libre.
    Acepta formatos:
    - Usuario: xxx  /  Contraseña: yyy  (con dos puntos)
    - Usuario xxx  /  Contraseña yyy    (sin dos puntos)
    - usuario paco contraseña pepe      (sin dos puntos)
    
    Returns:
        dict: {"username": str, "password": str, "ambos": bool}
    """
    texto_limpio = texto.strip()
    
    print(f"[DEBUG extraer_credenciales] Texto original: {texto}")
    
    username = None
    password = None
    
    # Patrón más flexible: con o sin dos puntos
    # Buscar "usuario" seguido de: dos puntos opcional, luego capturar hasta encontrar "contraseña" o fin de línea
    usuario_match = re.search(
        r'(?:usuario|user|username|login)\s*:?\s+([^\n\r]+?)(?=\s+(?:contraseña|contrasena|password|pass|clave|y\s*contraseña|y\s*password)|\s*$)',
        texto_limpio,
        re.IGNORECASE
    )
    
    if usuario_match:
        username = usuario_match.group(1).strip()
        # Solo limpiar espacios finales, NO puntos ni comas (pueden ser parte del usuario)
        username = re.sub(r'\s+$', '', username)
        print(f"[DEBUG extraer_credenciales] Usuario encontrado: '{username}'")
    
    # Buscar "contraseña" seguido de: dos puntos opcional, luego capturar hasta fin de línea o paréntesis
    password_match = re.search(
        r'(?:contraseña|contrasena|password|pass|clave|pwd)\s*:?\s+([^\n\r(]+)',
        texto_limpio,
        re.IGNORECASE
    )
    
    if password_match:
        password = password_match.group(1).strip()
        # Solo limpiar espacios finales, NO puntos ni comas (pueden ser parte de la contraseña)
        password = re.sub(r'\s+$', '', password)
        print(f"[DEBUG extraer_credenciales] Contraseña encontrada: '{password}'")
    
    resultado = {
        "username": username,
        "password": password,
        "ambos": bool(username and password)
    }
    
    print(f"[DEBUG extraer_credenciales] Resultado final: {resultado}")
    
    return resultado
