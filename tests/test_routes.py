"""Smoke tests that every HTML page actually renders."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config_manager import ConfigManager
from app.download_manager import DownloadManager
from app.routes import init_routes


@pytest.fixture
def client(tmp_path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir()
    downloads_dir.mkdir()

    config_manager = ConfigManager(str(config_dir))
    download_manager = DownloadManager(str(config_dir), str(downloads_dir))

    app = FastAPI()
    app.include_router(
        init_routes(config_manager, download_manager, str(config_dir), str(downloads_dir))
    )
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/configure", "/settings"])
def test_pages_render(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_download_page_redirects_without_configured_sources(client):
    response = client.get("/download", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/configure"


def test_download_page_renders_with_configured_source(client):
    client.post("/configure/storytel", data={"username": "u", "password": "p"})

    response = client.get("/download")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
