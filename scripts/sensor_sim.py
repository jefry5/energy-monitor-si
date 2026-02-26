import os, time, json, random, math
from datetime import datetime
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER  = os.getenv('MQTT_BROKER', 'localhost')
PORT    = int(os.getenv('MQTT_PORT', 1883))
MODE    = os.getenv('SIM_MODE', 'anomaly')  # normal | anomaly | sensor_failure
ANOMALY_AREA = os.getenv('ANOMALY_AREA', 'auditorio')

AREAS = {
    'laboratorio_computo':  {'base': 8.5,  'nocturno': 1.2},
    'aulas_teoricas':       {'base': 3.2,  'nocturno': 0.4},
    'biblioteca':           {'base': 4.8,  'nocturno': 0.8},
    'cafeteria':            {'base': 6.1,  'nocturno': 1.5},
    'oficinas_admin':       {'base': 3.9,  'nocturno': 0.3},
    'sala_servidores':      {'base': 12.0, 'nocturno':11.5},
    'estacionamiento':      {'base': 1.2,  'nocturno': 0.6},
    'auditorio':            {'base': 5.5,  'nocturno': 0.2},
}

def valor_normal(base, nocturno):
    hora = datetime.now().hour
    if 0 <= hora < 6 or hora >= 22:
        base_val = nocturno
    elif 8 <= hora <= 18:
        base_val = base
    else:
        base_val = (base + nocturno) / 2
    return round(max(0.1, base_val * (1 + random.uniform(-0.10, 0.10))), 4)

def publicar(client):
    for area, cfg in AREAS.items():
        if MODE == 'sensor_failure' and area == ANOMALY_AREA:
            continue  # El sensor falla: no publica nada

        if MODE == 'anomaly' and area == ANOMALY_AREA:
            # Pico del 280% del valor base — debe disparar nivel Crítico
            kwh = round(cfg['base'] * 2.8 * (1 + random.uniform(-0.05, 0.05)), 4)
        else:
            kwh = valor_normal(cfg['base'], cfg['nocturno'])

        payload = json.dumps({
            'area': area,
            'kwh': kwh,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'modo': MODE
        })
        topic = f'edificio/{area}/consumo'
        client.publish(topic, payload)
        print(f'[{MODE}] {topic}: {kwh} kWh')

def main():
    client = mqtt.Client(
        client_id='sensor_sim',
        protocol=mqtt.MQTTv311,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    client.connect(BROKER, PORT, 60)
    client.loop_start()
    print(f'Simulador iniciado. Modo: {MODE}. CTRL+C para detener.')
    try:
        while True:
            publicar(client)
            time.sleep(30)
    except KeyboardInterrupt:
        print('Simulador detenido.')
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == '__main__':
    main()