# Build context MUST be the backend/ directory: `docker build backend/`
# (the .dockerignore beside this file keeps .env, .git, .azure/, tests, and other
# secrets/dev artifacts out of the image so nothing sensitive is baked in).
FROM python:3.11-slim

# Install ffmpeg for audio conversion
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (secrets/tests excluded via .dockerignore)
COPY . .

# Run as an unprivileged user rather than root.
RUN adduser --system --group --no-create-home appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start with uvicorn directly (no reload in production)
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
