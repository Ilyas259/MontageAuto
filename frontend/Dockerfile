FROM python:3.11-slim

WORKDIR /app

# Dépendances Python
RUN pip install --no-cache-dir streamlit==1.35.0 httpx

# Code frontend
COPY frontend/ frontend/

ENV API_URL=http://backend:8001

EXPOSE 8502

CMD ["streamlit", "run", "frontend/app.py", "--server.port", "8502", "--server.address", "0.0.0.0"]
