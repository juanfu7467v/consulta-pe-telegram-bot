import express from "express";
import axios from "axios";
import bodyParser from "body-parser";
import dotenv from "dotenv";

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;
const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
const TELEGRAM_API = `https://api.telegram.org/bot${TELEGRAM_TOKEN}`;

let lastResponse = null; // Guardar última respuesta para AppCreator24

app.use(bodyParser.json());

// 📌 Health check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

// 📌 Webhook de Telegram (cuando alguien escribe al bot)
app.post("/webhook", async (req, res) => {
  const update = req.body;

  try {
    if (update.message) {
      const chatId = update.message.chat.id;
      const text = update.message.text || "📎 (Mensaje sin texto)";

      // Guardar la última respuesta para AppCreator24
      lastResponse = {
        chatId,
        text,
        timestamp: new Date().toISOString()
      };

      // Respuesta automática
      await axios.post(`${TELEGRAM_API}/sendMessage`, {
        chat_id: chatId,
        text: `🤖 Hola! Soy *Consulta PE Bot* y recibí tu mensaje: "${text}"`,
        parse_mode: "Markdown"
      });
    }
  } catch (error) {
    console.error("Error en webhook:", error.message);
  }

  res.sendStatus(200);
});

// 📌 Endpoint para enviar mensajes manualmente
app.post("/api/telegram/send", async (req, res) => {
  const { chatId, text } = req.body;

  if (!chatId || !text) {
    return res.status(400).json({ error: "Faltan parámetros (chatId, text)" });
  }

  try {
    const response = await axios.post(`${TELEGRAM_API}/sendMessage`, {
      chat_id: chatId,
      text
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
