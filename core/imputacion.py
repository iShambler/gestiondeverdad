"""
Lógica principal de imputación.
Coordina el flujo completo: clasificar → interpretar → ejecutar → responder.

 MODIFICADO: Añadido soporte para consultas de mes
"""

from datetime import datetime

from ai import (
    clasificar_mensaje,
    interpretar_con_gpt,
    generar_respuesta_natural,
    responder_conversacion,
    interpretar_consulta,
    generar_resumen_natural
)
from core.ejecutor import ejecutar_lista_acciones
from core.consultas import consultar_dia, consultar_semana, consultar_mes


def procesar_mensaje(driver, wait, texto, contexto=None, user_id="local_user"):
    """
    Procesa un mensaje del usuario y ejecuta las acciones correspondientes.
    
    Flujo:
    1. Clasificar mensaje (comando/consulta/conversación)
    2. Si es conversación → responder naturalmente
    3. Si es consulta → obtener información y formatear
    4. Si es comando → interpretar → ejecutar → confirmar
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        texto: Mensaje del usuario
        contexto: Diccionario de contexto (opcional)
        user_id: ID del usuario para mantener contexto de conversación (opcional)
        
    Returns:
        str: Respuesta generada para el usuario
    """
    if contexto is None:
        contexto = {"fila_actual": None, "proyecto_actual": None, "error_critico": False}
    
    # 1️⃣ Clasificar el tipo de mensaje
    tipo_mensaje = clasificar_mensaje(texto)
    
    # 2️⃣ Conversación general
    if tipo_mensaje == "conversacion":
        return responder_conversacion(texto, user_id)  #  Pasar user_id
    
    # 3️⃣ Consulta de información
    if tipo_mensaje == "consulta":
        consulta_info = interpretar_consulta(texto)
        
        if consulta_info:
            try:
                fecha = datetime.fromisoformat(consulta_info["fecha"])
                
                if consulta_info.get("tipo") == "dia":
                    # Consulta de un día específico
                    info_bruta = consultar_dia(driver, wait, fecha)
                    return generar_resumen_natural(info_bruta, texto)
                    
                elif consulta_info.get("tipo") == "semana":
                    # Consulta de una semana completa
                    info_bruta = consultar_semana(driver, wait, fecha)
                    return generar_resumen_natural(info_bruta, texto)
                
                elif consulta_info.get("tipo") == "mes":
                    #  Consulta de un mes completo
                    mes = fecha.month
                    anio = fecha.year
                    info_bruta = consultar_mes(driver, wait, mes, anio)
                    return generar_resumen_natural(info_bruta, texto)
                    
                else:
                    return "No he entendido si preguntas por un día, semana o mes."
                    
            except Exception as e:
                return f"No he podido consultar: {e}"
        else:
            return "No he entendido qué quieres consultar. ¿Podrías ser más específico?"
    
    # 4️⃣ Comando (imputación, modificación, etc.)
    if tipo_mensaje == "comando":
        # Interpretar comando con GPT
        ordenes = interpretar_con_gpt(texto)
        
        if not ordenes:
            return "No he entendido qué quieres que haga. ¿Podrías reformularlo?"
        
        # Reordenar: siempre primero la fecha, luego el resto
        ordenes = sorted(ordenes, key=lambda o: 0 if o["accion"] == "seleccionar_fecha" else 1)
        
        # Ejecutar acciones
        respuestas = ejecutar_lista_acciones(driver, wait, ordenes, contexto)
        
        # Generar respuesta natural
        if respuestas:
            return generar_respuesta_natural(respuestas, texto)
        else:
            return "No pude ejecutar ninguna acción."
    
    # Fallback
    return "No he entendido tu mensaje. ¿Podrías reformularlo?"


def iniciar_sesion_automatica(driver, wait, username=None, password=None):
    """
    Realiza el login automático al iniciar el asistente.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        username: Usuario (opcional, usa settings por defecto)
        password: Contraseña (opcional, usa settings por defecto)
        
    Returns:
        tuple: (success: bool, message: str)
    """
    from web_automation import hacer_login
    return hacer_login(driver, wait, username, password)


def mostrar_mensaje_bienvenida():
    """
    Muestra el mensaje de bienvenida al usuario.
    """
    print("\n" + "="*60)
    print("👋 ¡Hola! Soy tu asistente de imputación de horas")
    print("="*60)
    print("\nYa he iniciado sesión en el sistema por ti.")
    print("\nPuedes pedirme cosas como:")
    print("  • 'Imputa 8 horas en Desarrollo hoy'")
    print("  • 'Abre el proyecto Estudio y pon toda la semana'")
    print("  • 'Añade 2.5 horas en Dirección el lunes y emítelo'")
    print("  • 'Inicia la jornada'")
    print("  • 'Resumen de esta semana'")
    print("  • 'Resumen de este mes'")
    print("  • 'Cuántas horas tengo hoy'")
    print("\nEscribe 'salir' cuando quieras terminar.\n")
    print("="*60 + "\n")


def loop_interactivo(driver, wait):
    """
    Loop principal de interacción con el usuario.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
    """
    contexto = {"fila_actual": None, "proyecto_actual": None, "error_critico": False}
    
    while True:
        try:
            texto = input("💬 Tú: ")
            
            # Comando de salida
            if texto.lower() in ["salir", "exit", "quit"]:
                print("\n👋 ¡Hasta pronto! Cerrando el navegador...")
                break
            
            # Procesar mensaje
            respuesta = procesar_mensaje(driver, wait, texto, contexto)
            print(f"\n Asistente: {respuesta}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 ¡Hasta pronto! Cerrando el navegador...")
            break
        except Exception as e:
            print(f"\n Error inesperado: {e}\n")
            # No romper el loop, continuar
