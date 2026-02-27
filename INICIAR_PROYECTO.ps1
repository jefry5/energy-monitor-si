# ============================================================
#  EnergyCore v2 — Script de Arranque
#  Levanta toda la infraestructura del proyecto
# ============================================================

# 1. Cargar variables de entorno desde .env
if (Test-Path ".env") {
    Get-Content .env | Where-Object { $_ -notmatch "^#" -and $_ -match "=" } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"'), "Process")
    }
    Write-Host "✅ Variables de entorno cargadas desde .env" -ForegroundColor Green
} else {
    Write-Host "❌ Error: No se encuentra el archivo .env. Copia .env.example y configúralo." -ForegroundColor Red
    exit 1
}

$env:N8N_BLOCK_ENV_ACCESS_IN_NODE = "false"

# 2. Levantar infraestructura Docker
Write-Host "`n🐳 Iniciando infraestructura Docker (Postgres, InfluxDB, MQTT)..." -ForegroundColor Cyan
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Error al iniciar Docker. ¿Está Docker Desktop corriendo?" -ForegroundColor Red
    exit 1
}

# 3. Esperar a que los servicios estén listos
Write-Host "⏳ Esperando 5s para que los servicios estén listos..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 4. Inicializar base de datos InfluxDB (solo si es necesario)
Write-Host "`n📦 Inicializando InfluxDB..." -ForegroundColor Cyan
..\venv\Scripts\python.exe src\db\init_influxdb.py 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ InfluxDB lista." -ForegroundColor Green
}

# 5. Iniciar el Simulador de Sensores en background
Write-Host "`n🔌 Iniciando Simulador de Sensores (MQTT)..." -ForegroundColor Cyan
$simulator = Start-Process -FilePath "venv\Scripts\python.exe" `
    -ArgumentList "src\simulator\sensor_sim.py" `
    -PassThru -WindowStyle Minimized
Write-Host "✅ Simulador iniciado (PID: $($simulator.Id))" -ForegroundColor Green

# 6. Iniciar el Dashboard Web en background
Write-Host "`n🌐 Iniciando Dashboard Web (http://localhost:8000)..." -ForegroundColor Cyan
$dashboard = Start-Process -FilePath "venv\Scripts\python.exe" `
    -ArgumentList "src\dashboard\main.py" `
    -PassThru -WindowStyle Minimized
Write-Host "✅ Dashboard iniciado (PID: $($dashboard.Id))" -ForegroundColor Green

Write-Host "`n============================================" -ForegroundColor Magenta
Write-Host "  ⚡ EnergyCore v2 — SISTEMA ACTIVO" -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  🌐 Dashboard:  http://localhost:8000" -ForegroundColor White
Write-Host "  🔧 n8n:        http://localhost:5678" -ForegroundColor White
Write-Host "  📊 InfluxDB:   http://localhost:8086" -ForegroundColor White
Write-Host "  🗄️  Postgres:   localhost:5432" -ForegroundColor White
Write-Host "============================================`n" -ForegroundColor Magenta

Write-Host "Presiona CTRL+C para detener todos los servicios." -ForegroundColor Gray

# 7. Lanzar n8n en primer plano (bloquea hasta que el usuario cierre)
npx n8n start
