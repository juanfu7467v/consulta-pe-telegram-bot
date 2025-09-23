import os
import qrcode
from io import BytesIO
from flask import Flask, request, jsonify, send_file
from telethon import TelegramClient, events
import asyncio
import threading

# --- Configuración Telegram ---
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
SESSION = "consulta_pe_session"

# --- Flask App ---
app = Flask(__name__)

# Loop de asyncio para Telethon (corriendo en un hilo aparte)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)

messages = []
qr_login = None

# Correr el loop en segundo plano
def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()


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


@app.route("/qr")
def get_qr():
    global qr_login
    async def _get_qr():
        await client.connect()
        if not await client.is_user_authorized():
            qr_login = await client.qr_login()
            qr = qrcode.make(qr_login.url)
            buf = BytesIO()
            qr.save(buf, "PNG")
            buf.seek(0)
            return buf
        else:
            return None

    fut = asyncio.run_coroutine_threadsafe(_get_qr(), loop)
    buf = fut.result()
    if buf:
        return send_file(buf, mimetype="image/png")
    else:
        return jsonify({"status": "ya vinculado"})


@app.route("/send")
def send_msg():
    chat_id = request.args.get("chat_id")
    msg = request.args.get("msg")
    if not chat_id or not msg:
        return jsonify({"error": "Faltan parámetros chat_id o msg"}), 400

    async def _send():
        entity = await client.get_entity(int(chat_id)) if chat_id.isdigit() else chat_id
        await client.send_message(entity, msg)

    fut = asyncio.run_coroutine_threadsafe(_send(), loop)
    try:
        fut.result()
        return jsonify({"status": "enviado", "to": chat_id, "msg": msg})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get")
def get_msgs():
    return jsonify(messages)


@client.on(events.NewMessage)
async def handler(event):
    messages.append({
        "from_id": event.sender_id,
        "text": event.raw_text
    })


def main():
    async def run():
        await client.connect()
        print("✅ Cliente Telegram conectado (esperando QR si no autorizado).")
    asyncio.run_coroutine_threadsafe(run(), loop)

    app.run(host="0.0.0.0", port=3000)


if __name__ == "__main__":
    main()
