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

# Puerto expuesto (Railway asigna $PORT automáticamente)
EXPOSE 8080

# Comando de inicio con Gunicorn
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8"]
