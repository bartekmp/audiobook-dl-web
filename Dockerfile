FROM python:3.14-slim

# Install ffmpeg (required for combining audio files)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files and application code
COPY pyproject.toml ./
COPY app/ ./app/

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Create directories for volumes
RUN mkdir -p /app/config /app/downloads

# Set environment variables
ENV CONFIG_DIR=/app/config
ENV DOWNLOADS_DIR=/app/downloads
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DEBUG=false

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
