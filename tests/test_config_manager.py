import tomllib
from pathlib import Path

from app.config_manager import ConfigManager


def test_update_global_settings_persists_group_by_author(tmp_path: Path):
    cm = ConfigManager(str(tmp_path))

    ok = cm.update_global_settings(
        output_template="{title} - {author}",
        create_folder=True,
        group_by_author=True,
        max_concurrent_downloads=3,
    )
    assert ok is True

    loaded = cm.load_config()
    assert loaded["output_template"] == "{title} - {author}"
    assert loaded["create_folder"] is True
    assert loaded["group_by_author"] is True
    assert loaded["max_concurrent_downloads"] == 3

    # Ensure it is valid TOML on disk
    data = tomllib.loads(Path(cm.get_config_file_path()).read_text(encoding="utf-8"))
    assert data["group_by_author"] is True


def test_update_and_remove_source_config_round_trip(tmp_path: Path):
    cm = ConfigManager(str(tmp_path))

    ok = cm.update_source_config(
        source_name="storytel",
        username="u",
        password="p",
        library="lib",
    )
    assert ok is True

    cfg = cm.load_config()
    assert "sources" in cfg
    assert cfg["sources"]["storytel"]["username"] == "u"
    assert cfg["sources"]["storytel"]["password"] == "p"
    assert cfg["sources"]["storytel"]["library"] == "lib"

    ok = cm.remove_source_config("storytel")
    assert ok is True
    cfg2 = cm.load_config()
    assert "storytel" not in cfg2.get("sources", {})
