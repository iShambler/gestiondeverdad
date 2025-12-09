"""
Analizador de consultas sobre horas imputadas.
Extrae fechas y tipo de consulta (día o semana).
"""

import json
from datetime import datetime, timedelta
from config import settings


def interpretar_consulta(texto):
    """
    Interpreta consultas sobre horas imputadas y extrae la fecha solicitada.
    
    Args:
        texto: Consulta del usuario
        
    Returns:
        dict: {'fecha': 'YYYY-MM-DD', 'tipo': 'dia'|'semana'} o None si no se puede interpretar
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    prompt = f"""Eres un asistente que interpreta consultas sobre horas laborales imputadas.

Hoy es {hoy} ({dia_semana}).

El usuario pregunta: "{texto}"

Extrae la fecha sobre la que pregunta y devuelve SOLO un JSON válido con este formato:
{{
  "fecha": "YYYY-MM-DD",
  "tipo": "semana" | "dia"  
}}

Reglas CRÍTICAS:
- Siempre usa el año 2025 (estamos en 2025)
- Si pregunta por "esta semana", "semana actual", "la semana", "resumen de la semana" (SIN decir "pasada") → tipo: "semana", fecha: LUNES DE LA SEMANA ACTUAL QUE CONTIENE {hoy}
- Si pregunta por "HOY" → tipo: "dia", fecha: {hoy}
- Si pregunta por "MAÑANA" → tipo: "dia", fecha: calcular día siguiente a {hoy}
- Si pregunta por "AYER" → tipo: "dia", fecha: calcular día anterior a {hoy}
- Si pregunta por un DÍA ESPECÍFICO ("el miércoles 15", "el 22 de septiembre", "el 15 de octubre") → tipo: "dia", fecha: ese día exacto
- Si dice "semana pasada", calcula el lunes de la semana anterior a {hoy}
- Si dice "próxima semana", calcula el lunes de la siguiente semana

Ejemplos:
- "esta semana" → {{"fecha": "(LUNES de la semana que contiene {hoy})", "tipo": "semana"}}
- "resumen de la semana" → {{"fecha": "(LUNES de la semana que contiene {hoy})", "tipo": "semana"}}
- "la semana" → {{"fecha": "(LUNES de la semana que contiene {hoy})", "tipo": "semana"}}
- "semana pasada" → {{"fecha": "(LUNES de la semana anterior a {hoy})", "tipo": "semana"}}
- "la semana del 26 de septiembre" → {{"fecha": "2025-09-22", "tipo": "semana"}} (lunes de esa semana)
- "cuántas horas tengo hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "qué tengo imputado el miércoles 15" → {{"fecha": "2025-10-15", "tipo": "dia"}} (ese día exacto)
- "qué tengo el 22 de septiembre" → {{"fecha": "2025-09-22", "tipo": "dia"}} (ese día exacto)
- "dime qué tengo hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "cuántas horas he hecho hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "cuantas horas tengo el 15 de octubre" → {{"fecha": "2025-10-15", "tipo": "dia"}}
- "qué tengo el jueves" → {{"fecha": "(calcular próximo jueves)", "tipo": "dia"}}

MUY IMPORTANTE: 
- Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin explicaciones
- Si pregunta por un día específico → tipo: "dia" y la fecha EXACTA de ese día
- Si pregunta por una semana → tipo: "semana" y el LUNES de esa semana

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
