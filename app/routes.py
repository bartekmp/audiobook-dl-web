"""
FastAPI route handlers for audiobook-dl-web
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.services import SUPPORTED_SERVICES
from app.utils import is_valid_url

# Setup logger
logger = logging.getLogger(__name__)

# Setup templates
templates = Jinja2Templates(directory="app/templates")

# Create router
router = APIRouter()


def init_routes(config_manager, download_manager, config_dir: str, downloads_dir: str):
    """
    Initialize routes with dependency injection

    Args:
        config_manager: ConfigManager instance
        download_manager: DownloadManager instance
        config_dir: Configuration directory path
        downloads_dir: Downloads directory path
    """

    @router.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Home page"""
        configured_services = config_manager.list_configured_sources()
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "services": SUPPORTED_SERVICES,
                "configured_services": configured_services,
            },
        )

    @router.get("/configure", response_class=HTMLResponse)
    async def configure_page(request: Request, service: str | None = None):
        """Configuration page for setting up service credentials"""
        if service and service not in SUPPORTED_SERVICES:
            raise HTTPException(status_code=404, detail="Service not found")

        configured_services = config_manager.list_configured_sources()
        selected_service = None
        current_config = None

        if service:
            selected_service = SUPPORTED_SERVICES[service]
            selected_service["id"] = service
            current_config = config_manager.get_source_config(service)

        return templates.TemplateResponse(
            "configure.html",
            {
                "request": request,
                "services": SUPPORTED_SERVICES,
                "configured_services": configured_services,
                "selected_service": selected_service,
                "current_config": current_config,
            },
        )

    @router.post("/configure/{service}")
    async def configure_service(
        service: str,
        username: str | None = Form(None),
        password: str | None = Form(None),
        library: str | None = Form(None),
    ):
        """Save service configuration"""
        if service not in SUPPORTED_SERVICES:
            raise HTTPException(status_code=404, detail="Service not found")

        success = config_manager.update_source_config(
            source_name=service, username=username, password=password, library=library
        )

        if success:
            # Log configuration change (don't log passwords)
            fields_updated = []
            if username:
                fields_updated.append("username")
            if password:
                fields_updated.append("password")
            if library:
                fields_updated.append("library")
            logger.info(
                f"Configuration updated - service: {service}, fields: {', '.join(fields_updated)}"
            )

            return RedirectResponse(
                url=f"/configure?service={service}&success=true",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        else:
            logger.error(f"Failed to update configuration for service: {service}")
            raise HTTPException(status_code=500, detail="Failed to save configuration")

    @router.post("/configure/{service}/delete")
    async def delete_service_config(service: str):
        """Delete service configuration"""
        if service not in SUPPORTED_SERVICES:
            raise HTTPException(status_code=404, detail="Service not found")

        success = config_manager.remove_source_config(service)

        if success:
            logger.info(f"Configuration deleted - service: {service}")
            return RedirectResponse(url="/configure", status_code=status.HTTP_303_SEE_OTHER)
        else:
            logger.error(f"Failed to delete configuration for service: {service}")
            raise HTTPException(status_code=500, detail="Failed to delete configuration")

    @router.get("/download", response_class=HTMLResponse)
    async def download_page(request: Request):
        """Download page where users can paste audiobook URLs"""
        configured_services = config_manager.list_configured_sources()

        if not configured_services:
            return RedirectResponse(url="/configure", status_code=status.HTTP_303_SEE_OTHER)

        return templates.TemplateResponse(
            "download.html",
            {
                "request": request,
                "services": SUPPORTED_SERVICES,
                "configured_services": configured_services,
            },
        )

    @router.post("/api/download")
    async def start_download(
        urls: str = Form(...),
        combine: bool = Form(False),
        no_chapters: bool = Form(False),
        output_format: str | None = Form(None),
        output_template: str | None = Form(None),
    ):
        """
        Start downloading audiobooks from provided URLs

        Args:
            urls: Newline-separated list of audiobook URLs
            combine: Whether to combine files into a single file
            no_chapters: Whether to exclude chapter information
            output_format: Output file format (mp3, m4b, etc.)
            output_template: Output path template
        """
        url_list = [url.strip() for url in urls.split("\n") if url.strip()]

        if not url_list:
            raise HTTPException(status_code=400, detail="No URLs provided")

        logger.info(f"Adding {len(url_list)} URL(s) to download queue")

        tasks = []
        warnings = []

        for url in url_list:
            # Validate URL format
            if not is_valid_url(url):
                warning = {
                    "url": url,
                    "warning": "Invalid URL format",
                    "message": f"Skipped invalid URL: {url[:100]}",
                }
                warnings.append(warning)
                logger.warning(f"Invalid URL skipped: {url}")
                continue

            task_id = str(uuid.uuid4())
            task = await download_manager.add_download(
                url=url,
                task_id=task_id,
                output_template=output_template,
                combine=combine,
                no_chapters=no_chapters,
                output_format=output_format,
            )
            tasks.append(task.to_dict())
            logger.info(f"Task added to queue - ID: {task_id}, URL: {url}")

        return JSONResponse(content={"tasks": tasks, "warnings": warnings})

    @router.get("/api/tasks")
    async def get_tasks():
        """Get all download tasks"""
        tasks = download_manager.get_all_tasks()
        return JSONResponse(content={"tasks": [task.to_dict() for task in tasks]})

    @router.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        """Get specific download task status"""
        task = download_manager.get_task(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return JSONResponse(content=task.to_dict())

    @router.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        """Cancel a download task"""
        success = download_manager.cancel_task(task_id)

        if not success:
            raise HTTPException(status_code=400, detail="Cannot cancel task")

        return JSONResponse(content={"status": "cancelled"})

    @router.post("/api/tasks/clear")
    async def clear_completed_tasks():
        """Clear all completed, failed, and cancelled tasks"""
        download_manager.clear_completed()
        return JSONResponse(content={"status": "cleared"})

    @router.get("/settings", response_class=HTMLResponse)
    async def settings_page(request: Request):
        """Settings page for global audiobook-dl options"""
        config = config_manager.load_config()

        return templates.TemplateResponse(
            "settings.html",
            {
                "request": request,
                "config": config,
                "config_file_path": config_manager.get_config_file_path(),
                "downloads_dir": downloads_dir,
            },
        )

    @router.post("/settings")
    async def update_settings(
        output_template: str | None = Form(None),
        skip_downloaded: bool = Form(False),
        max_concurrent_downloads: int = Form(2),
    ):
        """Update global settings"""
        success = config_manager.update_global_settings(
            output_template=output_template if output_template else None,
            skip_downloaded=skip_downloaded,
            max_concurrent_downloads=max_concurrent_downloads,
        )

        if success:
            # Reload download manager config to apply new max concurrent downloads
            download_manager.reload_config()
            logger.info(
                f"Settings updated - output_template: {output_template}, skip_downloaded: {skip_downloaded}, max_concurrent_downloads: {max_concurrent_downloads}"
            )
            return RedirectResponse(
                url="/settings?success=true", status_code=status.HTTP_303_SEE_OTHER
            )
        else:
            logger.error("Failed to update settings")
            raise HTTPException(status_code=500, detail="Failed to update settings")

    @router.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "config_dir": config_dir,
            "downloads_dir": downloads_dir,
        }

    return router
