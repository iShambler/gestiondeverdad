# Requisitos de Infraestructura - Sistema de Imputación Automática

## Servidor

- **CPU:** 4 cores
- **RAM:** 8 GB
- **Disco:** 20 GB

## Software

- **Python:** 3.9+
- **MySQL:** 8.0+
- **Google Chrome:** Última versión estable
- **Nginx:** Última versión

## Base de Datos

- **Nombre:** `agente_bot`
- **Usuario:** `gestionitt_user`
- **Permisos:** ALL PRIVILEGES sobre `agente_bot`
- **Acceso:** Solo localhost

## Red y Puertos

- **Puerto 22:** SSH (administración)
- **Puerto 80:** HTTP (redirect a HTTPS)
- **Puerto 443:** HTTPS (API pública)
- **Puerto 3306:** MySQL (solo localhost)
- **Puerto 8000:** FastAPI (solo localhost)

## Dominio

- Subdominio público (ej: `gestionitt-api.empresa.com`)
- DNS apuntando a IP del servidor

## SSL/HTTPS

- Certificado Let's Encrypt (gratuito, renovación automática)

## Acceso

- Usuario con permisos `sudo` en el servidor
- Acceso SSH para despliegue y mantenimiento

## Arquitectura

```
Internet → Nginx (443) → FastAPI (8000) → MySQL (3306)
```

## Dependencias Python

```
selenium
webdriver-manager
openai
python-dotenv
fastapi
uvicorn
requests
sqlalchemy
pymysql
cryptography
```

## Notas

- No requiere Apache Tomcat ni Java
- Aplicación Python con FastAPI
- Automatización con Selenium + Chrome Headless

