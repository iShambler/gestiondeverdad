"""
Script de prueba para verificar el flujo de autenticación
"""
from db import SessionLocal, Usuario, obtener_usuario_por_origen, crear_usuario
from auth_handler import verificar_y_solicitar_credenciales, procesar_credencial, obtener_credenciales

def test_flujo_autenticacion():
    """Simula el flujo completo de autenticación de un nuevo usuario"""
    
    db = SessionLocal()
    
    # Simular un usuario nuevo desde Slack
    user_id = "U12345TEST"
    canal = "slack"
    
    print("=" * 60)
    print("🧪 TEST: Flujo de Autenticación")
    print("=" * 60)
    
    # 1. Primera interacción
    print("\n1️⃣ Primera interacción del usuario...")
    usuario, mensaje = verificar_y_solicitar_credenciales(db, user_id, canal)
    print(f"Usuario creado: {usuario.id}")
    print(f"Mensaje: {mensaje[:100]}...")
    
    # 2. Usuario envía username
    print("\n2️⃣ Usuario envía su username...")
    completado, mensaje = procesar_credencial(db, user_id, "jdoe_test", canal)
    print(f"Completado: {completado}")
    print(f"Mensaje: {mensaje[:100]}...")
    
    # 3. Usuario envía password
    print("\n3️⃣ Usuario envía su password...")
    completado, mensaje = procesar_credencial(db, user_id, "password123", canal)
    print(f"Completado: {completado}")
    print(f"Mensaje: {mensaje[:100]}...")
    
    # 4. Verificar que las credenciales se guardaron correctamente
    print("\n4️⃣ Verificando credenciales guardadas...")
    username, password = obtener_credenciales(db, user_id, canal)
    print(f"Username recuperado: {username}")
    print(f"Password recuperada: {password}")
    
    # 5. Segunda interacción (usuario ya autenticado)
    print("\n5️⃣ Segunda interacción (ya autenticado)...")
    usuario, mensaje = verificar_y_solicitar_credenciales(db, user_id, canal)
    print(f"¿Necesita autenticación?: {mensaje is not None}")
    
    # Limpieza
    print("\n🧹 Limpiando datos de prueba...")
    db.delete(usuario)
    db.commit()
    
    print("\n✅ TEST COMPLETADO")
    print("=" * 60)
    
    db.close()


def test_cifrado():
    """Prueba el sistema de cifrado/descifrado"""
    from db import cifrar, descifrar
    
    print("\n=" * 60)
    print("🔐 TEST: Cifrado de Contraseñas")
    print("=" * 60)
    
    password_original = "MiPasswordSuperSegura123!"
    
    print(f"\n🔓 Password original: {password_original}")
    
    # Cifrar
    password_cifrada = cifrar(password_original)
    print(f"🔒 Password cifrada: {password_cifrada[:50]}...")
    
    # Descifrar
    password_descifrada = descifrar(password_cifrada)
    print(f"🔓 Password descifrada: {password_descifrada}")
    
    # Verificar
    if password_original == password_descifrada:
        print("\n✅ Cifrado/descifrado funciona correctamente")
    else:
        print("\n❌ ERROR: Las passwords no coinciden")
    
    print("=" * 60)


def listar_usuarios():
    """Lista todos los usuarios en la base de datos"""
    db = SessionLocal()
    
    print("\n=" * 60)
    print("👥 USUARIOS EN LA BASE DE DATOS")
    print("=" * 60)
    
    usuarios = db.query(Usuario).all()
    
    if not usuarios:
        print("\n⚠️ No hay usuarios registrados")
    else:
        for u in usuarios:
            print(f"\n📋 Usuario #{u.id}")
            print(f"   App ID: {u.app_id}")
            print(f"   Slack ID: {u.slack_id}")
            print(f"   Nombre: {u.nombre}")
            print(f"   Email: {u.email}")
            print(f"   Canal: {u.canal_principal}")
            print(f"   Username Intranet: {u.username_intranet}")
            print(f"   Tiene password: {'✅' if u.password_intranet else '❌'}")
            print(f"   Creado: {u.creado}")
            print(f"   Último acceso: {u.ultimo_acceso}")
            print(f"   Activo: {'✅' if u.activo else '❌'}")
    
    print("\n" + "=" * 60)
    db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "listar":
            listar_usuarios()
        elif sys.argv[1] == "cifrado":
            test_cifrado()
        elif sys.argv[1] == "flujo":
            test_flujo_autenticacion()
        else:
            print("Uso: python test_auth.py [listar|cifrado|flujo]")
    else:
        # Ejecutar todos los tests
        test_cifrado()
        test_flujo_autenticacion()
        listar_usuarios()
