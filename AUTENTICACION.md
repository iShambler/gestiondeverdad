# 🔐 Sistema de Autenticación de Usuarios

## Descripción General

El sistema ahora solicita a cada usuario sus credenciales de GestiónITT la primera vez que interactúan con el servicio. Las credenciales se almacenan de forma **cifrada** en la base de datos usando Fernet (criptografía simétrica).

---

## 📋 Flujo de Autenticación

### 1. Primera interacción del usuario

Cuando un usuario nuevo envía su primer mensaje (desde Slack, la web app u otro canal):

1. **El sistema verifica** si el usuario existe en la base de datos
2. Si no existe, **lo crea automáticamente**
3. **Comprueba** si tiene credenciales guardadas
4. Si NO tiene credenciales, **inicia el proceso de solicitud**

### 2. Solicitud de credenciales

El bot responde con un mensaje solicitando el **nombre de usuario**:

```
👋 ¡Hola! Veo que es la primera vez que usas este servicio.

Para poder ayudarte con la imputación de horas, necesito que me proporciones 
tus credenciales de GestiónITT.

🔐 Por favor, envíame tu **nombre de usuario** de la intranet.

⚠️ Tranquilo/a, tus credenciales se guardarán cifradas y solo se usarán 
para automatizar tus imputaciones.
```

### 3. Usuario proporciona el nombre de usuario

El usuario envía su username, por ejemplo: `jdoe`

El sistema:
- Valida que tenga al menos 3 caracteres
- Lo guarda temporalmente
- Solicita la contraseña

### 4. Solicitud de contraseña

```
✅ Perfecto, he guardado tu usuario: **jdoe**

🔑 Ahora envíame tu **contraseña** de GestiónITT.

🔒 Recuerda que será cifrada y almacenada de forma segura.
```

### 5. Usuario proporciona la contraseña

El usuario envía su password, por ejemplo: `miPassword123`

El sistema:
- Valida que tenga al menos 4 caracteres
- **Cifra la contraseña** usando Fernet
- Guarda ambas credenciales en la base de datos
- Confirma al usuario

```
🎉 ¡Excelente! Tus credenciales han sido guardadas correctamente.

Ya puedes empezar a usar el servicio. Prueba a decirme cosas como:
  • 'Imputa 8 horas en Desarrollo hoy'
  • 'Pon toda la semana en el proyecto Estudio'
  • 'Inicia la jornada'

¿En qué puedo ayudarte? 😊
```

### 6. Uso normal

Una vez configuradas las credenciales, el usuario puede usar el servicio normalmente. El sistema:
- Recupera las credenciales cifradas de la BD
- Las descifra solo cuando necesita hacer login
- Ejecuta las acciones solicitadas

---

## 🔒 Seguridad

### Cifrado de contraseñas

Las contraseñas se cifran usando **Fernet** (AES en modo CBC con HMAC para autenticación):

```python
from cryptography.fernet import Fernet

# Generar o cargar clave de cifrado
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
fernet = Fernet(ENCRYPTION_KEY.encode())

# Cifrar
password_cifrada = fernet.encrypt(password.encode()).decode()

# Descifrar
password_original = fernet.decrypt(password_cifrada.encode()).decode()
```

### Clave de cifrado

La clave se almacena en la variable de entorno `ENCRYPTION_KEY` en el archivo `.env`:

```bash
ENCRYPTION_KEY=tu_clave_secreta_aqui
```

⚠️ **IMPORTANTE**: 
- Mantén esta clave en secreto
- No la compartas ni la subas a repositorios públicos
- Si se pierde, las contraseñas cifradas no se podrán recuperar

---

## 🗄️ Base de Datos

### Tabla `usuarios`

```sql
CREATE TABLE usuarios (
    id INT PRIMARY KEY AUTO_INCREMENT,
    app_id VARCHAR(255) UNIQUE,           -- ID desde web app
    slack_id VARCHAR(255) UNIQUE,         -- ID desde Slack
    external_id VARCHAR(255) UNIQUE,      -- ID desde otras apps
    nombre VARCHAR(255),
    email VARCHAR(255),
    canal_principal VARCHAR(50) DEFAULT 'webapp',
    username_intranet VARCHAR(255),       -- Usuario de GestiónITT
    password_intranet VARCHAR(255),       -- Contraseña CIFRADA
    creado DATETIME DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso DATETIME DEFAULT CURRENT_TIMESTAMP,
    activo BOOLEAN DEFAULT TRUE
);
```

### Métodos del modelo Usuario

```python
# Establecer credenciales (cifra automáticamente)
usuario.establecer_credenciales_intranet(username, password)

# Obtener contraseña descifrada
password = usuario.obtener_password_intranet()
```

---

## 📡 Integración con APIs

### Endpoint Web App: `/chats`

```json
POST /chats
{
    "user_id": "web_user_123",
    "message": "Imputa 8 horas en Desarrollo"
}
```

### Endpoint Slack: `/slack/events`

Recibe eventos estándar de Slack API. El `user_id` se extrae del evento.

---

## 🔄 Gestión de Estado

El sistema mantiene un estado temporal en memoria para usuarios que están proporcionando credenciales:

```python
class EstadoAutenticacion:
    def __init__(self):
        # user_id -> {"esperando": "username"|"password", "username_temporal": "..."}
        self.usuarios_en_proceso = {}
```

Este estado se limpia automáticamente cuando:
- El usuario completa el proceso de autenticación
- Ocurre un error en el proceso

---

## 🧪 Casos de Uso

### Caso 1: Nuevo usuario desde Slack

```
Usuario: "Hola, imputa 8 horas hoy"
Bot: "👋 ¡Hola! Veo que es la primera vez..."
Usuario: "jdoe"
Bot: "✅ Perfecto, he guardado tu usuario..."
Usuario: "miPassword123"
Bot: "🎉 ¡Excelente! Tus credenciales han sido guardadas..."
Usuario: "Imputa 8 horas hoy"
Bot: "¡Listo! He imputado 8 horas..."
```

### Caso 2: Usuario existente

```
Usuario: "Imputa 8 horas hoy"
Bot: "¡Listo! He imputado 8 horas..."
```

### Caso 3: Error en validación

```
Usuario: "ab"  # Username muy corto
Bot: "❌ El nombre de usuario debe tener al menos 3 caracteres..."
Usuario: "jdoe"
Bot: "✅ Perfecto, he guardado tu usuario..."
```

---

## 🛠️ Funciones Principales

### `auth_handler.py`

- `verificar_y_solicitar_credenciales()`: Verifica si el usuario tiene credenciales
- `procesar_credencial()`: Procesa el username o password que envía el usuario
- `obtener_credenciales()`: Recupera y descifra las credenciales de un usuario
- `EstadoAutenticacion`: Gestiona el estado temporal del proceso

### Modificaciones en `server.py`

Ambos endpoints (`/chats` y `/slack/events`) ahora:
1. Verifican autenticación antes de procesar comandos
2. Gestionan el flujo de solicitud de credenciales
3. Registran todas las interacciones en la BD

### Modificaciones en `main_script.py`

La función `hacer_login()` ahora acepta credenciales como parámetros:

```python
def hacer_login(driver, wait, username=None, password=None):
    # Si no se proporcionan, usa las del .env (compatibilidad)
    if username is None:
        username = USERNAME
    if password is None:
        password = PASSWORD
    # ... resto del código
```

---

## ⚙️ Configuración Inicial

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`)

```bash
# OpenAI
OPENAI_API_KEY=tu_clave_openai

# Intranet (para testing o modo compatibilidad)
URL_PRIVADA=https://tu-intranet.com
INTRA_USER=usuario_admin
INTRA_PASS=password_admin

# Base de datos
DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/agente_bot

# Cifrado (generar con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=tu_clave_de_cifrado_aqui

# Slack (opcional)
SLACK_BOT_TOKEN=xoxb-tu-token-de-slack
```

### 3. Inicializar la base de datos

```bash
python db.py
```

### 4. Iniciar el servidor

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

---

## 🔍 Debugging

### Ver usuarios en la base de datos

```python
from db import SessionLocal, Usuario

db = SessionLocal()
usuarios = db.query(Usuario).all()

for u in usuarios:
    print(f"ID: {u.id}, App ID: {u.app_id}, Slack ID: {u.slack_id}")
    print(f"Username: {u.username_intranet}")
    print(f"Tiene password: {bool(u.password_intranet)}")
    print("---")
```

### Verificar cifrado

```python
from db import cifrar, descifrar

password = "test123"
cifrada = cifrar(password)
print(f"Cifrada: {cifrada}")

descifrada = descifrar(cifrada)
print(f"Descifrada: {descifrada}")
assert password == descifrada
```

---

## 📝 Notas Adicionales

1. **Compatibilidad**: El sistema mantiene compatibilidad con el modo anterior usando variables de entorno
2. **Multi-canal**: Soporta usuarios desde múltiples canales (Slack, Web, API)
3. **Persistencia**: Las credenciales se mantienen entre sesiones
4. **Logs**: Todas las interacciones se registran en la tabla `peticiones`

---

## 🚀 Próximas Mejoras

- [ ] Permitir a usuarios actualizar sus credenciales
- [ ] Añadir verificación de credenciales con un login de prueba
- [ ] Sistema de recuperación de credenciales olvidadas
- [ ] Panel de administración para gestionar usuarios
- [ ] Notificaciones cuando las credenciales expiren
