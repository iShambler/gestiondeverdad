# ✅ Sistema de Corrección de Credenciales - RESUMEN

## 🎯 Qué se implementó

Cuando un usuario tiene credenciales incorrectas de GestiónITT:

1. ❌ Sistema detecta el div `<div class="errorLogin">Credenciales no válidas</div>`
2. 💬 Pregunta: "¿Quieres actualizar tus credenciales?"
3. 📝 Usuario proporciona nuevo username y password
4. ✅ Sistema guarda (cifrado) y reintenta login automáticamente

---

## 📁 Archivos Creados/Modificados

### ✅ NUEVO: `credential_manager.py`
- Gestor para cambio de credenciales
- Mantiene estado temporal del proceso
- Valida y guarda nuevas credenciales

### ✅ MODIFICADO: `main_script.py`
- `hacer_login()` ahora retorna `(success, message)`
- Detecta div `.errorLogin` en la página
- Si hay error → `return False, "credenciales_invalidas"`

### ✅ MODIFICADO: `server.py`
- Detecta error de login y ofrece cambiar credenciales
- Procesa el flujo de cambio de credenciales
- Fuerza nuevo login tras actualización

---

## 🔄 Flujo de Usuario

```
Usuario: "Imputa 8 horas"
  ↓
❌ Error: credenciales incorrectas
  ↓
Bot: "¿Quieres actualizar tus credenciales?"
  ↓
Usuario: "pablo.solis"
  ↓
Bot: "Ahora la contraseña..."
  ↓
Usuario: "NuevaPassword123"
  ↓
Bot: "🎉 ¡Credenciales actualizadas!"
  ↓
Usuario: "Imputa 8 horas"
  ↓
✅ Funciona correctamente
```

---

## 🧪 Cómo Probar

1. **Provocar error de login:**
   - Cambiar password en GestiónITT
   - O modificar en BD: `UPDATE usuarios SET password_intranet = 'incorrecta'`

2. **Enviar mensaje:**
   ```bash
   curl -X POST http://localhost:8000/chats \
     -d '{"user_id": "test", "message": "Imputa 8 horas"}'
   ```

3. **Seguir el flujo de actualización**

---

## ✅ ¡Listo para usar!

El sistema ahora maneja automáticamente credenciales incorrectas. 🚀
