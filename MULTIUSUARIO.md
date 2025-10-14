# 🔄 Sistema de Múltiples Usuarios Concurrentes

## Cambios Implementados

Se ha modificado el sistema para soportar **múltiples usuarios trabajando simultáneamente**, cada uno con su propio navegador Chrome independiente.

---

## 🆕 Archivo Nuevo: `browser_pool.py`

### **BrowserSession**
Representa la sesión de un usuario individual con:
- `driver`: Instancia de Chrome Selenium
- `wait`: WebDriverWait configurado
- `contexto`: Estado de la sesión (proyecto actual, fila, etc.)
- `is_logged_in`: Si ya hizo login
- `last_activity`: Timestamp de última actividad
- `lock`: Threading lock para operaciones thread-safe

### **BrowserPool**
Gestor centralizado de sesiones con:
- **Pool de navegadores**: Máximo 10 sesiones simultáneas (configurable)
- **Auto-limpieza**: Cierra sesiones inactivas después de 30 minutos
- **Thread-safe**: Operaciones seguras para múltiples threads
- **Gestión de recursos**: Limita el número de Chrome abiertos

---

## 🔧 Cambios en `server.py`

### Antes:
```python
# ❌ Un solo navegador global compartido por todos
driver = webdriver.Chrome(...)
wait = WebDriverWait(driver, 15)
```

### Ahora:
```python
# ✅ Cada usuario obtiene su propia sesión
session = browser_pool.get_session(user_id)
driver = session.driver
wait = session.wait
```

### Funcionalidad añadida:

1. **Función común `procesar_mensaje_usuario()`**
   - Código unificado para webapp y Slack
   - Obtiene sesión individual por usuario
   - Thread-safe con locks

2. **Nuevos endpoints:**
   - `GET /stats` - Ver sesiones activas
   - `POST /close-session/{user_id}` - Cerrar sesión específica

3. **Shutdown handler:**
   - Cierra todos los navegadores al apagar el servidor

---

## 🚀 Ventajas del Nuevo Sistema

### ✅ Concurrencia Real
- Usuario A y Usuario B pueden trabajar al mismo tiempo
- Sin interferencias entre sesiones
- Cada uno mantiene su propio estado (proyecto seleccionado, contexto)

### ✅ Gestión Inteligente de Recursos
- **Límite de sesiones**: Máximo 10 navegadores abiertos simultáneamente
- **Auto-limpieza**: Cierra navegadores inactivos (30 min)
- **LRU**: Si se alcanza el límite, cierra la sesión más antigua

### ✅ Thread-Safe
- Locks por sesión para evitar race conditions
- Operaciones Selenium protegidas
- Seguro para entornos multi-thread (FastAPI)

### ✅ Mejor Experiencia
- No más "espera tu turno"
- Cada usuario con su propia ventana
- Login persistente durante la sesión

---

## ⚙️ Configuración

### Variables de configuración en `browser_pool.py`:

```python
browser_pool = BrowserPool(
    max_sessions=10,              # Máximo de navegadores simultáneos
    session_timeout_minutes=30    # Tiempo de inactividad antes de cerrar
)
```

### Ajustar según tus necesidades:
- **Servidor potente**: Aumentar `max_sessions` a 20-30
- **Servidor limitado**: Reducir a 5-10
- **Usuarios muy activos**: Aumentar `session_timeout_minutes` a 60
- **Recursos limitados**: Reducir a 15

---

## 🧪 Cómo Probar

### 1. **Iniciar el servidor**
```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 2. **Simular múltiples usuarios (webapp)**

En diferentes terminales/Postman:

**Usuario 1:**
```bash
curl -X POST http://localhost:8000/chats \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "message": "Imputa 8 horas en Desarrollo hoy"}'
```

**Usuario 2 (simultáneamente):**
```bash
curl -X POST http://localhost:8000/chats \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user2", "message": "Imputa 5 horas en Estudio hoy"}'
```

### 3. **Ver estadísticas**
```bash
curl http://localhost:8000/stats
```

Respuesta:
```json
{
  "active_sessions": 2,
  "max_sessions": 10,
  "users": ["user1", "user2"]
}
```

### 4. **Cerrar sesión manualmente**
```bash
curl -X POST http://localhost:8000/close-session/user1
```

---

## 📊 Monitoreo

### Logs a observar:

```
[BROWSER POOL] 🚀 Pool inicializado (max: 10, timeout: 30min)
[BROWSER POOL] ✅ Navegador iniciado para usuario: user1
[BROWSER POOL] 📊 Sesiones activas: 1/10
[INFO] Haciendo login para usuario: jdoe (user1)
[INFO] Login exitoso para jdoe
[BROWSER POOL] 🧹 Limpiando 1 sesiones expiradas...
[BROWSER POOL] 🔒 Navegador cerrado para usuario: user1
```

---

## 🔍 Troubleshooting

### Problema: "No he podido iniciar el navegador"
**Causa**: ChromeDriver no se descargó correctamente  
**Solución**: 
```bash
pip install --upgrade webdriver-manager
```

### Problema: Muchos Chrome abiertos consumiendo RAM
**Causa**: `max_sessions` muy alto o timeout muy largo  
**Solución**: Reducir en `browser_pool.py`:
```python
browser_pool = BrowserPool(max_sessions=5, session_timeout_minutes=15)
```

### Problema: Usuario reporta "sesión expirada"
**Causa**: Inactividad > 30 minutos  
**Solución**: El usuario debe enviar un nuevo mensaje (se creará nueva sesión automáticamente)

### Problema: Bloqueos o "operación no permitida"
**Causa**: Race condition en operaciones Selenium  
**Solución**: Ya está protegido con `session.lock`, verificar logs

---

## 🎯 Mejoras Futuras Opcionales

1. **Modo headless**: Para servidores sin GUI
   ```python
   options.add_argument('--headless')
   ```

2. **Pool con prioridades**: VIP users con sesiones garantizadas

3. **Persistencia de sesión**: Guardar cookies entre reinicios

4. **Métricas avanzadas**: Prometheus/Grafana para monitoreo

5. **Balanceo de carga**: Distribuir entre múltiples servidores

---

## ⚠️ Notas Importantes

1. **Recursos del servidor**: Cada Chrome consume ~150-300 MB RAM
   - 10 sesiones = ~2-3 GB RAM
   - Monitorear uso con `htop` o `Task Manager`

2. **Thread-safety**: SIEMPRE usar `with session.lock:` al operar con el driver

3. **No compartir sesiones**: Cada `user_id` debe ser único

4. **Cierre limpio**: El servidor cierra todos los navegadores al apagar

---

## ✅ Checklist de Implementación

- [x] Crear `browser_pool.py`
- [x] Modificar `server.py`
- [x] Implementar thread-safety
- [x] Auto-limpieza de sesiones
- [x] Endpoints de monitoreo
- [x] Shutdown handler
- [ ] Probar con 2+ usuarios simultáneos
- [ ] Ajustar `max_sessions` según servidor
- [ ] Configurar logs de producción
- [ ] (Opcional) Activar modo headless

---

## 🎉 Resultado

Ahora el sistema soporta **múltiples usuarios trabajando simultáneamente** sin conflictos, con gestión inteligente de recursos y auto-limpieza.

**¡Cada usuario tiene su propio Chrome!** 🚀
