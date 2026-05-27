from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, request


@dataclass(slots=True)
class OllamaResponse:
    content: str
    tool_calls: list[dict[str, Any]]


class OllamaClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def list_models(self) -> list[str]:
        req = request.Request(
            url=f"{self.base_url}/api/tags",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                "Could not reach Ollama. Start Ollama and make sure it is running."
            ) from exc
        return [item["name"] for item in raw.get("models", [])]

    def chat(self, model: str, messages: list[dict], tools: list[dict] | None = None) -> OllamaResponse:
        raw = self._request_chat(model=model, messages=messages, tools=tools)
        message = raw.get("message", {})
        return OllamaResponse(
            content=message.get("content", ""),
            tool_calls=message.get("tool_calls", []) or [],
        )

    def _request_chat(self, model: str, messages: list[dict], tools: list[dict] | None = None) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
            },
        }
        if tools:
            payload["tools"] = tools

        req = request.Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if tools:
                # Some small local models and Ollama builds fail tool-call chat requests.
                return self._request_chat(model=model, messages=messages, tools=None)
            raise RuntimeError(
                f"Ollama returned HTTP {exc.code}. Response: {body or exc.reason}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(
                "Could not reach Ollama. Start Ollama and make sure the configured model is pulled."
            ) from exc
