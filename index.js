import express from "express";
import dotenv from "dotenv";
import qrcode from "qrcode";
import cors from "cors";
import { TelegramClient } from "telegram";
import { StringSession } from "telegram/sessions/index.js";
import { NewMessage } from "telegram/events/index.js";

dotenv.config();

const app = express();
app.use(cors({ origin: "*" }));
app.use(express.json());

const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;
const sessions = new Map();

// ------------------- Crear sesión -------------------
app.get("/api/session/create", async (req, res) => {
  const sessionId = req.query.sessionId || `session_${Date.now()}`;
  if (sessions.has(sessionId)) {
    return res.json({ ok: true, sessionId, status: sessions.get(sessionId).status });
  }

  const stringSession = new StringSession("");
  const client = new TelegramClient(stringSession, apiId, apiHash, { connectionRetries: 5 });
  await client.connect();

  sessions.set(sessionId, {
    client,
    session: stringSession,
    status: "waiting_qr",
    qr: null,
    inbox: [],
  });

  try {
    const qrLogin = await client.qrLogin({ apiId, apiHash });
    qrLogin.generate().then(async (qrBytes) => {
      const qrData = await qrcode.toDataURL(qrBytes.toString("utf-8"));
      const data = sessions.get(sessionId);
      if (data) {
        data.qr = qrData;
        data.status = "qr_generated";
        console.log(`📲 QR listo para ${sessionId}`);
      }
    });

    qrLogin.wait().then(async (user) => {
      const data = sessions.get(sessionId);
      if (data) {
        data.status = "connected";
        console.log(`✅ Sesión ${sessionId} conectada como ${user.firstName}`);
      }

      // Capturar mensajes
      client.addEventHandler(async (event) => {
        const msg = {
          from: event.message.senderId?.toString(),
          text: event.message.message,
          date: new Date().toISOString(),
        };
        const d = sessions.get(sessionId);
        if (d) d.inbox.push(msg);
        console.log("📥 Nuevo mensaje recibido:", msg);
      }, new NewMessage({}));
    });
  } catch (err) {
    console.error("❌ Error en QR login:", err);
    sessions.get(sessionId).status = "error";
  }

  res.json({ ok: true, sessionId, status: "waiting_qr" });
});

// ------------------- Obtener QR -------------------
app.get("/api/session/qr", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);

  if (!session) return res.status(404).json({ ok: false, error: "No existe la sesión" });

  if (!session.qr) {
    return res.json({ ok: false, status: session.status, message: "⚠️ Aún no se ha generado el QR." });
  }

  res.json({ ok: true, status: session.status, qr: session.qr });
});

// ------------------- Enviar mensaje -------------------
app.get("/api/message/send", async (req, res) => {
  const { sessionId, to, text } = req.query;
  const session = sessions.get(sessionId);
  if (!session || session.status !== "connected") {
    return res.status(400).json({ ok: false, error: "Sesión no conectada" });
  }

  try {
    await session.client.sendMessage(to, { message: text });
    res.json({ ok: true, message: "Mensaje enviado" });
  } catch (err) {
    console.error(err);
    res.status(500).json({ ok: false, error: err.message });
  }
});

// ------------------- Bandeja de entrada -------------------
app.get("/api/message/inbox", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);
  if (!session) return res.status(404).json({ ok: false, error: "No existe la sesión" });
  res.json({ ok: true, inbox: session.inbox });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Servidor escuchando en puerto ${PORT}`);
});
