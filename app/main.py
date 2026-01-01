"""
Main FastAPI application entrypoint for audiobook-dl-web
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config_manager import ConfigManager
from app.download_manager import DownloadManager
from app.routes import init_routes

# Load environment variables
load_dotenv()

# Configuration
CONFIG_DIR = os.getenv("CONFIG_DIR", "./config")
DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "./downloads")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "audiobook-dl-web.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    force=True,
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="audiobook-dl-web",
    description="Web interface for audiobook-dl",
    version="0.1.0",
    debug=DEBUG,
)

# Create necessary directories
Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)
Path(DOWNLOADS_DIR).mkdir(parents=True, exist_ok=True)
Path("app/static").mkdir(parents=True, exist_ok=True)
Path("app/templates").mkdir(parents=True, exist_ok=True)

# Setup static files with cache control
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# Add cache control headers for static files
@app.middleware("http")
async def add_cache_control_headers(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        # Cache static files for 1 hour, but revalidate
        response.headers["Cache-Control"] = "public, max-age=3600, must-revalidate"
    return response


# Initialize managers
config_manager = ConfigManager(CONFIG_DIR)
download_manager = DownloadManager(CONFIG_DIR, DOWNLOADS_DIR)

# Initialize and include routes
router = init_routes(config_manager, download_manager, CONFIG_DIR, DOWNLOADS_DIR)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))

    uvicorn.run("app.main:app", host=host, port=port, reload=DEBUG)
