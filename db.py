# db.py
from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, 
    ForeignKey, JSON, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os

# ==============================================================
# 🔧 CONFIGURACIÓN BASE DE DATOS
# ==============================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==============================================================
# 🔐 CIFRADO DE CREDENCIALES
# ==============================================================

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    ENCRYPTION_KEY = Fernet.generate_key().decode()
    print(f"[INFO] Se generó una nueva ENCRYPTION_KEY: {ENCRYPTION_KEY}")

fernet = Fernet(ENCRYPTION_KEY.encode())

def cifrar(texto: str) -> str:
    """Cifra texto plano."""
    return fernet.encrypt(texto.encode()).decode() if texto else ""

def descifrar(texto: str) -> str:
    """Descifra texto cifrado."""
    return fernet.decrypt(texto.encode()).decode() if texto else ""


# ==============================================================
# 🧍 TABLA USUARIOS
# ==============================================================

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identificadores por canal
    app_id = Column(String, unique=True, nullable=True)          # ID interno de tu app con login
    slack_id = Column(String, unique=True, nullable=True)        # ID de usuario de Slack
    external_id = Column(String, unique=True, nullable=True)     # Otras integraciones futuras

    nombre = Column(String, nullable=True)
    email = Column(String, nullable=True)
    canal_principal = Column(String, default="webapp")           # webapp / slack / otro

    # Credenciales de intranet
    username_intranet = Column(String, nullable=True)
    password_intranet = Column(String, nullable=True)            # Cifrada

    creado = Column(DateTime, default=datetime.utcnow)
    ultimo_acceso = Column(DateTime, default=datetime.utcnow)
    activo = Column(Boolean, default=True)

    peticiones = relationship("Peticion", back_populates="usuario", cascade="all, delete-orphan")

    # ==========================================================
    # Métodos útiles
    # ==========================================================

    def establecer_credenciales_intranet(self, username: str, password: str):
        self.username_intranet = username
        self.password_intranet = cifrar(password)
        self.ultimo_acceso = datetime.utcnow()

    def obtener_password_intranet(self):
        return descifrar(self.password_intranet) if self.password_intranet else None


# ==============================================================
# 💬 TABLA DE PETICIONES
# ==============================================================

class Peticion(Base):
    __tablename__ = "peticiones"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"))
    canal = Column(String, default="webapp")                     # Slack, WebApp, API...
    texto_usuario = Column(Text, nullable=False)
    tipo_mensaje = Column(String, nullable=True)                 # comando / consulta / conversacion
    acciones_ejecutadas = Column(JSON, nullable=True)
    respuesta = Column(Text, nullable=True)
    estado = Column(String, default="ok")
    duracion_ms = Column(Integer, nullable=True)
    fecha = Column(DateTime, default=datetime.utcnow)

    usuario = relationship("Usuario", back_populates="peticiones")


# ==============================================================
# 🧰 FUNCIONES AUXILIARES
# ==============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Buscar o crear usuario según origen ----------------------

def obtener_usuario_por_origen(db, *, app_id=None, slack_id=None):
    if app_id:
        return db.query(Usuario).filter(Usuario.app_id == app_id).first()
    if slack_id:
        return db.query(Usuario).filter(Usuario.slack_id == slack_id).first()
    return None


def crear_usuario(db, *, app_id=None, slack_id=None, canal="webapp", nombre=None, email=None):
    nuevo = Usuario(
        app_id=app_id,
        slack_id=slack_id,
        canal_principal=canal,
        nombre=nombre,
        email=email,
        creado=datetime.utcnow(),
        ultimo_acceso=datetime.utcnow(),
    )
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


# --- Registrar interacción del usuario -----------------------

def registrar_peticion(db, usuario_id, texto, tipo, canal="webapp",
                       acciones=None, respuesta=None, estado="ok", duracion_ms=None):
    peticion = Peticion(
        usuario_id=usuario_id,
        texto_usuario=texto,
        tipo_mensaje=tipo,
        canal=canal,
        acciones_ejecutadas=acciones,
        respuesta=respuesta,
        estado=estado,
        duracion_ms=duracion_ms,
        fecha=datetime.utcnow()
    )
    db.add(peticion)
    db.commit()


# --- Limpieza de usuarios inactivos ---------------------------

def limpiar_usuarios_inactivos(db, dias: int = 60):
    limite = datetime.utcnow() - timedelta(days=dias)
    inactivos = db.query(Usuario).filter(Usuario.ultimo_acceso < limite).all()
    for u in inactivos:
        u.activo = False
    db.commit()


# ==============================================================
# 🚀 INICIALIZAR
# ==============================================================

Base.metadata.create_all(bind=engine)
print("[DB] Tablas inicializadas correctamente ✅")
