from flask import Flask, request, jsonify
from telegram_client import client, send_message, read_response
import asyncio

app = Flask(__name__)

@app.route("/send_command", methods=["POST"])
def send_command():
    data = request.json
    command = data.get("command")
    if not command:
        return jsonify({"error": "No command provided"}), 400

    # Enviar comando y obtener respuesta
    try:
        response = asyncio.run(send_message(command))
        result = asyncio.run(read_response())
        return jsonify({"status": "success", "response": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/")
def home():
    return "✅ Bot puente activo. Usa POST /send_command con JSON {command: '...' }"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
