import os
import asyncio
import threading
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telethon import TelegramClient, events
import traceback

# --- Config ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost").rstrip("/")
SESSION = os.getenv("SESSION", "consulta_pe_session")

# Carpeta de descargas
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Flask
app = Flask(__name__)
CORS(app)

# Cola de mensajes en memoria
messages = deque(maxlen=2000)
_messages_lock = threading.Lock()
pending_phone = {"phone": None, "sent_at": None}

# --- Loop asyncio + Telethon ---
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)

def _loop_thread():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_loop_thread, daemon=True).start()

def run_coro(coro):
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()

# --- Handlers ---
async def _on_new_message(event):
    try:
        msg_obj = {
            "chat_id": getattr(event, "chat_id", None),
            "from_id": event.sender_id,
            "date": event.message.date.isoformat() if getattr(event, "message", None) else datetime.utcnow().isoformat(),
        }
        if getattr(event, "raw_text", None):
            msg_obj["message"] = event.raw_text
        if getattr(event, "message", None) and getattr(event.message, "media", None):
            try:
                saved_path = await event.download_media(file=DOWNLOAD_DIR)
                filename = os.path.basename(saved_path)
                msg_obj["url"] = f"{PUBLIC_URL}/files/{filename}"
            except Exception as e:
                msg_obj["media_error"] = str(e)
        with _messages_lock:
            messages.appendleft(msg_obj)
        print("📥 Nuevo mensaje:", msg_obj)
    except Exception:
        traceback.print_exc()

client.add_event_handler(_on_new_message, events.NewMessage(incoming=True))

# --- Rutas HTTP ---
@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "public_url": PUBLIC_URL,
        "endpoints": {
            "/login?phone=+51...": "Solicita código",
            "/code?code=12345": "Confirma código",
            "/send?chat_id=@user&msg=hola": "Enviar mensaje",
            "/get": "Obtener mensajes",
            "/files/<filename>": "Descargar archivos"
        }
    })

@app.route("/status")
def status():
    try:
        is_auth = run_coro(client.is_user_authorized())
    except Exception:
        is_auth = False
    return jsonify({"authorized": bool(is_auth), "pending_phone": pending_phone["phone"]})

@app.route("/login")
def login():
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"error": "Falta parámetro phone"}), 400

    async def _send_code():
        await client.connect()
        if await client.is_user_authorized():
            return {"status": "already_authorized"}
        try:
            await client.send_code_request(phone)
            pending_phone["phone"] = phone
            pending_phone["sent_at"] = datetime.utcnow().isoformat()
            return {"status": "code_sent", "phone": phone}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return jsonify(run_coro(_send_code()))

@app.route("/code")
def code():
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Falta parámetro code"}), 400
    if not pending_phone["phone"]:
        return jsonify({"error": "No hay login pendiente"}), 400

    phone = pending_phone["phone"]

    async def _sign_in():
        try:
            await client.sign_in(phone, code)
            await client.start()
            pending_phone["phone"] = None
            pending_phone["sent_at"] = None
            return {"status": "authenticated"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    return jsonify(run_coro(_sign_in()))

@app.route("/send")
def send_msg():
    chat_id = request.args.get("chat_id")
    msg = request.args.get("msg")
    if not chat_id or not msg:
        return jsonify({"error": "Faltan parámetros chat_id o msg"}), 400

    async def _send():
        target = int(chat_id) if chat_id.isdigit() else chat_id
        entity = await client.get_entity(target)
        await client.send_message(entity, msg)
        return {"status": "sent", "to": chat_id, "msg": msg}

    try:
        return jsonify(run_coro(_send()))
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/get")
def get_msgs():
    with _messages_lock:
        data = list(messages)
    return jsonify({"message": "found data" if data else "no data",
                    "result": {"quantity": len(data), "coincidences": data}})

@app.route("/files/<path:filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=False)

# --- Startup ---
def init_telethon():
    try:
        run_coro(client.connect())
        print("✅ Telethon conectado correctamente")
    except Exception as e:
        print("❌ Error iniciando Telethon:", e)

init_telethon()

# Importante: NO usar app.run() porque Gunicorn se encarga de levantar el servidor
