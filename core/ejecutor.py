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
    volver_inicio,
    copiar_semana_anterior
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
            # 🔥 Llamar PRIMERO (para que lea la fecha anterior del contexto)
            resultado = seleccionar_fecha(driver, fecha, contexto)
            # 🔥 Actualizar contexto DESPUÉS
            contexto["fecha_seleccionada"] = fecha
            return resultado
        except Exception as e:
            return f"No he podido procesar la fecha: {e}"

    # 📂 Seleccionar proyecto
    elif accion == "seleccionar_proyecto":
        try:
            nombre = orden["parametros"].get("nombre")
            nodo_padre = orden["parametros"].get("nodo_padre")
            
            # 🔍 Debug: mostrar si hay nodo padre
            if nodo_padre:
                print(f"[DEBUG] 🎯 Seleccionando proyecto con jerarquía: '{nombre}' bajo '{nodo_padre}'")
            
            # Detectar si es para "borrar horas" (no tiene sentido crear proyecto para borrarlo)
            solo_existente = contexto.get("es_borrado_horas", False)
            if solo_existente:
                print(f"[DEBUG] 🧹 Modo borrar horas: solo buscar proyecto existente")
            
            # Desempaquetar 4 valores
            fila, mensaje, necesita_desambiguacion, coincidencias = seleccionar_proyecto(
                driver, wait, nombre, nodo_padre, contexto=contexto, solo_existente=solo_existente
            )
            
            # Si necesita desambiguación, devolver info especial
            if necesita_desambiguacion:
                return {
                    "tipo": "desambiguacion",
                    "proyecto": nombre,
                    "coincidencias": coincidencias
                }
            
            if fila:
                # ✅ Proyecto encontrado o creado correctamente
                contexto["fila_actual"] = fila
                contexto["proyecto_actual"] = nombre
                contexto["nodo_padre_actual"] = nodo_padre
                
                # Guardar último proyecto usado
                user_id = contexto.get("user_id")
                if user_id:
                    from conversation_state import conversation_state_manager
                    conversation_state_manager.guardar_ultimo_proyecto(user_id, nombre, nodo_padre)
                
                return mensaje
            else:
                # ❌ Proyecto NO encontrado - DETENER ejecución
                contexto["fila_actual"] = None
                contexto["proyecto_actual"] = None
                contexto["error_critico"] = True
                return mensaje
                
        except Exception as e:
            return f"Error seleccionando proyecto: {e}"

    # 🗑️ Eliminar línea
    elif accion == "eliminar_linea":
        try:
            # 🔧 FIX: Usar .get() para evitar KeyError si no hay parámetros
            parametros = orden.get("parametros", {})
            nombre = parametros.get("nombre") if parametros else None
            
            # 🆕 Si no se especificó nombre, usar el proyecto del contexto
            if not nombre:
                nombre = contexto.get("proyecto_actual")
            
            if not nombre:
                return "❌ No sé qué proyecto eliminar. Especifica el nombre del proyecto."
            
            # 🆕 Pasar la fila del contexto si existe (evita buscar de nuevo)
            fila_contexto = contexto.get("fila_actual")
            resultado = eliminar_linea_proyecto(driver, wait, nombre, fila_contexto)
            
            # 🆕 Limpiar el contexto después de eliminar
            contexto["fila_actual"] = None
            contexto["proyecto_actual"] = None
            
            # El flujo normal incluye guardar_linea después de eliminar_linea
            return resultado
                
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
            nodo_padre = contexto.get("nodo_padre_actual")

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
                # 🔥 GUARDAR FECHA FORMATEADA PARA EL MENSAJE
                fecha_formateada = fecha_obj.strftime("%d/%m/%Y")
            except Exception:
                dia = dia_param.lower()
                # 🔥 Usar fecha del contexto si existe
                fecha_contexto = contexto.get("fecha_seleccionada")
                if fecha_contexto:
                    fecha_formateada = fecha_contexto.strftime("%d/%m/%Y")
                else:
                    # Fallback: usar hoy
                    fecha_formateada = datetime.now().strftime("%d/%m/%Y")
            
            # 🆕 Guardar día en contexto
            user_id = contexto.get("user_id")
            if user_id:
                from conversation_state import conversation_state_manager
                conversation_state_manager.guardar_ultimo_proyecto(user_id, proyecto, nodo_padre, dia)
            
            # 🆕 Intentar imputar, si falla por StaleElement, re-buscar proyecto
            try:
                resultado = imputar_horas_dia(driver, wait, dia, horas, fila, proyecto, modo)
                # 🔥 AÑADIR FECHA AL RESULTADO para que el response generator la use
                return f"{resultado} [FECHA:{fecha_formateada}]"
            except Exception as e:
                if "stale element" in str(e).lower():
                    print(f"[DEBUG] 🔄 Elemento obsoleto detectado, re-buscando proyecto '{proyecto}'...")
                    # Re-buscar el proyecto
                    fila_nueva, mensaje, necesita_desamb, coincidencias = seleccionar_proyecto(driver, wait, proyecto, nodo_padre)
                    
                    if necesita_desamb:
                        return {
                            "tipo": "desambiguacion",
                            "proyecto": proyecto,
                            "coincidencias": coincidencias
                        }
                    
                    if fila_nueva:
                        contexto["fila_actual"] = fila_nueva
                        print(f"[DEBUG] ✅ Proyecto re-encontrado, reintentando imputación...")
                        resultado = imputar_horas_dia(driver, wait, dia, horas, fila_nueva, proyecto, modo)
                        return f"{resultado} [FECHA:{fecha_formateada}]"
                    else:
                        return f"❌ No he podido re-encontrar el proyecto '{proyecto}': {mensaje}"
                else:
                    raise

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

    # 📅 Copiar semana anterior
    elif accion == "copiar_semana_anterior":
        try:
            exito, mensaje, proyectos = copiar_semana_anterior(driver, wait, contexto)
            return mensaje
        except Exception as e:
            return f"❌ Error al copiar la semana anterior: {e}"

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
    
    # ==========================================================================
    # 🆕 PRE-PROCESAMIENTO: Detectar si GPT generó "toda la semana" como 5 imputar_horas_dia
    # Si es así, convertir a una sola acción imputar_horas_semana
    # ==========================================================================
    ordenes_procesadas = []
    i = 0
    while i < len(ordenes):
        orden = ordenes[i]
        
        # Detectar patrón: seleccionar_proyecto + 5x imputar_horas_dia (L-V)
        if orden.get("accion") == "seleccionar_proyecto":
            # Contar cuántos imputar_horas_dia consecutivos hay después
            dias_encontrados = set()
            j = i + 1
            while j < len(ordenes) and ordenes[j].get("accion") == "imputar_horas_dia":
                dia_param = ordenes[j].get("parametros", {}).get("dia", "")
                # Normalizar día (puede venir como fecha ISO o nombre)
                try:
                    fecha_obj = datetime.fromisoformat(dia_param)
                    dia = fecha_obj.strftime("%A").lower()
                    dias_map = {"monday": "lunes", "tuesday": "martes", "wednesday": "miércoles", 
                               "thursday": "jueves", "friday": "viernes"}
                    dia = dias_map.get(dia, dia)
                except:
                    dia = dia_param.lower()
                dias_encontrados.add(dia)
                j += 1
            
            # Si hay exactamente 5 días (L-V), es "toda la semana"
            dias_semana = {"lunes", "martes", "miércoles", "miercoles", "jueves", "viernes"}
            if len(dias_encontrados) >= 5 and dias_encontrados.intersection(dias_semana):
                print(f"[DEBUG] 🔄 Detectado patrón 'toda la semana' (5 imputar_horas_dia), convirtiendo a imputar_horas_semana")
                
                # Añadir seleccionar_proyecto
                ordenes_procesadas.append(orden)
                
                # Reemplazar los 5 imputar_horas_dia por UN imputar_horas_semana
                ordenes_procesadas.append({"accion": "imputar_horas_semana"})
                
                # Saltar los 5 imputar_horas_dia originales
                i = j
                continue
        
        ordenes_procesadas.append(orden)
        i += 1
    
    # Usar las órdenes procesadas
    ordenes = ordenes_procesadas
    
    # ==========================================================================
    # PRE-PROCESAMIENTO: Detectar si es "borrar horas de proyecto específico"
    # ==========================================================================
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
    
    # ==========================================================================
    # EJECUCIÓN
    # ==========================================================================
    for orden in ordenes:
        # Si hay un error crítico, detener ejecución
        if contexto.get("error_critico"):
            break
        
        # Limpiar flag después de usarlo
        if orden.get("accion") == "imputar_horas_dia":
            contexto["es_borrado_horas"] = False
            
        mensaje = ejecutar_accion(driver, wait, orden, contexto)
        
        # 🔥 DETECCIÓN DE DESAMBIGUACIÓN: Si la acción devuelve un dict con tipo="desambiguacion", DETENER
        if isinstance(mensaje, dict) and mensaje.get("tipo") == "desambiguacion":
            print(f"[DEBUG] ⏸️ Desambiguación detectada, deteniendo ejecución de acciones")
            respuestas.append(mensaje)
            break  # 🔥 DETENER aquí, no continuar con las siguientes acciones
        
        if mensaje:
            respuestas.append(mensaje)
    
    return respuestas
