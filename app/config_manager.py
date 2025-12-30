"""
Configuration manager for audiobook-dl-web
Handles reading and writing audiobook-dl.toml configuration file
"""

import logging
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages audiobook-dl configuration file"""

    def __init__(self, config_dir: str):
        """
        Initialize configuration manager

        Args:
            config_dir: Directory where audiobook-dl.toml will be stored
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "audiobook-dl.toml"

    def load_config(self) -> dict[str, Any]:
        """
        Load configuration from audiobook-dl.toml

        Returns:
            Dictionary containing configuration data
        """
        if not self.config_file.exists():
            return {"sources": {}}

        try:
            with open(self.config_file, "rb") as f:
                config = tomllib.load(f)
            return config
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return {"sources": {}}

    def save_config(self, config: dict[str, Any]) -> bool:
        """
        Save configuration to audiobook-dl.toml

        Args:
            config: Configuration dictionary to save

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.config_file, "wb") as f:
                tomli_w.dump(config, f)
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    def get_source_config(self, source_name: str) -> dict[str, Any] | None:
        """
        Get configuration for a specific source

        Args:
            source_name: Name of the source (e.g., 'storytel', 'saxo')

        Returns:
            Source configuration dictionary or None
        """
        config = self.load_config()
        sources = config.get("sources", {})
        return sources.get(source_name.lower())

    def update_source_config(
        self,
        source_name: str,
        username: str | None = None,
        password: str | None = None,
        library: str | None = None,
        cookie_file: str | None = None,
    ) -> bool:
        """
        Update or create configuration for a source

        Args:
            source_name: Name of the source (e.g., 'storytel', 'saxo')
            username: Username for authentication
            password: Password for authentication
            library: Library identifier (if required)
            cookie_file: Path to cookie file (relative to config dir)

        Returns:
            True if successful, False otherwise
        """
        config = self.load_config()

        if "sources" not in config:
            config["sources"] = {}

        # Build source config from provided parameters
        source_config = {
            k: v
            for k, v in {
                "username": username,
                "password": password,
                "library": library,
                "cookie_file": cookie_file,
            }.items()
            if v is not None
        }

        config["sources"][source_name.lower()] = source_config

        result = self.save_config(config)
        if result:
            logger.info(
                f"Source configuration saved - source: {source_name}, fields: {list(source_config.keys())}"
            )
        return result

    def remove_source_config(self, source_name: str) -> bool:
        """
        Remove configuration for a source

        Args:
            source_name: Name of the source to remove

        Returns:
            True if successful, False otherwise
        """
        config = self.load_config()

        if "sources" in config and source_name.lower() in config["sources"]:
            del config["sources"][source_name.lower()]
            result = self.save_config(config)
            if result:
                logger.info(f"Source configuration removed - source: {source_name}")
            return result

        return True

    def list_configured_sources(self) -> list[str]:
        """
        Get list of all configured sources

        Returns:
            List of source names
        """
        config = self.load_config()
        sources = config.get("sources", {})
        return list(sources.keys())

    def update_global_settings(
        self,
        output_template: str | None = None,
        database_directory: str | None = None,
        skip_downloaded: bool | None = None,
        max_concurrent_downloads: int | None = None,
        create_folder: bool | None = None,
    ) -> bool:
        """
        Update global audiobook-dl settings

        Args:
            output_template: Output path template
            database_directory: Database directory path
            skip_downloaded: Whether to skip already downloaded books
            max_concurrent_downloads: Maximum number of concurrent downloads
            create_folder: Whether to create a folder for each downloaded audiobook

        Returns:
            True if successful, False otherwise
        """
        config = self.load_config()

        # Update config with provided settings
        updates = {
            "output_template": output_template,
            "database_directory": database_directory,
            "skip_downloaded": skip_downloaded,
            "max_concurrent_downloads": max_concurrent_downloads,
            "create_folder": create_folder,
        }

        changes = []
        for key, value in updates.items():
            if value is not None:
                config[key] = value
                changes.append(f"{key}={value}")

        result = self.save_config(config)
        if result and changes:
            logger.info(f"Global settings updated - {', '.join(changes)}")
        return result

    def get_config_file_path(self) -> str:
        """
        Get the full path to the configuration file

        Returns:
            String path to audiobook-dl.toml
        """
        return str(self.config_file)
