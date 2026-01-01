from pathlib import Path

from app.download_manager import DownloadManager, sanitize_template_literal


def test_sanitize_template_literal_preserves_spaces_and_hyphen():
    # Keeps spaces/hyphen, but removes Windows-invalid characters and control chars
    assert sanitize_template_literal(" - ") == " - "
    assert sanitize_template_literal("a:b") == "a_b"
    assert sanitize_template_literal("x\u0000y") == "xy"


def _write_config(config_dir: Path, toml_text: str) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "audiobook-dl.toml").write_text(toml_text, encoding="utf-8")


def test_build_download_command_uses_default_template_and_group_by_author(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    _write_config(
        config_dir,
        """
output_template = "{title} - {author}"
create_folder = true
group_by_author = true
max_concurrent_downloads = 2
""".lstrip(),
    )

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    base_dir = downloads_dir / "__task_123__"
    cmd = dm._build_download_command(
        url="https://example.invalid/book",
        output_template=None,
        combine=False,
        no_chapters=False,
        output_format=None,
        base_dir=base_dir,
    )

    assert "-o" in cmd
    out_path = cmd[cmd.index("-o") + 1].replace("\\", "/")

    # create_folder=true => <base>/{author}/<template>/<template>
    assert out_path.endswith("/__task_123__/{author}/{title} - {author}/{title} - {author}")


def test_unwrap_staging_dir_moves_single_dir_and_updates_output_file(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir(parents=True, exist_ok=True)

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    staging_dir = downloads_dir / "__task_abc__"
    book_dir = staging_dir / "Book"
    book_dir.mkdir(parents=True)

    audio = book_dir / "audio.m4b"
    audio.write_bytes(b"dummy")

    output_file = str(audio)
    new_output, search_root = dm._unwrap_staging_dir(staging_dir, output_file)

    assert search_root == downloads_dir / "Book"
    assert new_output is not None
    assert Path(new_output).exists()
    assert Path(new_output).name == "audio.m4b"
    assert (downloads_dir / "Book" / "audio.m4b").exists()
    assert not staging_dir.exists()


def test_unwrap_staging_dir_merges_into_existing_dir_and_renames_on_conflict(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir(parents=True, exist_ok=True)

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    # Existing target structure
    target_book_dir = downloads_dir / "Book"
    target_book_dir.mkdir(parents=True)
    (target_book_dir / "audio.m4b").write_bytes(b"existing")

    # Staging contains the same filename -> must be renamed
    staging_dir = downloads_dir / "__task_def__"
    staged_book_dir = staging_dir / "Book"
    staged_book_dir.mkdir(parents=True)
    staged_audio = staged_book_dir / "audio.m4b"
    staged_audio.write_bytes(b"new")

    new_output, search_root = dm._unwrap_staging_dir(staging_dir, str(staged_audio))

    assert search_root == target_book_dir
    assert new_output is not None
    new_path = Path(new_output)
    assert new_path.exists()
    assert new_path.parent == target_book_dir
    assert new_path.name.startswith("audio")
    assert new_path.suffix == ".m4b"

    # Both files must exist (original + renamed)
    assert (target_book_dir / "audio.m4b").exists()
    assert len(list(target_book_dir.glob("audio*.m4b"))) == 2
    assert not staging_dir.exists()


def test_unwrap_staging_dir_noop_when_multiple_entries(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    staging_dir = downloads_dir / "__task_multi__"
    (staging_dir / "A").mkdir(parents=True)
    (staging_dir / "B").mkdir(parents=True)

    output_file = None
    new_output, search_root = dm._unwrap_staging_dir(staging_dir, output_file)
    assert new_output is None
    assert search_root == staging_dir
    assert staging_dir.exists()


def test_unwrap_staging_dir_noop_when_target_is_file(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir.mkdir(parents=True, exist_ok=True)

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    # Create a file where a directory would be expected
    (downloads_dir / "Book").write_bytes(b"not a dir")

    staging_dir = downloads_dir / "__task_target_file__"
    staged_book_dir = staging_dir / "Book"
    staged_book_dir.mkdir(parents=True)
    staged_audio = staged_book_dir / "audio.m4b"
    staged_audio.write_bytes(b"x")

    new_output, search_root = dm._unwrap_staging_dir(staging_dir, str(staged_audio))
    assert new_output == str(staged_audio)
    assert search_root == staging_dir
    assert staging_dir.exists()


def test_unwrap_staging_dir_moves_single_file(tmp_path: Path):
    config_dir = tmp_path / "config"
    downloads_dir = tmp_path / "downloads"
    config_dir.mkdir(parents=True, exist_ok=True)

    dm = DownloadManager(str(config_dir), str(downloads_dir))

    staging_dir = downloads_dir / "__task_file__"
    staging_dir.mkdir(parents=True)
    staged_audio = staging_dir / "out.m4b"
    staged_audio.write_bytes(b"x")

    new_output, search_root = dm._unwrap_staging_dir(staging_dir, str(staged_audio))
    assert search_root == downloads_dir
    assert new_output is not None
    assert Path(new_output).exists()
    assert (downloads_dir / "out.m4b").exists()
    assert not staging_dir.exists()
