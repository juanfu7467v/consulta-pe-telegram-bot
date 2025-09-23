import express from "express";
import dotenv from "dotenv";
import qrcode from "qrcode";
import { TelegramClient } from "telegram";
import { StringSession } from "telegram/sessions/index.js";
import { CustomFile } from "telegram/client/uploads.js";
import { Api } from "telegram/index.js";
import path from "path";
import { fileURLToPath } from "url";
import cors from "cors";

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors({ origin: "*", methods: ["GET"] })); // habilitar CORS para AppCreator24

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessions = new Map();

// ------------------- Función para crear sesión -------------------
async function createAndConnectClient(sessionId) {
  const session = sessions.get(sessionId)?.session || new StringSession("");
  const client = new TelegramClient(session, apiId, apiHash, {
    connectionRetries: 5,
  });

  sessions.set(sessionId, {
    client,
    session,
    status: "starting",
    qr: null,
  });

  await client.start({
    qrCode: async (qr) => {
      const dataUrl = await qrcode.toDataURL(qr);
      const sessionData = sessions.get(sessionId);
      if (sessionData) {
        sessionData.qr = dataUrl;
        sessionData.status = "qr_generated";
      }
      console.log(`📲 QR code generated for session ${sessionId}`);
    },
    phoneNumber: async () => {
      console.log("⚠️ Se intentó pedir número de teléfono.");
      return "";
    },
    password: async () => {
      console.log("⚠️ Se intentó pedir contraseña de 2FA.");
      return "";
    },
  });

  client.addEventHandler(async (update) => {
    if (update instanceof Api.UpdateAuthorizationState) {
      const sessionData = sessions.get(sessionId);
      if (sessionData) {
        sessionData.status = "connected";
        sessionData.qr = null;
        sessionData.session = new StringSession(client.session.save());
        console.log(`✅ Session ${sessionId} connected successfully.`);
      }
    }
  });

  return client;
}

// ------------------- Endpoints -------------------

// Crear sesión
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

// Obtener QR
app.get("/api/session/qr", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);
  if (!session) {
    return res.status(404).json({ ok: false, error: "Session not found." });
  }
  res.json({ ok: true, status: session.status, qr: session.qr });
});

// Enviar mensaje (GET con parámetros para AppCreator24)
app.get("/api/message/send", async (req, res) => {
  const { sessionId, target, message, file_url } = req.query;
  const session = sessions.get(sessionId);

  if (!session || session.status !== "connected") {
    return res.status(400).json({ ok: false, error: "Session is not connected." });
  }

  const client = session.client;

  try {
    const peer = await client.getEntity(target);

    const sendMessageOptions = { message };

    if (file_url) {
      try {
        const filePath = path.join(__dirname, "temp_files", path.basename(file_url));
        sendMessageOptions.file = new CustomFile(
          path.basename(file_url),
          null,
          path.dirname(filePath),
          filePath
        );
      } catch (e) {
        console.error("❌ Error creating CustomFile:", e.message);
        return res.status(500).json({ ok: false, error: "Error processing the file URL." });
      }
    }

    await client.sendMessage(peer, sendMessageOptions);
    res.json({ ok: true, message: "Message sent successfully." });
  } catch (e) {
    console.error("❌ Error sending message:", e.message);
    res.status(500).json({ ok: false, error: `Failed to send message: ${e.message}` });
  }
});

// Resetear sesión
app.get("/api/session/reset", async (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);

  if (session) {
    await session.client.disconnect();
    sessions.delete(sessionId);
  }
  res.json({ ok: true, message: "Session reset." });
});

// Página de inicio
app.get("/", (req, res) => {
  res.send(`
    <h1>Telegram User Bot Interface</h1>
    <p>Use the following endpoints to manage your session:</p>
    <ul>
      <li>GET /api/session/create?sessionId=your_session_id</li>
      <li>GET /api/session/qr?sessionId=your_session_id</li>
      <li>GET /api/message/send?sessionId=your_session_id&target=usuario&message=hola</li>
      <li>GET /api/session/reset?sessionId=your_session_id</li>
    </ul>
    <p>Visit <a href="/api/session/create" target="_blank">/api/session/create</a> to start a new session and generate a QR code.</p>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Server is running on port ${PORT}`);
});
