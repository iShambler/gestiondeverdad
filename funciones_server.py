"""
Funciones auxiliares para server.py
Centraliza toda la lógica de manejo de desambiguación, login, credenciales y ejecución
"""

from typing import Tuple, Optional, Dict
from sqlalchemy.orm import Session

from web_automation import hacer_login, leer_tabla_imputacion
from web_automation.desambiguacion import (
    resolver_respuesta_desambiguacion,
    generar_mensaje_desambiguacion
)
from conversation_state import conversation_state_manager
from credential_manager import credential_manager
from core import ejecutar_accion
from ai import interpretar_con_gpt, generar_respuesta_natural
from db import registrar_peticion


# ============================================================================
# AUTENTICACIÓN Y LOGIN
# ============================================================================

def hacer_login_con_lock(session, username: str, password: str) -> Tuple[bool, str]:
    """
    Ejecuta login con lock de la sesión
    
    Args:
        session: BrowserSession del pool
        username: Usuario de GestionITT
        password: Contraseña de GestionITT
        
    Returns:
        (success, mensaje)
    """
    with session.lock:
        return hacer_login(session.driver, session.wait, username, password)


def manejar_cambio_credenciales(texto: str, user_id: str, usuario, db: Session, 
                                canal: str) -> Tuple[bool, str, bool]:
    """
    Maneja el proceso de cambio de credenciales
    
    Returns:
        (completado: bool, mensaje: str, debe_continuar: bool)
    """
    # Manejar cancelación
    if texto.lower().strip() in ['cancelar', 'cancel', 'no']:
        credential_manager.finalizar_cambio(user_id)
        respuesta = "❌ Cambio de credenciales cancelado. Si necesitas ayuda, contacta con soporte."
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=respuesta)
        return (False, respuesta, False)
    
    completado, mensaje = credential_manager.procesar_nueva_credencial(db, user_id, texto, canal=canal)
    registrar_peticion(db, usuario.id, texto, "cambio_credenciales", canal=canal, respuesta=mensaje)
    
    return (completado, mensaje, False)


def realizar_login_inicial(session, user_id: str, username: str, password: str, 
                          usuario, texto: str, db: Session, canal: str) -> Tuple[bool, str, bool]:
    """
    Realiza el login inicial del usuario
    
    Returns:
        (success: bool, mensaje: str, debe_continuar: bool)
    """
    if not session.is_logged_in:
        print(f"[INFO] Haciendo login para usuario: {username} ({user_id})")
        try:
            success, mensaje_login = hacer_login_con_lock(session, username, password)
            
            if not success:
                if "credenciales_invalidas" in mensaje_login:
                    credential_manager.iniciar_cambio_credenciales(user_id)
                    error_msg = (
                        "❌ **Error de login**: Las credenciales de GestiónITT no son correctas.\n\n"
                        "Necesito tus credenciales de GestiónITT.\n\n"
                        "📝 **Envíamelas así:**\n"
                        "```\n"
                        "Usuario: tu_usuario\n"
                        "Contraseña: tu_contraseña\n"
                        "```\n\n"
                        "🔒 **Tranquilo:** Tus credenciales se guardan cifradas.\n\n"
                        "⚠️ Si no quieres cambiarlas, escribe 'cancelar'."
                    )
                    registrar_peticion(db, usuario.id, texto, "error_login", canal=canal, 
                                     respuesta=error_msg, estado="credenciales_invalidas")
                    return (False, error_msg, False)
                else:
                    error_msg = f"⚠️ Error técnico al hacer login: {mensaje_login}"
                    registrar_peticion(db, usuario.id, texto, "error", canal=canal, 
                                     respuesta=error_msg, estado="error")
                    return (False, error_msg, False)
            
            session.is_logged_in = True
            session.update_activity()
            print(f"[INFO] Login exitoso para {username}")
            return (True, "", True)
            
        except Exception as e:
            error_msg = f"⚠️ Error al hacer login: {e}"
            registrar_peticion(db, usuario.id, texto, "error", canal=canal, 
                             respuesta=error_msg, estado="error")
            return (False, error_msg, False)
    
    return (True, "", True)


# ============================================================================
# MANEJO DE INFORMACIÓN INCOMPLETA
# ============================================================================

def manejar_info_incompleta(texto: str, estado: dict, user_id: str, session, 
                           contexto: dict, db: Session, usuario, canal: str) -> str:
    """
    Maneja comandos con información incompleta
    
    Returns:
        respuesta para el usuario
    """
    texto_lower = texto.lower().strip()
    palabras_cancelar = ['cancelar', 'cancel', 'nada', 'olvida', 'olvídalo', 
                        'equivocado', 'equivocada', 'me equivoqué', 'error', 'no quiero']
    
    if any(palabra in texto_lower for palabra in palabras_cancelar):
        conversation_state_manager.limpiar_estado(user_id)
        respuesta = "👍 Vale, no pasa nada. ¿En qué puedo ayudarte?"
        registrar_peticion(db, usuario.id, texto, "info_incompleta_cancelada", 
                         canal=canal, respuesta=respuesta)
        session.update_activity()
        return respuesta
    
    info_parcial = estado['info_parcial']
    que_falta = estado['que_falta']
    
    # Construir comando completo
    comando_completo = None
    
    if que_falta == "proyecto":
        horas = info_parcial.get('horas')
        dia = info_parcial.get('dia', 'hoy')
        texto_limpio = texto.lower().replace('en ', '').replace('el ', '').replace('la ', '').strip()
        
        if dia in ["semana", "toda_la_semana"]:
            comando_completo = f"pon toda la semana en {texto_limpio}"
        else:
            comando_completo = f"pon {horas} horas en {texto_limpio} {dia}"
    
    elif que_falta == "horas_y_dia":
        proyecto = info_parcial.get('proyecto')
        comando_completo = f"{texto} en {proyecto}"
    
    print(f"[DEBUG] ✅ Comando completo generado: '{comando_completo}'")
    conversation_state_manager.limpiar_estado(user_id)
    
    if comando_completo:
        return ejecutar_comando_completo(comando_completo, texto, session, contexto, 
                                        db, usuario, user_id, canal)
    else:
        respuesta = "🤔 No he entendido. Por favor, inténtalo de nuevo con toda la información."
        registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=respuesta)
        session.update_activity()
        return respuesta


# ============================================================================
# EJECUCIÓN DE COMANDOS
# ============================================================================

def ejecutar_comando_completo(comando: str, texto_original: str, session, contexto: dict,
                              db: Session, usuario, user_id: str, canal: str) -> str:
    """
    Ejecuta un comando completo y retorna la respuesta
    """
    # Leer tabla actual
    tabla_actual = None
    try:
        with session.lock:
            tabla_actual = leer_tabla_imputacion(session.driver)
    except Exception as e:
        print(f"[DEBUG] ⚠️ No se pudo leer la tabla: {e}")
    
    ordenes = interpretar_con_gpt(comando, contexto, tabla_actual)
    
    if not ordenes:
        respuesta = "🤔 No he entendido qué quieres que haga."
        registrar_peticion(db, usuario.id, texto_original, "comando", canal=canal, respuesta=respuesta)
        session.update_activity()
        return respuesta
    
    # Verificar errores de validación
    if len(ordenes) == 1 and ordenes[0].get('accion') in ['error_validacion', 'info_incompleta']:
        mensaje_error = ordenes[0].get('mensaje', '🤔 No he entendido qué quieres que haga.')
        registrar_peticion(db, usuario.id, texto_original, "comando_invalido", 
                         canal=canal, respuesta=mensaje_error)
        session.update_activity()
        return mensaje_error
    
    # Ejecutar órdenes
    return ejecutar_ordenes_y_generar_respuesta(ordenes, comando, session, contexto, 
                                                db, usuario, user_id, canal)


def ejecutar_ordenes_y_generar_respuesta(ordenes: list, texto: str, session, contexto: dict,
                                         db: Session, usuario, user_id: str, canal: str) -> str:
    """
    Ejecuta una lista de órdenes y genera la respuesta final
    """
    respuestas = []
    
    for orden in ordenes:
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
        
        # Verificar si necesita desambiguación o confirmación
        if isinstance(mensaje, dict):
            resultado = manejar_respuesta_especial(mensaje, orden, ordenes, texto, session, 
                                                   db, usuario, user_id, canal)
            if resultado:
                return resultado
        
        if mensaje:
            respuestas.append(mensaje)
    
    # Generar respuesta natural
    if respuestas:
        respuesta_natural = generar_respuesta_natural(respuestas, texto, contexto)
    else:
        respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."
    
    registrar_peticion(db, usuario.id, texto, "comando", canal=canal, 
                     respuesta=respuesta_natural, acciones=ordenes)
    session.update_activity()
    return respuesta_natural


def manejar_respuesta_especial(mensaje: dict, orden: dict, ordenes: list, texto: str,
                               session, db: Session, usuario, user_id: str, canal: str) -> Optional[str]:
    """
    Maneja respuestas especiales (desambiguación, confirmación)
    
    Returns:
        mensaje para el usuario o None si no es respuesta especial
    """
    tipo = mensaje.get("tipo")
    
    # CASO 1: Desambiguación
    if tipo == "desambiguacion":
        mensaje_pregunta = generar_mensaje_desambiguacion(
            mensaje["proyecto"],
            mensaje["coincidencias"],
            canal=canal
        )
        
        conversation_state_manager.guardar_desambiguacion(
            user_id,
            mensaje["proyecto"],
            mensaje["coincidencias"],
            ordenes
        )
        
        registrar_peticion(db, usuario.id, texto, "desambiguacion_pendiente", 
                         canal=canal, respuesta=mensaje_pregunta)
        session.update_activity()
        return mensaje_pregunta
    
    # CASO 2: Confirmar proyecto existente
    elif tipo == "confirmar_existente":
        print(f"[DEBUG] 💬 Proyecto existente encontrado, solicitando confirmación")
        
        info_existente = mensaje["coincidencias"][0] if mensaje.get("coincidencias") else {}
        texto_completo = info_existente.get("texto_completo", "")
        
        if canal == "webapp":
            mensaje_confirmacion = (
                f"He encontrado **{texto_completo}** ya imputado.\n\n"
                f"¿Quieres modificar horas a este proyecto?\n\n"
                f"💡 Responde:\n"
                f"- **'sí'** para usar este proyecto\n"
                f"- **'no'** para buscar otro"
            )
        else:
            mensaje_confirmacion = (
                f"He encontrado *{texto_completo}* ya imputado.\n\n"
                f"¿Quieres modificar horas a este proyecto?\n\n"
                f"Responde 'sí' o 'no'"
            )
        
        conversation_state_manager.guardar_desambiguacion(
            user_id,
            info_existente.get("proyecto", ""),
            [{"proyecto": info_existente.get("proyecto", ""), 
              "nodo_padre": info_existente.get("nodo_padre", ""),
              "path_completo": texto_completo}],
            ordenes
        )
        
        registrar_peticion(db, usuario.id, texto, "confirmacion_pendiente", 
                         canal=canal, respuesta=mensaje_confirmacion)
        session.update_activity()
        return mensaje_confirmacion
    
    return None


# ============================================================================
# MANEJO DE DESAMBIGUACIÓN
# ============================================================================

def manejar_confirmacion_si_no(texto: str, estado: dict, session, db: Session, 
                               usuario, user_id: str, canal: str, contexto: dict) -> str:
    """
    Maneja confirmación de proyecto existente (sí/no)
    """
    texto_lower = texto.lower().strip()
    
    # Detectar "sí"
    if texto_lower in ['si', 'sí', 'sip', 'vale', 'ok', 'yes', 'y', 's', 'claro', 'dale', 'sep']:
        print(f"[DEBUG] ✅ Usuario confirmó usar el proyecto existente")
        coincidencia = estado["coincidencias"][0]
        return ejecutar_con_coincidencia(coincidencia, estado, session, db, usuario, 
                                        user_id, canal, contexto, texto)
    
    # Detectar "no"
    elif any(palabra in texto_lower for palabra in ['no', 'nop', 'nope', 'n', 'nel', 
                                                     'negativo', 'ninguno', 'otro', 'busca', 'diferente']):
        print(f"[DEBUG] ❌ Usuario rechazó el proyecto existente, buscando en sistema...")
        return buscar_en_sistema(estado, session, db, usuario, user_id, canal, contexto, texto)
    
    else:
        return "❌ No he entendido. Responde 'sí' para usar este proyecto o 'no' para buscar otro."


def ejecutar_con_coincidencia(coincidencia: dict, estado: dict, session, db: Session,
                              usuario, user_id: str, canal: str, contexto: dict, 
                              texto_original: str) -> str:
    """
    Ejecuta comando con una coincidencia específica seleccionada
    """
    print(f"[DEBUG] ✅ Coincidencia encontrada: {coincidencia['nodo_padre']}")
    
    ordenes_originales = estado["comando_original"]
    nombre_proyecto = estado["nombre_proyecto"]
    
    # Modificar orden con proyecto específico
    for orden in ordenes_originales:
        if orden.get("accion") == "seleccionar_proyecto":
            proyecto_especifico = coincidencia["proyecto"]
            orden["parametros"]["nombre"] = proyecto_especifico
            orden["parametros"]["nodo_padre"] = coincidencia["nodo_padre"]
            print(f"[DEBUG] ✅ Proyecto actualizado: '{proyecto_especifico}' bajo '{coincidencia['nodo_padre']}'")
            break
    
    # Ejecutar órdenes
    respuestas = []
    for orden in ordenes_originales:
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
            
            if isinstance(mensaje, dict):
                conversation_state_manager.limpiar_estado(user_id)
                return "❌ Algo salió mal al seleccionar el proyecto. Inténtalo de nuevo."
            
            if mensaje:
                respuestas.append(mensaje)
    
    conversation_state_manager.limpiar_estado(user_id)
    
    if respuestas:
        respuesta_natural = generar_respuesta_natural(respuestas, f"Pon horas en {nombre_proyecto}", contexto)
    else:
        respuesta_natural = "✅ Listo"
    
    registrar_peticion(db, usuario.id, texto_original, "comando_desambiguado", 
                     canal=canal, respuesta=respuesta_natural)
    session.update_activity()
    return respuesta_natural


def buscar_en_sistema(estado: dict, session, db: Session, usuario, user_id: str,
                     canal: str, contexto: dict, texto_original: str) -> str:
    """
    Busca el proyecto en el sistema cuando el usuario rechaza el existente
    """
    ordenes_originales = estado["comando_original"]
    nombre_proyecto = estado["nombre_proyecto"]
    
    # Modificar orden para buscar en sistema
    for orden in ordenes_originales:
        if orden.get("accion") == "seleccionar_proyecto":
            orden["parametros"]["nodo_padre"] = "__buscar__"
            break
    
    # Re-ejecutar
    respuestas = []
    for orden in ordenes_originales:
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
            
            if isinstance(mensaje, dict) and mensaje.get("tipo") == "desambiguacion":
                mensaje_pregunta = generar_mensaje_desambiguacion(
                    mensaje["proyecto"],
                    mensaje["coincidencias"],
                    canal=canal
                )
                
                conversation_state_manager.limpiar_estado(user_id)
                conversation_state_manager.guardar_desambiguacion(
                    user_id,
                    mensaje["proyecto"],
                    mensaje["coincidencias"],
                    ordenes_originales
                )
                
                registrar_peticion(db, usuario.id, texto_original, "desambiguacion_pendiente", 
                                 canal=canal, respuesta=mensaje_pregunta)
                session.update_activity()
                return mensaje_pregunta
            
            if mensaje:
                respuestas.append(mensaje)
    
    conversation_state_manager.limpiar_estado(user_id)
    
    if respuestas:
        respuesta_natural = generar_respuesta_natural(respuestas, f"Pon horas en {nombre_proyecto}", contexto)
    else:
        respuesta_natural = "✅ Listo"
    
    registrar_peticion(db, usuario.id, texto_original, "comando_confirmado", 
                     canal=canal, respuesta=respuesta_natural)
    session.update_activity()
    return respuesta_natural


def manejar_desambiguacion_multiple(texto: str, estado: dict, session, db: Session,
                                   usuario, user_id: str, canal: str, contexto: dict) -> str:
    """
    Maneja desambiguación con múltiples opciones
    """
    coincidencia = resolver_respuesta_desambiguacion(texto, estado["coincidencias"])
    
    if coincidencia:
        return ejecutar_con_coincidencia(coincidencia, estado, session, db, usuario, 
                                        user_id, canal, contexto, texto)
    else:
        return "❌ No he entendido tu respuesta. Por favor, indica el número (1, 2, 3...), el nombre del departamento/área o escribe cancela."
