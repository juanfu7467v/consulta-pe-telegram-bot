import os
import qrcode
from io import BytesIO
from flask import Flask, request, jsonify, send_file
from telethon import TelegramClient, events
import asyncio

# --- Configuración Telegram ---
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))   # Consigue esto en https://my.telegram.org
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
SESSION = "consulta_pe_session"

# --- Flask App ---
app = Flask(__name__)

# Loop de asyncio para Telethon
loop = asyncio.get_event_loop()
client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)

# Para almacenar mensajes recibidos
messages = []

@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "endpoints": {
            "/qr": "Genera código QR para iniciar sesión",
            "/send?chat_id=ID&msg=Hola": "Enviar mensaje",
            "/get": "Obtener mensajes recibidos"
        }
    })

# Endpoint para obtener el QR
@app.route("/qr")
async def get_qr():
    qr_login = await client.qr_login()
    qr = qrcode.make(qr_login.url)
    buf = BytesIO()
    qr.save(buf, "PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

# Endpoint para enviar mensajes
@app.route("/send")
async def send_msg():
    chat_id = request.args.get("chat_id")
    msg = request.args.get("msg")
    if not chat_id or not msg:
        return jsonify({"error": "Faltan parámetros chat_id o msg"}), 400
    try:
        entity = await client.get_entity(int(chat_id)) if chat_id.isdigit() else chat_id
        await client.send_message(entity, msg)
        return jsonify({"status": "enviado", "to": chat_id, "msg": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Endpoint para obtener mensajes recibidos
@app.route("/get")
def get_msgs():
    return jsonify(messages)

# Evento cuando llega un mensaje
@client.on(events.NewMessage)
async def handler(event):
    messages.append({
        "from_id": event.sender_id,
        "text": event.raw_text
    })

# Arrancar Flask y Telethon juntos
def main():
    async def run():
        await client.start()
        print("✅ Cliente Telegram conectado.")
        app.run(host="0.0.0.0", port=3000)

    loop.run_until_complete(run())

if __name__ == "__main__":
    main()
