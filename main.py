import os
import asyncio
import threading
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telethon import TelegramClient, events, errors
from telethon.sessions import StringSession
import traceback
import aiohttp
import subprocess

# --- Config ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "https://consulta-pe-telegram-bot.fly.dev").rstrip("/")
SESSION_STRING = os.getenv("SESSION_STRING", "")  # StringSession almacenado en secrets
PORT = int(os.getenv("PORT", 3000))
FLY_APP = os.getenv("FLY_APP", "")  # Nombre de tu app Fly.io
FLY_API_TOKEN = os.getenv("FLY_API_TOKEN", "")  # Token API de Fly.io

# Carpeta para archivos descargados
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Flask
app = Flask(__name__)
CORS(app)

# Async loop
loop = asyncio.new_event_loop()

# --- Telethon Client con StringSession ---
if SESSION_STRING:
    session = StringSession(SESSION_STRING)
else:
    session = "consulta_pe_session"  # fallback a archivo físico

client = TelegramClient(session, API_ID, API_HASH, loop=loop)

# Mensajes en memoria
messages = deque(maxlen=2000)
_messages_lock = threading.Lock()

# Login pendiente
pending_phone = {"phone": None, "sent_at": None}

# --- Loop en thread ---
def _loop_thread():
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=_loop_thread, daemon=True).start()

# --- Helper para ejecutar coroutines ---
def run_coro(coro):
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()

# --- Función para actualizar SESSION_STRING en Fly.io Secrets ---
def update_fly_secret(new_string):
    if not (FLY_APP and FLY_API_TOKEN):
        print("⚠️ Fly.io secret no se actualizó: faltan FLY_APP o FLY_API_TOKEN")
        return
    try:
        cmd = [
            "flyctl", "secrets", "set",
            f"SESSION_STRING={new_string}",
            "--app", FLY_APP
        ]
        env = os.environ.copy()
        env["FLY_API_TOKEN"] = FLY_API_TOKEN
        subprocess.run(cmd, check=True, env=env)
        print("✅ SESSION_STRING actualizado en Fly.io Secrets")
    except Exception as e:
        print("❌ Error actualizando Fly.io Secret:", e)

# --- Reconexión automática + Ping interno cada 5min ---
async def _ensure_connected():
    while True:
        try:
            if not await client.is_connected():
                await client.connect()
                print("🔌 Reconectando Telethon...")
            if await client.is_user_authorized():
                print("✅ Cliente conectado y autorizado")
            else:
                print("⚠️ Cliente no autorizado, esperando login...")
        except Exception:
            traceback.print_exc()
        # Ping interno para evitar que Fly.io duerma el contenedor
        try:
            async with aiohttp.ClientSession() as session_http:
                async with session_http.get(f"{PUBLIC_URL}/status") as resp:
                    await resp.text()
        except Exception:
            pass
        await asyncio.sleep(300)  # cada 5 minutos
asyncio.run_coroutine_threadsafe(_ensure_connected(), loop)

# --- Event handler ---
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

# ------------------- Rutas HTTP -------------------

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
    return jsonify({
        "authorized": bool(is_auth),
        "pending_phone": pending_phone["phone"]
    })

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

    result = run_coro(_send_code())
    return jsonify(result)

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
            await client.start()  # asegura sesión persistente
            pending_phone["phone"] = None
            pending_phone["sent_at"] = None
            print("✅ Sesión iniciada correctamente")
            new_string = client.session.save()
            # Auto-guardar SESSION_STRING en Fly.io Secrets
            update_fly_secret(new_string)
            return {"status": "authenticated", "session_string": new_string}
        except errors.SessionPasswordNeededError:
            return {"status": "error", "error": "2FA required"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    result = run_coro(_sign_in())
    return jsonify(result)

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
        result = run_coro(_send())
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/get")
def get_msgs():
    with _messages_lock:
        data = list(messages)
    return jsonify({
        "message": "found data" if data else "no data",
        "result": {
            "quantity": len(data),
            "coincidences": data
        }
    })

@app.route("/files/<path:filename>")
def files(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=False)

# ------------------- Run -------------------
if __name__ == "__main__":
    try:
        run_coro(client.connect())
    except Exception:
        pass

    print(f"🚀 App corriendo en http://0.0.0.0:{PORT} (PUBLIC_URL={PUBLIC_URL})")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
