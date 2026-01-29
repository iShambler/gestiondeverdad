"""
Generador de respuestas naturales usando GPT.
Incluye conversación general y confirmación de acciones ejecutadas.

 MODIFICADO: Ahora incluye departamento y cliente en las respuestas
"""

from datetime import datetime
from config import settings
from utils.proyecto_utils import parsear_path_proyecto


#  Historial conversacional POR USUARIO (antes era global)
historiales_conversacion = {}  # user_id -> lista de mensajes


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
    
    #  Extraer fechas de cada acción y limpiar mensajes
    # Ahora mantenemos la fecha asociada a cada acción
    import re
    acciones_con_fecha = []
    
    for acc in acciones_ejecutadas:
        fecha = None
        if "[FECHA:" in acc:
            match = re.search(r'\[FECHA:(\d{2}/\d{2}/\d{4})\]', acc)
            if match:
                fecha = match.group(1)
            acc_limpia = re.sub(r'\[FECHA:[^\]]+\]', '', acc).strip()
        else:
            acc_limpia = acc
        
        # Guardar acción con su fecha si la tiene
        if fecha:
            acciones_con_fecha.append(f"{acc_limpia} (fecha: {fecha})")
        else:
            acciones_con_fecha.append(acc_limpia)
    
    # Crear resumen de acciones
    resumen_acciones = "\n".join([f"- {acc}" for acc in acciones_con_fecha])
    
    #  MEJORADO: Extraer información de jerarquía completa del proyecto
    info_adicional = ""
    if contexto:
        # Intentar obtener path completo primero (más información)
        path_completo = contexto.get("path_completo_actual")
        if path_completo:
            info = parsear_path_proyecto(path_completo)
            partes_jerarquia = []
            if info["departamento"]:
                partes_jerarquia.append(f"departamento '{info['departamento']}'")
            if info["cliente"]:
                partes_jerarquia.append(f"cliente '{info['cliente']}'")
            
            if partes_jerarquia:
                jerarquia_texto = " del ".join(partes_jerarquia)
                info_adicional = f"\n\n IMPORTANTE - JERARQUÍA DEL PROYECTO:\nEl proyecto '{info['nombre']}' pertenece al {jerarquia_texto}.\n SIEMPRE incluye el departamento y cliente en tu respuesta. Ejemplo: 'He imputado X horas en {info['nombre']} del {info['departamento'] or 'departamento'}" + (f" ({info['cliente']})" if info['cliente'] else "") + "'"
        
        # Fallback al método anterior si no hay path_completo
        elif contexto.get("nodo_padre_actual") and contexto.get("nodo_padre_actual") != "__buscar__":
            nodo_padre = contexto.get("nodo_padre_actual")
            proyecto = contexto.get("proyecto_actual", "proyecto")
            info_adicional = f"\n\n IMPORTANTE: El proyecto '{proyecto}' pertenece a '{nodo_padre}'. SIEMPRE menciona el departamento en tu respuesta."
    
    prompt = f"""Eres un asistente virtual amigable de imputación de horas laborales.

El usuario te dijo: "{entrada_usuario}"

Has ejecutado las siguientes acciones:
{resumen_acciones}{info_adicional}

Genera una respuesta natural, breve y amigable (máximo 2-3 líneas) confirmando lo que has hecho.

 REGLAS CRÍTICAS:
- NUNCA inventes fechas. USA EXACTAMENTE las fechas que aparecen en las acciones.
- Si hay VARIAS acciones con DIFERENTES fechas, menciona CADA fecha específica.
- NO digas "para esa misma fecha" si las fechas son diferentes.
- Usa formato de fecha legible (ej: "el 12/01" o "el lunes 12/01").
- Si no estás seguro de una fecha, NO la menciones, di solo "el lunes/martes/etc."
- Usa un tono conversacional, cercano y profesional. Puedes usar emojis ocasionalmente.
-  SIEMPRE incluye el departamento/área del proyecto en la respuesta si está disponible en la información.
-  RESPETA LA OPERACIÓN EXACTA: Si la acción dice "restado" o "quitado", usa ESE verbo. Si dice "sumado" o "añadido", usa ESE verbo. NO los confundas.
  Ejemplos CORRECTOS:
  - Acción: "Restado 2 horas" → Respuesta: "He restado/quitado 2 horas" 
  - Acción: "Sumado 3 horas" → Respuesta: "He sumado/añadido 3 horas" 
  - Acción: "Establecido a 5 horas" → Respuesta: "He establecido/puesto 5 horas totales" 
  Ejemplos INCORRECTOS:
  - Acción: "Restado 2 horas" → Respuesta: "He añadido 2 horas"  (confunde restar con añadir)
  - Acción: "Sumado 3 horas" → Respuesta: "He quitado 3 horas"  (confunde sumar con quitar)

Ejemplos de buen estilo completo (CON JERARQUÍA):
- "¡Listo! He imputado 8 horas en Desarrollo del Dpto. Comercial (Arelance) para hoy y lo he guardado todo."
- "Perfecto, he puesto 3h en Estudio del Departamento IDI para el 17/12. ¡Guardado! "
- "¡Hecho! He restado 4 horas del proyecto Formación (Staff) el lunes 12/01, dejando un total de 7 horas."
- "Perfecto, he quitado 2 horas de Eventos del Dpto. Marketing el viernes 16/01. "

Respuesta:"""
    
    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un asistente virtual amigable y profesional que confirma tareas completadas de forma natural. SIEMPRE incluyes el departamento/área del proyecto en tus respuestas."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        respuesta = response.choices[0].message.content.strip()
        return respuesta
    
    except Exception as e:
        # Fallback: si falla GPT, unir las acciones con fecha
        return " · ".join(acciones_con_fecha)


def responder_conversacion(texto, user_id="default"):
    """
    Usa GPT para responder a saludos, preguntas generales, etc.
    Mantiene contexto de la conversación POR USUARIO.
    
    Args:
        texto: Mensaje del usuario
        user_id: ID del usuario (requerido para mantener contexto separado)
        
    Returns:
        str: Respuesta conversacional natural
    """
    global historiales_conversacion
    
    #  Crear historial para este usuario si no existe
    if user_id not in historiales_conversacion:
        historiales_conversacion[user_id] = []
    
    historial_usuario = historiales_conversacion[user_id]
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    # Añadir mensaje del usuario al historial
    historial_usuario.append({"role": "user", "content": texto})
    
    # Limitar historial a últimos 20 mensajes para no consumir muchos tokens
    if len(historial_usuario) > 20:
        historial_usuario = historial_usuario[-20:]
        historiales_conversacion[user_id] = historial_usuario
    
    # System prompt solo la primera vez o si es un saludo explícito
    es_saludo_explicito = any(palabra in texto.lower() for palabra in ["hola", "buenos días", "buenas tardes", "buenas noches", "hey", "qué tal"])
    
    if len(historial_usuario) <= 1 or es_saludo_explicito:
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
            ] + historial_usuario,
            temperature=0.7,
            max_tokens=200
        )
        
        respuesta = response.choices[0].message.content.strip()
        
        # Añadir respuesta al historial del usuario
        historial_usuario.append({"role": "assistant", "content": respuesta})
        historiales_conversacion[user_id] = historial_usuario
        
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


def obtener_stats_historiales():
    """
    Obtiene estadísticas de los historiales conversacionales.
    
    Returns:
        dict: Estadísticas
    """
    global historiales_conversacion
    
    total_usuarios = len(historiales_conversacion)
    total_mensajes = sum(len(historial) for historial in historiales_conversacion.values())
    
    return {
        "usuarios_con_historial": total_usuarios,
        "total_mensajes": total_mensajes,
        "promedio_mensajes_por_usuario": round(total_mensajes / total_usuarios, 2) if total_usuarios > 0 else 0
    }
