"""
Clasificador de mensajes de usuario usando GPT-4o-mini.
Determina si un mensaje es un comando, consulta, conversación, ayuda o listar proyectos.
"""

from datetime import datetime
from config import settings
from config.constants import Constants


def clasificar_mensaje(texto):
    """
    Clasifica el mensaje del usuario usando GPT-4o-mini.
    
    Categorías posibles:
    - 'comando': requiere ejecutar acciones de imputación
    - 'consulta': pide información sobre horas imputadas O proyectos disponibles
    - 'conversacion': saludo, pregunta general o tema fuera del ámbito laboral
    - 'ayuda': solicita ayuda o lista de comandos
    
    Args:
        texto: Mensaje del usuario
        
    Returns:
        str: 'comando', 'consulta', 'conversacion' o 'ayuda'
    """
    print(f"[DEBUG] Clasificando con GPT: '{texto}'")
    
    texto_lower = texto.lower().strip()
    
    # 🆕 OPTIMIZACIÓN: Casos ultra-obvios sin GPT (opcional, pero ahorra latencia)
    # Solo los casos 100% seguros que no tienen ambigüedad
    if texto_lower in ["ayuda", "help", "comandos"]:
        print(f"[DEBUG]  Clasificación rápida: ayuda")
        return "ayuda"
    
    if texto_lower in ["hola", "buenos días", "buenas tardes", "buenas noches", "hey", "qué tal", "que tal"]:
        print(f"[DEBUG] Clasificación rápida: conversacion")
        return "conversacion"
    
    # Para todo lo demás, usar GPT
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")

    prompt = f"""
Clasifica el siguiente mensaje en UNA de estas categorías:

1️"comando" → El usuario quiere EJECUTAR una acción:
   - Imputar horas, modificar horas, eliminar horas
   - Iniciar/finalizar jornada
   - Guardar o emitir horas
   - Ejemplos: 
     * "pon 8 horas en desarrollo"
     * "imputa toda la semana en estudio"
     * "finaliza jornada"
     * "cambia las horas del lunes a 6"
     * "borra las horas de hoy"

2️"consulta" → El usuario quiere VER/CONSULTAR información:
   A) Sobre HORAS IMPUTADAS:
      - Ver resúmenes de horas
      - Preguntar qué tiene imputado
      - Consultar cuántas horas tiene
      - Ver información de días o semanas
   B) Sobre PROYECTOS DISPONIBLES:
      - Lista de proyectos
      - Qué proyectos hay
      - Ver proyectos disponibles
      - Proyectos en los que puede imputar
   - Ejemplos:
     * "resumen de esta semana" → consulta de horas
     * "qué tengo imputado hoy" → consulta de horas
     * "cuántas horas tengo el lunes" → consulta de horas
     * "lista de proyectos" → consulta de proyectos
     * "qué proyectos hay" → consulta de proyectos
     * "muéstrame los proyectos" → consulta de proyectos
     * "dime en qué proyectos puedo imputar" → consulta de proyectos

3️"conversacion" → Saludos, preguntas generales fuera del ámbito:
   - Saludos generales
   - Preguntas sobre temas externos
   - Conversación informal
   - Preguntas sobre cosas que NO sean horas ni proyectos disponibles
   - Ejemplos:
     * "hola"
     * "buenos días"
     * "quién es Messi"
     * "cuál es la capital de Francia"
     * "no veo el proyecto X" → problema técnico
     * "no encuentro X" → pregunta general

4️"ayuda" → Solicita ayuda o información sobre cómo usar el bot:
   - Ejemplos:
     * "ayuda"
     * "qué puedes hacer"
     * "cómo funciona esto"
     * "guía de uso"

CONTEXTO:
- Hoy es {hoy} ({dia_semana})

CRÍTICO: 
- Si pregunta por LISTA/PROYECTOS DISPONIBLES → "consulta"
- Si pregunta por información de HORAS/IMPUTACIONES → "consulta"
- Si pide hacer/modificar/añadir/cambiar → "comando"
- Si menciona "horas" en contexto de ver/mostrar → "consulta"
- Si menciona "horas" en contexto de poner/añadir → "comando"
- Si dice "no veo X", "dónde está X", "no encuentro X" → "conversacion"

Responde SOLO una palabra: "comando", "consulta", "conversacion" o "ayuda".

Mensaje: "{texto}"
Respuesta:"""

    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un clasificador experto de intenciones de usuario para un sistema de imputación de horas. Respondes SOLO con una palabra."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=15
        )

        clasificacion = response.choices[0].message.content.strip().lower()
        
        # Validar que la respuesta sea una de las categorías esperadas
        categorias_validas = ["comando", "consulta", "conversacion", "ayuda"]
        
        if clasificacion not in categorias_validas:
            print(f"[DEBUG] GPT devolvió clasificación inválida: '{clasificacion}', usando 'conversacion' por defecto")
            clasificacion = "conversacion"
        
        print(f"[DEBUG] 🧠 GPT clasificó '{texto[:50]}...' como: {clasificacion}")
        return clasificacion

    except Exception as e:
        print(f"[DEBUG] Error en clasificar_mensaje con GPT: {e}")
        print(f"[DEBUG] Usando clasificación por defecto: conversacion")
        return "conversacion"
