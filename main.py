# main.py
import os
import asyncio
import threading
import traceback
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from telethon import TelegramClient, events

# --- Config (asegúrate de configurar estas variables en Railway/entorno) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost").rstrip("/")
SESSION = os.getenv("SESSION", "consulta_pe_session")
PORT = int(os.getenv("PORT", "8080"))  # Railway asigna dinámico

# Validaciones básicas
if API_ID == 0 or API_HASH == "":
    print("⚠️ ADVERTENCIA: API_ID o API_HASH no están configurados. Define las secrets API_ID y API_HASH.")

# Carpeta de descargas
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Flask
app = Flask(__name__)
CORS(app)

# Cola de mensajes en memoria (thread-safe)
messages = deque(maxlen=2000)
_messages_lock = threading.Lock()

# Telethon (se crean *por worker* al arrancar lazy)
_client = None           # instancia TelegramClient por worker
_loop = None             # event loop por worker
_telethon_started = False
_start_lock = threading.Lock()


def _start_telethon(timeout: int = 20) -> bool:
    """
    Inicia Telethon en este proceso/worker si no está iniciado.
    Devuelve True si el cliente quedó conectado (o ya estaba conectado).
    """
    global _client, _loop, _telethon_started

    with _start_lock:
        if _telethon_started:
            return True

        if API_ID == 0 or API_HASH == "":
            print("❌ No se puede iniciar Telethon: falta API_ID / API_HASH")
            return False

        # Crear loop y cliente (se hacen aquí, no en el import)
        _loop = asyncio.new_event_loop()

        # Thread que ejecuta el loop (daemon para que termine con el worker)
        def _run_loop():
            try:
                asyncio.set_event_loop(_loop)
                _loop.run_forever()
            except Exception:
                traceback.print_exc()

        thread = threading.Thread(target=_run_loop, daemon=True)
        thread.start()

        # Crear cliente con el loop recién creado
        _client = TelegramClient(SESSION, API_ID, API_HASH, loop=_loop)

        # registrar handler de mensajes
        @ _client.on(events.NewMessage(incoming=True))
        async def _on_new_message(event):
            try:
                msg_obj = {
                    "chat_id": getattr(event, "chat_id", None),
                    "from_id": event.sender_id,
                    "date": (
                        event.message.date.isoformat()
                        if getattr(event, "message", None) and getattr(event.message, "date", None)
                        else datetime.utcnow().isoformat()
                    ),
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

                print("📥 Nuevo mensaje registrado:", msg_obj)
            except Exception:
                traceback.print_exc()

        # Conectar (sync esperando un máximo)
        try:
            fut = asyncio.run_coroutine_threadsafe(_client.connect(), _loop)
            fut.result(timeout=timeout)
            # Comprobar autorización (no bloqueante largo)
            try:
                auth_fut = asyncio.run_coroutine_threadsafe(_client.is_user_authorized(), _loop)
                is_auth = auth_fut.result(timeout=5)
            except Exception:
                is_auth = False
            _telethon_started = True
            print("✅ Telethon: conectado. Autorizado?:", bool(is_auth))
            return True
        except Exception as e:
            print("❌ Error iniciando Telethon:", e)
            traceback.print_exc()
            return False


def _ensure_telethon_started():
    """Helper que intenta iniciar Telethon y lanza excepción si no se pudo."""
    ok = _start_telethon()
    if not ok:
        raise RuntimeError("No se pudo iniciar Telethon. Revisa API_ID/API_HASH y logs.")


def run_coro(coro, timeout: int = 20):
    """Ejecuta una coroutine en el loop de Telethon del worker (asegura inicio)."""
    if not _telethon_started:
        _ensure_telethon_started()
    fut = asyncio.run_coroutine_threadsafe(coro, _loop)
    return fut.result(timeout=timeout)


# ------------------- Endpoints -------------------

@app.route("/")
def root():
    return jsonify({
        "status": "ok",
        "public_url": PUBLIC_URL,
        "endpoints": {
            "/status": "Estado y si está autorizado",
            "/login?phone=+51...": "Solicita código SMS/Telegram",
            "/code?code=12345": "Confirma código recibido",
            "/send?chat_id=@user&msg=hola": "Enviar mensaje",
            "/get": "Obtener mensajes (polling)",
            "/files/<filename>": "Descargar archivos recibidos"
        }
    })


@app.route("/status")
def status():
    try:
        if not _telethon_started:
            started = _start_telethon()
            authorized = False
            if started:
                authorized = run_coro(_client.is_user_authorized(), timeout=5)
        else:
            authorized = run_coro(_client.is_user_authorized(), timeout=5)
    except Exception:
        authorized = False
    return jsonify({"authorized": bool(authorized)})


@app.route("/login")
def login():
    phone = request.args.get("phone")
    if not phone:
        return jsonify({"error": "Falta parámetro phone"}), 400
    try:
        _ensure_telethon_started()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

    async def _send_code():
        if await _client.is_user_authorized():
            return {"status": "already_authorized"}
        await _client.send_code_request(phone)
        return {"status": "code_sent", "phone": phone}

    try:
        result = run_coro(_send_code())
        # guardamos phone para /code en memoria sencilla (no persistente)
        # Nota: en este código no guardamos en variable global el phone; Telethon requiere el phone param on sign_in
        # Para flows más robustos, guarda pending_phone en DB o variable.
        # Aquí asumimos que el usuario recuerda el phone ingresado.
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/code")
def code():
    code = request.args.get("code")
    phone = request.args.get("phone")  # mejor que se envíe phone también en /code
    if not code or not phone:
        return jsonify({"error": "Faltan parámetros code o phone (envía ambos)"}), 400

    try:
        _ensure_telethon_started()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

    async def _sign_in():
        try:
            await _client.sign_in(phone, code)
            await _client.start()
            return {"status": "authenticated"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    try:
        result = run_coro(_sign_in())
        return jsonify(result)
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/send")
def send_msg():
    chat_id = request.args.get("chat_id")
    msg = request.args.get("msg")
    if not chat_id or not msg:
        return jsonify({"error": "Faltan parámetros chat_id o msg"}), 400

    try:
        _ensure_telethon_started()
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

    async def _send():
        target = int(chat_id) if chat_id.isdigit() else chat_id
        entity = await _client.get_entity(target)
        await _client.send_message(entity, msg)
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
def file_serve(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=False)


# Local run (útil para pruebas)
if __name__ == "__main__":
    # arrancar Telethon localmente para dev (no obligatorio)
    try:
        _start_telethon()
    except Exception:
        pass
    print(f"🚀 App corriendo en 0.0.0.0:{PORT} (PUBLIC_URL={PUBLIC_URL})")
    app.run(host="0.0.0.0", port=PORT)
