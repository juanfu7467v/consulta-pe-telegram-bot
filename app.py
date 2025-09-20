from flask import Flask, request, jsonify
from telegram_client import client, start_client, send_message, last_response
import asyncio

app = Flask(__name__)

# Inicializar cliente de Telegram en segundo plano
loop = asyncio.get_event_loop()
loop.run_until_complete(start_client())

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "uptime": "api funcionando 🚀"})

@app.route("/api/send", methods=["GET"])
def send():
    text = request.args.get("text")
    if not text:
        return jsonify({"success": False, "message": "Falta el parámetro text"})
    
    loop.create_task(send_message(text))
    return jsonify({"success": True, "message": f"Enviado: {text}"})

@app.route("/api/last-response", methods=["GET"])
def last_resp():
    if last_response["text"]:
        return jsonify({"success": True, "lastResponse": last_response})
    return jsonify({"success": False, "message": "Aún no hay respuestas guardadas"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
