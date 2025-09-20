from telethon import TelegramClient, events
import os
from dotenv import load_dotenv

# Cargar .env
load_dotenv()

api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
phone = os.getenv("PHONE_NUMBER")

# Cliente (sesión persistente)
client = TelegramClient("session_lederdata", api_id, api_hash)

# Última respuesta del bot
last_response = {"from": None, "text": None, "timestamp": None}

async def start_client():
    """Inicia sesión en Telegram con tu número."""
    await client.start(phone)
    print("✅ Cliente de Telegram conectado como usuario real")

@client.on(events.NewMessage(from_users="lederdata_bot"))
async def handler(event):
    """Escucha respuestas de lederdata_bot."""
    global last_response
    last_response = {
        "from": "lederdata_bot",
        "text": event.text,
        "timestamp": event.date.isoformat()
    }
    print("📩 Respuesta de lederdata_bot:", event.text)

async def send_message(text: str):
    """Enviar mensaje al bot lederdata_bot."""
    await client.send_message("lederdata_bot", text)
    return {"success": True, "sent": text}
