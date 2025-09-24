# Imagen base de Python
FROM python:3.11-slim

# Carpeta de trabajo
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto (Railway ignora este EXPOSE, pero sirve localmente)
EXPOSE 8080

# Comando de inicio
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "main:app"]
