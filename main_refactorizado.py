"""
Asistente de Imputación de Horas - Script Principal
Versión refactorizada usando arquitectura modular.
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from core import (
    iniciar_sesion_automatica,
    mostrar_mensaje_bienvenida,
    loop_interactivo
)


def main():
    """
    Función principal del asistente.
    Inicializa el navegador, hace login automático y entra en el loop interactivo.
    """
    # Inicializar WebDriver
    service = ChromeService(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 15)

    try:
        # Login automático
        success, message = iniciar_sesion_automatica(driver, wait)
        
        if not success:
            print(f"\n❌ Error al iniciar sesión: {message}")
            print("Por favor, verifica tus credenciales en el archivo .env\n")
            return
        
        # Mostrar mensaje de bienvenida
        mostrar_mensaje_bienvenida()
        
        # Entrar en loop interactivo
        loop_interactivo(driver, wait)
        
    finally:
        driver.quit()
        print("\n🔚 Navegador cerrado. ¡Que tengas un buen día!\n")


if __name__ == "__main__":
    main()
