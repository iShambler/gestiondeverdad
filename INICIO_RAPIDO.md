# 🚀 Guía Rápida de Inicio - Sistema Multiusuario

## ⚡ Inicio Rápido (5 minutos)

### 1. Verificar que tienes todo instalado

```bash
cd C:\Proyectos\gestiondeverdad
pip install -r requirements.txt
```

### 2. Iniciar el servidor

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### 3. ¡Listo! Ya puedes tener múltiples usuarios trabajando

#### Opción A: Probar con el script de pruebas
```bash
python test_multiusuario.py
```

#### Opción B: Probar manualmente con curl

**Terminal 1 (Usuario 1):**
```bash
curl -X POST http://localhost:8000/chats \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"usuario1\", \"message\": \"Hola\"}"
```

**Terminal 2 (Usuario 2) - AL MISMO TIEMPO:**
```bash
curl -X POST http://localhost:8000/chats \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"usuario2\", \"message\": \"Imputa 8 horas en Desarrollo\"}"
```

### 4. Ver cuántos usuarios están conectados

```bash
curl http://localhost:8000/stats
```

---

## 📊 ¿Qué cambió?

### ANTES ❌
- Solo 1 usuario podía usar el bot a la vez
- Todos compartían el mismo navegador Chrome
- Si Usuario A estaba usando el bot, Usuario B tenía que esperar

### AHORA ✅
- **10 usuarios simultáneos** (configurable)
- Cada usuario tiene **su propio Chrome**
- **Sin interferencias** entre usuarios
- **Auto-limpieza**: cierra navegadores inactivos después de 30 minutos

---

## 🎯 Casos de Uso

### Escenario 1: Oficina con varios empleados
- 5 empleados pueden imputar horas al mismo tiempo
- Cada uno trabaja en su propio proyecto sin conflictos
- El sistema gestiona automáticamente los recursos

### Escenario 2: Picos de uso
- A las 9 AM, todos entran y empiezan a usar el bot
- El sistema abre hasta 10 navegadores simultáneos
- Si hay más de 10, pone en cola o cierra los más antiguos

### Escenario 3: Uso de Slack
- Múltiples personas en Slack pueden hablar con el bot
- Cada conversación es independiente
- Sin colas ni esperas

---

## ⚙️ Configuración Avanzada

### Cambiar el número máximo de usuarios simultáneos

Edita `browser_pool.py` (línea final):

```python
# Para más usuarios (servidor potente)
browser_pool = BrowserPool(max_sessions=20, session_timeout_minutes=30)

# Para menos usuarios (servidor limitado)
browser_pool = BrowserPool(max_sessions=5, session_timeout_minutes=15)
```

### Activar modo headless (sin ventanas visibles)

Edita `browser_pool.py` en la clase `BrowserSession`, método `initialize()`:

```python
options.add_argument('--headless')  # Descomentar esta línea
```

---

## 🧪 Pruebas Recomendadas

### Test 1: Verificar concurrencia básica
```bash
python test_multiusuario.py
# Seleccionar opción: 1 (Test de concurrencia)
```

### Test 2: Ver estadísticas en tiempo real
```bash
# Terminal 1: Iniciar servidor
uvicorn server:app --reload

# Terminal 2: Ejecutar tests
python test_multiusuario.py
# Seleccionar opción: 5 (Test de monitoreo)
```

### Test 3: Stress test
```bash
python test_multiusuario.py
# Seleccionar opción: 7 (Ejecutar TODOS los tests)
```

---

## 📈 Monitoreo

### Ver sesiones activas
```bash
curl http://localhost:8000/stats
```

Respuesta:
```json
{
  "active_sessions": 3,
  "max_sessions": 10,
  "users": ["usuario1", "usuario2", "slack_user_U123"]
}
```

### Cerrar sesión de un usuario específico
```bash
curl -X POST http://localhost:8000/close-session/usuario1
```

---

## 🔍 Logs a Observar

Cuando inicies el servidor verás:
```
[BROWSER POOL] 🚀 Pool inicializado (max: 10, timeout: 30min)
```

Cuando un usuario se conecta:
```
[BROWSER POOL] ✅ Navegador iniciado para usuario: usuario1
[BROWSER POOL] 📊 Sesiones activas: 1/10
[INFO] Haciendo login para usuario: jdoe (usuario1)
[INFO] Login exitoso para jdoe
```

Cada minuto verás limpieza automática (si hay sesiones expiradas):
```
[BROWSER POOL] 🧹 Limpiando 2 sesiones expiradas...
[BROWSER POOL] 🔒 Navegador cerrado para usuario: usuario3
```

---

## ⚠️ Problemas Comunes

### "No he podido iniciar el navegador"
**Causa**: ChromeDriver no disponible  
**Solución**:
```bash
pip install --upgrade webdriver-manager
```

### Muchos Chrome abiertos, servidor lento
**Causa**: Demasiadas sesiones abiertas  
**Solución**: Reducir `max_sessions` en `browser_pool.py`

### "Pool lleno" / "Límite alcanzado"
**Causa**: Más de 10 usuarios intentando conectar al mismo tiempo  
**Solución**: 
- Aumentar `max_sessions`
- O esperar a que se liberen sesiones inactivas

### Usuario pierde su sesión
**Causa**: Inactividad > 30 minutos  
**Solución**: Normal, al volver a escribir se crea una nueva sesión

---

## 📚 Archivos Importantes

- **`browser_pool.py`** → Gestor de navegadores (NUEVO)
- **`server.py`** → Servidor FastAPI (MODIFICADO)
- **`test_multiusuario.py`** → Script de pruebas (NUEVO)
- **`MULTIUSUARIO.md`** → Documentación completa (NUEVO)
- **`main_script.py`** → Lógica de negocio (SIN CAMBIOS)

---

## 🎉 Resultado Final

✅ Sistema listo para producción con múltiples usuarios  
✅ Cada usuario tiene su propio navegador Chrome  
✅ Gestión automática de recursos  
✅ Thread-safe y sin conflictos  
✅ Endpoints de monitoreo incluidos  

---

## 📞 Siguiente Paso

```bash
# 1. Iniciar servidor
uvicorn server:app --reload --host 0.0.0.0 --port 8000

# 2. Probar con el script
python test_multiusuario.py

# 3. ¡Disfrutar de múltiples usuarios trabajando! 🚀
```

---

## 💡 Tips de Producción

1. **Usar modo headless** para ahorrar recursos
2. **Configurar logs** en archivo para debugging
3. **Monitorear RAM** (cada Chrome consume ~200 MB)
4. **Ajustar timeouts** según patrones de uso
5. **Configurar reverse proxy** (nginx) para HTTPS

---

**¿Dudas?** Revisa `MULTIUSUARIO.md` para documentación completa.
