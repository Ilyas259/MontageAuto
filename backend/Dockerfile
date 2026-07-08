FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code backend + shared schemas
COPY backend/ backend/
COPY shared/ shared/

# Volume pour les profils de config et les données pipeline
VOLUME /app/backend/config/profiles
VOLUME /root/.video-automation/data

EXPOSE 8001

CMD ["uvicorn", "backend.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
