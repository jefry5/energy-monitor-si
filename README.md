# ⚡ Energy Monitor Pro v2 + Gemini AI

> **Sistema Inteligente de Monitoreo y Gestión Energética** — Proyecto académico para el curso de Sistemas Inteligentes (UNMSM). Arquitectura basada en microservicios, automatización con **n8n** e **Inteligencia Artificial (Google Gemini)** para detección de anomalías y predicción de consumo eléctrico en tiempo real.

---

## 📋 Tabla de Contenidos

- [Descripción General](#-descripción-general)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)
- [Requisitos Previos](#-requisitos-previos)
- [Configuración e Instalación](#-configuración-e-instalación)
- [Orquestación y Flujos n8n](#-orquestación-y-flujos-n8n)
- [API del Simulador de Sensores](#-api-del-simulador-de-sensores)
- [Comandos de Telegram](#-comandos-de-telegram)
- [Infraestructura Docker](#-infraestructura-docker)
- [Contribuidores](#-contribuidores)

---

## 📌 Descripción General

**Energy Monitor Pro v2** es un sistema de monitoreo energético inteligente que simula sensores IoT en distintas áreas de un edificio o instalación industrial, recopila datos en tiempo real, detecta anomalías automáticamente y genera predicciones de consumo usando IA generativa.

El proyecto integra tecnologías modernas de automatización, bases de datos relacionales y de series temporales, comunicación vía protocolo MQTT y canales de notificación vía Telegram, todo orquestado mediante **n8n** como motor de workflows central.

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                     CAPA DE PRESENTACIÓN                         │
│              Telegram Bot  ◄──────►  Dashboard HTML              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   MOTOR DE ORQUESTACIÓN                          │
│                     n8n Workflow Engine                          │
│    (Detección de Anomalías · Alertas · Integración con IA)       │
└────────┬────────────────────────────────────────┬───────────────┘
         │                                        │
┌────────▼──────────┐                  ┌──────────▼──────────────┐
│   MQTT Broker     │                  │    Google Gemini AI      │
│   (Mosquitto)     │                  │  (Diagnóstico + Pred.)   │
└────────┬──────────┘                  └─────────────────────────┘
         │
┌────────▼──────────────────────────────────────────────────────┐
│                  SIMULADOR DE SENSORES (Python)                │
│     sensor_sim.py — FastAPI HTTP + Publicación MQTT            │
│   Métricas: kWh · Voltaje · Corriente · Temperatura            │
└───────────────────────────────────────────────────────────────┘
         │
┌────────▼──────────────────┬──────────────────────────────────┐
│     PostgreSQL             │           InfluxDB               │
│  (Historial · Anomalías)   │   (Series Temporales · Métricas) │
└───────────────────────────┴──────────────────────────────────┘
```

### Flujo de Datos Principal

1. El **Simulador de Sensores** genera lecturas realistas con perfiles de consumo horario y patrones de falla simulados.
2. Los datos se publican vía **MQTT** (Mosquitto) hacia n8n.
3. **n8n** evalúa umbrales, detecta anomalías y llama a la **API de Gemini AI** para diagnóstico inteligente.
4. Los resultados se almacenan en **PostgreSQL** (historial estructurado) e **InfluxDB** (métricas de series temporales).
5. El usuario interactúa con el sistema a través del **Bot de Telegram** o el **Dashboard HTML**.
6. El acceso externo seguro se realiza mediante **Cloudflare Tunnels** sin exponer puertos.

---

## 📁 Estructura del Proyecto

```
energy-monitor-si/
│
├── src/                          # Código fuente principal
│   ├── simulator/
│   │   └── sensor_sim.py         # Simulador de sensores + API FastAPI
│   └── dashboard/
│       └── index.html            # Dashboard de visualización en tiempo real
│
├── n8n/
│   └── workflows/                # Definiciones exportadas de flujos n8n (.json)
│
├── infra/                        # Archivos de infraestructura y configuración
│
├── .agents/
│   └── skills/                   # Habilidades del agente (configuración AI)
│
├── docker-compose.yml            # Orquestación completa de contenedores Docker
├── requirements.txt              # Dependencias Python del simulador
├── requirements-dashboard.txt   # Dependencias del dashboard
├── .env.example                  # Plantilla de variables de entorno
├── skills-lock.json              # Lock de habilidades del agente
└── README.md                     # Este archivo
```

---

## 🛠️ Tecnologías Utilizadas

| Capa | Tecnología | Versión / Notas |
|------|-----------|-----------------|
| **Simulador / API** | Python + FastAPI | 3.10+ |
| **Comunicación IoT** | MQTT (paho-mqtt) | Protocolo estándar IoT |
| **Broker MQTT** | Eclipse Mosquitto | Contenedor Docker |
| **Orquestación** | n8n (self-hosted) | v2.7.5 |
| **Inteligencia Artificial** | Google Gemini AI | API REST |
| **Base de Datos Relacional** | PostgreSQL | psycopg2 |
| **Series Temporales** | InfluxDB | influxdb-client |
| **Notificaciones** | Telegram Bot API | python-telegram-bot |
| **Contenedores** | Docker + Docker Compose | — |
| **Acceso Externo Seguro** | Cloudflare Tunnels | Sin abrir puertos |
| **Dashboard** | HTML + JavaScript | Visualización en tiempo real |

---

## ✅ Requisitos Previos

- **Docker Desktop** instalado y en ejecución
- **Python 3.10+** (se recomienda entorno virtual `venv`)
- **Bot de Telegram** creado mediante [@BotFather](https://t.me/BotFather)
- **Google Gemini API Key** ([obtener aquí](https://aistudio.google.com/app/apikey))
- **PowerShell** (Windows) para el script de inicio automático

---

## ⚙️ Configuración e Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/jefry5/energy-monitor-si.git
cd energy-monitor-si
```

### 2. Configurar variables de entorno

Copia el archivo de ejemplo y completa los valores:

```bash
cp .env.example .env
```

Edita el `.env` con tus credenciales:

```env
# Google Gemini AI
GEMINI_API_KEY="tu_api_key_aqui"

# Telegram Bot
TELEGRAM_TOKEN="tu_token_aqui"
TELEGRAM_CHAT_ID="tu_chat_id_aqui"

# PostgreSQL
POSTGRES_DB="energia_db"
POSTGRES_USER="energia_user"
POSTGRES_PASSWORD="tu_password_segura"

# InfluxDB
INFLUXDB_TOKEN="tu_token_influx"
INFLUXDB_ORG="energy_monitor"
INFLUXDB_BUCKET="sensores"
```

### 3. Instalar dependencias Python (opcional, para desarrollo local)

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 4. Lanzamiento con Docker

Levanta todos los servicios con un solo comando:

```bash
docker-compose up -d
```

O usa el script de automatización en **PowerShell** (Windows):

```powershell
.\INICIAR_PROYECTO.ps1
```

> Este script levanta Docker, crea las tablas en la base de datos, configura el túnel de Cloudflare e inicia n8n automáticamente.

### 5. Verificar servicios

| Servicio | URL Local |
|---------|-----------|
| n8n Dashboard | `http://localhost:5678` |
| Simulador API | `http://localhost:8000` |
| InfluxDB UI | `http://localhost:8086` |
| MQTT Broker | `localhost:1883` |

---

## 🔄 Orquestación y Flujos n8n

Los workflows de n8n se encuentran en `n8n/workflows/` y se importan directamente desde el panel de n8n.

Los flujos principales incluyen:

- **Ingesta MQTT → PostgreSQL/InfluxDB**: Recibe mensajes del broker y persiste las lecturas.
- **Detección de Anomalías**: Evalúa umbrales de consumo, voltaje y temperatura; dispara alertas si se superan.
- **Diagnóstico con Gemini AI**: Envía datos de anomalías a la API de Gemini y almacena el diagnóstico generado.
- **Reporte Telegram**: Genera y envía reportes periódicos de consumo (24h) y resúmenes de anomalías.
- **Exportación CSV**: Extrae historial de la BD y lo envía como archivo al usuario de Telegram.

---

## 🌐 API del Simulador de Sensores

El simulador expone una API REST con FastAPI. Documentación interactiva disponible en `http://localhost:8000/docs`.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Estado del simulador |
| `GET` | `/status` | Lecturas actuales de todos los sensores |
| `POST` | `/simulate` | Genera y publica una lectura simulada vía MQTT |
| `GET` | `/history` | Historial reciente de lecturas generadas |
| `POST` | `/predict` | Endpoint de predicción de consumo mediante modelo ML (`.pkl`) |

>
---

## 📱 Comandos de Telegram

Una vez configurado el bot, los siguientes comandos están disponibles:

| Comando / Botón | Función |
|----------------|---------|
| `/start` | Abre el menú interactivo principal |
| 📊 **Estado en Vivo** | Carga actual por área con barras de progreso |
| 📈 **Reporte 24h** | Consumo, costos estimados y emisiones de CO₂ |
| 🚨 **Ver Anomalías** | Últimos incidentes diagnosticados por la IA |
| 🧠 **Predicción IA** | Consulta a Gemini sobre el consumo esperado (24h) |
| 💾 **Exportar CSV** | Descarga del historial crudo para análisis externo |

---

## 🐳 Infraestructura Docker

El archivo `docker-compose.yml` define todos los servicios del sistema:

```
Servicios incluidos:
  ├── mosquitto      → MQTT Broker (puerto 1883)
  ├── postgres       → Base de datos relacional (puerto 5432)
  ├── influxdb       → Base de datos de series temporales (puerto 8086)
  ├── n8n            → Motor de workflows (puerto 5678)
  └── sensor-sim     → Simulador de sensores Python (puerto 8000)
```

Todos los servicios están en la misma red Docker (`energy-net`) para comunicación interna directa.

---