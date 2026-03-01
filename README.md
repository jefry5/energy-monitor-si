# ⚡ Energy Monitor Pro v3 + Gemini AI

> **Sistema Inteligente de Monitoreo y Gestión Energética**  
> Proyecto académico para el curso de **Sistemas Inteligentes** — Universidad Nacional Mayor de San Marcos (UNMSM)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![n8n](https://img.shields.io/badge/n8n-v2.7.5-orange)](https://n8n.io)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)](https://docker.com)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-purple)](https://mosquitto.org)
[![License](https://img.shields.io/badge/Licencia-Académica-green)]()

---

## 📋 Tabla de Contenidos

- [¿Qué es este proyecto?](#-qué-es-este-proyecto)
- [Arquitectura del Sistema](#-arquitectura-del-sistema)
- [Flujo de Datos](#-flujo-de-datos)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Tecnologías Utilizadas](#-tecnologías-utilizadas)
- [Modos de Simulación](#-modos-de-simulación)
- [Áreas Simuladas](#-áreas-simuladas)
- [Actuadores Virtuales — Relay Manager](#-actuadores-virtuales--relay-manager)
- [API REST — Endpoints](#-api-rest--endpoints)
- [Orquestación con n8n](#-orquestación-con-n8n)
- [Comandos de Telegram](#-comandos-de-telegram)
- [Requisitos Previos](#-requisitos-previos)
- [Instalación y Configuración](#-instalación-y-configuración)
- [Variables de Entorno](#-variables-de-entorno)
- [Infraestructura Docker](#-infraestructura-docker)
- [Contribuidores](#-contribuidores)

---

## 🧠 ¿Qué es este proyecto?

**Energy Monitor Pro v3** es un sistema completo de monitoreo energético inteligente que simula una red de sensores IoT distribuidos en distintas áreas de un edificio universitario o instalación industrial. Su propósito es demostrar cómo integrar tecnologías modernas de automatización, inteligencia artificial y comunicación en tiempo real para detectar anomalías, predecir consumos y gestionar el suministro eléctrico de forma autónoma.

El sistema no requiere hardware físico: todo el comportamiento de los sensores es simulado por software con patrones realistas basados en perfiles horarios, factores estacionales y modos de falla configurables.

### Capacidades principales

- Simulación avanzada de sensores con **7 modos de comportamiento** distintos (normal, anomalías, fallos graduales, intermitentes, nocturnos, flood y fallo total de sensor)
- Comunicación **bidireccional** vía MQTT: los sensores publican datos **y** reciben comandos de control
- **Actuadores virtuales (relés)** que permiten cortar o restaurar el suministro eléctrico por área de forma remota
- Detección automática de anomalías con diagnóstico inteligente mediante **Google Gemini AI**
- Almacenamiento dual: histórico estructurado en **PostgreSQL** y métricas de series temporales en **InfluxDB**
- Notificaciones y control interactivo a través de un **Bot de Telegram**
- Acceso externo seguro sin abrir puertos mediante **Cloudflare Tunnels**
- Endpoint experimental de predicción de consumo con modelo ML (`.pkl`)

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CAPA DE PRESENTACIÓN                              │
│                                                                           │
│         Bot de Telegram  ◄──────────────►  Dashboard HTML               │
│         (Alertas · Reportes · Control)       (Tiempo Real)               │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP / Webhook
┌──────────────────────────────▼──────────────────────────────────────────┐
│                      MOTOR DE ORQUESTACIÓN                               │
│                                                                           │
│                         n8n  (Self-Hosted)                               │
│                                                                           │
│   ┌──────────────┐  ┌───────────────┐  ┌────────────────┐               │
│   │  Detección   │  │  Integración  │  │   Reportes +   │               │
│   │  Anomalías   │  │  Gemini AI    │  │   Exportación  │               │
│   └──────────────┘  └───────────────┘  └────────────────┘               │
└──────────┬───────────────────────────────────────┬──────────────────────┘
           │ MQTT Subscribe                         │ HTTP / REST
┌──────────▼───────────────┐            ┌──────────▼──────────────────────┐
│     MQTT Broker           │            │       Google Gemini AI           │
│     (Mosquitto)           │            │   Diagnóstico + Predicción IA   │
│                           │            └─────────────────────────────────┘
│  Tópicos de datos:        │
│  edificio/{area}/consumo  │            ┌─────────────────────────────────┐
│  edificio/summary         │            │         Cloudflare Tunnels       │
│                           │            │   (Acceso externo sin puertos)   │
│  Tópicos de control:      │            └─────────────────────────────────┘
│  edificio/{area}/comando  │
│  edificio/system/comando  │
└──────────┬────────────────┘
           │ MQTT Publish / Subscribe
┌──────────▼──────────────────────────────────────────────────────────────┐
│                    SIMULADOR DE SENSORES  (Python)                        │
│                       sensor_sim.py — Pro v3                             │
│                                                                           │
│  • 10 áreas con perfiles realistas de consumo                            │
│  • 7 modos de simulación configurables por variable de entorno           │
│  • Relay Manager — actuadores virtuales por área                         │
│  • Curva gaussiana horaria + factor estacional (clima Perú)              │
│  • Métricas: kWh · Voltaje · Corriente · Factor de Potencia              │
│              Temperatura · Humedad · Calidad · Nº de Secuencia           │
│  • Last Will Testament para detección de caída del sistema               │
│  • API REST experimental con endpoint /predict (ML)                      │
└───────────────────┬──────────────────────────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────▼──────────┐   ┌────────▼─────────┐
│   PostgreSQL      │   │     InfluxDB      │
│                   │   │                   │
│  • Historial de   │   │  • Series de      │
│    consumos       │   │    tiempo         │
│  • Anomalías      │   │  • Métricas de    │
│  • Estados del    │   │    sensores       │
│    sistema        │   │  • Dashboards     │
└───────────────────┘   └───────────────────┘
```

---

## 🔄 Flujo de Datos

El ciclo completo de operación del sistema funciona de la siguiente manera:

**1. Generación de datos** — El simulador produce lecturas cada N segundos (configurable) para cada área aplicando: perfil base del área + factor horario gaussiano + factor estacional + ruido gaussiano + modo de simulación activo.

**2. Publicación MQTT** — Cada lectura se serializa en JSON y se publica en el tópico `edificio/{area}/consumo`. Al final de cada ciclo se publica un resumen en `edificio/summary` con el total de kWh del edificio.

**3. Recepción en n8n** — n8n está suscrito al broker MQTT y recibe cada mensaje. Los workflows evalúan umbrales de consumo, voltaje y temperatura para determinar si existe una anomalía.

**4. Diagnóstico con IA** — Si se detecta una anomalía, n8n envía los datos a Google Gemini, que genera un diagnóstico en lenguaje natural indicando la causa probable y las acciones recomendadas.

**5. Persistencia** — Los datos se almacenan en PostgreSQL (historial consultable) e InfluxDB (visualización temporal).

**6. Notificación** — Las alertas críticas se envían automáticamente al Bot de Telegram. El usuario también puede consultar el estado, pedir reportes o enviar comandos de control desde Telegram.

**7. Control bidireccional** — n8n o el usuario vía Telegram pueden enviar comandos al broker MQTT en el tópico `edificio/{area}/comando`. El simulador los recibe, actualiza el estado del relé virtual del área y publica un ACK de confirmación.

---

## 📁 Estructura del Repositorio

```
energy-monitor-si/
│
├── src/                              # Código fuente principal
│   ├── simulator/
│   │   └── sensor_sim.py             # Simulador Pro v3 + API REST
│   └── dashboard/
│       └── index.html                # Dashboard de visualización en tiempo real
│
├── n8n/
│   └── workflows/                    # Workflows exportados de n8n (.json)
│
├── infra/                            # Configuración de infraestructura
│
├── .agents/
│   └── skills/                       # Habilidades del agente AI
│
├── docker-compose.yml                # Orquestación completa de contenedores
├── requirements.txt                  # Dependencias Python del simulador
├── requirements-dashboard.txt        # Dependencias del dashboard
├── .env.example                      # Plantilla de variables de entorno
├── skills-lock.json                  # Lock de habilidades del agente
└── README.md                         # Este archivo
```

---

## 🛠️ Tecnologías Utilizadas

| Capa | Tecnología | Rol en el sistema |
|------|------------|-------------------|
| **Simulador / Lógica** | Python 3.10+ | Generación de datos sintéticos y lógica de simulación |
| **API REST (experimental)** | FastAPI + Pydantic | Endpoint `/predict` para integración futura con modelos ML |
| **Comunicación IoT** | MQTT — paho-mqtt | Transporte de mensajes sensor → n8n y comandos → sensor |
| **Broker MQTT** | Eclipse Mosquitto | Hub central de mensajería pub/sub |
| **Orquestación** | n8n v2.7.5 (self-hosted) | Motor de workflows, detección de anomalías y lógica de negocio |
| **Inteligencia Artificial** | Google Gemini AI | Diagnóstico inteligente de anomalías y predicción de consumo |
| **Base de datos relacional** | PostgreSQL + psycopg2 | Historial de consumos, anomalías y estados del sistema |
| **Series temporales** | InfluxDB + influxdb-client | Almacenamiento y visualización de métricas en el tiempo |
| **Notificaciones** | Telegram Bot API | Alertas, reportes interactivos y control remoto |
| **Contenedores** | Docker + Docker Compose | Orquestación y aislamiento de todos los servicios |
| **Acceso externo** | Cloudflare Tunnels | HTTPS seguro sin exponer puertos al exterior |
| **Dashboard** | HTML + JavaScript | Visualización de consumos en tiempo real |
| **Variables de entorno** | python-dotenv | Gestión segura de credenciales y configuración |

---

## 🎛️ Modos de Simulación

El simulador soporta 7 modos de operación configurables mediante la variable de entorno `SIM_MODE`. Solo el área definida en `ANOMALY_AREA` recibe el comportamiento especial; el resto opera en modo normal.

| Modo | Valor `.env` | Comportamiento |
|------|-------------|----------------|
| **Normal** | `normal` | Lecturas realistas con variabilidad gaussiana y perfiles horarios |
| **Anomalía (pico)** | `anomaly` | El área objetivo genera consumo 2.8× el valor base de forma sostenida |
| **Fallo de sensor** | `sensor_failure` | El área objetivo deja de publicar lecturas completamente |
| **Deriva gradual** | `gradual_drift` | El consumo sube un 2% por ciclo hasta llegar a 3× (simula falla mecánica lenta) |
| **Intermitente** | `intermittent` | El área alterna entre publicar y no publicar (simula conexión inestable) |
| **Flood (prueba de carga)** | `flood` | Cada ciclo publica 10× el número normal de mensajes |
| **Anomalía nocturna** | `night_anomaly` | Pico de 3.5× solo entre las 22:00 y las 06:00 |

---

## 🏢 Áreas Simuladas

El edificio está compuesto por 10 áreas con perfiles individuales de consumo:

| Área | kWh base (día) | kWh base (noche) | Piso | Dispositivos | Hora pico |
|------|---------------|-----------------|------|-------------|-----------|
| Laboratorio de cómputo | 8.5 | 1.2 | 2 | 40 | 14:00 |
| Aulas teóricas | 3.2 | 0.4 | 1 | 12 | 10:00 |
| Biblioteca | 4.8 | 0.8 | 3 | 20 | 11:00 |
| Cafetería | 6.1 | 1.5 | 1 | 15 | 12:00 |
| Oficinas administrativas | 3.9 | 0.3 | 4 | 18 | 09:00 |
| Sala de servidores | 12.0 | 11.5 | 2 | 8 | 15:00 |
| Estacionamiento | 1.2 | 0.6 | 0 | 30 | 08:00 |
| Auditorio | 5.5 | 0.2 | 1 | 6 | 16:00 |
| Gimnasio | 4.2 | 0.5 | 1 | 10 | 17:00 |
| Laboratorio de química | 7.8 | 2.1 | 3 | 22 | 13:00 |

Cada perfil aplica una **curva gaussiana** centrada en la hora pico para modelar el consumo de forma continua y realista, combinado con un **factor estacional** ajustado al clima de Perú (verano diciembre-marzo, invierno junio-septiembre).

---

## ⚡ Actuadores Virtuales — Relay Manager

El sistema implementa un gestor de relés virtuales (`RelayManager`) que permite controlar el suministro eléctrico por área de forma remota. Cada área tiene un relé que puede estar en estado `ENCENDIDO` o `APAGADO`.

**Comandos disponibles vía MQTT** (tópico: `edificio/{area}/comando`):

```json
// Cortar energía de un área específica
{ "accion": "cortar_energia", "motivo": "mantenimiento", "origen": "telegram" }

// Restaurar energía de un área
{ "accion": "restaurar_energia", "motivo": "fin_mantenimiento", "origen": "n8n" }

// Corte de emergencia de todo el edificio (tópico: edificio/system/comando)
{ "accion": "corte_emergencia", "motivo": "alarma_incendio", "origen": "automatico" }

// Consultar estado de todos los relés
{ "accion": "status_rele" }
```

Cuando un relé está en `APAGADO`, el área publica lecturas con `kwh: 0.0` y `quality: "relay_off"`. El sistema confirma cada cambio con un ACK en `edificio/system/relay_ack`.

---

## 🌐 API REST — Endpoints

El simulador expone una API REST mediante FastAPI. La documentación interactiva estará disponible en `http://localhost:8000/docs` cuando la API esté activa.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/` | Estado general del simulador y configuración activa |
| `GET` | `/status` | Última lectura disponible por cada área |
| `POST` | `/simulate` | Genera y publica una lectura manual con área y modo especificables |
| `GET` | `/history` | Historial reciente (hasta 500 lecturas, configurable con `?limit=N`) |
| `POST` | `/predict` |  Predicción de consumo mediante modelo ML serializado `.pkl` |

### Endpoint `/predict` — Detalle


```json
// Request
POST /predict
{
  "area": "sala_servidores",
  "horizon_hours": 24,
  "last_readings": [12.1, 11.8, 12.3, 11.9]
}

// Response
{
  "status": "simulated",
  "area": "sala_servidores",
  "model_path": "models/sala_servidores_forecast.pkl",
  "features": { "mean_24h_kwh": 12.025, "trend_per_step": 0.066, ... },
  "predictions_kwh": [...],
  "total_predicted_kwh": 284.3,
  "warning": "Endpoint . Modelo .pkl  integrado ."
}
```

---

## 🔄 Orquestación con n8n

n8n actúa como el cerebro del sistema. Los workflows se importan desde `n8n/workflows/` en el panel de n8n (`http://localhost:5678`).

**Ingesta MQTT → Bases de Datos** recibe cada mensaje del broker y lo persiste en PostgreSQL e InfluxDB aplicando transformaciones de tipo y validación de campos.

**Detección de Anomalías** evalúa cada lectura contra umbrales configurables. Si `kwh > umbral × 1.8`, `voltage < 200V` o `temperature > 40°C`, dispara el flujo de alerta.

**Diagnóstico con Gemini AI** construye un prompt estructurado con los datos de la anomalía, obtiene el diagnóstico de Gemini (causa probable + acción recomendada) y lo almacena y envía a Telegram.

**Bot de Telegram** maneja comandos entrantes del usuario, consulta PostgreSQL/InfluxDB y puede publicar comandos MQTT para controlar relés directamente desde el chat.

**Reportes Programados** genera resúmenes diarios de consumo por área con costos estimados y emisiones de CO₂, enviándolos automáticamente al chat configurado.

---

## 📱 Comandos de Telegram

| Comando / Botón | Función |
|----------------|---------|
| `/start` | Menú interactivo principal |
| 📊 **Estado en Vivo** | Carga actual por área con barras de progreso visual |
| 📈 **Reporte 24h** | Consumo total, costos estimados (S/.) y emisiones de CO₂ |
| 🚨 **Ver Anomalías** | Últimos incidentes con diagnóstico de la IA |
| 🧠 **Predicción IA** | Consulta a Gemini sobre consumo esperado próximas 24h |
| 💾 **Exportar CSV** | Descarga del historial crudo para análisis externo |
| ⚡ **Control Relés** | Cortar o restaurar suministro por área (requiere confirmación) |

---

## ✅ Requisitos Previos

- **Docker Desktop** instalado y en ejecución
- **Python 3.10+** (recomendado entorno virtual `venv`)
- **Bot de Telegram** creado con [@BotFather](https://t.me/BotFather)
- **Google Gemini API Key** en [Google AI Studio](https://aistudio.google.com/app/apikey)
- **PowerShell** (Windows) para el script de inicio automático

---

## ⚙️ Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/jefry5/energy-monitor-si.git
cd energy-monitor-si
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env con tus credenciales
```

### 3. Instalar dependencias Python (desarrollo local)

```bash
python -m venv venv
venv\Scripts\activate           # Windows
source venv/bin/activate        # Linux / Mac

pip install -r requirements.txt
```

### 4. Levantar todos los servicios

```bash
docker-compose up -d
```

O con el script automático en Windows:

```powershell
.\INICIAR_PROYECTO.ps1
```

### 5. Importar workflows en n8n

Abre `http://localhost:5678` → Workflows → Import → selecciona los `.json` de `n8n/workflows/`.

### 6. Verificar servicios activos

| Servicio | URL / Puerto |
|----------|-------------|
| n8n Dashboard | `http://localhost:5678` |
| Simulador API Docs | `http://localhost:8000/docs` |
| InfluxDB UI | `http://localhost:8086` |
| MQTT Broker | `localhost:1883` |
| PostgreSQL | `localhost:5432` |

---

## 🔐 Variables de Entorno

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `GEMINI_API_KEY` | API Key de Google Gemini | `AIza...` |
| `TELEGRAM_TOKEN` | Token del Bot de Telegram | `123456:ABC...` |
| `TELEGRAM_CHAT_ID` | ID del chat destino de alertas | `987654321` |
| `POSTGRES_DB` | Nombre de la base de datos | `energia_db` |
| `POSTGRES_USER` | Usuario de PostgreSQL | `energia_user` |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | `tu_password` |
| `INFLUXDB_TOKEN` | Token de autenticación InfluxDB | `mi_token` |
| `INFLUXDB_ORG` | Organización en InfluxDB | `energy_monitor` |
| `INFLUXDB_BUCKET` | Bucket de almacenamiento | `sensores` |
| `MQTT_BROKER` | Host del broker MQTT | `mosquitto` |
| `MQTT_PORT` | Puerto MQTT | `1883` |
| `SIM_MODE` | Modo de simulación activo | `normal` |
| `ANOMALY_AREA` | Área que recibe el modo especial | `auditorio` |
| `SIM_INTERVAL` | Segundos entre ciclos de publicación | `30` |
| `BUILDING_ID` | Identificador del edificio | `edificio_principal` |
| `TOPIC_PREFIX` | Prefijo de los tópicos MQTT | `edificio` |
| `MQTT_QOS` | Nivel de calidad de servicio MQTT | `1` |

---

## 🐳 Infraestructura Docker

El `docker-compose.yml` define todos los servicios en una red interna compartida (`energy-net`):

```
Servicios:
  ├── mosquitto      → MQTT Broker          (puerto 1883)
  ├── postgres       → Base de datos        (puerto 5432)
  ├── influxdb       → Series temporales    (puerto 8086)
  ├── n8n            → Motor de workflows   (puerto 5678)
  └── sensor-sim     → Simulador Python     (puerto 8000)
```

Todos los servicios se comunican entre sí por nombre de servicio dentro de la red Docker interna.

---
