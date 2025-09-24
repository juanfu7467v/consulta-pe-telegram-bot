# Imagen base ligera de Python
FROM python:3.11-slim

# Evita problemas de buffering
ENV PYTHONUNBUFFERED=1

# Crea directorio de trabajo
WORKDIR /app

# Instala dependencias del sistema necesarias para Telethon y Flask
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia dependencias Python
COPY requirements.txt .

# Instala dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del proyecto
COPY . .

# Carpeta de descargas
RUN mkdir -p downloads

# Puerto expuesto (Railway usa $PORT)
EXPOSE 8080

# Arranque con Gunicorn
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers=1", "--threads=8"]
