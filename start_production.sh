#!/bin/bash
# =============================================================================
# Script de inicio para producción - GestiónDeVerdad
# =============================================================================

# Configuración
WORKERS=4                    # Número de workers (1 por cada 2-4 CPUs)
HOST="0.0.0.0"
PORT=8000
LOG_DIR="/var/log/gestiondeverdad"
PID_FILE="/var/run/gestiondeverdad.pid"

# Crear directorio de logs si no existe
mkdir -p $LOG_DIR

# Activar entorno virtual si existe
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Verificar Chrome y ChromeDriver
echo "🔍 Verificando dependencias..."

if ! command -v google-chrome &> /dev/null; then
    echo "❌ Google Chrome no instalado. Ejecuta:"
    echo "   wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
    echo "   sudo dpkg -i google-chrome-stable_current_amd64.deb"
    echo "   sudo apt-get install -f"
    exit 1
fi

if ! command -v chromedriver &> /dev/null; then
    echo "❌ ChromeDriver no instalado. Ejecuta:"
    echo "   sudo apt-get install chromium-chromedriver"
    echo "   sudo ln -s /usr/lib/chromium-browser/chromedriver /usr/bin/chromedriver"
    exit 1
fi

echo "✅ Chrome: $(google-chrome --version)"
echo "✅ ChromeDriver: $(chromedriver --version)"

# Verificar .env
if [ ! -f ".env" ]; then
    echo "❌ Archivo .env no encontrado"
    exit 1
fi

echo "✅ Archivo .env encontrado"

# Iniciar con Gunicorn (recomendado para producción)
echo ""
echo "🚀 Iniciando GestiónDeVerdad en modo producción..."
echo "   Workers: $WORKERS"
echo "   Host: $HOST:$PORT"
echo "   Logs: $LOG_DIR"
echo ""

# Opción 1: Gunicorn con Uvicorn workers (RECOMENDADO)
gunicorn server:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind $HOST:$PORT \
    --timeout 120 \
    --keep-alive 5 \
    --access-logfile $LOG_DIR/access.log \
    --error-logfile $LOG_DIR/error.log \
    --capture-output \
    --pid $PID_FILE \
    --daemon

echo "✅ Servidor iniciado en background"
echo "   PID: $(cat $PID_FILE)"
echo ""
echo "📋 Comandos útiles:"
echo "   Ver logs:     tail -f $LOG_DIR/error.log"
echo "   Detener:      kill \$(cat $PID_FILE)"
echo "   Estado:       curl http://localhost:$PORT/stats"
