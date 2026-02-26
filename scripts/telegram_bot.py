import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Final

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from influxdb_client import InfluxDBClient
import psycopg2
import google.generativeai as genai

# Configuración de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Cargar variables de entorno
load_dotenv()

TOKEN: Final = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY: Final = os.getenv("GEMINI_API_KEY")

# Usamos localhost porque el bot corre en Windows
INFLUX_URL: Final = "http://localhost:8086"
INFLUX_TOKEN: Final = os.getenv("INFLUXDB_TOKEN")
INFLUX_ORG: Final = os.getenv("INFLUXDB_ORG")
INFLUX_BUCKET: Final = os.getenv("INFLUXDB_BUCKET")

POSTGRES_DB: Final = os.getenv("POSTGRES_DB")
POSTGRES_USER: Final = os.getenv("POSTGRES_USER")
POSTGRES_PASS: Final = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST: Final = "localhost"

# Configurar Gemini
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start: Muestra el menú principal."""
    keyboard = [
        [InlineKeyboardButton("📊 Generar Reporte 24h", callback_data='get_report')],
        [InlineKeyboardButton("⚡ Estado de Áreas", callback_data='get_status')],
        [InlineKeyboardButton("🧠 Consultar a la IA", callback_data='get_ai_help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg = (
        "👋 <b>¡Bienvenido al Monitor de Energía!</b>\n\n"
        "Este bot interactivo te permite consultar el consumo del edificio "
        "sin necesidad de servidores externos.\n\n"
        "Comandos nuevos:\n"
        "• <code>/ai [tu pregunta]</code> - Pregunta a la IA sobre tus datos.\n\n"
        "¿Qué deseas consultar?"
    )
    await update.message.reply_html(msg, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones."""
    query = update.callback_query
    await query.answer()

    if query.data == 'get_report':
        await query.edit_message_text("⌛ Generando reporte desde InfluxDB...")
        report = get_influx_report()
        
        keyboard = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data='go_home')]]
        await query.edit_message_text(report, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == 'get_status':
        status = get_current_status()
        keyboard = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data='go_home')]]
        await query.edit_message_text(status, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif query.data == 'get_ai_help':
        msg = (
            "🧠 <b>Consultar a la IA</b>\n\n"
            "Usa el comando <code>/ai</code> seguido de tu pregunta.\n"
            "Ejem: <code>/ai ¿Qué día consumí más energía esta semana?</code>\n\n"
            "La IA tiene acceso a los últimos 7 días de consumo energético del edificio."
        )
        keyboard = [[InlineKeyboardButton("⬅️ Volver al Menú", callback_data='go_home')]]
        await query.edit_message_text(msg, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == 'go_home':
        keyboard = [
            [InlineKeyboardButton("📊 Generar Reporte 24h", callback_data='get_report')],
            [InlineKeyboardButton("⚡ Estado de Áreas", callback_data='get_status')],
            [InlineKeyboardButton("🧠 Consultar a la IA", callback_data='get_ai_help')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("¿Qué deseas hacer?", reply_markup=reply_markup)

async def ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /ai: Consulta a Gemini con contexto de InfluxDB."""
    user_query = " ".join(context.args) if context.args else None
    
    if not user_query:
        await update.message.reply_text("🧐 Por favor, escribe una pregunta después de /ai.\nEjem: /ai ¿Cuál fue el consumo total ayer?")
        return

    if not model:
        await update.message.reply_text("❌ No se ha configurado la API Key de Gemini.")
        return

    sent_msg = await update.message.reply_text("🤔 Analizando datos del edificio con IA...")
    
    try:
        # Obtener datos de los últimos 7 días como contexto
        data_context = get_ai_data_context()
        
        prompt = (
            f"Actúa como un analista de eficiencia energética. Aquí están los datos de consumo (kWh) "
            f"por área y día de la última semana del edificio:\n\n"
            f"{data_context}\n\n"
            f"Pregunta del usuario: {user_query}\n\n"
            f"Responde de forma clara, directa y en español. Si te preguntan 'quién consumió más' o 'cuándo', "
            f"usa los datos proporcionados para ser preciso."
        )
        
        response = model.generate_content(prompt)
        await sent_msg.edit_text(response.text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error en Gemini AI: {e}")
        await sent_msg.edit_text("⚠️ No pude conectar con la IA en este momento o hubo un error al procesar los datos.")

def get_ai_data_context():
    """Consulta InfluxDB y genera un resumen de la última semana para la IA."""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        # Query de los últimos 7 días agrupado por día y área
        flux_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -7d)
            |> filter(fn: (r) => r["_measurement"] == "consumo_energetico" and r["_field"] == "kwh")
            |> aggregateWindow(every: 1d, fn: sum, createEmpty: false)
        '''
        
        tables = query_api.query(flux_query)
        client.close()
        
        context_lines = []
        for table in tables:
            for record in table.records:
                fecha = record.get_time().strftime("%Y-%m-%d")
                area = record.values.get("area")
                kwh = record.get_value()
                context_lines.append(f"Fecha: {fecha}, Área: {area}, Consumo: {kwh:.2f} kWh")
        
        return "\n".join(context_lines) if context_lines else "No hay datos recientes."
    except Exception as e:
        logging.error(f"Error cargando contexto IA: {e}")
        return "Error cargando datos de InfluxDB."

def get_influx_report():
    """Consulta InfluxDB y formatea el reporte de 24h."""
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        query_api = client.query_api()
        
        flux_query = f'''
        from(bucket: "{INFLUX_BUCKET}")
            |> range(start: -24h)
            |> filter(fn: (r) => r["_measurement"] == "consumo_energetico")
            |> filter(fn: (r) => r["_field"] == "kwh")
            |> group(columns: ["area"])
            |> sum()
        '''
        
        tables = query_api.query(flux_query)
        client.close()
        
        if not tables:
            return "❌ No hay datos suficientes para generar el reporte."
            
        resumen = "📊 <b>REPORTE 24 HORAS</b>\n\n"
        total_acumulado = 0
        
        for table in tables:
            for record in table.records:
                area = record.values.get("area")
                kwh = record.get_value()
                total_acumulado += kwh
                resumen += f"• {area}: <b>{kwh:.2f}</b> kWh\n"
        
        resumen += f"\n🔋 <b>Total Edificio: {total_acumulado:.2f} kWh</b>"
        return resumen
    except Exception as e:
        logging.error(f"Error consultando InfluxDB: {e}")
        return "⚠️ Error al conectar con la base de datos de energía."

def get_current_status():
    """Consulta el estado del EMA y anomalías recientes."""
    try:
        conn = psycopg2.connect(
            dbname=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASS,
            host=POSTGRES_HOST
        )
        cur = conn.cursor()
        
        # Obtener últimas anomalías
        cur.execute("SELECT area, severidad, valor_kwh FROM anomalias ORDER BY timestamp DESC LIMIT 3;")
        anomalias = cur.fetchall()
        
        cur.close()
        conn.close()
        
        resumen = "⚡ <b>ESTADO DE ÁREAS</b>\n\n"
        
        if not anomalias:
            resumen += "✅ No se han detectado anomalías recientes."
        else:
            resumen += "<b>Últimas alertas:</b>\n"
            for a in anomalias:
                emoji = "🔴" if "Critico" in a[1] else "🟠"
                resumen += f"{emoji} {a[0]}: {a[2]:.2f} kWh ({a[1]})\n"
                
        return resumen
    except Exception as e:
        logging.error(f"Error consultando Postgres: {e}")
        return "⚠️ Error al conectar con la base de datos de alertas."

if __name__ == '__main__':
    if not TOKEN:
        print("❌ Error: No se encontró TELEGRAM_TOKEN en el archivo .env")
        exit(1)
        
    print("🤖 Bot de Energía iniciado (Modo Polling)...")
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ai", ai_handler))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    app.run_polling()
