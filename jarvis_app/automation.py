from __future__ import annotations

import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from .config import AppConfig, AppPaths


@dataclass(slots=True)
class ActionResult:
    name: str
    ok: bool
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AutomationHub:
    def __init__(self, config: AppConfig, paths: AppPaths) -> None:
        self.config = config
        self.paths = paths
        self._allowed_browsers = {"chrome", "msedge", "edge"}

    def open_browser_search(self, query: str, browser_name: str | None = None) -> ActionResult:
        clean_query = query.strip()
        if not clean_query:
            url = "https://www.google.com"
            label = "Opened browser homepage."
        else:
            url = f"https://www.google.com/search?q={quote_plus(clean_query)}"
            label = f"Searched the web for: {clean_query}"

        browser = self._normalize_browser(browser_name)
        if browser:
            launched = self._start_browser(browser, url)
            if launched:
                return ActionResult(
                    name="browser_search",
                    ok=True,
                    message=label,
                    metadata={"query": clean_query, "url": url, "browser": browser},
                )

        opened = webbrowser.open(url)
        return ActionResult(
            name="browser_search",
            ok=opened,
            message=label if opened else "I could not open the browser automatically.",
            metadata={"query": clean_query, "url": url, "browser": browser or "default"},
        )

    def open_url(self, url: str, browser_name: str | None = None, label: str | None = None) -> ActionResult:
        clean_url = url.strip()
        if not clean_url:
            return ActionResult(
                name="open_url",
                ok=False,
                message="No URL was provided.",
                metadata={},
            )

        if not clean_url.startswith(("http://", "https://", "whatsapp://")):
            clean_url = "https://" + clean_url

        browser = self._normalize_browser(browser_name)
        if browser and self._start_browser(browser, clean_url):
            return ActionResult(
                name="open_url",
                ok=True,
                message=label or f"Opened {clean_url}",
                metadata={"url": clean_url, "browser": browser},
            )

        opened = webbrowser.open(clean_url)
        return ActionResult(
            name="open_url",
            ok=opened,
            message=(label or f"Opened {clean_url}") if opened else f"I could not open {clean_url}.",
            metadata={"url": clean_url, "browser": browser or "default"},
        )

    def _normalize_browser(self, browser_name: str | None) -> str:
        name = (browser_name or self.config.preferred_browser).strip().lower()
        if name == "edge":
            name = "msedge"
        return name if name in self._allowed_browsers else ""

    @staticmethod
    def _escape_ps(value: str) -> str:
        return value.replace("'", "''")

    def _start_browser(self, browser: str, url: str) -> bool:
        safe_browser = self._escape_ps(browser)
        safe_url = self._escape_ps(url)
        command = f"Start-Process -FilePath '{safe_browser}' -ArgumentList @('{safe_url}')"
        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            return completed.returncode == 0
        except Exception:
            return False

    def open_app(self, name: str) -> ActionResult:
        app_name = name.strip().lower()
        if app_name not in {item.lower() for item in self.config.allowed_apps}:
            return ActionResult(
                name="open_app",
                ok=False,
                message=f"App is not allowed: {name}",
                metadata={"app": name},
            )

        try:
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Start-Process {app_name}"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception as exc:
            return ActionResult(
                name="open_app",
                ok=False,
                message=f"Could not start {name}: {exc}",
                metadata={"app": name},
            )

        return ActionResult(
            name="open_app",
            ok=completed.returncode == 0,
            message=f"Opened {app_name}." if completed.returncode == 0 else f"Could not open {app_name}.",
            metadata={"app": app_name},
        )

    def prepare_whatsapp_message(self, message: str, recipient: str | None = None) -> ActionResult:
        text = message.strip()
        if not text:
            return ActionResult(
                name="whatsapp_message",
                ok=False,
                message="No message text was provided for WhatsApp.",
                metadata={},
            )

        encoded_text = quote_plus(text)
        if recipient:
            clean_recipient = "".join(ch for ch in recipient if ch.isdigit() or ch == "+")
            url = f"https://web.whatsapp.com/send?phone={quote_plus(clean_recipient)}&text={encoded_text}"
            label = f"Opened WhatsApp message draft for {recipient}."
        else:
            url = f"https://web.whatsapp.com/send?text={encoded_text}"
            label = "Opened WhatsApp with your draft message."

        return self.open_url(url, browser_name=self.config.preferred_browser, label=label)

    def open_website(self, website: str) -> ActionResult:
        candidate = website.strip()
        if not candidate:
            return ActionResult(
                name="open_website",
                ok=False,
                message="No website was provided.",
                metadata={},
            )

        if "." not in candidate and not candidate.startswith(("http://", "https://")):
            candidate = f"https://www.{candidate}.com"
        parsed = urlparse(candidate if candidate.startswith(("http://", "https://")) else "https://" + candidate)
        if not parsed.netloc:
            candidate = "https://" + candidate
        return self.open_url(candidate, browser_name=self.config.preferred_browser, label=f"Opened {candidate}")

    def write_note(self, filename: str, content: str) -> ActionResult:
        safe_name = Path(filename).name or "note.txt"
        target = self.paths.notes_dir / safe_name
        target.write_text(content, encoding="utf-8")
        return ActionResult(
            name="write_note",
            ok=True,
            message=f"Saved note to {target.name}.",
            metadata={"path": str(target)},
        )

    def list_folder(self, path_text: str) -> ActionResult:
        target = Path(path_text).expanduser()
        if not target.exists():
            return ActionResult(
                name="list_folder",
                ok=False,
                message=f"Path not found: {target}",
                metadata={"path": str(target)},
            )
        items = []
        for item in target.iterdir():
            items.append({"name": item.name, "type": "dir" if item.is_dir() else "file"})
        return ActionResult(
            name="list_folder",
            ok=True,
            message=f"Listed {len(items)} items in {target}.",
            metadata={"path": str(target), "items": items[:80]},
        )

    def reveal_data_folder(self) -> ActionResult:
        try:
            os.startfile(self.paths.root)  # type: ignore[attr-defined]
            return ActionResult(
                name="reveal_folder",
                ok=True,
                message="Opened the Jarvis project folder.",
                metadata={"path": str(self.paths.root)},
            )
        except Exception as exc:
            return ActionResult(
                name="reveal_folder",
                ok=False,
                message=f"Could not open the project folder: {exc}",
                metadata={"path": str(self.paths.root)},
            )

    def delete_path(self, path_text: str) -> ActionResult:
        target = Path(path_text).expanduser()
        if not target.exists():
            return ActionResult(
                name="delete_path",
                ok=False,
                message=f"Path not found: {target}",
                metadata={"path": str(target)},
            )
        try:
            if target.is_dir():
                shutil.rmtree(target)
                label = f"Deleted folder {target}"
                kind = "folder"
            else:
                target.unlink()
                label = f"Deleted file {target}"
                kind = "file"
            return ActionResult(
                name="delete_path",
                ok=True,
                message=label,
                metadata={"path": str(target), "kind": kind},
            )
        except Exception as exc:
            return ActionResult(
                name="delete_path",
                ok=False,
                message=f"Could not delete {target}: {exc}",
                metadata={"path": str(target)},
            )

    def move_path(self, source_text: str, dest_text: str) -> ActionResult:
        source = Path(source_text).expanduser()
        dest = Path(dest_text).expanduser()
        if not source.exists():
            return ActionResult(
                name="move_path",
                ok=False,
                message=f"Source not found: {source}",
                metadata={"source": str(source), "dest": str(dest)},
            )
        try:
            result = shutil.move(str(source), str(dest))
            return ActionResult(
                name="move_path",
                ok=True,
                message=f"Moved {source} to {dest}",
                metadata={"source": str(source), "dest": str(dest), "result": result},
            )
        except Exception as exc:
            return ActionResult(
                name="move_path",
                ok=False,
                message=f"Could not move {source} to {dest}: {exc}",
                metadata={"source": str(source), "dest": str(dest)},
            )

    def copy_path(self, source_text: str, dest_text: str) -> ActionResult:
        source = Path(source_text).expanduser()
        dest = Path(dest_text).expanduser()
        if not source.exists():
            return ActionResult(
                name="copy_path",
                ok=False,
                message=f"Source not found: {source}",
                metadata={"source": str(source), "dest": str(dest)},
            )
        if dest.exists():
            return ActionResult(
                name="copy_path",
                ok=False,
                message=f"Destination already exists: {dest}",
                metadata={"source": str(source), "dest": str(dest)},
            )
        try:
            if source.is_dir():
                shutil.copytree(source, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            return ActionResult(
                name="copy_path",
                ok=True,
                message=f"Copied {source} to {dest}",
                metadata={"source": str(source), "dest": str(dest)},
            )
        except Exception as exc:
            return ActionResult(
                name="copy_path",
                ok=False,
                message=f"Could not copy {source} to {dest}: {exc}",
                metadata={"source": str(source), "dest": str(dest)},
            )

    def create_folder(self, path_text: str) -> ActionResult:
        target = Path(path_text).expanduser()
        try:
            target.mkdir(parents=True, exist_ok=True)
            message = f"Created folder {target}" if target.exists() else f"Could not create {target}"
            return ActionResult(
                name="create_folder",
                ok=target.exists(),
                message=message,
                metadata={"path": str(target)},
            )
        except Exception as exc:
            return ActionResult(
                name="create_folder",
                ok=False,
                message=f"Could not create folder {target}: {exc}",
                metadata={"path": str(target)},
            )

    def write_file(self, path_text: str, content: str) -> ActionResult:
        target = Path(path_text).expanduser()
        if not target.parent.exists():
            return ActionResult(
                name="write_file",
                ok=False,
                message=f"Parent folder not found: {target.parent}",
                metadata={"path": str(target)},
            )
        try:
            target.write_text(content, encoding="utf-8")
            return ActionResult(
                name="write_file",
                ok=True,
                message=f"Wrote {len(content)} characters to {target}",
                metadata={"path": str(target)},
            )
        except Exception as exc:
            return ActionResult(
                name="write_file",
                ok=False,
                message=f"Could not write to {target}: {exc}",
                metadata={"path": str(target)},
            )

    def append_file(self, path_text: str, content: str) -> ActionResult:
        target = Path(path_text).expanduser()
        if not target.parent.exists():
            return ActionResult(
                name="append_file",
                ok=False,
                message=f"Parent folder not found: {target.parent}",
                metadata={"path": str(target)},
            )
        try:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(content)
            return ActionResult(
                name="append_file",
                ok=True,
                message=f"Appended {len(content)} characters to {target}",
                metadata={"path": str(target)},
            )
        except Exception as exc:
            return ActionResult(
                name="append_file",
                ok=False,
                message=f"Could not append to {target}: {exc}",
                metadata={"path": str(target)},
            )
