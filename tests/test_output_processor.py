import asyncio
import json
from pathlib import Path

import pytest

from app import output_processor


def test_find_output_file_in_lines_parses_output_keyword(tmp_path: Path):
    downloads_dir = tmp_path
    p = downloads_dir / "out.m4b"
    p.write_bytes(b"x")

    lines = [f"Output: {p}"]
    rel = output_processor.find_output_file_in_lines(lines, downloads_dir)
    assert rel is not None
    assert rel.endswith("out.m4b")


def test_find_output_file_in_lines_fallback_path_detection(tmp_path: Path):
    downloads_dir = tmp_path
    nested = downloads_dir / "some" / "dir"
    nested.mkdir(parents=True)
    p = nested / "x.mp3"
    p.write_bytes(b"x")

    lines = [str(p)]
    rel = output_processor.find_output_file_in_lines(lines, downloads_dir)
    assert rel is not None
    assert rel.replace("\\", "/").endswith("some/dir/x.mp3")


def test_find_output_file_in_lines_prefers_existing_file_when_multiple_candidates(tmp_path: Path):
    downloads_dir = tmp_path
    existing = downloads_dir / "exists.m4b"
    existing.write_bytes(b"x")

    missing = downloads_dir / "missing.m4b"
    lines = [f"Saved to: {missing}", f"Saved to: {existing}"]

    rel = output_processor.find_output_file_in_lines(lines, downloads_dir)
    assert rel is not None
    assert rel.endswith("exists.m4b")


def test_find_output_file_in_lines_handles_quotes_ansi_and_spaces(tmp_path: Path):
    downloads_dir = tmp_path
    p = downloads_dir / "My Book.m4b"
    p.write_bytes(b"x")

    ansi_line = f"\x1b[32mOutput:\x1b[0m \"{p}\""
    rel = output_processor.find_output_file_in_lines([ansi_line], downloads_dir)
    assert rel is not None
    assert rel.endswith("My Book.m4b")


@pytest.mark.asyncio
async def test_extract_audio_metadata_returns_duration_and_size_without_tags(monkeypatch):
    class FakeProc:
        returncode = 0

        async def communicate(self):
            payload = {
                "format": {
                    "duration": "3661.0",
                    "size": "1048576",
                    "tags": {},
                }
            }
            return json.dumps(payload).encode("utf-8"), b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        # Basic sanity: it should call ffprobe
        assert args[0] == "ffprobe"
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    md = await output_processor.extract_audio_metadata("/tmp/does-not-need-to-exist.m4b")
    assert md == {"duration": "1h 1m", "size": "1.0 MB"}


@pytest.mark.asyncio
async def test_extract_audio_metadata_returns_none_on_nonzero_exit(monkeypatch):
    class FakeProc:
        returncode = 1

        async def communicate(self):
            return b"", b"error"

    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    md = await output_processor.extract_audio_metadata("/tmp/x.m4b")
    assert md is None


@pytest.mark.asyncio
async def test_extract_audio_metadata_returns_none_on_invalid_json(monkeypatch):
    class FakeProc:
        returncode = 0

        async def communicate(self):
            return b"not-json", b""

    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    md = await output_processor.extract_audio_metadata("/tmp/x.m4b")
    assert md is None


def _make_stream_reader(chunks: list[bytes]) -> asyncio.StreamReader:
    reader = asyncio.StreamReader()
    for c in chunks:
        reader.feed_data(c)
    reader.feed_eof()
    return reader


@pytest.mark.asyncio
async def test_read_process_stream_dedupes_carriage_return_updates():
    lines: list[str] = []
    reader = _make_stream_reader([b"10%\r10%\r11%\r", b"done\n"])

    await output_processor.read_process_stream(reader, lines)
    # Should not contain repeated identical progress updates
    assert lines[-1] == "done"
    assert lines.count("10%") == 1
