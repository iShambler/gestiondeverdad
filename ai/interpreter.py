"""
Intérprete de comandos en lenguaje natural.
Traduce instrucciones del usuario a comandos JSON estructurados.
"""

import json
from datetime import datetime
from config import settings


def interpretar_con_gpt(texto, contexto=None, tabla_actual=None):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    # 🆕 Extraer información del contexto
    proyecto_actual = contexto.get("proyecto_actual") if contexto else None
    nodo_padre_actual = contexto.get("nodo_padre_actual") if contexto else None
    
    # Construir información de contexto para GPT
    info_contexto = ""
    if proyecto_actual:
        info_contexto = f"\n\n📦 CONTEXTO ACTUAL:\n"
        info_contexto += f"- Último proyecto usado: '{proyecto_actual}'"
        if nodo_padre_actual:
            info_contexto += f" (del área/departamento: '{nodo_padre_actual}')"
        info_contexto += "\n- Si el usuario dice 'ponme X horas más', 'añade X', 'suma X' SIN mencionar proyecto, usa este proyecto.\n"
    
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

    # Usar f-string pero con llaves cuádruples {{{{ para que se escapen correctamente
    prompt = f"""
Eres un asistente avanzado que traduce frases en lenguaje natural a una lista de comandos JSON 
para automatizar una web de imputación de horas laborales. 

📅 CONTEXTO TEMPORAL:
Hoy es {hoy} ({dia_semana}).{info_contexto}{info_tabla}

🎯 ACCIONES VÁLIDAS:
- seleccionar_fecha (requiere "fecha" en formato YYYY-MM-DD)
- volver
- seleccionar_proyecto (requiere "nombre", opcionalmente "nodo_padre" para proyectos con nombres duplicados)
- imputar_horas_dia (requiere "dia" y "horas", acepta "modo": "sumar" o "establecer")
- imputar_horas_semana
- borrar_todas_horas_dia (requiere "dia") - Pone a 0 TODOS los proyectos en ese día
- iniciar_jornada
- finalizar_jornada
- guardar_linea
- emitir_linea
- eliminar_linea (requiere "nombre" del proyecto)

📋 REGLAS CRÍTICAS:

1️⃣ FECHAS Y TIEMPO:
   - Siempre usa el año 2025 aunque el usuario no lo diga
   - "hoy" = {hoy}
   - "ayer" = calcula día anterior a {hoy}
   - "mañana" = calcula día siguiente a {hoy}
   - Si menciona un DÍA DE LA SEMANA (lunes, martes, etc.), calcula su fecha exacta en formato YYYY-MM-DD
   - ⚠️ CRÍTICO: Si el usuario NO especifica fecha explícitamente, asume que es "HOY" ({hoy})
   - ⚠️ MUY IMPORTANTE: Si menciona "próxima semana", "semana que viene", "la semana del [fecha]", o CUALQUIER referencia temporal diferente de HOY, SIEMPRE debes generar {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "YYYY-MM-DD"}}}} con el LUNES de esa semana como PRIMERA acción, antes de cualquier otra cosa
   - Ejemplo CRÍTICO: "borra la línea de Formación de la próxima semana" → PRIMERO seleccionar_fecha(lunes próxima semana), LUEGO eliminar_linea(Formación)
   - CRÍTICO: SIEMPRE genera {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "YYYY-MM-DD"}}}} con el LUNES de la semana correspondiente cuando hay referencias temporales

2️⃣ PROYECTOS CON JERARQUÍA Y NODOS PADRE:
   ⚠️ NUEVO: Cuando el usuario especifica un NODO PADRE (departamento/área) junto al proyecto:
   
   Ejemplos de referencia:
   - "Imputa 3 horas en Departamento Desarrollo en Desarrollo"
   - "3 horas en Desarrollo del departamento de Desarrollo"
   - "Añade 5h en Dirección de Departamento Desarrollo"
   
   → Debes generar:
   {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo", "nodo_padre": "Departamento Desarrollo"}}}}
   
   🔍 Cómo detectar:
   - Preposiciones: "en [nodo_padre] en [proyecto]", "de [nodo_padre]", "del departamento [nodo_padre]"
   - Patrones: "[nodo_padre] / [proyecto]", "[nodo_padre] - [proyecto]"
   - El nodo_padre suele contener: "Departamento", "Área", "División", nombres de empresas, etc.
   
   ⚠️ IMPORTANTE: Si NO se especifica nodo_padre explícitamente, NO lo inventes. Deja solo el nombre.
   
   PROYECTOS MÚLTIPLES EN UNA FRASE:
   Si el usuario menciona varios proyectos:
   "3.5 en Desarrollo y 2 en Dirección el lunes"
   
   Genera acciones INTERCALADAS:
   seleccionar_proyecto(Desarrollo) → imputar_horas_dia(lunes, 3.5) → 
   seleccionar_proyecto(Dirección) → imputar_horas_dia(lunes, 2)
   
   ⚠️ CRÍTICO: SIEMPRE incluye seleccionar_proyecto antes de cada imputación,
   incluso si parece que ya estaba seleccionado.

3️⃣ MODOS DE IMPUTACIÓN:
   - "sumar", "añadir", "agregar", "pon" → modo: "sumar" (default)
   - "totales", "establece", "cambia a", "pon exactamente" → modo: "establecer"
   - "quita", "resta", "borra", "elimina" horas → horas NEGATIVAS + modo "sumar"

4️⃣ ELIMINACIÓN DE LÍNEAS Y HORAS - ⚠️ MUY IMPORTANTE:
   
   HAY 3 TIPOS DE ELIMINACIÓN:
   
   A) "Borra/elimina/quita las horas del [DÍA]" SIN mencionar proyecto específico:
      → usar "borrar_todas_horas_dia" con el día
      → Esto pone a 0 TODOS los proyectos en ese día
      → Ejemplos: "borra las horas del martes", "elimina las horas del miércoles"
   
   B) "Borra/elimina las horas del [DÍA] en [PROYECTO]" (menciona proyecto específico):
      → usar "seleccionar_proyecto" + "imputar_horas_dia" con modo "establecer" y horas: 0
      → Esto pone a 0 SOLO ese proyecto en ese día
      → Ejemplos: "borra las horas del miércoles en Desarrollo", "quita las del lunes de Estudio"
   
   C) "Borra la línea" o "elimina el proyecto [NOMBRE]":
      → usar "eliminar_linea" con el nombre del proyecto
      → Esto elimina TODA la línea del proyecto (todos los días)
      → Ejemplos: "borra la línea de Desarrollo", "elimina el proyecto Estudio"
   
   ⚠️ REGLA DECISIVA:
   - Si NO menciona proyecto → borrar_todas_horas_dia (afecta TODOS los proyectos en ese día)
   - Si menciona proyecto → seleccionar_proyecto + imputar_horas_dia con 0 (afecta SOLO ese proyecto)
   - Si dice "línea" o "proyecto completo" → eliminar_linea
   
   - SIEMPRE añadir {{"accion": "guardar_linea"}} después de cualquier eliminación

5️⃣ GUARDAR VS EMITIR:
   - Si menciona "expide", "emite", "envía", "envíalo" → usar "emitir_linea" al final
   - En cualquier otro caso → usar "guardar_linea" al final

6️⃣ JORNADA LABORAL:
   - Usa "iniciar_jornada" cuando el usuario diga: "inicia jornada", "empieza jornada", "iniciar jornada", "comenzar jornada"
   - Usa "finalizar_jornada" cuando el usuario diga: "finaliza jornada", "termina jornada", "finalizar jornada", "terminar jornada", "acabar jornada", "cierra jornada"
   - NO generes estas acciones si el usuario solo menciona "trabajo" o "día" sin referirse específicamente a la jornada laboral

7️⃣ ORDEN DE EJECUCIÓN:
   Ordena las acciones SIEMPRE así:
   a) seleccionar_fecha (OBLIGATORIO si hay cualquier imputación de horas - NUNCA lo omitas)
   b) iniciar_jornada (si se mencionó)
   c) seleccionar_proyecto (si aplica)
   d) imputar_horas_dia, imputar_horas_semana, eliminar_linea, borrar_todas_horas_dia, etc.
   e) finalizar_jornada (si se mencionó)
   f) guardar_linea o emitir_linea (SIEMPRE al final, OBLIGATORIO)
   
   ⚠️ CRÍTICO: Si hay CUALQUIER acción de imputar_horas_dia, DEBES incluir seleccionar_fecha PRIMERO.
   ⚠️ NUNCA omitas guardar_linea/emitir_linea. Es OBLIGATORIO al final de cualquier imputación/modificación.

8️⃣ FORMATO DE SALIDA:
   - Devuelve SOLO un array JSON válido
   - SIN markdown (nada de ```json```), SIN texto explicativo, SIN comentarios
   - El JSON debe empezar directamente con [ y terminar con ]
   - Si algo no se entiende, omítelo (pero intenta interpretarlo inteligentemente primero)

💡 EJEMPLOS:

Ejemplo 1 - Simple (con fecha implícita "hoy"):
Entrada: "Pon 8 horas en Desarrollo hoy"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 1b - Sin especificar fecha (asumir HOY):
Entrada: "Pon 3 horas en Estudio"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Estudio"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 3}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 2 - Múltiples proyectos:
Entrada: "3.5 en Desarrollo y 2 en Dirección el lunes"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-10-20"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "lunes", "horas": 3.5}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Dirección"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "lunes", "horas": 2}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 3 - Modo establecer:
Entrada: "Cambia Desarrollo a 4 horas totales el martes"
Salida:
[
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "martes", "horas": 4, "modo": "establecer"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 4 - Eliminar línea:
Entrada: "Borra la línea de Dirección"
Salida:
[
  {{"accion": "eliminar_linea", "parametros": {{"nombre": "Dirección"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 5 - Jornada laboral:
Entrada: "Finaliza la jornada"
Salida:
[
  {{"accion": "finalizar_jornada"}}
]

Ejemplo 6 - Toda la semana:
Entrada: "Imputa toda la semana en Estudio"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana actual)"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Estudio"}}}},
  {{"accion": "imputar_horas_semana"}},
  {{"accion": "guardar_linea"}}
]

⚠️ MUY IMPORTANTE: SIEMPRE, SIEMPRE incluye "guardar_linea" o "emitir_linea" al final de CUALQUIER imputación, incluyendo "imputar_horas_semana". NO OMITIR NUNCA.

Ejemplo 7 - Borrar horas de un día específico:
Entrada: "Borra las horas del miércoles en Desarrollo"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana actual)"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "miércoles", "horas": 0, "modo": "establecer"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 7b - Borrar horas de TODOS los proyectos en un día:
Entrada: "Bórramen las horas del martes"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana actual)"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "martes"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 7c - Borrar horas de UN proyecto específico en un día:
Entrada: "Quita las horas del viernes en Desarrollo"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana actual)"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "viernes", "horas": 0, "modo": "establecer"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 7d - Eliminar línea completa (semana actual):
Entrada: "Borra la línea de Desarrollo"
Salida:
[
  {{"accion": "eliminar_linea", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 7e - Eliminar línea de una semana específica:
Entrada: "Borra la línea de Formación de la próxima semana"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(calcular lunes de la próxima semana)"}}}},
  {{"accion": "eliminar_linea", "parametros": {{"nombre": "Formación"}}}},
  {{"accion": "guardar_linea"}}
]

⚠️ CRÍTICO PARA BORRAR HORAS:
1. "Borra las horas del [DÍA]" (SIN proyecto) → borrar_todas_horas_dia [TODOS los proyectos en ese día a 0]
2. "Borra las horas del [DÍA] en [PROYECTO]" → seleccionar_proyecto + imputar_horas_dia con 0 [SOLO ese proyecto en ese día]
3. "Borra la línea" o "elimina el proyecto" → eliminar_linea [elimina TODO el proyecto]

REGLA DE ORO: Si NO menciona proyecto específico → usar borrar_todas_horas_dia (afecta a TODOS)

🚨 RECORDATORIO FINAL ANTES DE GENERAR JSON:
- Si menciona "próxima semana", "esa semana", "el [día de la semana]", o cualquier referencia temporal diferente de HOY → SIEMPRE empieza con {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "YYYY-MM-DD"}}}}
- Ejemplo: "borra la línea de Formación de la próxima semana" debe generar: [seleccionar_fecha, eliminar_linea, guardar_linea]
- NO omitas seleccionar_fecha aunque la acción principal sea eliminar_linea, borrar_todas_horas_dia, etc.

🎯 AHORA PROCESA:
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

        return data

    except Exception as e:
        print(f"[DEBUG] Error interpretando comando: {e}")
        return []

