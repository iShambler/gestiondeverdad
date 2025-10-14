# test_multiusuario.py
"""
Script de prueba para verificar que el sistema multiusuario funciona correctamente.
"""
import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://localhost:8000"

def test_usuario(user_id: str, mensaje: str):
    """
    Simula un usuario enviando un mensaje.
    """
    try:
        inicio = time.time()
        response = requests.post(
            f"{BASE_URL}/chats",
            json={"user_id": user_id, "message": mensaje},
            timeout=30
        )
        duracion = time.time() - inicio
        
        if response.status_code == 200:
            respuesta = response.json().get("reply", "Sin respuesta")
            print(f"✅ {user_id} ({duracion:.2f}s): {respuesta[:100]}...")
            return True
        else:
            print(f"❌ {user_id}: Error {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {user_id}: {e}")
        return False


def test_concurrencia():
    """
    Prueba de concurrencia: múltiples usuarios simultáneos.
    """
    print("\n" + "="*80)
    print("🧪 TEST DE CONCURRENCIA - MÚLTIPLES USUARIOS SIMULTÁNEOS")
    print("="*80 + "\n")
    
    usuarios = [
        ("user_test_1", "Hola, ¿cómo estás?"),
        ("user_test_2", "Imputa 8 horas en Desarrollo hoy"),
        ("user_test_3", "Resumen de esta semana"),
        ("user_test_4", "Inicia la jornada"),
        ("user_test_5", "¿Qué día es hoy?"),
    ]
    
    print(f"📤 Enviando {len(usuarios)} mensajes simultáneos...\n")
    inicio_total = time.time()
    
    # Ejecutar en paralelo
    with ThreadPoolExecutor(max_workers=len(usuarios)) as executor:
        futures = {
            executor.submit(test_usuario, user_id, msg): user_id 
            for user_id, msg in usuarios
        }
        
        resultados = []
        for future in as_completed(futures):
            resultados.append(future.result())
    
    duracion_total = time.time() - inicio_total
    exitosos = sum(resultados)
    
    print(f"\n📊 Resultados:")
    print(f"   ✅ Exitosos: {exitosos}/{len(usuarios)}")
    print(f"   ⏱️  Tiempo total: {duracion_total:.2f}s")
    print(f"   ⚡ Promedio por usuario: {duracion_total/len(usuarios):.2f}s")


def test_secuencial():
    """
    Prueba secuencial: un usuario tras otro.
    """
    print("\n" + "="*80)
    print("🧪 TEST SECUENCIAL - UN USUARIO TRAS OTRO")
    print("="*80 + "\n")
    
    usuarios = [
        ("user_seq_1", "Hola"),
        ("user_seq_1", "¿Cómo estás?"),
        ("user_seq_1", "Gracias"),
    ]
    
    for user_id, mensaje in usuarios:
        test_usuario(user_id, mensaje)
        time.sleep(1)


def test_mismo_usuario_concurrente():
    """
    Prueba: mismo usuario enviando múltiples mensajes simultáneos.
    """
    print("\n" + "="*80)
    print("🧪 TEST MISMO USUARIO - MÚLTIPLES MENSAJES SIMULTÁNEOS")
    print("="*80 + "\n")
    
    user_id = "user_stress"
    mensajes = [
        "Hola",
        "¿Qué día es hoy?",
        "Imputa 5 horas",
        "Gracias",
    ]
    
    print(f"📤 {user_id} enviando {len(mensajes)} mensajes simultáneos...\n")
    
    with ThreadPoolExecutor(max_workers=len(mensajes)) as executor:
        futures = [executor.submit(test_usuario, user_id, msg) for msg in mensajes]
        for future in as_completed(futures):
            future.result()


def ver_estadisticas():
    """
    Consulta las estadísticas del pool de navegadores.
    """
    print("\n" + "="*80)
    print("📊 ESTADÍSTICAS DEL POOL DE NAVEGADORES")
    print("="*80 + "\n")
    
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"🌐 Sesiones activas: {stats['active_sessions']}/{stats['max_sessions']}")
            print(f"👥 Usuarios conectados: {', '.join(stats['users']) if stats['users'] else 'Ninguno'}")
        else:
            print(f"❌ Error obteniendo estadísticas: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")


def test_stats_durante_uso():
    """
    Monitorea las estadísticas mientras se usan los navegadores.
    """
    print("\n" + "="*80)
    print("🧪 TEST DE MONITOREO - ESTADÍSTICAS EN TIEMPO REAL")
    print("="*80 + "\n")
    
    # Crear algunas sesiones
    usuarios = [f"monitor_user_{i}" for i in range(1, 4)]
    
    print("📤 Creando sesiones de usuarios...\n")
    for user in usuarios:
        test_usuario(user, "Hola")
        time.sleep(0.5)
    
    print("\n📊 Estadísticas durante uso:")
    ver_estadisticas()
    
    print("\n⏳ Esperando 5 segundos...\n")
    time.sleep(5)
    
    print("📊 Estadísticas después de 5s:")
    ver_estadisticas()


def test_cierre_sesion():
    """
    Prueba el cierre manual de sesión.
    """
    print("\n" + "="*80)
    print("🧪 TEST DE CIERRE DE SESIÓN MANUAL")
    print("="*80 + "\n")
    
    user_id = "user_close_test"
    
    # Crear sesión
    print(f"📤 Creando sesión para {user_id}...")
    test_usuario(user_id, "Hola")
    
    print("\n📊 Estadísticas antes de cerrar:")
    ver_estadisticas()
    
    # Cerrar sesión
    print(f"\n🔒 Cerrando sesión de {user_id}...")
    try:
        response = requests.post(f"{BASE_URL}/close-session/{user_id}")
        if response.status_code == 200:
            print(f"✅ Sesión cerrada correctamente")
        else:
            print(f"❌ Error cerrando sesión: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n📊 Estadísticas después de cerrar:")
    ver_estadisticas()


def menu():
    """
    Menú interactivo de pruebas.
    """
    while True:
        print("\n" + "="*80)
        print("🧪 MENÚ DE PRUEBAS - SISTEMA MULTIUSUARIO")
        print("="*80)
        print("\n1. Test de concurrencia (5 usuarios simultáneos)")
        print("2. Test secuencial (mismo usuario, varios mensajes)")
        print("3. Test mismo usuario concurrente (estrés)")
        print("4. Ver estadísticas del pool")
        print("5. Test de monitoreo en tiempo real")
        print("6. Test de cierre de sesión manual")
        print("7. Ejecutar TODOS los tests")
        print("0. Salir")
        print("\n" + "="*80)
        
        opcion = input("\n👉 Selecciona una opción: ").strip()
        
        if opcion == "1":
            test_concurrencia()
        elif opcion == "2":
            test_secuencial()
        elif opcion == "3":
            test_mismo_usuario_concurrente()
        elif opcion == "4":
            ver_estadisticas()
        elif opcion == "5":
            test_stats_durante_uso()
        elif opcion == "6":
            test_cierre_sesion()
        elif opcion == "7":
            print("\n🚀 Ejecutando todos los tests...\n")
            test_concurrencia()
            time.sleep(2)
            test_secuencial()
            time.sleep(2)
            test_mismo_usuario_concurrente()
            time.sleep(2)
            test_stats_durante_uso()
            time.sleep(2)
            test_cierre_sesion()
            print("\n✅ Todos los tests completados!")
        elif opcion == "0":
            print("\n👋 ¡Hasta luego!")
            break
        else:
            print("\n❌ Opción inválida")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔧 PRUEBAS DEL SISTEMA MULTIUSUARIO")
    print("="*80)
    print("\n⚠️  Asegúrate de que el servidor esté corriendo:")
    print("   uvicorn server:app --reload --host 0.0.0.0 --port 8000")
    print("\n" + "="*80)
    
    input("\n📍 Presiona ENTER cuando el servidor esté listo...")
    
    # Verificar que el servidor está disponible
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=5)
        if response.status_code == 200:
            print("✅ Servidor detectado correctamente\n")
            menu()
        else:
            print("❌ El servidor respondió pero con error")
    except Exception as e:
        print(f"❌ No se pudo conectar al servidor: {e}")
        print("\n💡 Asegúrate de iniciar el servidor primero:")
        print("   uvicorn server:app --reload --host 0.0.0.0 --port 8000")
