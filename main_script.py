from selenium import webdriver
from selenium.webdriver.common.by import By
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

def hacer_login(driver, wait):
    """Realiza el login en la intranet."""
    driver.get(LOGIN_URL)
    usr = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, USERNAME_SELECTOR)))
    usr.clear()
    usr.send_keys(USERNAME)
    pwd = driver.find_element(By.CSS_SELECTOR, PASSWORD_SELECTOR)
    pwd.clear()
    pwd.send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, SUBMIT_SELECTOR).click()
    time.sleep(3)

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
        
        # 🔍 Buscar si el proyecto ya existe - MEJORADO para selects disabled
        # Buscar TODOS los selects de subproyecto (incluso disabled)
        selects = driver.find_elements(By.CSS_SELECTOR, "select[name*='subproyecto']")
        
        # Si no encuentra por name, intentar por id
        if not selects:
            selects = driver.find_elements(By.CSS_SELECTOR, "select[id*='subproyecto']")
        
        print(f"[DEBUG] 🔍 Buscando proyecto '{nombre_proyecto}' en {len(selects)} líneas existentes...")
        
        for idx, sel in enumerate(selects):
            # Obtener el atributo 'title' que contiene el nombre completo del proyecto
            title = sel.get_attribute("title") or ""
            
            # También buscar la opción seleccionada usando JavaScript (funciona con disabled)
            try:
                texto_selected = driver.execute_script("""
                    var select = arguments[0];
                    var selectedOption = select.options[select.selectedIndex];
                    return selectedOption ? selectedOption.text : '';
                """, sel)
            except:
                texto_selected = ""
            
            # Combinar ambos textos
            texto_completo = f"{title} {texto_selected}".lower()
            print(f"[DEBUG]   Línea {idx+1}: '{title}' | Selected: '{texto_selected}'")
            
            # Comparar normalizado
            if normalizar(nombre_proyecto) in normalizar(texto_completo):
                # Obtenemos la fila que contiene este select
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                time.sleep(0.3)
                print(f"[DEBUG] ✅ ¡Encontrado! Reutilizando línea {idx+1}")
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
        xpath = (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúü'), "
            f"'{normalizar(nombre_proyecto)}')]"
        )

        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
        elemento.click()
        time.sleep(1)

        return fila, f"He abierto el proyecto '{nombre_proyecto}'"

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




def imputar_horas_dia(driver, wait, dia, horas, fila, nombre_proyecto=None):
    """
    Imputa una cantidad específica de horas en un día concreto (lunes a viernes)
    dentro de la fila (<tr>) del proyecto correspondiente.
    Si ya hay horas, las suma.
    """
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




def guardar_linea(driver, wait):
    """Pulsa el botón 'Guardar' tras imputar horas."""
    try:
        btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btGuardarLinea")))
        btn_guardar.click()
        time.sleep(1.5)
        return "He guardado los cambios"
    except Exception as e:
        return f"No he podido guardar: {e}"

def emitir_linea(driver, wait):
    """Pulsa el botón 'Emitir' tras imputar horas."""
    try:
        btn_emitir = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btEmitir")))
        btn_emitir.click()
        time.sleep(1.5)
        return "He emitido las horas correctamente"
    except Exception as e:
        return f"No he podido emitir: {e}"


def iniciar_jornada(driver, wait):
    """
    Pulsa el botón 'Inicio jornada' si está disponible.
    Si el botón no está o ya se ha pulsado, lo ignora.
    """
    try:
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
# INTERPRETACIÓN REAL CON GPT
# ---------------------------------------------------------------------
def clasificar_mensaje(texto):
    """
    Clasifica si el mensaje del usuario es:
    - 'comando': requiere ejecutar acciones de imputación
    - 'conversacion': saludo, pregunta general, etc.
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""Clasifica el siguiente mensaje del usuario en una de estas categorías:

1. "comando" - Si pide realizar acciones de imputación de horas (imputar, añadir, quitar, seleccionar proyecto, iniciar/finalizar jornada, guardar, emitir, etc.)
2. "conversacion" - Si es un saludo, pregunta general, consulta de información, charla casual, etc.

Mensaje: "{texto}"

Responde SOLO con una palabra: "comando" o "conversacion"
"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un clasificador de mensajes. Responde solo con 'comando' o 'conversacion'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=10
        )
        
        clasificacion = response.choices[0].message.content.strip().lower()
        return clasificacion
    
    except Exception as e:
        # Por defecto, asumimos que es conversación
        return "conversacion"


def responder_conversacion(texto):
    """
    Usa GPT para responder a saludos, preguntas generales, etc.
    """
    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    
    prompt = f"""Eres un asistente virtual amigable especializado en gestión de imputación de horas laborales.

Hoy es {hoy} ({dia_semana}).

El usuario te dice: "{texto}"

Responde de forma natural, amigable y concisa. Si te pregunta sobre algo externo (noticias, clima, información general), responde normalmente.
Si es un saludo, preséntate brevemente como el asistente de imputación de horas.

Respuesta:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un asistente virtual amigable de imputación de horas que también puede conversar sobre temas generales."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return "Disculpa, he tenido un problema al procesar tu mensaje. ¿Podrías intentarlo de nuevo?"


def interpretar_con_gpt(texto):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")

    prompt = f"""
Eres un asistente que traduce frases en una lista de comandos JSON para automatizar
una web de imputación de horas. Hoy es {hoy} ({dia_semana}).

Acciones válidas:
- seleccionar_fecha (requiere "fecha" en formato YYYY-MM-DD)
- volver
- seleccionar_proyecto (requiere "nombre")
- imputar_horas_dia (requiere "dia" y "horas")
- imputar_horas_semana
- iniciar_jornada
- finalizar_jornada
- guardar_linea
- emitir_linea

Reglas:
1️⃣ Siempre usa el año 2025 aunque el usuario no lo diga.
2️⃣ Si el usuario dice "hoy", la fecha es {hoy}.
3️⃣ Si el usuario dice "ayer" o "mañana", calcula la fecha correspondiente a partir de {hoy}.
5️⃣ Si el usuario menciona varios proyectos y horas en la misma frase (por ejemplo:
    "3.5 en Desarrollo y 2 en Dirección el lunes"),
    genera varias acciones intercaladas en este orden:
    seleccionar_proyecto → imputar_horas_dia → seleccionar_proyecto → imputar_horas_dia.
    Así cada imputación se asocia al proyecto anterior.
6️⃣ Si menciona "expide", "emite", "envía", "envíalo", "expídelo" o similares,
    añade una acción {{"accion": "emitir_linea"}} al final.
7️⃣ Si no menciona ninguna de esas palabras, añade {{"accion": "guardar_linea"}} después de imputar horas.
8️⃣ Si dice "quita", "resta", "borra" o "elimina", las horas deben ser NEGATIVAS (por ejemplo -2).
9️⃣ Si dice "suma", "añade", "agrega" o "pon", las horas son POSITIVAS.
🔟 Si el usuario no menciona día, asume el día actual ({hoy}).

3️⃣ Si la frase incluye varias acciones, ordénalas SIEMPRE así:
   - seleccionar_fecha primero (si procede)
   - luego seleccionar_proyecto
   - luego imputar_horas_dia o imputar_horas_semana
   - finalmente guardar_linea o emitir_linea (si aplica)

❗ Solo incluye {{"accion": "iniciar_jornada"}} si el usuario dice explícitamente
   frases como "inicia jornada", "empieza jornada", "comienza el día" o similares.

4️⃣ Devuelve SOLO un JSON válido (nada de texto explicativo ni comentarios).
5️⃣ Si algo no se entiende, omítelo.

Ejemplo correcto:
[
  {{"accion": "seleccionar_fecha", "parametros": {{"fecha": "{hoy}"}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Desarrollo"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 2}}}},
  {{"accion": "seleccionar_proyecto", "parametros": {{"nombre": "Estudio"}}}},
  {{"accion": "imputar_horas_dia", "parametros": {{"dia": "{hoy}", "horas": 3}}}},
  {{"accion": "guardar_linea"}}
]

Frase del usuario: "{texto}"
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Eres un traductor de lenguaje natural a comandos JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)

        # Si devuelve un solo objeto, lo convertimos a lista
        if isinstance(data, dict):
            data = [data]

        # 🧠 Reordenar acciones: fecha → proyecto → imputación
        orden_correcto = ["seleccionar_fecha", "seleccionar_proyecto",
                          "imputar_horas_dia", "imputar_horas_semana", "volver"]
        data = sorted(data, key=lambda x: orden_correcto.index(
            x["accion"]) if x["accion"] in orden_correcto else 99)

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
                contexto["fila_actual"] = fila
                contexto["proyecto_actual"] = nombre
            return mensaje
        except Exception as e:
            return f"Error seleccionando proyecto: {e}"

    # ⏱️ Imputar horas del día
    elif accion == "imputar_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            horas = float(orden["parametros"].get("horas", 0))
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

            return imputar_horas_dia(driver, wait, dia, horas, fila, proyecto)

        except Exception as e:
            return f"Error al imputar horas: {e}"

    # ⏱️ Imputar horas semanales
    elif accion == "imputar_horas_semana":
        fila = contexto.get("fila_actual")
        proyecto = contexto.get("proyecto_actual", "Desconocido")

        if not fila:
            return "Necesito que primero selecciones un proyecto antes de imputar la semana"

        return imputar_horas_semana(driver, wait, fila, proyecto)

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
