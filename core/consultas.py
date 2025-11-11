"""
Funciones de consulta de información sobre horas imputadas.
Incluye consultas de días y semanas específicas.
"""

import time
from datetime import timedelta


def consultar_dia(driver, wait, fecha_obj):
    """
    Consulta la información de un día específico.
    Navega a la fecha, lee la tabla y devuelve un resumen del día.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        fecha_obj: Objeto datetime con la fecha a consultar
        
    Returns:
        str: Resumen formateado con las horas del día
    """
    from web_automation import lunes_de_semana, seleccionar_fecha, leer_tabla_imputacion
    
    try:
        # Calcular el lunes de esa semana para navegar
        lunes = lunes_de_semana(fecha_obj)
        seleccionar_fecha(driver, lunes)
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
            
            if horas_dia > 0:
                proyectos_con_horas.append((nombre_corto, horas_dia))
                total_dia += horas_dia
        
        if not proyectos_con_horas:
            return f"📅 {dia_nombre_capitalize} {fecha_str}\n\n⚪ No hay horas imputadas este día"
        
        for nombre, horas in proyectos_con_horas:
            resumen += f"🔹 {nombre}: {horas}h\n"
        
        resumen += f"\n📊 Total: {total_dia} horas"
        
        return resumen
    
    except Exception as e:
        return f"No he podido consultar ese día: {e}"


def consultar_semana(driver, wait, fecha_obj):
    """
    Consulta la información de una semana específica.
    Navega a la fecha, lee la tabla y devuelve un resumen.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        fecha_obj: Objeto datetime con la fecha (cualquier día de la semana)
        
    Returns:
        str: Resumen formateado con las horas de la semana
    """
    from web_automation import lunes_de_semana, seleccionar_fecha, leer_tabla_imputacion
    
    try:
        # Seleccionar la fecha (lunes de la semana)
        lunes = lunes_de_semana(fecha_obj)
        seleccionar_fecha(driver, lunes)
        time.sleep(2)  # Esperar a que cargue la tabla
        
        # Leer la información de la tabla
        proyectos = leer_tabla_imputacion(driver)
        
        if not proyectos:
            return "No hay horas imputadas en esa semana"
        
        # Formatear la información
        fecha_inicio = lunes.strftime('%d/%m/%Y')
        fecha_fin = (lunes + timedelta(days=4)).strftime('%d/%m/%Y')
        
        resumen = f"📅 Semana del {fecha_inicio} al {fecha_fin}\n\n"
        
        total_semana = 0
        for proyecto in proyectos:
            nombre_corto = proyecto['proyecto'].split(' - ')[-1]  # Solo la última parte
            horas = proyecto['horas']
            total = proyecto['total']
            total_semana += total
            
            # Formato de horas por día
            dias_str = f"L:{horas['lunes']}, M:{horas['martes']}, X:{horas['miércoles']}, J:{horas['jueves']}, V:{horas['viernes']}"
            resumen += f"🔹 {nombre_corto}: {total}h ({dias_str})\n"
        
        resumen += f"\n📊 Total: {total_semana} horas"
        
        return resumen
    
    except Exception as e:
        return f"No he podido consultar la semana: {e}"
