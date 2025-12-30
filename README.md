# audiobook-dl-web

A modern, responsive web interface for [audiobook-dl](https://github.com/jo1gi/audiobook-dl) - download audiobooks from various online services through an easy-to-use web application.

![Python Version](https://img.shields.io/badge/python-3.14+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## TL;DR - Quick Start

**With Docker (Recommended):**
```bash
git clone https://github.com/yourusername/audiobook-dl-web.git
cd audiobook-dl-web
docker-compose up -d
```
Open `http://localhost:8000` → Configure Services → Enter credentials → Download → Paste URLs → Start Download

**Without Docker:**
```bash
git clone https://github.com/yourusername/audiobook-dl-web.git
cd audiobook-dl-web
python -m venv venv
source venv/bin/activate  # Linux/macOS
# Or: .\venv\Scripts\Activate.ps1 (Windows PowerShell)
pip install -e .
# Install ffmpeg: apt-get install ffmpeg (Linux) | brew install ffmpeg (macOS) | winget install Gyan.FFmpeg (Windows)
python -m app.main  # Or on Windows: .\start.ps1
```
Open `http://localhost:8000`

⚠️ **Storytel users**: Add books to your shelf BEFORE downloading!

![Home Page](docs/home-page.png)

## What Can You Do?

**audiobook-dl-web** is a self-hosted web interface for [audiobook-dl](https://github.com/jo1gi/audiobook-dl), making it easy to download audiobooks from multiple services through your browser. Everything that audiobook-dl supports, this web interface supports too.

**Configure Your Services**: Set up login credentials for any audiobook service supported by `audiobook-dl`, including Storytel, Saxo, Nextory, eReolen, Podimo, YourCloudLibrary, Everand, and more. Your credentials are stored securely in a local configuration file, so you only need to enter them once.

**Track Downloads in Real-Time**: Watch your audiobook downloads progress with live percentage updates that reflect actual download status. Each task shows detailed progress messages from authentication through file combining, with metadata automatically extracted when complete—including title, author, narrator, duration, and file size. Service badges identify which platform each audiobook comes from at a glance.

**Manage Your Queue Efficiently**: Download multiple audiobooks simultaneously with configurable concurrency (1-10 downloads at once). Collapse individual downloads or the entire queue to stay focused on active items while keeping completed ones accessible. The interface maintains your collapsed state even as downloads update, keeping your workspace organized.

**Customize Output Properties**: Configure how your audiobooks are saved—choose the output format (M4B, MP3, M4A), customize the file naming template with variables like `{author}/{series}/{title}`, decide whether to combine audio parts into a single file, and control chapter information. Set these options per-download or save them as global defaults.

**Self-Host Anywhere**: Deploy with Docker for one-command setup, or run manually on any system with Python 3.14+. The responsive web interface works on desktop and mobile, with dark mode support optimized for readability. All downloads are saved to your local storage with full file paths displayed, and comprehensive logging helps you track everything that happens.

## Table of Contents

- [TL;DR - Quick Start](#tldr---quick-start)
- [Features](#features)
- [Installation](#installation)
  - [Docker (Recommended)](#docker-recommended)
  - [Manual Installation](#manual-installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Supported Services](#supported-services)
- [Advanced Options](#advanced-options)
- [Logging](#logging)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## Installation

### Docker (Recommended)

The easiest way to run audiobook-dl-web is using Docker:

```bash
# Clone the repository
git clone https://github.com/yourusername/audiobook-dl-web.git
cd audiobook-dl-web

# Copy the example environment file
cp .env.example .env

# Edit .env if needed (optional)
nano .env

# Start with docker-compose
docker-compose up -d
```

The application will be available at `http://localhost:8000`

#### Docker Volumes

The Docker Compose configuration creates three important volumes:

- `./config` - Stores `audiobook-dl.toml` configuration file with credentials
- `./downloads` - Stores downloaded audiobooks
- `./logs` - Stores application logs with timestamps

These directories are automatically created and persisted on your host machine.

### TrueNAS CE Installation

Deploy `audiobook-dl-web` as a custom app in TrueNAS Community Edition:

#### 1. Prepare Storage

Create datasets for the deployed app via the UI: **Datasets** → **Add Dataset** (create one parent `audiobook-dl-web` and three children datasets: `config`, `downloads`, `logs`), can be of `Generic` type.

#### 2. Install Custom App

1. Navigate to **Apps** → **Discover Apps** → **Custom App**
2. Configure the following settings:

**Application Name:**
- Name: `audiobook-dl-web`

**Container Images:**
- Image Repository: `ghcr.io/bartekmp/audiobook-dl-web`
- Image Tag: `<insert a specific version tag here>` (or `latest` for the newest version)
- Pull Policy: `Always Pull Image`

**Container Environment Variables:**
- Add the following variables (click **Add** for each):
  - Name: `CONFIG_DIR`, Value: `/app/config`
  - Name: `DOWNLOADS_DIR`, Value: `/app/downloads`
  - Name: `HOST`, Value: `0.0.0.0`
  - Name: `PORT`, Value: `8000`
  - Name: `DEBUG`, Value: `false`
  - Name: `SECRET_KEY`, Value: `change-this-to-a-random-secret-key`

**Networking:**
- Host Network: Leave unchecked
- Add Port:
  - Container Port: `8000`
  - Host Port: `8000`
  - Protocol: `TCP`

**Storage:**
- Add three Host Path volumes (click **Add** for each):
  1. Host Path: `/mnt/tank/audiobook-dl-web/config`, Mount Path: `/app/config`
  2. Host Path: `/mnt/tank/audiobook-dl-web/downloads`, Mount Path: `/app/downloads`
  3. Host Path: `/mnt/tank/audiobook-dl-web/logs`, Mount Path: `/app/logs`

**Resources Configuration:**
- CPU: `2` (2 CPUs) - adjust based on your needs
- Memory: `2G` (2048 MiB / 2 GiB) - adjust based on your needs

1. Click **Install**

The application will be available at `http://your-truenas-ip:8000`

> **Note:** The built-in health check in the Docker image will automatically monitor the application status in TrueNAS.

### Manual Installation

If you prefer to run without Docker:

```bash
# Clone the repository
git clone https://github.com/yourusername/audiobook-dl-web.git
cd audiobook-dl-web

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# On Windows PowerShell: .\venv\Scripts\Activate.ps1
# On Windows CMD: venv\Scripts\activate.bat

# Install dependencies
pip install -e .

# Install ffmpeg (required for combining audio files)
# On Ubuntu/Debian:
sudo apt-get install ffmpeg
# On macOS:
brew install ffmpeg
# On Windows:
winget install -e Gyan.FFmpeg

# Create necessary directories
mkdir -p config downloads logs  # Linux/macOS
# On Windows PowerShell: New-Item -ItemType Directory -Path config, downloads, logs -Force

# Copy environment file (optional)
cp .env.example .env  # Linux/macOS
# On Windows: copy .env.example .env

# Start the application
python -m app.main  # Or on Windows PowerShell: .\start.ps1
```

The application will be available at `http://localhost:8000`

## Usage

### 1. Configure a Service

1. Navigate to **Configure Services** in the menu
2. Select a service from the list (e.g., Storytel, Saxo)
3. Enter your credentials (username and password)
4. Click **Save Configuration**

Your credentials are stored securely in `config/audiobook-dl.toml`.

![Service Configuration](docs/service-config.png)

### 2. Download Audiobooks

1. Navigate to **Download** in the menu
2. Paste one or more audiobook URLs (one per line)
   - **Important for Storytel**: Make sure the book is added to your shelf before downloading!
3. (Optional) Configure advanced options:
   - Output template (e.g., `{author}/{series}/{title}`)
   - Output format (M4B, MP3, M4A)
   - Combine files into a single file
   - Include/exclude chapter information
4. Click **Start Download**
5. Monitor progress in the download queue

![Download Queue](docs/downloads.png)

**Failed downloads** are clearly marked with error details:

![Failed Download](docs/failed-download.png)

### 3. Adjust Settings

Navigate to **Settings** to configure:

- **Default output template** - Customize where files are saved
- **Skip already downloaded books** - Avoid re-downloading
- **Create folder for downloaded books** - When enabled, each audiobook will be downloaded to a dedicated folder named using the output template (default: disabled)
- **Maximum concurrent downloads** - Control how many audiobooks download simultaneously (1-10, default: 2)
- View current configuration

![Settings Page](docs/settings.png)

## Configuration

### Environment Variables

The application can be configured using environment variables in `.env`:

```bash
# Server Configuration
HOST=0.0.0.0
PORT=8000
DEBUG=false

# Paths
CONFIG_DIR=/app/config
DOWNLOADS_DIR=/app/downloads

# Security
SECRET_KEY=change-this-to-a-random-secret-key-in-production
```

### audiobook-dl.toml

The configuration file (`config/audiobook-dl.toml`) stores service credentials and global settings:

```toml
# Global settings
output_template = "{author}/{title}"
skip_downloaded = true
create_folder = false
max_concurrent_downloads = 2

# Service credentials
[sources.storytel]
username = "your_username"
password = "your_password"

[sources.saxo]
username = "your_email@example.com"
password = "your_password"
```

## Supported Services

`audiobook-dl-web` supports all services provided by `audiobook-dl`, see [Supported Services](https://github.com/jo1gi/audiobook-dl/tree/master?tab=readme-ov-file#supported-services) list for more info.

### URL Formats

Each service requires specific URL formats. Examples:

- **Storytel**: `https://www.storytel.com/pl/books/book-name-12345`
- **Saxo**: `https://www.saxo.com/en/book-name`
- **Nextory**: `https://nextory.com/book/example`

The listening page URL is required, not just the information page.

## Advanced Options

### Output Templates

Customize where audiobooks are saved using these variables:

- `{title}` - Book title
- `{author}` - Author name
- `{series}` - Series name
- `{narrator}` - Narrator name

**Examples:**
- `{title}` → `Book Name.m4b`
- `{author}/{title}` → `Author Name/Book Name.m4b`
- `{author}/{series}/{title}` → `Author Name/Series Name/Book Name.m4b`

**With "Create folder for downloaded books" enabled:**
- Template: `{title}` → Folder: `Book Name/`, File: `Book Name.m4b`
- Template: `{title} - {author}` → Folder: `Book Name - Author Name/`, File: `Book Name - Author Name.m4b`
- This is useful when audiobooks consist of multiple files, keeping all parts organized in a dedicated folder

### Output Formats

Supported output formats:
- **M4B** - Audiobook format (recommended)
- **MP3** - Universal audio format
- **M4A** - MPEG-4 audio

### Combining Files

Enable "Combine all files into a single file" to merge all audio parts into one file. Requires `ffmpeg`.

## Development

### Running in Development Mode

```bash
# Set DEBUG mode
export DEBUG=true

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### API Endpoints

The application provides a REST API:

- `GET /` - Home page
- `GET /configure` - Configuration page
- `POST /configure/{service}` - Save service configuration
- `GET /download` - Download page
- `POST /api/download` - Start downloads
- `GET /api/tasks` - Get all download tasks
- `GET /api/tasks/{task_id}` - Get specific task status
- `POST /api/tasks/{task_id}/cancel` - Cancel a task
- `DELETE /api/tasks/{task_id}` - Remove a specific task
- `POST /api/tasks/clear` - Clear completed tasks
- `GET /settings` - Settings page
- `POST /settings` - Update settings
- `GET /health` - Health check

## Troubleshooting

### Downloads Fail Immediately

- **Storytel users**: Ensure the book is added to your shelf/library
- Check that credentials are correct in the configuration
- Verify the URL format is correct (use the listening page URL)

### "audiobook-dl not found" Error

- Ensure `audiobook-dl` is installed: `pip install audiobook-dl`
- In Docker, rebuild the container: `docker-compose build`

### Permission Errors with Docker

```bash
# Fix permissions for config and downloads directories
sudo chown -R $USER:$USER config downloads
```

### Cannot Combine Files

- Ensure `ffmpeg` is installed
- In Docker, `ffmpeg` is included automatically
- Manually: `apt-get install ffmpeg`, `brew install ffmpeg` or `winget install -e Gyan.FFmpeg`

### Progress Not Updating

- Check browser console for errors (F12)
- Ensure JavaScript is enabled
- Try refreshing the page

### Too Many Concurrent Downloads

- Adjust **Maximum Concurrent Downloads** in Settings (default: 2)
- Lower values reduce server load and avoid rate limiting
- Higher values (up to 10) can speed up batch downloads if the service allows it

### Configuration File Issues

The configuration file is located at:
- **Docker**: `./config/audiobook-dl.toml`
- **Manual**: `./config/audiobook-dl.toml` or as specified in `.env`

You can edit this file manually if needed.

## Important Notes

### Storytel / Mofibo

⚠️ **Important**: For Storytel, you **must** add books to your shelf/library before downloading them. The download will fail if the book is not in your shelf.

### Legal Considerations

This tool is intended for downloading audiobooks you have legal access to. Please respect copyright laws and the terms of service of the audiobook platforms you use.

### Rate Limiting

Some services may have rate limits. The application limits concurrent downloads to 2 by default to avoid triggering rate limits. You can adjust this in **Settings** → **Maximum Concurrent Downloads** (range: 1-10) based on your needs and the service's tolerance.

## Logging

The application logs all important events with timestamps to help you track what's happening:

### What is Logged

- **Download Queue**: When URLs are added to the download queue
- **Download Status**: Status changes (pending → downloading → completed/failed) with duration
- **Configuration Changes**: When service credentials are updated or deleted
- **Settings Changes**: When global settings are modified

### Log Format

Logs use the standard Python logging format:
```
2024-01-15 14:32:45,123 - app.main - INFO - Adding 3 URL(s) to download queue
2024-01-15 14:32:45,456 - app.download_manager - INFO - Download started - Task: abc-123, URL: https://...
2024-01-15 14:35:12,789 - app.download_manager - INFO - Download completed - Task: abc-123, Duration: 147.3s
2024-01-15 14:35:20,123 - app.config_manager - INFO - Configuration updated - service: storytel, fields: username, password
```

### Accessing Logs

**Docker**: Logs are available in the `./logs` directory (mounted volume)
```bash
tail -f logs/audiobook-dl-web.log
```

**Manual Installation**: Logs are stored in the `logs/` directory in your installation path

**View in Docker**: You can also view logs using Docker commands
```bash
docker-compose logs -f audiobook-dl-web
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

[audiobook-dl](https://github.com/jo1gi/audiobook-dl) - The underlying audiobook download library

## Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review [audiobook-dl documentation](https://github.com/jo1gi/audiobook-dl)
3. Open an issue on GitHub

---

**Disclaimer**: This project is not affiliated with or endorsed by any of the supported audiobook services. Use responsibly and in accordance with applicable laws and terms of service.
