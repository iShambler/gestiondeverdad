import os

from dotenv import load_dotenv 

load_dotenv()

import re
import requests
from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from collections import deque
from datetime import datetime
from sqlalchemy.orm import Session
import asyncio
from concurrent.futures import ThreadPoolExecutor
from db import SessionLocal
import traceback

# Importaciones de módulos
from ai import clasificar_mensaje, interpretar_con_gpt, responder_conversacion, interpretar_consulta
from core import consultar_dia, consultar_semana, consultar_mes, mostrar_comandos
from web_automation import leer_tabla_imputacion
from db import get_db, registrar_peticion, obtener_usuario_por_origen, crear_usuario
from auth_handler import verificar_y_solicitar_credenciales, obtener_credenciales, extraer_credenciales_con_gpt
from browser_pool import browser_pool
from conversation_state import conversation_state_manager
from credential_manager import credential_manager

# ⭐ IMPORTAR TODAS LAS FUNCIONES AUXILIARES
from funciones_server import (
    hacer_login_con_lock,
    manejar_cambio_credenciales,
    realizar_login_inicial,
    manejar_info_incompleta,
    ejecutar_comando_completo,
    ejecutar_ordenes_y_generar_respuesta,
    manejar_confirmacion_si_no,
    manejar_desambiguacion_multiple
)

# Inicialización
app = FastAPI()
executor = ThreadPoolExecutor(max_workers=50)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GREEN_API_INSTANCE_ID = os.getenv("GREEN_API_INSTANCE_ID")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN")

# ============================================================================
# FUNCIÓN PRINCIPAL DE PROCESAMIENTO
# ============================================================================

def procesar_mensaje_usuario_sync(texto: str, user_id: str, db: Session, canal: str = "webapp"):
    """Lógica principal para procesar mensajes de usuarios"""
    
    # Verificar autenticación
    usuario, mensaje_auth = verificar_y_solicitar_credenciales(db, user_id, canal=canal)
    
    # Manejar cambio de credenciales
    if credential_manager.esta_cambiando_credenciales(user_id):
        _, mensaje, _ = manejar_cambio_credenciales(texto, user_id, usuario, db, canal)
        session = browser_pool.get_session(user_id)
        if session:
            session.is_logged_in = False
        return mensaje
    
    # Si necesita credenciales por primera vez
    if mensaje_auth:
        registrar_peticion(db, usuario.id, texto, "autenticacion", canal=canal, respuesta=mensaje_auth)
        return mensaje_auth
    
    # Obtener sesión de navegador
    session = browser_pool.get_session(user_id)
    if not session or not session.driver:
        error_msg = " No he podido iniciar el navegador. Intenta de nuevo en unos momentos."
        registrar_peticion(db, usuario.id, texto, "error", canal=canal, respuesta=error_msg, estado="error")
        return error_msg
    
    # Asegurar login activo
    username, password = obtener_credenciales(db, user_id, canal=canal)
    if username and password:
        success, mensaje, debe_continuar = realizar_login_inicial(
            session, user_id, username, password, usuario, texto, db, canal
        )
        if not debe_continuar:
            return mensaje

    try:
        contexto = session.contexto
        contexto["user_id"] = user_id
        
        # VERIFICAR SI HAY PREGUNTA PENDIENTE
        if conversation_state_manager.tiene_pregunta_pendiente(user_id):
            print(f"[DEBUG] 💬 Usuario {user_id} tiene pregunta pendiente")
            estado = conversation_state_manager.obtener_desambiguacion(user_id)
            
            #  DETECTAR CANCELACIÓN O NUEVA ORDEN
            texto_lower = texto.lower().strip()
            
            # 1. Palabras de cancelación
            palabras_cancelar = [
                'cancelar', 'cancel', 'nada', 'olvida', 'olvídalo', 'olvidalo',
                'equivocado', 'equivocada', 'me equivoqué', 'me equivoque',
                'error', 'no quiero', 'déjalo', 'dejalo', 'salir', 'sal',
                'no importa', 'da igual'
            ]
            
            if any(palabra in texto_lower for palabra in palabras_cancelar):
                print(f"[DEBUG]  Usuario canceló la desambiguación")
                conversation_state_manager.limpiar_estado(user_id)
                respuesta = "👍 Vale, no pasa nada. ¿En qué puedo ayudarte?"
                registrar_peticion(db, usuario.id, texto, "cancelacion_desambiguacion", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta
            
            # 2. Nueva orden (palabras de acción)
            palabras_orden_nueva = [
                'pon', 'ponme', 'añade', 'añádeme', 'añademe', 
                'imputa', 'mete', 'quita', 'resta', 'borra',
                'dame', 'dime', 'muéstrame', 'muestrame', 'lista', 'listar'
            ]
            
            # Si contiene palabras de orden nueva, cancelar desambiguación y procesar como nuevo comando
            if any(palabra in texto_lower for palabra in palabras_orden_nueva):
                print(f"[DEBUG] 🔄 Usuario dio una orden nueva, cancelando desambiguación")
                conversation_state_manager.limpiar_estado(user_id)
                # NO hacer return, dejar que siga procesando como comando normal
            else:
                # Es respuesta a la desambiguación, procesar normalmente
                
                # CASO 1: Info incompleta
                if estado and estado.get("tipo") == "info_incompleta":
                    return manejar_info_incompleta(texto, estado, user_id, session, 
                                                  contexto, db, usuario, canal)
                
                # CASO 2: Confirmación (solo 1 coincidencia)
                if len(estado["coincidencias"]) == 1:
                    return manejar_confirmacion_si_no(texto, estado, session, db, usuario, 
                                                     user_id, canal, contexto)
                
                # CASO 3: Desambiguación múltiple
                else:
                    return manejar_desambiguacion_multiple(texto, estado, session, db, usuario, 
                                                          user_id, canal, contexto)
        
        # PROCESAR NUEVO MENSAJE
        tipo_mensaje = clasificar_mensaje(texto)

        # AYUDA
        if tipo_mensaje == "ayuda":
            respuesta = mostrar_comandos()
            registrar_peticion(db, usuario.id, texto, "ayuda", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # CONVERSACIÓN
        elif tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto, user_id)
            registrar_peticion(db, usuario.id, texto, "conversacion", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # CONSULTAS
        elif tipo_mensaje == "consulta":
            consulta_info = interpretar_consulta(texto)
            
            #  CASO 1: Listar proyectos
            if not consulta_info or consulta_info.get("tipo") == "listar_proyectos":
                from web_automation.listado_proyectos import listar_todos_proyectos, formatear_lista_proyectos
                
                filtro_nodo = None
                texto_lower = texto.lower()
                
                if "departamento" in texto_lower:
                    match = re.search(r'departamento\s+(\w+(?:\s+\w+)*)', texto_lower, re.IGNORECASE)
                    if match:
                        filtro_nodo = match.group(0).strip()
                elif "en " in texto_lower:
                    match = re.search(r'en\s+([\w-]+(?:\s+[\w-]+)*)', texto_lower, re.IGNORECASE)
                    if match:
                        filtro_nodo = match.group(1).strip()
                
                with session.lock:
                    proyectos_por_nodo = listar_todos_proyectos(session.driver, session.wait, filtro_nodo)
                
                respuesta = formatear_lista_proyectos(proyectos_por_nodo, canal=canal)
                registrar_peticion(db, usuario.id, texto, "listar_proyectos", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta
            
        #  CASO 2: Consulta de horas (día, semana o mes)
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
                
                elif consulta_info.get("tipo") == "mes":
                    #  Consulta de un mes completo
                    mes = fecha.month
                    anio = fecha.year
                    with session.lock:
                        resumen = consultar_mes(session.driver, session.wait, mes, anio, canal=canal)
                    registrar_peticion(db, usuario.id, texto, "consulta_mes", canal=canal, respuesta=resumen)
                    session.update_activity()
                    return resumen
            
            # No se pudo interpretar qué tipo de consulta es
            respuesta = "🤔 No he entendido qué quieres consultar."
            registrar_peticion(db, usuario.id, texto, "consulta", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

        # COMANDOS DE IMPUTACIÓN
        elif tipo_mensaje == "comando":
            tabla_actual = None
            try:
                with session.lock:
                    tabla_actual = leer_tabla_imputacion(session.driver)
            except Exception as e:
                print(f"[DEBUG]  No se pudo leer la tabla: {e}")
            
            ordenes = interpretar_con_gpt(texto, contexto, tabla_actual)
            
            if not ordenes:
                respuesta = "🤔 No he entendido qué quieres que haga."
                registrar_peticion(db, usuario.id, texto, "comando", canal=canal, respuesta=respuesta)
                session.update_activity()
                return respuesta

            # Verificar errores de validación
            if len(ordenes) == 1 and ordenes[0].get('accion') == 'error_validacion':
                mensaje_error = ordenes[0].get('mensaje', '🤔 No he entendido qué quieres que haga.')
                registrar_peticion(db, usuario.id, texto, "comando_invalido", canal=canal, respuesta=mensaje_error)
                session.update_activity()
                return mensaje_error
            
            # Verificar información incompleta
            if len(ordenes) == 1 and ordenes[0].get('accion') == 'info_incompleta':
                info_parcial = ordenes[0].get('info_parcial', {})
                que_falta = ordenes[0].get('que_falta', '')
                mensaje = ordenes[0].get('mensaje', '🤔 Falta información.')
                
                conversation_state_manager.guardar_info_incompleta(user_id, info_parcial, que_falta)
                
                registrar_peticion(db, usuario.id, texto, "info_incompleta", canal=canal, respuesta=mensaje)
                session.update_activity()
                return mensaje

            # Ejecutar órdenes
            return ejecutar_ordenes_y_generar_respuesta(ordenes, texto, session, contexto, 
                                                        db, usuario, user_id, canal)

        else:
            respuesta = "No he entendido el tipo de mensaje."
            registrar_peticion(db, usuario.id, texto, "desconocido", canal=canal, respuesta=respuesta)
            session.update_activity()
            return respuesta

    except Exception as e:
        error_msg = f" Error procesando la solicitud: {e}"
        registrar_peticion(db, usuario.id, texto, "error", canal=canal, 
                         respuesta=error_msg, estado="error")
        return error_msg


async def procesar_mensaje_usuario(texto: str, user_id: str, db: Session, canal: str = "webapp"):
    """Versión asíncrona que ejecuta el procesamiento en thread pool"""
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


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.post("/chats")
async def chat(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    texto = data.get("message", "").strip()
    user_id = data.get("user_id", "web_user_default")
    wa_id = data.get("wa_id", "").strip()
    
    # Auto-detectar WhatsApp
    if not wa_id and user_id and user_id.isdigit() and 10 <= len(user_id) <= 15:
        wa_id = user_id
    
    # Credenciales desde Agente Co
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    agente_co_user_id = data.get("agente_co_user_id", "").strip()
    
    # ---------------------------------------------------------
    # LOGIN DESDE AGENTE CO (WEBAPP)
    # ---------------------------------------------------------
    if username and password and agente_co_user_id:
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
            success, mensaje = await loop.run_in_executor(
                executor,
                lambda: hacer_login_con_lock(session, username, password)
            )
            
            if success:
                session.is_logged_in = True
                usuario = obtener_usuario_por_origen(db, app_id=agente_co_user_id)
                
                if not usuario:
                    usuario = crear_usuario(db, app_id=agente_co_user_id, canal="webapp")
                
                usuario.establecer_credenciales_intranet(username, password)
                db.commit()
                
                return JSONResponse({
                    "success": True,
                    "message": " Credenciales verificadas y guardadas correctamente",
                    "username": username,
                    "gestiondeverdad_user_id": usuario.id
                })
            else:
                return JSONResponse({
                    "success": False,
                    "error": "Usuario o contraseña incorrectos"
                }, status_code=401)
        
        except Exception as e:
            return JSONResponse({
                "success": False,
                "error": f"Error al verificar credenciales: {str(e)}"
            }, status_code=500)

    # ---------------------------------------------------------
    # WHATSAPP
    # ---------------------------------------------------------
    if wa_id:
        if not texto:
            return JSONResponse({"reply": "No he recibido ningún mensaje."})
        
        usuario_wa = obtener_usuario_por_origen(db, wa_id=wa_id)
        
        if not usuario_wa:
            usuario_wa = crear_usuario(db, wa_id=wa_id, canal="whatsapp")
        
        # -----------------------------------------------------
        # REGISTRO DE CREDENCIALES SI NO EXISTEN
        # -----------------------------------------------------
        if not usuario_wa.username_intranet or not usuario_wa.password_intranet:
            credenciales = extraer_credenciales_con_gpt(texto)
            
            if credenciales["ambos"]:
                loop = asyncio.get_event_loop()
                session = await loop.run_in_executor(
                    executor,
                    lambda: browser_pool.get_session(wa_id)
                )
                
                if not session or not session.driver:
                    return JSONResponse({"reply": " No he podido iniciar el navegador."})
                
                try:
                    success, mensaje = await loop.run_in_executor(
                        executor,
                        lambda: hacer_login_con_lock(
                            session,
                            credenciales["username"],
                            credenciales["password"]
                        )
                    )
                    
                    if success:
                        session.is_logged_in = True
                        usuario_wa.establecer_credenciales_intranet(
                            credenciales["username"], 
                            credenciales["password"]
                        )
                        db.commit()
                        
                        registrar_peticion(
                            db,
                            usuario_wa.id,
                            texto,
                            "registro_whatsapp",
                            canal="whatsapp",
                            respuesta="Credenciales guardadas exitosamente"
                        )
                        
                        return JSONResponse({
                            "reply": (
                                " *¡Credenciales guardadas correctamente!*\n\n"
                                f"✓ Usuario: *{credenciales['username']}*\n"
                                "✓ Contraseña: ******\n\n"
                                " Ya puedes empezar a usar el bot. ¿En qué puedo ayudarte?"
                            )
                        })
                    else:
                        return JSONResponse({
                            "reply": (
                                " *Error de login*\n\n"
                                "Las credenciales no son correctas."
                            )
                        })
                
                except Exception as e:
                    return JSONResponse({"reply": f" Error: {str(e)}"})
            
            else:
                return JSONResponse({
                    "reply": (
                        "👋 *¡Hola!* Aún no tengo tus credenciales de GestiónITT.\n\n"
                        " Envíamelas así:\n"
                        "```\n"
                        "Usuario: tu_usuario  Contraseña: tu_contraseña (todo sin tabular)\n"
                        "```"
                    )
                })
        # 🔐 ASEGURAR LOGIN Y NAVEGACIÓN BASE
        session = browser_pool.get_session(wa_id)
        if not session or not session.driver:
            return JSONResponse({"reply": " No he podido iniciar el navegador."})

        #  VERIFICAR SI ESTÁ CAMBIANDO CREDENCIALES (antes de hacer login con las viejas)
        if credential_manager.esta_cambiando_credenciales(wa_id):
            _, mensaje, _ = manejar_cambio_credenciales(texto, wa_id, usuario_wa, db, "whatsapp")
            session.is_logged_in = False
            return JSONResponse({"reply": mensaje})

        username, password = obtener_credenciales(db, wa_id, canal="whatsapp")
        if username and password:
            success, mensaje, debe_continuar = realizar_login_inicial(
                session,
                wa_id,
                username,
                password,
                usuario_wa,
                texto,
                db,
                "whatsapp"
            )

            if not debe_continuar:
                return JSONResponse({"reply": mensaje})

        # -----------------------------------------------------
        # ⏳ MENSAJE PREVIO + BACKGROUND TASK (WHATSAPP)
        # -----------------------------------------------------
        #  Si tiene pregunta pendiente, procesar respuesta directamente
        if conversation_state_manager.tiene_pregunta_pendiente(wa_id):
            respuesta = await procesar_mensaje_usuario(
                texto, wa_id, db, canal="whatsapp"
            )
            return JSONResponse({"reply": respuesta})
        
        #  Si NO tiene pregunta pendiente, clasificar para decidir flujo
        tipo_mensaje = clasificar_mensaje(texto)  #  UNA SOLA CLASIFICACIÓN

        if tipo_mensaje in ("consulta", "comando"):
            #  Lanzar procesamiento en background (SIN db)
            asyncio.create_task(
                procesar_whatsapp_en_background(texto, wa_id)
            )

            # 👇 RESPUESTA INMEDIATA (WhatsApp)
            return JSONResponse({
                "reply": "⏳ *Estoy trabajando en ello…*"
            })
        
        #  Para conversación/ayuda, procesar directamente SIN clasificar de nuevo
        elif tipo_mensaje == "ayuda":
            respuesta = mostrar_comandos()
            registrar_peticion(db, usuario_wa.id, texto, "ayuda", canal="whatsapp", respuesta=respuesta)
            session.update_activity()
            return JSONResponse({"reply": respuesta})
        
        elif tipo_mensaje == "conversacion":
            respuesta = responder_conversacion(texto, wa_id)
            registrar_peticion(db, usuario_wa.id, texto, "conversacion", canal="whatsapp", respuesta=respuesta)
            session.update_activity()
            return JSONResponse({"reply": respuesta})
        
        # Fallback para otros tipos
        else:
            respuesta = await procesar_mensaje_usuario(
                texto, wa_id, db, canal="whatsapp"
            )
            return JSONResponse({"reply": respuesta})

    # ---------------------------------------------------------
    # WEBAPP NORMAL (sin WhatsApp, sin login inicial)
    # ---------------------------------------------------------
    if not texto:
        return JSONResponse({"reply": "No he recibido ningún mensaje."})
    
    # Procesar mensaje para webapp
    respuesta = await procesar_mensaje_usuario(texto, user_id, db, canal="webapp")
    return JSONResponse({"reply": respuesta})

    
async def procesar_whatsapp_en_background(texto: str, wa_id: str):
    db = SessionLocal()
    try:
        respuesta = await procesar_mensaje_usuario(
            texto, wa_id, db, canal="whatsapp"
        )

        enviar_whatsapp(wa_id, respuesta)

    except Exception:
        print("[BACKGROUND ERROR]  Excepción en background:")
        traceback.print_exc()  #  ESTO ES CLAVE

        enviar_whatsapp(
            wa_id,
            " Ha ocurrido un error procesando tu solicitud."
        )

    finally:
        db.close()


def enviar_whatsapp(wa_id: str, mensaje: str):
    """
    Envía un mensaje de WhatsApp usando Green API
    """
    try:
        url = (
            f"https://api.green-api.com/waInstance{GREEN_API_INSTANCE_ID}"
            f"/sendMessage/{GREEN_API_TOKEN}"
        )

        payload = {
            "chatId": f"{wa_id}@c.us",
            "message": mensaje
        }

        response = requests.post(url, json=payload, timeout=15)

        if response.status_code != 200:
            print(f"[GREEN API]  Error {response.status_code}: {response.text}")
        else:
            print(f"[GREEN API]  Mensaje enviado a {wa_id}")

    except Exception as e:
        print(f"[GREEN API]  Excepción enviando mensaje: {e}")


@app.get("/stats")
async def stats():
    """ Estadísticas del pool de navegadores y historiales conversacionales"""
    from ai import obtener_stats_historiales
    
    browser_stats = browser_pool.get_stats()
    conversation_stats = obtener_stats_historiales()
    
    return JSONResponse({
        "browser_pool": browser_stats,
        "conversaciones": conversation_stats
    })


@app.post("/close-session/{user_id}")
async def close_user_session(user_id: str):
    """Cerrar sesión de un usuario"""
    browser_pool.close_session(user_id)
    return JSONResponse({"status": "ok", "message": f"Sesión de {user_id} cerrada"})


@app.on_event("shutdown")
def shutdown_event():
    print("[SERVER] 🛑 Apagando servidor, cerrando todos los navegadores...")
    browser_pool.close_all()
    executor.shutdown(wait=True)


#  Manejo de señales para cierre limpio (Ctrl+C, kill)
import signal
import sys
import os

def signal_handler(signum, frame):
    print(f"\n[SERVER] 🛑 Señal {signum} recibida, cerrando...")
    browser_pool.close_all()
    # En lugar de sys.exit(), dejamos que uvicorn maneje el cierre
    os._exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
