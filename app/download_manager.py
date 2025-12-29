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

logger = logging.getLogger(__name__)


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
        """Load max concurrent downloads from config, default to 2"""
        try:
            import tomllib

            config_file = self.config_dir / "audiobook-dl.toml"
            if config_file.exists():
                with open(config_file, "rb") as f:
                    config = tomllib.load(f)
                    self.max_concurrent_downloads = config.get("max_concurrent_downloads", 2)
            else:
                self.max_concurrent_downloads = 2
        except Exception:
            self.max_concurrent_downloads = 2

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

        logger.info(f"Download started - Task: {task.task_id}, URL: {task.url}")

        try:
            # Build audiobook-dl command
            cmd = [
                "audiobook-dl",
                "--config",
                str(self.config_dir / "audiobook-dl.toml"),
            ]

            # Add output directory
            if output_template:
                output_path = str(self.downloads_dir / output_template)
            else:
                output_path = str(self.downloads_dir / "{title}")

            cmd.extend(["-o", output_path])

            # Add optional flags
            if combine:
                cmd.append("--combine")
            if no_chapters:
                cmd.append("--no-chapters")
            if output_format:
                cmd.extend(["--output-format", output_format])

            # Add URL
            cmd.append(task.url)

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.downloads_dir),
            )

            stdout = process.stdout
            stderr = process.stderr
            if stdout is None or stderr is None:
                raise RuntimeError("Failed to capture subprocess output streams")

            # Read output and update progress
            stdout_lines = []
            stderr_lines = []

            while True:
                line = await stdout.readline()
                if not line:
                    break

                line_text = line.decode("utf-8").strip()
                stdout_lines.append(line_text)

                # Update progress based on output
                task.message = self._parse_progress(line_text, task)

                # Extract percentage if available (e.g., from ffmpeg output)
                percentage_match = re.search(r"(\d+)%", line_text)
                if percentage_match:
                    task.progress = int(percentage_match.group(1))

            # Read stderr
            stderr_data = await stderr.read()
            if stderr_data:
                stderr_lines = stderr_data.decode("utf-8").strip().split("\n")

            # Wait for process to complete
            await process.wait()

            if process.returncode == 0:
                task.status = DownloadStatus.COMPLETED
                task.progress = 100
                task.message = "Download completed successfully!"
                task.completed_at = datetime.now()

                duration = (task.completed_at - task.started_at).total_seconds()
                logger.info(f"Download completed - Task: {task.task_id}, Duration: {duration:.1f}s")

                # Try to find output file
                task.output_file = self._find_output_file(stdout_lines)
            else:
                task.status = DownloadStatus.FAILED
                task.progress = 0
                task.message = "Download failed"
                task.completed_at = datetime.now()

                duration = (task.completed_at - task.started_at).total_seconds()
                logger.error(
                    f"Download failed - Task: {task.task_id}, Return code: {process.returncode}, Duration: {duration:.1f}s"
                )
                # Format error message for better readability
                if stderr_lines:
                    # Clean up and format error messages
                    formatted_errors = []
                    for line in stderr_lines:
                        line = line.strip()
                        if line and not line.startswith("WARNING:"):
                            # Split on common audiobook-dl error patterns
                            if "ERROR:" in line:
                                parts = line.split("ERROR:")
                                for part in parts[1:]:  # Skip first empty part
                                    formatted_errors.append(f"ERROR: {part.strip()}")
                            elif line:
                                formatted_errors.append(line)
                    task.error = (
                        "\n".join(formatted_errors) if formatted_errors else "Unknown error"
                    )
                else:
                    task.error = "Unknown error"
                task.completed_at = datetime.now()

        except Exception as e:
            task.status = DownloadStatus.FAILED
            task.message = "Download failed with exception"
            task.error = str(e)
            task.completed_at = datetime.now()

            if task.started_at:
                duration = (task.completed_at - task.started_at).total_seconds()
                logger.error(
                    f"Download failed with exception - Task: {task.task_id}, Error: {str(e)}, Duration: {duration:.1f}s"
                )
            else:
                logger.error(
                    f"Download failed with exception - Task: {task.task_id}, Error: {str(e)}"
                )
        finally:
            self.active_downloads -= 1

    def _parse_progress(self, line: str, task: DownloadTask) -> str:
        """
        Parse progress message from audiobook-dl output and update task progress

        Args:
            line: Output line from audiobook-dl
            task: The download task to update

        Returns:
            Formatted progress message
        """
        line_lower = line.lower()

        # Update progress based on download stages
        if "authenticating" in line_lower or "login" in line_lower:
            task.progress = 10
            return "Authenticating with service..."
        elif "downloading" in line_lower or "download" in line_lower:
            # If we see download, we're at least 20% through
            if task.progress < 20:
                task.progress = 20
            # Gradually increase progress during download phase
            elif task.progress < 70:
                task.progress = min(task.progress + 5, 70)
            return "Downloading audiobook files..."
        elif "combining" in line_lower or "merge" in line_lower or "concat" in line_lower:
            task.progress = 75
            return "Combining audio files..."
        elif "chapter" in line_lower:
            task.progress = 85
            return "Adding chapter information..."
        elif "saving" in line_lower or "writing" in line_lower:
            task.progress = 90
            return "Saving audiobook..."
        elif "complete" in line_lower or "finished" in line_lower or "done" in line_lower:
            task.progress = 95
            return "Finalizing..."
        elif line:
            # Show the actual output for transparency
            return line[:100]  # Truncate long messages
        return "Processing..."

    def _find_output_file(self, stdout_lines: list[str]) -> str | None:
        """
        Try to find the output file from stdout

        Args:
            stdout_lines: Lines from stdout

        Returns:
            Relative path to output file or None
        """
        for line in reversed(stdout_lines):
            # Look for common patterns that might indicate file paths
            if any(ext in line.lower() for ext in [".m4b", ".mp3", ".m4a"]):
                # Extract potential file path
                parts = line.split()
                for part in parts:
                    if any(ext in part.lower() for ext in [".m4b", ".mp3", ".m4a"]):
                        return part
        return None

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

    def clear_completed(self):
        """Clear all completed, failed, and cancelled tasks"""
        to_remove = [
            task_id
            for task_id, task in self.tasks.items()
            if task.status
            in [
                DownloadStatus.COMPLETED,
                DownloadStatus.FAILED,
                DownloadStatus.CANCELLED,
            ]
        ]
        for task_id in to_remove:
            del self.tasks[task_id]
