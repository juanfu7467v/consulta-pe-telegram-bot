import express from "express";
import dotenv from "dotenv";
import qrcode from "qrcode";
import cors from "cors";
import { TelegramClient } from "telegram";
import { StringSession } from "telegram/sessions/index.js";

dotenv.config();

const app = express();
app.use(cors({ origin: "*", methods: ["GET"] }));
app.use(express.json());

// Credenciales de tu app en my.telegram.org
const apiId = parseInt(process.env.API_ID);
const apiHash = process.env.API_HASH;

// Manejador de sesiones en memoria
const sessions = new Map();

// ------------------- Crear sesión -------------------
app.get("/api/session/create", async (req, res) => {
  const sessionId = req.query.sessionId || `session_${Date.now()}`;

  if (sessions.has(sessionId)) {
    return res.json({
      ok: true,
      sessionId,
      status: sessions.get(sessionId).status,
    });
  }

  const stringSession = new StringSession("");
  const client = new TelegramClient(stringSession, apiId, apiHash, {
    connectionRetries: 5,
  });

  sessions.set(sessionId, {
    client,
    session: stringSession,
    status: "starting",
    qr: null,
    inbox: [],
  });

  // Arrancamos sin marcar como "connected"
  client
    .start({
      qrCode: async (qr) => {
        const qrData = await qrcode.toDataURL(qr);
        const data = sessions.get(sessionId);
        if (data) {
          data.qr = qrData;
          data.status = "qr_generated";
          console.log(`📲 QR listo para ${sessionId}`);
        }
      },
      phoneNumber: async () => "",
      password: async () => "",
    })
    .then(() => {
      const data = sessions.get(sessionId);
      if (data) {
        data.status = "connected";
        console.log(`✅ Sesión ${sessionId} conectada`);
      }

      // Manejo de mensajes entrantes
      client.addEventHandler((update) => {
        if (update.message && update.message.message) {
          const msg = {
            from: update.message.senderId?.toString(),
            text: update.message.message,
            date: new Date().toISOString(),
          };
          const d = sessions.get(sessionId);
          if (d) d.inbox.push(msg);
          console.log("📥 Nuevo mensaje recibido:", msg);
        }
      });
    })
    .catch((err) => {
      console.error("❌ Error en login:", err);
      const data = sessions.get(sessionId);
      if (data) data.status = "error";
    });

  res.json({ ok: true, sessionId, status: "starting" });
});

// ------------------- Obtener QR -------------------
app.get("/api/session/qr", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);

  if (!session) return res.status(404).json({ ok: false, error: "No existe la sesión" });

  if (!session.qr) {
    return res.json({ ok: false, status: session.status, message: "⚠️ Aún no se ha generado el QR. Intenta de nuevo en unos segundos." });
  }

  res.json({ ok: true, status: session.status, qr: session.qr });
});

// ------------------- Enviar mensaje -------------------
app.get("/api/message/send", async (req, res) => {
  const { sessionId, target, message } = req.query;
  const session = sessions.get(sessionId);

  if (!session || session.status !== "connected") {
    return res.status(400).json({ ok: false, error: "Sesión no conectada" });
  }

  try {
    const entity = await session.client.getEntity(target);
    await session.client.sendMessage(entity, { message });
    res.json({ ok: true, sent: { target, message } });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// ------------------- Recibir mensajes -------------------
app.get("/api/message/inbox", (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);

  if (!session) return res.status(404).json({ ok: false, error: "Sesión no encontrada" });

  res.json({ ok: true, inbox: session.inbox });
});

// ------------------- Resetear sesión -------------------
app.get("/api/session/reset", async (req, res) => {
  const { sessionId } = req.query;
  const session = sessions.get(sessionId);

  if (session) {
    await session.client.disconnect();
    sessions.delete(sessionId);
  }
  res.json({ ok: true, message: "Sesión eliminada" });
});

// ------------------- Página base -------------------
app.get("/", (req, res) => {
  res.send(`
    <h2>Telegram Bot con Endpoints</h2>
    <ul>
      <li>/api/session/create?sessionId=tu_sesion</li>
      <li>/api/session/qr?sessionId=tu_sesion</li>
      <li>/api/message/send?sessionId=tu_sesion&target=@usuario&message=hola</li>
      <li>/api/message/inbox?sessionId=tu_sesion</li>
      <li>/api/session/reset?sessionId=tu_sesion</li>
    </ul>
  `);
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, "0.0.0.0", () => {
  console.log(`🚀 Server ready at http://localhost:${PORT}`);
});
