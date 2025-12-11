"""
Generador de respuestas naturales usando GPT.
Incluye conversación general y confirmación de acciones ejecutadas.
"""

from datetime import datetime
from config import settings


# Historial conversacional para GPT (global para mantener contexto)
historial_conversacion = []


def generar_respuesta_natural(acciones_ejecutadas, entrada_usuario, contexto=None):
    """
    Usa GPT para generar una respuesta natural basada en las acciones ejecutadas.
    
    Args:
        acciones_ejecutadas: Lista de mensajes de acciones completadas
        entrada_usuario: Mensaje original del usuario
        contexto: Diccionario con contexto de la sesión (opcional)
        
    Returns:
        str: Respuesta natural y amigable
    """
    if not acciones_ejecutadas:
        return "No he entendido qué quieres que haga. ¿Podrías reformularlo?"
    
    # 🔥 Extraer fecha si viene en el formato [FECHA:dd/mm/yyyy]
    fecha_imputacion = None
    acciones_limpias = []
    for acc in acciones_ejecutadas:
        if "[FECHA:" in acc:
            # Extraer fecha
            import re
            match = re.search(r'\[FECHA:(\d{2}/\d{2}/\d{4})\]', acc)
            if match:
                fecha_imputacion = match.group(1)
            # Limpiar el mensaje
            acc_limpia = re.sub(r'\[FECHA:[^\]]+\]', '', acc).strip()
            acciones_limpias.append(acc_limpia)
        else:
            acciones_limpias.append(acc)
    
    # Crear resumen de acciones
    resumen_acciones = "\n".join([f"- {acc}" for acc in acciones_limpias])
    
    # 🆕 Si hay nodo_padre en el contexto (Y NO es __buscar__), añadirlo a la información
    info_adicional = ""
    if contexto and contexto.get("nodo_padre_actual"):
        nodo_padre = contexto.get("nodo_padre_actual")
        # 🚫 Ignorar si es la señal interna __buscar__
        if nodo_padre != "__buscar__":
            proyecto = contexto.get("proyecto_actual", "proyecto")
            info_adicional = f"\n\n⚠️ IMPORTANTE: El proyecto '{proyecto}' pertenece a '{nodo_padre}'. Debes mencionar esto en tu respuesta."
    
    # 🔥 Si hay fecha de imputación, añadirla
    if fecha_imputacion:
        info_adicional += f"\n\n📅 FECHA IMPORTANTE: Las horas se imputaron para el día {fecha_imputacion}. Debes mencionar esta fecha EXACTA en tu respuesta, NO menciones 'el lunes de esa semana' ni ningún otro día."
    
    prompt = f"""Eres un asistente virtual amigable de imputación de horas laborales.

El usuario te dijo: "{entrada_usuario}"

Has ejecutado las siguientes acciones:
{resumen_acciones}{info_adicional}

Genera una respuesta natural, breve y amigable (máximo 2-3 líneas) confirmando lo que has hecho.
Usa un tono conversacional, cercano y profesional. Puedes usar emojis ocasionalmente.
No inventes información que no esté en las acciones ejecutadas.

Ejemplos de buen estilo:
- "¡Listo! He imputado 8 horas en Desarrollo para hoy y lo he guardado todo."
- "Perfecto, ya tienes toda la semana imputada en el proyecto Estudio. He guardado los cambios."
- "He iniciado tu jornada laboral. ¡A trabajar! 💪"

Respuesta:"""
    
    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un asistente virtual amigable y profesional que confirma tareas completadas de forma natural."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        respuesta = response.choices[0].message.content.strip()
        return respuesta
    
    except Exception as e:
        # Fallback: si falla GPT, unir las respuestas simples (ya limpias)
        return " · ".join(acciones_limpias)


def responder_conversacion(texto):
    """
    Usa GPT para responder a saludos, preguntas generales, etc.
    Mantiene contexto de la conversación.
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        str: Respuesta conversacional natural
    """
    global historial_conversacion
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    # Añadir mensaje del usuario al historial
    historial_conversacion.append({"role": "user", "content": texto})
    
    # Limitar historial a últimos 20 mensajes para no consumir muchos tokens
    if len(historial_conversacion) > 20:
        historial_conversacion = historial_conversacion[-20:]
    
    # System prompt solo la primera vez o si es un saludo explícito
    es_saludo_explicito = any(palabra in texto.lower() for palabra in ["hola", "buenos días", "buenas tardes", "buenas noches", "hey", "qué tal"])
    
    if len(historial_conversacion) <= 1 or es_saludo_explicito:
        system_content = f"""Eres un asistente virtual amigable especializado en gestión de imputación de horas laborales.

Hoy es {hoy} ({dia_semana}).

Si el usuario te saluda por primera vez, preséntate brevemente. 
Si ya has conversado con el usuario y te vuelve a saludar, responde de forma natural sin volver a presentarte.
Si el usuario NO te saluda, NO le saludes tú tampoco. Ve directo al punto.
Responde de forma natural, amigable y concisa."""
    else:
        system_content = f"""Eres un asistente virtual amigable especializado en gestión de imputación de horas laborales.

Hoy es {hoy} ({dia_semana}).

Estás en medio de una conversación. NO te presentes de nuevo, NO saludes, solo responde a la pregunta de forma natural y directa.
Si te pregunta sobre algo externo (noticias, clima, información general), responde normalmente."""
    
    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": system_content}
            ] + historial_conversacion,
            temperature=0.7,
            max_tokens=200
        )
        
        respuesta = response.choices[0].message.content.strip()
        
        # Añadir respuesta al historial
        historial_conversacion.append({"role": "assistant", "content": respuesta})
        
        return respuesta
    
    except Exception as e:
        return "Disculpa, he tenido un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"


def generar_resumen_natural(info_horas, consulta_usuario):
    """
    Mejora el formato de la información de horas para hacerla más legible en web.
    NO modifica los datos, solo mejora la presentación con formato HTML/Markdown.
    
    Args:
        info_horas: Resumen estructurado de horas (ya formateado con emojis)
        consulta_usuario: Pregunta original del usuario
        
    Returns:
        str: El mismo contenido con mejor formato para web
    """
    # Si ya tiene emojis y formato, simplemente añadir saltos de línea HTML para mejor visualización en web
    # Convertir saltos de línea en <br> para HTML
    info_con_html = info_horas.replace("\n", "<br>")
    return info_con_html
