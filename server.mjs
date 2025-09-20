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

// Middlewares
app.use(cors());
app.use(express.json());

// 📌 Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// 📌 Webhook de Telegram (POST)
app.post("/webhook", async (req, res) => {
  try {
    const message = req.body?.message;

    if (!message || !message.chat?.id) {
      return res.status(400).json({ success: false, message: "Mensaje inválido" });
    }

    const chatId = message.chat.id;
    const text = message.text?.trim() || "📎 (Mensaje sin texto)";

    // Guardar última respuesta
    lastResponse = {
      chatId,
      text,
      timestamp: new Date().toISOString(),
    };

    // Respuesta automática
    await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text: `🤖 Hola! Soy *Consulta PE Bot* y recibí tu mensaje:\n\n"${text}"`,
      parse_mode: "Markdown",
    });

    // Telegram espera status 200
    return res.status(200).json({ success: true, message: "Mensaje procesado" });
  } catch (error) {
    console.error("❌ Error en webhook:", error.response?.data || error.message);
    res.status(500).json({ error: error.message });
  }
});

// 📌 Endpoint para enviar mensajes manualmente (GET, para AppCreator24)
app.get("/api/telegram/send", async (req, res) => {
  try {
    const { chatId, text } = req.query;

    if (!chatId || !text) {
      return res.json({ success: false, message: "Faltan parámetros (chatId, text)" });
    }

    const response = await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text: text.trim(),
    });

    res.json({ success: true, result: response.data });
  } catch (error) {
    console.error("❌ Error enviando mensaje:", error.response?.data || error.message);
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
