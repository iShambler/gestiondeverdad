"""
Funciones para el manejo específico de proyectos:
- Selección de proyectos (búsqueda y asignación)
- Imputación de horas (día específico y semana completa)
- Eliminación de líneas de proyectos
- Borrado de horas
- Lectura de tabla de imputación
"""

import time
import unicodedata
from datetime import timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from config import Selectors, Constants


def normalizar(texto):
    """Normaliza acentos y minúsculas para comparaciones flexibles."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )


def seleccionar_proyecto(driver, wait, nombre_proyecto, nodo_padre=None, elemento_preseleccionado=None, contexto=None):
    """
    Selecciona el proyecto en la tabla de imputación.
    Si ya existe una línea con ese proyecto, la reutiliza.
    Si no existe, crea una nueva línea, abre el buscador,
    busca el proyecto y lo selecciona.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        nombre_proyecto: Nombre del proyecto a seleccionar
        nodo_padre: (Opcional) Nombre del nodo padre para desambiguar proyectos con mismo nombre
                    Ejemplo: "Departamento Desarrollo" cuando hay varios "Desarrollo"
        elemento_preseleccionado: (Opcional) WebElement ya seleccionado del árbol (para desambiguación)
        
    Returns:
        tuple: (fila: WebElement o None, mensaje: str, necesita_desambiguacion: bool, coincidencias: list)
            - fila: Elemento <tr> del proyecto si se encontró/creó
            - mensaje: Descripción de lo que se hizo
            - necesita_desambiguacion: True si hay múltiples coincidencias sin nodo padre
            - coincidencias: Lista de coincidencias (si necesita_desambiguacion=True)
    """
    try:
        # Dar tiempo a que la página se estabilice tras guardar
        time.sleep(0.5)
        
        # Buscar si el proyecto ya existe en TODAS las líneas (guardadas o no)
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        # Si no encuentra por name, intentar por id
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        print(f"[DEBUG] 🔍 Buscando proyecto '{nombre_proyecto}' en {len(selects)} líneas totales...")
        
        # 🆕 Recolectar TODAS las coincidencias
        coincidencias_encontradas = []
        
        for idx, sel in enumerate(selects):
            # Verificar si el select está disabled (guardado)
            is_disabled = sel.get_attribute("disabled")
            estado = "guardada" if is_disabled else "editable"
            
            # Obtener el texto de la opción seleccionada usando JavaScript
            try:
                texto_completo = driver.execute_script("""
                    var select = arguments[0];
                    var selectedOption = select.options[select.selectedIndex];
                    return selectedOption ? selectedOption.text : '';
                """, sel)
            except:
                texto_completo = ""
            
            if not texto_completo or texto_completo == "Seleccione opción":
                print(f"[DEBUG]   Línea {idx+1} ({estado}): Vacía o sin selección")
                continue
            
            # CRÍTICO: Extraer SOLO la última parte (el proyecto real)
            # Ejemplo: "Arelance - Departamento - Desarrollo" → "Desarrollo"
            partes = texto_completo.split(' - ')
            nombre_proyecto_real = partes[-1].strip() if partes else ""
            
            print(f"[DEBUG]   Línea {idx+1} ({estado}): '{texto_completo}' → Proyecto: '{nombre_proyecto_real}'")
            
            # BÚSQUEDA FLEXIBLE: Comparar si el nombre buscado está CONTENIDO en el nombre real
            # Esto permite que "Estudio" coincida con "Estudio/Investigación"
            nombre_buscado_norm = normalizar(nombre_proyecto)
            nombre_real_norm = normalizar(nombre_proyecto_real)
            
            # Coincidencia si:
            # 1. Son exactamente iguales, O
            # 2. El nombre buscado está contenido en el nombre real
            if nombre_buscado_norm == nombre_real_norm or nombre_buscado_norm in nombre_real_norm:
                # 🆕 ENCONTRADO - Añadir a la lista de coincidencias
                print(f"[DEBUG] ✅ Encontrado '{nombre_proyecto}' en línea {idx+1}")
                
                # Extraer nodo padre del proyecto en tabla
                nodo_padre_encontrado = partes[-2].strip() if len(partes) >= 2 else ""
                
                # Leer las horas de la fila para mostrarlas
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                horas_dias = {}
                total_horas = 0.0
                
                try:
                    for dia_nombre, dia_key in Constants.DIAS_KEYS.items():
                        try:
                            campo = fila.find_element(By.CSS_SELECTOR, Selectors.campo_horas_dia(dia_key))
                            valor = campo.get_attribute("value") or "0"
                            try:
                                valor_float = float(valor.replace(",", "."))
                            except ValueError:
                                valor_float = 0.0
                            horas_dias[dia_nombre] = valor_float
                            total_horas += valor_float
                        except:
                            horas_dias[dia_nombre] = 0.0
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error leyendo horas: {e}")
                
                coincidencias_encontradas.append({
                    "proyecto": nombre_proyecto_real,
                    "nodo_padre": nodo_padre_encontrado,
                    "texto_completo": texto_completo,
                    "path_completo": texto_completo,  # Alias
                    "total_horas": total_horas,
                    "horas_dias": horas_dias,
                    "fila_idx": idx
                })
        
        # 🆕 Si encontramos coincidencias Y no hay nodo_padre especificado
        if coincidencias_encontradas and not nodo_padre:
            print(f"[DEBUG] 📊 Encontradas {len(coincidencias_encontradas)} coincidencias en tabla")
            
            # 🔥 NUEVO: Si solo hay UNA coincidencia Y viene del contexto → USAR DIRECTAMENTE
            if len(coincidencias_encontradas) == 1:
                coincidencia = coincidencias_encontradas[0]
                proyecto_contexto = (contexto or {}).get("proyecto_actual", "").lower() if contexto else ""
                proyecto_encontrado = normalizar(coincidencia["proyecto"])
                
                # Si el proyecto del contexto coincide con el encontrado → usar sin preguntar
                if proyecto_contexto and normalizar(proyecto_contexto) in proyecto_encontrado:
                    print(f"[DEBUG] ✅ Proyecto del contexto '{proyecto_contexto}' coincide, usando directamente sin preguntar")
                    fila = selects[coincidencia["fila_idx"]].find_element(By.XPATH, "./ancestor::tr")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                    time.sleep(0.3)
                    return (fila, f"Usando '{coincidencia['proyecto']}' existente", False, [])
                
                # Si NO viene del contexto → preguntar para confirmar
                print(f"[DEBUG] 💬 Solicitando confirmación del proyecto existente")
                return (None, "", "confirmar_existente", coincidencias_encontradas)
            
            # Si hay MÚLTIPLES coincidencias, devolver tipo "desambiguacion"
            # El usuario debe elegir entre las que ya tiene
            else:
                print(f"[DEBUG] 💬 Múltiples proyectos encontrados, solicitando selección")
                return (None, "", "desambiguacion", coincidencias_encontradas)
        
        # 🆕 Si YA especificó nodo_padre (está confirmando)
        if coincidencias_encontradas and nodo_padre:
            # Buscar la coincidencia que match con el nodo_padre
            for coincidencia in coincidencias_encontradas:
                if normalizar(nodo_padre) in normalizar(coincidencia["nodo_padre"]):
                    # ✅ Coincide - usar este
                    print(f"[DEBUG] ✅ Nodo padre coincide, reutilizando línea existente")
                    fila = selects[coincidencia["fila_idx"]].find_element(By.XPATH, "./ancestor::tr")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                    time.sleep(0.3)
                    return (fila, f"Usando '{coincidencia['proyecto']}' de '{coincidencia['nodo_padre']}'", False, [])

        # Si no existe → añadimos nueva línea
        print(f"[DEBUG] ➕ Proyecto '{nombre_proyecto}' NO encontrado, añadiendo nueva línea...")
        try:
            btn_nueva_linea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BTN_NUEVA_LINEA)))
            btn_nueva_linea.click()
            print(f"[DEBUG] ✅ Botón nueva línea pulsado")
            time.sleep(1)
        except Exception as e:
            print(f"[DEBUG] ❌ Error al pulsar botón nueva línea: {e}")
            return (None, f"No he podido crear una nueva línea: {e}", False, [])

        # Detectar el nuevo <select> (último en la lista)
        try:
            selects_actualizados = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
            print(f"[DEBUG] 📋 Selects encontrados después de añadir: {len(selects_actualizados)}")
            
            if not selects_actualizados:
                return (None, "No se pudo detectar el nuevo select después de añadir línea", False, [])
                
            nuevo_select = selects_actualizados[-1]
            fila = nuevo_select.find_element(By.XPATH, "./ancestor::tr")
            print(f"[DEBUG] ✅ Nuevo select detectado")
        except Exception as e:
            print(f"[DEBUG] ❌ Error detectando nuevo select: {e}")
            return (None, f"No he podido detectar la nueva línea: {e}", False, [])

        # Buscar el botón "»" correspondiente dentro de la misma fila
        try:
            btn_cambiar = fila.find_element(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
        except Exception:
            botones = driver.find_elements(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
            btn_cambiar = botones[-1] if botones else None

        if btn_cambiar:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cambiar)
            btn_cambiar.click()
        else:
            return (None, f"No he encontrado el botón para buscar el proyecto '{nombre_proyecto}'", False, [])

        # Esperar a que aparezca el campo de búsqueda
        campo_buscar = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, Selectors.BUSCADOR_INPUT)))
        campo_buscar.clear()
        campo_buscar.send_keys(nombre_proyecto)
        print(f"[DEBUG] 🔍 Escrito '{nombre_proyecto}' en el campo de búsqueda")

        # Pulsar en el botón "Buscar"
        btn_buscar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BUSCADOR_BOTON)))
        btn_buscar.click()
        print(f"[DEBUG] 🔘 Botón 'Buscar' pulsado, esperando resultados...")
        time.sleep(1.5)

        # Expandir árbol de resultados
        print(f"[DEBUG] 🌳 Expandiendo árbol de resultados...")
        driver.execute_script("""
            var tree = $('#treeTipologia');
            if (tree && tree.jstree) { tree.jstree('open_all'); }
        """)
        time.sleep(1)
        print(f"[DEBUG] ✅ Árbol expandido")

        # Buscar y seleccionar el proyecto
        # IMPORTANTE: NO normalizar (quitar tildes) porque el sistema es sensible a tildes
        
        if nodo_padre and nodo_padre != "__buscar__":
            # 🎯 Búsqueda con jerarquía: buscar el proyecto bajo su nodo padre específico
            print(f"[DEBUG] 🔍 Buscando '{nombre_proyecto}' bajo nodo padre '{nodo_padre}'...")
            
            try:
                # 🆕 BUSCAR TODOS los nodos y comparar normalizados en Python (más confiable que XPath)
                todos_nodos = driver.find_elements(By.XPATH, "//li//a")
                nodo_padre_norm = normalizar(nodo_padre)
                nodo_padre_elemento = None
                
                print(f"[DEBUG] 🔍 Buscando entre {len(todos_nodos)} nodos...")
                
                for nodo in todos_nodos:
                    try:
                        texto_nodo = nodo.text.strip()
                        if texto_nodo and nodo_padre_norm in normalizar(texto_nodo):
                            nodo_padre_elemento = nodo
                            print(f"[DEBUG] ✅ Nodo padre encontrado: '{texto_nodo}'")
                            break
                    except:
                        continue
                
                if not nodo_padre_elemento:
                    raise Exception(f"No se encontró el nodo padre '{nodo_padre}'")
                
                # Obtener el ID del nodo padre para limitar la búsqueda
                nodo_padre_li = nodo_padre_elemento.find_element(By.XPATH, "./ancestor::li[1]")
                nodo_padre_id = nodo_padre_li.get_attribute("id")
                print(f"[DEBUG] 🆔 Nodo padre ID: {nodo_padre_id}")
                
                # Ahora buscar el proyecto SOLO dentro de ese nodo padre
                xpath_proyecto = (
                    f"//li[@id='{nodo_padre_id}']//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
                    f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                    f"'{nombre_proyecto.lower()}')]"
                )
                
                # 🆕 Buscar TODOS los elementos que coinciden
                elementos_en_nodo = driver.find_elements(By.XPATH, xpath_proyecto)
                print(f"[DEBUG] 📊 Encontrados {len(elementos_en_nodo)} proyectos en '{nodo_padre}'")
                
                # 🆕 Si hay MÚLTIPLES en el mismo nodo padre → DESAMBIGUAR
                if len(elementos_en_nodo) > 1 and not elemento_preseleccionado:
                    print(f"[DEBUG] 🤔 Múltiples '{nombre_proyecto}' en '{nodo_padre}', necesita desambiguación")
                    
                    from web_automation.desambiguacion import buscar_proyectos_duplicados
                    coincidencias = buscar_proyectos_duplicados(driver, wait, nombre_proyecto)
                    
                    # Filtrar solo las del nodo_padre especificado
                    coincidencias_filtradas = [
                        c for c in coincidencias 
                        if nodo_padre_norm in normalizar(c.get("nodo_padre", ""))
                    ]
                    
                    print(f"[DEBUG] 📋 {len(coincidencias_filtradas)} coincidencias en '{nodo_padre}'")
                    
                    # Cerrar buscador
                    try:
                        driver.execute_script("""
                            document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                            document.getElementById('textoBusqueda').style.color='gray';
                            buscadorJTree();
                            var tree = $('#treeTipologia');
                            tree.jstree('deselect_all');
                            tree.jstree('close_all');
                            hideOverlay();
                        """)
                        time.sleep(0.5)
                    except:
                        pass
                    
                    # Eliminar línea temporal
                    try:
                        btn_eliminar = fila.find_element(By.CSS_SELECTOR, "button.botonEliminar, button#botonEliminar, input[id*='btEliminar']")
                        btn_eliminar.click()
                        time.sleep(0.3)
                    except:
                        pass
                    
                    return (None, "", True, coincidencias_filtradas if coincidencias_filtradas else coincidencias)
                
                # Si solo hay UNO o hay elemento_preseleccionado → usarlo
                elemento = elemento_preseleccionado if elemento_preseleccionado else elementos_en_nodo[0]
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
                elemento.click()
                time.sleep(1)
                
                return (fila, f"He abierto el proyecto '{nombre_proyecto}' de '{nodo_padre}'", False, [])
                
            except Exception as e:
                print(f"[DEBUG] ❌ Error buscando con nodo padre: {e}")
                # Si falla la búsqueda con nodo padre, intentar búsqueda simple
                print(f"[DEBUG] 🔄 Intentando búsqueda simple sin nodo padre...")
        
        # Búsqueda estándar (sin nodo padre o si falló la búsqueda jerárquica)
        xpath = (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            f"'{nombre_proyecto.lower()}')]"
        )
        
        print(f"[DEBUG] 🔎 XPath de búsqueda: {xpath}")

        try:
            # Si hay múltiples coincidencias, verificar si necesitamos desambiguación
            elementos = driver.find_elements(By.XPATH, xpath)
            print(f"[DEBUG] 📊 Elementos encontrados: {len(elementos)}")
            if not elementos:
                # 🆕 Buscar en NODOS PADRE (departamentos/áreas)
                print(f"[DEBUG] 🔍 No se encontraron proyectos, buscando nodos padre...")
                
                # 🆕 BUSCAR TODOS LOS ENLACES Y FILTRAR EN PYTHON (más confiable)
                todos_los_nodos = driver.find_elements(By.XPATH, "//li//a")
                nombre_normalizado = normalizar(nombre_proyecto)
                
                print(f"[DEBUG] 🔍 Buscando '{nombre_proyecto}' entre {len(todos_los_nodos)} nodos...")
                
                nodos_padre = []
                
                for nodo in todos_los_nodos:
                    try:
                        texto_nodo = nodo.text.strip()
                        if not texto_nodo:
                            continue
                        
                        # Comparar normalizando tildes
                        if nombre_normalizado in normalizar(texto_nodo):
                            # Verificar que NO sea un subproyecto
                            li_padre = nodo.find_element(By.XPATH, "./ancestor::li[1]")
                            rel_attr = li_padre.get_attribute("rel")
                            
                            # Si NO es subproyecto, es un nodo padre
                            if rel_attr != "subproyectos":
                                nodos_padre.append(nodo)
                                print(f"[DEBUG] 📁 Nodo padre encontrado: '{texto_nodo}' (rel={rel_attr})")
                    except:
                        continue
                
                if nodos_padre:
                    print(f"[DEBUG] 📁 Encontrados {len(nodos_padre)} nodos padre")
                    
                    # Obtener proyectos dentro de los nodos
                    proyectos_en_nodos = []
                    
                    for nodo in nodos_padre:
                        nodo_nombre = nodo.text.strip()
                        print(f"[DEBUG] 📂 Explorando nodo: {nodo_nombre}")
                        
                        try:
                            li_nodo = nodo.find_element(By.XPATH, "./ancestor::li[1]")
                            nodo_id = li_nodo.get_attribute("id")
                            
                            xpath_hijos = f"//li[@id='{nodo_id}']//li[@rel='subproyectos']//a"
                            proyectos_hijos = driver.find_elements(By.XPATH, xpath_hijos)
                            
                            for proyecto in proyectos_hijos:
                                proyectos_en_nodos.append({
                                    "proyecto": proyecto.text.strip(),
                                    "nodo_padre": nodo_nombre,
                                    "elemento": proyecto,
                                    "path_completo": f"{nodo_nombre} → {proyecto.text.strip()}"
                                })
                        except Exception as e:
                            print(f"[DEBUG] ⚠️ Error explorando nodo {nodo_nombre}: {e}")
                            continue
                    
                    print(f"[DEBUG] 📊 Total proyectos en nodos: {len(proyectos_en_nodos)}")
                    
                    if len(proyectos_en_nodos) == 0:
                        raise Exception(f"No encontré proyectos dentro de '{nombre_proyecto}'")
                    
                    elif len(proyectos_en_nodos) == 1:
                        # ✅ SOLO 1 PROYECTO: Seleccionarlo automáticamente
                        proyecto_unico = proyectos_en_nodos[0]
                        print(f"[DEBUG] ✅ Solo 1 proyecto en '{nombre_proyecto}', seleccionando: {proyecto_unico['proyecto']}")
                        
                        elemento = proyecto_unico["elemento"]
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
                        elemento.click()
                        time.sleep(1)
                        
                        return (fila, f"He seleccionado '{proyecto_unico['proyecto']}' de '{proyecto_unico['nodo_padre']}'", False, [])
                    
                    else:
                        # 🔀 MÚLTIPLES PROYECTOS: Desambiguar
                        print(f"[DEBUG] 🤔 Múltiples proyectos en '{nombre_proyecto}', requiere desambiguación")
                        
                        # Cerrar buscador
                        try:
                            driver.execute_script("""
                                document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                                document.getElementById('textoBusqueda').style.color='gray';
                                buscadorJTree();
                                var tree = $('#treeTipologia');
                                tree.jstree('deselect_all');
                                tree.jstree('close_all');
                                hideOverlay();
                            """)
                            time.sleep(0.5)
                        except:
                            pass
                        
                        # Eliminar línea temporal
                        try:
                            btn_eliminar = fila.find_element(By.CSS_SELECTOR, "button.botonEliminar, button#botonEliminar, input[id*='btEliminar']")
                            btn_eliminar.click()
                            time.sleep(0.3)
                        except:
                            pass
                        
                        return (None, "", True, proyectos_en_nodos)
                
                else:
                    # No encontró ni proyectos ni nodos padre
                    raise Exception(f"No se encontró ninguna coincidencia para '{nombre_proyecto}'")
            
            # 🆕 DESAMBIGUACIÓN INTERACTIVA: Si hay múltiples coincidencias SIN nodo padre
            # O si el nodo_padre es "__buscar__" (usuario rechazó proyecto existente)
            if len(elementos) > 1 and (not nodo_padre or nodo_padre == "__buscar__") and not elemento_preseleccionado:
                print(f"[DEBUG] 🤔 Encontradas {len(elementos)} coincidencias para '{nombre_proyecto}'")
                print(f"[DEBUG] 💬 Necesita desambiguación - devolviendo coincidencias...")
                
                # Importar la función para obtener información detallada de coincidencias
                from web_automation.desambiguacion import buscar_proyectos_duplicados
                
                coincidencias = buscar_proyectos_duplicados(driver, wait, nombre_proyecto)
                
                # Cerrar el buscador antes de preguntar
                try:
                    driver.execute_script("""
                        document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                        document.getElementById('textoBusqueda').style.color='gray';
                        buscadorJTree();
                        var tree = $('#treeTipologia');
                        tree.jstree('deselect_all');
                        tree.jstree('close_all');
                        hideOverlay();
                    """)
                    time.sleep(0.5)
                except:
                    pass
                
                # Eliminar la línea temporal
                try:
                    btn_eliminar = fila.find_element(By.CSS_SELECTOR, "button.botonEliminar, button#botonEliminar, input[id*='btEliminar']")
                    btn_eliminar.click()
                    time.sleep(0.3)
                except:
                    pass
                
                # Devolver flag de desambiguación
                return (None, "", True, coincidencias)
            
            # 🎯 Si hay elemento preseleccionado (usuario ya eligió), usarlo
            if elemento_preseleccionado:
                print(f"[DEBUG] ✅ Usando elemento preseleccionado por el usuario")
                elemento = elemento_preseleccionado
            else:
                # Tomar la primera coincidencia
                elemento = elementos[0]
                if len(elementos) > 1:
                    print(f"[DEBUG] ⚠️ Usando primera coincidencia de {len(elementos)} (nodo padre especificado)")
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            elemento.click()
            time.sleep(1)

            mensaje_nodo = f" (primera coincidencia de {len(elementos)})" if len(elementos) > 1 and nodo_padre else ""
            return (fila, f"He abierto el proyecto '{nombre_proyecto}'{mensaje_nodo}", False, [])
            
        except Exception as e:
            # CRÍTICO: Si no encuentra el proyecto, cerrar todo y devolver error
            print(f"[DEBUG] ❌ No se encontró el proyecto '{nombre_proyecto}' en el sistema")
            
            # Cerrar el overlay del buscador
            try:
                driver.execute_script("""
                    document.getElementById('textoBusqueda').value='Introduzca proyecto/tipologia';
                    document.getElementById('textoBusqueda').style.color='gray';
                    buscadorJTree();
                    var tree = $('#treeTipologia');
                    tree.jstree('deselect_all');
                    tree.jstree('close_all');
                    hideOverlay();
                """)
                time.sleep(0.5)
            except Exception as close_error:
                print(f"[DEBUG] ⚠️ Error cerrando overlay: {close_error}")
            
            # Eliminar la línea vacía que quedó
            try:
                btn_eliminar = fila.find_element(By.CSS_SELECTOR, "button.botonEliminar, button#botonEliminar, input[id*='btEliminar']")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_eliminar)
                time.sleep(0.2)
                btn_eliminar.click()
                time.sleep(0.5)
                print(f"[DEBUG] 🗑️ Línea vacía eliminada")
            except Exception as del_error:
                print(f"[DEBUG] ⚠️ No se pudo eliminar la línea vacía: {del_error}")
            
            # Devolver None para indicar ERROR y detener la ejecución
            return (None, f"❌ No he encontrado el proyecto '{nombre_proyecto}' en el sistema. Verifica el nombre e inténtalo de nuevo.", False, [])

    except Exception as e:
        return (None, f"No he podido seleccionar el proyecto '{nombre_proyecto}': {e}", False, [])


def eliminar_linea_proyecto(driver, wait, nombre_proyecto):
    """
    Elimina una línea de proyecto completa.
    Busca el proyecto, encuentra su botón de eliminar y lo pulsa.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        nombre_proyecto: Nombre del proyecto a eliminar
        
    Returns:
        str: Mensaje de confirmación o error
    """
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
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
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


def imputar_horas_dia(driver, wait, dia, horas, fila, nombre_proyecto=None, modo="sumar"):
    """
    Imputa una cantidad específica de horas en un día concreto.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        dia: Nombre del día (lunes, martes, etc.)
        horas: Cantidad de horas a imputar
        fila: Elemento <tr> del proyecto
        nombre_proyecto: Nombre del proyecto (opcional, para mensaje)
        modo: "sumar" (default) añade horas | "establecer" pone exactamente esa cantidad
        
    Returns:
        str: Mensaje de confirmación o error
    """
    dia_clave = Constants.DIAS_KEYS.get(dia.lower())
    if not dia_clave:
        return f"No reconozco el día '{dia}'"

    try:
        campo = fila.find_element(By.CSS_SELECTOR, Selectors.campo_horas_dia(dia_clave))
        
        print(f"[DEBUG] 📝 Campo encontrado para {dia} ({dia_clave})")
        
        if campo.is_enabled():
            # Hacer scroll y enfocar el campo
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo)
            time.sleep(0.3)
            
            # Click para asegurar foco
            campo.click()
            time.sleep(0.2)
            
            valor_actual = campo.get_attribute("value") or "0"
            try:
                valor_actual = float(valor_actual.replace(",", "."))
            except ValueError:
                valor_actual = 0.0

            nuevas_horas = float(horas)
            
            if modo == "establecer":
                total = nuevas_horas
                # Limpiar con Ctrl+A y Delete para asegurar
                campo.send_keys(Keys.CONTROL + "a")
                campo.send_keys(Keys.DELETE)
                time.sleep(0.1)
                campo.send_keys(str(total))
                
                # 🆕 CRÍTICO: Hacer clic fuera del input para que refresque la tabla
                # Esto evita que el botón guardar se desactualice
                time.sleep(0.2)
                campo.send_keys(Keys.TAB)  # Salir del campo con TAB
                time.sleep(0.5)  # Dar tiempo a que la tabla se actualice
                
                proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
                print(f"[DEBUG] ✅ Establecidas {total}h el {dia} {proyecto_texto}")
                return f"He establecido {total}h el {dia} {proyecto_texto}"
            else:
                total = round(valor_actual + nuevas_horas, 2)
                # Limpiar con Ctrl+A y Delete para asegurar
                campo.send_keys(Keys.CONTROL + "a")
                campo.send_keys(Keys.DELETE)
                time.sleep(0.1)
                campo.send_keys(str(total))
                
                # 🆕 CRÍTICO: Hacer clic fuera del input para que refresque la tabla
                # Esto evita que el botón guardar se desactualice
                time.sleep(0.2)
                campo.send_keys(Keys.TAB)  # Salir del campo con TAB
                time.sleep(0.5)  # Dar tiempo a que la tabla se actualice
                
                proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
                accion = "añadido" if nuevas_horas > 0 else "restado"
                
                print(f"[DEBUG] ✅ {accion.capitalize()} {abs(nuevas_horas)}h el {dia} {proyecto_texto} (total: {total}h)")
                
                if valor_actual > 0:
                    return f"He {accion} {abs(nuevas_horas)}h el {dia} {proyecto_texto} (total: {total}h)"
                else:
                    return f"He imputado {total}h el {dia} {proyecto_texto}"
        else:
            return f"El {dia} no está disponible para imputar"
    except Exception as e:
        print(f"[DEBUG] ❌ Error imputando horas: {e}")
        import traceback
        traceback.print_exc()
        return f"No he podido imputar horas el {dia}: {e}"


def imputar_horas_semana(driver, wait, fila, nombre_proyecto=None):
    """
    Imputa las horas de lunes a viernes dentro de la fila (<tr>) del proyecto.
    Usa las horas por defecto de Constants.HORAS_SEMANA_DEFAULT.
    Si un campo no está disponible (festivo, deshabilitado, etc.), lo omite.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        fila: Elemento <tr> del proyecto
        nombre_proyecto: Nombre del proyecto (opcional, para mensaje)
        
    Returns:
        str: Mensaje de confirmación o error
    """
    dias_imputados = []

    try:
        for dia_nombre, valor in Constants.HORAS_SEMANA_DEFAULT.items():
            try:
                dia_key = Constants.DIAS_KEYS[dia_nombre]
                campo = fila.find_element(By.CSS_SELECTOR, Selectors.campo_horas_dia(dia_key))
                if campo.is_enabled():
                    # Hacer scroll y click
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", campo)
                    campo.click()
                    time.sleep(0.1)
                    
                    # Limpiar y escribir
                    campo.send_keys(Keys.CONTROL + "a")
                    campo.send_keys(Keys.DELETE)
                    campo.send_keys(str(valor))
                    
                    dias_imputados.append(f"{dia_nombre} ({valor}h)")
                    time.sleep(0.1)
            except Exception:
                pass
        
        # 🆕 CRÍTICO: Después de modificar TODOS los días, salir del último input
        # para que la tabla se actualice correctamente antes de guardar
        if dias_imputados:
            try:
                # Enviar TAB para salir del último campo
                driver.switch_to.active_element.send_keys(Keys.TAB)
                time.sleep(0.5)  # Dar tiempo a que la tabla se actualice
            except:
                pass

        if dias_imputados:
            dias_texto = ", ".join(dias_imputados)
            proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
            return f"He imputado toda la semana {proyecto_texto}: {dias_texto}"
        else:
            return f"No he podido imputar ningún día (puede que estén bloqueados o sean festivos)"

    except Exception as e:
        return f"Ha habido un problema al imputar la semana: {e}"


def borrar_todas_horas_dia(driver, wait, dia):
    """
    Pone a 0 las horas de TODOS los proyectos en un día específico.
    Busca todas las líneas de la tabla y pone 0 en la columna del día indicado.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        dia: Nombre del día (lunes, martes, etc.)
        
    Returns:
        str: Mensaje de confirmación o error
    """
    dia_clave = Constants.DIAS_KEYS.get(dia.lower())
    if not dia_clave:
        return f"No reconozco el día '{dia}'"

    try:
        # Buscar TODAS las filas de proyectos
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        proyectos_modificados = []
        
        for idx, sel in enumerate(selects):
            try:
                # Obtener el nombre del proyecto
                proyecto_nombre = driver.execute_script("""
                    var select = arguments[0];
                    var selectedOption = select.options[select.selectedIndex];
                    return selectedOption ? selectedOption.text : '';
                """, sel)
                
                if not proyecto_nombre or proyecto_nombre == "Seleccione opción":
                    continue
                
                # Extraer solo el nombre del proyecto (última parte)
                partes = proyecto_nombre.split(' - ')
                nombre_corto = partes[-1].strip() if partes else proyecto_nombre
                
                # Buscar la fila
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                
                # Buscar el campo de horas del día
                campo = fila.find_element(By.CSS_SELECTOR, Selectors.campo_horas_dia(dia_clave))
                
                if campo.is_enabled():
                    valor_actual = campo.get_attribute("value") or "0"
                    try:
                        valor_actual = float(valor_actual.replace(",", "."))
                    except ValueError:
                        valor_actual = 0.0
                    
                    # Solo modificar si tenía horas
                    if valor_actual > 0:
                        campo.click()
                        campo.send_keys(Keys.CONTROL + "a")
                        campo.send_keys("0")
                        proyectos_modificados.append(f"{nombre_corto} ({valor_actual}h)")
                        time.sleep(0.1)
            
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error procesando línea {idx+1}: {e}")
                continue
        
        # 🆕 CRÍTICO: Después de modificar todos los campos, salir del último input
        # para que la tabla se actualice correctamente antes de guardar
        if proyectos_modificados:
            try:
                # Enviar TAB para salir del último campo
                driver.switch_to.active_element.send_keys(Keys.TAB)
                time.sleep(0.5)  # Dar tiempo a que la tabla se actualice
            except:
                pass
            
            proyectos_texto = ", ".join(proyectos_modificados)
            return f"He borrado las horas del {dia} en: {proyectos_texto}"
        else:
            return f"No había horas que borrar el {dia}"
    
    except Exception as e:
        return f"No he podido borrar las horas del {dia}: {e}"


def leer_tabla_imputacion(driver):
    """
    Lee toda la información de la tabla de imputación actual.
    Devuelve una lista de diccionarios con los proyectos y sus horas.
    
    Args:
        driver: WebDriver de Selenium
        
    Returns:
        list: Lista de diccionarios con información de cada proyecto:
              [
                  {
                      "proyecto": "Nombre del proyecto",
                      "horas": {"lunes": 8.5, "martes": 8.5, ...},
                      "total": 42.5
                  },
                  ...
              ]
    """
    try:
        # Buscar todas las filas con proyectos
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        print(f"[DEBUG] 📊 Leyendo tabla... Encontrados {len(selects)} proyectos")
        
        proyectos_info = []
        
        for idx, sel in enumerate(selects):
            # Leer el proyecto seleccionado
            try:
                proyecto_nombre = driver.execute_script("""
                    var select = arguments[0];
                    var selectedOption = select.options[select.selectedIndex];
                    return selectedOption ? selectedOption.text : '';
                """, sel)
                
                if not proyecto_nombre or proyecto_nombre == "Seleccione opción":
                    print(f"[DEBUG]   Proyecto {idx+1}: Sin selección")
                    continue
                
                print(f"[DEBUG]   Proyecto {idx+1}: {proyecto_nombre}")
                
                # Buscar la fila correspondiente
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                
                # Leer las horas de cada día
                horas_dias = {}
                
                for dia_nombre, dia_key in Constants.DIAS_KEYS.items():
                    try:
                        campo = fila.find_element(By.CSS_SELECTOR, Selectors.campo_horas_dia(dia_key))
                        valor = campo.get_attribute("value") or "0"
                        try:
                            valor_float = float(valor.replace(",", "."))
                        except ValueError:
                            valor_float = 0.0
                        horas_dias[dia_nombre] = valor_float
                    except:
                        horas_dias[dia_nombre] = 0.0
                
                # Calcular total
                total_horas = sum(horas_dias.values())
                
                print(f"[DEBUG]     Total horas: {total_horas}")
                
                # INCLUIR PROYECTO AUNQUE TENGA 0 HORAS (FIX)
                proyectos_info.append({
                    "proyecto": proyecto_nombre,
                    "horas": horas_dias,
                    "total": total_horas
                })
            
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error leyendo proyecto {idx}: {e}")
                continue
        
        print(f"[DEBUG] ✅ Lectura completa: {len(proyectos_info)} proyectos procesados")
        return proyectos_info
    
    except Exception as e:
        print(f"[DEBUG] ❌ Error leyendo tabla: {e}")
        import traceback
        traceback.print_exc()
        return []
