import os
from flask import Flask, request, jsonify
from telethon import TelegramClient, events
import asyncio
import threading

# --- Configuración Telegram ---
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
SESSION = "consulta_pe_session"

app = Flask(__name__)

# Loop de asyncio en segundo plano
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)

messages = []
pending_phone = None  # Guardamos el número en espera de confirmación

# Correr loop en segundo plano
def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

# --- Rutas ---
@app.route("/")
def index():
    return jsonify({
        "status": "ok",
        "endpoints": {
            "/login?phone=+51987654321": "Iniciar sesión con número",
            "/code?code=12345": "Confirmar código SMS",
            "/send?chat_id=ID&msg=Hola": "Enviar mensaje",
            "/get": "Obtener mensajes recibidos"
        }
    })

@app.route("/login")
def login():
    global pending_phone
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"error": "Falta parámetro phone"}), 400

    async def _send_code():
        global pending_phone
        await client.connect()
        if not await client.is_user_authorized():
            pending_phone = phone
            await client.send_code_request(phone)
            return {"status": "codigo enviado", "phone": phone}
        else:
            return {"status": "ya autorizado"}

    fut = asyncio.run_coroutine_threadsafe(_send_code(), loop)
    return jsonify(fut.result())

@app.route("/code")
def code():
    global pending_phone
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Falta parámetro code"}), 400
    if not pending_phone:
        return jsonify({"error": "No hay login pendiente"}), 400

    async def _sign_in():
        global pending_phone
        try:
            await client.sign_in(pending_phone, code)
            pending_phone = None
            return {"status": "autenticado"}
        except Exception as e:
            return {"error": str(e)}

    fut = asyncio.run_coroutine_threadsafe(_sign_in(), loop)
    return jsonify(fut.result())

@app.route("/send")
def send_msg():
    chat_id = request.args.get("chat_id")
    msg = request.args.get("msg")
    if not chat_id or not msg:
        return jsonify({"error": "Faltan parámetros"}), 400

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

# --- Iniciar ---
def main():
    async def run():
        await client.connect()
        print("✅ Cliente Telegram corriendo (esperando login).")
    asyncio.run_coroutine_threadsafe(run(), loop)
    app.run(host="0.0.0.0", port=3000)

if __name__ == "__main__":
    main()
