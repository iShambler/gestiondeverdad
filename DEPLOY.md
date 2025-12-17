# 🚀 Guía de Despliegue en Producción - GestiónDeVerdad

## Requisitos del Servidor

### Hardware Mínimo (50 usuarios)
- **CPU**: 4 cores
- **RAM**: 8 GB (cada Chrome ~150-200MB)
- **Disco**: 20 GB SSD
- **SO**: Ubuntu 22.04 LTS

### Hardware Recomendado (50+ usuarios)
- **CPU**: 8 cores
- **RAM**: 16 GB
- **Disco**: 50 GB SSD
- **SO**: Ubuntu 22.04 LTS

---

## 1. Instalación de Dependencias

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11+
sudo apt install python3.11 python3.11-venv python3-pip -y

# Instalar MySQL
sudo apt install mysql-server -y
sudo mysql_secure_installation

# Instalar Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
sudo apt-get install -f -y

# Instalar ChromeDriver (debe coincidir con versión de Chrome)
sudo apt install chromium-chromedriver -y
sudo ln -sf /usr/lib/chromium-browser/chromedriver /usr/bin/chromedriver

# Verificar instalación
google-chrome --version
chromedriver --version
```

---

## 2. Configurar MySQL

```bash
sudo mysql
```

```sql
CREATE DATABASE agente_bot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'agente'@'localhost' IDENTIFIED BY 'tu_password_segura';
GRANT ALL PRIVILEGES ON agente_bot.* TO 'agente'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 3. Desplegar Aplicación

```bash
# Clonar o copiar proyecto
cd /opt
git clone https://tu-repo/gestiondeverdad.git
cd gestiondeverdad

# Crear entorno virtual
python3.11 -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements-prod.txt
```

---

## 4. Configurar Variables de Entorno

```bash
cp .env.example .env
nano .env
```

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Base de datos
DATABASE_URL=mysql+pymysql://agente:tu_password@localhost:3306/agente_bot

# Cifrado (GENERA UNA NUEVA, NO USES ESTA)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=tu_clave_fernet_generada

# WhatsApp (opcional)
GREEN_API_INSTANCE_ID=...
GREEN_API_TOKEN=...
```

---

## 5. Configurar Systemd (Inicio Automático)

```bash
sudo nano /etc/systemd/system/gestiondeverdad.service
```

```ini
[Unit]
Description=GestionDeVerdad Bot
After=network.target mysql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/gestiondeverdad
Environment="PATH=/opt/gestiondeverdad/.venv/bin"
ExecStart=/opt/gestiondeverdad/.venv/bin/gunicorn server:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --timeout 120 \
    --access-logfile /var/log/gestiondeverdad/access.log \
    --error-logfile /var/log/gestiondeverdad/error.log
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Crear directorio de logs
sudo mkdir -p /var/log/gestiondeverdad
sudo chown www-data:www-data /var/log/gestiondeverdad

# Habilitar e iniciar
sudo systemctl daemon-reload
sudo systemctl enable gestiondeverdad
sudo systemctl start gestiondeverdad

# Ver estado
sudo systemctl status gestiondeverdad
```

---

## 6. Configurar Nginx (Reverse Proxy)

```bash
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/gestiondeverdad
```

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/gestiondeverdad /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 7. SSL con Let's Encrypt (Recomendado)

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d tu-dominio.com
```

---

## 8. Monitoreo y Mantenimiento

### Ver logs en tiempo real
```bash
sudo journalctl -u gestiondeverdad -f
tail -f /var/log/gestiondeverdad/error.log
```

### Ver estadísticas
```bash
curl http://localhost:8000/stats
```

### Reiniciar servicio
```bash
sudo systemctl restart gestiondeverdad
```

### Actualizar código
```bash
cd /opt/gestiondeverdad
git pull
source .venv/bin/activate
pip install -r requirements-prod.txt
sudo systemctl restart gestiondeverdad
```

---

## 9. Límites del Sistema (Importante para 50+ Chrome)

```bash
# Aumentar límite de archivos abiertos
sudo nano /etc/security/limits.conf
```

Añadir:
```
www-data soft nofile 65535
www-data hard nofile 65535
```

```bash
# Aumentar límite de procesos
sudo nano /etc/sysctl.conf
```

Añadir:
```
fs.file-max = 65535
vm.max_map_count = 262144
```

```bash
sudo sysctl -p
```

---

## 10. Checklist Pre-Producción

- [ ] Chrome y ChromeDriver instalados y funcionando
- [ ] MySQL configurado y accesible
- [ ] `.env` con todas las variables correctas
- [ ] `ENCRYPTION_KEY` generada de forma segura
- [ ] Systemd configurado y servicio activo
- [ ] Nginx configurado como reverse proxy
- [ ] SSL habilitado (HTTPS)
- [ ] Límites del sistema aumentados
- [ ] Logs rotando correctamente
- [ ] Backup de base de datos configurado

---

## Solución de Problemas Comunes

### Chrome no inicia
```bash
# Verificar que Chrome funciona
google-chrome --headless --disable-gpu --dump-dom https://google.com

# Si falla, instalar dependencias
sudo apt install -y libglib2.0-0 libnss3 libgconf-2-4 libfontconfig1
```

### Error "DevToolsActivePort file doesn't exist"
```bash
# Añadir más flags en browser_pool.py
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--remote-debugging-port=0')
```

### Memoria alta
```bash
# Reducir timeout de sesiones en browser_pool.py
browser_pool = BrowserPool(max_sessions=30, session_timeout_minutes=15)
```

### Conexiones MySQL agotadas
```bash
# Verificar conexiones activas
mysql -e "SHOW STATUS LIKE 'Threads_connected';"

# Aumentar en /etc/mysql/mysql.conf.d/mysqld.cnf
max_connections = 200
```
