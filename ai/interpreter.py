"""
Intérprete de comandos en lenguaje natural.
Traduce instrucciones del usuario a comandos JSON estructurados.
"""

import json
from datetime import datetime
from config import settings


def validar_ordenes(ordenes, texto, contexto=None):
    """
    Valida que las órdenes generadas tengan sentido y contengan información crítica.
    
    Args:
        ordenes: Lista de órdenes JSON generadas por GPT
        texto: Texto original del usuario
    
    Returns:
        (bool, str): (es_valido, mensaje_error)
    """
    # Normalizar texto para comparación
    texto_lower = texto.lower()
    
    # 💾 Obtener proyecto actual del contexto (si existe)
    proyecto_actual = contexto.get('proyecto_actual') if contexto else None
    nodo_padre_actual = contexto.get('nodo_padre_actual') if contexto else None
    
    # 🚨 Detectar si selecciona proyecto pero NO imputa horas (COMANDO INCOMPLETO)
    tiene_proyecto = any(
        orden.get('accion') == 'seleccionar_proyecto' 
        for orden in ordenes
    )
    
    tiene_imputacion = any(
        orden.get('accion') in ['imputar_horas_dia', 'imputar_horas_semana']
        for orden in ordenes
    )
    
    # 🆕 CRÍTICO: Detectar si GPT está INVENTANDO el nombre del proyecto
    if tiene_proyecto and tiene_imputacion:
        for orden in ordenes:
            if orden.get('accion') == 'seleccionar_proyecto':
                nombre_proyecto = orden.get('parametros', {}).get('nombre', '')
                nombre_lower = nombre_proyecto.lower()
                
                # ✅ NUEVO: Si el proyecto coincide con el proyecto_actual del contexto, PERMITIRLO
                # PERO SOLO si el usuario NO mencionó otro proyecto diferente en el texto
                if proyecto_actual and nombre_proyecto.lower() == proyecto_actual.lower():
                    # Verificar si el usuario mencionó algún otro proyecto en el texto
                    # Si dijo "ponme en eventos" pero GPT usa "Permiso", es un error
                    palabras_sospechosas = texto_lower.split()
                    
                    # 🆕 Filtrar palabras comunes Y palabras de acción
                    palabras_accion = ['ponme', 'pon', 'añade', 'quita', 'quitale', 'resta', 'suma', 
                                       'agrega', 'cambia', 'establece', 'borra', 'elimina', 'dame', 
                                       'para', 'esta', 'este', 'toda', 'todo', 'horas', 'hora', 
                                       'media', 'cuarto', 'minutos', 'del', 'la', 'el', 'en', 'de', 'a']
                    
                    palabras_relevantes = [
                        p for p in palabras_sospechosas 
                        if len(p) > 3 and p not in palabras_accion
                    ]
                    
                    # Si alguna palabra relevante NO aparece en el proyecto_actual, es sospechoso
                    proyecto_actual_lower = proyecto_actual.lower()
                    menciona_otro_proyecto = any(
                        palabra not in proyecto_actual_lower and 
                        palabra not in ['lunes', 'martes', 'miercoles', 'jueves', 'viernes', 'sabado', 'domingo', 'semana', 'ayer', 'hoy', 'mañana']
                        for palabra in palabras_relevantes
                    )
                    
                    if not menciona_otro_proyecto:
                        print(f"[DEBUG] ✅ Proyecto del contexto detectado: '{proyecto_actual}'")
                        return None  # ✅ Válido, está usando el contexto
                    else:
                        print(f"[DEBUG] ⚠️ Usuario mencionó otro proyecto ('{palabras_relevantes}') pero GPT usó contexto ('{proyecto_actual}')")
                        # Continuar con las validaciones normales
                
                # Lista de nombres genéricos que GPT suele inventar cuando NO SABE
                nombres_genericos = ['general', 'proyecto', 'trabajo', 'horas', 'tarea', 'actividad', 'defecto', 'default']
                
                # CASO 1: GPT usó un nombre genérico porque NO SABE cuál es
                if nombre_lower in nombres_genericos:
                    return [{"accion": "error_validacion", "mensaje": "🤔 **¿En qué proyecto quieres imputar las horas?**\n\n💡 Ejemplo: *\"Pon 3 horas en Desarrollo\"*"}]
                
                # CASO 2: El nombre NO aparece en el texto original (GPT lo inventó)
                # Verificar si alguna palabra del proyecto aparece en el texto
                palabras_proyecto = nombre_proyecto.split()
                alguna_coincide = any(
                    palabra.lower() in texto_lower 
                    for palabra in palabras_proyecto 
                    if len(palabra) > 2  # Ignorar palabras muy cortas
                )
                
                if not alguna_coincide:
                    return [{"accion": "error_validacion", "mensaje": "🤔 **¿En qué proyecto quieres imputar las horas?**\n\n💡 Ejemplo: *\"Pon 3 horas en Desarrollo\"*"}]
                
                break
    
    # 🆕 CASO 1: Menciona proyecto pero NO dice cuántas horas ni qué día
    if tiene_proyecto and not tiene_imputacion:
        # Extraer nombre del proyecto
        nombre_proyecto = None
        for orden in ordenes:
            if orden.get('accion') == 'seleccionar_proyecto':
                nombre_proyecto = orden.get('parametros', {}).get('nombre')
                break
        
        if nombre_proyecto:
            # Devolver info para que server.py guarde el contexto
            return [{"accion": "info_incompleta", "info_parcial": {"proyecto": nombre_proyecto}, "que_falta": "horas_y_dia", "mensaje": f"📝 Vale, **{nombre_proyecto}**. ¿Cuántas horas quieres imputar y para qué día?\n\n💡 Ejemplos:\n- *\"Pon 8 horas hoy\"*\n- *\"5 horas el lunes\"*\n- *\"Toda la semana\"*"}]
        else:
            return [{"accion": "error_validacion", "mensaje": "📝 ¿Cuántas horas quieres imputar y para qué día?\n\n💡 Ejemplo: *\"Pon 8 horas hoy\"*"}]
    
    # 🆕 CASO 2: Tiene imputación pero NO tiene proyecto
    if tiene_imputacion and not tiene_proyecto:
        # Extraer horas y día
        horas = None
        dia = None
        for orden in ordenes:
            if orden.get('accion') == 'imputar_horas_dia':
                horas = orden.get('parametros', {}).get('horas')
                dia = orden.get('parametros', {}).get('dia')
                break
            elif orden.get('accion') == 'imputar_horas_semana':
                horas = "toda_la_semana"
                dia = "semana"
                break
        
        if horas:
            # Devolver info para que server.py guarde el contexto
            info_parcial = {"horas": horas}
            if dia:
                info_parcial["dia"] = dia
            return [{"accion": "info_incompleta", "info_parcial": info_parcial, "que_falta": "proyecto", "mensaje": "🤔 **¿En qué proyecto quieres imputar las horas?**\n\n💡 Ejemplo: *\"Pon 8 horas en Desarrollo\"*"}]
        else:
            return [{"accion": "error_validacion", "mensaje": "🤔 **¿En qué proyecto quieres imputar las horas?**\n\n💡 Ejemplo: *\"Pon 8 horas en Desarrollo\"*"}]
    
    # 🚨 Detectar comandos vacíos (solo fecha + guardar)
    if len(ordenes) == 2:
        if (ordenes[0].get('accion') == 'seleccionar_fecha' and 
            ordenes[1].get('accion') in ['guardar_linea', 'emitir_linea']):
            return [{"accion": "error_validacion", "mensaje": "🤔 **No he entendido qué quieres que haga.**\n\nNecesito más información:\n- ¿Qué proyecto?\n- ¿Cuántas horas?\n- ¿Qué acción realizar?\n\n💡 Ejemplos:\n- *\"Pon 8 horas en Desarrollo\"*\n- *\"Borra las horas del martes\"*\n- *\"Lista los proyectos\"*"}]
    
    # 🚨 Detectar comandos sin sentido (solo guardar)
    if len(ordenes) == 1 and ordenes[0].get('accion') in ['guardar_linea', 'emitir_linea']:
        return [{"accion": "error_validacion", "mensaje": "🤔 **¿Qué quieres que haga exactamente?**\n\nPuedo ayudarte con:\n- Imputar horas: *\"Pon 8h en Desarrollo\"*\n- Consultar horas: *\"¿Cuántas horas tengo hoy?\"*\n- Borrar horas: *\"Borra las del martes\"*\n- Listar proyectos: *\"Lista los proyectos\"*"}]
    
    # 🚨 Detectar: seleccionar_proyecto + guardar (sin imputación real)
    if len(ordenes) == 3:
        if (ordenes[0].get('accion') == 'seleccionar_fecha' and
            ordenes[1].get('accion') == 'seleccionar_proyecto' and
            ordenes[2].get('accion') in ['guardar_linea', 'emitir_linea']):
            nombre_proyecto = ordenes[1].get('parametros', {}).get('nombre')
            if nombre_proyecto:
                return [{"accion": "info_incompleta", "info_parcial": {"proyecto": nombre_proyecto}, "que_falta": "horas_y_dia", "mensaje": f"📝 Vale, **{nombre_proyecto}**. ¿Cuántas horas quieres imputar y para qué día?\n\n💡 Ejemplos:\n- *\"Pon 8 horas hoy\"*\n- *\"5 horas el lunes\"*\n- *\"Toda la semana\"*"}]
    
    return None  # ✅ Comando válido


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
   - "Ponme 3 horas en staff en el proyecto permiso" → {{"nombre": "Permiso", "nodo_padre": "Staff"}}
   - "Pon 5h en administracion en permiso" → {{"nombre": "Permiso", "nodo_padre": "Administración"}}
   - "3h en comercial en desarrollo" → {{"nombre": "Desarrollo", "nodo_padre": "Comercial"}}
   
   → Debes generar:
   {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo", "nodo_padre": "Departamento Desarrollo"}}}}
   
   🔍 REGLAS DE DETECCIÓN - ⚠️ EXTREMADAMENTE IMPORTANTE:
   
   **REGLA #1 - DOBLE "EN" (LA MÁS IMPORTANTE):**
   Si la frase contiene DOS menciones de "en", la PRIMERA indica nodo_padre:
   - "en [X] en [Y]" → nodo_padre: X, nombre: Y
   - "en [X] en el proyecto [Y]" → nodo_padre: X, nombre: Y
   - "en [X] en la tarea [Y]" → nodo_padre: X, nombre: Y
   
   Ejemplos aplicando REGLA #1:
   - "ponme 3h en staff en permiso" → {{"nombre": "Permiso", "nodo_padre": "Staff"}}
   - "pon 5h en administracion en desarrollo" → {{"nombre": "Desarrollo", "nodo_padre": "Administración"}}
   - "añade 2h en comercial en estudio" → {{"nombre": "Estudio", "nodo_padre": "Comercial"}}
   
   **REGLA #2 - PALABRAS CLAVE:**
   - "Departamento [X]" → nodo_padre: "Departamento X"
   - "Área [X]" → nodo_padre: "Área X"
   - "Staff", "Administración", "Comercial" → nodo_padre cuando están solas
   
   **REGLA #3 - PREPOSICIONES:**
   - "del departamento [X]" → nodo_padre: X
   - "de [X]" (cuando X es organización/área) → nodo_padre: X
   
   **REGLA #4 - SEPARADORES:**
   - "[X] / [Y]" → nodo_padre: X, nombre: Y
   - "[X] - [Y]" → nodo_padre: X, nombre: Y
   
   🚨 IMPORTANTE: 
   - Si NO hay ningún indicador claro de nodo_padre, NO lo inventes
   - Si hay DUDA, aplicar REGLA #1 (doble "en") - es la más confiable
   - Capitalizar: "staff" → "Staff", "administracion" → "Administración".
   
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

