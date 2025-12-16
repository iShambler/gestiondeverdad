"""
Intérprete de comandos en lenguaje natural.
Traduce instrucciones del usuario a comandos JSON estructurados.
"""

import json
from datetime import datetime
from config import settings


def validar_ordenes(ordenes, texto, contexto=None):
    """
    Valida las órdenes generadas por GPT, detectando:
    - proyectos inventados
    - comandos incompletos
    - falta de horas o proyecto
    - uso correcto del proyecto del contexto
    
    Sin listas de palabras clave: validación 100% semántica.
    """

    texto_lower = texto.lower()
    
    # Contexto
    proyecto_actual = (contexto or {}).get("proyecto_actual")
    proyecto_actual_lower = proyecto_actual.lower() if proyecto_actual else None

    # Identificar si hay proyecto y/o imputación
    tiene_proyecto = any(o.get("accion") == "seleccionar_proyecto" for o in ordenes)
    tiene_imputacion = any(o.get("accion") in ["imputar_horas_dia", "imputar_horas_semana"] for o in ordenes)
    tiene_eliminacion = any(o.get("accion") == "eliminar_linea" for o in ordenes)
    tiene_borrado_horas = any(o.get("accion") == "borrar_todas_horas_dia" for o in ordenes)

    # 🔥 Si hay eliminación o borrado de horas → NO VALIDAR (son acciones válidas sin imputación)
    if tiene_eliminacion or tiene_borrado_horas:
        print(f"[DEBUG] ✅ Acción de eliminación/borrado detectada, omitiendo validación")
        return None

    # ----------------------------------------------------------------------
    # 🔍 1. VALIDACIÓN INTELIGENTE DE PROYECTO (si proyecto + imputación)
    # ----------------------------------------------------------------------
    # 🔥 DESHABILITADA: Dejamos que el sistema web valide si el proyecto existe
    # Si GPT genera un nombre, confiamos en él y dejamos que la web lo busque
    # Si no existe, la web devolverá: "❌ No he encontrado el proyecto 'X'"
    # ----------------------------------------------------------------------
    # if tiene_proyecto and tiene_imputacion:
    #     ... validación semántica comentada ...
    # ----------------------------------------------------------------------

    # ----------------------------------------------------------------------
    # 🧩 2. Proyecto sin imputación → Falta horas y día
    # ----------------------------------------------------------------------
    if tiene_proyecto and not tiene_imputacion:
        for orden in ordenes:
            if orden.get("accion") == "seleccionar_proyecto":
                nombre_proyecto = orden.get("parametros", {}).get("nombre")
                break
        else:
            nombre_proyecto = None

        if nombre_proyecto:
            return [{
                "accion": "info_incompleta",
                "info_parcial": {"proyecto": nombre_proyecto},
                "que_falta": "horas_y_dia",
                "mensaje": (
                    f"📝 Vale, **{nombre_proyecto}**. ¿Cuántas horas y para qué día?\n\n"
                    "💡 Ejemplos:\n- \"Pon 8 horas hoy\"\n- \"5 horas el lunes\"\n- \"Toda la semana\""
                )
            }]
        
        return [{
            "accion": "error_validacion",
            "mensaje": "📝 ¿Cuántas horas quieres imputar y para qué día?"
        }]

    # ----------------------------------------------------------------------
    # 🧩 3. Imputación sin proyecto → falta el proyecto
    # ----------------------------------------------------------------------
    if tiene_imputacion and not tiene_proyecto:
        info = {}
        for orden in ordenes:
            if orden.get("accion") == "imputar_horas_dia":
                info["horas"] = orden["parametros"]["horas"]
                info["dia"] = orden["parametros"]["dia"]
                break
            if orden.get("accion") == "imputar_horas_semana":
                info["horas"] = "toda_la_semana"
                info["dia"] = "semana"
                break

        return [{
            "accion": "info_incompleta",
            "info_parcial": info,
            "que_falta": "proyecto",
            "mensaje": (
                "🤔 **¿En qué proyecto quieres imputar las horas?**\n\n"
                "💡 Ejemplo: \"Pon 8 horas en Desarrollo\""
            )
        }]

    # ----------------------------------------------------------------------
    # 🚫 4. Comandos vacíos o sin sentido
    # ----------------------------------------------------------------------
    if len(ordenes) == 2 and ordenes[0].get("accion") == "seleccionar_fecha":
        if ordenes[1].get("accion") in ["guardar_linea", "emitir_linea"]:
            return [{
                "accion": "error_validacion",
                "mensaje": (
                    "🤔 **Necesito más información.**\n\n"
                    "¿Qué proyecto? ¿Cuántas horas?\n"
                )
            }]

    if len(ordenes) == 1 and ordenes[0].get("accion") in ["guardar_linea", "emitir_linea"]:
        return [{
            "accion": "error_validacion",
            "mensaje": "🤔 ¿Qué quieres hacer exactamente?"
        }]

    # ----------------------------------------------------------------------
    # TODO LO DEMÁS ES VÁLIDO
    # ----------------------------------------------------------------------
    return None


def interpretar_con_gpt(texto, contexto=None, tabla_actual=None, historial=None):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    # 🆕 Extraer información del contexto
    proyecto_actual = contexto.get("proyecto_actual") if contexto else None
    nodo_padre_actual = contexto.get("nodo_padre_actual") if contexto else None
    dia_actual = contexto.get("dia_actual") if contexto else None  # 🆕 NUEVO
    
    # Construir información de contexto para GPT
    info_contexto = ""
    if proyecto_actual:
        info_contexto = f"\n\n📦 CONTEXTO ACTUAL:\n"
        info_contexto += f"- Último proyecto usado: '{proyecto_actual}'"
        if nodo_padre_actual:
            info_contexto += f" (del área/departamento: '{nodo_padre_actual}')"
        if dia_actual:  # 🆕 NUEVO
            info_contexto += f"\n- Último día imputado: '{dia_actual}'"
        info_contexto += "\n- Si el usuario dice 'ponme X horas más', 'añade X', 'suma X', 'quita X' SIN mencionar proyecto ni día, usa este proyecto y este día.\n"
    
    # 🆕 Añadir información de la tabla actual si está disponible
    info_tabla = ""
    if tabla_actual and len(tabla_actual) > 0:
        info_tabla = "\n\n📊 ESTADO ACTUAL DE LA TABLA DE IMPUTACIÓN:\n"
        for proyecto_info in tabla_actual:
            nombre_proyecto = proyecto_info['proyecto'].split(' - ')[-1]  # Solo último nombre
            horas = proyecto_info['horas']
            
            # Mostrar solo días con horas > 0
            dias_con_horas = []
            for dia, valor in horas.items():
                if valor > 0:
                    dias_con_horas.append(f"{dia.capitalize()}: {valor}h")
            
            if dias_con_horas:
                info_tabla += f"  • {nombre_proyecto}: {', '.join(dias_con_horas)}\n"
        
        info_tabla += "\n⚠️ IMPORTANTE: Puedes usar esta información para:\n"
        info_tabla += "  - Copiar horas de un proyecto a otro\n"
        info_tabla += "  - Duplicar/triplicar horas\n"
        info_tabla += "  - Sumar o restar basándote en datos existentes\n"
        info_tabla += "  - Distribuir horas proporcionalmente\n"

    # 🆕 HISTORIAL DE CONVERSACIÓN
    info_historial = ""
    if historial and len(historial) > 0:
        info_historial = "\n\n💬 HISTORIAL DE CONVERSACIÓN (últimos mensajes):\n"
        for msg in historial:
            usuario_texto = msg.get('usuario', '').strip()
            asistente_texto = msg.get('asistente', '').strip()
            if usuario_texto:
                info_historial += f"Usuario: {usuario_texto}\n"
            if asistente_texto:
                # Truncar respuestas muy largas (solo primeras 200 caracteres)
                if len(asistente_texto) > 200:
                    asistente_texto = asistente_texto[:200] + "..."
                info_historial += f"Asistente: {asistente_texto}\n"
            info_historial += "\n"
        info_historial += "⚠️ Usa este historial para entender mejor el contexto y las intenciones del usuario.\n"
        info_historial += "⚠️ Si el usuario dice 'lo mismo', 'otra vez', 'igual', etc., busca en el historial qué hizo antes.\n"

    # Usar f-string pero con llaves cuádruples {{{{ para que se escapen correctamente
    prompt = f"""
Eres un asistente que convierte frases en lenguaje natural en una lista de acciones JSON
para automatizar una web de imputación de horas. Devuelves SOLO un array JSON, sin texto
extra, sin markdown, sin explicaciones.

====================================================
CONTEXTO
====================================================
Hoy es {hoy} ({dia_semana}).
{info_contexto}{info_tabla}{info_historial}

====================================================
REGLAS GENERALES
====================================================
1. Orden de acciones:
   a) seleccionar_fecha (si fecha != hoy o indefinida)
   b) iniciar_jornada (si se menciona)
   c) seleccionar_proyecto (cuando se impute/borre de un proyecto)
   d) imputar_horas_dia / imputar_horas_semana / borrar_todas_horas_dia / eliminar_linea
   e) finalizar_jornada (si se menciona)
   f) guardar_linea (solo cuando se CAMBIA DE SEMANA o al FINAL de todo)

2. Fechas:
   - "hoy" = {hoy}. Sin fecha → usar {hoy}
   - "ayer" = hoy -1; "mañana" = hoy +1
   - 🚨 Día de la semana SIN "próximo/siguiente" → SIEMPRE el PRÓXIMO (hacia adelante)
     Ejemplos con hoy={dia_semana} {hoy}:
     - "el lunes" = PRÓXIMO lunes (si hoy es lunes, sería el siguiente lunes)
     - "el martes" = PRÓXIMO martes
     - "el viernes" = PRÓXIMO viernes
   - "la semana pasada" / "el lunes pasado" → entonces sí ir hacia atrás
   - "próxima semana" / "semana que viene" → día de la semana siguiente
   - IMPORTANTE: Si dice "el martes", calcula la fecha del MARTES, NO del lunes de esa semana
   - Referencia temporal != "hoy" → PRIMERA acción: seleccionar_fecha con la fecha EXACTA del día mencionado

3. Proyectos múltiples del MISMO día → INTERCALAR sin guardar_linea entre ellos:
   "3h en X y 2h en Y" (mismo día) → seleccionar_fecha → seleccionar_proyecto(X) → imputar(3) → seleccionar_proyecto(Y) → imputar(2) → guardar_linea (UNA VEZ AL FINAL)

4. Múltiples días de la MISMA SEMANA → NO guardar entre días, solo al FINAL:
   Ejemplo: "3h en X el lunes, 5h en Y el miércoles" (ambos semana 16-20 dic) → fecha(lunes) → proyecto(X) → imputar(3) → fecha(miércoles) → proyecto(Y) → imputar(5) → guardar_linea (UNA VEZ AL FINAL)
   
5. Cambio de SEMANA → guardar antes de cambiar:
   Ejemplo: "3h el lunes 16, 5h el lunes 23" (semanas diferentes) → fecha(16) → proyecto(X) → imputar(3) → guardar_linea → fecha(23) → proyecto(Y) → imputar(5) → guardar_linea
   
6. REGLA CLAVE: guardar_linea solo cuando:
   - Vas a cambiar de semana (antes del cambio)
   - Al final de TODAS las órdenes

====================================================
NODO PADRE
====================================================
REGLA #1 (PRIORIDAD): Doble "en" → primera = nodo_padre, segunda = proyecto
  Ej: "3h en staff en permiso" → {{"nombre": "Permiso", "nodo_padre": "Staff"}}

Palabras clave: "Departamento X", "Área X", "Staff", "Administración", "Comercial"
Separadores: "X / Y", "X - Y" → nodo_padre = X, nombre = Y
Capitalizar siempre.

====================================================
TIPOS DE ACCIONES
====================================================
1) IMPUTAR HORAS:
   - Modo: "sumar" (default) o "establecer" (si dice "totales", "cambia a", "exactamente")
   - Restar → horas negativas + modo "sumar"

2) ELIMINAR HORAS:
   A) Sin proyecto: "borra horas del <día>" → borrar_todas_horas_dia
   B) Con proyecto pero día específico: "borra horas del <día> en <proyecto>" → seleccionar_proyecto + imputar_horas_dia (horas=0, modo="establecer")
   C) Línea completa: "borra la línea", "elimina <proyecto>", "borra todo de <proyecto>" → seleccionar_proyecto + eliminar_linea
   D) Borrar múltiples días de la semana: "borra las horas de esta semana" → seleccionar_fecha (LUNES) + borrar_todas_horas_dia (lunes) + borrar_todas_horas_dia (martes) + ... + guardar_linea
      IMPORTANTE: NO cambiar fecha entre cada día, hacer todos los borrados en la misma pantalla
   Tras eliminar → guardar_linea

3) JORNADA:
   - iniciar_jornada: "inicia/empieza jornada"
   - finalizar_jornada: "finaliza/termina jornada"

4) GUARDAR vs EMITIR:
   - "emitir", "expide", "envía" → emitir_linea
   - Resto → guardar_linea

====================================================
EJEMPLOS
====================================================
"Pon 8 horas en Desarrollo hoy"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]

"3h en staff en permiso"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Permiso", "nodo_padre": "Staff"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 3}}}},
  {{"accion": "guardar_linea"}}
]

"Borra las horas del martes"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-17"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "martes"}}}},
  {{"accion": "guardar_linea"}}
]

"Borra todas las horas de esta semana"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-16"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "lunes"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "martes"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "miércoles"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "jueves"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "viernes"}}}},
  {{"accion": "guardar_linea"}}
]

"3.5 en Desarrollo y 2 en Dirección el lunes"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-16"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-16", "horas": 3.5}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Dirección"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-16", "horas": 2}}}},
  {{"accion": "guardar_linea"}}
]

"Ponme 3h en Eventos el lunes, 2h en Desarrollo el martes y 4h en Formación el jueves"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-16"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Eventos"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-16", "horas": 3}}}},
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-17"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-17", "horas": 2}}}},
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-19"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Formación"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-19", "horas": 4}}}},
  {{"accion": "guardar_linea"}}
]

"3h el lunes 16 y 5h el lunes 23"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-16"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-16", "horas": 3}}}},
  {{"accion": "guardar_linea"}},
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-23"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-23", "horas": 5}}}},
  {{"accion": "guardar_linea"}}
]

"Último proyecto: Eventos. Usuario: 'borra la línea'"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Eventos"}}}},
  {{"accion": "eliminar_linea"}},
  {{"accion": "guardar_linea"}}
]

"Borra todo de Desarrollo"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "eliminar_linea"}},
  {{"accion": "guardar_linea"}}
]

"Elimina el proyecto Comercial"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Comercial"}}}},
  {{"accion": "eliminar_linea"}},
  {{"accion": "guardar_linea"}}
]

====================================================
OUTPUT: SOLO JSON, SIN TEXTO ADICIONAL
====================================================
Frase del usuario: "{texto}"
"""

    try:
        client = settings.get_openai_client()  # ✅ Necesario para usar la API

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un intérprete experto de lenguaje natural a comandos JSON estructurados. Procesas instrucciones complejas con alta precisión, manejando múltiples proyectos, fechas relativas y contextos ambiguos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        print(f"[DEBUG] 🧠 GPT generó: {raw}")
        
        # 🧹 Limpiar markdown si GPT-4o lo añade (```json ... ```)
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])  # Quitar primera y última línea
            raw = raw.strip()
            print(f"[DEBUG] 🧹 JSON limpio: {raw}")
        
        data = json.loads(raw)

        # Si devuelve un solo objeto, lo convertimos a lista
        if isinstance(data, dict):
            data = [data]

        # 🆕 VALIDAR que las órdenes tengan sentido
        resultado_validacion = validar_ordenes(data, texto, contexto)
        if resultado_validacion:
            # Si devuelve algo, es porque hay error o info incompleta
            print(f"[DEBUG] ⚠️ Comando requiere atención: {texto}")
            return resultado_validacion

        return data

    except Exception as e:
        print(f"[DEBUG] Error interpretando comando: {e}")
        return []