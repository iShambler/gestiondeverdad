"""
Funciones de consulta de información sobre horas imputadas.
Incluye consultas de días y semanas específicas.
"""

import time
from datetime import timedelta


def consultar_dia(driver, wait, fecha_obj, canal="webapp"):
    """
    Consulta la información de un día específico.
    Navega a la fecha, lee la tabla y devuelve un resumen del día.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        fecha_obj: Objeto datetime con la fecha a consultar
        canal: Canal de origen ("webapp" o "slack")
        
    Returns:
        str: Resumen formateado con las horas del día
    """
    from web_automation import lunes_de_semana, seleccionar_fecha, leer_tabla_imputacion
    
    print(f"[DEBUG] 📅 consultar_dia - Fecha recibida: {fecha_obj.strftime('%Y-%m-%d %A')}")
    
    try:
        # 🆕 Navegar directamente a la fecha del día (no al lunes)
        # Esto asegura que el día esté habilitado en la vista
        seleccionar_fecha(driver, fecha_obj)
        time.sleep(2)  # Esperar a que cargue la tabla
        
        # Leer la información de la tabla
        proyectos = leer_tabla_imputacion(driver)
        
        if not proyectos:
            fecha_str = fecha_obj.strftime('%d/%m/%Y')
            return f"No hay horas imputadas el {fecha_str}"
        
        # Determinar qué día de la semana es
        dia_semana_num = fecha_obj.weekday()  # 0=lunes, 4=viernes
        dias_nombres = ["lunes", "martes", "miércoles", "jueves", "viernes"]
        dia_nombre = dias_nombres[dia_semana_num] if dia_semana_num < 5 else None
        
        if not dia_nombre:
            return f"El día seleccionado es fin de semana"
        
        # Formatear la información
        fecha_str = fecha_obj.strftime('%d/%m/%Y')
        dia_nombre_capitalize = dia_nombre.capitalize()
        
        resumen = f"📅 {dia_nombre_capitalize} {fecha_str}\n\n"
        
        total_dia = 0
        proyectos_con_horas = []
        
        for proyecto in proyectos:
            nombre_corto = proyecto['proyecto'].split(' - ')[-1]  # Solo la última parte
            horas_dia = proyecto['horas'][dia_nombre]
            
            # 🆕 CONDICIÓN: Solo mostrar proyectos con horas > 0
            if horas_dia > 0:
                proyectos_con_horas.append((nombre_corto, horas_dia))
                total_dia += horas_dia
        
        if not proyectos_con_horas:
            return f"📅 {dia_nombre_capitalize} {fecha_str}\n\n⚪ No hay horas imputadas este día"
        
        # 🌐 Si es webapp, generar tabla HTML
        if canal == "webapp":
            resumen = f"<h3 style='margin: 0 0 5px 0;'>📅 {dia_nombre_capitalize} {fecha_str}</h3>\n"
            resumen += "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%;'>\n"
            resumen += "<thead><tr style='background-color: #f0f0f0;'><th>Proyecto</th><th>Horas</th></tr></thead>\n"
            resumen += "<tbody>\n"
            
            for nombre, horas in proyectos_con_horas:
                resumen += f"<tr><td>{nombre}</td><td style='text-align: center;'>{horas}h</td></tr>\n"
            
            # Determinar color de la celda total según validación
            limite_horas = 6.5 if dia_nombre == 'viernes' else 8.5
            if total_dia > limite_horas:
                color_fondo = '#ffcccc'  # Rojo claro - Exceso
            elif 0 < total_dia < limite_horas:
                color_fondo = '#fff8dc'  # Amarillo claro - Faltan horas
            else:
                color_fondo = '#e8f4f8'  # Azul claro - Correcto
            
            resumen += f"<tr style='background-color: {color_fondo}; font-weight: bold;'><td>Total</td><td style='text-align: center;'>{total_dia}h</td></tr>\n"
            resumen += "</tbody></table>\n"
        else:
            # 💬 Formato texto para Slack
            for nombre, horas in proyectos_con_horas:
                resumen += f"🔹 {nombre}: {horas}h\n"
            
            resumen += f"\n📊 Total: {total_dia} horas"
        
        # ⚠️ VALIDACIONES DE HORAS
        avisos = []
        
        # Determinar límite de horas según el día (viernes = 6.5h, resto = 8.5h)
        limite_horas = 6.5 if dia_nombre == 'viernes' else 8.5
        
        # Verificar si hay exceso de horas
        if total_dia > limite_horas:
            horas_exceso = round(total_dia - limite_horas, 2)
            avisos.append(f"⚠️ EXCESO: Te has pasado {horas_exceso}h en este día.")
        
        # Verificar si faltan horas
        elif 0 < total_dia < limite_horas:
            horas_faltantes = round(limite_horas - total_dia, 2)
            avisos.append(f"⚠️ FALTAN HORAS: Te faltan {horas_faltantes}h para completar la jornada.")
        
        # Mostrar avisos si existen
        if avisos:
            if canal == "webapp":
                resumen += "<p style='margin-top: 10px; font-size: 0.9em; color: #666;'>\n"
                for aviso in avisos:
                    resumen += f"* {aviso}<br>\n"
                resumen += "</p>\n"
            else:
                resumen += "\n\n"
                for aviso in avisos:
                    resumen += f"{aviso}\n"
                resumen += "\n¿Es correcto o necesitas modificarlo?"
        
        print(f"[DEBUG] ✅ consultar_dia - Resumen generado ({len(resumen)} caracteres)")
        print(f"[DEBUG] Primeras 200 chars: {resumen[:200]}")
        return resumen
    
    except Exception as e:
        return f"No he podido consultar ese día: {e}"


def consultar_semana(driver, wait, fecha_obj, canal="webapp"):
    """
    Consulta la información de una semana específica.
    Navega a la fecha, lee la tabla y devuelve un resumen.
    
    🆕 IMPORTANTE: Detecta si hay días deshabilitados en la vista actual
    y hace una segunda consulta si es necesario para obtener todos los datos.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        fecha_obj: Objeto datetime con la fecha (cualquier día de la semana)
        canal: Canal de origen ("webapp" o "slack")
        
    Returns:
        str: Resumen formateado con las horas de la semana
    """
    from web_automation import lunes_de_semana, seleccionar_fecha, leer_tabla_imputacion, detectar_dias_deshabilitados
    
    print(f"[DEBUG] 📅 consultar_semana - Fecha recibida: {fecha_obj.strftime('%Y-%m-%d %A')}")
    
    try:
        # Calcular lunes y viernes de la semana
        lunes = lunes_de_semana(fecha_obj)
        viernes = lunes + timedelta(days=4)
        
        print(f"[DEBUG] 📅 Semana: {lunes.strftime('%d/%m/%Y')} - {viernes.strftime('%d/%m/%Y')}")
        
        # Diccionario para acumular horas de todos los proyectos
        proyectos_combinados = {}
        
        # =====================================================
        # CONSULTA 1: Navegar al LUNES
        # =====================================================
        print(f"[DEBUG] 📊 Consulta 1: Navegando al lunes {lunes.strftime('%d/%m/%Y')}...")
        seleccionar_fecha(driver, lunes)
        time.sleep(2)
        
        # 🆕 Detectar si hay días deshabilitados
        dias_estado = detectar_dias_deshabilitados(driver)
        dias_deshabilitados = [dia for dia, habilitado in dias_estado.items() if not habilitado]
        
        proyectos_lunes = leer_tabla_imputacion(driver)
        print(f"[DEBUG] 📊 Consulta 1 (lunes): {len(proyectos_lunes)} proyectos encontrados")
        
        # Acumular proyectos de la primera consulta
        for proyecto in proyectos_lunes:
            nombre = proyecto['proyecto']
            if nombre not in proyectos_combinados:
                proyectos_combinados[nombre] = {
                    'proyecto': nombre,
                    'horas': {'lunes': 0, 'martes': 0, 'miércoles': 0, 'jueves': 0, 'viernes': 0}
                }
            # Sumar horas de cada día
            for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                proyectos_combinados[nombre]['horas'][dia] += proyecto['horas'].get(dia, 0)
        
        # =====================================================
        # CONSULTA 2: Si hay días deshabilitados, navegar al VIERNES
        # =====================================================
        if dias_deshabilitados:
            print(f"[DEBUG] 🔄 Consulta 2: Navegando al viernes {viernes.strftime('%d/%m/%Y')} para completar días: {dias_deshabilitados}...")
            seleccionar_fecha(driver, viernes)
            time.sleep(2)
            
            proyectos_viernes = leer_tabla_imputacion(driver)
            print(f"[DEBUG] 📊 Consulta 2 (viernes): {len(proyectos_viernes)} proyectos encontrados")
            
            # Acumular proyectos de la segunda consulta
            for proyecto in proyectos_viernes:
                nombre = proyecto['proyecto']
                if nombre not in proyectos_combinados:
                    proyectos_combinados[nombre] = {
                        'proyecto': nombre,
                        'horas': {'lunes': 0, 'martes': 0, 'miércoles': 0, 'jueves': 0, 'viernes': 0}
                    }
                # Sumar horas solo de los días que estaban deshabilitados
                for dia in dias_deshabilitados:
                    valor_actual = proyectos_combinados[nombre]['horas'][dia]
                    valor_nuevo = proyecto['horas'].get(dia, 0)
                    # Solo actualizar si el valor actual es 0
                    if valor_actual == 0 and valor_nuevo > 0:
                        proyectos_combinados[nombre]['horas'][dia] = valor_nuevo
            
            print(f"[DEBUG] ✅ Datos combinados de ambas consultas")
        
        # Convertir diccionario a lista
        proyectos = list(proyectos_combinados.values())
        
        if not proyectos:
            fecha_inicio = lunes.strftime('%d/%m/%Y')
            fecha_fin = viernes.strftime('%d/%m/%Y')
            return f"📅 Semana del {fecha_inicio} al {fecha_fin}\n\n⚪ No hay horas imputadas en esta semana"
        
        # Formatear la información
        fecha_inicio = lunes.strftime('%d/%m/%Y')
        fecha_fin = viernes.strftime('%d/%m/%Y')
        
        resumen = f"📅 Semana del {fecha_inicio} al {fecha_fin}\n\n"
        
        # 🆕 CALCULAR TOTALES POR DÍA PRIMERO (para usar en validaciones)
        totales_por_dia = {
            'lunes': 0,
            'martes': 0,
            'miércoles': 0,
            'jueves': 0,
            'viernes': 0
        }
        
        # Primera pasada: calcular totales por día
        for proyecto in proyectos:
            horas = proyecto['horas']
            for dia in totales_por_dia.keys():
                totales_por_dia[dia] += horas.get(dia, 0)
        
        # Calcular total real de la semana sumando los días
        total_semana = sum(totales_por_dia.values())
        
        # 🌐 Generar encabezado según canal
        if canal == "webapp":
            resumen = f"<h3 style='margin: 0 0 5px 0;'>📅 Semana del {fecha_inicio} al {fecha_fin}</h3>\n"
            resumen += "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%;'>\n"
            resumen += "<thead><tr style='background-color: #f0f0f0;'><th>Proyecto</th><th>Total</th><th>L</th><th>M</th><th>X</th><th>J</th><th>V</th></tr></thead>\n"
            resumen += "<tbody>\n"
        else:
            resumen = f"📅 Semana del {fecha_inicio} al {fecha_fin}\n\n"
            
        for proyecto in proyectos:
            nombre_corto = proyecto['proyecto'].split(' - ')[-1]  # Solo la última parte
            horas = proyecto['horas']
            
            # 🆕 Calcular el total del proyecto sumando solo L-V (no confiar en proyecto['total'])
            total_proyecto = (
                horas.get('lunes', 0) + 
                horas.get('martes', 0) + 
                horas.get('miércoles', 0) + 
                horas.get('jueves', 0) + 
                horas.get('viernes', 0)
            )
            
            # 🆕 SOLO PROCESAR PROYECTOS CON HORAS > 0 EN LA SEMANA
            if total_proyecto == 0:
                continue
            
            # 🌐 Mostrar proyecto según canal
            if canal == "webapp":
                # Tabla HTML - NO colorear celdas individuales de proyectos
                resumen += f"<tr><td>{nombre_corto}</td><td style='text-align: center; font-weight: bold;'>{total_proyecto}h</td>"
                
                # Mostrar valores SIN color en las celdas de proyectos individuales
                for dia_key in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                    valor = horas.get(dia_key, 0)
                    
                    if valor == 0:
                        texto = '-'
                    else:
                        texto = str(valor)
                    
                    resumen += f"<td style='text-align: center;'>{texto}</td>"
                
                resumen += "</tr>\n"
            else:
                # Formato texto para Slack - SOLO DÍAS CON HORAS > 0
                dias_con_horas = []
                if horas['lunes'] > 0:
                    dias_con_horas.append(f"L:{horas['lunes']}")
                if horas['martes'] > 0:
                    dias_con_horas.append(f"M:{horas['martes']}")
                if horas['miércoles'] > 0:
                    dias_con_horas.append(f"X:{horas['miércoles']}")
                if horas['jueves'] > 0:
                    dias_con_horas.append(f"J:{horas['jueves']}")
                if horas['viernes'] > 0:
                    dias_con_horas.append(f"V:{horas['viernes']}")
                
                if dias_con_horas:
                    dias_str = ", ".join(dias_con_horas)
                    resumen += f"🔹 {nombre_corto}: {total_proyecto}h ({dias_str})\n"
        
        if total_semana == 0:
            return f"📅 Semana del {fecha_inicio} al {fecha_fin}\n\n⚪ No hay horas imputadas en esta semana"
        
        # 🌐 Cerrar tabla y mostrar total según canal
        if canal == "webapp":
            # Fila de totales por día con colores
            resumen += f"<tr style='font-weight: bold;'><td>Total</td><td style='text-align: center; background-color: #e8f4f8;'>{total_semana}h</td>"
            
            # Colorear cada celda de total según validación
            for dia_key in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                total_dia = totales_por_dia[dia_key]
                limite = 6.5 if dia_key == 'viernes' else 8.5
                
                if total_dia == 0:
                    color = '#f0f0f0'  # Gris - Sin imputar
                elif total_dia > limite:
                    color = '#ffcccc'  # Rojo claro - Exceso
                elif total_dia < limite:
                    color = '#fff8dc'  # Amarillo claro - Faltan horas
                else:
                    color = '#d4edda'  # Verde claro - Correcto
                
                resumen += f"<td style='text-align: center; background-color: {color};'>{total_dia}h</td>"
            
            resumen += "</tr>\n"
            resumen += "</tbody></table>\n"
            
            # Leyenda de colores pequeña
            resumen += "<p style='margin-top: 8px; font-size: 0.8em; color: #888;'>\n"
            resumen += "<span style='background-color: #d4edda; padding: 2px 6px; margin-right: 8px;'>✓ Correcto</span> "
            resumen += "<span style='background-color: #fff8dc; padding: 2px 6px; margin-right: 8px;'>⚠ Faltan horas</span> "
            resumen += "<span style='background-color: #ffcccc; padding: 2px 6px; margin-right: 8px;'>⚠ Exceso</span> "
            resumen += "<span style='background-color: #f0f0f0; padding: 2px 6px;'>- Sin imputar</span>\n"
            resumen += "</p>\n"
        else:
            resumen += f"\n📊 Total: {total_semana} horas"
        
        # ⚠️ VALIDACIONES DE HORAS POR DÍA (usando totales_por_dia ya calculados)
        dias_exceso = []
        dias_faltantes = []
        dias_sin_imputar = []
        
        dias_nombres_completos = {
            'lunes': 'Lunes',
            'martes': 'Martes', 
            'miércoles': 'Miércoles',
            'jueves': 'Jueves',
            'viernes': 'Viernes'
        }
        
        # 🆕 Detectar qué días tienen Festivo o Vacaciones (no se validan)
        dias_con_festivo_o_vacaciones = set()
        for proyecto in proyectos:
            nombre_lower = proyecto['proyecto'].lower()
            if 'festivo' in nombre_lower or 'vacaciones' in nombre_lower:
                # Marcar los días que tienen horas en este proyecto
                for dia in ['lunes', 'martes', 'miércoles', 'jueves', 'viernes']:
                    if proyecto['horas'].get(dia, 0) > 0:
                        dias_con_festivo_o_vacaciones.add(dia)
        
        if dias_con_festivo_o_vacaciones:
            print(f"[DEBUG] 🏖️ Días con Festivo/Vacaciones (sin validar): {dias_con_festivo_o_vacaciones}")
        
        # Verificar cada día (totales_por_dia ya está calculado arriba)
        for dia, total in totales_por_dia.items():
            # 🆕 SKIP: No validar días con Festivo o Vacaciones
            if dia in dias_con_festivo_o_vacaciones:
                continue
            
            # Determinar límite según el día (viernes = 6.5h, resto = 8.5h)
            limite_horas = 6.5 if dia == 'viernes' else 8.5
            
            if total > limite_horas:
                # Día con exceso de horas
                horas_exceso = round(total - limite_horas, 2)
                dias_exceso.append(f"{dias_nombres_completos[dia]}: {horas_exceso}h de más (total: {total}h)")
            elif total == 0:
                # Día sin imputar
                dias_sin_imputar.append(f"{dias_nombres_completos[dia]}: 0h imputadas")
            elif 0 < total < limite_horas:
                # Día con horas faltantes
                horas_faltantes = round(limite_horas - total, 2)
                dias_faltantes.append(f"{dias_nombres_completos[dia]}: Faltan {horas_faltantes}h (tienes {total}h)")
        
        # Mostrar avisos si existen (solo para webapp, pequeñas notas)
        if canal == "webapp":
            notas = []
            
            if dias_exceso:
                for dia_info in dias_exceso:
                    notas.append(f"* {dia_info}")
            
            if dias_faltantes:
                for dia_info in dias_faltantes:
                    notas.append(f"* {dia_info}")
            
            if dias_sin_imputar:
                for dia_info in dias_sin_imputar:
                    notas.append(f"* {dia_info}")
            
            if notas:
                resumen += "<p style='margin-top: 10px; font-size: 0.85em; color: #666; line-height: 1.4;'>\n"
                resumen += "<br>".join(notas)
                resumen += "</p>\n"
        else:
            # Formato texto para Slack
            if dias_exceso:
                resumen += "\n\n⚠️ EXCESO DE HORAS:\n"
                for dia_info in dias_exceso:
                    resumen += f"  • {dia_info}\n"
            
            if dias_faltantes:
                resumen += "\n⚠️ FALTAN HORAS:\n"
                for dia_info in dias_faltantes:
                    resumen += f"  • {dia_info}\n"
            
            if dias_sin_imputar:
                resumen += "\n⚠️ DÍAS SIN IMPUTAR:\n"
                for dia_info in dias_sin_imputar:
                    resumen += f"  • {dia_info}\n"
        
        print(f"[DEBUG] ✅ consultar_semana - Resumen generado ({len(resumen)} caracteres)")
        print(f"[DEBUG] Total semana calculado: {total_semana}h")
        if dias_deshabilitados:
            print(f"[DEBUG] ℹ️ Días deshabilitados detectados: {dias_deshabilitados} - se hicieron 2 consultas")
        return resumen
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"No he podido consultar la semana: {e}"


def mostrar_comandos():
    """
    Muestra la lista de comandos disponibles y cómo usarlos.
    
    Returns:
        str: Lista formateada de comandos con ejemplos
    """
    
    comandos = """
📋 **COMANDOS DISPONIBLES**

DEBES PONER EL TÍTULO DEL PROYECTO TAL Y COMO ESTÁ ESCRITO EN GESTIONITT,
CON SUS TILDES. NO HACE FALTA PONER EL NOMBRE ENTERO.
Ejemplo: Si tu proyecto se llama Estudio/Investigación de tecnología o proyecto cliente,
puedes decirle: "Ponme 3 horas en Estudio hoy"

🔹 **IMPUTAR HORAS**
Puedes imputar horas de varias formas:

  • "Imputa 8 horas a [proyecto] hoy"
  • "Pon 4 horas en [proyecto] el lunes"
  • "Añade 2.5h a [proyecto] mañana"
  • "Registra 6 horas en [proyecto] ayer"
  • "Imputa 8h a [proyecto] el 25/12/2024"

🔹 **CONSULTAR HORAS**
Revisa tus horas imputadas:

  • "¿Qué horas tengo hoy?"
  • "Resumen de hoy"
  • "Muéstrame las horas del martes"
  • "¿Cuántas horas tengo el 15/12?"
  • "Dame un resumen de esta semana"
  • "¿Qué horas tengo la semana del 2 de diciembre?"

🔹 **MODIFICAR/ELIMINAR**
Cambia horas ya imputadas:

  • "Cambia las horas de [proyecto] de hoy a 6"
  • "Modifica [proyecto] del lunes a 4 horas"
  • "Elimina las horas de [proyecto] de hoy"
  • "Borra [proyecto] del martes"

🔹 **AYUDA**
  • "Ayuda" o "Comandos" - Muestra este mensaje
  • "¿Qué puedes hacer?"

💡 **TIPS:**
  - Puedes usar días: hoy, ayer, mañana, lunes, martes, etc.
  - Puedes usar fechas: 25/12/2024 o 25 de diciembre
  - Las horas pueden ser decimales: 2.5, 4.25, etc.
  - No hace falta ser muy específico, ¡entiendo lenguaje natural!

⚠️ **VALIDACIONES AUTOMÁTICAS:**
  - Te aviso si te pasas de horas en un día (8.5h L-J, 6.5h V)
  - Te aviso si te faltan horas por imputar
  - Te aviso si hay días sin imputar en la semana

¿En qué puedo ayudarte?
    """
    
    return comandos.strip()
