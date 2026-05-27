from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig, AppPaths
from .memory import MemoryStore
from .profile import ProfileStore


BLOCKED_SHELL_PATTERNS = [
    "Remove-Item",
    "del ",
    "rmdir ",
    "Format-",
    "shutdown",
    "restart-computer",
    "Stop-Computer",
    "taskkill",
    "reg delete",
]


@dataclass(slots=True)
class ToolContext:
    config: AppConfig
    paths: AppPaths
    memory: MemoryStore
    profile: ProfileStore


class ToolRegistry:
    def __init__(self, context: ToolContext) -> None:
        self.context = context
        self._tools = {
            "get_profile": self.get_profile,
            "update_profile": self.update_profile,
            "save_fact": self.save_fact,
            "search_memory": self.search_memory,
            "create_task": self.create_task,
            "complete_task": self.complete_task,
            "list_tasks": self.list_tasks,
            "list_files": self.list_files,
            "read_file": self.read_file,
            "write_note": self.write_note,
            "run_powershell": self.run_powershell,
            "open_app": self.open_app,
        }

    def specs(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_profile",
                    "description": "Read the user's personalization profile.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "update_profile",
                    "description": "Update a single profile field such as preferred_browser or tone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_fact",
                    "description": "Store a short personal fact or preference in memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "source": {"type": "string"},
                        },
                        "required": ["key", "value"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_memory",
                    "description": "Search notes, prior interactions, and saved facts.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "create_task",
                    "description": "Create a task in Jarvis memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "complete_task",
                    "description": "Mark a task as done.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "integer"},
                        },
                        "required": ["task_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_tasks",
                    "description": "List tasks from local memory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "status": {"type": "string"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in a directory to inspect the local workspace.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a UTF-8 text file for analysis.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "write_note",
                    "description": "Write a note or draft into Jarvis data/notes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["filename", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_powershell",
                    "description": "Run a safe PowerShell command for local automation. Avoid risky commands.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                        },
                        "required": ["command"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "open_app",
                    "description": "Open an allowed desktop app by name.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                },
            },
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self._tools:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        return self._tools[name](**arguments)

    def get_profile(self) -> dict[str, Any]:
        return {"ok": True, "profile": self.context.profile.load()}

    def update_profile(self, key: str, value: str) -> dict[str, Any]:
        profile = self.context.profile.set(key, value)
        return {"ok": True, "profile": profile}

    def save_fact(self, key: str, value: str, source: str = "agent") -> dict[str, Any]:
        self.context.memory.save_fact(key, value, source)
        return {"ok": True, "saved": {"key": key, "value": value, "source": source}}

    def search_memory(self, query: str) -> dict[str, Any]:
        results = self.context.memory.search(query)
        return {"ok": True, "results": results}

    def create_task(self, title: str, details: str = "") -> dict[str, Any]:
        task_id = self.context.memory.create_task(title, details)
        return {"ok": True, "task_id": task_id}

    def complete_task(self, task_id: int) -> dict[str, Any]:
        success = self.context.memory.complete_task(task_id)
        return {"ok": success, "task_id": task_id}

    def list_tasks(self, status: str | None = None) -> dict[str, Any]:
        tasks = self.context.memory.list_tasks(status)
        return {"ok": True, "tasks": tasks}

    def list_files(self, path: str) -> dict[str, Any]:
        target = Path(path).expanduser()
        if not target.exists():
            return {"ok": False, "error": f"Path not found: {target}"}
        items = []
        for item in target.iterdir():
            items.append(
                {
                    "name": item.name,
                    "path": str(item),
                    "type": "dir" if item.is_dir() else "file",
                }
            )
        return {"ok": True, "items": items[:100]}

    def read_file(self, path: str) -> dict[str, Any]:
        target = Path(path).expanduser()
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": f"File not found: {target}"}
        content = target.read_text(encoding="utf-8", errors="ignore")
        return {"ok": True, "path": str(target), "content": content[:12000]}

    def write_note(self, filename: str, content: str) -> dict[str, Any]:
        safe_name = Path(filename).name
        target = self.context.paths.notes_dir / safe_name
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target)}

    def run_powershell(self, command: str) -> dict[str, Any]:
        lowered = command.lower()
        if not self.context.config.allow_unsafe_shell:
            for pattern in BLOCKED_SHELL_PATTERNS:
                if pattern.lower() in lowered:
                    return {"ok": False, "error": f"Blocked risky command pattern: {pattern}"}

        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }

    def open_app(self, name: str) -> dict[str, Any]:
        app_name = name.strip().lower()
        if app_name not in {item.lower() for item in self.context.config.allowed_apps}:
            return {"ok": False, "error": f"App not allowed: {name}"}
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"Start-Process {app_name}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stderr": completed.stderr[-2000:],
        }

    @staticmethod
    def dump_result(result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=True)

