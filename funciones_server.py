"""
Funciones auxiliares para server.py
Centraliza toda la lógica de manejo de desambiguación, login, credenciales y ejecución
"""

from typing import Tuple, Optional, Dict, List
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
# UTILIDADES
# ============================================================================

def detectar_tipo_accion(ordenes: List[dict], indice_actual: int) -> str:
    """
    Detecta el tipo de acción principal que se va a realizar.
    Busca en las órdenes siguientes para determinar si es eliminación, imputación, etc.
    
    Returns:
        'eliminar' | 'imputar' | 'modificar' | 'otro'
    """
    for idx in range(indice_actual, len(ordenes)):
        accion = ordenes[idx].get("accion", "")
        if accion == "eliminar_linea":
            return "eliminar"
        elif accion in ["imputar_horas_dia", "imputar_horas_semana"]:
            return "imputar"
        elif accion == "borrar_todas_horas_dia":
            return "borrar_horas"
    return "modificar"


def generar_mensaje_confirmacion_proyecto(texto_completo: str, tipo_accion: str, canal: str) -> str:
    """
    Genera el mensaje de confirmación según el tipo de acción.
    
    Args:
        texto_completo: Nombre completo del proyecto (ej: "Arelance - Dpto - Eventos")
        tipo_accion: 'eliminar' | 'imputar' | 'borrar_horas' | 'modificar'
        canal: 'webapp' | 'whatsapp' | 'slack'
    
    Returns:
        Mensaje de confirmación personalizado
    """
    # Determinar la pregunta según el tipo de acción
    if tipo_accion == "eliminar":
        pregunta = "¿Quieres eliminar este proyecto?"
        emoji_accion = "🗑️"
    elif tipo_accion == "borrar_horas":
        pregunta = "¿Quieres borrar las horas de este proyecto?"
        emoji_accion = "🧹"
    elif tipo_accion == "imputar":
        pregunta = "¿Quieres imputar horas a este proyecto?"
        emoji_accion = "⏱️"
    else:
        pregunta = "¿Quieres usar este proyecto?"
        emoji_accion = "📝"
    
    if canal == "webapp":
        return (
            f"{emoji_accion} He encontrado **{texto_completo}** ya imputado.\n\n"
            f"{pregunta}\n\n"
            f"💡 Responde:\n"
            f"- **'sí'** para continuar\n"
            f"- **'no'** para buscar otro proyecto"
        )
    else:
        # WhatsApp / Slack
        return (
            f"{emoji_accion} He encontrado *{texto_completo}* ya imputado.\n\n"
            f"{pregunta}\n\n"
            f"Responde 'sí' o 'no'"
        )


def manejar_pregunta_modificacion(mensaje_dict: dict, texto: str, user_id: str, 
                                  db: Session, usuario, canal: str, session) -> str:
    """
    Genera el mensaje de pregunta al usuario sobre qué proyecto modificar
    
    Args:
        mensaje_dict: Dict con tipo="pregunta_modificacion" y los proyectos
        texto: Texto original del usuario
        user_id: ID del usuario
        db: Sesión de base de datos
        usuario: Objeto Usuario
        canal: Canal de comunicación
        session: BrowserSession
        
    Returns:
        Mensaje formateado para el usuario
    """
    proyectos = mensaje_dict["proyectos"]
    dia = mensaje_dict["dia"]
    horas = mensaje_dict["horas"]
    modo = mensaje_dict["modo"]
    fecha = mensaje_dict["fecha"]
    
    # Determinar texto de acción
    if horas < 0:
        accion_texto = f"quitar {abs(horas)}h"
        emoji = "➖"
    elif modo == "establecer":
        accion_texto = f"establecer en {horas}h"
        emoji = "🎯"
    else:
        accion_texto = f"añadir {horas}h"
        emoji = "➕"
    
    # Construir mensaje
    num_proyectos = len(proyectos)
    
    if canal == "webapp":
        mensaje = f"📊 Tienes **{num_proyectos} proyecto{'s' if num_proyectos > 1 else ''}** el {dia}:\n\n"
        
        for i, proyecto in enumerate(proyectos, 1):
            mensaje += f"  **{i}.** {proyecto['nombre']}: **{proyecto['horas']}h**\n"
        
        mensaje += f"\n{emoji} ¿A cuál quieres {accion_texto}?\n\n"
        mensaje += "💡 Responde con:\n"
        mensaje += "- El **número** (1, 2, 3...)\n"
        mensaje += "- El **nombre del proyecto**\n"
        mensaje += "- **'cancelar'** para salir"
    else:
        # WhatsApp / Slack
        mensaje = f"📊 Tienes *{num_proyectos} proyecto{'s' if num_proyectos > 1 else ''}* el {dia}:\n\n"
        
        for i, proyecto in enumerate(proyectos, 1):
            mensaje += f"  *{i}.* {proyecto['nombre']}: *{proyecto['horas']}h*\n"
        
        mensaje += f"\n{emoji} ¿A cuál quieres {accion_texto}?\n\n"
        mensaje += "Responde con el número (1, 2...) o el nombre"
    
    # 🆕 Guardar estado en conversation_state_manager
    conversation_state_manager.guardar_info_incompleta(
        user_id,
        {
            "proyectos": proyectos,
            "fecha": fecha,
            "dia": dia,
            "horas": horas,
            "modo": modo
        },
        "seleccion_proyecto_modificacion"
    )
    
    registrar_peticion(db, usuario.id, texto, "pregunta_modificacion", 
                      canal=canal, respuesta=mensaje)
    session.update_activity()
    
    return mensaje


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
    Maneja el proceso de cambio de credenciales.
    
    FLUJO (igual que primera vez):
    1. Extraer credenciales del texto
    2. Hacer login para verificar
    3. Si login OK → guardar credenciales
    4. Si login falla → pedir de nuevo
    
    Returns:
        (completado: bool, mensaje: str, debe_continuar: bool)
    """
    from browser_pool import browser_pool
    
    # Procesar credenciales (extrae y valida formato)
    necesita_login, mensaje, credenciales = credential_manager.procesar_nueva_credencial(
        db, user_id, texto, canal=canal
    )
    
    # Si no necesita login (cancelación o error de formato)
    if not necesita_login:
        registrar_peticion(db, usuario.id, texto, "cambio_credenciales", canal=canal, respuesta=mensaje)
        return (False, mensaje, False)
    
    # Credenciales extraídas OK → hacer login para verificar
    username = credenciales["username"]
    password = credenciales["password"]
    
    print(f"[INFO] Verificando nuevas credenciales para {user_id}: {username}")
    
    # Obtener sesión del navegador
    session = browser_pool.get_session(user_id)
    if not session or not session.driver:
        respuesta = "⚠️ No he podido iniciar el navegador. Intenta de nuevo."
        registrar_peticion(db, usuario.id, texto, "cambio_credenciales", canal=canal, respuesta=respuesta)
        return (False, respuesta, False)
    
    # Hacer login con las nuevas credenciales
    try:
        success, mensaje_login = hacer_login_con_lock(session, username, password)
        
        if success:
            # Login OK → guardar credenciales
            session.is_logged_in = True
            ok, mensaje_guardado = credential_manager.guardar_credenciales(
                db, user_id, username, password, canal=canal
            )
            registrar_peticion(db, usuario.id, texto, "cambio_credenciales", 
                             canal=canal, respuesta=mensaje_guardado)
            return (True, mensaje_guardado, False)
        else:
            # Login falló → pedir de nuevo
            respuesta = (
                "❌ *Error de login*: Las credenciales no son correctas.\n\n"
                "📝 *Envíamelas de nuevo:*\n"
                "```\n"
                "Usuario: tu_usuario  Contraseña: tu_contraseña\n"
                "```\n\n"
                "💡 También puedes escribir:\n"
                "_pablo.solis y contraseña MiClave123_\n\n"
                "⚠️ Escribe *'cancelar'* para salir."
            )
            registrar_peticion(db, usuario.id, texto, "cambio_credenciales", 
                             canal=canal, respuesta=respuesta, estado="credenciales_invalidas")
            return (False, respuesta, False)
    
    except Exception as e:
        respuesta = f"⚠️ Error al verificar credenciales: {e}"
        registrar_peticion(db, usuario.id, texto, "cambio_credenciales", 
                         canal=canal, respuesta=respuesta, estado="error")
        return (False, respuesta, False)


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
                        "Usuario: tu_usuario  Contraseña: tu_contraseña (todo sin tabular)\n"
                        
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
    
    # 🆕 Manejar selección de proyecto por número o nombre
    elif que_falta == "seleccion_proyecto":
        proyectos = estado.get('proyectos', [])
        horas = info_parcial.get('horas', 0)
        dia = info_parcial.get('dia', 'hoy')
        
        # Intentar interpretar como número
        try:
            numero = int(texto_lower.strip())
            if 1 <= numero <= len(proyectos):
                proyecto_seleccionado = proyectos[numero - 1]
                nombre_proyecto = proyecto_seleccionado['nombre']
                
                # Construir comando con horas (pueden ser negativas para quitar)
                if horas < 0:
                    comando_completo = f"quita {abs(horas)} horas de {nombre_proyecto}"
                else:
                    comando_completo = f"pon {horas} horas en {nombre_proyecto}"
            else:
                conversation_state_manager.limpiar_estado(user_id)
                respuesta = f"❌ El número debe estar entre 1 y {len(proyectos)}."
                registrar_peticion(db, usuario.id, texto, "seleccion_invalida", 
                                 canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta
        except ValueError:
            # No es número, buscar por nombre
            texto_busqueda = texto_lower.strip()
            proyecto_encontrado = None
            
            for p in proyectos:
                if texto_busqueda in p['nombre'].lower():
                    proyecto_encontrado = p
                    break
            
            if proyecto_encontrado:
                nombre_proyecto = proyecto_encontrado['nombre']
                if horas < 0:
                    comando_completo = f"quita {abs(horas)} horas de {nombre_proyecto}"
                else:
                    comando_completo = f"pon {horas} horas en {nombre_proyecto}"
            else:
                conversation_state_manager.limpiar_estado(user_id)
                respuesta = "❌ No he encontrado ese proyecto. Indica el número o el nombre exacto."
                registrar_peticion(db, usuario.id, texto, "proyecto_no_encontrado", 
                                 canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta
    
    # 🆕 Manejar selección de proyecto para modificar horas
    elif que_falta == "seleccion_proyecto_modificacion":
        proyectos = info_parcial.get('proyectos', [])
        horas = info_parcial.get('horas', 0)
        modo = info_parcial.get('modo', 'sumar')
        fecha = info_parcial.get('fecha')
        dia = info_parcial.get('dia', 'hoy')
        
        # Intentar interpretar como número
        proyecto_seleccionado = None
        
        try:
            numero = int(texto_lower.strip())
            if 1 <= numero <= len(proyectos):
                proyecto_seleccionado = proyectos[numero - 1]
        except:
            # No es número, buscar por nombre
            for proyecto in proyectos:
                if texto_lower in proyecto['nombre'].lower():
                    proyecto_seleccionado = proyecto
                    break
        
        if not proyecto_seleccionado:
            conversation_state_manager.limpiar_estado(user_id)
            respuesta = f"❌ No he encontrado ese proyecto. Por favor, responde con el número (1-{len(proyectos)}) o el nombre exacto."
            registrar_peticion(db, usuario.id, texto, "seleccion_invalida", 
                             canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta
        
        # Proyecto seleccionado → construir comando completo
        nombre_proyecto = proyecto_seleccionado['nombre']
        
        # Determinar si es "quitar", "sumar" o "establecer"
        if horas < 0:
            comando_completo = f"quita {abs(horas)} horas de {nombre_proyecto} el {dia}"
        elif modo == "establecer":
            comando_completo = f"establece {nombre_proyecto} a {horas} horas el {dia}"
        else:
            comando_completo = f"suma {horas} horas a {nombre_proyecto} el {dia}"
    
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
                                                db, usuario, user_id, canal,
                                                texto_original=texto_original)


def ejecutar_ordenes_y_generar_respuesta(ordenes: list, texto: str, session, contexto: dict,
                                         db: Session, usuario, user_id: str, canal: str,
                                         texto_original: str = None) -> str:
    """
    Ejecuta una lista de órdenes y genera la respuesta final
    
    Args:
        texto_original: Texto original del usuario (si es diferente a texto). 
                       Si no se proporciona, se usa texto.
    """
    # Si no se proporciona texto_original, usar texto
    if texto_original is None:
        texto_original = texto
    
    respuestas = []
    
    # Pre-procesar: detectar si es "borrar horas de proyecto específico"
    # (seleccionar_proyecto seguido de imputar_horas_dia con horas=0 y modo=establecer)
    for i, orden in enumerate(ordenes):
        if orden.get("accion") == "seleccionar_proyecto":
            if i + 1 < len(ordenes):
                siguiente = ordenes[i + 1]
                if siguiente.get("accion") == "imputar_horas_dia":
                    horas = siguiente.get("parametros", {}).get("horas", 0)
                    modo = siguiente.get("parametros", {}).get("modo", "sumar")
                    if horas == 0 and modo == "establecer":
                        contexto["es_borrado_horas"] = True
                        print(f"[DEBUG] 🧹 Detectado: seleccionar_proyecto + imputar(0, establecer) → modo borrar horas")
                        break
    
    for idx, orden in enumerate(ordenes):
        # Limpiar flag después de usarlo
        if orden.get("accion") == "imputar_horas_dia":
            contexto["es_borrado_horas"] = False
        
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
        
        # Verificar si necesita desambiguación o confirmación
        if isinstance(mensaje, dict):
            resultado = manejar_respuesta_especial(mensaje, orden, ordenes, texto, texto_original, session, 
                                                   db, usuario, user_id, canal, idx, respuestas)
            if resultado:
                return resultado
        
        if mensaje:
            respuestas.append(mensaje)
    
    # Generar respuesta natural
    if respuestas:
        respuesta_natural = generar_respuesta_natural(respuestas, texto_original, contexto)
    else:
        respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."
    
    registrar_peticion(db, usuario.id, texto_original, "comando", canal=canal, 
                     respuesta=respuesta_natural, acciones=ordenes)
    session.update_activity()
    return respuesta_natural


def manejar_respuesta_especial(mensaje: dict, orden: dict, ordenes: list, texto: str, texto_original: str,
                               session, db: Session, usuario, user_id: str, canal: str, 
                               indice_orden: int = 0, respuestas_acumuladas: list = None) -> Optional[str]:
    """
    Maneja respuestas especiales (desambiguación, pregunta_modificacion, error)
    
    Args:
        indice_orden: Índice de la orden actual en la lista (para continuar después)
        respuestas_acumuladas: Lista de respuestas ya generadas antes de la desambiguación
    
    Returns:
        mensaje para el usuario o None si no es respuesta especial
    """
    tipo = mensaje.get("tipo")
    
    if respuestas_acumuladas is None:
        respuestas_acumuladas = []
    
    # 🆕 Pregunta de modificación de horas
    if tipo == "pregunta_modificacion":
        return manejar_pregunta_modificacion(mensaje, texto_original, user_id, 
                                            db, usuario, canal, session)
    
    # ❌ Error
    elif tipo == "error":
        respuesta_final = mensaje.get("mensaje", "❌ Ha ocurrido un error")
        registrar_peticion(db, usuario.id, texto_original, "error", 
                         canal=canal, respuesta=respuesta_final)
        session.update_activity()
        return respuesta_final
    
    # Desambiguación
    elif tipo == "desambiguacion":
        # Detectar tipo de acción para personalizar el mensaje
        tipo_accion = detectar_tipo_accion(ordenes, indice_orden)
        
        mensaje_pregunta = generar_mensaje_desambiguacion(
            mensaje["proyecto"],
            mensaje["coincidencias"],
            canal=canal,
            tipo_accion=tipo_accion
        )
        
        conversation_state_manager.guardar_desambiguacion(
            user_id,
            mensaje["proyecto"],
            mensaje["coincidencias"],
            ordenes,
            indice_orden,
            respuestas_acumuladas=respuestas_acumuladas,  # 🆕 Pasar respuestas acumuladas
            texto_original=texto_original  # 🆕 Pasar texto original
        )
        
        registrar_peticion(db, usuario.id, texto, "desambiguacion_pendiente", 
                         canal=canal, respuesta=mensaje_pregunta)
        session.update_activity()
        return mensaje_pregunta
    
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
        print(f"[DEBUG] ❌ Usuario rechazó el proyecto existente")
        
        # 🔥 LIMPIAR EL ESTADO - el usuario canceló la confirmación
        conversation_state_manager.limpiar_estado(user_id)
        
        # 🔥 Responder que debe volver a intentar con el comando completo
        respuesta = (
            "👍 Vale, no usaré ese proyecto.\n\n"
            "💡 Por favor, vuelve a escribir tu comando con el proyecto correcto.\n"
            "Ejemplo: *Pon 3 horas en [nombre del proyecto]*"
        )
        registrar_peticion(db, usuario.id, texto, "confirmacion_rechazada", 
                         canal=canal, respuesta=respuesta)
        session.update_activity()
        return respuesta
    
    else:
        return "❌ No he entendido. Responde 'sí' para usar este proyecto o 'no' para cancelar."


def ejecutar_con_coincidencia(coincidencia: dict, estado: dict, session, db: Session,
                              usuario, user_id: str, canal: str, contexto: dict, 
                              texto_original: str) -> str:
    """
    Ejecuta comando con una coincidencia específica seleccionada
    """
    print(f"[DEBUG] ✅ Coincidencia encontrada: {coincidencia['nodo_padre']}")
    
    ordenes_originales = estado["comando_original"]
    nombre_proyecto = estado["nombre_proyecto"]
    indice_orden = estado.get("indice_orden", 0)
    
    # 🆕 Recuperar respuestas acumuladas de desambiguaciones anteriores
    respuestas_previas = estado.get("respuestas_acumuladas", [])
    
    # 🆕 Recuperar texto original del comando completo
    texto_comando_original = estado.get("texto_original", f"Pon horas en {nombre_proyecto}")
    
    # Modificar la orden que causó desambiguación con proyecto específico
    if indice_orden < len(ordenes_originales):
        orden = ordenes_originales[indice_orden]
        if orden.get("accion") == "seleccionar_proyecto":
            proyecto_especifico = coincidencia["proyecto"]
            orden["parametros"]["nombre"] = proyecto_especifico
            orden["parametros"]["nodo_padre"] = coincidencia["nodo_padre"]
            print(f"[DEBUG] ✅ Proyecto actualizado: '{proyecto_especifico}' bajo '{coincidencia['nodo_padre']}'")
    
    # Ejecutar solo desde el índice que falló en adelante
    respuestas = list(respuestas_previas)  # 🆕 Empezar con las respuestas previas
    
    # Pre-procesar: detectar si es "borrar horas de proyecto específico"
    for i, orden in enumerate(ordenes_originales):
        if orden.get("accion") == "seleccionar_proyecto":
            if i + 1 < len(ordenes_originales):
                siguiente = ordenes_originales[i + 1]
                if siguiente.get("accion") == "imputar_horas_dia":
                    horas = siguiente.get("parametros", {}).get("horas", 0)
                    modo = siguiente.get("parametros", {}).get("modo", "sumar")
                    if horas == 0 and modo == "establecer":
                        contexto["es_borrado_horas"] = True
                        print(f"[DEBUG] 🧹 Detectado en desambiguación: modo borrar horas")
                        break
    
    print(f"[DEBUG] 🔁 Ejecutando órdenes desde índice {indice_orden} hasta {len(ordenes_originales)-1}")
    print(f"[DEBUG] 🔁 Respuestas previas acumuladas: {len(respuestas_previas)}")
    
    for idx in range(indice_orden, len(ordenes_originales)):
        orden = ordenes_originales[idx]
        print(f"[DEBUG] 🔁 Ejecutando orden {idx}: {orden.get('accion')}")
        
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
            print(f"[DEBUG] 🔁 Resultado: {type(mensaje).__name__} - {str(mensaje)[:100] if not isinstance(mensaje, dict) else 'dict'}")
            
            # Si devuelve dict, es desambiguación - mantener el flujo
            if isinstance(mensaje, dict):
                tipo_msg = mensaje.get("tipo")
                
                if tipo_msg == "desambiguacion":
                    print(f"[DEBUG] 🔄 Necesita desambiguación adicional, actualizando estado...")
                    
                    # Detectar tipo de acción para personalizar el mensaje
                    tipo_accion = detectar_tipo_accion(ordenes_originales, idx)
                    
                    mensaje_pregunta = generar_mensaje_desambiguacion(
                        mensaje["proyecto"],
                        mensaje["coincidencias"],
                        canal=canal,
                        tipo_accion=tipo_accion
                    )
                    
                    conversation_state_manager.limpiar_estado(user_id)
                    conversation_state_manager.guardar_desambiguacion(
                        user_id,
                        mensaje["proyecto"],
                        mensaje["coincidencias"],
                        ordenes_originales,
                        idx,
                        respuestas_acumuladas=respuestas,  # 🆕 Pasar respuestas acumuladas
                        texto_original=texto_comando_original  # 🆕 Pasar texto original
                    )
                    
                    registrar_peticion(db, usuario.id, texto_original, "desambiguacion_pendiente", 
                                     canal=canal, respuesta=mensaje_pregunta)
                    session.update_activity()
                    return mensaje_pregunta
                
                else:
                    conversation_state_manager.limpiar_estado(user_id)
                    return "❌ Algo salió mal al seleccionar el proyecto. Inténtalo de nuevo."
            
            if mensaje:
                respuestas.append(mensaje)
    
    conversation_state_manager.limpiar_estado(user_id)
    
    if respuestas:
        # 🆕 Usar el texto original completo para generar la respuesta
        respuesta_natural = generar_respuesta_natural(respuestas, texto_comando_original, contexto)
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
    indice_orden = estado.get("indice_orden", 0)
    
    # 🆕 Recuperar respuestas y texto original
    respuestas_previas = estado.get("respuestas_acumuladas", [])
    texto_comando_original = estado.get("texto_original", f"Pon horas en {nombre_proyecto}")
    
    # Modificar la orden que causó desambiguación para buscar en sistema
    if indice_orden < len(ordenes_originales):
        orden = ordenes_originales[indice_orden]
        if orden.get("accion") == "seleccionar_proyecto":
            orden["parametros"]["nodo_padre"] = "__buscar__"
    
    # Re-ejecutar solo desde el índice que falló
    respuestas = list(respuestas_previas)  # 🆕 Empezar con respuestas previas
    
    for idx in range(indice_orden, len(ordenes_originales)):
        orden = ordenes_originales[idx]
        
        with session.lock:
            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
            
            # Manejar desambiguación
            if isinstance(mensaje, dict):
                tipo_msg = mensaje.get("tipo")
                
                if tipo_msg == "desambiguacion":
                    # Detectar tipo de acción para personalizar el mensaje
                    tipo_accion = detectar_tipo_accion(ordenes_originales, idx)
                    
                    mensaje_pregunta = generar_mensaje_desambiguacion(
                        mensaje["proyecto"],
                        mensaje["coincidencias"],
                        canal=canal,
                        tipo_accion=tipo_accion
                    )
                    
                    conversation_state_manager.limpiar_estado(user_id)
                    conversation_state_manager.guardar_desambiguacion(
                        user_id,
                        mensaje["proyecto"],
                        mensaje["coincidencias"],
                        ordenes_originales,
                        idx,
                        respuestas_acumuladas=respuestas,  # 🆕 Pasar respuestas
                        texto_original=texto_comando_original  # 🆕 Pasar texto original
                    )
                    
                    registrar_peticion(db, usuario.id, texto_original, "desambiguacion_pendiente", 
                                     canal=canal, respuesta=mensaje_pregunta)
                    session.update_activity()
                    return mensaje_pregunta
            
            if mensaje:
                respuestas.append(mensaje)
    
    conversation_state_manager.limpiar_estado(user_id)
    
    if respuestas:
        respuesta_natural = generar_respuesta_natural(respuestas, texto_comando_original, contexto)
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
    texto_lower = texto.lower().strip()
    
    # 🆕 Detectar CANCELACIÓN
    palabras_cancelar = ['cancelar', 'cancel', 'nada', 'olvida', 'olvídalo', 'olvidalo',
                        'equivocado', 'equivocada', 'me equivoqué', 'me equivoque',
                        'error', 'no quiero', 'déjalo', 'dejalo', 'salir', 'sal']
    
    if any(palabra in texto_lower for palabra in palabras_cancelar):
        print(f"[DEBUG] 🚫 Usuario canceló la desambiguación")
        conversation_state_manager.limpiar_estado(user_id)
        respuesta = "👍 Vale, no pasa nada. ¿En qué puedo ayudarte?"
        registrar_peticion(db, usuario.id, texto, "cancelacion_desambiguacion", 
                         canal=canal, respuesta=respuesta)
        session.update_activity()
        return respuesta
    
    # 🆕 Detectar BÚSQUEDA DE OTRO PROYECTO (ninguno/otro)
    palabras_otro = ['ninguno', 'ninguna', 'otro', 'otra', 'diferente', 'busca', 
                     'buscar', 'otro proyecto', 'uno diferente', 'distinto']
    
    if any(palabra in texto_lower for palabra in palabras_otro):
        print(f"[DEBUG] 🔄 Usuario quiere buscar otro proyecto diferente")
        
        # Obtener información del estado
        son_existentes = estado.get("coincidencias", [{}])[0].get('total_horas') is not None
        
        if son_existentes:
            # Si son proyectos existentes, buscar en el sistema
            print(f"[DEBUG] 📂 Proyectos existentes rechazados, buscando en sistema...")
            return buscar_en_sistema(estado, session, db, usuario, user_id, canal, contexto, texto)
        else:
            # Si son del sistema, es ambiguo - no hay "otro"
            conversation_state_manager.limpiar_estado(user_id)
            nombre_proyecto = estado.get("nombre_proyecto", "ese proyecto")
            respuesta = (
                f"🤔 No hay más proyectos llamados '{nombre_proyecto}' en el sistema.\n\n"
                f"Si ninguno de estos es el correcto, verifica el nombre exacto del proyecto "
                f"que buscas."
            )
            registrar_peticion(db, usuario.id, texto, "desambiguacion_no_hay_otro", 
                             canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta
    
    # Intentar resolver normalmente
    coincidencia = resolver_respuesta_desambiguacion(texto, estado["coincidencias"])
    
    if coincidencia:
        return ejecutar_con_coincidencia(coincidencia, estado, session, db, usuario, 
                                        user_id, canal, contexto, texto)
    else:
        return "❌ No he entendido tu respuesta. Por favor:\n• Indica el **número** (1, 2, 3...)\n• El **nombre del departamento/área**\n• Escribe **'otro'** si ninguno es el correcto\n• Escribe **'cancelar'** para salir"
