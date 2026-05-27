from __future__ import annotations

import json
from pathlib import Path


DEFAULT_PROFILE = {
    "user_name": "User",
    "tone": "helpful",
    "preferred_browser": "chrome",
    "work_style": "step-by-step",
    "priority_topics": [],
    "restricted_actions": ["payments", "bulk delete", "send message without review"],
}


class ProfileStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        if not self.path.exists():
            self.save(DEFAULT_PROFILE)

    def load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, profile: dict) -> None:
        self.path.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    def set(self, key: str, value: str) -> dict:
        profile = self.load()
        profile[key] = value
        self.save(profile)
        return profile

