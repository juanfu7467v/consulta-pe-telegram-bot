import express from "express";
import axios from "axios";
import dotenv from "dotenv";
import cors from "cors";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;
const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
const TELEGRAM_API = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`;

let lastResponse = null; // Guardar última respuesta para AppCreator24

// ✅ Activar CORS para todas las rutas
app.use(cors());

// Middleware para leer JSON
app.use(express.json());

// 📌 Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// 📌 Webhook de Telegram (se debe usar POST desde Telegram)
app.post("/webhook", async (req, res) => {
  try {
    const message = req.body.message;

    if (!message) {
      return res.json({ success: false, message: "No hay mensaje en el body" });
    }

    const chatId = message.chat.id;
    const text = message.text || "📎 (Mensaje sin texto)";

    // Guardar la última respuesta
    lastResponse = {
      chatId,
      text,
      timestamp: new Date().toISOString(),
    };

    // Respuesta automática
    await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text: `🤖 Hola! Soy *Consulta PE Bot* y recibí tu mensaje: "${text}"`,
      parse_mode: "Markdown",
    });

    return res.json({ success: true, message: "Mensaje procesado" });
  } catch (error) {
    console.error("Error en webhook:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// 📌 Endpoint para enviar mensajes manualmente (usando GET para AppCreator24)
app.get("/api/telegram/send", async (req, res) => {
  const { chatId, text } = req.query;

  if (!chatId || !text) {
    return res.json({ success: false, message: "Faltan parámetros (chatId, text)" });
  }

  try {
    // ⚡ Importante: aquí usamos axios.post para Telegram, pero la entrada sigue siendo GET
    const response = await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text,
    });

    res.json({ success: true, result: response.data });
  } catch (error) {
    console.error("Error enviando mensaje:", error.message);
    res.status(500).json({ error: error.message });
  }
});

// 📌 Endpoint para consultar última respuesta
app.get("/api/last-response", (req, res) => {
  if (lastResponse) {
    res.json({ success: true, lastResponse });
  } else {
    res.json({ success: false, message: "Aún no hay respuestas guardadas" });
  }
});

app.listen(PORT, () => {
  console.log(`🚀 Servidor corriendo en http://localhost:${PORT}`);
});
