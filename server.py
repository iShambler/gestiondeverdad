import os
import re  # 🆕 Para expresiones regulares
from dotenv import load_dotenv  
import requests
from fastapi import FastAPI, Request, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
import time
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 🧩 Importa todas las funciones necesarias desde los módulos refactorizados
from ai import (
    clasificar_mensaje,
    interpretar_con_gpt,
    responder_conversacion,
    interpretar_consulta,
    generar_respuesta_natural,
    generar_resumen_natural
)

from core import (
    ejecutar_accion,
    consultar_dia,
    consultar_semana,
    mostrar_comandos
)

from web_automation import hacer_login

# Importar funciones de base de datos y autenticación
from db import get_db, registrar_peticion
from auth_handler import (
    verificar_y_solicitar_credenciales,
    obtener_credenciales
)

# 🆕 Importar el pool de navegadores
from browser_pool import browser_pool

# 🚀 Inicialización de la app FastAPI
app = FastAPI()

# 🔥 ThreadPoolExecutor para operaciones bloqueantes de Selenium
# ⚠️ Ajustar según tu hardware:
# - 50 workers = 50 usuarios simultáneos (requiere ~5GB RAM)
# - 100 workers = 100 usuarios simultáneos (requiere ~10GB RAM)
# - 200 workers = 200 usuarios simultáneos (requiere ~20GB RAM)
executor = ThreadPoolExecutor(max_workers=50)  # 👉 CAMBIAR AQUÍ para más usuarios

# 🌐 Habilitar CORS (para tu frontend o Slack)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔐 Config Slack
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_API_URL = "https://slack.com/api/chat.postMessage"


# -------------------------------------------------------------------
# 🔧 FUNCIONES AUXILIARES
# -------------------------------------------------------------------
def procesar_mensaje_usuario_sync(texto: str, user_id: str, db: Session, canal: str = "webapp"):
    """
    Lógica común para procesar mensajes de usuarios (webapp o slack).
    Usa el pool de navegadores para obtener una sesión individual por usuario.
    
    ⚠️ Esta función es SÍNCRONA y debe ejecutarse en un thread separado
    
    Returns:
        str: Respuesta para el usuario
    """
    from credential_manager import credential_manager
    
    # 🔐 Verificar autenticación
    usuario, mensaje_auth = verificar_y_solicitar_credenciales(db, user_id, canal=canal)
    
    # 🔄 Si está cambiando credenciales (por error de login)
    if credential_manager.esta_cambiando_credenciales(user_id):
        # Manejar cancelación
        if texto.lower().strip() in ['cancelar', 'cancel', 'no']:
            credential_manager.finalizar_cambio(user_id)
            respuesta = "❌ Cambio de credenciales cancelado. Si necesitas ayuda, contacta con soporte."
            registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=respuesta)
            return respuesta
        
        completado, mensaje = credential_manager.procesar_nueva_credencial(db, user_id, texto, canal=canal)
        registrar_peticion(db, usuario.id, texto, "cambio_credenciales", canal=canal, respuesta=mensaje)
        
        # Si completó el cambio, cerrar la sesión del navegador para forzar nuevo login
        if completado:
            session = browser_pool.get_session(user_id)
            if session:
                session.is_logged_in = False
        
        return mensaje
    
    # Si necesita proporcionar credenciales por primera vez
    if mensaje_auth:
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=mensaje_auth)
        return mensaje_auth
    
    # 🌐 Obtener sesión de navegador para este usuario
    session = browser_pool.get_session(user_id)
    
    if not session or not session.driver:
        error_msg = "⚠️ No he podido iniciar el navegador. Intenta de nuevo en unos momentos."
        registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=error_msg, estado="error")
        return error_msg
    
    # 🎯 Asegurar que hay login activo con las credenciales del usuario
    username, password = obtener_credenciales(db, user_id, canal=canal)
    
    if username and password:
        # Si no está logueado, hacer login
        if not session.is_logged_in:
            print(f"[INFO] Haciendo login para usuario: {username} ({user_id})")
            try:
                from credential_manager import credential_manager
                
                # 🔒 LOCK SOLO PARA LOGIN - operación crítica
                with session.lock:
                    success, mensaje_login = hacer_login(session.driver, session.wait, username, password)
                    
                    if not success:
                        # ❌ Login fallido
                        if "credenciales_invalidas" in mensaje_login:
                            # Iniciar proceso de cambio de credenciales
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
                            registrar_peticion(db, usuario.id, texto, "error_login", canal=canal, respuesta=error_msg, estado="credenciales_invalidas")
                            return error_msg
                        else:
                            error_msg = f"⚠️ Error técnico al hacer login: {mensaje_login}"
                            registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=error_msg, estado="error")
                            return error_msg
                    
                    # ✅ Login exitoso
                    session.is_logged_in = True
                    session.update_activity()
                print(f"[INFO] Login exitoso para {username}")
            except Exception as e:
                error_msg = f"⚠️ Error al hacer login: {e}"
                registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=error_msg, estado="error")
                return error_msg

    try:
        # 🆕 PASO 1: Verificar si hay pregunta pendiente de desambiguación
        from conversation_state import conversation_state_manager
        
        # Obtener contexto de la sesión (necesario para ejecutar acciones)
        contexto = session.contexto
        contexto["user_id"] = user_id  # 🆕 Añadir user_id para guardar último proyecto
        
        if conversation_state_manager.tiene_pregunta_pendiente(user_id):
            print(f"[DEBUG] 💬 Usuario {user_id} tiene pregunta pendiente")
            estado = conversation_state_manager.obtener_desambiguacion(user_id)
            
            # 🆕 VERIFICAR TIPO DE ESTADO
            if estado and estado.get("tipo") == "info_incompleta":
                # 🛡️ Detectar si el usuario quiere cancelar
                texto_lower = texto.lower().strip()
                palabras_cancelar = ['cancelar', 'cancel', 'nada', 'olvida', 'olvídalo', 'equivocado', 'equivocada', 'me equivoqué', 'error', 'no quiero']
                
                if any(palabra in texto_lower for palabra in palabras_cancelar):
                    # Limpiar estado
                    conversation_state_manager.limpiar_estado(user_id)
                    respuesta = "👍 Vale, no pasa nada. ¿En qué puedo ayudarte?"
                    registrar_peticion(db, usuario.id, texto, "info_incompleta_cancelada", canal=canal, respuesta=respuesta)
                    session.update_activity()
                    return respuesta
                
                # 💾 Usuario tiene información incompleta guardada
                print(f"[DEBUG] 💾 Info incompleta detectada")
                print(f"[DEBUG]    Info parcial: {estado['info_parcial']}")
                print(f"[DEBUG]    Falta: {estado['que_falta']}")
                
                info_parcial = estado['info_parcial']
                que_falta = estado['que_falta']
                
                # Construir comando completo combinando info guardada + mensaje actual
                comando_completo = None
                
                if que_falta == "proyecto":
                    # Usuario dijo "3 horas", ahora dice "en desarrollo" o "desarrollo"
                    horas = info_parcial.get('horas')
                    dia = info_parcial.get('dia', 'hoy')
                    
                    # Limpiar el texto para extraer solo el nombre del proyecto
                    texto_limpio = texto.lower().replace('en ', '').replace('el ', '').replace('la ', '').strip()
                    
                    if dia == "semana":
                        comando_completo = f"pon toda la semana en {texto_limpio}"
                    elif dia == "toda_la_semana":
                        comando_completo = f"pon toda la semana en {texto_limpio}"
                    else:
                        comando_completo = f"pon {horas} horas en {texto_limpio} {dia}"
                    
                    print(f"[DEBUG] ✅ Comando completo generado: '{comando_completo}'")
                
                elif que_falta == "horas_y_dia":
                    # Usuario dijo "ponme en desarrollo", ahora dice "3 horas" o "toda la semana"
                    proyecto = info_parcial.get('proyecto')
                    comando_completo = f"{texto} en {proyecto}"
                    
                    print(f"[DEBUG] ✅ Comando completo generado: '{comando_completo}'")
                
                # Limpiar estado
                conversation_state_manager.limpiar_estado(user_id)
                
                if comando_completo:
                    # Re-procesar el comando completo
                    print(f"[DEBUG] 🔄 Re-procesando comando completo...")
                    
                    # Leer tabla actual
                    tabla_actual = None
                    try:
                        from web_automation import leer_tabla_imputacion
                        with session.lock:
                            tabla_actual = leer_tabla_imputacion(session.driver)
                    except Exception as e:
                        print(f"[DEBUG] ⚠️ No se pudo leer la tabla: {e}")
                    
                    ordenes_completas = interpretar_con_gpt(comando_completo, contexto, tabla_actual)
                    
                    if not ordenes_completas:
                        respuesta = "🤔 No he entendido qué quieres que haga."
                        registrar_peticion(db, usuario.id, texto, "comando", canal=canal, respuesta=respuesta)
                        session.update_activity()
                        return respuesta
                    
                    # Verificar si son órdenes válidas
                    if len(ordenes_completas) == 1 and ordenes_completas[0].get('accion') in ['error_validacion', 'info_incompleta']:
                        mensaje_error = ordenes_completas[0].get('mensaje', '🤔 No he entendido qué quieres que haga.')
                        registrar_peticion(db, usuario.id, texto, "comando_invalido", canal=canal, respuesta=mensaje_error)
                        session.update_activity()
                        return mensaje_error
                    
                    # Ejecutar órdenes
                    respuestas = []
                    for orden in ordenes_completas:
                        with session.lock:
                            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                        
                        # 🆕 VERIFICAR SI NECESITA DESAMBIGUACIÓN O CONFIRMACIÓN
                        if isinstance(mensaje, dict):
                            tipo = mensaje.get("tipo")
                            
                            # CASO 1: Desambiguación
                            if tipo == "desambiguacion":
                                from web_automation.desambiguacion import generar_mensaje_desambiguacion
                                
                                mensaje_pregunta = generar_mensaje_desambiguacion(
                                    mensaje["proyecto"],
                                    mensaje["coincidencias"],
                                    canal=canal
                                )
                                
                                conversation_state_manager.guardar_desambiguacion(
                                    user_id,
                                    mensaje["proyecto"],
                                    mensaje["coincidencias"],
                                    ordenes_completas
                                )
                                
                                registrar_peticion(db, usuario.id, texto, "desambiguacion_pendiente", canal=canal, respuesta=mensaje_pregunta)
                                session.update_activity()
                                return mensaje_pregunta  # 🛑 DETENER EJECUCIÓN
                            
                            # CASO 2: Confirmar proyecto existente
                            elif tipo == "confirmar_existente":
                                print(f"[DEBUG] 💬 Proyecto existente encontrado (info_incompleta), solicitando confirmación")
                                
                                info_existente = mensaje["coincidencias"][0] if mensaje.get("coincidencias") else {}
                                proyecto_nombre = info_existente.get("proyecto", "")
                                nodo_padre = info_existente.get("nodo_padre", "")
                                texto_completo = info_existente.get("texto_completo", "")
                                
                                if canal == "webapp":
                                    mensaje_confirmacion = (
                                        f"✅ He encontrado **{texto_completo}** ya imputado.\n\n"
                                        f"¿Quieres añadir horas a este proyecto?\n\n"
                                        f"💡 Responde:\n"
                                        f"- **'sí'** para usar este proyecto\n"
                                        f"- **'no'** para buscar otro"
                                    )
                                else:
                                    mensaje_confirmacion = (
                                        f"✅ He encontrado *{texto_completo}* ya imputado.\n\n"
                                        f"¿Quieres añadir horas a este proyecto?\n\n"
                                        f"Responde 'sí' o 'no'"
                                    )
                                
                                conversation_state_manager.guardar_desambiguacion(
                                    user_id,
                                    proyecto_nombre,
                                    [{"proyecto": proyecto_nombre, "nodo_padre": nodo_padre, 
                                      "path_completo": texto_completo}],
                                    ordenes_completas
                                )
                                
                                registrar_peticion(db, usuario.id, texto, "confirmacion_pendiente", 
                                                 canal=canal, respuesta=mensaje_confirmacion)
                                session.update_activity()
                                return mensaje_confirmacion  # 🛑 DETENER EJECUCIÓN
                        
                        if mensaje:
                            respuestas.append(mensaje)
                    
                    # Generar respuesta
                    if respuestas:
                        respuesta_natural = generar_respuesta_natural(respuestas, comando_completo, contexto)
                    else:
                        respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."
                    
                    registrar_peticion(db, usuario.id, texto, "comando_completado", canal=canal, respuesta=respuesta_natural, acciones=ordenes_completas)
                    session.update_activity()
                    return respuesta_natural
                else:
                    # No se pudo construir comando completo
                    respuesta = "🤔 No he entendido. Por favor, inténtalo de nuevo con toda la información."
                    registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=respuesta)
                    session.update_activity()
                    return respuesta
            
            # Si no es info_incompleta, es desambiguación o confirmación
            from web_automation.desambiguacion import resolver_respuesta_desambiguacion
            
            # 🆕 Si solo hay UNA coincidencia, es confirmación (sí/no)
            if len(estado["coincidencias"]) == 1:
                texto_lower = texto.lower().strip()
                
                # Detectar "sí"
                if texto_lower in ['si', 'sí', 'sip', 'vale', 'ok', 'yes', 'y', 's', 'claro', 'dale', 'sep']:
                    print(f"[DEBUG] ✅ Usuario confirmó usar el proyecto existente")
                    coincidencia = estado["coincidencias"][0]
                
                # Detectar "no" o palabras que indican rechazo
                elif any(palabra in texto_lower for palabra in ['no', 'nop', 'nope', 'n', 'nel', 'negativo', 'ninguno', 'otro', 'busca', 'diferente']):
                    print(f"[DEBUG] ❌ Usuario rechazó el proyecto existente, buscando en sistema...")
                    # Modificar la orden para buscar en sistema con nodo_padre="__buscar__"
                    ordenes_originales = estado["comando_original"]
                    nombre_proyecto = estado["nombre_proyecto"]
                    
                    for orden in ordenes_originales:
                        if orden.get("accion") == "seleccionar_proyecto":
                            orden["parametros"]["nodo_padre"] = "__buscar__"  # Señal especial para buscar en sistema
                            break
                    
                    # Re-ejecutar buscando en sistema
                    respuestas = []
                    for orden in ordenes_originales:
                        with session.lock:
                            mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                            
                            if isinstance(mensaje, dict):
                                # Si devuelve desambiguación, manejarla
                                if mensaje.get("tipo") == "desambiguacion":
                                    from web_automation.desambiguacion import generar_mensaje_desambiguacion
                                    
                                    mensaje_pregunta = generar_mensaje_desambiguacion(
                                        mensaje["proyecto"],
                                        mensaje["coincidencias"],
                                        canal=canal
                                    )
                                    
                                    # 🆕 Limpiar estado anterior y guardar nueva desambiguación
                                    conversation_state_manager.limpiar_estado(user_id)
                                    conversation_state_manager.guardar_desambiguacion(
                                        user_id,
                                        mensaje["proyecto"],
                                        mensaje["coincidencias"],
                                        ordenes_originales
                                    )
                                    
                                    registrar_peticion(db, usuario.id, texto, "desambiguacion_pendiente", canal=canal, respuesta=mensaje_pregunta)
                                    session.update_activity()
                                    return mensaje_pregunta
                            
                            if mensaje:
                                respuestas.append(mensaje)
                    
                    # Limpiar estado
                    conversation_state_manager.limpiar_estado(user_id)
                    
                    if respuestas:
                        respuesta_natural = generar_respuesta_natural(respuestas, f"Pon horas en {nombre_proyecto}", contexto)
                    else:
                        respuesta_natural = "✅ Listo"
                    
                    registrar_peticion(db, usuario.id, texto, "comando_confirmado", canal=canal, respuesta=respuesta_natural)
                    session.update_activity()
                    return respuesta_natural
                
                else:
                    # No entendió sí/no
                    return "❌ No he entendido. Responde 'sí' para usar este proyecto o 'no' para buscar otro."
            
            # Si hay MÚLTIPLES coincidencias, usar resolución normal
            else:
                # Resolver respuesta del usuario
                coincidencia = resolver_respuesta_desambiguacion(texto, estado["coincidencias"])
            
            if coincidencia:
                print(f"[DEBUG] ✅ Coincidencia encontrada: {coincidencia['nodo_padre']}")
                
                # Re-ejecutar el comando original con el elemento preseleccionado
                ordenes_originales = estado["comando_original"]
                nombre_proyecto = estado["nombre_proyecto"]
                
                # Modificar la orden para incluir el elemento preseleccionado
                for orden in ordenes_originales:
                    if orden.get("accion") == "seleccionar_proyecto":
                        # 🆕 IMPORTANTE: Usar el nombre ESPECÍFICO del proyecto, no solo el nodo padre
                        # Extraer el nombre del proyecto del path completo
                        proyecto_especifico = coincidencia["proyecto"]  # "Permiso Retribuido Festivo"
                        
                        # Actualizar AMBOS parámetros
                        orden["parametros"]["nombre"] = proyecto_especifico  # ✅ Nombre específico
                        orden["parametros"]["nodo_padre"] = coincidencia["nodo_padre"]  # ✅ Nodo padre
                        
                        print(f"[DEBUG] ✅ Proyecto actualizado: '{proyecto_especifico}' bajo '{coincidencia['nodo_padre']}'")
                        break
                
                # Ejecutar las órdenes con el nodo padre especificado
                respuestas = []
                for orden in ordenes_originales:
                    with session.lock:
                        mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                        
                        # Si devuelve dict (desambiguación), algo salió mal
                        if isinstance(mensaje, dict):
                            conversation_state_manager.limpiar_estado(user_id)
                            return "❌ Algo salió mal al seleccionar el proyecto. Inténtalo de nuevo."
                        
                        if mensaje:
                            respuestas.append(mensaje)
                
                # Limpiar estado
                conversation_state_manager.limpiar_estado(user_id)
                
                # Generar respuesta
                if respuestas:
                    respuesta_natural = generar_respuesta_natural(respuestas, f"Pon horas en {nombre_proyecto}", contexto)
                else:
                    respuesta_natural = "✅ Listo"
                
                registrar_peticion(db, usuario.id, texto, "comando_desambiguado", canal=canal, respuesta=respuesta_natural)
                session.update_activity()
                return respuesta_natural
            else:
                # No se entendió la respuesta
                return "❌ No he entendido tu respuesta. Por favor, indica el número (1, 2, 3...) o el nombre del departamento/área."
        
        # 🔥 SIN LOCK AQUÍ - cada operación maneja su propio lock si es necesario
        tipo_mensaje = clasificar_mensaje(texto)

        # 🆕 LISTAR PROYECTOS - Mostrar todos los proyectos disponibles
        if tipo_mensaje == "listar_proyectos":
            from web_automation.listado_proyectos import listar_todos_proyectos, formatear_lista_proyectos
            
            # 🆕 Detectar si menciona un nodo específico
            filtro_nodo = None
            texto_lower = texto.lower()
            
            # Palabras clave que indican un nodo específico
            if "departamento" in texto_lower:
                # Extraer el texto después de "departamento"
                match = re.search(r'departamento\s+(\w+(?:\s+\w+)*)', texto_lower, re.IGNORECASE)
                if match:
                    filtro_nodo = match.group(0).strip()  # Incluir "departamento" completo
                    print(f"[DEBUG] 🎯 Filtro detectado: '{filtro_nodo}'")
            elif "en " in texto_lower and any(keyword in texto_lower for keyword in ["admin", "administración", "desarrollo", "staff"]):
                # Detectar patrones como "en admin-staff", "en administración"
                match = re.search(r'en\s+([\w-]+(?:\s+[\w-]+)*)', texto_lower, re.IGNORECASE)
                if match:
                    filtro_nodo = match.group(1).strip()
                    print(f"[DEBUG] 🎯 Filtro detectado: '{filtro_nodo}'")
            
            with session.lock:
                proyectos_por_nodo = listar_todos_proyectos(session.driver, session.wait, filtro_nodo)
            
            respuesta = formatear_lista_proyectos(proyectos_por_nodo, canal=canal)
            registrar_peticion(db, usuario.id, texto, "listar_proyectos", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # 🖊️ Comando de ayuda - Mostrar lista de comandos
        if tipo_mensaje == "ayuda":
            respuesta = mostrar_comandos()
            registrar_peticion(db, usuario.id, texto, "ayuda", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # 🗣️ Conversación natural (saludos o charla)
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)
            registrar_peticion(db, usuario.id, texto, "conversacion", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # 📊 Consultas (resumen semanal o diario)
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            
            # 🔍 DEBUG: Ver qué interpretó GPT
            print(f"[DEBUG] 📊 Consulta interpretada: {consulta_info}")
            
            if consulta_info:
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                
                if consulta_info.get("tipo") == "dia":
                    with session.lock:
                        resumen = consultar_dia(session.driver, session.wait, fecha, canal=canal)
                    registrar_peticion(db, usuario.id, texto, "consulta_dia", canal=canal, respuesta=resumen)
                    session.update_activity()
                    return resumen
                    
                elif consulta_info.get("tipo") == "semana":
                    with session.lock:
                        resumen = consultar_semana(session.driver, session.wait, fecha, canal=canal)
                    registrar_peticion(db, usuario.id, texto, "consulta_semana", canal=canal, respuesta=resumen)
                    session.update_activity()
                    return resumen
                else:
                    respuesta = "🤔 No he entendido si preguntas por un día o una semana."
                    registrar_peticion(db, usuario.id, texto, "consulta", canal=canal, respuesta=respuesta)
                    session.update_activity()
                    return respuesta
            else:
                respuesta = "🤔 No he entendido qué quieres consultar."
                registrar_peticion(db, usuario.id, texto, "consulta", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta

        # ⚙️ Comandos de imputación
        elif tipo_mensaje == "comando":
            # 🆕 LEER LA TABLA ACTUAL para dar contexto a GPT
            tabla_actual = None
            try:
                from web_automation import leer_tabla_imputacion
                with session.lock:
                    tabla_actual = leer_tabla_imputacion(session.driver)
                print(f"[DEBUG] 📊 Tabla leída: {len(tabla_actual)} proyectos")
            except Exception as e:
                print(f"[DEBUG] ⚠️ No se pudo leer la tabla: {e}")
                # Continuar sin tabla, GPT funcionará sin ese contexto
            
            ordenes = interpretar_con_gpt(texto, contexto, tabla_actual)  # 🆕 Pasar tabla
            if not ordenes:
                respuesta = "🤔 No he entendido qué quieres que haga."
                registrar_peticion(db, usuario.id, texto, "comando", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta

            # 🆕 VERIFICAR SI ES UN ERROR DE VALIDACIÓN
            if len(ordenes) == 1 and ordenes[0].get('accion') == 'error_validacion':
                mensaje_error = ordenes[0].get('mensaje', '🤔 No he entendido qué quieres que haga.')
                registrar_peticion(db, usuario.id, texto, "comando_invalido", canal=canal, respuesta=mensaje_error)
                session.update_activity()
                return mensaje_error
            
            # 🆕 VERIFICAR SI ES INFORMACIÓN INCOMPLETA (GUARDAR ESTADO)
            if len(ordenes) == 1 and ordenes[0].get('accion') == 'info_incompleta':
                info_parcial = ordenes[0].get('info_parcial', {})
                que_falta = ordenes[0].get('que_falta', '')
                mensaje = ordenes[0].get('mensaje', '🤔 Falta información.')
                
                # Guardar estado para el próximo mensaje
                conversation_state_manager.guardar_info_incompleta(user_id, info_parcial, que_falta)
                
                registrar_peticion(db, usuario.id, texto, "info_incompleta", canal=canal, respuesta=mensaje)
                session.update_activity()
                return mensaje

            respuestas = []
            for orden in ordenes:
                # 🔒 LOCK SOLO PARA CADA ACCIÓN INDIVIDUAL
                with session.lock:
                    mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                
                # 🆕 VERIFICAR SI NECESITA DESAMBIGUACIÓN O CONFIRMACIÓN
                if isinstance(mensaje, dict):
                    tipo = mensaje.get("tipo")
                    
                    # CASO 1: Desambiguación (múltiples proyectos con mismo nombre)
                    if tipo == "desambiguacion":
                        from web_automation.desambiguacion import generar_mensaje_desambiguacion
                        
                        mensaje_pregunta = generar_mensaje_desambiguacion(
                            mensaje["proyecto"],
                            mensaje["coincidencias"],
                            canal=canal
                        )
                        
                        # Guardar estado para la próxima respuesta
                        conversation_state_manager.guardar_desambiguacion(
                            user_id,
                            mensaje["proyecto"],
                            mensaje["coincidencias"],
                            ordenes  # Comando original
                        )
                        
                        registrar_peticion(db, usuario.id, texto, "desambiguacion_pendiente", canal=canal, respuesta=mensaje_pregunta)
                        session.update_activity()
                        return mensaje_pregunta  # 🛑 DETENER EJECUCIÓN
                    
                    # CASO 2: Confirmar proyecto existente (encontrado en tabla)
                    elif tipo == "confirmar_existente":
                        print(f"[DEBUG] 💬 Proyecto existente encontrado, solicitando confirmación")
                        
                        info_existente = mensaje["coincidencias"][0] if mensaje.get("coincidencias") else {}
                        proyecto_nombre = info_existente.get("proyecto", "")
                        nodo_padre = info_existente.get("nodo_padre", "")
                        texto_completo = info_existente.get("texto_completo", "")
                        
                        # Generar mensaje de confirmación según el canal
                        if canal == "webapp":
                            mensaje_confirmacion = (
                                f"✅ He encontrado **{texto_completo}** ya imputado.\n\n"
                                f"¿Quieres añadir horas a este proyecto?\n\n"
                                f"💡 Responde:\n"
                                f"- **'sí'** para usar este proyecto\n"
                                f"- **'no'** para buscar otro"
                            )
                        else:
                            mensaje_confirmacion = (
                                f"✅ He encontrado *{texto_completo}* ya imputado.\n\n"
                                f"¿Quieres añadir horas a este proyecto?\n\n"
                                f"Responde 'sí' o 'no'"
                            )
                        
                        # Guardar estado (similar a desambiguación)
                        conversation_state_manager.guardar_desambiguacion(
                            user_id,
                            proyecto_nombre,
                            [{"proyecto": proyecto_nombre, "nodo_padre": nodo_padre, 
                              "path_completo": texto_completo}],
                            ordenes  # Comando original
                        )
                        
                        print(f"[DEBUG] 💾 Estado guardado - Esperando confirmación del usuario")
                        registrar_peticion(db, usuario.id, texto, "confirmacion_pendiente", 
                                         canal=canal, respuesta=mensaje_confirmacion)
                        session.update_activity()
                        return mensaje_confirmacion  # 🛑 DETENER EJECUCIÓN
                
                if mensaje:
                    respuestas.append(mensaje)

            # Generar respuesta SIN lock
            if respuestas:
                respuesta_natural = generar_respuesta_natural(respuestas, texto, contexto)
            else:
                respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."

            registrar_peticion(db, usuario.id, texto, "comando", canal=canal, 
                            respuesta=respuesta_natural, acciones=ordenes)
            session.update_activity()
            return respuesta_natural

        else:
            respuesta = "No he entendido el tipo de mensaje."
            registrar_peticion(db, usuario.id, texto, "desconocido", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

    except Exception as e:
        error_msg = f"⚠️ Error procesando la solicitud: {e}"
        registrar_peticion(db, usuario.id, texto, "error", canal=canal, 
                         respuesta=error_msg, estado="error")
        return error_msg


# 🔥 Función asíncrona que ejecuta el procesamiento en un thread separado
async def procesar_mensaje_usuario(texto: str, user_id: str, db: Session, canal: str = "webapp"):
    """
    Versión asíncrona que ejecuta el procesamiento síncrono en un thread pool.
    """
    loop = asyncio.get_event_loop()
    resultado = await loop.run_in_executor(
        executor,
        procesar_mensaje_usuario_sync,
        texto,
        user_id,
        db,
        canal
    )
    return resultado


# -------------------------------------------------------------------
# 💬 Endpoint del chatbot (para tu app web o interfaz HTTP directa)
# -------------------------------------------------------------------
@app.post("/chats")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    texto = data.get("message", "").strip()
    user_id = data.get("user_id", "web_user_default")
    
    # 📱 WhatsApp ID (si viene desde WhatsApp)
    wa_id = data.get("wa_id", "").strip()
    
    # 🔍 Auto-detectar si user_id es un número de WhatsApp
    if not wa_id and user_id and user_id.isdigit() and 10 <= len(user_id) <= 15:
        print(f"🔍 [CHATS] Auto-detectado número de WhatsApp en user_id: {user_id}")
        wa_id = user_id
    
    # 🆕 Credenciales opcionales enviadas desde Agente Co
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    agente_co_user_id = data.get("agente_co_user_id", "").strip()
    
    # 🔐 Si se envían credenciales, verificar y guardar
    if username and password and agente_co_user_id:
        print(f"\n🔐 [CHATS] Recibidas credenciales desde Agente Co")
        print(f"   Usuario GestionITT: {username}")
        print(f"   Agente Co User ID: {agente_co_user_id}")
        
        user_id = agente_co_user_id
        loop = asyncio.get_event_loop()
        session = await loop.run_in_executor(
            executor,
            lambda: browser_pool.get_session(user_id)
        )
        
        if not session or not session.driver:
            return JSONResponse({
                "success": False,
                "error": "Error al inicializar el navegador"
            }, status_code=500)
        
        try:
            # 🔥 Ejecutar login en thread separado
            loop = asyncio.get_event_loop()
            success, mensaje = await loop.run_in_executor(
                executor,
                lambda: hacer_login_with_lock(session, username, password)
            )
            
            if success:
                print(f"✅ [CHATS] Login exitoso para: {username}")
                session.is_logged_in = True
                
                from db import obtener_usuario_por_origen, crear_usuario
                usuario = obtener_usuario_por_origen(db, app_id=agente_co_user_id)
                
                if not usuario:
                    usuario = crear_usuario(db, app_id=agente_co_user_id, canal="webapp")
                    print(f"✅ [CHATS] Usuario creado en gestiondeverdad: {usuario.id}")
                
                usuario.establecer_credenciales_intranet(username, password)
                db.commit()
                
                print(f"💾 [CHATS] Credenciales guardadas en BD para usuario ID: {usuario.id}")
                
                return JSONResponse({
                    "success": True,
                    "message": "✅ Credenciales verificadas y guardadas correctamente",
                    "username": username,
                    "gestiondeverdad_user_id": usuario.id
                })
            else:
                print(f"❌ [CHATS] Login fallido para: {username}")
                return JSONResponse({
                    "success": False,
                    "error": "Usuario o contraseña incorrectos"
                }, status_code=401)
        
        except Exception as e:
            print(f"❌ [CHATS] Error al verificar credenciales: {e}")
            import traceback
            traceback.print_exc()
            return JSONResponse({
                "success": False,
                "error": f"Error al verificar credenciales: {str(e)}"
            }, status_code=500)
    
    # 📱 Si viene desde WhatsApp
    if wa_id:
        print(f"\n📱 [CHATS] Petición desde WhatsApp: {wa_id}")
        
        if not texto:
            return JSONResponse({"reply": "No he recibido ningún mensaje."})
        
        from db import obtener_usuario_por_origen, crear_usuario
        usuario_wa = obtener_usuario_por_origen(db, wa_id=wa_id)
        
        if not usuario_wa:
            usuario_wa = crear_usuario(db, wa_id=wa_id, canal="whatsapp")
            print(f"✅ [CHATS] Usuario de WhatsApp creado: {usuario_wa.id}")
        
        if not usuario_wa.username_intranet or not usuario_wa.password_intranet:
            print(f"🔐 [CHATS] Usuario sin credenciales, intentando extraer...")
            
            from auth_handler import extraer_credenciales_con_gpt
            credenciales = extraer_credenciales_con_gpt(texto)
            
            if credenciales["ambos"]:
                print(f"🔑 [CHATS] Credenciales extraídas: {credenciales['username']}")
                
                loop = asyncio.get_event_loop()
                session = await loop.run_in_executor(
                    executor,
                    lambda: browser_pool.get_session(wa_id)
                )
                
                if not session or not session.driver:
                    return JSONResponse({"reply": "⚠️ No he podido iniciar el navegador."})
                
                try:
                    # 🔥 Login en thread separado
                    loop = asyncio.get_event_loop()
                    success, mensaje = await loop.run_in_executor(
                        executor,
                        lambda: hacer_login_with_lock(session, credenciales["username"], credenciales["password"])
                    )
                    
                    if success:
                        print(f"✅ [CHATS] Login exitoso para WhatsApp: {credenciales['username']}")
                        session.is_logged_in = True
                        
                        usuario_wa.establecer_credenciales_intranet(
                            credenciales["username"], 
                            credenciales["password"]
                        )
                        db.commit()
                        
                        registrar_peticion(db, usuario_wa.id, texto, "registro_whatsapp", 
                                         canal="whatsapp", respuesta="Credenciales guardadas exitosamente")
                        
                        return JSONResponse({
                            "reply": (
                                "✅ *¡Credenciales guardadas correctamente!*\n\n"
                                f"✓ Usuario: *{credenciales['username']}*\n"
                                "✓ Contraseña: ******\n\n"
                                "🚀 Ya puedes empezar a usar el bot. ¿En qué puedo ayudarte?"
                            )
                        })
                    else:
                        return JSONResponse({
                            "reply": (
                                "❌ *Error de login*\n\n"
                                "Las credenciales no son correctas."
                            )
                        })
                
                except Exception as e:
                    print(f"❌ [CHATS] Error: {e}")
                    return JSONResponse({"reply": f"⚠️ Error: {str(e)}"})
            
            else:
                return JSONResponse({
                    "reply": (
                        "👋 *¡Hola!* Aún no tengo tus credenciales de GestiónITT.\n\n"
                        "📝 Envíamelas así:\n"
                        "```\n"
                        "Usuario: tu_usuario\n"
                        "Contraseña: tu_contraseña\n"
                        "```"
                    )
                })
        
        # 🔥 Procesar mensaje en thread separado
        respuesta = await procesar_mensaje_usuario(texto, wa_id, db, canal="whatsapp")
        return JSONResponse({"reply": respuesta})
    
    # 💬 Procesamiento normal
    if not texto:
        return JSONResponse({"reply": "No he recibido ningún mensaje."})
    
    # 🔥 Procesar mensaje en thread separado
    respuesta = await procesar_mensaje_usuario(texto, user_id, db, canal="webapp")
    return JSONResponse({"reply": respuesta})


# Helper para login con lock
def hacer_login_with_lock(session, username, password):
    """Helper para hacer login con lock"""
    with session.lock:
        return hacer_login(session.driver, session.wait, username, password)


# -------------------------------------------------------------------
# 💬 Endpoint Slack Events
# -------------------------------------------------------------------
eventos_procesados = deque(maxlen=1000)

@app.post("/slack/events")
async def slack_events(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    if "challenge" in data:
        return JSONResponse({"challenge": data["challenge"]})

    event_id = data.get("event_id")
    if event_id in eventos_procesados:
        print(f"⚠️ Evento duplicado ignorado: {event_id}")
        return JSONResponse({"status": "duplicate_ignored"})
    eventos_procesados.append(event_id)

    event = data.get("event", {})
    texto = event.get("text", "")
    user = event.get("user", "")
    bot_id = event.get("bot_id", None)
    channel = event.get("channel", "")

    if bot_id or not texto:
        return JSONResponse({"status": "ignored"})

    print(f"📩 Mensaje de {user}: {texto}")
    
    # 🔥 Procesar en thread separado
    respuesta = await procesar_mensaje_usuario(texto, user, db, canal="slack")
    
    # ✅ Enviar respuesta a Slack
    requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": respuesta}
    )

    print(f"💬 Respondido en Slack: {respuesta}")
    return JSONResponse({"status": "ok"})


# -------------------------------------------------------------------
# 📊 Endpoint de estadísticas del pool
# -------------------------------------------------------------------
@app.get("/stats")
async def stats():
    """Endpoint para ver estadísticas del pool de navegadores."""
    return JSONResponse(browser_pool.get_stats())


# -------------------------------------------------------------------
# 🛑 Cerrar navegador de un usuario específico
# -------------------------------------------------------------------
@app.post("/close-session/{user_id}")
async def close_user_session(user_id: str):
    """Endpoint para cerrar manualmente la sesión de un usuario."""
    browser_pool.close_session(user_id)
    return JSONResponse({"status": "ok", "message": f"Sesión de {user_id} cerrada"})


# -------------------------------------------------------------------
# 🔄 Shutdown: cerrar todos los navegadores al apagar el servidor
# -------------------------------------------------------------------
@app.on_event("shutdown")
def shutdown_event():
    print("[SERVER] 🛑 Apagando servidor, cerrando todos los navegadores...")
    browser_pool.close_all()
    executor.shutdown(wait=True)
