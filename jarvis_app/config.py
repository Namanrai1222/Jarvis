from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class AppConfig:
    ollama_base_url: str = "http://127.0.0.1:11434"
    main_model: str = "qwen2.5:0.5b"
    coder_model: str = "qwen2.5-coder:1.5b"
    vision_model: str = "qwen2.5vl:3b"
    allow_unsafe_shell: bool = False
    confirm_file_changes: bool = True
    max_steps: int = 6
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    preferred_browser: str = "chrome"
    allowed_apps: list[str] = field(
        default_factory=lambda: ["notepad", "calc", "mspaint", "chrome", "msedge", "code"]
    )


@dataclass(slots=True)
class AppPaths:
    root: Path
    data_dir: Path
    db_path: Path
    profile_path: Path
    config_path: Path
    files_dir: Path
    notes_dir: Path
    templates_dir: Path
    static_dir: Path


def get_paths() -> AppPaths:
    root = Path(__file__).resolve().parent.parent
    data_dir = root / "data"
    files_dir = data_dir / "files"
    notes_dir = data_dir / "notes"
    templates_dir = root / "templates"
    static_dir = root / "static"
    data_dir.mkdir(exist_ok=True)
    files_dir.mkdir(exist_ok=True)
    notes_dir.mkdir(exist_ok=True)
    templates_dir.mkdir(exist_ok=True)
    static_dir.mkdir(exist_ok=True)
    return AppPaths(
        root=root,
        data_dir=data_dir,
        db_path=data_dir / "jarvis.db",
        profile_path=data_dir / "profile.json",
        config_path=root / "config.json",
        files_dir=files_dir,
        notes_dir=notes_dir,
        templates_dir=templates_dir,
        static_dir=static_dir,
    )


def load_config(paths: AppPaths) -> AppConfig:
    example_path = paths.root / "config.example.json"
    if not paths.config_path.exists() and example_path.exists():
        paths.config_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    if not paths.config_path.exists():
        return AppConfig()

    raw = json.loads(paths.config_path.read_text(encoding="utf-8"))
    return AppConfig(
        ollama_base_url=raw.get("ollama_base_url", AppConfig.ollama_base_url),
        main_model=raw.get("main_model", AppConfig.main_model),
        coder_model=raw.get("coder_model", AppConfig.coder_model),
        vision_model=raw.get("vision_model", AppConfig.vision_model),
        allow_unsafe_shell=raw.get("allow_unsafe_shell", False),
        confirm_file_changes=bool(raw.get("confirm_file_changes", True)),
        max_steps=int(raw.get("max_steps", 6)),
        server_host=raw.get("server_host", AppConfig.server_host),
        server_port=int(raw.get("server_port", AppConfig.server_port)),
        preferred_browser=raw.get("preferred_browser", AppConfig.preferred_browser),
        allowed_apps=list(raw.get("allowed_apps", [])) or AppConfig().allowed_apps,
    )
