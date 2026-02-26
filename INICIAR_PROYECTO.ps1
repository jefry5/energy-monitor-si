# Cargar variables de entorno desde .env
if (Test-Path ".env") {
    Get-Content .env | Where-Object { $_ -notmatch "^#" -and $_ -match "=" } | ForEach-Object {
        $name, $value = $_.Split('=', 2)
        [System.Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim().Trim('"'), "Process")
    }
    Write-Host "✅ Variables de entorno cargadas desde .env" -ForegroundColor Green
}

$env:N8N_BLOCK_ENV_ACCESS_IN_NODE="false"


Write-Host "--- Iniciando infraestructura Docker (BD y MQTT) ---" -ForegroundColor Cyan
docker-compose up -d

Write-Host "--- Configurando Bases de Datos (Postgres e InfluxDB) ---" -ForegroundColor Yellow
Start-Sleep -s 3
.\venv\Scripts\python.exe scripts/setup_postgres.py
.\venv\Scripts\python.exe scripts/init_influxdb.py

Write-Host "--- Iniciando Tunel de Cloudflare ---" -ForegroundColor Cyan

# Lanzamos el tunel en una ventana nueva para que no bloquee
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cloudflared tunnel --url http://localhost:5678"

Write-Host "--- Esperando 5 segundos a que el tunel genere la URL ---" -ForegroundColor Yellow
Start-Sleep -s 5

Write-Host "--- Por favor, mira la otra ventana de Cloudflare y COPIA la URL (.trycloudflare.com) ---" -ForegroundColor Magenta
$url = Read-Host "Pega aqui la URL de Cloudflare"

if ($url -ne "" -and $url -match "trycloudflare.com") {
    $env:WEBHOOK_URL = $url.Trim()
    Write-Host "--- Configurando n8n con Webhook: $url ---" -ForegroundColor Green
    
    Write-Host "--- Iniciando n8n y Simulador de Sensores ---" -ForegroundColor Cyan
    # Lanzamos el simulador en segundo plano
    Start-Process .\venv\Scripts\python.exe -ArgumentList "scripts/sensor_sim.py"
    
    # Lanzamos n8n aqui mismo
    npx n8n start
} else {
    Write-Host "Error: No pusiste una URL valida (debe contener trycloudflare.com). Abortando." -ForegroundColor Red
}
