"""
Analizador de consultas sobre horas imputadas.
Extrae fechas y tipo de consulta (día o semana).
"""

import json
from datetime import datetime, timedelta
from config import settings


def interpretar_consulta(texto):
    """
    Interpreta consultas sobre horas imputadas o proyectos disponibles.
    
    Args:
        texto: Consulta del usuario
        
    Returns:
        dict: {'fecha': 'YYYY-MM-DD', 'tipo': 'dia'|'semana'|'listar_proyectos'} o None
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    hoy_obj = datetime.now()
    dia_semana = hoy_obj.strftime("%A")
    
    # Calcular ejemplos dinámicos
    ayer = (hoy_obj - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Calcular jueves pasado
    weekday_hoy = hoy_obj.weekday()  # 0=Monday, 6=Sunday
    weekday_jueves = 3  # Thursday
    if weekday_hoy > weekday_jueves:
        dias_atras_jueves = weekday_hoy - weekday_jueves
    else:
        dias_atras_jueves = 7 - (weekday_jueves - weekday_hoy)
    jueves_pasado = (hoy_obj - timedelta(days=dias_atras_jueves)).strftime("%Y-%m-%d")
    
    # Calcular martes pasado
    weekday_martes = 1  # Tuesday
    if weekday_hoy > weekday_martes:
        dias_atras_martes = weekday_hoy - weekday_martes
    else:
        dias_atras_martes = 7 - (weekday_martes - weekday_hoy)
    martes_pasado = (hoy_obj - timedelta(days=dias_atras_martes)).strftime("%Y-%m-%d")
    
    prompt = f"""Eres un asistente que interpreta consultas sobre horas laborales y proyectos disponibles.

Hoy es {hoy} ({dia_semana}).

El usuario pregunta: "{texto}"

🆕 IMPORTANTE: Primero identifica el TIPO de consulta:

TIPO A: "listar_proyectos" - Pide lista de proyectos disponibles
- Ejemplos: "qué proyectos hay", "lista de proyectos", "muéstrame los proyectos", "dime en qué proyectos puedo imputar"
- Devuelve: {{"tipo": "listar_proyectos"}}

TIPO B: "dia" o "semana" - Consulta sobre horas imputadas
- Ejemplos: "qué tengo hoy", "resumen de la semana"
- Devuelve: {{"fecha": "YYYY-MM-DD", "tipo": "dia" o "semana"}}

Si es TIPO A (listar_proyectos):
{{"tipo": "listar_proyectos"}}

Si es TIPO B (consulta de horas), extrae la fecha y tipo:
{{
  "fecha": "YYYY-MM-DD",
  "tipo": "semana" | "dia"  
}}

Reglas para TIPO B:
- Si pregunta por "esta semana" o "la semana" (sin especificar otra) → tipo: "semana", fecha: LUNES DE LA SEMANA ACTUAL
- Si pregunta por "la semana pasada" → tipo: "semana", fecha: LUNES DE LA SEMANA ANTERIOR
- Si pregunta por "HOY" → tipo: "dia", fecha: {hoy}
- Si pregunta por un día específico futuro (ej: "el viernes", "mañana") → tipo: "dia", fecha: ese día exacto
- Si pregunta por un día específico PASADO (ej: "jueves pasado", "el martes pasado", "ayer"):
  * CRÍTICO: Calcula desde HOY ({hoy}) hacia ATRÁS
  * Encuentra el día más reciente en el PASADO con ese nombre
  * Hoy es {dia_semana} ({hoy})
  * Mapeo de días: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
  * ALGORITMO:
    1. Obtener weekday de hoy: {dia_semana} = [número del 0-6]
    2. Obtener weekday objetivo (ej: "jueves"=Thursday=3)
    3. Calcular días atrás:
       - Si weekday_hoy > weekday_objetivo: días_atrás = weekday_hoy - weekday_objetivo
       - Si weekday_hoy <= weekday_objetivo: días_atrás = 7 - (weekday_objetivo - weekday_hoy)
    4. Fecha = {hoy} - días_atrás días
  * Ejemplo concreto HOY ({hoy}={dia_semana}):
    - Si piden "jueves pasado" y hoy es Sunday(6): días_atrás = 7-(3-6) = 7-(-3) = 10? NO
    - CORRECTO: Si hoy es Sunday(6) y quieren Thursday(3): hoy(6) > objetivo(3) → días_atrás = 6-3 = 3 días
    - Fecha = {hoy} - 3 días = jueves pasado
  * tipo: "dia", fecha: ese día específico calculado

🚨 CÁLCULO DEL LUNES DE LA SEMANA ACTUAL:
Hoy es {hoy} ({dia_semana})
- Si {dia_semana} = Monday → lunes = {hoy}
- Si {dia_semana} = Tuesday → lunes = {hoy} - 1 día
- Si {dia_semana} = Wednesday → lunes = {hoy} - 2 días
- Si {dia_semana} = Thursday → lunes = {hoy} - 3 días
- Si {dia_semana} = Friday → lunes = {hoy} - 4 días
- Si {dia_semana} = Saturday → lunes = {hoy} - 5 días
- Si {dia_semana} = Sunday → lunes = {hoy} - 6 días (lunes anterior)

🚨 CRÍTICO: "resumen de la semana" SIN especificar = ESTA SEMANA (calcular lunes actual según tabla arriba)
🚨 SOLO si dice "semana pasada", "semana anterior", "last week" → usar lunes anterior menos 7 días

Ejemplos:
- "resumen de la semana" (hoy={hoy} que es {dia_semana}) → {{"fecha": "[CALCULAR_SEGUN_TABLA]", "tipo": "semana"}}
- "qué tengo esta semana" (hoy={hoy} que es {dia_semana}) → {{"fecha": "[CALCULAR_SEGUN_TABLA]", "tipo": "semana"}}
- "resumen de la semana pasada" → {{"fecha": "[LUNES_ACTUAL - 7 DIAS]", "tipo": "semana"}}
- "dame las horas del jueves pasado" (hoy={hoy}={dia_semana}) → {{"fecha": "{jueves_pasado}", "tipo": "dia"}} (jueves fue hace {dias_atras_jueves} días)
- "qué tenía el martes pasado" (hoy={hoy}={dia_semana}) → {{"fecha": "{martes_pasado}", "tipo": "dia"}} (martes fue hace {dias_atras_martes} días)
- "resumen de ayer" → {{"fecha": "{ayer}", "tipo": "dia"}}

Devuelve SOLO el JSON, sin texto adicional.

Respuesta:"""
    
    try:
        client = settings.get_openai_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un intérprete de fechas. Devuelves solo JSON válido, sin markdown ni texto adicional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        raw = response.choices[0].message.content.strip()
        
        # 🔥 DEBUG: Ver qué devuelve GPT
        print(f"[DEBUG] 🤖 GPT raw response para '{texto}': {raw}")
        
        # Limpiar posible markdown
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # Quitar primera línea
            raw = raw.rsplit("\n", 1)[0]  # Quitar última línea
            raw = raw.replace("```", "").strip()
        
        data = json.loads(raw)
        
        # VALIDACIÓN ADICIONAL: Asegurar que la fecha sea un lunes SOLO si tipo="semana"
        try:
            if data.get("tipo") == "semana":
                fecha_obj = datetime.fromisoformat(data["fecha"])
                # Si no es lunes (weekday != 0), calcular el lunes de esa semana
                if fecha_obj.weekday() != 0:
                    dias_hasta_lunes = fecha_obj.weekday()
                    lunes = fecha_obj - timedelta(days=dias_hasta_lunes)
                    data["fecha"] = lunes.strftime("%Y-%m-%d")
                    print(f"[DEBUG] 🔧 Ajustado a lunes: {data['fecha']}")
        except:
            pass
        
        return data
    
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Error parseando JSON de GPT. Raw: {raw}")
        print(f"[DEBUG] Error: {e}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error interpretando consulta: {e}")
        return None
