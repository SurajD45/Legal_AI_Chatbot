FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.base.txt requirements.ml.txt ./

RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.base.txt \
    -r requirements.ml.txt

# App code
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY frontend/ ./frontend/

RUN mkdir -p /app/data

EXPOSE 8000

# 🚫 NO HEALTHCHECK (intentional)

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
