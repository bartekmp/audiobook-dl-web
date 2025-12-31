"""
Download manager for audiobook-dl-web
Handles audiobook downloads with progress tracking
"""

import asyncio
import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path

from app import output_processor

logger = logging.getLogger(__name__)

# Constants
REMOVABLE_STATUSES = ["completed", "failed", "cancelled"]


def sanitize_path_component(path: str) -> str:
    r"""
    Sanitize path component by removing/replacing invalid filesystem characters.

    Windows doesn't allow: < > : " / \ | ? *
    Also removes leading/trailing spaces and dots
    """
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", path)
    # Remove control characters (0-31)
    sanitized = re.sub(r"[\x00-\x1f]", "", sanitized)
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip(". ")
    # Collapse multiple spaces/underscores
    sanitized = re.sub(r"[_\s]+", " ", sanitized)
    return sanitized or "unnamed"


class DownloadStatus(Enum):
    """Download status enumeration"""

    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadTask:
    """Represents a single download task"""

    def __init__(self, url: str, task_id: str):
        self.url = url
        self.task_id = task_id
        self.status = DownloadStatus.PENDING
        self.progress = 0
        self.message = "Waiting to start..."
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self.error: str | None = None
        self.output_file: str | None = None
        self.metadata: dict | None = None

    @property
    def duration(self) -> float | None:
        """Calculate task duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        """Convert task to dictionary for JSON serialization"""
        return {
            "task_id": self.task_id,
            "url": self.url,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "error": self.error,
            "output_file": self.output_file,
            "metadata": self.metadata,
        }


class DownloadManager:
    """Manages audiobook downloads"""

    def __init__(self, config_dir: str, downloads_dir: str):
        """
        Initialize download manager

        Args:
            config_dir: Directory containing audiobook-dl.toml
            downloads_dir: Directory where audiobooks will be downloaded
        """
        self.config_dir = Path(config_dir)
        self.downloads_dir = Path(downloads_dir)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        self.tasks: dict[str, DownloadTask] = {}
        self.active_downloads = 0
        self._load_max_concurrent_downloads()

    def _load_max_concurrent_downloads(self):
        """Load max concurrent downloads and create_folder setting from config"""
        try:
            import tomllib

            config_file = self.config_dir / "audiobook-dl.toml"
            if config_file.exists():
                with open(config_file, "rb") as f:
                    config = tomllib.load(f)
                    self.max_concurrent_downloads = config.get("max_concurrent_downloads", 2)
                    self.create_folder = config.get("create_folder", False)
            else:
                self.max_concurrent_downloads = 2
                self.create_folder = False
        except Exception:
            self.max_concurrent_downloads = 2
            self.create_folder = False

        # Ensure valid range (1-10)
        self.max_concurrent_downloads = max(1, min(10, self.max_concurrent_downloads))

    def reload_config(self):
        """Reload configuration settings from config file"""
        self._load_max_concurrent_downloads()

    async def add_download(
        self,
        url: str,
        task_id: str,
        output_template: str | None = None,
        combine: bool = False,
        no_chapters: bool = False,
        output_format: str | None = None,
    ) -> DownloadTask:
        """
        Add a download task

        Args:
            url: URL of the audiobook listening page
            task_id: Unique identifier for this task
            output_template: Custom output template
            combine: Whether to combine files into a single file
            no_chapters: Whether to exclude chapters
            output_format: Output file format

        Returns:
            DownloadTask object
        """
        task = DownloadTask(url, task_id)
        self.tasks[task_id] = task

        # Start download in background
        asyncio.create_task(
            self._download_audiobook(task, output_template, combine, no_chapters, output_format)
        )

        return task

    async def _download_audiobook(
        self,
        task: DownloadTask,
        output_template: str | None,
        combine: bool,
        no_chapters: bool,
        output_format: str | None,
    ):
        """
        Execute the audiobook download

        Args:
            task: DownloadTask to execute
            output_template: Custom output template
            combine: Whether to combine files
            no_chapters: Whether to exclude chapters
            output_format: Output file format
        """
        # Wait if too many concurrent downloads
        while self.active_downloads >= self.max_concurrent_downloads:
            await asyncio.sleep(1)

        self.active_downloads += 1
        task.status = DownloadStatus.DOWNLOADING
        task.started_at = datetime.now()
        task.message = "Starting download..."

        try:
            cmd = self._build_download_command(
                task.url, output_template, combine, no_chapters, output_format
            )

            logger.info(
                f"Download started - Task: {task.task_id}, URL: {task.url}, Command: {' '.join(cmd)}"
            )

            # Execute command with unbuffered output
            import os

            env = {
                "PYTHONUNBUFFERED": "1",  # Force Python unbuffered output
                "FORCE_COLOR": "0",  # Disable ANSI colors that might interfere
            }
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.downloads_dir),
                env={**os.environ, **env},  # Merge with existing env
            )

            stdout = process.stdout
            stderr = process.stderr
            if stdout is None or stderr is None:
                raise RuntimeError("Failed to capture subprocess output streams")

            # Read output and update progress in real-time from both stdout and stderr
            stdout_lines = []
            stderr_lines = []

            # Callback to update task progress as lines come in
            def on_line(line: str):
                progress, message = output_processor.parse_progress_line(line, task.progress)
                task.progress = progress
                if message != task.message:
                    task.message = message

            # Run both readers concurrently
            await asyncio.gather(
                output_processor.read_process_stream(stdout, stdout_lines, on_line),
                output_processor.read_process_stream(stderr, stderr_lines, on_line),
            )

            # Wait for process to complete
            await process.wait()

            if process.returncode == 0:
                task.status = DownloadStatus.COMPLETED
                task.progress = 100
                task.message = "Download completed successfully!"
                task.completed_at = datetime.now()

                # Try to find output file from captured output
                task.output_file = output_processor.find_output_file_in_lines(
                    stdout_lines + stderr_lines, self.downloads_dir
                )

                # If not found in output, search for files created after task started
                if not task.output_file and task.started_at:
                    # Determine search directory based on create_folder setting
                    search_dir = None
                    if self.create_folder and output_template:
                        # Extract the first variable value if possible from sanitized template
                        # For now, just search in downloads_dir since we can't know the expanded template
                        search_dir = self.downloads_dir

                    min_time = task.started_at.timestamp()
                    task.output_file = output_processor.find_latest_audio_file(
                        self.downloads_dir, min_mtime=min_time, search_dir=search_dir
                    )

                # Extract metadata from the file
                if task.output_file:
                    task.metadata = await output_processor.extract_audio_metadata(task.output_file)

                log_msg = (
                    f"Download completed - Task: {task.task_id}, Duration: {task.duration:.1f}s"
                )
                if task.output_file:
                    log_msg += f", File: {task.output_file}"
                logger.info(log_msg)
            else:
                task.status = DownloadStatus.FAILED
                task.progress = 0
                task.message = "Download failed"
                task.completed_at = datetime.now()

                logger.error(
                    f"Download failed - Task: {task.task_id}, Return code: {process.returncode}, "
                    f"Duration: {task.duration:.1f}s"
                )

                # Log stderr output for debugging
                if stderr_lines:
                    logger.error(f"Task {task.task_id} stderr output:")
                    for line in stderr_lines[-20:]:  # Log last 20 lines
                        if line.strip():
                            logger.error(f"  {line}")

                task.error = output_processor.format_error_messages(stderr_lines)

        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.message = "Download failed with exception"
            task.error = str(e)
            task.completed_at = datetime.now()

            duration_msg = f", Duration: {task.duration:.1f}s" if task.duration else ""
            logger.error(
                f"Download failed with exception - Task: {task.task_id}, Error: {str(e)}{duration_msg}"
            )
        finally:
            self.active_downloads -= 1

    def get_task(self, task_id: str) -> DownloadTask | None:
        """
        Get a download task by ID

        Args:
            task_id: Task identifier

        Returns:
            DownloadTask or None if not found
        """
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> list[DownloadTask]:
        """
        Get all download tasks

        Returns:
            List of all DownloadTask objects
        """
        return list(self.tasks.values())

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a download task (if possible)

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled, False otherwise
        """
        task = self.tasks.get(task_id)
        if task and task.status in [DownloadStatus.PENDING, DownloadStatus.DOWNLOADING]:
            task.status = DownloadStatus.CANCELLED
            task.message = "Download cancelled by user"
            task.completed_at = datetime.now()
            return True
        return False

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a specific task from the task list

        Args:
            task_id: Task identifier

        Returns:
            True if removed, False if task not found or still active
        """
        task = self.tasks.get(task_id)
        if task and task.status.value in REMOVABLE_STATUSES:
            del self.tasks[task_id]
            logger.info(f"Task removed - ID: {task_id}, Status: {task.status.value}")
            return True
        return False

    def clear_completed(self):
        """Clear all completed, failed, and cancelled tasks"""
        to_remove = [
            task_id
            for task_id, task in self.tasks.items()
            if task.status.value in REMOVABLE_STATUSES
        ]
        for task_id in to_remove:
            del self.tasks[task_id]

    def _build_download_command(
        self,
        url: str,
        output_template: str | None,
        combine: bool,
        no_chapters: bool,
        output_format: str | None,
    ) -> list[str]:
        """Build audiobook-dl command with options"""
        cmd = ["audiobook-dl", "--config", str(self.config_dir / "audiobook-dl.toml")]

        # Determine output path
        template = output_template or "{title}"

        # Sanitize template parts that are not variables (outside of {})
        # Variables like {title}, {author} are handled by audiobook-dl
        # Split into parts, keeping {...} patterns intact
        parts = re.split(r"(\{[^}]+\})", template)
        sanitized_template = "".join(
            part if part.startswith("{") else sanitize_path_component(part) for part in parts
        )

        if self.create_folder:
            output_path = str(self.downloads_dir / sanitized_template / sanitized_template)
        else:
            output_path = str(self.downloads_dir / sanitized_template)

        cmd.extend(["-o", output_path])

        # Add optional flags
        if combine:
            cmd.append("--combine")
        if no_chapters:
            cmd.append("--no-chapters")
        if output_format:
            cmd.extend(["--output-format", output_format])

        cmd.append(url)
        return cmd
