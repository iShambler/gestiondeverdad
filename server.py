import os
import requests
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
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

# 🚀 Lanzar navegador al iniciar el servidor
service = ChromeService(ChromeDriverManager().install())
options = webdriver.ChromeOptions()
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 15)

# Estado global para controlar si hay sesión activa y de qué usuario
sesion_actual = {"user_id": None, "logueado": False}

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
    
    # 🔐 Verificar autenticación
    usuario, mensaje_auth = verificar_y_solicitar_credenciales(db, user_id, canal="webapp")
    
    # Si está esperando credenciales, procesarlas
    if estado_auth.esta_en_proceso(user_id):
        completado, mensaje = procesar_credencial(db, user_id, texto, canal="webapp")
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal="webapp", respuesta=mensaje)
        return JSONResponse({"reply": mensaje})
    
    # Si necesita proporcionar credenciales por primera vez
    if mensaje_auth:
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal="webapp", respuesta=mensaje_auth)
        return JSONResponse({"reply": mensaje_auth})
    
    # 🎯 Asegurar que hay login activo con las credenciales del usuario
    username, password = obtener_credenciales(db, user_id, canal="webapp")
    if username and password:
        # Si no hay sesión o es de otro usuario, hacer login
        if not sesion_actual["logueado"] or sesion_actual["user_id"] != user_id:
            print(f"[INFO] Haciendo login para usuario: {username}")
            try:
                hacer_login(driver, wait, username, password)
                sesion_actual["user_id"] = user_id
                sesion_actual["logueado"] = True
                print(f"[INFO] Login exitoso para {username}")
            except Exception as e:
                error_msg = f"⚠️ Error al hacer login: {e}"
                registrar_peticion(db, usuario.id, texto, "error", canal="webapp", respuesta=error_msg, estado="error")
                return JSONResponse({"reply": error_msg})

    try:
        tipo_mensaje = clasificar_mensaje(texto)
        contexto = {"fila_actual": None, "proyecto_actual": None}

        # 🗣️ Conversación natural (saludos o charla)
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)
            registrar_peticion(db, usuario.id, texto, "conversacion", canal="webapp", respuesta=respuesta)
            return JSONResponse({"reply": respuesta})

        # 📊 Consultas (resumen semanal)
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            if consulta_info and consulta_info.get("tipo") == "semana":
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                info_bruta = consultar_semana(driver, wait, fecha)
                resumen_natural = generar_resumen_natural(info_bruta, texto)
                registrar_peticion(db, usuario.id, texto, "consulta", canal="webapp", respuesta=resumen_natural)
                return JSONResponse({"reply": resumen_natural})
            else:
                respuesta = "🤔 No he entendido qué semana quieres consultar."
                registrar_peticion(db, usuario.id, texto, "consulta", canal="webapp", respuesta=respuesta)
                return JSONResponse({"reply": respuesta})

        # ⚙️ Comandos de imputación
        elif tipo_mensaje == "comando":
            ordenes = interpretar_con_gpt(texto)
            if not ordenes:
                respuesta = "🤔 No he entendido qué quieres que haga."
                registrar_peticion(db, usuario.id, texto, "comando", canal="webapp", respuesta=respuesta)
                return JSONResponse({"reply": respuesta})

            respuestas = []
            for orden in ordenes:
                mensaje = ejecutar_accion(driver, wait, orden, contexto)
                if mensaje:
                    respuestas.append(mensaje)

            if respuestas:
                respuesta_natural = generar_respuesta_natural(respuestas, texto)
            else:
                respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."

            registrar_peticion(db, usuario.id, texto, "comando", canal="webapp", 
                             respuesta=respuesta_natural, acciones=ordenes)
            return JSONResponse({"reply": respuesta_natural})

        else:
            respuesta = "No he entendido el tipo de mensaje."
            registrar_peticion(db, usuario.id, texto, "desconocido", canal="webapp", respuesta=respuesta)
            return JSONResponse({"reply": respuesta})

    except Exception as e:
        error_msg = f"⚠️ Error procesando la solicitud: {e}"
        registrar_peticion(db, usuario.id, texto, "error", canal="webapp", 
                         respuesta=error_msg, estado="error")
        return JSONResponse({"reply": error_msg})


# -------------------------------------------------------------------
# 💬 Endpoint Slack Events (idéntico comportamiento al de consola)
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
    
    # 🔐 Verificar autenticación del usuario de Slack
    print(f"[DEBUG] Verificando autenticación para user_id: {user}")
    usuario_db, mensaje_auth = verificar_y_solicitar_credenciales(db, user, canal="slack")
    print(f"[DEBUG] Usuario DB: {usuario_db.id if usuario_db else None}")
    print(f"[DEBUG] Mensaje auth: {mensaje_auth[:50] if mensaje_auth else 'None'}...")
    
    # Si está en proceso de proporcionar credenciales
    if estado_auth.esta_en_proceso(user):
        print(f"[DEBUG] Usuario en proceso de autenticación")
        completado, mensaje = procesar_credencial(db, user, texto, canal="slack")
        print(f"[DEBUG] Completado: {completado}, Mensaje: {mensaje[:50] if mensaje else 'None'}...")
        
        # Enviar respuesta a Slack
        requests.post(
            SLACK_API_URL,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": channel, "text": mensaje}
        )
        
        registrar_peticion(db, usuario_db.id, texto, "autenticacion", canal="slack", respuesta=mensaje)
        return JSONResponse({"status": "ok"})
    
    # Si necesita credenciales por primera vez
    if mensaje_auth:
        print(f"[DEBUG] Enviando mensaje de solicitud de credenciales")
        requests.post(
            SLACK_API_URL,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": channel, "text": mensaje_auth}
        )
        registrar_peticion(db, usuario_db.id, texto, "autenticacion", canal="slack", respuesta=mensaje_auth)
        print(f"💬 Respondido en Slack: {mensaje_auth[:50]}...")
        return JSONResponse({"status": "ok"})
    
    # 🎯 Asegurar que hay login activo con las credenciales del usuario
    username, password = obtener_credenciales(db, user, canal="slack")
    if username and password:
        # Si no hay sesión o es de otro usuario, hacer login
        if not sesion_actual["logueado"] or sesion_actual["user_id"] != user:
            print(f"[INFO] Haciendo login para usuario: {username}")
            try:
                hacer_login(driver, wait, username, password)
                sesion_actual["user_id"] = user
                sesion_actual["logueado"] = True
                print(f"[INFO] Login exitoso para {username}")
            except Exception as e:
                error_msg = f"⚠️ Error al hacer login: {e}. ¿Tus credenciales son correctas?"
                requests.post(
                    SLACK_API_URL,
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json={"channel": channel, "text": error_msg}
                )
                registrar_peticion(db, usuario_db.id, texto, "error", canal="slack", respuesta=error_msg, estado="error")
                return JSONResponse({"status": "error", "message": str(e)})

    try:
        tipo_mensaje = clasificar_mensaje(texto)
        contexto = {"fila_actual": None, "proyecto_actual": None}

        # 🗣️ Conversación natural
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)
            registrar_peticion(db, usuario_db.id, texto, "conversacion", canal="slack", respuesta=respuesta)

        # 📊 Consulta semanal
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            if consulta_info and consulta_info.get("tipo") == "semana":
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                info_bruta = consultar_semana(driver, wait, fecha)
                respuesta = generar_resumen_natural(info_bruta, texto)
            else:
                respuesta = "🤔 No he entendido qué semana quieres consultar."
            
            registrar_peticion(db, usuario_db.id, texto, "consulta", canal="slack", respuesta=respuesta)

        # ⚙️ Comando de imputación
        elif tipo_mensaje == "comando":
            ordenes = interpretar_con_gpt(texto)
            if not ordenes:
                respuesta = "🤔 No he entendido qué quieres que haga."
            else:
                respuestas = []
                for orden in ordenes:
                    mensaje = ejecutar_accion(driver, wait, orden, contexto)
                    if mensaje:
                        respuestas.append(mensaje)
                if respuestas:
                    respuesta = generar_respuesta_natural(respuestas, texto)
                else:
                    respuesta = "He procesado la instrucción, pero no hubo mensajes de salida."
            
            registrar_peticion(db, usuario_db.id, texto, "comando", canal="slack", 
                             respuesta=respuesta, acciones=ordenes if ordenes else None)

        else:
            respuesta = "No he entendido el tipo de mensaje."
            registrar_peticion(db, usuario_db.id, texto, "desconocido", canal="slack", respuesta=respuesta)

        # ✅ Enviar respuesta a Slack
        requests.post(
            SLACK_API_URL,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            json={"channel": channel, "text": respuesta}
        )

        print(f"💬 Respondido en Slack: {respuesta}")
        return JSONResponse({"status": "ok"})

    except Exception as e:
        error_msg = f"⚠️ Error procesando mensaje de Slack: {e}"
        print(error_msg)
        registrar_peticion(db, usuario_db.id, texto, "error", canal="slack", 
                         respuesta=error_msg, estado="error")
        return JSONResponse({"status": "error", "message": error_msg})
