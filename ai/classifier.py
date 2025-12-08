"""
Clasificador de mensajes de usuario.
Determina si un mensaje es un comando, una consulta o conversación general.
"""

from datetime import datetime
from config import settings


def clasificar_mensaje(texto):
    """
    Clasifica si el mensaje del usuario es:
    - 'comando': requiere ejecutar acciones de imputación
    - 'consulta': pide información sobre horas imputadas
    - 'conversacion': saludo, pregunta general o tema fuera del ámbito laboral
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        str: 'comando', 'consulta' o 'conversacion'
    """
    print(f"[DEBUG] 🔍 Clasificando: '{texto}'")
    
    # Keywords para detectar comandos de jornada sin ambigüedad
    keywords_jornada = [
        "iniciar jornada", "empezar jornada", "comenzar jornada", "inicia jornada",
        "finalizar jornada", "terminar jornada", "acabar jornada", "finaliza jornada", 
        "termina jornada", "acaba jornada",
        "finaliza el dia", "termina el dia", "acaba el dia",
        "finalizar el dia", "terminar el dia", "acabar el dia",
        "fin de jornada", "cierra jornada"
    ]
    
    texto_lower = texto.lower()
    
    # 🆕 COMANDO DE AYUDA - Prioridad máxima
    keywords_ayuda = [
        "ayuda", "help", "comandos", "qué puedes hacer", "que puedes hacer",
        "cómo funciona", "como funciona", "instrucciones", "guía", "guia"
    ]
    
    if any(keyword in texto_lower for keyword in keywords_ayuda):
        return "ayuda"
    
    # Si contiene keywords de jornada, es comando directo
    if any(keyword in texto_lower for keyword in keywords_jornada):
        return "comando"
    
    # Keywords para imputación
    keywords_imputacion = [
        "imput", "pon", "añade", "agrega", "quita", "resta", "borra",
        "horas", "proyecto", "guardar", "emitir"
    ]
    
    if any(keyword in texto_lower for keyword in keywords_imputacion):
        return "comando"
    
    # Keywords para consultas - Detectar solicitudes de información
    keywords_consulta = [
        "qué tengo", "que tengo", "dime", "qué he imputado", "que he imputado",
        "cuántas", "cuantas", "cuántas horas", "cuantas horas",
        "ver", "mostrar", "dame", "info", "consulta", 
        "resumen", "resume", "resumíme", "qué hice", "que hice",
        "he hecho", "tengo hecho"
    ]
    
    # Detectar consultas por keywords
    if any(keyword in texto_lower for keyword in keywords_consulta):
        print(f"[DEBUG] 📊 Detectada keyword de consulta")
        return "consulta"
    
    # DETECCIÓN ADICIONAL: Frases tipo "cuántas horas..."
    if ("cuantas" in texto_lower or "cuántas" in texto_lower) and "horas" in texto_lower:
        print(f"[DEBUG] 📊 Detectada consulta de horas")
        return "consulta"
    
    # Si menciona "semana" + palabras de consulta = es una consulta
    if "semana" in texto_lower:
        print(f"[DEBUG] 📅 Detectado 'semana' en el texto")
        keywords_consulta_semana = [
            "resumen", "resume", "resumíme", "qué tengo", "dime", "qué he imputado",
            "cuántas", "ver", "mostrar", "dame", "info", "consulta", "cuenta"
        ]
        
        matches = [k for k in keywords_consulta_semana if k in texto_lower]
        print(f"[DEBUG] Keywords de consulta encontradas: {matches}")
        
        if matches:
            print(f"[DEBUG] ✅ Clasificado como CONSULTA por keywords: semana + {matches}")
            return "consulta"
        else:
            print(f"[DEBUG] ⚠️ Tiene 'semana' pero no keywords específicas, pasando a GPT...")
    
    # Si no matchea keywords claras, usar GPT
    hoy = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
Clasifica el siguiente mensaje en UNA de estas tres categorías:

1️⃣ "comando" → El usuario quiere HACER algo:
   - Imputar horas, modificar datos, iniciar/finalizar jornada
   - Ejemplos: "pon 8 horas", "imputa en desarrollo", "finaliza jornada"

2️⃣ "consulta" → El usuario quiere VER/SABER información:
   - Resúmenes, qué tiene imputado, cuántas horas, ver semanas/días
   - Ejemplos: "resumen de esta semana", "qué tengo imputado", "cuántas horas", "cuántas horas tengo hoy", "cuántas horas he hecho"

3️⃣ "conversacion" → Saludos o temas NO relacionados con trabajo:
   - Ejemplos: "hola", "quién es Messi", "capital de Francia"

⚠️ IMPORTANTE: Si pregunta por información de horas/semanas/proyectos = "consulta"
Si quiere modificar/añadir/cambiar horas = "comando"

Responde SOLO una palabra: "comando", "consulta" o "conversacion".

Mensaje: "{texto}"
Respuesta:"""

    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un clasificador inteligente de intenciones de usuario."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )

        clasificacion = response.choices[0].message.content.strip().lower()
        print(f"[DEBUG] 🧠 GPT clasificó '{texto[:50]}...' como: {clasificacion}")
        return clasificacion

    except Exception as e:
        print(f"[DEBUG] Error en clasificar_mensaje: {e}")
        return "conversacion"
