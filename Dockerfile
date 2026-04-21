FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/      ./backend/
COPY modal_app/    ./modal_app/
COPY sample_scenes/ ./sample_scenes/
COPY scripts/      ./scripts/

# Generate fallback PLY at build time if missing
RUN python3 scripts/generate_fallback_ply.py || true

# Create scenes output directory
RUN mkdir -p /app/scenes

# Expose port
EXPOSE 8000

# Start FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
