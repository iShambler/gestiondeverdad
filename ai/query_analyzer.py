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
    dia_semana = datetime.now().strftime("%A")
    
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
- Si pregunta por un día específico → tipo: "dia", fecha: ese día exacto

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
