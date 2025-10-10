"""
Script para resetear un usuario y que vuelva a solicitar credenciales
"""
from db import SessionLocal, Usuario

def resetear_usuario_slack(slack_id: str):
    """Resetea las credenciales de un usuario de Slack"""
    db = SessionLocal()
    
    usuario = db.query(Usuario).filter(Usuario.slack_id == slack_id).first()
    
    if usuario:
        print(f"✅ Usuario encontrado:")
        print(f"   ID: {usuario.id}")
        print(f"   Slack ID: {usuario.slack_id}")
        print(f"   Username actual: {usuario.username_intranet}")
        
        # Resetear credenciales
        usuario.username_intranet = None
        usuario.password_intranet = None
        db.commit()
        
        print(f"\n🔄 Credenciales reseteadas. El usuario deberá proporcionarlas de nuevo.")
    else:
        print(f"❌ No se encontró usuario con Slack ID: {slack_id}")
    
    db.close()

def listar_usuarios_slack():
    """Lista todos los usuarios de Slack"""
    db = SessionLocal()
    
    usuarios = db.query(Usuario).filter(Usuario.slack_id.isnot(None)).all()
    
    print("👥 Usuarios de Slack:")
    print("=" * 60)
    
    for u in usuarios:
        print(f"\nID: {u.id}")
        print(f"Slack ID: {u.slack_id}")
        print(f"Username: {u.username_intranet}")
        print(f"Tiene password: {'✅' if u.password_intranet else '❌'}")
    
    print("\n" + "=" * 60)
    db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "listar":
            listar_usuarios_slack()
        elif sys.argv[1] == "resetear" and len(sys.argv) > 2:
            slack_id = sys.argv[2]
            resetear_usuario_slack(slack_id)
        else:
            print("Uso:")
            print("  python reset_user.py listar")
            print("  python reset_user.py resetear U12345ABCD")
    else:
        listar_usuarios_slack()
