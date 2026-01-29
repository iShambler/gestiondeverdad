"""
Analizador de consultas sobre horas imputadas.
Extrae fechas y tipo de consulta (día, semana o mes).

 MODIFICADO: Añadido soporte para consultas de mes
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
        dict: {'fecha': 'YYYY-MM-DD', 'tipo': 'dia'|'semana'|'mes'|'listar_proyectos'} o None
              Para tipo='mes', fecha es el primer día del mes consultado
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    hoy_obj = datetime.now()
    dia_semana = hoy_obj.strftime("%A")
    
    #  DEBUG: Verificar fecha actual
    print(f"[DEBUG]  HOY calculado: {hoy} ({dia_semana})")
    print(f"[DEBUG]  Weekday: {hoy_obj.weekday()} (0=Monday, 6=Sunday)")
    
    # Calcular lunes de esta semana
    weekday_actual = hoy_obj.weekday()
    if weekday_actual == 0:  # Ya es lunes
        lunes_esta_semana = hoy
    else:
        lunes_esta_semana = (hoy_obj - timedelta(days=weekday_actual)).strftime("%Y-%m-%d")
    
    # Calcular lunes de la semana pasada
    lunes_semana_pasada = (hoy_obj - timedelta(days=weekday_actual + 7)).strftime("%Y-%m-%d")
    
    #  Calcular lunes de la semana siguiente
    dias_hasta_proximo_lunes = 7 - weekday_actual  # Días desde hoy hasta el próximo lunes
    lunes_semana_siguiente = (hoy_obj + timedelta(days=dias_hasta_proximo_lunes)).strftime("%Y-%m-%d")
    
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
    
    #  Calcular primer día del mes actual y mes anterior
    primer_dia_mes_actual = hoy_obj.replace(day=1).strftime("%Y-%m-%d")
    mes_anterior = (hoy_obj.replace(day=1) - timedelta(days=1)).replace(day=1)
    primer_dia_mes_anterior = mes_anterior.strftime("%Y-%m-%d")
    
    # Nombres de meses en español
    meses_es = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
    }
    mes_actual_nombre = meses_es[hoy_obj.month]
    mes_anterior_nombre = meses_es[mes_anterior.month]
    
    prompt = f"""Eres un asistente que interpreta consultas sobre horas laborales y proyectos disponibles.

Hoy es {hoy} ({dia_semana}). Mes actual: {mes_actual_nombre} {hoy_obj.year}.

El usuario pregunta: "{texto}"

 IMPORTANTE: Primero identifica el TIPO de consulta:

TIPO A: "listar_proyectos" - Pide lista de proyectos disponibles
- Ejemplos: "qué proyectos hay", "lista de proyectos", "muéstrame los proyectos", "dime en qué proyectos puedo imputar"
- Devuelve: {{"tipo": "listar_proyectos"}}

TIPO B: "dia" - Consulta de un día específico
- Ejemplos: "qué tengo hoy", "resumen del martes", "horas del 15 de enero"
- Devuelve: {{"fecha": "YYYY-MM-DD", "tipo": "dia"}}

TIPO C: "semana" - Consulta de una semana
- Ejemplos: "resumen de la semana", "qué tengo esta semana", "semana del 15 de enero"
- Devuelve: {{"fecha": "YYYY-MM-DD", "tipo": "semana"}}

 TIPO D: "mes" - Consulta de un mes completo
- Ejemplos: "resumen del mes", "qué tengo este mes", "resumen de enero", "horas de diciembre", "mes pasado", "mes de febrero"
- Palabras clave: "mes", "mensual", nombre de mes (enero, febrero, etc.)
- Devuelve: {{"fecha": "YYYY-MM-01", "tipo": "mes"}} (siempre día 01 del mes)
- Si dice "este mes" o "el mes" → usar mes actual: {primer_dia_mes_actual}
- Si dice "mes pasado" o "mes anterior" → usar mes anterior: {primer_dia_mes_anterior}
- Si menciona un mes específico (ej: "enero", "diciembre"):
  * Si el mes es POSTERIOR al actual en el mismo año → usar año actual
  * Si el mes es ANTERIOR o IGUAL al actual → determinar si es este año o el anterior:
    - Si el mes mencionado < mes actual → podría ser año pasado o este año
    - Usar sentido común: "diciembre" en enero 2026 → diciembre 2025
    - "febrero" en enero 2026 → febrero 2026 (futuro cercano)

REGLAS PARA TIPO D (MES):

Mapeo de meses (español → número):
- enero=1, febrero=2, marzo=3, abril=4, mayo=5, junio=6
- julio=7, agosto=8, septiembre=9, octubre=10, noviembre=11, diciembre=12

Ejemplos de consulta de MES:
- "resumen del mes" → {{"fecha": "{primer_dia_mes_actual}", "tipo": "mes"}}
- "qué tengo este mes" → {{"fecha": "{primer_dia_mes_actual}", "tipo": "mes"}}
- "resumen del mes pasado" → {{"fecha": "{primer_dia_mes_anterior}", "tipo": "mes"}}
- "horas de {mes_anterior_nombre}" → {{"fecha": "{primer_dia_mes_anterior}", "tipo": "mes"}}
- "resumen de enero" (estamos en enero 2026) → {{"fecha": "2026-01-01", "tipo": "mes"}}
- "resumen de diciembre" (estamos en enero 2026) → {{"fecha": "2025-12-01", "tipo": "mes"}}
- "qué imputé en noviembre" (estamos en enero 2026) → {{"fecha": "2025-11-01", "tipo": "mes"}}

REGLAS PARA TIPO B y C (DIA y SEMANA):

 FECHAS ABSOLUTAS (día + mes especificado):
- Si menciona día y mes específico (ej: "19 de diciembre", "15 de enero", "semana del 23 de noviembre"):
  * PRIMERO determina el año correcto:
    - Hoy es {hoy} (año actual: {hoy_obj.year}, mes actual: {hoy_obj.month})
    - Si el mes mencionado es ANTERIOR al mes actual → usar AÑO ANTERIOR ({hoy_obj.year - 1})
    - Si el mes mencionado es IGUAL O POSTERIOR al mes actual → usar AÑO ACTUAL ({hoy_obj.year})
  * SEGUNDO calcula la fecha en formato YYYY-MM-DD
  * TERCERO determina el tipo:
    - Si dice "semana del [fecha]" → tipo: "semana", fecha: esa fecha específica
    - Si solo menciona la fecha → tipo: "dia", fecha: esa fecha específica

FECHAS RELATIVAS (sin mes específico):
- Si pregunta por "esta semana" o "la semana" (sin especificar otra) → tipo: "semana", fecha: HOY
- Si pregunta por "la semana pasada" → tipo: "semana", fecha: LUNES DE LA SEMANA ANTERIOR
- Si pregunta por "próxima semana" / "siguiente semana" → tipo: "semana", fecha: LUNES DE LA SEMANA SIGUIENTE
- Si pregunta por "HOY" → tipo: "dia", fecha: {hoy}
- Si pregunta por un día específico PASADO (ej: "jueves pasado", "ayer") → tipo: "dia", fecha: ese día calculado

 CÁLCULO DEL LUNES DE LA SEMANA ACTUAL:
Hoy es {hoy} ({dia_semana})
- Si {dia_semana} = Monday → lunes = {hoy}
- Si {dia_semana} = Tuesday → lunes = {hoy} - 1 día
- etc.

Ejemplos completos:
- "resumen de la semana" → {{"fecha": "{hoy}", "tipo": "semana"}}
- "qué tengo esta semana" → {{"fecha": "{hoy}", "tipo": "semana"}}
- "resumen de la semana pasada" → {{"fecha": "{lunes_semana_pasada}", "tipo": "semana"}}
- "resumen de la próxima semana" → {{"fecha": "{lunes_semana_siguiente}", "tipo": "semana"}}
- "dame las horas del jueves pasado" → {{"fecha": "{jueves_pasado}", "tipo": "dia"}}
- "resumen de ayer" → {{"fecha": "{ayer}", "tipo": "dia"}}
- "resumen del mes" → {{"fecha": "{primer_dia_mes_actual}", "tipo": "mes"}}
- "horas de diciembre" → {{"fecha": "2025-12-01", "tipo": "mes"}}

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
        
        #  DEBUG: Ver qué devuelve GPT
        print(f"[DEBUG]  GPT raw response para '{texto}': {raw}")
        
        # Limpiar posible markdown
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # Quitar primera línea
            raw = raw.rsplit("\n", 1)[0]  # Quitar última línea
            raw = raw.replace("```", "").strip()
        
        data = json.loads(raw)
        
        return data
    
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Error parseando JSON de GPT. Raw: {raw}")
        print(f"[DEBUG] Error: {e}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error interpretando consulta: {e}")
        return None
