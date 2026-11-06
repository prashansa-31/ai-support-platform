FROM python:3.10-slim

WORKDIR /app

# Install system dependencies needed for compiling C-extensions and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 1. Install lightweight CPU PyTorch
RUN pip install --no-cache-dir torch==2.2.0 --index-url https://download.pytorch.org/whl/cpu
# 2. Install requirements (it sees torch is already satisfied, so it won't overwrite it!)
RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache the sentence-transformers model inside the container image so cold starts are instant
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application files
COPY . .

# Render dynamically sets $PORT (defaults to 8000 locally)
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]