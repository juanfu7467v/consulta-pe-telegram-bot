import express from "express";
import dotenv from "dotenv";
import qrcode from "qrcode";
import { TelegramClient } from "telegram";
import { StringSession } from "telegram/sessions/index.js";
import { CustomFile } from "telegram/client/uploads.js";
import { Api } from "telegram/index.js";
import { isChannel, isUser } from "telegram/tl/helpers.js";
import path from "path";
import { fileURLToPath } from "url";

dotenv.config();

const app = express();
app.use(express.json());

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessions = new Map();

// Función para inicializar y conectar el cliente de Telegram
async function createAndConnectClient(sessionId) {
  const session = sessions.get(sessionId)?.session || new StringSession("");
  const client = new TelegramClient(session, apiId, apiHash, {
    connectionRetries: 5,
  });

  client.start({
    qrCode: true,
    phoneNumber: async () => {}, // No necesitamos esto para el login con QR
    password: async () => {},
  });

  client.addQrCodeGenerator(async (qr) => {
    const dataUrl = await qrcode.toDataURL(qr.url);
    sessions.get(sessionId).qr = dataUrl;
    sessions.get(sessionId).status = "qr_generated";
    console.log(`QR code generated for session ${sessionId}`);
  });

  sessions.set(sessionId, {
    client,
    session: new StringSession(""),
    status: "starting",
    qr: null,
  });

  client.start();

  client.addEventHandler(
    async (update) => {
      if (update instanceof Api.updates.UpdateAuthorization) {
        sessions.get(sessionId).status = "connected";
        sessions.get(sessionId).qr = null;
        sessions.get(sessionId).session = new StringSession(client.session.save());
        console.log(`✅ Session ${sessionId} connected successfully.`);
      }
    }
  );

  return client;
}

// ------------------- Endpoints -------------------
app.get("/api/session/create", async (req, res) => {
  const sessionId = req.query.sessionId || `session_${Date.now()}`;
  if (sessions.has(sessionId) && sessions.get(sessionId).status !== "disconnected") {
    return res.json({
      ok: true,
      sessionId,
      status: sessions.get(sessionId).status,
      qr: sessions.get(sessionId).qr,
    });
  }
  
  await createAndConnectClient(sessionId);
  res.json({ ok: true, sessionId, status: "starting" });
});

app.get("/api/session/qr", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);
  if (!session) {
    return res.status(404).json({ ok: false, error: "Session not found." });
  }
  res.json({ ok: true, status: session.status, qr: session.qr });
});

app.post("/api/message/send", async (req, res) => {
  const { sessionId, target, message, file_url } = req.body;
  const session = sessions.get(sessionId);
  
  if (!session || session.status !== "connected") {
    return res.status(400).json({ ok: false, error: "Session is not connected." });
  }

  const client = session.client;
  let peer = null;

  try {
    // Intenta encontrar la entidad por username, número de teléfono o ID
    peer = await client.getEntity(target);
  } catch (e) {
    console.error(`Error finding entity for target '${target}':`, e.message);
    return res.status(404).json({ ok: false, error: `Could not find a user, channel, or group for '${target}'.` });
  }

  const sendMessageOptions = {
    message: message,
  };

  if (file_url) {
    try {
      const filePath = path.join(__dirname, "temp_files", path.basename(file_url));
      // En un entorno de producción, descargarías el archivo desde la URL a una carpeta temporal.
      // Para este ejemplo, asumimos que el archivo ya existe en el disco para fines de demostración.
      // Aquí, solo simulamos el path.
      
      sendMessageOptions.file = new CustomFile(path.basename(file_url), null, path.dirname(filePath), filePath);
    } catch (e) {
      console.error("Error creating CustomFile:", e.message);
      return res.status(500).json({ ok: false, error: "Error processing the file URL." });
    }
  }

  try {
    await client.sendMessage(peer, sendMessageOptions);
    res.json({ ok: true, message: "Message sent successfully." });
  } catch (e) {
    console.error("Error sending message:", e.message);
    res.status(500).json({ ok: false, error: `Failed to send message: ${e.message}` });
  }
});

app.get("/api/session/reset", async (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);
  
  if (session) {
    session.client.disconnect();
    sessions.delete(sessionId);
  }
  res.json({ ok: true, message: "Session reset." });
});

app.get("/", (req, res) => {
  res.send(`
    <h1>Telegram User Bot Interface</h1>
    <p>Use the following endpoints to manage your session:</p>
    <ul>
      <li>GET /api/session/create?sessionId=your_session_id</li>
      <li>GET /api/session/qr?sessionId=your_session_id</li>
      <li>POST /api/message/send (body: { sessionId, target, message, file_url? })</li>
      <li>GET /api/session/reset?sessionId=your_session_id</li>
    </ul>
    <p>Visit /api/session/create to start a new session and get a QR code.</p>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server is running on port ${PORT}`);
});
