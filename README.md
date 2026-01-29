# 🤖 Bot de Imputación de Horas - GestiónITT

Sistema inteligente de automatización para imputación de horas con soporte multiusuario, múltiples interfaces y **búsqueda jerárquica de proyectos**.

---

## 🆕 ¡NUEVA FUNCIONALIDAD! - Nodos Padre

Ahora puedes especificar proyectos con el mismo nombre diferenciándolos por su **nodo padre** (departamento/área).

### Ejemplo:
```
 Antes: "Pon 3 horas en Desarrollo" 
   → Tomaba el primer "Desarrollo" (podía ser el incorrecto)

 Ahora: "Pon 3 horas en Departamento Desarrollo en Desarrollo"
   → Selecciona específicamente el "Desarrollo" de "Departamento Desarrollo"
```

**📖 Guía completa**: Ver `GUIA_NODO_PADRE.md`

---

##  Características

-  **Interpretación en lenguaje natural** con GPT-4
-  **Multiusuario concurrente** (50+ usuarios simultáneos)
-  **Múltiples interfaces**: WebApp, Slack, WhatsApp
-  **Búsqueda jerárquica**: Selección precisa con nodos padre
-  **Pool de navegadores**: Sesión individual por usuario
-  **Credenciales cifradas**: Almacenamiento seguro con Fernet
-  **Auto-recovery**: Gestión inteligente de errores de login

---

## 📦 Instalación

```bash
# 1. Clonar el repositorio
git clone <repo_url>
cd gestiondeverdad

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env con tus credenciales
```

---

## ⚙️ Configuración (.env)

```env
# OpenAI
OPENAI_API_KEY=tu_api_key_aqui

# MySQL
DATABASE_URL=mysql+pymysql://usuario:password@localhost:3306/agente_bot

# Cifrado
ENCRYPTION_KEY=tu_clave_fernet_aqui

# Slack (opcional)
SLACK_BOT_TOKEN=xoxb-tu-token-aqui
```

---

##  Uso

### Iniciar el servidor
```bash
python run_server.py
```

El servidor estará disponible en: `http://localhost:8000`

### Endpoints principales

- **POST /chats** - Interfaz principal (WebApp, WhatsApp)
- **POST /slack/events** - Integración Slack
- **GET /stats** - Estadísticas del pool de navegadores

---

## 💬 Ejemplos de Comandos

### Imputación básica
```
"Pon 8 horas en Desarrollo hoy"
"Imputa toda la semana en Estudio"
"Añade 3.5 horas el lunes en Dirección"
```

### Con nodos padre (NUEVO ✨)
```
"Pon 3 horas en Departamento Desarrollo en Desarrollo"
"Imputa 5h en Dirección del Departamento Comercial"
"Añade 4 horas en Estudio de Departamento IDI el martes"
```

### Múltiples proyectos
```
"3 horas en Desarrollo y 5 en Dirección el lunes"
"Pon 4h en Desarrollo del Dpto Comercial y 3h en Estudio del Dpto IDI"
```

### Consultas
```
"¿Cuántas horas tengo hoy?"
"Resumen de esta semana"
"¿Qué horas tengo el martes?"
```

### Modificaciones
```
"Borra las horas del miércoles"
"Cambia Desarrollo a 4 horas totales el martes"
"Elimina la línea de Dirección"
```

### Jornada laboral
```
"Inicia la jornada"
"Finaliza la jornada"
```

---

## 🏗️ Arquitectura

```
gestiondeverdad/
├── ai/                    # Inteligencia artificial
│   ├── classifier.py      # Clasificación de mensajes
│   ├── interpreter.py     # 🆕 Interpretación con nodos padre
│   ├── query_analyzer.py  # Análisis de consultas
│   └── response_generator.py
├── config/                # Configuración
│   ├── constants.py
│   ├── selectors.py
│   └── settings.py
├── core/                  # Lógica de negocio
│   ├── consultas.py
│   ├── ejecutor.py        # 🆕 Soporte nodos padre
│   └── imputacion.py
├── web_automation/        # Automatización web
│   ├── interactions.py
│   ├── jornada.py
│   ├── navigation.py
│   └── proyecto_handler.py  # 🆕 Búsqueda jerárquica
├── browser_pool.py        # Pool de navegadores
├── credential_manager.py  # Gestión de credenciales
├── db.py                  # Base de datos
├── server.py              # Servidor FastAPI
└── run_server.py          # Script de ejecución
```

---

## 🔐 Seguridad

- **Cifrado Fernet**: Todas las contraseñas se almacenan cifradas
- **Sin logs sensibles**: Passwords nunca aparecen en logs
- **Sesiones individuales**: Cada usuario tiene su navegador aislado
- **Auto-limpieza**: Sesiones inactivas se cierran automáticamente

---

## 📊 Rendimiento

**Configuración actual**:
- 50 usuarios concurrentes
- 50 navegadores simultáneos
- 500 peticiones en cola
- Pool MySQL: 20 + 30 overflow

**Recursos recomendados**:
- RAM: ~5GB (50 usuarios)
- CPU: 4+ cores
- Disco: 2GB mínimo

---

## 🧪 Testing

### Probar la funcionalidad de nodo padre
```bash
python test_nodo_padre.py
```

Verás una lista de casos de prueba que puedes enviar al bot.

### Verificar logs
Busca líneas como:
```
[DEBUG]  Seleccionando proyecto con jerarquía: 'Desarrollo' bajo 'Departamento Desarrollo'
[DEBUG]  Buscando 'Desarrollo' bajo nodo padre 'Departamento Desarrollo'...
[DEBUG]  Nodo padre encontrado: Departamento Desarrollo
```

---

## 📚 Documentación Adicional

- **GUIA_NODO_PADRE.md** - Guía de usuario para nodos padre
- **CHANGELOG_NODO_PADRE.md** - Detalles técnicos de la implementación
- **test_nodo_padre.py** - Suite de pruebas

---

## 🐛 Solución de Problemas

### "No he encontrado el proyecto X"
1. Verifica el nombre exacto en GestiónITT
2. Si hay duplicados, especifica el nodo padre
3. Revisa los logs para ver qué está buscando

### "Encontradas múltiples coincidencias"
```
 "Pon 3h en Desarrollo"
 "Pon 3h en Departamento Desarrollo en Desarrollo"
```

### Error de login
El bot pedirá automáticamente nuevas credenciales.

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Commit: `git commit -m 'Añadir nueva funcionalidad'`
4. Push: `git push origin feature/nueva-funcionalidad`
5. Pull Request

---

## 📝 Licencia

[Tu licencia aquí]

---

## 👨‍💻 Autor

[Tu nombre/empresa]

---

## 🔗 Links Útiles

- Documentación FastAPI: https://fastapi.tiangolo.com/
- Selenium Docs: https://selenium-python.readthedocs.io/
- OpenAI API: https://platform.openai.com/docs/
