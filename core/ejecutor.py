"""
Ejecutor de acciones.
Coordina la ejecución de comandos interpretados por la IA.
"""

import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from web_automation import (
    seleccionar_fecha,
    seleccionar_proyecto,
    imputar_horas_dia,
    imputar_horas_semana,
    borrar_todas_horas_dia,
    eliminar_linea_proyecto,
    iniciar_jornada,
    finalizar_jornada,
    guardar_linea,
    emitir_linea,
    volver_inicio
)


def ejecutar_accion(driver, wait, orden, contexto):
    """
    Ejecuta una acción específica recibida desde el intérprete de IA.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        orden: Diccionario con la acción y sus parámetros
               {'accion': 'nombre_accion', 'parametros': {...}}
        contexto: Diccionario que mantiene estado entre acciones
                  {'fila_actual': WebElement, 'proyecto_actual': str, 'error_critico': bool}
    
    Returns:
        str: Mensaje descriptivo del resultado de la acción
    """
    accion = orden.get("accion")

    # 🕒 Iniciar jornada
    if accion == "iniciar_jornada":
        return iniciar_jornada(driver, wait)

    # 🕓 Finalizar jornada
    elif accion == "finalizar_jornada":
        return finalizar_jornada(driver, wait)

    # 📅 Seleccionar fecha
    elif accion == "seleccionar_fecha":
        try:
            fecha = datetime.fromisoformat(orden["parametros"]["fecha"])
            return seleccionar_fecha(driver, fecha)
        except Exception as e:
            return f"No he podido procesar la fecha: {e}"

    # 📂 Seleccionar proyecto
    elif accion == "seleccionar_proyecto":
        try:
            nombre = orden["parametros"].get("nombre")
            fila, mensaje = seleccionar_proyecto(driver, wait, nombre)
            
            if fila:
                # ✅ Proyecto encontrado o creado correctamente
                contexto["fila_actual"] = fila
                contexto["proyecto_actual"] = nombre
                return mensaje
            else:
                # ❌ Proyecto NO encontrado - DETENER ejecución
                contexto["fila_actual"] = None
                contexto["proyecto_actual"] = None
                contexto["error_critico"] = True  # Marcar error crítico
                return mensaje  # El mensaje ya viene con el error
                
        except Exception as e:
            return f"Error seleccionando proyecto: {e}"

    # 🗑️ Eliminar línea
    elif accion == "eliminar_linea":
        try:
            nombre = orden["parametros"].get("nombre")
            resultado = eliminar_linea_proyecto(driver, wait, nombre)
            
            # Auto-guardar después de eliminar
            time.sleep(0.5)
            try:
                btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btGuardarLinea")))
                btn_guardar.click()
                time.sleep(1.5)
                return resultado + " y he guardado los cambios"
            except:
                return resultado + " (recuerda guardar los cambios)"
                
        except Exception as e:
            return f"Error eliminando línea: {e}"

    # 🗑️ Borrar todas las horas de un día
    elif accion == "borrar_todas_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            
            # Si GPT devuelve una fecha ISO → convertir a nombre de día
            try:
                fecha_obj = datetime.fromisoformat(dia_param)
                dia = fecha_obj.strftime("%A").lower()
                dias_map = {
                    "monday": "lunes",
                    "tuesday": "martes",
                    "wednesday": "miércoles",
                    "thursday": "jueves",
                    "friday": "viernes"
                }
                dia = dias_map.get(dia, dia)
            except Exception:
                dia = dia_param.lower()
            
            return borrar_todas_horas_dia(driver, wait, dia)
        
        except Exception as e:
            return f"Error al borrar horas: {e}"

    # ⏱️ Imputar horas del día
    elif accion == "imputar_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            horas = float(orden["parametros"].get("horas", 0))
            modo = orden["parametros"].get("modo", "sumar")
            fila = contexto.get("fila_actual")
            proyecto = contexto.get("proyecto_actual", "Desconocido")

            if not fila:
                return "Necesito que primero selecciones un proyecto antes de imputar horas"

            # Si GPT devuelve una fecha ISO → convertir a nombre de día
            try:
                fecha_obj = datetime.fromisoformat(dia_param)
                dia = fecha_obj.strftime("%A").lower()
                dias_map = {
                    "monday": "lunes",
                    "tuesday": "martes",
                    "wednesday": "miércoles",
                    "thursday": "jueves",
                    "friday": "viernes"
                }
                dia = dias_map.get(dia, dia)
            except Exception:
                dia = dia_param.lower()

            return imputar_horas_dia(driver, wait, dia, horas, fila, proyecto, modo)

        except Exception as e:
            return f"Error al imputar horas: {e}"

    # ⏱️ Imputar horas semanales
    elif accion == "imputar_horas_semana":
        proyecto = contexto.get("proyecto_actual")
        if not proyecto:
            return "❌ No sé en qué proyecto quieres imputar. Dímelo, por favor."

        fila = contexto.get("fila_actual")
        if not fila:
            return f"❌ No he podido seleccionar el proyecto '{proyecto}'. ¿Estás en la pantalla de imputación?"

        return imputar_horas_semana(driver, wait, fila, nombre_proyecto=proyecto)

    # 💾 Guardar línea
    elif accion == "guardar_linea":
        return guardar_linea(driver, wait)

    # 📤 Emitir línea
    elif accion == "emitir_linea":
        return emitir_linea(driver, wait)

    # ↩️ Volver a inicio
    elif accion == "volver":
        return volver_inicio(driver)

    # ❓ Desconocido
    else:
        return "No he entendido esa instrucción"


def ejecutar_lista_acciones(driver, wait, ordenes, contexto=None):
    """
    Ejecuta una lista de acciones en secuencia.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        ordenes: Lista de diccionarios con acciones
        contexto: Diccionario de contexto (opcional, se crea si no existe)
        
    Returns:
        list: Lista de mensajes de respuesta de cada acción
    """
    if contexto is None:
        contexto = {"fila_actual": None, "proyecto_actual": None, "error_critico": False}
    
    respuestas = []
    
    for orden in ordenes:
        # Si hay un error crítico, detener ejecución
        if contexto.get("error_critico"):
            break
            
        mensaje = ejecutar_accion(driver, wait, orden, contexto)
        if mensaje:
            respuestas.append(mensaje)
    
    return respuestas
