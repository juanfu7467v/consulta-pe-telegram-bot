# Imagen base de Python
FROM python:3.11-slim

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
