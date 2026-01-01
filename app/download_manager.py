"""
Download manager for audiobook-dl-web
Handles audiobook downloads with progress tracking
"""

import asyncio
import logging
import re
import shutil
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


def sanitize_template_literal(literal: str) -> str:
    """Sanitize only the literal parts of the output template.

    This is intentionally less aggressive than `sanitize_path_component`:
    - Keeps spaces/hyphens exactly as written (e.g. " - ")
    - Only removes characters that are invalid in Windows paths and control chars

    The `{variables}` are expanded by audiobook-dl.
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", literal)
    sanitized = re.sub(r"[\x00-\x1f]", "", sanitized)
    return sanitized


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
        self.expected_output_dir: Path | None = None  # Track expected output directory

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
        self.config_dir = Path(config_dir).resolve()
        self.downloads_dir = Path(downloads_dir).resolve()
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

        self.tasks: dict[str, DownloadTask] = {}
        self.active_downloads = 0
        self._load_config()

    def _read_config(self) -> dict:
        """Read configuration from audiobook-dl.toml file

        Returns:
            Configuration dictionary or empty dict if file doesn't exist or can't be read
        """
        try:
            import tomllib

            config_file = self.config_dir / "audiobook-dl.toml"
            if config_file.exists():
                with open(config_file, "rb") as f:
                    return tomllib.load(f)
        except Exception as e:
            logger.warning(f"Failed to read config file: {e}")
        return {}

    def _load_config(self):
        """Load configuration settings from config file"""
        config = self._read_config()

        self.max_concurrent_downloads = config.get("max_concurrent_downloads", 2)
        self.create_folder = config.get("create_folder", False)
        self.group_by_author = config.get("group_by_author", False)
        self.default_output_template = config.get("output_template", "{title}")

        # Ensure valid range (1-10)
        self.max_concurrent_downloads = max(1, min(10, self.max_concurrent_downloads))

    def reload_config(self):
        """Reload configuration settings from config file"""
        self._load_config()

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
            # Use a per-task staging directory so concurrent tasks can never
            # claim each other's output by "newest file" heuristics.
            task_base_dir = self.downloads_dir / f"__task_{task.task_id}__"
            task_base_dir.mkdir(parents=True, exist_ok=True)
            task.expected_output_dir = task_base_dir

            cmd = self._build_download_command(
                task.url,
                output_template,
                combine,
                no_chapters,
                output_format,
                base_dir=task_base_dir,
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

                # Keep search root within this task's staging directory for deterministic
                # file detection, then unwrap/move after we've identified the output.
                search_root = task.expected_output_dir or self.downloads_dir

                # Try to find output file from captured output
                logger.info(
                    f"Task {task.task_id}: Captured {len(stdout_lines)} stdout lines, "
                    f"{len(stderr_lines)} stderr lines"
                )

                # First try to parse the exact file path from tool output.
                task.output_file = output_processor.find_output_file_in_lines(
                    stdout_lines + stderr_lines, self.downloads_dir
                )

                if task.output_file:
                    logger.info(f"Task {task.task_id}: Found file in output: {task.output_file}")

                # If not found in output, search for files created after task started
                if not task.output_file and task.started_at:
                    min_time = task.started_at.timestamp()

                    # With per-task staging dirs, we can deterministically search only within the
                    # task's own output tree (staging dir or the moved-to target).
                    # This works for both "single file" (file directly in a folder) and multi-file.
                    if (
                        isinstance(search_root, Path)
                        and search_root.exists()
                        and search_root.is_file()
                    ):
                        task.output_file = output_processor.normalize_path(search_root)
                    else:
                        task.output_file = output_processor.find_latest_audio_file(
                            self.downloads_dir,
                            min_mtime=min_time,
                            search_dir=search_root
                            if isinstance(search_root, Path)
                            else self.downloads_dir,
                        )

                    if not task.output_file:
                        logger.warning(
                            f"Task {task.task_id}: No audio file found under search root: {search_root}"
                        )

                    if task.output_file:
                        logger.info(
                            f"Task {task.task_id}: Found file by timestamp search: {task.output_file}"
                        )

                # Unwrap staging directory into the main downloads folder (merge-safe).
                # Also update `task.output_file` to the new location when possible.
                if task.expected_output_dir and task.expected_output_dir.exists():
                    try:
                        task.output_file, search_root = self._unwrap_staging_dir(
                            task.expected_output_dir, task.output_file
                        )
                    except Exception as e:
                        logger.warning(f"Task {task.task_id}: Failed to unwrap staging dir: {e}")

                # Extract metadata from the file
                if task.output_file:
                    logger.info(f"Extracting metadata for: {task.output_file}")
                    task.metadata = await output_processor.extract_audio_metadata(task.output_file)
                    if task.metadata:
                        logger.info(f"Metadata extracted: {list(task.metadata.keys())}")
                    else:
                        logger.warning(f"No metadata extracted for: {task.output_file}")

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
        base_dir: Path,
    ) -> list[str]:
        """Build audiobook-dl command with options"""
        cmd = ["audiobook-dl", "--config", str(self.config_dir / "audiobook-dl.toml")]

        # Determine output path - use provided template or fall back to config default
        template = output_template if output_template is not None else self.default_output_template

        # Sanitize template parts that are not variables (outside of {})
        # Variables like {title}, {author} are handled by audiobook-dl
        # Split into parts, keeping {...} patterns intact
        parts = re.split(r"(\{[^}]+\})", template)
        sanitized_template = "".join(
            part if (not part or part.startswith("{")) else sanitize_template_literal(part)
            for part in parts
        )

        effective_base_dir = base_dir
        if getattr(self, "group_by_author", False):
            # Let audiobook-dl expand {author} and handle its own sanitization.
            effective_base_dir = base_dir / "{author}"

        if self.create_folder:
            output_path = str(effective_base_dir / sanitized_template / sanitized_template)
        else:
            output_path = str(effective_base_dir / sanitized_template)

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

    def _unique_destination(self, dest: Path) -> Path:
        """Return a non-existing destination path by appending a numeric suffix."""
        if not dest.exists():
            return dest

        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent

        for i in range(2, 10_000):
            candidate = parent / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return candidate
        # Fallback (should be extremely unlikely)
        return parent / f"{stem} (copy){suffix}"

    def _merge_dir_contents(self, src_dir: Path, dest_dir: Path) -> dict[Path, Path]:
        """Move top-level children from src_dir into dest_dir. Returns mapping of moved children."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        moved: dict[Path, Path] = {}

        for child in src_dir.iterdir():
            target_child = dest_dir / child.name
            if target_child.exists():
                target_child = self._unique_destination(target_child)
            shutil.move(str(child), str(target_child))
            moved[child] = target_child

        return moved

    def _unwrap_staging_dir(
        self, staging_dir: Path, output_file: str | None
    ) -> tuple[str | None, Path]:
        """Move results from staging_dir into downloads_dir, merging if necessary.

        Returns updated (output_file, search_root).
        """
        entries = list(staging_dir.iterdir())
        if len(entries) != 1:
            return output_file, staging_dir

        entry = entries[0]
        target = self.downloads_dir / entry.name

        old_output_path: Path | None = None
        if output_file:
            try:
                old_output_path = Path(output_file)
            except Exception:
                old_output_path = None

        if entry.is_dir():
            if not target.exists():
                shutil.move(str(entry), str(target))
                shutil.rmtree(staging_dir, ignore_errors=True)

                if old_output_path and old_output_path.is_relative_to(entry):
                    new_output = target / old_output_path.relative_to(entry)
                    return output_processor.normalize_path(new_output), target
                return output_file, target

            if not target.is_dir():
                # Destination exists but isn't a directory; keep staging
                return output_file, staging_dir

            moved_map = self._merge_dir_contents(entry, target)
            shutil.rmtree(staging_dir, ignore_errors=True)

            if old_output_path and old_output_path.is_relative_to(entry):
                rel = old_output_path.relative_to(entry)
                top = entry / rel.parts[0]
                new_top = moved_map.get(top)
                if new_top:
                    new_output = new_top.joinpath(*rel.parts[1:])
                    return output_processor.normalize_path(new_output), target
            return output_file, target

        # entry is a file
        if target.exists():
            target = self._unique_destination(target)
        shutil.move(str(entry), str(target))
        shutil.rmtree(staging_dir, ignore_errors=True)

        if old_output_path and old_output_path == entry:
            return output_processor.normalize_path(target), target.parent
        return output_file, target.parent
