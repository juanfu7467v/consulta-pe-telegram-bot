import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

import os

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_FILE = "session.session"

# Si existe sesión persistente, se carga
if os.path.exists(SESSION_FILE):
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
else:
    client = TelegramClient(StringSession(), API_ID, API_HASH)

async def start_client():
    await client.start()
    print("✅ Cliente de Telegram conectado")

# Enviar mensaje al bot de LederData
async def send_message(message):
    await start_client()
    entity = "@LEDERDATA_OFC_BOT"
    await client.send_message(entity, message)
    return "Mensaje enviado"

# Leer última respuesta del bot
async def read_response():
    entity = "@LEDERDATA_OFC_BOT"
    async for message in client.iter_messages(entity, limit=1):
        return message.text

# Guardar sesión automáticamente
async def save_session():
    if isinstance(client.session, StringSession):
        with open(SESSION_FILE, "w") as f:
            f.write(client.session.save())
        print("✅ Sesión guardada")
