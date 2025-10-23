def eliminar_linea_proyecto(driver, wait, nombre_proyecto):
    """
    Elimina una línea de proyecto completa.
    Busca el proyecto, encuentra su botón de eliminar y lo pulsa.
    """
    import unicodedata

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

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv
import time, json, os


# --- CARGAR VARIABLES DEL .env ---
load_dotenv()  # Carga OPENAI_API_KEY, INTRA_USER, INTRA_PASS, etc.
# -------------------

# --- CONFIGURAR ---
LOGIN_URL = os.getenv("URL_PRIVADA")
USERNAME = os.getenv("INTRA_USER")
PASSWORD = os.getenv("INTRA_PASS")
USERNAME_SELECTOR = '#usuario'
PASSWORD_SELECTOR = '#password'
SUBMIT_SELECTOR = '#btAceptar'
CALENDAR_BUTTON_SELECTOR = '.ui-datepicker-trigger'
VOLVER_SELECTOR = '#btVolver'
BUSCADOR_INPUT_SELECTOR = '#textoBusqueda'
BUSCADOR_BOTON_SELECTOR = '#buscar'
# -------------------

hoy = datetime.now()

# Crear cliente OpenAI con la clave del .env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Variable global para acumular respuestas
respuestas_acumuladas = []

# Historial conversacional para GPT
historial_conversacion = []

# ---------------------------------------------------------------------
# GENERAR RESPUESTA NATURAL CON GPT
# ---------------------------------------------------------------------
def generar_respuesta_natural(acciones_ejecutadas, entrada_usuario):
    """
    Usa GPT para generar una respuesta natural basada en las acciones ejecutadas.
    """
    if not acciones_ejecutadas:
        return "No he entendido qué quieres que haga. ¿Podrías reformularlo?"
    
    # Crear resumen de acciones
    resumen_acciones = "\n".join([f"- {acc}" for acc in acciones_ejecutadas])
    
    prompt = f"""Eres un asistente virtual amigable de imputación de horas laborales.

El usuario te dijo: "{entrada_usuario}"

Has ejecutado las siguientes acciones:
{resumen_acciones}

Genera una respuesta natural, breve y amigable (máximo 2-3 líneas) confirmando lo que has hecho.
Usa un tono conversacional, cercano y profesional. Puedes usar emojis ocasionalmente.
No inventes información que no esté en las acciones ejecutadas.

Ejemplos de buen estilo:
- "¡Listo! He imputado 8 horas en Desarrollo para hoy y lo he guardado todo."
- "Perfecto, ya tienes toda la semana imputada en el proyecto Estudio. He guardado los cambios."
- "He iniciado tu jornada laboral. ¡A trabajar! 💪"

Respuesta:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente virtual amigable y profesional que confirma tareas completadas de forma natural."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        respuesta = response.choices[0].message.content.strip()
        return respuesta
    
    except Exception as e:
        # Fallback: si falla GPT, unir las respuestas simples
        return " · ".join(acciones_ejecutadas)

# ---------------------------------------------------------------------
# FUNCIONES BASE
# ---------------------------------------------------------------------
def save_cookies(driver, path="cookies.json"):
    with open(path, "w") as f:
        json.dump(driver.get_cookies(), f)

def lunes_de_semana(fecha):
    return fecha - timedelta(days=fecha.weekday())

def hacer_login(driver, wait, username=None, password=None):
    """Realiza el login en la intranet con las credenciales proporcionadas.
    
    Returns:
        tuple: (success: bool, message: str)
            - success: True si el login fue exitoso, False si falló
            - message: Mensaje descriptivo del resultado
    """
    # Si no se proporcionan credenciales, usar las del .env (modo compatibilidad)
    if username is None:
        username = USERNAME
    if password is None:
        password = PASSWORD
    
    try:
        driver.get(LOGIN_URL)
        usr = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, USERNAME_SELECTOR)))
        usr.clear()
        usr.send_keys(username)
        pwd = driver.find_element(By.CSS_SELECTOR, PASSWORD_SELECTOR)
        pwd.clear()
        pwd.send_keys(password)
        driver.find_element(By.CSS_SELECTOR, SUBMIT_SELECTOR).click()
        time.sleep(3)
        
        # 🔍 Verificar si hay error de login
        try:
            error_div = driver.find_element(By.CSS_SELECTOR, ".errorLogin, div[class*='error']")
            if error_div.is_displayed():
                error_text = error_div.text.strip()
                print(f"[DEBUG] ❌ Error de login detectado: {error_text}")
                return False, "credenciales_invalidas"
        except:
            # No hay div de error, el login fue exitoso
            pass
        
        # ✅ Login exitoso
        return True, "login_exitoso"
        
    except Exception as e:
        print(f"[DEBUG] ❌ Excepción durante login: {e}")
        return False, f"error_tecnico: {e}"

def volver_inicio(driver):
    """Pulsa el botón 'Volver' para regresar a la pantalla principal tras login."""
    try:
        btn_volver = driver.find_element(By.CSS_SELECTOR, VOLVER_SELECTOR)
        btn_volver.click()
        time.sleep(2)
        return "He vuelto a la pantalla principal"
    except Exception as e:
        return f"No he podido volver a la pantalla principal: {e}"

def seleccionar_fecha(driver, fecha_obj):
    """Abre el calendario, navega hasta el mes correcto y selecciona el día correspondiente."""
    
    # 🔍 Detectar si estamos en la pantalla de imputación
    try:
        btn_volver = driver.find_element(By.CSS_SELECTOR, "#btVolver")
        if btn_volver.is_displayed():
            print("[DEBUG] 🔙 Detectada pantalla de imputación, volviendo para cambiar fecha...")
            btn_volver.click()
            time.sleep(2)
    except:
        # No hay botón volver, ya estamos donde debemos
        pass
    
    wait = WebDriverWait(driver, 15)
    wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, CALENDAR_BUTTON_SELECTOR))).click()
    wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".ui-datepicker-calendar")))

    titulo_selector = ".ui-datepicker-title"
    meses = {
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
        "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
    }

    def obtener_mes_anio_actual():
        texto = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, titulo_selector))).text.lower()
        partes = texto.split()
        mes_visible = meses[partes[0]]
        anio_visible = int(partes[1])
        return mes_visible, anio_visible

    mes_visible, anio_visible = obtener_mes_anio_actual()

    while (anio_visible, mes_visible) < (fecha_obj.year, fecha_obj.month):
        driver.find_element(By.CSS_SELECTOR, ".ui-datepicker-next").click()
        time.sleep(0.3)
        mes_visible, anio_visible = obtener_mes_anio_actual()

    while (anio_visible, mes_visible) > (fecha_obj.year, fecha_obj.month):
        driver.find_element(By.CSS_SELECTOR, ".ui-datepicker-prev").click()
        time.sleep(0.3)
        mes_visible, anio_visible = obtener_mes_anio_actual()

    dia_seleccionado = fecha_obj.day

    try:
        driver.find_element(By.XPATH, f"//a[text()='{dia_seleccionado}']").click()
        fecha_formateada = fecha_obj.strftime('%d/%m/%Y')
        time.sleep(2)  # ⏸️ Esperar a que cargue la pantalla de imputación
        return f"He seleccionado la fecha {fecha_formateada}"
    except Exception as e:
        return f"No he podido seleccionar el día {dia_seleccionado}: {e}"


# ---------------------------------------------------------------------
# NUEVA FUNCIÓN: SELECCIONAR PROYECTO
# ---------------------------------------------------------------------
def seleccionar_proyecto(driver, wait, nombre_proyecto):
    """
    Selecciona el proyecto en la tabla de imputación.
    Si ya existe una línea con ese proyecto, la reutiliza.
    Si no existe, crea una nueva línea, abre el buscador,
    busca el proyecto y lo selecciona.
    Devuelve el elemento <tr> correspondiente al proyecto.
    """

    import unicodedata

    def normalizar(texto):
        """Normaliza acentos y minúsculas."""
        return ''.join(
            c for c in unicodedata.normalize('NFD', texto.lower())
            if unicodedata.category(c) != 'Mn'
        )

    try:
        # ⏸️ Dar tiempo a que la página se estabilice tras guardar
        time.sleep(0.5)
        
        # 🔍 Buscar si el proyecto ya existe en TODAS las líneas (guardadas o no)
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        # Si no encuentra por name, intentar por id
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        print(f"[DEBUG] 🔍 Buscando proyecto '{nombre_proyecto}' en {len(selects)} líneas totales...")
        
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
            
            # 🎯 CRÍTICO: Extraer SOLO la última parte (el proyecto real)
            # Ejemplo: "Arelance - Departamento - Desarrollo" → "Desarrollo"
            partes = texto_completo.split(' - ')
            nombre_proyecto_real = partes[-1].strip() if partes else ""
            
            print(f"[DEBUG]   Línea {idx+1} ({estado}): '{texto_completo}' → Proyecto: '{nombre_proyecto_real}'")
            
            # 🎯 BÚSQUEDA FLEXIBLE: Comparar si el nombre buscado está CONTENIDO en el nombre real
            # Esto permite que "Estudio" coincida con "Estudio/Investigación"
            nombre_buscado_norm = normalizar(nombre_proyecto)
            nombre_real_norm = normalizar(nombre_proyecto_real)
            
            # Coincidencia si:
            # 1. Son exactamente iguales, O
            # 2. El nombre buscado está contenido en el nombre real
            if nombre_buscado_norm == nombre_real_norm or nombre_buscado_norm in nombre_real_norm:
                # Si el proyecto YA está guardado (disabled), reutilizamos esa fila
                if is_disabled:
                    print(f"[DEBUG] ✅ ¡Proyecto '{nombre_proyecto}' encontrado en línea {idx+1} (GUARDADA)! Reutilizando...")
                    fila = sel.find_element(By.XPATH, "./ancestor::tr")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                    time.sleep(0.3)
                    return fila, f"He encontrado el proyecto '{nombre_proyecto}' ya guardado, añadiendo horas"
                
                # Si el proyecto está en una línea editable (no guardada), también la reutilizamos
                else:
                    print(f"[DEBUG] ✅ ¡Proyecto '{nombre_proyecto}' encontrado en línea {idx+1} (EDITABLE)! Reutilizando...")
                    fila = sel.find_element(By.XPATH, "./ancestor::tr")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                    time.sleep(0.3)
                    return fila, f"Ya tenías el proyecto '{nombre_proyecto}' abierto, lo estoy usando"

        # 🆕 Si no existe → añadimos nueva línea
        print(f"[DEBUG] ➕ Proyecto '{nombre_proyecto}' NO encontrado, añadiendo nueva línea...")
        btn_nueva_linea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btNuevaLinea")))
        btn_nueva_linea.click()
        time.sleep(1)

        # 🔢 Detectar el nuevo <select> (último en la lista)
        selects_actualizados = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
        nuevo_select = selects_actualizados[-1]
        fila = nuevo_select.find_element(By.XPATH, "./ancestor::tr")

        # 📌 Buscar el botón "»" correspondiente dentro de la misma fila
        try:
            btn_cambiar = fila.find_element(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
        except Exception:
            botones = driver.find_elements(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
            btn_cambiar = botones[-1] if botones else None

        if btn_cambiar:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cambiar)
            btn_cambiar.click()
        else:
            return None, f"No he encontrado el botón para buscar el proyecto '{nombre_proyecto}'"

        # 3️⃣ Esperar a que aparezca el campo de búsqueda
        campo_buscar = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#textoBusqueda")))
        campo_buscar.clear()
        campo_buscar.send_keys(nombre_proyecto)

        # 4️⃣ Pulsar en el botón "Buscar"
        btn_buscar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#buscar")))
        btn_buscar.click()
        time.sleep(1.5)

        # 5️⃣ Expandir árbol de resultados
        driver.execute_script("""
            var tree = $('#treeTipologia');
            if (tree && tree.jstree) { tree.jstree('open_all'); }
        """)
        time.sleep(1)

        # 6️⃣ Buscar y seleccionar el proyecto
        # IMPORTANTE: NO normalizar (quitar tildes) porque el sistema es sensible a tildes
        xpath = (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            f"'{nombre_proyecto.lower()}')]"
        )

        try:
            elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            elemento.click()
            time.sleep(1)

            return fila, f"He abierto el proyecto '{nombre_proyecto}'"
            
        except Exception as e:
            # 🛑 CRÍTICO: Si no encuentra el proyecto, cerrar todo y devolver error
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
            
            # 🛑 Devolver None para indicar ERROR y detener la ejecución
            return None, f"❌ No he encontrado el proyecto '{nombre_proyecto}' en el sistema. Verifica el nombre e inténtalo de nuevo."

    except Exception as e:
        return None, f"No he podido seleccionar el proyecto '{nombre_proyecto}': {e}"



def imputar_horas_semana(driver, wait, fila, nombre_proyecto=None):
    """
    Imputa las horas de lunes a viernes dentro de la fila (<tr>) del proyecto.
    Lunes a jueves → 8.5 horas
    Viernes → 6.5 horas
    Si un campo no está disponible (festivo, deshabilitado, etc.), lo omite.
    """
    horas_semana = {
        "lunes": "8.5",
        "martes": "8.5",
        "miércoles": "8.5",
        "jueves": "8.5",
        "viernes": "6.5",
    }
    
    dias_keys = {
        "lunes": "h1",
        "martes": "h2",
        "miércoles": "h3",
        "jueves": "h4",
        "viernes": "h5",
    }
    
    dias_imputados = []

    try:
        for dia_nombre, valor in horas_semana.items():
            try:
                campo = fila.find_element(By.CSS_SELECTOR, f"input[id$='.{dias_keys[dia_nombre]}']")
                if campo.is_enabled():
                    campo.clear()
                    campo.send_keys(valor)
                    dias_imputados.append(f"{dia_nombre} ({valor}h)")
                    time.sleep(0.2)
            except Exception:
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
    """
    mapa_dias = {
        "lunes": "h1", "martes": "h2", "miércoles": "h3",
        "miercoles": "h3", "jueves": "h4", "viernes": "h5"
    }

    dia_clave = mapa_dias.get(dia.lower())
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
                campo = fila.find_element(By.CSS_SELECTOR, f"input[id$='.{dia_clave}']")
                
                if campo.is_enabled():
                    valor_actual = campo.get_attribute("value") or "0"
                    try:
                        valor_actual = float(valor_actual.replace(",", "."))
                    except ValueError:
                        valor_actual = 0.0
                    
                    # Solo modificar si tenía horas
                    if valor_actual > 0:
                        campo.clear()
                        campo.send_keys("0")
                        proyectos_modificados.append(f"{nombre_corto} ({valor_actual}h)")
                        time.sleep(0.2)
            
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error procesando línea {idx+1}: {e}")
                continue
        
        if proyectos_modificados:
            proyectos_texto = ", ".join(proyectos_modificados)
            return f"He borrado las horas del {dia} en: {proyectos_texto}"
        else:
            return f"No había horas que borrar el {dia}"
    
    except Exception as e:
        return f"No he podido borrar las horas del {dia}: {e}"


def imputar_horas_dia(driver, wait, dia, horas, fila, nombre_proyecto=None, modo="sumar"):
    """
    Imputa una cantidad específica de horas en un día concreto.
    modo: "sumar" (default) añade horas | "establecer" pone exactamente esa cantidad
    """
    mapa_dias = {
        "lunes": "h1", "martes": "h2", "miércoles": "h3",
        "miercoles": "h3", "jueves": "h4", "viernes": "h5"
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
                total = nuevas_horas
                campo.clear()
                campo.send_keys(str(total))
                proyecto_texto = f"en el proyecto {nombre_proyecto}" if nombre_proyecto else ""
                return f"He establecido {total}h el {dia} {proyecto_texto}"
            else:
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
            return f"El {dia} no está disponible para imputar"
    except Exception as e:
        return f"No he podido imputar horas el {dia}: {e}"



def guardar_linea(driver, wait):
    """Pulsa el botón 'Guardar' tras imputar horas."""
    try:
        btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btGuardarLinea")))
        btn_guardar.click()
        time.sleep(1.5)
        
        # 🔍 Verificar si hay algún popup de error
        try:
            # Buscar el popup de error (puede tener diferentes clases)
            popup_error = driver.find_element(By.CSS_SELECTOR, ".ui-dialog, .modal, [role='dialog']")
            
            if popup_error.is_displayed():
                # Leer el mensaje de error
                try:
                    mensaje_error = popup_error.find_element(By.CSS_SELECTOR, ".ui-dialog-content, .modal-body, p").text
                    print(f"[DEBUG] ⚠️ Error detectado al guardar: {mensaje_error}")
                    
                    # Cerrar el popup haciendo clic en "Aceptar" o botón de cerrar
                    try:
                        btn_aceptar = popup_error.find_element(By.XPATH, ".//button[contains(text(), 'Aceptar') or contains(text(), 'OK') or contains(text(), 'Cerrar')]")
                        btn_aceptar.click()
                        time.sleep(0.5)
                    except:
                        # Si no encuentra el botón, intentar con Escape
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(0.5)
                    
                    return f"❌ Error al guardar: {mensaje_error}"
                except:
                    return "❌ Error al guardar (no se pudo leer el mensaje de error)"
        except:
            # No hay popup de error, todo OK
            pass
        
        return "He guardado los cambios"
    except Exception as e:
        return f"No he podido guardar: {e}"

def emitir_linea(driver, wait):
    """Pulsa el botón 'Emitir' tras imputar horas y acepta el alert de confirmación."""
    try:
        btn_emitir = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btEmitir")))
        btn_emitir.click()
        
        # ⏳ Esperar a que aparezca el alert de confirmación
        time.sleep(0.5)  # Pequeña espera para que se muestre el alert
        
        try:
            # 📢 Capturar el alert de JavaScript
            alert = wait.until(EC.alert_is_present())
            
            # 📝 Leer el mensaje del alert (opcional, para debug)
            mensaje_alert = alert.text
            print(f"[DEBUG] 📢 Alert detectado: '{mensaje_alert}'")
            
            # ✅ Aceptar el alert (equivalente a pulsar "Aceptar")
            alert.accept()
            print(f"[DEBUG] ✅ Alert aceptado")
            
            time.sleep(1.5)  # Esperar a que se procese la emisión
            return "He emitido las horas correctamente"
            
        except Exception as e_alert:
            # Si no hay alert o falla, continuar
            print(f"[DEBUG] ⚠️ No se detectó alert o error al aceptarlo: {e_alert}")
            time.sleep(1.5)
            return "He pulsado emitir (no se detectó confirmación)"
            
    except Exception as e:
        return f"No he podido emitir: {e}"


def iniciar_jornada(driver, wait):
    """
    Pulsa el botón 'Inicio jornada' si está disponible.
    Si el botón no está o ya se ha pulsado, lo ignora.
    """
    try:
        # 🔙 Volver al inicio si estamos en pantalla de imputación
        try:
            btn_volver = driver.find_element(By.CSS_SELECTOR, "#btVolver")
            if btn_volver.is_displayed():
                print("[DEBUG] 🔙 Volviendo al inicio antes de iniciar jornada...")
                btn_volver.click()
                time.sleep(2)
        except:
            pass  # Ya estamos en la pantalla correcta
        
        btn_inicio = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#botonInicioJornada")))

        if btn_inicio.is_enabled():
            btn_inicio.click()
            time.sleep(2)
            return "He iniciado tu jornada laboral"
        else:
            return "Tu jornada ya estaba iniciada"

    except Exception as e:
        return f"No he podido iniciar la jornada: {e}"

def finalizar_jornada(driver, wait):
    """
    Pulsa el botón 'Finalizar jornada' si está disponible.
    Si el botón no está o ya se ha pulsado, lo ignora.
    """
    try:
        # 🔙 Volver al inicio si estamos en pantalla de imputación
        try:
            btn_volver = driver.find_element(By.CSS_SELECTOR, "#btVolver")
            if btn_volver.is_displayed():
                print("[DEBUG] 🔙 Volviendo al inicio antes de finalizar jornada...")
                btn_volver.click()
                time.sleep(2)
        except:
            pass  # Ya estamos en la pantalla correcta
        
        btn_fin = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#botonFinJornada")))

        if btn_fin.is_enabled():
            btn_fin.click()
            time.sleep(2)
            return "He finalizado tu jornada laboral"
        else:
            return "Tu jornada ya estaba finalizada"

    except Exception as e:
        return f"No he podido finalizar la jornada: {e}"



# ---------------------------------------------------------------------
# FUNCIONES DE CONSULTA
# ---------------------------------------------------------------------
def leer_tabla_imputacion(driver):
    """
    Lee toda la información de la tabla de imputación actual.
    Devuelve un diccionario con los proyectos y sus horas.
    """
    try:
        # Buscar todas las filas con proyectos
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
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
                    continue
                
                # Buscar la fila correspondiente
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                
                # Leer las horas de cada día
                horas_dias = {}
                dias_map = {
                    "lunes": "h1",
                    "martes": "h2",
                    "miércoles": "h3",
                    "jueves": "h4",
                    "viernes": "h5"
                }
                
                for dia_nombre, dia_key in dias_map.items():
                    try:
                        campo = fila.find_element(By.CSS_SELECTOR, f"input[id$='.{dia_key}']")
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
                
                if total_horas > 0:
                    proyectos_info.append({
                        "proyecto": proyecto_nombre,
                        "horas": horas_dias,
                        "total": total_horas
                    })
            
            except Exception as e:
                print(f"[DEBUG] Error leyendo proyecto {idx}: {e}")
                continue
        
        return proyectos_info
    
    except Exception as e:
        print(f"[DEBUG] Error leyendo tabla: {e}")
        return []


def consultar_dia(driver, wait, fecha_obj):
    """
    Consulta la información de un día específico.
    Navega a la fecha, lee la tabla y devuelve un resumen del día.
    """
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
    """
    try:
        # Seleccionar la fecha (lunes de la semana)
        # seleccionar_fecha() ya detectará si necesita volver
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


def generar_resumen_natural(info_semana, consulta_usuario):
    """
    Usa GPT para generar un resumen natural de la información de la semana.
    """
    prompt = f"""Eres un asistente de imputación de horas. El usuario preguntó: "{consulta_usuario}"

Información de la semana:
{info_semana}

Genera una respuesta natural, amigable y bien formateada con emojis. 
Destaca lo más importante y presenta la información de forma clara.

⚠️ IMPORTANTE: NO incluyas saludos ni presentaciones. Ve directo a la información solicitada.

Respuesta:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente que resume información de horas laborales de forma amigable."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        # Si falla GPT, devolver el resumen tal cual
        return info_semana




# ---------------------------------------------------------------------
# INTERPRETACIÓN REAL CON GPT
# ---------------------------------------------------------------------
def clasificar_mensaje(texto):
    """
    Clasifica si el mensaje del usuario es:
    - 'comando': requiere ejecutar acciones de imputación
    - 'consulta': pide información sobre horas imputadas
    - 'conversacion': saludo, pregunta general o tema fuera del ámbito laboral
    """
    print(f"[DEBUG] 🔍 Clasificando: '{texto}'")
    
    # Keywords para detectar comandos de jornada sin ambigüedad
    keywords_jornada = [
        "iniciar jornada", "empezar jornada", "comenzar jornada", "inicia jornada",
        "finalizar jornada", "terminar jornada", "acabar jornada", "finaliza jornada", 
        "termina jornada", "acaba jornada",
        "finaliza el dia", "termina el dia", "acaba el dia",
        "finalizar el dia", "terminar el dia", "acabar el dia",
        "fin de jornada", "cierra jornada"
    ]
    
    texto_lower = texto.lower()
    
    # Si contiene keywords de jornada, es comando directo
    if any(keyword in texto_lower for keyword in keywords_jornada):
        return "comando"
    
    # Keywords para imputación
    keywords_imputacion = [
        "imput", "pon", "añade", "agrega", "quita", "resta", "borra",
        "horas", "proyecto", "guardar", "emitir"
    ]
    
    if any(keyword in texto_lower for keyword in keywords_imputacion):
        return "comando"
    
    # Keywords para consultas - Detectar solicitudes de información
    keywords_consulta = [
        "qué tengo", "que tengo", "dime", "qué he imputado", "que he imputado",
        "cuántas", "cuantas", "cuántas horas", "cuantas horas",
        "ver", "mostrar", "dame", "info", "consulta", 
        "resumen", "resume", "resumíme", "qué hice", "que hice",
        "he hecho", "tengo hecho"
    ]
    
    # Detectar consultas por keywords
    if any(keyword in texto_lower for keyword in keywords_consulta):
        print(f"[DEBUG] 📊 Detectada keyword de consulta")
        return "consulta"
    
    # 🔴 DETECCIÓN ADICIONAL: Frases tipo "cuántas horas..."
    if ("cuantas" in texto_lower or "cuántas" in texto_lower) and "horas" in texto_lower:
        print(f"[DEBUG] 📊 Detectada consulta de horas")
        return "consulta"
    
    # Si menciona "semana" + palabras de consulta = es una consulta
    if "semana" in texto_lower:
        print(f"[DEBUG] 📅 Detectado 'semana' en el texto")
        keywords_consulta_semana = [
            "resumen", "resume", "resumíme", "qué tengo", "dime", "qué he imputado",
            "cuántas", "ver", "mostrar", "dame", "info", "consulta", "cuenta"
        ]
        
        matches = [k for k in keywords_consulta_semana if k in texto_lower]
        print(f"[DEBUG] Keywords de consulta encontradas: {matches}")
        
        if matches:
            print(f"[DEBUG] ✅ Clasificado como CONSULTA por keywords: semana + {matches}")
            return "consulta"
        else:
            print(f"[DEBUG] ⚠️ Tiene 'semana' pero no keywords específicas, pasando a GPT...")
            # NO retornar nada, dejar que siga a GPT
    
    # Si no matchea keywords claras, usar GPT
    hoy = datetime.now().strftime("%Y-%m-%d")

    prompt = f"""
Clasifica el siguiente mensaje en UNA de estas tres categorías:

1️⃣ "comando" → El usuario quiere HACER algo:
   - Imputar horas, modificar datos, iniciar/finalizar jornada
   - Ejemplos: "pon 8 horas", "imputa en desarrollo", "finaliza jornada"

2️⃣ "consulta" → El usuario quiere VER/SABER información:
   - Resúmenes, qué tiene imputado, cuántas horas, ver semanas/días
   - Ejemplos: "resumen de esta semana", "qué tengo imputado", "cuántas horas", "cuántas horas tengo hoy", "cuántas horas he hecho"

3️⃣ "conversacion" → Saludos o temas NO relacionados con trabajo:
   - Ejemplos: "hola", "quién es Messi", "capital de Francia"

⚠️ IMPORTANTE: Si pregunta por información de horas/semanas/proyectos = "consulta"
Si quiere modificar/añadir/cambiar horas = "comando"

Responde SOLO una palabra: "comando", "consulta" o "conversacion".

Mensaje: "{texto}"
Respuesta:"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un clasificador inteligente de intenciones de usuario."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )

        clasificacion = response.choices[0].message.content.strip().lower()
        print(f"[DEBUG] 🧠 GPT clasificó '{texto[:50]}...' como: {clasificacion}")
        return clasificacion

    except Exception as e:
        print(f"[DEBUG] Error en clasificar_mensaje: {e}")
        return "conversacion"



def responder_conversacion(texto):
    """
    Usa GPT para responder a saludos, preguntas generales, etc.
    Mantiene contexto de la conversación.
    """
    global historial_conversacion
    
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    # Añadir mensaje del usuario al historial
    historial_conversacion.append({"role": "user", "content": texto})
    
    # Limitar historial a últimos 10 mensajes para no consumir muchos tokens
    if len(historial_conversacion) > 20:
        historial_conversacion = historial_conversacion[-20:]
    
    # System prompt solo la primera vez o si es un saludo explícito
    es_saludo_explicito = any(palabra in texto.lower() for palabra in ["hola", "buenos días", "buenas tardes", "buenas noches", "hey", "qué tal"])
    
    if len(historial_conversacion) <= 1 or es_saludo_explicito:
        system_content = f"""Eres un asistente virtual amigable especializado en gestión de imputación de horas laborales.

Hoy es {hoy} ({dia_semana}).

Si el usuario te saluda por primera vez, preséntate brevemente. 
Si ya has conversado con el usuario y te vuelve a saludar, responde de forma natural sin volver a presentarte.
Si el usuario NO te saluda, NO le saludes tú tampoco. Ve directo al punto.
Responde de forma natural, amigable y concisa."""
    else:
        system_content = f"""Eres un asistente virtual amigable especializado en gestión de imputación de horas laborales.

Hoy es {hoy} ({dia_semana}).

Estás en medio de una conversación. NO te presentes de nuevo, NO saludes, solo responde a la pregunta de forma natural y directa.
Si te pregunta sobre algo externo (noticias, clima, información general), responde normalmente."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_content}
            ] + historial_conversacion,
            temperature=0.7,
            max_tokens=200
        )
        
        respuesta = response.choices[0].message.content.strip()
        
        # Añadir respuesta al historial
        historial_conversacion.append({"role": "assistant", "content": respuesta})
        
        return respuesta
    
    except Exception as e:
        return "Disculpa, he tenido un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"


def interpretar_consulta(texto):
    """
    Interpreta consultas sobre horas imputadas y extrae la fecha solicitada.
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    prompt = f"""Eres un asistente que interpreta consultas sobre horas laborales imputadas.

Hoy es {hoy} ({dia_semana}).

El usuario pregunta: "{texto}"

Extrae la fecha sobre la que pregunta y devuelve SOLO un JSON válido con este formato:
{{
  "fecha": "YYYY-MM-DD",
  "tipo": "semana" | "dia"  
}}

Reglas CRÍTICAS:
- Siempre usa el año 2025 (estamos en 2025)
- Si pregunta por "esta semana", "semana actual", "la semana" → tipo: "semana", fecha: lunes de la semana
- Si pregunta por "HOY" → tipo: "dia", fecha: {hoy}
- Si pregunta por "MAÑANA" → tipo: "dia", fecha: calcular día siguiente a {hoy}
- Si pregunta por "AYER" → tipo: "dia", fecha: calcular día anterior a {hoy}
- Si pregunta por un DÍA ESPECÍFICO ("el miércoles 15", "el 22 de septiembre", "el 15 de octubre") → tipo: "dia", fecha: ese día exacto
- Si dice "semana pasada", calcula el lunes de la semana anterior a {hoy}
- Si dice "próxima semana", calcula el lunes de la siguiente semana

Ejemplos:
- "esta semana" → {{"fecha": "(lunes de la semana actual)", "tipo": "semana"}}
- "semana pasada" → {{"fecha": "(lunes de la semana anterior)", "tipo": "semana"}}
- "la semana del 26 de septiembre" → {{"fecha": "2025-09-22", "tipo": "semana"}} (lunes de esa semana)
- "cuántas horas tengo hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "qué tengo imputado el miércoles 15" → {{"fecha": "2025-10-15", "tipo": "dia"}} (ese día exacto)
- "qué tengo el 22 de septiembre" → {{"fecha": "2025-09-22", "tipo": "dia"}} (ese día exacto)
- "dime qué tengo hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "cuántas horas he hecho hoy" → {{"fecha": "{hoy}", "tipo": "dia"}}
- "cuantas horas tengo el 15 de octubre" → {{"fecha": "2025-10-15", "tipo": "dia"}}
- "qué tengo el jueves" → {{"fecha": "(calcular próximo jueves)", "tipo": "dia"}}

MUY IMPORTANTE: 
- Devuelve SOLO el JSON, sin texto adicional, sin markdown, sin explicaciones
- Si pregunta por un día específico → tipo: "dia" y la fecha EXACTA de ese día
- Si pregunta por una semana → tipo: "semana" y el LUNES de esa semana

Respuesta:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un intérprete de fechas. Devuelves solo JSON válido, sin markdown ni texto adicional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        raw = response.choices[0].message.content.strip()
        
        # Limpiar posible markdown
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # Quitar primera línea
            raw = raw.rsplit("\n", 1)[0]  # Quitar última línea
            raw = raw.replace("```", "").strip()
        
        data = json.loads(raw)
        
        # ✅ VALIDACIÓN ADICIONAL: Asegurar que la fecha sea un lunes SOLO si tipo="semana"
        try:
            if data.get("tipo") == "semana":
                fecha_obj = datetime.fromisoformat(data["fecha"])
                # Si no es lunes (weekday != 0), calcular el lunes de esa semana
                if fecha_obj.weekday() != 0:
                    dias_hasta_lunes = fecha_obj.weekday()
                    lunes = fecha_obj - timedelta(days=dias_hasta_lunes)
                    data["fecha"] = lunes.strftime("%Y-%m-%d")
                    print(f"[DEBUG] 🔧 Ajustado a lunes: {data['fecha']}")
        except:
            pass
        
        return data
    
    except json.JSONDecodeError as e:
        print(f"[DEBUG] Error parseando JSON de GPT. Raw: {raw}")
        print(f"[DEBUG] Error: {e}")
        return None
    except Exception as e:
        print(f"[DEBUG] Error interpretando consulta: {e}")
        return None


def interpretar_con_gpt(texto):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")

    # Usar f-string pero con llaves cuádruples {{{{ para que se escapen correctamente
    prompt = f"""
Eres un asistente avanzado que traduce frases en lenguaje natural a una lista de comandos JSON 
para automatizar una web de imputación de horas laborales. 

📅 CONTEXTO TEMPORAL:
Hoy es {hoy} ({dia_semana}).

🎯 ACCIONES VÁLIDAS:
- seleccionar_fecha (requiere "fecha" en formato YYYY-MM-DD)
- volver
- seleccionar_proyecto (requiere "nombre")
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

2️⃣ PROYECTOS MÚLTIPLES:
   Si el usuario menciona varios proyectos en una frase:
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
   a) seleccionar_fecha (si aplica - SIEMPRE si menciona una semana/día específico diferente de HOY)
   b) iniciar_jornada (si se mencionó)
   c) seleccionar_proyecto (si aplica)
   d) imputar_horas_dia, imputar_horas_semana, eliminar_linea, borrar_todas_horas_dia, etc.
   e) finalizar_jornada (si se mencionó)
   f) guardar_linea o emitir_linea (SIEMPRE al final, OBLIGATORIO)
   
   ⚠️ CRÍTICO: NUNCA omitas guardar_linea/emitir_linea. Es OBLIGATORIO al final de cualquier imputación/modificación.
   ⚠️ IMPORTANTE: Si el usuario menciona "próxima semana", "esa semana", "el martes", etc., seleccionar_fecha es el PRIMER paso obligatorio.

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
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana de hoy)"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 8}}}},
  {{"accion": "guardar_linea"}}
]

Ejemplo 1b - Sin especificar fecha (asumir HOY):
Entrada: "Pon 3 horas en Estudio"
Salida:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "(lunes de la semana de hoy)"}}}},
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
        response = client.chat.completions.create(
            model="gpt-4o",  # 🚀 ACTUALIZADO: Modelo más potente para interpretación compleja
            messages=[
                {"role": "system", "content": "Eres un intérprete experto de lenguaje natural a comandos JSON estructurados. Procesas instrucciones complejas con alta precisión, manejando múltiples proyectos, fechas relativas y contextos ambiguos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0  # Mantener en 0 para máxima precisión y consistencia
        )

        raw = response.choices[0].message.content.strip()
        print(f"[DEBUG] 🧠 GPT generó: {raw}")
        
        # 🧹 Limpiar markdown si GPT-4o lo añade (```json ... ```)
        if raw.startswith("```"):
            # Quitar la primera línea (```json o ```)
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])  # Quitar primera y última línea
            raw = raw.strip()
            print(f"[DEBUG] 🧹 JSON limpio: {raw}")
        
        data = json.loads(raw)

        # Si devuelve un solo objeto, lo convertimos a lista
        if isinstance(data, dict):
            data = [data]

        # NO reordenar si hay múltiples proyectos intercalados
        # El prompt de GPT ya genera el orden correcto
        # data = sorted(data, key=lambda x: orden_correcto.index(
        #     x["accion"]) if x["accion"] in orden_correcto else 99)

        return data

    except Exception as e:
        return []



# ---------------------------------------------------------------------
# EJECUTAR ACCIÓN
# ---------------------------------------------------------------------
def ejecutar_accion(driver, wait, orden, contexto):
    """
    Ejecuta la acción recibida desde el modelo de IA.
    El parámetro `contexto` mantiene información temporal,
    como la fila del proyecto actualmente seleccionado.
    Devuelve el mensaje de respuesta natural.
    """
    accion = orden.get("accion")

    # 🕒 Iniciar jornada
    if accion == "iniciar_jornada":
        return iniciar_jornada(driver, wait)

    # 🕓 Finalizar jornada
    elif accion == "finalizar_jornada":
        return finalizar_jornada(driver, wait)

    # 📅 Seleccionar fecha
    elif accion == "seleccionar_fecha":
        try:
            fecha = datetime.fromisoformat(orden["parametros"]["fecha"])
            return seleccionar_fecha(driver, fecha)
        except Exception as e:
            return f"No he podido procesar la fecha: {e}"

    # 📂 Seleccionar proyecto
    elif accion == "seleccionar_proyecto":
        try:
            nombre = orden["parametros"].get("nombre")
            fila, mensaje = seleccionar_proyecto(driver, wait, nombre)
            
            if fila:
                # ✅ Proyecto encontrado o creado correctamente
                contexto["fila_actual"] = fila
                contexto["proyecto_actual"] = nombre
                return mensaje
            else:
                # ❌ Proyecto NO encontrado - DETENER ejecución
                contexto["fila_actual"] = None
                contexto["proyecto_actual"] = None
                contexto["error_critico"] = True  # Marcar error crítico
                return mensaje  # El mensaje ya viene con el error
                
        except Exception as e:
            return f"Error seleccionando proyecto: {e}"
        # 🗑️ Eliminar línea
# 🗑️ Eliminar línea
    elif accion == "eliminar_linea":
        try:
            nombre = orden["parametros"].get("nombre")
            resultado = eliminar_linea_proyecto(driver, wait, nombre)
            
            # Auto-guardar después de eliminar
            time.sleep(0.5)
            try:
                btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btGuardarLinea")))
                btn_guardar.click()
                time.sleep(1.5)
                return resultado + " y he guardado los cambios"
            except:
                return resultado + " (recuerda guardar los cambios)"
                
        except Exception as e:
            return f"Error eliminando línea: {e}"

    # 🗑️ Borrar todas las horas de un día
    elif accion == "borrar_todas_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            
            # Si GPT devuelve una fecha ISO → convertir a nombre de día
            try:
                fecha_obj = datetime.fromisoformat(dia_param)
                dia = fecha_obj.strftime("%A").lower()
                dias_map = {
                    "monday": "lunes",
                    "tuesday": "martes",
                    "wednesday": "miércoles",
                    "thursday": "jueves",
                    "friday": "viernes"
                }
                dia = dias_map.get(dia, dia)
            except Exception:
                dia = dia_param.lower()
            
            return borrar_todas_horas_dia(driver, wait, dia)
        
        except Exception as e:
            return f"Error al borrar horas: {e}"

    # ⏱️ Imputar horas del día
    elif accion == "imputar_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            horas = float(orden["parametros"].get("horas", 0))
            modo = orden["parametros"].get("modo", "sumar")  # ← NUEVO
            fila = contexto.get("fila_actual")
            proyecto = contexto.get("proyecto_actual", "Desconocido")

            if not fila:
                return "Necesito que primero selecciones un proyecto antes de imputar horas"

            # Si GPT devuelve una fecha ISO → convertir a nombre de día
            try:
                fecha_obj = datetime.fromisoformat(dia_param)
                dia = fecha_obj.strftime("%A").lower()
                dias_map = {
                    "monday": "lunes",
                    "tuesday": "martes",
                    "wednesday": "miércoles",
                    "thursday": "jueves",
                    "friday": "viernes"
                }
                dia = dias_map.get(dia, dia)
            except Exception:
                dia = dia_param.lower()

            return imputar_horas_dia(driver, wait, dia, horas, fila, proyecto, modo)  # ← ACTUALIZADO

        except Exception as e:
            return f"Error al imputar horas: {e}"

    # ⏱️ Imputar horas semanales
    elif accion == "imputar_horas_semana":
       
        proyecto = contexto.get("proyecto_actual")
        if not proyecto:
            return "❌ No sé en qué proyecto quieres imputar. Dímelo, por favor."

        fila = contexto.get("fila_actual")
        if not fila:
            return f"❌ No he podido seleccionar el proyecto '{proyecto}'. ¿Estás en la pantalla de imputación?"

        return imputar_horas_semana(driver, wait, fila, nombre_proyecto=proyecto)

    # 💾 Guardar línea
    elif accion == "guardar_linea":
        return guardar_linea(driver, wait)

    # 📤 Emitir línea
    elif accion == "emitir_linea":
        return emitir_linea(driver, wait)

    # ↩️ Volver a inicio
    elif accion == "volver":
        return volver_inicio(driver)

    # ❓ Desconocido
    else:
        return "No he entendido esa instrucción"



# ---------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------
def main():
    service = ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 15)

    # 🚀 Login automático al inicio
    hacer_login(driver, wait)

    print("\n" + "="*60)
    print("👋 ¡Hola! Soy tu asistente de imputación de horas")
    print("="*60)
    print("\nYa he iniciado sesión en el sistema por ti.")
    print("\nPuedes pedirme cosas como:")
    print("  • 'Imputa 8 horas en Desarrollo hoy'")
    print("  • 'Abre el proyecto Estudio y pon toda la semana'")
    print("  • 'Añade 2.5 horas en Dirección el lunes y emítelo'")
    print("  • 'Inicia la jornada'")
    print("\nEscribe 'salir' cuando quieras terminar.\n")
    print("="*60 + "\n")

    try:
        contexto = {"fila_actual": None, "proyecto_actual": None}

        while True:
            texto = input("💬 Tú: ")
            if texto.lower() in ["salir", "exit", "quit"]:
                print("\n👋 ¡Hasta pronto! Cerrando el navegador...")
                break

            # Clasificar el tipo de mensaje
            tipo_mensaje = clasificar_mensaje(texto)
            
            if tipo_mensaje == "conversacion":
                # Responder con conversación natural
                respuesta = responder_conversacion(texto)
                print(f"\n🤖 Asistente: {respuesta}\n")
                continue
            
            # Si es una consulta, procesar la información
            if tipo_mensaje == "consulta":
                consulta_info = interpretar_consulta(texto)
                
                if consulta_info:
                    try:
                        fecha = datetime.fromisoformat(consulta_info["fecha"])
                        
                        if consulta_info.get("tipo") == "dia":
                            # Consulta de un día específico
                            info_bruta = consultar_dia(driver, wait, fecha)
                            resumen_natural = generar_resumen_natural(info_bruta, texto)
                            print(f"\n🤖 Asistente:\n{resumen_natural}\n")
                        elif consulta_info.get("tipo") == "semana":
                            # Consulta de una semana completa
                            info_bruta = consultar_semana(driver, wait, fecha)
                            resumen_natural = generar_resumen_natural(info_bruta, texto)
                            print(f"\n🤖 Asistente:\n{resumen_natural}\n")
                        else:
                            print("\n🤔 No he entendido si preguntas por un día o una semana.\n")
                    except Exception as e:
                        print(f"\n⚠️ No he podido consultar: {e}\n")
                else:
                    print("\n🤔 No he entendido qué quieres consultar. ¿Podrías ser más específico?\n")
                continue
            
            # Si es un comando, interpretarlo y ejecutarlo
            ordenes = interpretar_con_gpt(texto)
            
            if not ordenes:
                print("🤔 No he entendido qué quieres que haga. ¿Podrías reformularlo?\n")
                continue

            # 🔄 Reordenar: siempre primero la fecha, luego el resto
            ordenes = sorted(ordenes, key=lambda o: 0 if o["accion"] == "seleccionar_fecha" else 1)

            # Ejecutar acciones y acumular respuestas
            respuestas = []
            i = 0
            while i < len(ordenes):
                orden = ordenes[i]
                mensaje = ejecutar_accion(driver, wait, orden, contexto)
                if mensaje:
                    respuestas.append(mensaje)
                i += 1

            # Generar respuesta natural con GPT
            if respuestas:
                respuesta_natural = generar_respuesta_natural(respuestas, texto)
                print(f"\n🤖 Asistente: {respuesta_natural}\n")

    finally:
        driver.quit()
        print("\n🔚 Navegador cerrado. ¡Que tengas un buen día!\n")


# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
