import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from main_script import interpretar_con_gpt, ejecutar_accion, hacer_login
from fastapi.middleware.cors import CORSMiddleware  # 👈 Import necesario
from collections import deque
import time

# 🚀 Inicialización de la app FastAPI
app = FastAPI()

# 🌐 Habilitar CORS (para tu frontend en Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # 👈 para pruebas locales
        # Recomendado para producción:
        # "https://proyecto-agente.onrender.com"
    ],
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

# 💬 Endpoint del chatbot (para tu app web o botón flotante)
@app.post("/chats")
async def chat(request: Request):
    data = await request.json()
    texto = data.get("message", "")
    ordenes = interpretar_con_gpt(texto)
    for orden in ordenes:
        ejecutar_accion(driver, wait, orden)
    return JSONResponse({"reply": f"✅ Ejecutadas {len(ordenes)} acciones."})


# 💬 Endpoint Slack Events
eventos_procesados = deque(maxlen=1000)

@app.post("/slack/events")
async def slack_events(request: Request):
    data = await request.json()

    # 1️⃣ Challenge de verificación
    if "challenge" in data:
        return JSONResponse({"challenge": data["challenge"]})

    # 2️⃣ Evitar procesar dos veces el mismo evento
    event_id = data.get("event_id")
    if event_id in eventos_procesados:
        print(f"⚠️ Evento duplicado ignorado: {event_id}")
        return JSONResponse({"status": "duplicate_ignored"})
    eventos_procesados.append(event_id)

    # 3️⃣ Extraer info del evento
    event = data.get("event", {})
    texto = event.get("text", "")
    user = event.get("user", "")
    bot_id = event.get("bot_id", None)
    channel = event.get("channel", "")

    # 4️⃣ Evitar bucles del propio bot
    if bot_id or not texto:
        return JSONResponse({"status": "ignored"})

    print(f"📩 Mensaje de {user}: {texto}")
    ordenes = interpretar_con_gpt(texto)
    print("🧾 Interpretación:", ordenes)

    for orden in ordenes:
        ejecutar_accion(driver, wait, orden)

    # 💬 Construir respuesta legible
    detalles = []
    for o in ordenes:
        if isinstance(o, dict):
            partes = []
            if "accion" in o:
                partes.append(o["accion"])
            if "parametros" in o:
                for k, v in o["parametros"].items():
                    partes.append(f"{k}: {v}")
            detalles.append(" ".join(partes))
        else:
            detalles.append(str(o))

    respuesta = f"✅ Tarea ejecutada: {', '.join(detalles)}"

    # ✅ Enviar respuesta al canal Slack
    requests.post(
        SLACK_API_URL,
        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
        json={"channel": channel, "text": respuesta}
    )

    print(f"💬 Respondido en Slack: {respuesta}")
    return JSONResponse({"status": "ok"})
