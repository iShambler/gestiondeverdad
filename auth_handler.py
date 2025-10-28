# auth_handler.py
"""
Maneja la verificación de credenciales ya guardadas.
(No solicita ni procesa credenciales por chat)
"""
from sqlalchemy.orm import Session
from db import Usuario, obtener_usuario_por_origen, crear_usuario


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
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)

    # Crear usuario si no existe
    if not usuario:
        if canal == "slack":
            usuario = crear_usuario(db, slack_id=user_id, canal=canal)
        else:
            usuario = crear_usuario(db, app_id=user_id, canal=canal)

    # ✅ Si NO tiene credenciales guardadas → mostrar mensaje
    if not usuario.username_intranet or not usuario.password_intranet:
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
    else:
        usuario = obtener_usuario_por_origen(db, app_id=user_id)

    if not usuario:
        return None, None

    username = usuario.username_intranet
    password = usuario.obtener_password_intranet()

    return username, password
