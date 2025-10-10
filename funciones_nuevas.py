# ===================================================================
# NUEVAS FUNCIONES PARA AÑADIR A main_script.py
# ===================================================================

def eliminar_linea_proyecto(driver, wait, nombre_proyecto):
    """
    Elimina una línea de proyecto completa.
    Busca el proyecto, encuentra su botón de eliminar y lo pulsa.
    """
    from selenium.webdriver.common.by import By
    import unicodedata
    import time

    def normalizar(texto):
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto.lower())
            if unicodedata.category(c) != 'Mn'
        )

    try:
        # Buscar el proyecto en la tabla
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        print(f"[DEBUG] 🗑️ Buscando proyecto '{nombre_proyecto}' para eliminar...")
        
        for idx, sel in enumerate(selects):
            # Leer el nombre del proyecto
            title = sel.get_attribute("title") or ""
            
            try:
                texto_selected = driver.execute_script("""
                    var select = arguments[0];
                    var selectedOption = select.options[select.selectedIndex];
                    return selectedOption ? selectedOption.text : '';
                """, sel)
            except:
                texto_selected = ""
            
            texto_completo = f"{title} {texto_selected}".lower()
            
            # Si encontramos el proyecto
            if normalizar(nombre_proyecto) in normalizar(texto_completo):
                # Buscar el botón de eliminar en la misma fila
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                
                try:
                    btn_eliminar = fila.find_element(By.CSS_SELECTOR, "button.botonEliminar, button#botonEliminar")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_eliminar)
                    time.sleep(0.3)
                    btn_eliminar.click()
                    time.sleep(1)
                    
                    print(f"[DEBUG] ✅ Línea del proyecto '{nombre_proyecto}' eliminada")
                    return f"He eliminado la línea del proyecto '{nombre_proyecto}'"
                    
                except Exception as e:
                    return f"Encontré el proyecto pero no pude eliminar la línea: {e}"
        
        return f"No encontré ninguna línea con el proyecto '{nombre_proyecto}'"
    
    except Exception as e:
        return f"Error al intentar eliminar la línea: {e}"


def imputar_horas_dia_mejorada(driver, wait, dia, horas, fila, nombre_proyecto=None, modo="sumar"):
    """
    Imputa una cantidad específica de horas en un día concreto (lunes a viernes)
    dentro de la fila (<tr>) del proyecto correspondiente.
    
    modo: "sumar" (por defecto) o "establecer"
    - "sumar": añade las horas a las existentes
    - "establecer": pone exactamente esa cantidad, reemplazando lo anterior
    """
    from selenium.webdriver.common.by import By
    
    mapa_dias = {
        "lunes": "h1",
        "martes": "h2",
        "miércoles": "h3",
        "miercoles": "h3",
        "jueves": "h4",
        "viernes": "h5"
    }

    dia_clave = mapa_dias.get(dia.lower())
    if not dia_clave:
        return f"No reconozco el día '{dia}'"

    try:
        campo = fila.find_element(By.CSS_SELECTOR, f"input[id$='.{dia_clave}']")
        if campo.is_enabled():
            valor_actual = campo.get_attribute("value") or "0"
            try:
                valor_actual = float(valor_actual.replace(",", "."))
            except ValueError:
                valor_actual = 0.0

            nuevas_horas = float(horas)
            
            if modo == "establecer":
                # Establecer directamente el valor
                total = nuevas_horas
                campo.clear()
                campo.send_keys(str(total))
                
                proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
                return f"He establecido {total}h el {dia} {proyecto_texto}"
            else:
                # Modo sumar (comportamiento original)
                total = round(valor_actual + nuevas_horas, 2)
                campo.clear()
                campo.send_keys(str(total))
                
                proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
                accion = "añadido" if nuevas_horas > 0 else "restado"
                
                if valor_actual > 0:
                    return f"He {accion} {abs(nuevas_horas)}h el {dia} {proyecto_texto} (total: {total}h)"
                else:
                    return f"He imputado {total}h el {dia} {proyecto_texto}"
        else:
            return f"El {dia} no está disponible para imputar (puede ser festivo)"

    except Exception as e:
        return f"No he podido imputar horas el {dia}: {e}"
