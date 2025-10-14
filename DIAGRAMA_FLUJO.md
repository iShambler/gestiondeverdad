# 🔄 Diagrama de Flujo - Sistema Multiusuario

## 📊 Flujo Completo del Sistema

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INICIO DEL SERVIDOR                              │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────┐
                    │   BrowserPool Iniciado   │
                    │   - max_sessions: 10     │
                    │   - timeout: 30 min      │
                    │   - Thread limpieza ON   │
                    └─────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐
        │  Endpoint /chats   │       │ Endpoint /slack   │
        │    (Web App)       │       │    (Slack Bot)    │
        └───────────────────┘       └───────────────────┘
                    │                           │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
        ┌─────────────────────────────────────────────┐
        │     procesar_mensaje_usuario()              │
        │     - user_id: "usuario123"                 │
        │     - mensaje: "Imputa 8 horas en Dev"     │
        └─────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐
        │ ¿Tiene credenciales?│      │  NO → Solicitar   │
        │       SÍ ↓          │       │  credenciales     │
        └───────────────────┘       └───────────────────┘
                    │
                    ▼
        ┌─────────────────────────────────────────────┐
        │   browser_pool.get_session(user_id)         │
        └─────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌─────────────────┐   ┌─────────────────┐
│ ¿Sesión existe? │   │ NO → Crear nueva│
│   SÍ ↓          │   │   BrowserSession│
└─────────────────┘   └─────────────────┘
        │                       │
        │                       ▼
        │           ┌───────────────────────┐
        │           │ 1. Iniciar Chrome     │
        │           │ 2. Crear WebDriverWait│
        │           │ 3. Contexto vacío     │
        │           └───────────────────────┘
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │ session.update_activity()    │
        │ (actualizar timestamp)       │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │ ¿Usuario ya logueado?        │
        └─────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
    ┌──────┐            ┌────────────────┐
    │  SÍ  │            │  NO → Login    │
    │  ↓   │            │  hacer_login() │
    └──────┘            └────────────────┘
        │                       │
        │                       ▼
        │           ┌───────────────────────┐
        │           │ session.is_logged_in  │
        │           │ = True                │
        │           └───────────────────────┘
        │                       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │   with session.lock:         │
        │   (Thread-safe operations)   │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │ clasificar_mensaje(texto)    │
        └─────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        │           │           │
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│Conversación│ │ Consulta │ │ Comando  │
└──────────┘ └──────────┘ └──────────┘
        │           │           │
        ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│responder_│ │interpretar│ │interpretar│
│conversa  │ │_consulta  │ │_con_gpt   │
└──────────┘ └──────────┘ └──────────┘
        │           │           │
        └───────────┼───────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  ejecutar_accion()           │
        │  - usar session.driver       │
        │  - usar session.wait         │
        │  - usar session.contexto     │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  generar_respuesta_natural() │
        │  (con GPT)                   │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  registrar_peticion(db)      │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  Responder al usuario        │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  session.update_activity()   │
        │  (marcar uso reciente)       │
        └─────────────────────────────┘


═══════════════════════════════════════════════════════════════════

                    PROCESO EN PARALELO

═══════════════════════════════════════════════════════════════════

        ┌─────────────────────────────┐
        │  Thread de Auto-limpieza     │
        │  (ejecuta cada 60 segundos)  │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  Iterar sobre todas las      │
        │  sesiones activas            │
        └─────────────────────────────┘
                    │
                    ▼
        ┌─────────────────────────────┐
        │  ¿Sesión inactiva > 30 min?  │
        └─────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
    ┌──────┐            ┌────────────────┐
    │  NO  │            │  SÍ → Cerrar   │
    │      │            │  session.close()│
    └──────┘            └────────────────┘
                                  │
                                  ▼
                        ┌───────────────────┐
                        │ driver.quit()     │
                        │ Liberar recursos  │
                        │ Eliminar del pool │
                        └───────────────────┘
```

---

## 🔄 Ejemplo Concreto con 3 Usuarios

```
TIEMPO: t=0s
═══════════════════════════════════════════════════════════════════

Usuario 1: "Hola"                      ┌──────────────┐
    ├──▶ browser_pool.get_session()   │  Chrome 1    │
    └──▶ Crea nueva sesión     ────▶  │  (User 1)    │
                                       └──────────────┘

═══════════════════════════════════════════════════════════════════
TIEMPO: t=2s
═══════════════════════════════════════════════════════════════════

Usuario 2: "Imputa 8 horas"            ┌──────────────┐
    ├──▶ browser_pool.get_session()   │  Chrome 2    │
    └──▶ Crea nueva sesión     ────▶  │  (User 2)    │
                                       └──────────────┘
                    ┌──────────────┐
User 1 sigue usando │  Chrome 1    │
                    │  (User 1)    │
                    └──────────────┘

═══════════════════════════════════════════════════════════════════
TIEMPO: t=5s
═══════════════════════════════════════════════════════════════════

Usuario 3: "Resumen semana"            ┌──────────────┐
    ├──▶ browser_pool.get_session()   │  Chrome 3    │
    └──▶ Crea nueva sesión     ────▶  │  (User 3)    │
                                       └──────────────┘
                    ┌──────────────┐
User 1 sigue usando │  Chrome 1    │
                    │  (User 1)    │
                    └──────────────┘
                    ┌──────────────┐
User 2 sigue usando │  Chrome 2    │
                    │  (User 2)    │
                    └──────────────┘

🎉 3 usuarios trabajando SIMULTÁNEAMENTE

═══════════════════════════════════════════════════════════════════
TIEMPO: t=35min (después de 30 min de inactividad)
═══════════════════════════════════════════════════════════════════

Thread de limpieza detecta:
    User 1: inactivo 32 min ❌
    User 2: inactivo 33 min ❌
    User 3: activo (usó hace 5 min) ✅

Acción:
    ┌──────────────┐
    │  Chrome 1    │  ──▶ driver.quit() 🔒 CERRADO
    │  (User 1)    │
    └──────────────┘
    
    ┌──────────────┐
    │  Chrome 2    │  ──▶ driver.quit() 🔒 CERRADO
    │  (User 2)    │
    └──────────────┘
    
    ┌──────────────┐
    │  Chrome 3    │  ──▶ Sigue activo ✅
    │  (User 3)    │
    └──────────────┘

Sesiones activas: 3 → 1
```

---

## 🔀 Comparación de Flujos

### ANTES (Sistema Antiguo)

```
┌──────────┐                   ┌──────────┐
│ Usuario 1│───┐               │ Usuario 2│─── ⏳ ESPERANDO
└──────────┘   │               └──────────┘
               │
               ▼
        ┌──────────────┐
        │  1 Chrome    │
        │  Compartido  │
        └──────────────┘
               │
               ▼
        [Procesar User 1]
               │
               ▼
        [Cerrar Chrome]
               │
               ▼
        [Abrir Chrome]
               │
               ▼
        [Procesar User 2] ◀─── Finalmente su turno
               │
               ▼
        [Cerrar Chrome]

⏱️ Tiempo total: 60 segundos (secuencial)
```

### AHORA (Sistema Nuevo)

```
┌──────────┐        ┌──────────────┐
│ Usuario 1│───────▶│  Chrome 1    │───▶ [Procesar] ✅
└──────────┘        └──────────────┘

┌──────────┐        ┌──────────────┐
│ Usuario 2│───────▶│  Chrome 2    │───▶ [Procesar] ✅
└──────────┘        └──────────────┘
                          ↓
                    SIMULTÁNEO

⚡ Tiempo total: 20 segundos (paralelo)
```

---

## 📊 Estados de una Sesión

```
┌─────────────────────────────────────────────────────────────┐
│                    CICLO DE VIDA                            │
└─────────────────────────────────────────────────────────────┘

[INICIO]
   │
   ▼
┌──────────────────┐
│   INEXISTENTE    │  ◀─── Usuario nunca ha usado el sistema
└──────────────────┘
   │
   │ Usuario envía mensaje
   ▼
┌──────────────────┐
│    CREANDO       │  ◀─── browser_pool.get_session()
└──────────────────┘       Inicializando Chrome...
   │
   │ Chrome iniciado
   ▼
┌──────────────────┐
│    ACTIVA        │  ◀─── Usuario puede trabajar
│  sin login       │       last_activity actualizado
└──────────────────┘
   │
   │ hacer_login()
   ▼
┌──────────────────┐
│    ACTIVA        │  ◀─── Usuario logueado y trabajando
│  con login       │       is_logged_in = True
└──────────────────┘
   │
   │ (cada mensaje)
   │ update_activity()
   │
   ├──────────────────────┐
   │                      │
   │ 30 min sin uso       │ Usuario sigue activo
   ▼                      ▼
┌──────────────────┐  ┌──────────────────┐
│    EXPIRADA      │  │    ACTIVA        │
│                  │  │  con login       │
└──────────────────┘  └──────────────────┘
   │                      │
   │ Thread limpieza      │ Ciclo continúa
   ▼                      ▼
┌──────────────────┐
│    CERRADA       │  ◀─── driver.quit()
│                  │       Recursos liberados
└──────────────────┘
   │
   │ Usuario vuelve a escribir
   ▼
[INICIO] (Nueva sesión)
```

---

## 🎯 Decisiones del Pool

```
┌─────────────────────────────────────────────────────────────┐
│              browser_pool.get_session(user_id)              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │ ¿Sesión existe? │
                  └─────────────────┘
                    │             │
              ┌─────┘             └─────┐
              │                         │
              ▼ SÍ                   NO ▼
    ┌─────────────────┐      ┌─────────────────┐
    │ Devolver sesión │      │ ¿Pool lleno?    │
    │ existente       │      │ (>= max_sessions)│
    └─────────────────┘      └─────────────────┘
              │                    │         │
              │              ┌─────┘         └─────┐
              │              │ SÍ              NO  │
              │              ▼                     ▼
              │    ┌──────────────────┐  ┌──────────────────┐
              │    │ Limpiar expiradas│  │ Crear nueva      │
              │    └──────────────────┘  │ sesión           │
              │              │            └──────────────────┘
              │              ▼                     │
              │    ┌──────────────────┐            │
              │    │ ¿Aún lleno?      │            │
              │    └──────────────────┘            │
              │         │         │                │
              │    ┌────┘         └────┐           │
              │    │ SÍ            NO  │           │
              │    ▼                   ▼           │
              │  ┌────────────┐  ┌────────────┐   │
              │  │ Cerrar más │  │ Crear nueva│   │
              │  │ antiguo    │  │ sesión     │   │
              │  └────────────┘  └────────────┘   │
              │         │              │           │
              └─────────┴──────────────┴───────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │ Devolver sesión │
                  └─────────────────┘
```

---

## 🔐 Thread Safety

```
┌─────────────────────────────────────────────────────────────┐
│                    PROTECCIÓN THREAD-SAFE                    │
└─────────────────────────────────────────────────────────────┘

Usuario A y Usuario B envían mensaje AL MISMO TIEMPO
│
├──▶ Proceso A                    ├──▶ Proceso B
│                                  │
▼                                  ▼
session_A.lock.acquire()          session_B.lock.acquire()
│                                  │
├─ [Operaciones Selenium]         ├─ [Operaciones Selenium]
│  · driver.find_element()        │  · driver.find_element()
│  · driver.click()               │  · driver.click()
│  · contexto["fila_actual"]      │  · contexto["proyecto_actual"]
│                                  │
session_A.lock.release()          session_B.lock.release()
│                                  │
▼                                  ▼
✅ Sin conflictos                  ✅ Sin conflictos

═══════════════════════════════════════════════════════════════

IMPORTANTE: Cada sesión tiene su propio lock
    session_A.lock ≠ session_B.lock

Por eso pueden ejecutarse en PARALELO sin conflictos
```

---

## 🎉 Resultado Final

```
          ┌─────────────────────────────────┐
          │    SISTEMA MULTIUSUARIO         │
          │    ✅ FUNCIONANDO               │
          └─────────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Usuario 1   │ │  Usuario 2   │ │  Usuario N   │
│   Chrome 1   │ │   Chrome 2   │ │   Chrome N   │
│   Login 1    │ │   Login 2    │ │   Login N    │
│  Contexto 1  │ │  Contexto 2  │ │  Contexto N  │
└──────────────┘ └──────────────┘ └──────────────┘

    ⚡ SIMULTÁNEO        ⚡ INDEPENDIENTE        ⚡ THREAD-SAFE
```
