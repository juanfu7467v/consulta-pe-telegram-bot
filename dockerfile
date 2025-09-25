# Imagen base oficial de Python (más estable para Fly.io)
FROM python:3.11-bullseye

# Carpeta de trabajo
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto
EXPOSE 3000

# Comando
CMD ["python", "main.py"]
