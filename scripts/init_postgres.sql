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
        accion_tomada VARCHAR(50) DEFAULT 'pendiente'
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
-- Persiste el EMA entre reinicios del contenedor n8n.
-- n8n lee esta tabla al inicio de cada ejecución y la actualiza
-- al final, garantizando continuidad del algoritmo.
CREATE TABLE
    IF NOT EXISTS ema_estado (
        area VARCHAR(100) PRIMARY KEY,
        ema_actual DECIMAL(10, 4) NOT NULL,
        contador INTEGER NOT NULL DEFAULT 0,
        ultima_vez TIMESTAMPTZ NOT NULL DEFAULT NOW ()
    );

--Índices para queries rápidas
CREATE INDEX IF NOT EXISTS idx_anomalias_timestamp ON anomalias (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_anomalias_area ON anomalias (area);

CREATE INDEX IF NOT EXISTS idx_anomalias_severidad ON anomalias (severidad);