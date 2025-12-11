"""
Sistema de desambiguación interactiva para proyectos duplicados.
Permite al usuario seleccionar el proyecto correcto mediante conversación natural.
"""

import unicodedata
from difflib import SequenceMatcher


def normalizar(texto):
    """Normaliza acentos y minúsculas para comparaciones flexibles."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )


def similitud(texto1, texto2):
    """
    Calcula la similitud entre dos textos (0.0 a 1.0).
    Usa SequenceMatcher para comparación fuzzy.
    """
    return SequenceMatcher(None, normalizar(texto1), normalizar(texto2)).ratio()


def buscar_proyectos_duplicados(driver, wait, nombre_proyecto):
    """
    Busca todos los proyectos que coincidan con el nombre dado
    y devuelve una lista con sus nodos padre.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        nombre_proyecto: Nombre del proyecto a buscar
        
    Returns:
        list: Lista de diccionarios con información de cada coincidencia:
              [
                  {
                      "proyecto": "Desarrollo",
                      "nodo_padre": "Departamento Desarrollo e IDI",
                      "path_completo": "Arelance - Departamento Desarrollo e IDI - Desarrollo",
                      "elemento": WebElement
                  },
                  ...
              ]
    """
    from selenium.webdriver.common.by import By
    
    try:
        print(f"[DEBUG] 🔍 Buscando todas las coincidencias de '{nombre_proyecto}'...")
        
        # Expandir árbol completo
        driver.execute_script("""
            var tree = $('#treeTipologia');
            if (tree && tree.jstree) { tree.jstree('open_all'); }
        """)
        
        import time
        time.sleep(1)
        
        # Buscar todos los proyectos que coincidan
        xpath = (
            f"//li[@rel='subproyectos']//a[contains(translate(normalize-space(.), "
            f"'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
            f"'{nombre_proyecto.lower()}')]"
        )
        
        elementos = driver.find_elements(By.XPATH, xpath)
        print(f"[DEBUG] 📊 Encontradas {len(elementos)} coincidencias")
        
        if not elementos:
            return []
        
        coincidencias = []
        
        for idx, elemento in enumerate(elementos, 1):
            try:
                # Obtener el nombre del proyecto
                nombre_elem = elemento.text.strip()
                
                # Obtener el nodo padre (elemento <li> padre)
                li_proyecto = elemento.find_element(By.XPATH, "./ancestor::li[@rel='subproyectos'][1]")
                li_padre = li_proyecto.find_element(By.XPATH, "./ancestor::li[1]")
                
                # Obtener el nombre del nodo padre
                try:
                    link_padre = li_padre.find_element(By.XPATH, "./a")
                    nodo_padre = link_padre.text.strip()
                except:
                    nodo_padre = "Desconocido"
                
                # Construir path completo navegando hacia arriba
                path_partes = []
                current_li = li_proyecto
                
                while True:
                    try:
                        parent_li = current_li.find_element(By.XPATH, "./parent::ul/parent::li")
                        parent_link = parent_li.find_element(By.XPATH, "./a")
                        parent_name = parent_link.text.strip()
                        
                        if parent_name and parent_name != nombre_elem:
                            path_partes.insert(0, parent_name)
                        
                        current_li = parent_li
                    except:
                        break
                
                path_partes.append(nombre_elem)
                path_completo = " → ".join(path_partes)
                
                print(f"[DEBUG]   {idx}. {path_completo}")
                
                coincidencias.append({
                    "proyecto": nombre_elem,
                    "nodo_padre": nodo_padre,
                    "path_completo": path_completo,
                    "elemento": elemento
                })
                
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error procesando elemento {idx}: {e}")
                continue
        
        return coincidencias
        
    except Exception as e:
        print(f"[DEBUG] ❌ Error buscando proyectos duplicados: {e}")
        return []


def encontrar_mejor_coincidencia_nodo(nodo_respuesta, coincidencias):
    """
    Encuentra la mejor coincidencia de nodo padre usando búsqueda fuzzy.
    
    Args:
        nodo_respuesta: Texto de respuesta del usuario (ej: "NeoLyfe", "Comercial")
        coincidencias: Lista de coincidencias de buscar_proyectos_duplicados()
        
    Returns:
        dict: Mejor coincidencia encontrada o None
    """
    if not coincidencias:
        return None
    
    mejor_coincidencia = None
    mejor_similitud = 0.0
    
    for coincidencia in coincidencias:
        # Calcular similitud con el nodo padre
        sim_nodo = similitud(nodo_respuesta, coincidencia["nodo_padre"])
        
        # También calcular similitud con el path completo
        sim_path = similitud(nodo_respuesta, coincidencia["path_completo"])
        
        # Tomar la mejor de las dos
        sim_maxima = max(sim_nodo, sim_path)
        
        print(f"[DEBUG]   Similitud '{nodo_respuesta}' vs '{coincidencia['nodo_padre']}': {sim_nodo:.2f}")
        print(f"[DEBUG]   Similitud '{nodo_respuesta}' vs path: {sim_path:.2f}")
        
        if sim_maxima > mejor_similitud:
            mejor_similitud = sim_maxima
            mejor_coincidencia = coincidencia
    
    # Umbral mínimo de similitud: 0.4 (40%)
    if mejor_similitud >= 0.4:
        print(f"[DEBUG] ✅ Mejor coincidencia: '{mejor_coincidencia['nodo_padre']}' (similitud: {mejor_similitud:.2f})")
        return mejor_coincidencia
    else:
        print(f"[DEBUG] ❌ No hay coincidencias suficientemente buenas (máxima similitud: {mejor_similitud:.2f})")
        return None


def generar_mensaje_desambiguacion(nombre_proyecto, coincidencias, canal="webapp"):
    """
    Genera un mensaje preguntando al usuario cuál proyecto quiere.
    
    Args:
        nombre_proyecto: Nombre del proyecto buscado
        coincidencias: Lista de coincidencias
        canal: Canal de comunicación (webapp, slack, whatsapp)
        
    Returns:
        str: Mensaje formateado para el usuario
    """
    if len(coincidencias) == 0:
        return f"❌ No he encontrado ningún proyecto llamado '{nombre_proyecto}'"
    
    if len(coincidencias) == 1:
        return None  # No hay ambigüedad
    
    # 🆕 Detectar si son proyectos existentes (tienen horas) o del sistema
    son_existentes = all(coin.get('total_horas') is not None for coin in coincidencias)
    
    # Formato según el canal
    if canal == "slack":
        if son_existentes:
            mensaje = f"✅ *Ya tienes {len(coincidencias)} proyectos con horas:*\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                horas = coin.get('total_horas', 0)
                mensaje += f"{idx}. `{coin['path_completo']}` - *{horas}h*\n"
            mensaje += f"\n💬 *¿En cuál quieres añadir horas?*\n"
            mensaje += f"• Responde con el *número* o *nombre del departamento*\n"
            mensaje += f"• Escribe *'ninguno'* o *'otro'* si quieres un proyecto diferente\n"
            mensaje += f"• Escribe *'cancelar'* para abandonar"
        else:
            mensaje = f"🤔 He encontrado *{len(coincidencias)}* proyectos llamados *'{nombre_proyecto}'*:\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                mensaje += f"{idx}. `{coin['path_completo']}`\n"
            mensaje += f"\n💬 *¿En cuál quieres imputar?*\n"
            mensaje += f"• Responde con el *número* o *nombre del departamento*\n"
            mensaje += f"• Escribe *'ninguno'* o *'otro'* si quieres un proyecto diferente\n"
            mensaje += f"• Escribe *'cancelar'* para abandonar"
    
    elif canal == "whatsapp":
        if son_existentes:
            mensaje = f"✅ *Ya tienes {len(coincidencias)} proyectos con horas:*\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                horas = coin.get('total_horas', 0)
                mensaje += f"{idx}. {coin['path_completo']} - *{horas}h*\n"
            mensaje += f"\n💬 *¿En cuál quieres añadir horas?*\n"
            mensaje += f"• Número o nombre del departamento\n"
            mensaje += f"• 'ninguno' o 'otro' para buscar diferente\n"
            mensaje += f"• 'cancelar' para salir"
        else:
            mensaje = f"🤔 *He encontrado {len(coincidencias)} proyectos llamados '{nombre_proyecto}'*:\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                mensaje += f"{idx}. {coin['path_completo']}\n"
            mensaje += f"\n💬 *¿En cuál quieres imputar?*\n"
            mensaje += f"• Número o nombre del departamento\n"
            mensaje += f"• 'ninguno' o 'otro' para buscar diferente\n"
            mensaje += f"• 'cancelar' para salir"
    
    else:  # webapp
        if son_existentes:
            mensaje = f"✅ **Ya tienes {len(coincidencias)} proyectos con horas:**\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                horas = coin.get('total_horas', 0)
                mensaje += f"**{idx}.** {coin['path_completo']} - **{horas}h**\n"
            mensaje += f"\n💬 **¿En cuál quieres añadir horas?**\n"
            mensaje += f"• Responde con el **número** o **nombre del departamento**\n"
            mensaje += f"• Escribe **'ninguno'** o **'otro'** si quieres un proyecto diferente\n"
            mensaje += f"• Escribe **'cancelar'** para abandonar"
        else:
            mensaje = f"🤔 He encontrado **{len(coincidencias)}** proyectos llamados **'{nombre_proyecto}'**:\n\n"
            for idx, coin in enumerate(coincidencias, 1):
                mensaje += f"**{idx}.** {coin['path_completo']}\n"
            mensaje += f"\n💬 **¿En cuál quieres imputar?**\n"
            mensaje += f"• Responde con el **número** o **nombre del departamento**\n"
            mensaje += f"• Escribe **'ninguno'** o **'otro'** si quieres un proyecto diferente\n"
            mensaje += f"• Escribe **'cancelar'** para abandonar"
    
    return mensaje


def resolver_respuesta_desambiguacion(respuesta_usuario, coincidencias):
    """
    Interpreta la respuesta del usuario y devuelve la coincidencia seleccionada.
    
    Args:
        respuesta_usuario: Texto de respuesta del usuario
        coincidencias: Lista de coincidencias
        
    Returns:
        dict: Coincidencia seleccionada o None si no se pudo determinar
    """
    respuesta = respuesta_usuario.strip().lower()
    
    # 🔢 Diccionario de números en letras
    numeros_letras = {
        'uno': 1, 'un': 1, 'una': 1,
        'dos': 2,
        'tres': 3,
        'cuatro': 4,
        'cinco': 5,
        'seis': 6,
        'siete': 7,
        'ocho': 8,
        'nueve': 9,
        'diez': 10,
        'once': 11,
        'doce': 12,
        'trece': 13,
        'catorce': 14,
        'quince': 15,
        'dieciséis': 16, 'dieciseis': 16,
        'diecisiete': 17,
        'dieciocho': 18,
        'diecinueve': 19,
        'veinte': 20
    }
    
    # Caso 1: Extraer número de la respuesta (dígitos o letras)
    # Ejemplos: "4", "el 4", "en el 4", "opción 2", "cuatro", "el cuatro"
    import re
    
    # Primero buscar dígitos
    numeros = re.findall(r'\d+', respuesta)
    numero = None
    
    if numeros:
        numero = int(numeros[0])
    else:
        # Buscar números en letras
        palabras = respuesta.split()
        for palabra in palabras:
            if palabra in numeros_letras:
                numero = numeros_letras[palabra]
                print(f"[DEBUG] 🔤 Convertido '{palabra}' a {numero}")
                break
    
    if numero:
        indice = numero - 1
        
        if 0 <= indice < len(coincidencias):
            print(f"[DEBUG] ✅ Usuario seleccionó opción {numero}")
            return coincidencias[indice]
        else:
            print(f"[DEBUG] ❌ Número fuera de rango: {numero} (máximo: {len(coincidencias)})")
            return None  # ❌ No continuar con fuzzy si el número está fuera de rango
    
    # Caso 2: Usuario responde con texto (nombre del departamento/área)
    print(f"[DEBUG] 🔍 Buscando coincidencia fuzzy para: '{respuesta}'")
    return encontrar_mejor_coincidencia_nodo(respuesta, coincidencias)
