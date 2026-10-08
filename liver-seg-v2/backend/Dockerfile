# backend/Dockerfile
# ---------------------------------------------------------------
# Multi-stage build for the FastAPI backend.
# Base image includes CUDA 12.1 for GPU inference.
# ---------------------------------------------------------------

FROM python:3.11-slim AS base

# System dependencies needed by scikit-image / scipy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# --workers 1 is important: we want a single process so the model
# singleton is shared across all async requests.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--loop", "asyncio"]