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

    #  Si NO tiene credenciales guardadas → generar enlace de login
    if not usuario.username_intranet or not usuario.password_intranet:
        if canal == "whatsapp":
            from auth_token_manager import auth_token_manager
            import os
            base_url = os.getenv("BASE_URL", "https://tu-dominio.com")
            token = auth_token_manager.generar_token(user_id)
            login_url = f"{base_url}/auth/login?token={token}"
            mensaje = (
                f"👋 *¡Hola!* Aún no tengo tus credenciales de GestiónITT.\n\n"
                f"🔐 Configura tus credenciales aquí:\n{login_url}\n\n"
                f"⏳ El enlace caduca en 15 minutos.\n"
                f"🔒 Tus credenciales se guardan cifradas y seguras."
            )
        else:
            mensaje = (
                "👋 **¡Hola!** Aún no tengo tus credenciales de GestiónITT.\n\n"
                " Dirígete a **Mi Perfil → Integración con GestiónITT** y configúralas.\n\n"
                "Una vez configuradas, ¡podré ayudarte! 😊"
            )
        return usuario, mensaje

    #  Si las tiene → todo OK
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
    - paco y contraseña pepe            (lenguaje natural)
    - mi usuario es paco y mi clave es pepe
    
    Returns:
        dict: {"username": str, "password": str, "ambos": bool}
    """
    texto_limpio = texto.strip()
    
    print(f"[DEBUG extraer_credenciales] Texto original: {texto}")
    
    username = None
    password = None
    
    # =====================================================
    # PATRÓN 1: Lenguaje natural "XXX y contraseña YYY"
    # Ejemplo: "pablo.solis y contraseña Arelance2026k."
    # =====================================================
    patron_natural = re.search(
        r'^([^\s]+)\s+y\s+(?:contraseña|contrasena|password|pass|clave)\s+([^\s]+)',
        texto_limpio,
        re.IGNORECASE
    )
    
    if patron_natural:
        username = patron_natural.group(1).strip().rstrip('.')
        password = patron_natural.group(2).strip().rstrip('.')
        print(f"[DEBUG extraer_credenciales] Patrón natural detectado: user='{username}', pass='{password}'")
    
    # =====================================================
    # PATRÓN 2: Con palabra clave "usuario" explícita
    # Ejemplo: "Usuario: pablo.solis Contraseña: xxx"
    # =====================================================
    if not username:
        usuario_match = re.search(
            r'(?:usuario|user|username|login)\s*:?\s+([^\n\r]+?)(?=\s+(?:contraseña|contrasena|password|pass|clave|y\s*contraseña|y\s*password)|\s*$)',
            texto_limpio,
            re.IGNORECASE
        )
        
        if usuario_match:
            username = usuario_match.group(1).strip()
            username = re.sub(r'\s+$', '', username)
            print(f"[DEBUG extraer_credenciales] Usuario encontrado (patrón 2): '{username}'")
    
    if not password:
        password_match = re.search(
            r'(?:contraseña|contrasena|password|pass|clave|pwd)\s*:?\s+([^\n\r(]+)',
            texto_limpio,
            re.IGNORECASE
        )
        
        if password_match:
            password = password_match.group(1).strip()
            password = re.sub(r'\s+$', '', password)
            print(f"[DEBUG extraer_credenciales] Contraseña encontrada (patrón 2): '{password}'")
    
    # =====================================================
    # PATRÓN 3: "mi usuario es X y mi clave es Y"
    # =====================================================
    if not username or not password:
        patron_es = re.search(
            r'(?:mi\s+)?(?:usuario|user)\s+(?:es\s+)?([^\s,]+).*?(?:mi\s+)?(?:contraseña|contrasena|password|pass|clave)\s+(?:es\s+)?([^\s,]+)',
            texto_limpio,
            re.IGNORECASE
        )
        
        if patron_es:
            username = patron_es.group(1).strip().rstrip('.')
            password = patron_es.group(2).strip().rstrip('.')
            print(f"[DEBUG extraer_credenciales] Patrón 'es' detectado: user='{username}', pass='{password}'")
    
    resultado = {
        "username": username,
        "password": password,
        "ambos": bool(username and password)
    }
    
    print(f"[DEBUG extraer_credenciales] Resultado final: {resultado}")
    
    return resultado
