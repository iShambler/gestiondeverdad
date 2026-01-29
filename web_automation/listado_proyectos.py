"""
Funciones para listar y explorar proyectos disponibles.
VERSIÓN CON JERARQUÍA COMPLETA DE CARPETAS - v2.0
"""

print("[IMPORT] 🔄 Cargando listado_proyectos.py v2.0 con jerarquía completa")

import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import Selectors


def listar_todos_proyectos(driver, wait, filtro_nodo=None):
    """
    Lista TODOS los proyectos disponibles en el árbol con jerarquía completa de carpetas.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        filtro_nodo: (Opcional) Nombre del nodo/carpeta para filtrar.
        
    Returns:
        dict: Estructura de proyectos con rutas completas:
              {
                  "Arelance > Admin-Staff": ["Proyecto1", "Proyecto2"],
                  "Departamento > Subdepartamento": ["Proyecto3"],
                  ...
              }
    """
    try:
        print("[DEBUG]  Listando todos los proyectos disponibles con jerarquía...")
        
        # 🗓️ PASO 1: Asegurarnos de estar en la página principal y seleccionar fecha de HOY
        from web_automation.navigation import seleccionar_fecha
        from web_automation.interactions import volver_inicio
        
        try:
            volver_inicio(driver)
            time.sleep(1)
        except Exception as e:
            print(f"[DEBUG]  Error volviendo a inicio: {e}")
        
        fecha_hoy = datetime.now()
        print(f"[DEBUG] 📅 Seleccionando fecha: {fecha_hoy.strftime('%d/%m/%Y')}")
        
        try:
            mensaje = seleccionar_fecha(driver, fecha_hoy)
            print(f"[DEBUG]  {mensaje}")
            time.sleep(1)
        except Exception as e:
            print(f"[DEBUG]  Error seleccionando fecha: {e}")
        
        # 🆕 PASO 2: Crear nueva línea para abrir el buscador
        try:
            btn_nueva_linea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BTN_NUEVA_LINEA)))
            btn_nueva_linea.click()
            print("[DEBUG]  Click en 'Nueva línea'")
            time.sleep(1)
            
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
            if not selects:
                print("[DEBUG]  No se encontró el select de subproyecto")
                return {}
            
            nuevo_select = selects[-1]
            fila = nuevo_select.find_element(By.XPATH, "./ancestor::tr")
            
            #  PASO 3: Abrir el buscador de proyectos
            btn_cambiar = fila.find_element(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cambiar)
            btn_cambiar.click()
            print("[DEBUG]  Abriendo buscador de proyectos...")
            time.sleep(1.5)
            
        except Exception as e:
            print(f"[DEBUG]  Error abriendo buscador: {e}")
            import traceback
            traceback.print_exc()
            return {}
        
        # 🌳 PASO 4: Expandir todo el árbol
        driver.execute_script("""
            var tree = $('#treeTipologia');
            if (tree && tree.jstree) { 
                tree.jstree('open_all'); 
            }
        """)
        print("[DEBUG] 🌳 Expandiendo árbol completo...")
        time.sleep(2)
        
        # 📊 PASO 5: Buscar todos los nodos con JERARQUÍA COMPLETA
        proyectos_por_nodo = {}
        
        nodos_padre = driver.find_elements(By.XPATH, "//li[contains(@class, 'jstree')]//li[@rel='subproyectos']/parent::ul/parent::li")
        
        print(f"[DEBUG] 📊 Encontrados {len(nodos_padre)} nodos padre")
        
        if len(nodos_padre) == 0:
            print(f"[DEBUG]  No se encontraron nodos padre en el árbol")
            print(f"[DEBUG]  HTML del árbol: {driver.find_element(By.ID, 'treeTipologia').get_attribute('outerHTML')[:500]}")
        
        for idx, nodo in enumerate(nodos_padre):
            print(f"[DEBUG] 🔄 INICIO bucle - Procesando nodo {idx+1}/{len(nodos_padre)}")
            try:
                print(f"[DEBUG] 🔄 DENTRO try - Procesando nodo {idx+1}/{len(nodos_padre)}")
                
                link_nodo = nodo.find_element(By.XPATH, "./a")
                nombre_nodo = link_nodo.text.strip()
                
                print(f"[DEBUG]   📝 Nombre nodo: '{nombre_nodo}'")
                
                if not nombre_nodo:
                    print(f"[DEBUG]    Nodo vacío, saltando...")
                    continue
                
                # 🌲 OBTENER JERARQUÍA COMPLETA
                ruta_completa = [nombre_nodo]
                nodo_actual = nodo
                
                print(f"[DEBUG]   🌲 Obteniendo jerarquía para '{nombre_nodo}'...")
                
                # Subir por los ancestros
                intentos = 0
                while True:
                    intentos += 1
                    if intentos > 10:
                        print(f"[DEBUG]    Demasiados intentos subiendo jerarquía, cortando")
                        break
                        
                    try:
                        nodo_padre_superior = nodo_actual.find_element(By.XPATH, "./parent::ul/parent::li")
                        link_padre = nodo_padre_superior.find_element(By.XPATH, "./a")
                        nombre_padre = link_padre.text.strip()
                        
                        print(f"[DEBUG]   📂 Padre encontrado: '{nombre_padre}'")
                        
                        if nombre_padre and nombre_padre not in ruta_completa:
                            ruta_completa.insert(0, nombre_padre)
                            nodo_actual = nodo_padre_superior
                        else:
                            print(f"[DEBUG]   🛑 Padre vacío o duplicado, cortando")
                            break
                    except Exception as ex:
                        print(f"[DEBUG]    No hay más padres (esto es normal): {ex}")
                        break
                
                # Crear clave: "Arelance > Admin-Staff"
                clave_nodo = " > ".join(ruta_completa)
                
                # Filtrar si es necesario
                if filtro_nodo:
                    import unicodedata
                    def normalizar(texto):
                        return ''.join(
                            c for c in unicodedata.normalize('NFD', texto.lower())
                            if unicodedata.category(c) != 'Mn'
                        )
                    
                    filtro_norm = normalizar(filtro_nodo)
                    ruta_norm = normalizar(clave_nodo)
                    
                    if filtro_norm not in ruta_norm:
                        continue
                
                # Encontrar proyectos
                proyectos = nodo.find_elements(By.XPATH, ".//li[@rel='subproyectos']//a")
                
                print(f"[DEBUG]    Encontrados {len(proyectos)} proyectos en este nodo")
                
                nombres_proyectos = []
                for proyecto in proyectos:
                    nombre_proyecto = proyecto.text.strip()
                    if nombre_proyecto and nombre_proyecto not in nombres_proyectos:
                        nombres_proyectos.append(nombre_proyecto)
                
                print(f"[DEBUG]    Proyectos válidos: {len(nombres_proyectos)}")
                
                if nombres_proyectos:
                    proyectos_por_nodo[clave_nodo] = sorted(nombres_proyectos)
                    print(f"[DEBUG]   📁 {clave_nodo}: {len(nombres_proyectos)} proyectos")
                else:
                    print(f"[DEBUG]    No se encontraron proyectos válidos en {clave_nodo}")
                
            except Exception as e:
                print(f"[DEBUG]  ERROR procesando nodo {idx+1}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 🧹 PASO 6: Cerrar el overlay
        try:
            print("[DEBUG] 🧹 Cerrando buscador...")
            driver.execute_script("""
                document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                document.getElementById('textoBusqueda').style.color='gray';
                var tree = $('#treeTipologia');
                tree.jstree('deselect_all');
                tree.jstree('close_all');
                hideOverlay();
            """)
            time.sleep(0.5)
        except Exception as e:
            print(f"[DEBUG]  Error cerrando overlay: {e}")
        
        # 🗑️ PASO 7: Eliminar línea temporal
        try:
            print("[DEBUG] 🗑️ Eliminando línea temporal...")
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
            if selects:
                ultimo_select = selects[-1]
                fila = ultimo_select.find_element(By.XPATH, "./ancestor::tr")
                
                selectores_eliminar = [
                    "button.botonEliminar",
                    "button[id*='btEliminar']",
                    "input[id*='btEliminar']",
                    "button[onclick*='eliminar']",
                    "input[onclick*='eliminar']"
                ]
                
                btn_eliminar = None
                for selector in selectores_eliminar:
                    try:
                        btn_eliminar = fila.find_element(By.CSS_SELECTOR, selector)
                        if btn_eliminar:
                            break
                    except:
                        continue
                
                if btn_eliminar:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_eliminar)
                    time.sleep(0.3)
                    btn_eliminar.click()
                    print("[DEBUG]  Línea temporal eliminada")
                    time.sleep(0.5)
        except Exception as e:
            print(f"[DEBUG]  Error eliminando línea: {e}")
        
        print(f"[DEBUG]  Listado completo: {len(proyectos_por_nodo)} nodos padre con proyectos")
        print(f"[DEBUG] 📊 Total proyectos encontrados: {sum(len(p) for p in proyectos_por_nodo.values())}")
        
        if len(proyectos_por_nodo) == 0:
            print(f"[DEBUG]  DICT VACÍO - No se agregaron proyectos al diccionario")
            print(f"[DEBUG]  Nodos procesados pero sin proyectos válidos")
        
        return proyectos_por_nodo
        
    except Exception as e:
        print(f"[DEBUG]  Error listando proyectos: {e}")
        import traceback
        traceback.print_exc()
        return {}


def formatear_lista_proyectos(proyectos_por_nodo, canal="webapp"):
    """Formatea la lista de proyectos con jerarquía completa."""
    if not proyectos_por_nodo:
        return " No he podido obtener la lista de proyectos"
    
    total_proyectos = sum(len(proyectos) for proyectos in proyectos_por_nodo.values())
    
    if canal == "slack":
        mensaje = f" *Proyectos Disponibles* ({total_proyectos} proyectos)\n\n"
        for ruta, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 *{ruta}*\n"
            for proyecto in proyectos:
                mensaje += f"   • {proyecto}\n"
            mensaje += "\n"
    
    elif canal == "whatsapp":
        mensaje = f" *Proyectos Disponibles*\n_{total_proyectos} proyectos_\n\n"
        for ruta, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 *{ruta}*\n"
            for proyecto in proyectos:
                mensaje += f"  • {proyecto}\n"
            mensaje += "\n"
    
    else:  # webapp
        mensaje = f" **Proyectos Disponibles** ({total_proyectos} proyectos)\n\n"
        for ruta, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 **{ruta}**\n"
            for proyecto in proyectos:
                mensaje += f"   • {proyecto}\n"
            mensaje += "\n"
    
    mensaje += " Puedes filtrar por carpeta:\n"
    mensaje += "   `Lista proyectos en Admin-Staff`"
    
    return mensaje
