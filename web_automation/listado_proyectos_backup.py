"""
Funciones para listar y explorar proyectos disponibles.
"""

import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from config import Selectors


def listar_todos_proyectos(driver, wait, filtro_nodo=None):
    """
    Lista TODOS los proyectos disponibles en el árbol con sus nodos padre.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        filtro_nodo: (Opcional) Nombre del nodo padre para filtrar. Si se proporciona,
                     solo devuelve los proyectos de ese nodo.
        
    Returns:
        dict: Estructura de proyectos organizados por nodo padre:
              {
                  "Departamento Desarrollo e IDI": ["Desarrollo", "Dirección", "Estudio"],
                  "Departamento Comercial": ["Desarrollo", "Ventas"],
                  ...
              }
    """
    try:
        print("[DEBUG] 📋 Listando todos los proyectos disponibles...")
        
        # 🗓️ PASO 1: Asegurarnos de estar en la página principal y seleccionar fecha de HOY
        from web_automation.navigation import seleccionar_fecha
        from web_automation.interactions import volver_inicio
        
        # Volver a la página principal por si acaso
        try:
            volver_inicio(driver)
            time.sleep(1)
        except Exception as e:
            print(f"[DEBUG] ⚠️ Error volviendo a inicio (tal vez ya estamos ahí): {e}")
        
        fecha_hoy = datetime.now()
        print(f"[DEBUG] 📅 Seleccionando fecha: {fecha_hoy.strftime('%d/%m/%Y')}")
        
        try:
            mensaje = seleccionar_fecha(driver, fecha_hoy)  # Solo 2 argumentos!
            print(f"[DEBUG] ✅ {mensaje}")
            time.sleep(1)
        except Exception as e:
            print(f"[DEBUG] ⚠️ Error seleccionando fecha: {e}")
            # Continuar de todas formas, tal vez ya está en la fecha correcta
        
        # 🆕 PASO 2: Crear nueva línea para abrir el buscador
        try:
            btn_nueva_linea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BTN_NUEVA_LINEA)))
            btn_nueva_linea.click()
            print("[DEBUG] ✅ Click en 'Nueva línea'")
            time.sleep(1)
            
            # Buscar el select de subproyecto
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
            if not selects:
                print("[DEBUG] ❌ No se encontró el select de subproyecto")
                return {}
            
            # Obtener el último select (la nueva línea)
            nuevo_select = selects[-1]
            fila = nuevo_select.find_element(By.XPATH, "./ancestor::tr")
            
            # 🔍 PASO 3: Abrir el buscador de proyectos (botón "»")
            btn_cambiar = fila.find_element(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cambiar)
            btn_cambiar.click()
            print("[DEBUG] 🔍 Abriendo buscador de proyectos...")
            time.sleep(1.5)
            
        except Exception as e:
            print(f"[DEBUG] ❌ Error abriendo buscador: {e}")
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
        
        # 📊 PASO 5: Buscar todos los nodos del árbol
        proyectos_por_nodo = {}
        
        # Encontrar todos los elementos <li> que son nodos padre (contienen subproyectos)
        nodos_padre = driver.find_elements(By.XPATH, "//li[contains(@class, 'jstree')]//li[@rel='subproyectos']/parent::ul/parent::li")
        
        print(f"[DEBUG] 📊 Encontrados {len(nodos_padre)} nodos padre")
        
        for nodo in nodos_padre:
            try:
                # Obtener el nombre del nodo padre
                link_nodo = nodo.find_element(By.XPATH, "./a")
                nombre_nodo = link_nodo.text.strip()
                
                if not nombre_nodo:
                    continue
                
                # 🆕 Si hay filtro, verificar si este nodo coincide
                if filtro_nodo:
                    # Normalizar para comparación flexible
                    import unicodedata
                    def normalizar(texto):
                        return ''.join(
                            c for c in unicodedata.normalize('NFD', texto.lower())
                            if unicodedata.category(c) != 'Mn'
                        )
                    
                    filtro_norm = normalizar(filtro_nodo)
                    nodo_norm = normalizar(nombre_nodo)
                    
                    # Si no coincide, saltar este nodo
                    if filtro_norm not in nodo_norm:
                        continue
                
                # Encontrar todos los proyectos bajo este nodo
                proyectos = nodo.find_elements(By.XPATH, ".//li[@rel='subproyectos']//a")
                
                nombres_proyectos = []
                for proyecto in proyectos:
                    nombre_proyecto = proyecto.text.strip()
                    if nombre_proyecto and nombre_proyecto not in nombres_proyectos:
                        nombres_proyectos.append(nombre_proyecto)
                
                if nombres_proyectos:
                    proyectos_por_nodo[nombre_nodo] = sorted(nombres_proyectos)
                    print(f"[DEBUG]   📁 {nombre_nodo}: {len(nombres_proyectos)} proyectos")
                
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error procesando nodo: {e}")
                continue
        
        # 🧹 PASO 6: Cerrar el overlay del buscador (SIN GUARDAR)
        try:
            print("[DEBUG] 🧹 Cerrando buscador...")
            driver.execute_script("""
                // Limpiar búsqueda
                document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                document.getElementById('textoBusqueda').style.color='gray';
                
                // Cerrar árbol
                var tree = $('#treeTipologia');
                tree.jstree('deselect_all');
                tree.jstree('close_all');
                
                // Cerrar overlay
                hideOverlay();
            """)
            time.sleep(0.5)
            
        except Exception as e:
            print(f"[DEBUG] ⚠️ Error cerrando overlay: {e}")
        
        # 🗑️ PASO 7: Eliminar la línea temporal que creamos (SIN GUARDAR)
        try:
            print("[DEBUG] 🗑️ Eliminando línea temporal...")
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
            if selects:
                ultimo_select = selects[-1]
                fila = ultimo_select.find_element(By.XPATH, "./ancestor::tr")
                
                # Buscar el botón de eliminar (puede tener varios selectores)
                try:
                    # Intenta varios selectores posibles para el botón eliminar
                    btn_eliminar = None
                    selectores_eliminar = [
                        "button.botonEliminar",
                        "button[id*='btEliminar']",
                        "input[id*='btEliminar']",
                        "button[onclick*='eliminar']",
                        "input[onclick*='eliminar']"
                    ]
                    
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
                        print("[DEBUG] ✅ Línea temporal eliminada")
                        time.sleep(0.5)
                    else:
                        print("[DEBUG] ⚠️ No se encontró botón de eliminar, la línea quedará sin guardar")
                        
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error eliminando línea: {e}")
                    # No es crítico, la línea quedará ahí sin guardar
        
        except Exception as e:
            print(f"[DEBUG] ⚠️ Error buscando línea a eliminar: {e}")
        
        print(f"[DEBUG] ✅ Listado completo: {len(proyectos_por_nodo)} nodos padre")
        return proyectos_por_nodo
        
    except Exception as e:
        print(f"[DEBUG] ❌ Error listando proyectos: {e}")
        import traceback
        traceback.print_exc()
        return {}


def formatear_lista_proyectos(proyectos_por_nodo, canal="webapp"):
    """
    Formatea la lista de proyectos para mostrar al usuario.
    
    Args:
        proyectos_por_nodo: Dict con proyectos organizados por nodo padre
        canal: Canal de comunicación (webapp, slack, whatsapp)
        
    Returns:
        str: Mensaje formateado con la lista de proyectos
    """
    if not proyectos_por_nodo:
        return "❌ No he podido obtener la lista de proyectos"
    
    total_proyectos = sum(len(proyectos) for proyectos in proyectos_por_nodo.values())
    
    if canal == "slack":
        mensaje = f"📋 *Proyectos Disponibles* ({total_proyectos} proyectos en {len(proyectos_por_nodo)} áreas)\n\n"
        
        for nodo, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 *{nodo}*\n"
            for proyecto in proyectos:
                mensaje += f"   • {proyecto}\n"
            mensaje += "\n"
    
    elif canal == "whatsapp":
        mensaje = f"📋 *Proyectos Disponibles*\n"
        mensaje += f"_{total_proyectos} proyectos en {len(proyectos_por_nodo)} áreas_\n\n"
        
        for nodo, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 *{nodo}*\n"
            for proyecto in proyectos:
                mensaje += f"  • {proyecto}\n"
            mensaje += "\n"
    
    else:  # webapp
        mensaje = f"📋 **Proyectos Disponibles** ({total_proyectos} proyectos en {len(proyectos_por_nodo)} áreas)\n\n"
        
        for nodo, proyectos in sorted(proyectos_por_nodo.items()):
            mensaje += f"📁 **{nodo}**\n"
            for proyecto in proyectos:
                mensaje += f"   • {proyecto}\n"
            mensaje += "\n"
    
    mensaje += "💡 Para imputar en un proyecto específico, usa:\n"
    mensaje += "   `Pon 3h en [Departamento] en [Proyecto]`"
    
    return mensaje
