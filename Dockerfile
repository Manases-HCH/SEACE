FROM python:3.11-slim

# Instalar dependencias del sistema, Chromium y su Driver
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Definir rutas para que Selenium las encuentre siempre
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER=/usr/bin/chromedriver
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run requiere el puerto 8080
ENV PORT=8080
EXPOSE 8080

CMD ["python", "app.py"]
