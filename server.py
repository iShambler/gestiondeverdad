import os

from dotenv import load_dotenv  

import requests
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
import time
from datetime import datetime
from sqlalchemy.orm import Session

# 🧩 Importa todas las funciones necesarias del script principal
from main_script import (
    interpretar_con_gpt,
    ejecutar_accion,
    hacer_login,
    generar_respuesta_natural,
    clasificar_mensaje,
    responder_conversacion,
    interpretar_consulta,
    consultar_semana,
    generar_resumen_natural,
)

# Importar funciones de base de datos y autenticación
from db import get_db, registrar_peticion
from auth_handler import (
    verificar_y_solicitar_credenciales,
    procesar_credencial,
    obtener_credenciales,
    estado_auth
)

# 🆕 Importar el pool de navegadores
from browser_pool import browser_pool

# 🚀 Inicialización de la app FastAPI
app = FastAPI()

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
def procesar_mensaje_usuario(texto: str, user_id: str, db: Session, canal: str = "webapp"):
    """
    Lógica común para procesar mensajes de usuarios (webapp o slack).
    Usa el pool de navegadores para obtener una sesión individual por usuario.
    
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
    
    # Si está esperando credenciales iniciales, procesarlas
    if estado_auth.esta_en_proceso(user_id):
        completado, mensaje = procesar_credencial(db, user_id, texto, canal=canal)
        
        # Si completó el proceso de credenciales, verificarlas con login de prueba
        if completado:
            username, password = obtener_credenciales(db, user_id, canal=canal)
            
            if username and password:
                # Obtener sesión para verificar login
                session = browser_pool.get_session(user_id)
                
                if session and session.driver:
                    print(f"[INFO] 🔍 Verificando credenciales para: {username}")
                    
                    try:
                        with session.lock:
                            success, mensaje_login = hacer_login(session.driver, session.wait, username, password)
                        
                        if success:
                            # ✅ Credenciales válidas
                            session.is_logged_in = True
                            mensaje_verificado = (
                                f"✅ **¡Perfecto!** He verificado tus credenciales y funcionan correctamente.\n\n"
                                f"✅ Usuario: **{username}**\n"
                                f"✅ Contraseña: ******\n\n"
                                "🚀 Ya puedes usar el servicio. ¿En qué te ayudo?"
                            )
                            registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=mensaje_verificado)
                            return mensaje_verificado
                        else:
                            # Eliminar credenciales incorrectas
                            usuario.username_intranet = None
                            usuario.password_intranet = None
                            db.commit()
                            
                            # Reiniciar proceso
                            estado_auth.iniciar_proceso(user_id)
                            
                            mensaje_error = (
                                "❌ **Error**: Las credenciales no son válidas en GestiónITT.\n\n"
                                "Por favor, verifica tus datos y envíamelos de nuevo:\n\n"
                                "🔑 **Nombre de usuario**:"
                            )
                            registrar_peticion(db, usuario.id, texto, "autenticacion_fallida", canal=canal, respuesta=mensaje_error, estado="credenciales_invalidas")
                            return mensaje_error
                    except Exception as e:
                        mensaje_error = f"⚠️ Error al verificar credenciales: {e}"
                        registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=mensaje_error, estado="error")
                        return mensaje_error
        
        # Si no completó aún (esperando más datos)
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=mensaje)
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
                
                with session.lock:  # Thread-safe
                    success, mensaje_login = hacer_login(session.driver, session.wait, username, password)
                    
                    if not success:
                        # ❌ Login fallido
                        if "credenciales_invalidas" in mensaje_login:
                            # Iniciar proceso de cambio de credenciales
                            credential_manager.iniciar_cambio_credenciales(user_id)
                            error_msg = (
                                "❌ **Error de login**: Las credenciales de GestiónITT no son correctas.\n\n"
                                "¿Quieres actualizar tus credenciales?\n\n"
                                "👉 Si es así, envíame tu **nuevo nombre de usuario** de GestiónITT.\n"
                                "👉 Si no, escribe 'cancelar' y revisaré el problema."
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
        with session.lock:  # Thread-safe para operaciones del navegador
            tipo_mensaje = clasificar_mensaje(texto)
            contexto = session.contexto  # Usar el contexto de la sesión del usuario

            # 🗣️ Conversación natural (saludos o charla)
            if tipo_mensaje == "conversacion":
                respuesta = responder_conversacion(texto)
                registrar_peticion(db, usuario.id, texto, "conversacion", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta

            # 📊 Consultas (resumen semanal)
            elif tipo_mensaje == "consulta":
                consulta_info = interpretar_consulta(texto)
                if consulta_info and consulta_info.get("tipo") == "semana":
                    fecha = datetime.fromisoformat(consulta_info["fecha"])
                    info_bruta = consultar_semana(session.driver, session.wait, fecha)
                    resumen_natural = generar_resumen_natural(info_bruta, texto)
                    registrar_peticion(db, usuario.id, texto, "consulta", canal=canal, respuesta=resumen_natural)
                    session.update_activity()
                    return resumen_natural
                else:
                    respuesta = "🤔 No he entendido qué semana quieres consultar."
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
                    mensaje = ejecutar_accion(session.driver, session.wait, orden, contexto)
                    if mensaje:
                        respuestas.append(mensaje)

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


# -------------------------------------------------------------------
# 💬 Endpoint del chatbot (para tu app web o interfaz HTTP directa)
# -------------------------------------------------------------------
@app.post("/chats")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    texto = data.get("message", "").strip()
    user_id = data.get("user_id", "web_user_default")  # ID del usuario desde el frontend

    if not texto:
        return JSONResponse({"reply": "No he recibido ningún mensaje."})
    
    respuesta = procesar_mensaje_usuario(texto, user_id, db, canal="webapp")
    return JSONResponse({"reply": respuesta})


# -------------------------------------------------------------------
# 💬 Endpoint Slack Events
# -------------------------------------------------------------------
eventos_procesados = deque(maxlen=1000)

@app.post("/slack/events")
async def slack_events(request: Request, db: Session = Depends(get_db)):
    data = await request.json()

    # 1️⃣ Challenge de verificación inicial de Slack
    if "challenge" in data:
        return JSONResponse({"challenge": data["challenge"]})

    # 2️⃣ Evitar procesar el mismo evento varias veces
    event_id = data.get("event_id")
    if event_id in eventos_procesados:
        print(f"⚠️ Evento duplicado ignorado: {event_id}")
        return JSONResponse({"status": "duplicate_ignored"})
    eventos_procesados.append(event_id)

    # 3️⃣ Extraer información del evento
    event = data.get("event", {})
    texto = event.get("text", "")
    user = event.get("user", "")
    bot_id = event.get("bot_id", None)
    channel = event.get("channel", "")

    # 4️⃣ Evitar responderse a sí mismo
    if bot_id or not texto:
        return JSONResponse({"status": "ignored"})

    print(f"📩 Mensaje de {user}: {texto}")
    
    # Procesar mensaje con la función común
    respuesta = procesar_mensaje_usuario(texto, user, db, canal="slack")
    
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
