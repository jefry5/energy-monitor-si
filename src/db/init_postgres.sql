-- ============================================================
--  EnergyCore v3 — PostgreSQL Schema
--  Incluye tablas para agentes inteligentes, relés virtuales,
--  feedback loop y mantenimiento preventivo.
-- ============================================================

-- Tabla de anomalías detectadas
CREATE TABLE
    IF NOT EXISTS anomalias (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        area VARCHAR(100) NOT NULL,
        dispositivo VARCHAR(100) NOT NULL,
        valor_kwh DECIMAL(10, 4) NOT NULL,
        ema_kwh DECIMAL(10, 4) NOT NULL,
        desviacion DECIMAL(8, 2) NOT NULL,
        severidad VARCHAR(20) NOT NULL, -- 'Normal','Advertencia','Critico'
        recomendacion TEXT,
        accion_tomada VARCHAR(50) DEFAULT 'pendiente',
        causa_raiz VARCHAR(100) DEFAULT NULL,           -- clasificación automática
        correlacion_id INTEGER DEFAULT NULL,             -- agrupa anomalías correlacionadas
        resuelto_en TIMESTAMPTZ DEFAULT NULL,            -- cuándo se verificó resolución
        metodo_deteccion VARCHAR(50) DEFAULT 'ema'       -- 'ema' | 'isolation_forest' | 'rule_based'
    );

-- Tabla de eventos de falla de sensor
CREATE TABLE
    IF NOT EXISTS fallas_sensor (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        dispositivo VARCHAR(100) NOT NULL,
        tipo_falla VARCHAR(50) NOT NULL,
        descripcion TEXT,
        resuelto BOOLEAN DEFAULT FALSE
    );

-- Tabla de estado del EMA por área (reemplaza Static Data)
CREATE TABLE
    IF NOT EXISTS ema_estado (
        area VARCHAR(100) PRIMARY KEY,
        ema_actual DECIMAL(10, 4) NOT NULL,
        contador INTEGER NOT NULL DEFAULT 0,
        ultima_vez TIMESTAMPTZ NOT NULL DEFAULT NOW ()
    );

-- Tabla de historial detallado de energía (Series de tiempo en Postgres)
CREATE TABLE
    IF NOT EXISTS energy_history (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        area VARCHAR(100) NOT NULL,
        reading DECIMAL(10, 4) NOT NULL,
        ema DECIMAL(10, 4) NOT NULL,
        severity VARCHAR(20) NOT NULL DEFAULT 'Normal'
    );

-- ============================================================
--  Nuevas tablas para Sistema de Agentes Inteligentes
-- ============================================================

-- Estado de relés virtuales por área
CREATE TABLE
    IF NOT EXISTS relay_states (
        area VARCHAR(100) PRIMARY KEY,
        estado VARCHAR(20) NOT NULL DEFAULT 'ENCENDIDO',  -- 'ENCENDIDO' | 'APAGADO'
        motivo VARCHAR(200) DEFAULT NULL,
        ultimo_cambio TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        cambiado_por VARCHAR(100) DEFAULT 'sistema'       -- 'sistema' | 'operador' | 'agente_X'
    );

-- Decisiones de agentes (log de auditoría)
CREATE TABLE
    IF NOT EXISTS agent_decisions (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        agent_name VARCHAR(100) NOT NULL,
        decision_type VARCHAR(100) NOT NULL,
        area VARCHAR(100) DEFAULT NULL,
        input_data JSONB DEFAULT NULL,
        output_data JSONB DEFAULT NULL,
        action_taken TEXT DEFAULT NULL,
        confidence DECIMAL(5, 4) DEFAULT NULL,
        execution_time_ms INTEGER DEFAULT NULL
    );

-- Tabla de incidentes (para verificación de resolución)
CREATE TABLE
    IF NOT EXISTS incidentes (
        id SERIAL PRIMARY KEY,
        anomalia_id INTEGER REFERENCES anomalias(id),
        timestamp_apertura TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        timestamp_cierre TIMESTAMPTZ DEFAULT NULL,
        area VARCHAR(100) NOT NULL,
        severidad VARCHAR(20) NOT NULL,
        estado VARCHAR(30) NOT NULL DEFAULT 'abierto',  -- 'abierto' | 'resuelto' | 'escalado' | 'falso_positivo'
        kwh_al_abrir DECIMAL(10, 4) NOT NULL,
        kwh_al_cerrar DECIMAL(10, 4) DEFAULT NULL,
        resolucion_automatica BOOLEAN DEFAULT FALSE,
        notas TEXT DEFAULT NULL
    );

-- Tabla de mantenimiento preventivo
CREATE TABLE
    IF NOT EXISTS mantenimiento_preventivo (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        area VARCHAR(100) NOT NULL,
        tipo VARCHAR(50) NOT NULL,            -- 'degradacion_gradual' | 'tendencia_creciente' | 'patron_anomalo'
        tendencia_diaria_pct DECIMAL(6, 3),   -- % de incremento diario promedio
        dias_detectados INTEGER DEFAULT 0,
        ema_inicio DECIMAL(10, 4),
        ema_actual DECIMAL(10, 4),
        prioridad VARCHAR(20) DEFAULT 'media', -- 'baja' | 'media' | 'alta' | 'urgente'
        estado VARCHAR(30) DEFAULT 'pendiente', -- 'pendiente' | 'programado' | 'completado'
        recomendacion TEXT DEFAULT NULL
    );

-- Tabla de feedback del operador (Telegram /resuelto, /falso_positivo)
CREATE TABLE
    IF NOT EXISTS feedback (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        anomalia_id INTEGER DEFAULT NULL,
        incidente_id INTEGER DEFAULT NULL,
        usuario VARCHAR(100) NOT NULL,
        tipo VARCHAR(30) NOT NULL,              -- 'resuelto' | 'falso_positivo' | 'correcto' | 'incorrecto'
        comentario TEXT DEFAULT NULL,
        chat_id BIGINT DEFAULT NULL
    );

-- Tabla de correlaciones entre áreas
CREATE TABLE
    IF NOT EXISTS correlaciones (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        areas TEXT[] NOT NULL,                  -- array de áreas afectadas
        tipo VARCHAR(50) NOT NULL,              -- 'simultaneo' | 'cascada' | 'patron_comun'
        descripcion TEXT DEFAULT NULL,
        anomalia_ids INTEGER[] DEFAULT NULL,
        severidad_consolidada VARCHAR(20) DEFAULT 'Advertencia'
    );

-- Historial de alertas (para deduplicación del orquestador)
CREATE TABLE
    IF NOT EXISTS alert_history (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW (),
        area VARCHAR(100) NOT NULL,
        tipo_alerta VARCHAR(50) DEFAULT NULL,
        hash_contenido VARCHAR(64) DEFAULT NULL,
        agente_origen VARCHAR(100) DEFAULT NULL,
        dedup_key VARCHAR(128) UNIQUE DEFAULT NULL,
        severidad VARCHAR(20) DEFAULT NULL,
        kwh DECIMAL(10, 4) DEFAULT NULL
    );

-- ============================================================
--  Índices para queries rápidas
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_anomalias_timestamp ON anomalias (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_anomalias_area ON anomalias (area);
CREATE INDEX IF NOT EXISTS idx_anomalias_severidad ON anomalias (severidad);
CREATE INDEX IF NOT EXISTS idx_history_timestamp ON energy_history (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_history_area ON energy_history (area);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_ts ON agent_decisions (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_agent ON agent_decisions (agent_name);
CREATE INDEX IF NOT EXISTS idx_incidentes_estado ON incidentes (estado);
CREATE INDEX IF NOT EXISTS idx_incidentes_area ON incidentes (area);
CREATE INDEX IF NOT EXISTS idx_feedback_tipo ON feedback (tipo);
CREATE INDEX IF NOT EXISTS idx_correlaciones_ts ON correlaciones (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alert_history_hash ON alert_history (hash_contenido);
CREATE INDEX IF NOT EXISTS idx_alert_history_area_ts ON alert_history (area, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_mantenimiento_area ON mantenimiento_preventivo (area);
CREATE INDEX IF NOT EXISTS idx_mantenimiento_estado ON mantenimiento_preventivo (estado);

-- Inicializar relés de todas las áreas como ENCENDIDO
INSERT INTO relay_states (area, estado) VALUES
    ('laboratorio_computo', 'ENCENDIDO'),
    ('aulas_teoricas', 'ENCENDIDO'),
    ('biblioteca', 'ENCENDIDO'),
    ('cafeteria', 'ENCENDIDO'),
    ('oficinas_admin', 'ENCENDIDO'),
    ('sala_servidores', 'ENCENDIDO'),
    ('estacionamiento', 'ENCENDIDO'),
    ('auditorio', 'ENCENDIDO'),
    ('gimnasio', 'ENCENDIDO'),
    ('laboratorio_quimica', 'ENCENDIDO')
ON CONFLICT (area) DO NOTHING;
