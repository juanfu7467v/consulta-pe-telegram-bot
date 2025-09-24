# Imagen base ligera de Python
FROM python:3.11-slim

# Evita problemas de buffering
ENV PYTHONUNBUFFERED=1

# Crea un directorio de trabajo
WORKDIR /app

# Copia e instala dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo el proyecto
COPY . .

# Crea carpeta para descargas (por seguridad)
RUN mkdir -p downloads

# Puerto (Railway usará su propia variable $PORT)
EXPOSE 8000

# Comando de inicio con Gunicorn, usando $PORT de Railway
CMD gunicorn main:app --bind 0.0.0.0:$PORT --workers 1 --threads 8
