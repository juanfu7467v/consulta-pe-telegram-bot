# Imagen base de Python
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Aquí usamos sh -c para que se expanda $PORT
CMD ["sh", "-c", "gunicorn -w 4 -b 0.0.0.0:${PORT} main:app"]
