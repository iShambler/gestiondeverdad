"""
Funciones básicas de interacción con la web mediante Selenium.
Incluye login, guardar, emitir y operaciones fundamentales.
"""

import time
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

from config import settings, Selectors


def save_cookies(driver, path="cookies.json"):
    """Guarda las cookies de la sesión actual."""
    with open(path, "w") as f:
        json.dump(driver.get_cookies(), f)


def hacer_login(driver, wait, username=None, password=None):
    """Realiza el login en la intranet con las credenciales proporcionadas.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        username: Usuario (opcional, usa settings.INTRA_USER por defecto)
        password: Contraseña (opcional, usa settings.INTRA_PASS por defecto)
    
    Returns:
        tuple: (success: bool, message: str)
            - success: True si el login fue exitoso, False si falló
            - message: Mensaje descriptivo del resultado
    """
    # Si no se proporcionan credenciales, usar las del .env
    if username is None:
        username = settings.INTRA_USER
    if password is None:
        password = settings.INTRA_PASS
    
    try:
        print(f"[DEBUG] Intentando login con usuario: {username}")
        
        # Establecer timeout de 30 segundos para cargar páginas
        driver.set_page_load_timeout(30)
        
        driver.get(settings.LOGIN_URL)
        
        # Esperar y rellenar formulario
        usr = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, Selectors.USERNAME)))
        usr.clear()
        usr.send_keys(username)
        
        pwd = driver.find_element(By.CSS_SELECTOR, Selectors.PASSWORD)
        pwd.clear()
        pwd.send_keys(password)
        
        driver.find_element(By.CSS_SELECTOR, Selectors.SUBMIT).click()
        print(f"[DEBUG] Formulario enviado, esperando respuesta...")
        time.sleep(3)
        
        # Guardar HTML completo para debugging
        html_completo = driver.page_source
        
        # Verificación 1: Buscar div de error
        print(f"[DEBUG] Buscando errorLogin...")
        if "errorLogin" in html_completo:
            print(f"[DEBUG]  Encontrado 'errorLogin' en el HTML")
            import re
            match = re.search(r'<div[^>]*class="[^"]*errorLogin[^"]*"[^>]*>(.*?)</div>', html_completo, re.DOTALL)
            if match:
                error_text = match.group(1).strip()
                error_text = re.sub(r'<[^>]+>', '', error_text).strip()
                print(f"[DEBUG]  Texto del error: '{error_text}'")
                if "credenciales no válidas" in error_text.lower() or "credenciales no validas" in error_text.lower():
                    print(f"[DEBUG]  CONFIRMADO: Credenciales inválidas")
                    return False, "credenciales_invalidas"
        else:
            print(f"[DEBUG] No se encontró 'errorLogin' en el HTML")
        
        # Verificación 2: Buscar botón de salir
        print(f"[DEBUG] Buscando botonSalirHtml...")
        if "botonSalirHtml" in html_completo:
            print(f"[DEBUG]  Encontrado 'botonSalirHtml' en el HTML")
            print(f"[DEBUG]  CONFIRMADO: Login exitoso")
            
            #  NUEVO: Comprobar si existe el botón especial "Imputar horas"
            print(f"[DEBUG]  Buscando botón especial 'Imputar horas'...")
            try:
                boton_imputar = driver.find_element(By.ID, "botonImputar")
                if boton_imputar:
                    print(f"[DEBUG]  Botón 'Imputar horas' encontrado, haciendo click...")
                    boton_imputar.click()
                    time.sleep(2)  # Esperar a que cargue la pantalla de imputación
                    print(f"[DEBUG]  Click en botón 'Imputar horas' completado")
            except:
                print(f"[DEBUG] ℹ️ Botón 'Imputar horas' no encontrado (interfaz estándar)")
            
            return True, "login_exitoso"
        else:
            print(f"[DEBUG] No se encontró 'botonSalirHtml' en el HTML")
        
        # Si no encontramos ni error ni botón
        print(f"[DEBUG]  No se encontró ni errorLogin ni botonSalirHtml")
        print(f"[DEBUG] Título de la página: {driver.title}")
        print(f"[DEBUG] URL actual: {driver.current_url}")
        
        # Guardar HTML en archivo para inspección
        try:
            with open("/tmp/ultimo_login.html", "w", encoding="utf-8") as f:
                f.write(html_completo)
            print(f"[DEBUG] HTML guardado en /tmp/ultimo_login.html para inspección")
        except:
            pass
        
        return False, "estado_indeterminado"
        
    except Exception as e:
        print(f"[DEBUG]  Excepción durante login: {e}")
        import traceback
        traceback.print_exc()
        return False, f"error_tecnico: {e}"


def volver_inicio(driver):
    """Pulsa el botón 'Volver' para regresar a la pantalla principal."""
    try:
        btn_volver = driver.find_element(By.CSS_SELECTOR, Selectors.VOLVER)
        btn_volver.click()
        time.sleep(2)
        return "He vuelto a la pantalla principal"
    except Exception as e:
        return f"No he podido volver a la pantalla principal: {e}"


def guardar_linea(driver, wait):
    """Pulsa el botón 'Guardar' tras imputar horas.
    
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        btn_guardar = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BTN_GUARDAR_LINEA)))
        btn_guardar.click()
        time.sleep(1.5)
        
        # Verificar si hay algún popup de error
        try:
            popup_error = driver.find_element(By.CSS_SELECTOR, ".ui-dialog, .modal, [role='dialog']")
            
            if popup_error.is_displayed():
                # Leer el mensaje de error
                try:
                    mensaje_error = popup_error.find_element(By.CSS_SELECTOR, ".ui-dialog-content, .modal-body, p").text
                    print(f"[DEBUG]  Error detectado al guardar: {mensaje_error}")
                    
                    # Cerrar el popup
                    try:
                        btn_aceptar = popup_error.find_element(By.XPATH, ".//button[contains(text(), 'Aceptar') or contains(text(), 'OK') or contains(text(), 'Cerrar')]")
                        btn_aceptar.click()
                        time.sleep(0.5)
                    except:
                        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                        time.sleep(0.5)
                    
                    return f" Error al guardar: {mensaje_error}"
                except:
                    return " Error al guardar (no se pudo leer el mensaje de error)"
        except:
            # No hay popup de error, todo OK
            pass
        
        return "He guardado los cambios"
    except Exception as e:
        return f"No he podido guardar: {e}"


def emitir_linea(driver, wait):
    """Pulsa el botón 'Emitir' tras imputar horas y acepta el alert de confirmación.
    
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        btn_emitir = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, Selectors.BTN_EMITIR)))
        btn_emitir.click()
        
        # Esperar a que aparezca el alert de confirmación
        time.sleep(0.5)
        
        try:
            # Capturar el alert de JavaScript
            alert = wait.until(EC.alert_is_present())
            
            # Leer el mensaje del alert (opcional, para debug)
            mensaje_alert = alert.text
            print(f"[DEBUG] 📢 Alert detectado: '{mensaje_alert}'")
            
            # Aceptar el alert
            alert.accept()
            print(f"[DEBUG]  Alert aceptado")
            
            time.sleep(1.5)
            return "He emitido las horas correctamente"
            
        except Exception as e_alert:
            print(f"[DEBUG]  No se detectó alert o error al aceptarlo: {e_alert}")
            time.sleep(1.5)
            return "He pulsado emitir (no se detectó confirmación)"
            
    except Exception as e:
        return f"No he podido emitir: {e}"
