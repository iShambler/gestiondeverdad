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
    print("✅ Login completado.")

def volver_inicio(driver):
    """Pulsa el botón 'Volver' para regresar a la pantalla principal tras login."""
    try:
        btn_volver = driver.find_element(By.CSS_SELECTOR, VOLVER_SELECTOR)
        btn_volver.click()
        time.sleep(2)
        print("↩️ Volviendo a la pantalla principal...")
    except Exception as e:
        print(f"⚠️ No se pudo pulsar el botón Volver: {e}")

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
    print(f"📅 Seleccionando {dia_seleccionado}/{fecha_obj.month}/{fecha_obj.year}")

    try:
        driver.find_element(By.XPATH, f"//a[text()='{dia_seleccionado}']").click()
        print(f"✅ Fecha seleccionada correctamente: {fecha_obj.strftime('%d/%m/%Y')}")
    except Exception as e:
        print(f"⚠️ No se pudo seleccionar el día {dia_seleccionado}: {e}")


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
        # 🔍 Buscar si el proyecto ya existe
        selects = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
        for sel in selects:
            combinado = (sel.get_attribute("title") or sel.text or "").lower()
            if normalizar(nombre_proyecto) in normalizar(combinado):
                # Obtenemos la fila que contiene este select
                fila = sel.find_element(By.XPATH, "./ancestor::tr")
                print(f"🧩 Proyecto '{nombre_proyecto}' ya existe, reutilizando su fila.")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", fila)
                time.sleep(0.3)
                return fila  # ✅ devolvemos la fila del proyecto

        # 🆕 Si no existe → añadimos nueva línea
        print("🆕 Añadiendo nueva línea de imputación...")
        btn_nueva_linea = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btNuevaLinea")))
        btn_nueva_linea.click()
        time.sleep(1)

        # 🔢 Detectar el nuevo <select> (último en la lista)
        selects_actualizados = driver.find_elements(By.CSS_SELECTOR, "select[id^='listaEmpleadoHoras'][id$='.subproyecto']")
        nuevo_select = selects_actualizados[-1]
        fila = nuevo_select.find_element(By.XPATH, "./ancestor::tr")

        # 📌 Buscar el botón “»” correspondiente dentro de la misma fila
        try:
            btn_cambiar = fila.find_element(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
        except Exception:
            botones = driver.find_elements(By.CSS_SELECTOR, "input[id^='btCambiarSubproyecto']")
            btn_cambiar = botones[-1] if botones else None

        if btn_cambiar:
            print("🔍 Abriendo buscador de proyectos...")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_cambiar)
            btn_cambiar.click()
        else:
            print("⚠️ No se encontró el botón '»' para la nueva línea.")
            return None

        # 3️⃣ Esperar a que aparezca el campo de búsqueda
        print("⌛ Esperando campo de búsqueda...")
        campo_buscar = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#textoBusqueda")))
        campo_buscar.clear()
        campo_buscar.send_keys(nombre_proyecto)

        # 4️⃣ Pulsar en el botón "Buscar"
        print(f"🔎 Buscando proyecto: {nombre_proyecto}")
        btn_buscar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#buscar")))
        btn_buscar.click()
        time.sleep(1.5)

        # 5️⃣ Expandir árbol de resultados
        print("🌳 Expandiendo árbol de resultados...")
        driver.execute_script("""
            var tree = $('#treeTipologia');
            if (tree && tree.jstree) { tree.jstree('open_all'); }
        """)
        time.sleep(1)

        # 6️⃣ Buscar y seleccionar el proyecto
        print("📂 Seleccionando el proyecto en el árbol...")
        xpath = (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÜ', 'abcdefghijklmnopqrstuvwxyzáéíóúü'), "
            f"'{normalizar(nombre_proyecto)}')]"
        )

        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
        elemento.click()
        time.sleep(1)

        print(f"✅ Proyecto '{nombre_proyecto}' seleccionado correctamente.")
        return fila  # ✅ devolvemos la fila asociada al proyecto

    except Exception as e:
        print(f"⚠️ No se pudo seleccionar el proyecto '{nombre_proyecto}': {e}")
        return None



def imputar_horas_semana(driver, wait, fila, nombre_proyecto=None):
    """
    Imputa las horas de lunes a viernes dentro de la fila (<tr>) del proyecto.
    Lunes a jueves → 8.5 horas
    Viernes → 6.5 horas
    Si un campo no está disponible (festivo, deshabilitado, etc.), lo omite.
    """
    print(f"🕒 Imputando horas semanales "
          f"{'(proyecto ' + nombre_proyecto + ')' if nombre_proyecto else ''}...")

    horas_semana = {
        "h1": "8.5",
        "h2": "8.5",
        "h3": "8.5",
        "h4": "8.5",
        "h5": "6.5",
    }

    try:
        for dia, valor in horas_semana.items():
            try:
                campo = fila.find_element(By.CSS_SELECTOR, f"input[id$='.{dia}']")
                if campo.is_enabled():
                    campo.clear()
                    campo.send_keys(valor)
                    print(f"✅ {dia.upper()} → {valor} horas imputadas correctamente.")
                    time.sleep(0.2)
                else:
                    print(f"⚠️ {dia.upper()} no editable (posible festivo o bloqueo).")
            except Exception:
                print(f"⚠️ Campo para {dia.upper()} no encontrado (omitido).")

        print(f"✅ Imputación semanal completada "
              f"{'(proyecto ' + nombre_proyecto + ')' if nombre_proyecto else ''}.\n")

    except Exception as e:
        print(f"❌ Error imputando horas semanales en "
              f"{'(proyecto ' + nombre_proyecto + ')' if nombre_proyecto else ''}: {e}")




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
        print(f"⚠️ Día no reconocido: {dia}")
        return

    print(f"🕓 Imputando {horas}h el {dia} "
          f"{'(proyecto ' + nombre_proyecto + ')' if nombre_proyecto else ''}...")

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
            print(f"✅ {dia.capitalize()} → {nuevas_horas} horas añadidas (total {total}) "
                  f"en {nombre_proyecto or 'proyecto'}.")
        else:
            print(f"⚠️ Campo de {dia.capitalize()} no editable en "
                  f"{nombre_proyecto or 'proyecto'} (posible bloqueo).")

    except Exception as e:
        print(f"⚠️ No se pudo imputar horas en {dia} "
              f"({nombre_proyecto or 'proyecto'}): {e}")




def guardar_linea(driver, wait):
    """Pulsa el botón 'Guardar' tras imputar horas."""
    try:
        btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btGuardarLinea")))
        btn_guardar.click()
        time.sleep(1.5)
        print("💾 Línea guardada correctamente.")
    except Exception as e:
        print(f"⚠️ No se pudo pulsar el botón Guardar: {e}")

def emitir_linea(driver, wait):
    """Pulsa el botón 'Emitir' tras imputar horas."""
    try:
        btn_emitir = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btEmitir")))
        btn_emitir.click()
        time.sleep(1.5)
        print("📤 Línea emitida correctamente.")
    except Exception as e:
        print(f"⚠️ No se pudo pulsar el botón Emitir: {e}")


def iniciar_jornada(driver, wait):
    """
    Pulsa el botón 'Inicio jornada' si está disponible.
    Si el botón no está o ya se ha pulsado, lo ignora.
    """
    print("🕒 Intentando iniciar jornada...")

    try:
        btn_inicio = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#botonInicioJornada")))

        if btn_inicio.is_enabled():
            btn_inicio.click()
            time.sleep(2)
            print("✅ Jornada iniciada correctamente.")
        else:
            print("⚠️ El botón de inicio de jornada no está habilitado (posible jornada ya iniciada).")

    except Exception as e:
        print(f"⚠️ No se pudo iniciar la jornada: {e}")

def finalizar_jornada(driver, wait):
    """
    Pulsa el botón 'Finalizar jornada' si está disponible.
    Si el botón no está o ya se ha pulsado, lo ignora.
    """
    print("🕓 Intentando finalizar jornada...")

    try:
        btn_fin = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#botonFinJornada")))

        if btn_fin.is_enabled():
            btn_fin.click()
            time.sleep(2)
            print("✅ Jornada finalizada correctamente.")
        else:
            print("⚠️ El botón de finalizar jornada no está habilitado (posible jornada ya cerrada).")

    except Exception as e:
        print(f"⚠️ No se pudo finalizar la jornada: {e}")




# ---------------------------------------------------------------------
# INTERPRETACIÓN REAL CON GPT
# ---------------------------------------------------------------------
def interpretar_con_gpt(texto):

    hoy = datetime.now().strftime("%Y-%m-%d")
    dia_semana = datetime.now().strftime("%A")
    """
    Traduce la frase del usuario en una lista de comandos JSON para automatizar
    la imputación de horas en la intranet.

    Acciones posibles:
    - seleccionar_fecha (requiere 'fecha' en formato YYYY-MM-DD)
    - volver
    - seleccionar_proyecto (requiere 'nombre')
    - imputar_horas_semana
    - iniciar_jornada

    Reglas:
    1. Siempre asume que el año es 2025, aunque el usuario no lo diga.
    2. Si el usuario dice "esta semana", "la próxima", etc., genera la fecha del lunes de esa semana en 2025.
    3. Si el usuario mezcla acciones (como "imputa horas en el proyecto X la semana del 7 de octubre"),
       **primero debe ir la fecha**, luego el proyecto, y al final la imputación.
    4. Devuelve SOLO una lista JSON válida (sin texto adicional).
    5. Si no se puede interpretar algo, ignóralo.
    """

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
        print("⚠️ Error interpretando respuesta del modelo:", e)
        return []



# ---------------------------------------------------------------------
# EJECUTAR ACCIÓN
# ---------------------------------------------------------------------
def ejecutar_accion(driver, wait, orden, contexto):
    """
    Ejecuta la acción recibida desde el modelo de IA.
    El parámetro `contexto` mantiene información temporal,
    como la fila del proyecto actualmente seleccionado.
    """
    accion = orden.get("accion")

    # 🕒 Iniciar jornada
    if accion == "iniciar_jornada":
        iniciar_jornada(driver, wait)

    # 🕓 Finalizar jornada
    elif accion == "finalizar_jornada":
        finalizar_jornada(driver, wait)

    # 📅 Seleccionar fecha
    elif accion == "seleccionar_fecha":
        try:
            fecha = datetime.fromisoformat(orden["parametros"]["fecha"])
            seleccionar_fecha(driver, fecha)
        except Exception as e:
            print("❌ No se pudo procesar la fecha:", e)

    # 📂 Seleccionar proyecto
    elif accion == "seleccionar_proyecto":
        try:
            nombre = orden["parametros"].get("nombre")
            fila = seleccionar_proyecto(driver, wait, nombre)
            if fila:
                contexto["fila_actual"] = fila
                contexto["proyecto_actual"] = nombre
            else:
                print("⚠️ No se pudo obtener la fila del proyecto.")
        except Exception as e:
            print(f"⚠️ Error seleccionando proyecto: {e}")

    # ⏱️ Imputar horas del día
    elif accion == "imputar_horas_dia":
        try:
            dia_param = orden["parametros"].get("dia")
            horas = float(orden["parametros"].get("horas", 0))
            fila = contexto.get("fila_actual")
            proyecto = contexto.get("proyecto_actual", "Desconocido")

            if not fila:
                print("⚠️ No hay proyecto seleccionado para imputar horas.")
                return

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

            imputar_horas_dia(driver, wait, dia, horas, fila, proyecto)

        except Exception as e:
            print(f"❌ Error al imputar horas del día: {e}")

    # ⏱️ Imputar horas semanales
    elif accion == "imputar_horas_semana":
        fila = contexto.get("fila_actual")
        proyecto = contexto.get("proyecto_actual", "Desconocido")

        if not fila:
            print("⚠️ No hay proyecto seleccionado para imputar la semana.")
            return

        imputar_horas_semana(driver, wait, fila, proyecto)

    # 💾 Guardar línea
    elif accion == "guardar_linea":
        guardar_linea(driver, wait)

    # 📤 Emitir línea
    elif accion == "emitir_linea":
        emitir_linea(driver, wait)

    # ↩️ Volver a inicio
    elif accion == "volver":
        volver_inicio(driver)

    # ❓ Desconocido
    else:
        print("🤔 No entiendo la instrucción o no está implementada todavía.")



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

    print("\n🧠 Asistente con IA (OpenAI) para imputación de horas")
    print("Ya estás logueado en el sistema.")
    print("Puedes decir cosas como:")
    print(" - 'selecciona la semana del 7 de octubre'")
    print(" - 'abre el proyecto Estudio/Investigación de tecnología o proyecto cliente'")
    print(" - 'vuelve a la pantalla principal'")
    print("Escribe 'salir' para terminar.\n")

    try:
        contexto = {"fila_actual": None, "proyecto_actual": None}

        while True:
            texto = input("🗣️  > ")
            if texto.lower() in ["salir", "exit", "quit"]:
                break

            ordenes = interpretar_con_gpt(texto)
            print("🧾 Interpretación:", ordenes)

            # 🔄 Reordenar: siempre primero la fecha, luego el resto
            ordenes = sorted(ordenes, key=lambda o: 0 if o["accion"] == "seleccionar_fecha" else 1)

            # 🧠 Nueva ejecución agrupada: proyecto + horas
            i = 0
            while i < len(ordenes):
                orden = ordenes[i]
                accion = orden.get("accion")

                # 👉 Si es un proyecto, lo seleccionamos y verificamos si la siguiente acción son horas
                if accion == "seleccionar_proyecto":
                    nombre = orden["parametros"].get("nombre")
                    linea_index = seleccionar_proyecto(driver, wait, nombre)
                    contexto["fila_actual"] = linea_index
                    contexto["proyecto_actual"] = nombre

                    # Si la siguiente acción es imputar horas, ejecutarla inmediatamente
                    if i + 1 < len(ordenes) and ordenes[i + 1]["accion"] == "imputar_horas_dia":
                        siguiente = ordenes[i + 1]
                        dia_param = siguiente["parametros"].get("dia")
                        horas = float(siguiente["parametros"].get("horas"))

                        # convertir la fecha ISO en nombre del día
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

                        imputar_horas_dia(driver, wait, dia, horas, linea_index, nombre)
                        i += 1  # saltar la imputación ya procesada

                # 👉 Si no es seleccionar_proyecto, ejecutar normalmente
                else:
                    ejecutar_accion(driver, wait, orden, contexto)

                i += 1

    finally:
        driver.quit()
        print("🔚 Navegador cerrado.")


# ---------------------------------------------------------------------
if __name__ == "__main__":
    main()
