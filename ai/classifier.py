"""
Clasificador de mensajes de usuario.
Determina si un mensaje es un comando, una consulta o conversación general.
"""

from datetime import datetime
from config import settings
from config.constants import Constants


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
    
    # Keywords importadas desde constants.py
    keywords_jornada = Constants.KEYWORDS_JORNADA
    
    texto_lower = texto.lower()
    print(f"[DEBUG] 🔍 Texto normalizado: '{texto_lower}'")
    
    # 🆕 COMANDO DE AYUDA - Prioridad máxima
    keywords_ayuda = [
        "ayuda", "help", "comandos", "qué puedes hacer", "que puedes hacer",
        "cómo funciona", "como funciona", "instrucciones", "guía", "guia"
    ]
    
    if any(keyword in texto_lower for keyword in keywords_ayuda):
        return "ayuda"
    
    # 🆕 LISTAR PROYECTOS - Nueva categoría
    keywords_listar_proyectos = [
        "qué proyectos", "que proyectos", "q proyectos",  # Variante abreviada
        "lista de proyectos", "listar proyectos",
        "dime los proyectos", "muéstrame los proyectos", "muestrame los proyectos",
        "proyectos disponibles", "ver proyectos", "mostrar proyectos",
        "qué proyectos tengo", "que proyectos tengo", "q proyectos tengo",
        "cuales proyectos", "cuáles proyectos",
        "proyectos hay", "cuántos proyectos", "cuantos proyectos",
        "dame proyectos", "dame los proyectos",
        "listar los proyectos", "ver los proyectos"
    ]
    
    if any(keyword in texto_lower for keyword in keywords_listar_proyectos):
        print(f"[DEBUG] ✅ Detectado 'listar_proyectos' por keywords")
        return "listar_proyectos"
    
    # Si contiene keywords de jornada, es comando directo
    if any(keyword in texto_lower for keyword in keywords_jornada):
        return "comando"
    
    # Keywords importadas desde constants.py
    keywords_imputacion = Constants.KEYWORDS_IMPUTACION
    
    if any(keyword in texto_lower for keyword in keywords_imputacion):
        return "comando"
    
    # Keywords importadas desde constants.py
    keywords_consulta = Constants.KEYWORDS_CONSULTA
    
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
