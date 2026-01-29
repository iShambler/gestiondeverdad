#!/usr/bin/env python3
"""
Script para ejecutar el servidor con configuración óptima para 50+ usuarios concurrentes
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        #  CRÍTICO: workers=1 para que todos compartan el mismo browser_pool
        # Si usas múltiples workers, cada uno tendría su propio pool y memoria
        workers=1,
        
        #  CONCURRENCIA ALTA: hasta 500 peticiones simultáneas en cola
        # Tu ThreadPoolExecutor(max_workers=50) procesará 50 a la vez
        # Las demás esperarán en cola (FastAPI las gestiona eficientemente)
        limit_concurrency=500,
        
        # 📊 Sin límite de peticiones (para alto tráfico)
        limit_max_requests=None,
        
        # ⏱️ Timeouts generosos para operaciones de scraping
        timeout_keep_alive=300,  # 5 minutos para mantener conexiones vivas
        timeout_graceful_shutdown=30,  # 30 segundos para shutdown ordenado
        
        # 📝 Logs detallados
        log_level="info",
        access_log=True,  # Ver todas las peticiones
        
        # 🔄 Reload: True para desarrollo, False para producción
        reload=True,  #  Cambiar a False en producción
        
        #  Loop asyncio (mejor rendimiento)
        loop="asyncio",
        
        # 🌐 Backlog de conexiones TCP (cuántas conexiones pueden esperar)
        backlog=2048  # Alta capacidad de cola de conexiones
    )
