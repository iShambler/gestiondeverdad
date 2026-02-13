"""
Scheduler de recordatorios semanales.
Cada viernes a las 14:00, revisa usuarios de WhatsApp que no han imputado horas
y les envía un recordatorio con opción de cargar la semana anterior.
"""

import time
import traceback
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from db import SessionLocal, Usuario
from browser_pool import browser_pool
from auth_handler import obtener_credenciales
from web_automation import leer_tabla_imputacion, seleccionar_fecha, lunes_de_semana
from conversation_state import conversation_state_manager


# ============================================================================
# 🧪 MODO PRUEBA: Solo enviar a estos números
# Dejar vacío o eliminar para enviar a TODOS los usuarios de WhatsApp
# ============================================================================
TEST_ONLY_NUMBERS = ["34674590643"]
# TEST_ONLY_NUMBERS = []  # ← Descomentar esta línea para activar para todos


def obtener_usuarios_whatsapp(db: Session) -> list:
    """
    Obtiene todos los usuarios activos que tienen WhatsApp configurado
    y credenciales guardadas.
    
    Si TEST_ONLY_NUMBERS tiene valores, filtra solo esos números.
    
    Returns:
        Lista de objetos Usuario con wa_id, username y password
    """
    query = db.query(Usuario).filter(
        Usuario.wa_id.isnot(None),
        Usuario.wa_id != "",
        Usuario.username_intranet.isnot(None),
        Usuario.password_intranet.isnot(None),
        Usuario.activo == True
    )
    
    #  Filtrar por números de prueba si están definidos
    if TEST_ONLY_NUMBERS:
        query = query.filter(Usuario.wa_id.in_(TEST_ONLY_NUMBERS))
        print(f"[SCHEDULER] 🧪 MODO PRUEBA: Solo enviando a {TEST_ONLY_NUMBERS}")
    
    return query.all()


def verificar_horas_semana(session, driver, wait) -> bool:
    """
    Verifica si el usuario tiene ALGUNA hora imputada en la semana actual.
    
    Returns:
        True si tiene al menos una hora, False si tiene 0 horas
    """
    try:
        # Navegar al lunes de la semana actual
        hoy = datetime.now()
        lunes = lunes_de_semana(hoy)
        
        seleccionar_fecha(driver, lunes)
        time.sleep(2)
        
        # Leer tabla de imputación
        proyectos = leer_tabla_imputacion(driver)
        
        if not proyectos:
            return False
        
        # Sumar todas las horas de la semana
        total_semana = 0
        for proyecto in proyectos:
            horas = proyecto.get('horas', {})
            total_semana += (
                horas.get('lunes', 0) +
                horas.get('martes', 0) +
                horas.get('miércoles', 0) +
                horas.get('jueves', 0) +
                horas.get('viernes', 0)
            )
        
        print(f"[SCHEDULER]    Total semana: {total_semana}h")
        return total_semana > 0
    
    except Exception as e:
        print(f"[SCHEDULER]    ⚠️ Error verificando horas: {e}")
        # En caso de error, no enviar recordatorio (mejor no molestar)
        return True


def enviar_recordatorio_whatsapp(wa_id: str, mensaje: str):
    """
    Envía un mensaje de recordatorio por WhatsApp usando Green API.
    Importa la función de server.py para reutilizarla.
    """
    # Importar aquí para evitar importación circular
    from server import enviar_whatsapp
    enviar_whatsapp(wa_id, mensaje)


def hacer_login_para_check(session, username: str, password: str) -> bool:
    """
    Hace login si la sesión no está autenticada.
    
    Returns:
        True si el login fue exitoso o ya estaba logueado
    """
    if session.is_logged_in:
        return True
    
    try:
        from web_automation import hacer_login
        with session.lock:
            success, mensaje = hacer_login(session.driver, session.wait, username, password)
        
        if success:
            session.is_logged_in = True
            return True
        else:
            print(f"[SCHEDULER]    ⚠️ Login fallido: {mensaje}")
            return False
    
    except Exception as e:
        print(f"[SCHEDULER]    ⚠️ Error en login: {e}")
        return False


def ejecutar_check_semanal():
    """
    Job principal del scheduler.
    Recorre todos los usuarios de WhatsApp y envía recordatorio
    a los que no tienen horas imputadas esta semana.
    """
    print(f"\n[SCHEDULER] {'='*60}")
    print(f"[SCHEDULER] 📋 Iniciando check semanal de imputación - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"[SCHEDULER] {'='*60}")
    
    db = SessionLocal()
    
    try:
        # Obtener usuarios de WhatsApp con credenciales
        usuarios = obtener_usuarios_whatsapp(db)
        print(f"[SCHEDULER] 👥 Usuarios WhatsApp con credenciales: {len(usuarios)}")
        
        if not usuarios:
            print(f"[SCHEDULER] ℹ️ No hay usuarios que revisar")
            return
        
        recordatorios_enviados = 0
        usuarios_con_horas = 0
        errores = 0
        
        for usuario in usuarios:
            wa_id = usuario.wa_id
            username = usuario.username_intranet
            password = usuario.obtener_password_intranet()
            
            if not password:
                print(f"[SCHEDULER]  ⚠️ {wa_id}: No se pudo descifrar la contraseña, saltando")
                errores += 1
                continue
            
            print(f"[SCHEDULER]  🔍 Revisando usuario: {wa_id} ({username})")
            
            try:
                # Obtener o crear sesión de navegador
                session = browser_pool.get_session(wa_id)
                if not session or not session.driver:
                    print(f"[SCHEDULER]    ⚠️ No se pudo obtener sesión de navegador")
                    errores += 1
                    continue
                
                # Hacer login si es necesario
                if not hacer_login_para_check(session, username, password):
                    print(f"[SCHEDULER]    ⚠️ No se pudo hacer login, saltando")
                    errores += 1
                    continue
                
                # Verificar si tiene horas esta semana
                with session.lock:
                    tiene_horas = verificar_horas_semana(session, session.driver, session.wait)
                
                session.update_activity()
                
                if tiene_horas:
                    print(f"[SCHEDULER]    ✅ Tiene horas imputadas")
                    usuarios_con_horas += 1
                else:
                    print(f"[SCHEDULER]    📩 Sin horas → enviando recordatorio")
                    
                    # Construir mensaje de recordatorio
                    mensaje = (
                        "📋 *Recordatorio de imputación*\n\n"
                        "No tienes horas registradas esta semana.\n\n"
                        "¿Quieres que cargue el horario de la semana pasada?\n\n"
                        "Responde *Sí* o *No*"
                    )
                    
                    # Guardar estado de pregunta pendiente
                    conversation_state_manager.guardar_recordatorio_semanal(wa_id)
                    
                    # Enviar mensaje
                    enviar_recordatorio_whatsapp(wa_id, mensaje)
                    recordatorios_enviados += 1
                
                # Esperar entre usuarios para no saturar
                time.sleep(3)
            
            except Exception as e:
                print(f"[SCHEDULER]    ❌ Error procesando {wa_id}: {e}")
                traceback.print_exc()
                errores += 1
                continue
        
        # Resumen final
        print(f"\n[SCHEDULER] {'='*60}")
        print(f"[SCHEDULER] 📊 Resumen del check semanal:")
        print(f"[SCHEDULER]    👥 Total revisados: {len(usuarios)}")
        print(f"[SCHEDULER]    ✅ Con horas: {usuarios_con_horas}")
        print(f"[SCHEDULER]    📩 Recordatorios enviados: {recordatorios_enviados}")
        print(f"[SCHEDULER]    ⚠️ Errores: {errores}")
        print(f"[SCHEDULER] {'='*60}\n")
    
    except Exception as e:
        print(f"[SCHEDULER] ❌ Error general en check semanal: {e}")
        traceback.print_exc()
    
    finally:
        db.close()
