"""
Funciones para gestionar el inicio y fin de jornada laboral.
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import Selectors


def iniciar_jornada(driver, wait):
    """Pulsa el botón 'Inicio jornada' si está disponible.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        # Volver al inicio si estamos en pantalla de imputación
        try:
            btn_volver = driver.find_element(By.CSS_SELECTOR, Selectors.VOLVER)
            if btn_volver.is_displayed():
                print("[DEBUG] 🔙 Volviendo al inicio antes de iniciar jornada...")
                btn_volver.click()
                time.sleep(2)
        except:
            pass  # Ya estamos en la pantalla correcta
        
        btn_inicio = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, Selectors.BTN_INICIO_JORNADA)))

        if btn_inicio.is_enabled():
            btn_inicio.click()
            time.sleep(2)
            return "He iniciado tu jornada laboral"
        else:
            return "Tu jornada ya estaba iniciada"

    except Exception as e:
        return f"No he podido iniciar la jornada: {e}"


def finalizar_jornada(driver, wait):
    """Pulsa el botón 'Finalizar jornada' si está disponible.
    
    Args:
        driver: WebDriver de Selenium
        wait: WebDriverWait configurado
        
    Returns:
        str: Mensaje de confirmación o error
    """
    try:
        # Volver al inicio si estamos en pantalla de imputación
        try:
            btn_volver = driver.find_element(By.CSS_SELECTOR, Selectors.VOLVER)
            if btn_volver.is_displayed():
                print("[DEBUG] 🔙 Volviendo al inicio antes de finalizar jornada...")
                btn_volver.click()
                time.sleep(2)
        except:
            pass  # Ya estamos en la pantalla correcta
        
        btn_fin = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, Selectors.BTN_FIN_JORNADA)))

        if btn_fin.is_enabled():
            btn_fin.click()
            time.sleep(2)
            return "He finalizado tu jornada laboral"
        else:
            return "Tu jornada ya estaba finalizada"

    except Exception as e:
        return f"No he podido finalizar la jornada: {e}"
