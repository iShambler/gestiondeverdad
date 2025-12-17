"""
Funciones de navegación en la web.
Incluye cambio de fechas, navegación por calendarios, etc.
"""

import time
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import Selectors, Constants


def lunes_de_semana(fecha):
    """Calcula el lunes de la semana a la que pertenece una fecha.
    
    Args:
        fecha: objeto datetime
        
    Returns:
        datetime: El lunes de esa semana
    """
    return fecha - timedelta(days=fecha.weekday())


def seleccionar_fecha(driver, fecha_obj, contexto=None):
    """Abre el calendario, navega hasta el mes correcto y selecciona el día.
    
    Args:
        driver: WebDriver de Selenium
        fecha_obj: objeto datetime con la fecha a seleccionar
        contexto: (Opcional) Diccionario de contexto para limpiar si se vuelve atrás
        
    Returns:
        str: Mensaje de confirmación o error
    """
    from web_automation.interactions import guardar_linea
    
    print(f"[DEBUG] 📅 Seleccionando fecha: {fecha_obj.strftime('%d/%m/%Y')}")
    
    # Calcular lunes de la semana objetivo
    lunes_objetivo = lunes_de_semana(fecha_obj)
    print(f"[DEBUG] 📅 Lunes objetivo: {lunes_objetivo.strftime('%d/%m/%Y')}")
    
    # Obtener la semana actual del contexto
    fecha_actual_contexto = contexto.get("fecha_seleccionada") if contexto else None
    lunes_actual = lunes_de_semana(fecha_actual_contexto) if fecha_actual_contexto else None
    
    print(f"[DEBUG] 📅 Fecha actual contexto: {fecha_actual_contexto.strftime('%d/%m/%Y') if fecha_actual_contexto else 'None'}")
    print(f"[DEBUG] 📅 Lunes actual: {lunes_actual.strftime('%d/%m/%Y') if lunes_actual else 'None'}")
    
    # 🔥 Verificar si hay botón volver visible (estamos en pantalla de imputación)
    try:
        btn_volver = driver.find_element(By.CSS_SELECTOR, Selectors.VOLVER)
        if btn_volver.is_displayed():
            # Decidir si debemos volver
            debe_volver = False
            
            if lunes_actual is None:
                # Primera vez o no sabemos dónde estamos
                print(f"[DEBUG] 🔙 No hay fecha en contexto, volviendo para navegar...")
                debe_volver = True
            elif lunes_actual != lunes_objetivo:
                # Cambiamos de semana
                print(f"[DEBUG] 🔙 Cambiando de semana ({lunes_actual.strftime('%d/%m')} → {lunes_objetivo.strftime('%d/%m')})")
                
                # 🔥 GUARDAR ANTES de volver si hay cambios pendientes
                print(f"[DEBUG] 💾 Guardando cambios antes de cambiar de semana...")
                try:
                    resultado_guardar = guardar_linea(driver, WebDriverWait(driver, 15))
                    print(f"[DEBUG] 💾 {resultado_guardar}")
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error guardando antes de volver: {e}")
                
                debe_volver = True
            else:
                # Misma semana, NO volver
                print(f"[DEBUG] ✅ Misma semana ({lunes_objetivo.strftime('%d/%m')}), NO volver atrás")
                debe_volver = False
            
            if debe_volver:
                print(f"[DEBUG] 🔙 Volviendo atrás...")
                btn_volver.click()
                time.sleep(2)
                
                # Limpiar el contexto porque todos los elementos quedan obsoletos
                if contexto:
                    print("[DEBUG] 🧹 Limpiando contexto tras volver atrás...")
                    contexto["fila_actual"] = None
                    contexto["proyecto_actual"] = None
                    contexto["nodo_padre_actual"] = None
    except:
        # No hay botón volver, ya estamos en la pantalla principal
        print(f"[DEBUG] 📅 No hay botón volver visible, estamos en pantalla principal")
        pass
    
    wait = WebDriverWait(driver, 15)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.CALENDAR_BUTTON))).click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, Selectors.DATEPICKER_CALENDAR)))

    def obtener_mes_anio_actual():
        """Lee el mes y año actual del datepicker."""
        texto = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, Selectors.DATEPICKER_TITLE))).text.lower()
        partes = texto.split()
        mes_visible = Constants.MESES_ESPANOL[partes[0]]
        anio_visible = int(partes[1])
        return mes_visible, anio_visible

    mes_visible, anio_visible = obtener_mes_anio_actual()

    # Navegar hacia adelante si es necesario
    while (anio_visible, mes_visible) < (fecha_obj.year, fecha_obj.month):
        driver.find_element(By.CSS_SELECTOR, Selectors.DATEPICKER_NEXT).click()
        time.sleep(0.3)
        mes_visible, anio_visible = obtener_mes_anio_actual()

    # Navegar hacia atrás si es necesario
    while (anio_visible, mes_visible) > (fecha_obj.year, fecha_obj.month):
        driver.find_element(By.CSS_SELECTOR, Selectors.DATEPICKER_PREV).click()
        time.sleep(0.3)
        mes_visible, anio_visible = obtener_mes_anio_actual()

    dia_seleccionado = fecha_obj.day

    try:
        driver.find_element(By.XPATH, f"//a[text()='{dia_seleccionado}']").click()
        fecha_formateada = fecha_obj.strftime('%d/%m/%Y')
        time.sleep(2)  # Esperar a que cargue la pantalla de imputación
        return f"He seleccionado la fecha {fecha_formateada}"
    except Exception as e:
        return f"No he podido seleccionar el día {dia_seleccionado}: {e}"
