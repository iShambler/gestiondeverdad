"""
Intérprete de comandos en lenguaje natural.
Traduce instrucciones del usuario a comandos JSON estructurados.

CORRECCIÓN APLICADA:
-  Validación post-GPT: SIEMPRE añadir 'dia' a imputar_horas_dia si GPT lo omite (usar hoy por defecto)
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

    # Imputación válida = tiene acción de imputar CON horas != 0 O con modo establecer
    tiene_imputacion = False
    for o in ordenes:
        if o.get("accion") == "imputar_horas_dia":
            horas = o.get("parametros", {}).get("horas", 0)
            modo = o.get("parametros", {}).get("modo", "sumar")
            # Es imputación válida si tiene horas != 0 O si modo es establecer
            if horas != 0 or modo == "establecer":
                tiene_imputacion = True
                break
        elif o.get("accion") == "imputar_horas_semana":
            tiene_imputacion = True
            break

    tiene_eliminacion = any(o.get("accion") == "eliminar_linea" for o in ordenes)
    tiene_borrado_horas = any(o.get("accion") == "borrar_todas_horas_dia" for o in ordenes)
    tiene_copiar_semana = any(o.get("accion") == "copiar_semana_anterior" for o in ordenes)

    print(f"[DEBUG]  Validación - proyecto:{tiene_proyecto} imputacion:{tiene_imputacion} eliminacion:{tiene_eliminacion} borrado:{tiene_borrado_horas} copiar:{tiene_copiar_semana}")

    #  Si hay eliminación, borrado de horas o copiar semana → NO VALIDAR (son acciones válidas sin imputación)
    if tiene_eliminacion or tiene_borrado_horas or tiene_copiar_semana:
        print(f"[DEBUG]  Acción especial detectada, omitiendo validación")
        return None

    # ----------------------------------------------------------------------
    #  2. Proyecto sin imputación → Falta horas y día
    # ----------------------------------------------------------------------
    if tiene_proyecto and not tiene_imputacion:
        print(f"[DEBUG]  Detectado: proyecto SIN imputación - preguntando horas")
        for orden in ordenes:
            if orden.get("accion") == "seleccionar_proyecto":
                nombre_proyecto = orden.get("parametros", {}).get("nombre")
                break
        else:
            nombre_proyecto = None

        if nombre_proyecto:
            print(f"[DEBUG]  Proyecto encontrado: {nombre_proyecto}")
            return [{
                "accion": "info_incompleta",
                "info_parcial": {"proyecto": nombre_proyecto},
                "que_falta": "horas_y_dia",
                "mensaje": (
                    f" Vale, **{nombre_proyecto}**. ¿Cuántas horas y para qué día?\n\n"
                    " Ejemplos:\n- \"Pon 8 horas hoy\"\n- \"5 horas el lunes\"\n- \"Toda la semana\""
                )
            }]

        return [{
            "accion": "error_validacion",
            "mensaje": " ¿Cuántas horas quieres imputar y para qué día?"
        }]

    # ----------------------------------------------------------------------
    #  3. Imputación sin proyecto → FLUJO DE LECTURA PREVIA
    # ----------------------------------------------------------------------
    if tiene_imputacion and not tiene_proyecto:
        print(f"[DEBUG]  Detectado: imputación SIN proyecto - requiere lectura previa")

        # Extraer información de la imputación
        horas_a_modificar = 0
        modo = "sumar"
        dia_objetivo = None

        for orden in ordenes:
            if orden.get("accion") == "imputar_horas_dia":
                horas_a_modificar = orden["parametros"]["horas"]
                modo = orden["parametros"].get("modo", "sumar")
                dia_objetivo = orden["parametros"]["dia"]
                break
            if orden.get("accion") == "imputar_horas_semana":
                # Para semana completa, no tiene sentido modificar sin proyecto
                return [{
                    "accion": "error_validacion",
                    "mensaje": "🤔 ¿A qué proyecto quieres imputar toda la semana?"
                }]

        #  Convertir fecha ISO a nombre de día
        dia_nombre = None
        if dia_objetivo:
            try:
                fecha_obj = datetime.strptime(dia_objetivo, "%Y-%m-%d")
                dia_nombre_en = fecha_obj.strftime("%A").lower()
                dias_map = {
                    "monday": "lunes",
                    "tuesday": "martes",
                    "wednesday": "miércoles",
                    "thursday": "jueves",
                    "friday": "viernes",
                    "saturday": "sábado",
                    "sunday": "domingo"
                }
                dia_nombre = dias_map.get(dia_nombre_en, dia_nombre_en)
            except:
                dia_nombre = "lunes"  # fallback
        else:
            dia_nombre = "lunes"

        #  DEVOLVER ACCIÓN ESPECIAL: leer_tabla_y_preguntar
        # Esta acción le dirá al ejecutor que lea la tabla y pregunte al usuario
        return [{
            "accion": "leer_tabla_y_preguntar",
            "parametros": {
                "fecha": dia_objetivo,
                "dia": dia_nombre,
                "horas": horas_a_modificar,
                "modo": modo
            }
        }]

    # ----------------------------------------------------------------------
    #  4. Comandos realmente vacíos (solo seleccionar_fecha sin más acciones)
    # ----------------------------------------------------------------------
    #  PERMITIR: emitir_linea / guardar_linea (con o sin seleccionar_fecha)
    #  RECHAZAR: solo seleccionar_fecha sin ninguna acción después
    
    # Caso: SOLO seleccionar_fecha, nada más
    if len(ordenes) == 1 and ordenes[0].get("accion") == "seleccionar_fecha":
        return [{
            "accion": "error_validacion",
            "mensaje": "🤔 ¿Qué quieres hacer en esa fecha?"
        }]
    
    # NOTA: emitir_linea y guardar_linea SOLAS son válidas (trabajan sobre la tabla actual)
    # NOTA: seleccionar_fecha + emitir_linea/guardar_linea es válido (trabaja sobre otra fecha)

    # ----------------------------------------------------------------------
    # TODO LO DEMÁS ES VÁLIDO
    # ----------------------------------------------------------------------
    return None


def interpretar_con_gpt(texto, contexto=None, tabla_actual=None, historial=None):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")

    #  Pasar tabla al contexto para que validar_ordenes pueda usarla
    if contexto is None:
        contexto = {}
    if tabla_actual:
        contexto["tabla_actual"] = tabla_actual

    #  Añadir información de la tabla actual si está disponible
    info_tabla = ""
    if tabla_actual and len(tabla_actual) > 0:
        info_tabla = "\n\n ESTADO ACTUAL DE LA TABLA DE IMPUTACIÓN:\n"
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

        info_tabla += "\n IMPORTANTE: Puedes usar esta información para:\n"
        info_tabla += "  - Copiar horas de un proyecto a otro\n"
        info_tabla += "  - Duplicar/triplicar horas\n"
        info_tabla += "  - Sumar o restar basándote en datos existentes\n"
        info_tabla += "  - Distribuir horas proporcionalmente\n"

    #  HISTORIAL DE CONVERSACIÓN
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
        info_historial += " Usa este historial para entender mejor el contexto y las intenciones del usuario.\n"
        info_historial += " Si el usuario dice 'lo mismo', 'otra vez', 'igual', etc., busca en el historial qué hizo antes.\n"

    # Usar f-string pero con llaves cuádruples {{{{ para que se escapen correctamente
    prompt = f"""
Eres un asistente que convierte frases en lenguaje natural en una lista de acciones JSON
para automatizar una web de imputación de horas. Devuelves SOLO un array JSON, sin texto
extra, sin markdown, sin explicaciones.

====================================================
CONTEXTO
====================================================
Hoy es {hoy} ({dia_semana}).
{info_tabla}{info_historial}

====================================================
REGLAS GENERALES
====================================================
 REGLA CRÍTICA - "LA SEMANA PASADA":
Antes de continuar, IMPORTANTE distinguir:
- "COPIA/DUPLICA/REPITE la semana pasada" → copiar_semana_anterior (trae datos a semana actual)
- "EMITE/GUARDA/BORRA la semana pasada" → seleccionar_fecha(lunes_sem_pasada) + acción (trabaja EN semana pasada)

Ejemplos:
- "Copia la semana pasada" → [{{"accion": "copiar_semana_anterior"}}]
- "Emite la semana pasada" → [{{"accion": "seleccionar_fecha", ...}}, {{"accion": "emitir_linea"}}]

1. Orden de acciones:
   a) seleccionar_fecha:
      - SIEMPRE cuando uses imputar_horas_semana (calcular lunes de la semana)
      - Cuando la fecha != hoy
      - Cuando se especifica un día concreto ("el lunes", "mañana", etc.)
   b) iniciar_jornada (si se menciona)
   c) seleccionar_proyecto (cuando se impute/borre de un proyecto)
   d) imputar_horas_dia / imputar_horas_semana / borrar_todas_horas_dia / eliminar_linea
   e) finalizar_jornada (si se menciona)
   f) guardar_linea (solo cuando se CAMBIA DE SEMANA o al FINAL de todo)
1.5. REGLA ESPECIAL - PROYECTO "VACACIONES":
   Cuando el proyecto sea "Vacaciones" (sin importar el nodo_padre):
   - Si el usuario NO menciona horas → usar 8 horas por defecto (jornada completa)
   - Si el usuario SÍ menciona horas → respetar las horas indicadas
   
   Ejemplos:
   - "Pon vacaciones el lunes" → 8 horas (default)
   - "Vacaciones en admin-staf el martes" → 8 horas (default)
   - "Pon 4 horas en vacaciones el miércoles" → 4 horas (respeta)
   - "Vacaciones toda la semana" → 8h cada día (default)
   - "Media jornada de vacaciones" → 4 horas (respeta "media jornada" = 4h)
   
   IMPORTANTE: Esto solo aplica si el nombre del proyecto contiene "Vacaciones" (case-insensitive)
2. Fechas:
   - "hoy" = {hoy}. Sin fecha → usar {hoy}
   - "ayer" = hoy -1; "mañana" = hoy +1
   -  REGLA CRÍTICA: SIEMPRE usar la FECHA EXACTA del día mencionado, NUNCA el lunes de esa semana
     - Si dice "el jueves de la semana pasada" → calcular la fecha del JUEVES de la semana pasada
     - Si dice "el martes" → calcular la fecha del MARTES de esta semana
     - NUNCA sustituir por el lunes, SIEMPRE el día específico mencionado
   - Ejemplos con hoy = {hoy} ({dia_semana}):
     - "el lunes" → lunes de ESTA semana (calcular fecha exacta)
     - "el jueves" → jueves de ESTA semana (calcular fecha exacta)
     - "el jueves de la semana pasada" → jueves de la SEMANA ANTERIOR (calcular fecha exacta)
     - "el martes de la próxima semana" → martes de la SEMANA SIGUIENTE (calcular fecha exacta)
   - "la semana pasada" sin día específico → lunes de la semana anterior
   - "próxima semana" sin día específico → lunes de la semana siguiente
   -  TANTO seleccionar_fecha COMO imputar_horas_dia deben usar LA MISMA FECHA EXACTA del día mencionado
   -  CRÍTICO: Si el usuario NO menciona un día específico, SIEMPRE usar {hoy}

3. Proyectos múltiples del MISMO día → INTERCALAR sin guardar_linea entre ellos:
   "3h en X y 2h en Y" (mismo día) → seleccionar_fecha → seleccionar_proyecto(X) → imputar(3) → seleccionar_proyecto(Y) → imputar(2) → guardar_linea (UNA VEZ AL FINAL)

4. Múltiples días de la MISMA SEMANA con DIFERENTES proyectos → NO guardar entre días, solo al FINAL:
   Ejemplo: "3h en X el lunes, 5h en Y el miércoles" (ambos semana 16-20 dic) → fecha(lunes) → proyecto(X) → imputar(3) → fecha(miércoles) → proyecto(Y) → imputar(5) → guardar_linea (UNA VEZ AL FINAL)

5.  CRÍTICO - MISMO proyecto en MÚLTIPLES días de la MISMA SEMANA:
   - seleccionar_proyecto UNA SOLA VEZ al inicio de cada semana
   - Luego múltiples imputar_horas_dia (uno por cada día)
   - NO repetir seleccionar_proyecto entre días de la misma semana
   - Ejemplo: "4h en Estudio lunes, martes, jueves" → seleccionar_fecha(primera_fecha) + seleccionar_proyecto(Estudio) + imputar(lunes) + imputar(martes) + imputar(jueves) + guardar_linea

6.  CRÍTICO - Cambio de SEMANA → SIEMPRE guardar Y volver a seleccionar proyecto:
   - ANTES de cambiar de semana → guardar_linea
   - DESPUÉS de cambiar de semana → seleccionar_proyecto (OBLIGATORIO)
   - Ejemplo: "8h en Vacaciones el 26/12, 29/12, 30/12" (semanas diferentes):
     * fecha(26/12) → seleccionar_proyecto(Vacaciones) → imputar(26/12) → guardar_linea
     * fecha(29/12) → seleccionar_proyecto(Vacaciones) → imputar(29/12) + imputar(30/12) → guardar_linea
   
   REGLA ABSOLUTA: Después de cada guardar_linea, si hay más acciones pendientes:
   - SIEMPRE incluir seleccionar_proyecto antes de imputar
   - Aunque sea el mismo proyecto
   - Porque guardar_linea limpia el contexto del navegador

7. REGLA CLAVE: guardar_linea solo cuando:
   - Vas a cambiar de semana (antes del cambio)
   - Al final de TODAS las órdenes

====================================================
NODO PADRE - JERÁRQUIA COMPLETA
====================================================
La estructura jerárquica es: Empresa/Cliente → Departamento/Área → Proyecto

REGLA #1 (PRIORIDAD): Doble "en" → primera = nodo_padre, segunda = proyecto
  Ejemplos:
  - "3h en staff en permiso" → {{"nombre": "Permiso", "nodo_padre": "Staff"}}
  - "4h en desarrollo en subvenciones" → {{"nombre": "Desarrollo", "nodo_padre": "Subvenciones"}}
  - "5h en subvenciones en marketing" → {{"nombre": "Marketing", "nodo_padre": "Subvenciones"}}

REGLA #2: Palabras clave de jerarquía
  - "Departamento X", "Área X", "Staff", "Administración", "Comercial", "Subvenciones"
  - Separadores: "X / Y", "X - Y" → nodo_padre = X, nombre = Y
  - Capitalizar siempre los nombres

 IMPORTANTE: El nodo_padre puede ser un departamento ("Subvenciones") o una empresa/cliente ("Inn2Travel", "Menpe")
El sistema buscará el proyecto dentro de ese nodo específico.

====================================================
TIPOS DE ACCIONES
====================================================
1) IMPUTAR HORAS:
   - imputar_horas_dia: Para UN día específico. Requiere día y horas.
     Modo: "sumar" (default) o "establecer" (si dice "totales", "cambia a", "exactamente")

      QUITAR / RESTAR / SUMAR:
     - "quita 2h" o "resta 2h" → horas: -2 (NEGATIVO), modo: "sumar"
     - "suma 3h" o "añade 3h" → horas: 3 (POSITIVO), modo: "sumar"
     - "pon 5h" o "establece 5h" → horas: 5, modo: "establecer"

      CRÍTICO - DÍA OBLIGATORIO:
     - SIEMPRE incluir el parámetro "dia" en imputar_horas_dia
     - Si el usuario NO menciona un día → usar {hoy}
     - Ejemplos:
       * "quita 2h" → {{"dia": "{hoy}", "horas": -2}}
       * "suma 3h el viernes" → {{"dia": "2026-01-17", "horas": 3}}

      REGLA CRÍTICA - NO ADIVINAR PROYECTOS:
     Si el usuario dice "quita/suma/establece X horas" SIN mencionar explícitamente el proyecto,
     NO incluyas 'seleccionar_proyecto'. El sistema preguntará automáticamente.

     Ejemplos de CUÁNDO NO incluir seleccionar_proyecto:
     - "quita 2h el viernes" → NO proyecto (usuario no lo mencionó)
     - "suma 3h hoy" → NO proyecto
     - "establece 5h el lunes" → NO proyecto
     - "quitale media hora" → NO proyecto
     - "quitale 6 horas el viernes" → NO proyecto

     Ejemplos de CUÁNDO SÍ incluir seleccionar_proyecto:
     - "quita 2h A Desarrollo" → SÍ proyecto ("A Desarrollo" = explícito)
     - "suma 3h EN Formación" → SÍ proyecto ("EN Formación" = explícito)
     - "quita 2h DE Estudio" → SÍ proyecto ("DE Estudio" = explícito)
     - "quitale 2h A Estudio" → SÍ proyecto ("A Estudio" = explícito)
     - "establece Desarrollo a 5h" → SÍ proyecto ("Desarrollo" mencionado)

      Si hay duda: si el proyecto NO está en el texto del usuario, NO lo incluyas.

   - imputar_horas_semana: Para TODA LA SEMANA (L-V). NO requiere parámetros.
      CRÍTICO: SIEMPRE debe ir precedida de seleccionar_fecha con el LUNES de la semana
      Si el usuario NO especifica semana → calcular el lunes de la semana ACTUAL
      OBLIGATORIO usar cuando el usuario diga:
        - "toda la semana", "la semana entera", "semana completa"
        - "de lunes a viernes", "todos los días"
        - "imputa la semana", "rellena la semana"
     El sistema automáticamente usa las horas correctas (8.5h L-J, 6.5h V)
     y omite días que ya tengan horas (festivos, vacaciones, etc.)

     Ejemplos:
     - "pon toda la semana en Desarrollo" → seleccionar_fecha(lunes_semana_actual) + seleccionar_proyecto + imputar_horas_semana
     - "imputa la semana en Formación" → seleccionar_fecha(lunes_semana_actual) + seleccionar_proyecto + imputar_horas_semana

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

5) COPIAR SEMANA ANTERIOR vs TRABAJAR EN SEMANA PASADA:
    IMPORTANTE: "la semana pasada" tiene dos interpretaciones según el verbo:
   
   A) COPIAR (traer datos a semana actual):
      - "copia la semana pasada", "igual que la semana pasada", "lo mismo que la semana anterior"
      - "carga el horario de la semana pasada", "repite la semana pasada"
      - "duplica la semana anterior", "clona la semana pasada"
      - → copiar_semana_anterior (SIN PARÁMETROS, es una acción atómica)
      - Esta acción va SOLA, no necesita seleccionar_fecha ni guardar_linea
      - Lee los proyectos/horas de la semana pasada y los copia a la actual automáticamente
   
   B) TRABAJAR EN SEMANA PASADA (navegar a ella):
      - "emite la semana pasada", "guarda la semana pasada"
      - "consulta la semana pasada", "ve a la semana pasada"
      - "imputa X horas en la semana pasada", "borra la semana pasada"
      - → seleccionar_fecha (lunes de semana pasada) + [acción correspondiente]
      - Ejemplos:
        * "Emite la semana pasada" → seleccionar_fecha(lunes_sem_pasada) + emitir_linea
        * "Guarda la semana pasada" → seleccionar_fecha(lunes_sem_pasada) + guardar_linea
        * "Borra la semana pasada" → seleccionar_fecha(lunes_sem_pasada) + borrar_todas_horas... + guardar_linea
   
    REGLA CLAVE: 
   - Si el verbo es COPIAR/CLONAR/DUPLICAR/REPETIR → copiar_semana_anterior
   - Si el verbo es EMITIR/GUARDAR/BORRAR/IMPUTAR/VER → seleccionar_fecha + acción

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

"Quítale 2 horas a Estudio hoy"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Estudio"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": -2, "modo": "sumar"}}}},
  {{"accion": "guardar_linea"}}
]

"Suma 1.5h a Formación el martes"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-13"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Formación"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-13", "horas": 1.5, "modo": "sumar"}}}},
  {{"accion": "guardar_linea"}}
]

"Quita 6 horas el viernes" (SIN proyecto explícito)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-16"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-16", "horas": -6, "modo": "sumar"}}}}
]
NOTA: NO incluye seleccionar_proyecto porque el usuario NO mencionó ningún proyecto.

"Quitale media hora" (SIN día ni proyecto)
[
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": -0.5, "modo": "sumar"}}}}
]
NOTA: Usa hoy por defecto porque no mencionó día. NO incluye proyecto porque no lo mencionó.

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

"Ponme 4h en Estudio el lunes, el martes y el jueves" (MISMO proyecto, MÚLTIPLES días)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-20"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Estudio"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-20", "horas": 4}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-21", "horas": 4}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-23", "horas": 4}}}},
  {{"accion": "guardar_linea"}}
]
NOTA CRÍTICA: MISMO proyecto → seleccionar_proyecto UNA SOLA VEZ al principio. NO repetir entre días

"8h en Vacaciones en Admin-Staf los días 26/12/2025, 29/12/2025, 30/12/2025, 31/12/2025, 02/01/2026"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-26"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones", "nodo_padre": "Admin-Staf"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-26", "horas": 8}}}},
  {{"accion": "guardar_linea"}},
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2025-12-29"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones", "nodo_padre": "Admin-Staf"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-29", "horas": 8}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-30", "horas": 8}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2025-12-31", "horas": 8}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-02", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]
NOTA CRÍTICA: 
- 26/12 está en semana del 22/12 (lunes)
- 29/12 está en semana del 29/12 (lunes)
- Cambio de semana detectado → guardar_linea ANTES de cambiar
- OBLIGATORIO: seleccionar_proyecto DESPUÉS de cada guardar_linea
- 29/12, 30/12, 31/12, 02/01 son la misma semana → NO repetir seleccionar_proyecto entre ellos

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

"Copia la semana pasada" / "Igual que la semana anterior" / "Carga el horario de la semana pasada"
[
  {{"accion": "copiar_semana_anterior"}}
]
NOTA: Estos verbos (copiar, igual, cargar) indican COPIAR datos a la semana actual.

"Emite la semana pasada" (hoy es {hoy}, semana pasada = lunes 2026-01-13)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-13"}}}},
  {{"accion": "emitir_linea"}}
]
NOTA: "Emite" NO es copiar, es trabajar EN la semana pasada. Calcular lunes de semana anterior.

"Guarda la semana pasada" (hoy es {hoy}, semana pasada = lunes 2026-01-13)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-13"}}}},
  {{"accion": "guardar_linea"}}
]

"Borra las horas de la semana pasada" (hoy es {hoy}, semana pasada = lunes 2026-01-13)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-13"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "lunes"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "martes"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "miércoles"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "jueves"}}}},
  {{"accion": "borrar_todas_horas_dia", "parametros": {{"dia": "viernes"}}}},
  {{"accion": "guardar_linea"}}
]

"Pon 4 horas en desarrollo en subvenciones" (doble "en" = nodo_padre + proyecto)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo", "nodo_padre": "Subvenciones"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 4}}}},
  {{"accion": "guardar_linea"}}
]
NOTA: "desarrollo en subvenciones" → primera "en" = nodo_padre (Subvenciones), segunda implícita = proyecto (Desarrollo)

"Pon toda la semana en Desarrollo" (hoy es {hoy} que es {dia_semana}, calcular lunes de esta semana)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "[LUNES_SEMANA_ACTUAL]"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_semana"}},
  {{"accion": "guardar_linea"}}
]
NOTA: Calcular el lunes de la semana actual:
- Si hoy es lunes a domingo → ir hacia atrás hasta encontrar el lunes de esta semana
- Domingo pertenece a la semana que termina (lunes anterior)

"Imputa la semana en Formación" (sin especificar = semana actual)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "[LUNES_SEMANA_ACTUAL]"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Formación"}}}},
  {{"accion": "imputar_horas_semana"}},
  {{"accion": "guardar_linea"}}
]
"Pon vacaciones el lunes" (sin mencionar horas = 8h default)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-20"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-20", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]
NOTA: Proyecto "Vacaciones" sin horas → automáticamente 8h

"Vacaciones en admin-staf el martes y el miércoles"
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-21"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones", "nodo_padre": "Admin-Staf"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-21", "horas": 8}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-22", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]
NOTA: Vacaciones sin horas especificadas → 8h por defecto en cada día

"Pon 4 horas en vacaciones el jueves" (horas explícitas = respeta)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "2026-01-23"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "2026-01-23", "horas": 4}}}},
  {{"accion": "guardar_linea"}}
]
NOTA: Usuario especificó 4 horas → se respeta

"Vacaciones toda la semana" (sin horas = 8h cada día)
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "[LUNES_SEMANA_ACTUAL]"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Vacaciones"}}}},
  {{"accion": "imputar_horas_semana"}},
  {{"accion": "guardar_linea"}}
]
NOTA: imputar_horas_semana usa automáticamente 8.5h (L-J) y 6.5h (V)
====================================================
OUTPUT: SOLO JSON, SIN TEXTO ADICIONAL
====================================================
Frase del usuario: "{texto}"
"""

    try:
        client = settings.get_openai_client()  #  Necesario para usar la API

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_MINI,
            messages=[
                {"role": "system", "content": "Eres un intérprete experto de lenguaje natural a comandos JSON estructurados. Procesas instrucciones complejas con alta precisión, manejando múltiples proyectos, fechas relativas y contextos ambiguos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        print(f"[DEBUG]  GPT generó: {raw}")

        #  Limpiar markdown si GPT-4o lo añade (```json ... ```)
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])  # Quitar primera y última línea
            raw = raw.strip()
            print(f"[DEBUG]  JSON limpio: {raw}")

        data = json.loads(raw)

        # Si devuelve un solo objeto, lo convertimos a lista
        if isinstance(data, dict):
            data = [data]

        #  VALIDACIÓN POST-GPT: Asegurar que imputar_horas_dia SIEMPRE tenga 'dia'
        for orden in data:
            if orden.get("accion") == "imputar_horas_dia":
                parametros = orden.get("parametros", {})
                # Si no tiene 'dia', usar hoy por defecto
                if "dia" not in parametros or not parametros.get("dia"):
                    parametros["dia"] = hoy
                    orden["parametros"] = parametros
                    print(f"[DEBUG]  GPT omitió 'dia' en imputar_horas_dia, usando hoy: {hoy}")

        #  VALIDAR que las órdenes tengan sentido
        resultado_validacion = validar_ordenes(data, texto, contexto)
        if resultado_validacion:
            # Si devuelve algo, es porque hay error o info incompleta
            print(f"[DEBUG]  Comando requiere atención: {texto}")
            return resultado_validacion

        return data

    except Exception as e:
        print(f"[DEBUG] Error interpretando comando: {e}")
        return []