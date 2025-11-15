import os
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
    consultar_semana
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
        # 🔥 SIN LOCK AQUÍ - cada operación maneja su propio lock si es necesario
        tipo_mensaje = clasificar_mensaje(texto)
        contexto = session.contexto  # Usar el contexto de la sesión del usuario

        # 🗣️ Conversación natural (saludos o charla)
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)
            registrar_peticion(db, usuario.id, texto, "conversacion", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # 📊 Consultas (resumen semanal o diario)
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            if consulta_info:
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                
                if consulta_info.get("tipo") == "dia":
                    # 🔒 LOCK SOLO PARA LA OPERACIÓN DEL NAVEGADOR
                    with session.lock:
                        info_bruta = consultar_dia(session.driver, session.wait, fecha)
                    
                    # Generar respuesta SIN lock
                    resumen_natural = generar_resumen_natural(info_bruta, texto)
                    registrar_peticion(db, usuario.id, texto, "consulta_dia", canal=canal, respuesta=resumen_natural)
                    session.update_activity()
                    return resumen_natural
                    
                elif consulta_info.get("tipo") == "semana":
                    # 🔒 LOCK SOLO PARA LA OPERACIÓN DEL NAVEGADOR
                    with session.lock:
                        info_bruta = consultar_semana(session.driver, session.wait, fecha)
                    
                    # Generar respuesta SIN lock
                    resumen_natural = generar_resumen_natural(info_bruta, texto)
                    registrar_peticion(db, usuario.id, texto, "consulta_semana", canal=canal, respuesta=resumen_natural)
                    session.update_activity()
                    return resumen_natural
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
            ordenes = interpretar_con_gpt(texto)
            if not ordenes:
                respuesta = "🤔 No he entendido qué quieres que haga."
                registrar_peticion(db, usuario.id, texto, "comando", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta

            respuestas = []
            for orden in ordenes:
                # 🔒 LOCK SOLO PARA CADA ACCIÓN INDIVIDUAL
                with session.lock:
                    mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                if mensaje:
                    respuestas.append(mensaje)

            # Generar respuesta SIN lock
            if respuestas:
                respuesta_natural = generar_respuesta_natural(respuestas, texto)
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
        session = browser_pool.get_session(user_id)
        
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
                
                session = browser_pool.get_session(wa_id)
                
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
