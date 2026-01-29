# db.py
from dotenv import load_dotenv
load_dotenv() 
from sqlalchemy import (
    create_engine, Column, String, Integer, Text, DateTime, 
    ForeignKey, JSON, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os

# ==============================================================
#  CONFIGURACIÓN BASE DE DATOS
# ==============================================================

DATABASE_URL = "mysql+pymysql://agente:1234@localhost:3306/agente_bot"


engine = create_engine(
    DATABASE_URL,
    #  CONFIGURACIÓN OPTIMIZADA PARA CONCURRENCIA
    pool_size=20,              # 20 conexiones permanentes
    max_overflow=30,           # Hasta 30 conexiones adicionales (total: 50)
    pool_pre_ping=True,        # Verificar conexiones antes de usar
    pool_recycle=3600,         # Reciclar conexiones cada hora
    echo=False,                # No imprimir SQL (performance)
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==============================================================
# 🔐 CIFRADO DE CREDENCIALES
# ==============================================================

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    raise RuntimeError(
        " ENCRYPTION_KEY no definida. "
        "Nunca se debe generar automáticamente."
    )

fernet = Fernet(ENCRYPTION_KEY.encode())


def cifrar(texto: str) -> str:
    """Cifra texto plano."""
    return fernet.encrypt(texto.encode()).decode() if texto else ""

def descifrar(texto: str) -> str:
    """Descifra texto cifrado."""
    if not texto:
        return ""
    try:
        return fernet.decrypt(texto.encode()).decode()
    except Exception as e:
        print(f"[DB]  Error descifrando contraseña: {e}")
        return None  # Devolverá None y el sistema pedirá credenciales de nuevo


# ==============================================================
# 🧍 TABLA USUARIOS
# ==============================================================

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identificadores por canal
    app_id = Column(String(255), unique=True, nullable=True)
    slack_id = Column(String(255), unique=True, nullable=True)
    wa_id = Column(String(255), unique=True, nullable=True)
    external_id = Column(String(255), unique=True, nullable=True)
    nombre = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    canal_principal = Column(String(50), default="webapp")
    username_intranet = Column(String(255), nullable=True)
    password_intranet = Column(String(255), nullable=True)


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
    canal = Column(String(50), default="webapp")                     # Slack, WebApp, API...
    texto_usuario = Column(Text, nullable=False)
    tipo_mensaje = Column(String(50), nullable=True)                 # comando / consulta / conversacion
    acciones_ejecutadas = Column(JSON, nullable=True)
    respuesta = Column(Text, nullable=True)
    estado = Column(String(50), default="ok")
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

def obtener_usuario_por_origen(db, *, app_id=None, slack_id=None, wa_id=None):
    if app_id:
        return db.query(Usuario).filter(Usuario.app_id == app_id).first()
    if slack_id:
        return db.query(Usuario).filter(Usuario.slack_id == slack_id).first()
    if wa_id:
        return db.query(Usuario).filter(Usuario.wa_id == wa_id).first()
    return None


def crear_usuario(db, *, app_id=None, slack_id=None, wa_id=None, canal="webapp", nombre=None, email=None):
    nuevo = Usuario(
        app_id=app_id,
        slack_id=slack_id,
        wa_id=wa_id,
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
#  INICIALIZAR
# ==============================================================

Base.metadata.create_all(bind=engine)
print("[DB] Tablas inicializadas correctamente ")
