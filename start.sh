#!/bin/bash
# Startup script for audiobook-dl-web

set -e

echo "Starting audiobook-dl-web..."

# Create necessary directories
mkdir -p "${CONFIG_DIR:-/app/config}"
mkdir -p "${DOWNLOADS_DIR:-/app/downloads}"

echo "Configuration directory: ${CONFIG_DIR:-/app/config}"
echo "Downloads directory: ${DOWNLOADS_DIR:-/app/downloads}"

# Check if audiobook-dl is installed
if ! command -v audiobook-dl &> /dev/null; then
    echo "ERROR: audiobook-dl is not installed!"
    exit 1
fi

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "WARNING: ffmpeg is not installed. Some features may not work."
    echo "Install ffmpeg to enable file combining and format conversion."
fi

# Print audiobook-dl version
echo "audiobook-dl version: $(audiobook-dl --version 2>&1 || echo 'unknown')"

# Start the application
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
