import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
import time
from datetime import datetime

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
    generar_resumen_natural
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
hacer_login(driver, wait)

# -------------------------------------------------------------------
# 💬 Endpoint del chatbot (para tu app web o interfaz HTTP directa)
# -------------------------------------------------------------------
@app.post("/chats")
async def chat(request: Request):
    data = await request.json()
    texto = data.get("message", "").strip()

    if not texto:
        return JSONResponse({"reply": "No he recibido ningún mensaje."})

    try:
        tipo_mensaje = clasificar_mensaje(texto)
        contexto = {"fila_actual": None, "proyecto_actual": None}

        # 🗣️ Conversación natural (saludos o charla)
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)
            return JSONResponse({"reply": respuesta})

        # 📊 Consultas (resumen semanal)
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            if consulta_info and consulta_info.get("tipo") == "semana":
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                info_bruta = consultar_semana(driver, wait, fecha)
                resumen_natural = generar_resumen_natural(info_bruta, texto)
                return JSONResponse({"reply": resumen_natural})
            else:
                return JSONResponse({"reply": "🤔 No he entendido qué semana quieres consultar."})

        # ⚙️ Comandos de imputación
        elif tipo_mensaje == "comando":
            ordenes = interpretar_con_gpt(texto)
            if not ordenes:
                return JSONResponse({"reply": "🤔 No he entendido qué quieres que haga."})

            respuestas = []
            for orden in ordenes:
                mensaje = ejecutar_accion(driver, wait, orden, contexto)
                if mensaje:
                    respuestas.append(mensaje)

            if respuestas:
                respuesta_natural = generar_respuesta_natural(respuestas, texto)
            else:
                respuesta_natural = "He procesado la instrucción, pero no hubo mensajes de salida."

            return JSONResponse({"reply": respuesta_natural})

        else:
            return JSONResponse({"reply": "No he entendido el tipo de mensaje."})

    except Exception as e:
        return JSONResponse({"reply": f"⚠️ Error procesando la solicitud: {e}"})


# -------------------------------------------------------------------
# 💬 Endpoint Slack Events (idéntico comportamiento al de consola)
# -------------------------------------------------------------------
eventos_procesados = deque(maxlen=1000)

@app.post("/slack/events")
async def slack_events(request: Request):
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

    try:
        tipo_mensaje = clasificar_mensaje(texto)
        contexto = {"fila_actual": None, "proyecto_actual": None}

        # 🗣️ Conversación natural
        if tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto)

        # 📊 Consulta semanal
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            if consulta_info and consulta_info.get("tipo") == "semana":
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                info_bruta = consultar_semana(driver, wait, fecha)
                respuesta = generar_resumen_natural(info_bruta, texto)
            else:
                respuesta = "🤔 No he entendido qué semana quieres consultar."

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

        else:
            respuesta = "No he entendido el tipo de mensaje."

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
        return JSONResponse({"status": "error", "message": error_msg})
