from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .automation import ActionResult, AutomationHub
from .memory import MemoryStore
from .ollama_client import OllamaClient
from .profile import ProfileStore


@dataclass(slots=True)
class PlannedStep:
    agent: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass(slots=True)
class AgentOutcome:
    reply: str
    actions: list[dict[str, Any]]
    memory_hits: list[dict[str, Any]]


class MemoryAgent:
    def __init__(self, memory: MemoryStore, profile: ProfileStore) -> None:
        self.memory = memory
        self.profile = profile

    def build_context(self, user_text: str) -> dict[str, Any]:
        return {
            "profile": self.profile.load(),
            "memory_hits": self.memory.search(user_text, limit=6),
            "recent_activities": self.memory.recent_activities(6),
            "open_tasks": self.memory.list_tasks("open")[:6],
        }

    def recall_actions(self, query: str) -> list[dict[str, Any]]:
        normalized = query.lower()
        if "internship" in normalized or "apply" in normalized or "applied" in normalized:
            results = self.memory.search_activities("internship", limit=8)
            if results:
                return results
        if "search" in normalized or "browser" in normalized:
            results = self.memory.search_activities("browser", limit=8)
            if results:
                return results

        tokens = [token for token in re.findall(r"[a-zA-Z0-9]+", normalized) if len(token) > 3]
        for token in tokens:
            results = self.memory.search_activities(token, limit=8)
            if results:
                return results
        return self.memory.recent_activities(8)

    def capture_user_activity(self, user_text: str) -> list[int]:
        saved: list[int] = []
        patterns = [
            ("internship", r"\bi applied for (?:an?\s+)?(.+)", "Internship application"),
            ("submission", r"\bi submitted (.+)", "Submission"),
            ("email", r"\bi emailed (.+)", "Email sent"),
            ("meeting", r"\bi attended (.+)", "Meeting attended"),
            ("task_done", r"\bi completed (.+)", "Completed work"),
            ("task_done", r"\bi finished (.+)", "Finished work"),
        ]
        normalized = user_text.strip()
        for kind, pattern, title in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if match:
                detail = match.group(1).strip().rstrip(".")
                saved.append(
                    self.memory.add_activity(
                        kind=kind,
                        title=title,
                        details=detail,
                        source="user",
                        metadata={"captured_from": normalized},
                    )
                )
        remember_match = re.search(r"\bremember that (.+)", normalized, flags=re.IGNORECASE)
        if remember_match:
            statement = remember_match.group(1).strip().rstrip(".")
            self.memory.save_fact("remembered_note", statement, source="user")
        return saved


class PlannerAgent:
    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def plan(self, user_text: str) -> list[PlannedStep]:
        text = user_text.strip()
        lowered = text.lower()
        steps: list[PlannedStep] = []

        pending = self.memory.get_state("pending_action")
        if pending:
            if self._looks_like_confirm(lowered):
                return [
                    PlannedStep(
                        agent="planner",
                        action="confirm_pending",
                        reason="The user confirmed the pending action.",
                    )
                ]
            if self._looks_like_cancel(lowered):
                return [
                    PlannedStep(
                        agent="planner",
                        action="cancel_pending",
                        reason="The user cancelled the pending action.",
                    )
                ]
            summary = pending.get("summary", "the previous request")
            return [
                PlannedStep(
                    agent="planner",
                    action="pending_requires_confirmation",
                    params={"summary": summary},
                    reason="A pending action needs confirmation before new tasks.",
                )
            ]

        delete_match = re.search(
            r"\b(?:delete|remove)\s+(?:the\s+)?(?:file|folder|directory)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if delete_match:
            path = self._clean_path(delete_match.group(1))
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="delete_path",
                    params={"path": path},
                    reason="The user asked to delete a file or folder.",
                )
            )

        move_match = re.search(
            r"\bmove\s+(?:the\s+)?(?:file|folder|directory)\s+(.+?)\s+(?:to|into)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if move_match:
            source = self._clean_path(move_match.group(1))
            dest = self._clean_path(move_match.group(2))
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="move_path",
                    params={"source": source, "dest": dest},
                    reason="The user asked to move a file or folder.",
                )
            )

        copy_match = re.search(
            r"\bcopy\s+(?:the\s+)?(?:file|folder|directory)\s+(.+?)\s+(?:to|into)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if copy_match:
            source = self._clean_path(copy_match.group(1))
            dest = self._clean_path(copy_match.group(2))
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="copy_path",
                    params={"source": source, "dest": dest},
                    reason="The user asked to copy a file or folder.",
                )
            )

        rename_match = re.search(
            r"\brename\s+(?:the\s+)?(?:file|folder|directory)\s+(.+?)\s+to\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if rename_match:
            source = self._clean_path(rename_match.group(1))
            dest = self._clean_path(rename_match.group(2))
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="move_path",
                    params={"source": source, "dest": dest},
                    reason="The user asked to rename a file or folder.",
                )
            )

        create_folder_match = re.search(
            r"\b(?:create|make)\s+(?:a\s+)?(?:folder|directory)\s+(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if create_folder_match:
            path = self._clean_path(create_folder_match.group(1))
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="create_folder",
                    params={"path": path},
                    reason="The user asked to create a folder.",
                )
            )

        append_match = re.search(
            r"\bappend\s+to\s+file\s+(.+?)\s*[:,-]\s*(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if append_match:
            path = self._clean_path(append_match.group(1))
            content = append_match.group(2).strip()
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="append_file",
                    params={"path": path, "content": content},
                    reason="The user asked to append to a file.",
                )
            )

        write_match = re.search(
            r"\b(?:write|overwrite|create)\s+file\s+(.+?)\s*[:,-]\s*(.+)",
            text,
            flags=re.IGNORECASE,
        )
        if write_match:
            path = self._clean_path(write_match.group(1))
            content = write_match.group(2).strip()
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="write_file",
                    params={"path": path, "content": content},
                    reason="The user asked to write a file.",
                )
            )

        if "open my browser" in lowered or "search for" in lowered or lowered.startswith("google "):
            query = self._extract_search_query(text)
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="browser_search",
                    params={"query": query},
                    reason="The user asked for a browser search.",
                )
            )

        whatsapp_match = re.search(
            r"(?:open\s+(?:my\s+)?whatsapp(?:\s+and)?\s+(?:write|type|draft)\s+(?:a\s+)?text(?:\s+message)?(?:\s+to\s+(.+?))?\s*[:,-]?\s*(.+))",
            text,
            flags=re.IGNORECASE,
        )
        if whatsapp_match:
            recipient = whatsapp_match.group(1).strip() if whatsapp_match.group(1) else None
            message = whatsapp_match.group(2).strip()
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="prepare_whatsapp_message",
                    params={"recipient": recipient, "message": message},
                    reason="The user asked to open WhatsApp and draft a message.",
                )
            )

        open_site_match = re.search(r"\bopen\s+(?:the\s+)?website\s+(.+)", text, flags=re.IGNORECASE)
        if open_site_match:
            website = open_site_match.group(1).strip().rstrip(".")
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="open_website",
                    params={"website": website},
                    reason="The user asked to open a website.",
                )
            )

        open_app_match = re.search(
            r"\bopen\s+(?:my\s+)?(chrome|browser|edge|msedge|notepad|calculator|calc|paint|mspaint|code|vscode|whatsapp)\b",
            lowered,
        )
        if open_app_match and not steps:
            app_name = open_app_match.group(1)
            if app_name == "browser":
                app_name = "chrome"
            if app_name == "calculator":
                app_name = "calc"
            if app_name == "paint":
                app_name = "mspaint"
            if app_name == "vscode":
                app_name = "code"
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="open_app",
                    params={"name": app_name},
                    reason="The user asked to open an app.",
                )
            )

        todo_match = re.search(r"(?:add task|create task|todo|remind me to)\s+(.+)", lowered)
        if todo_match:
            title = todo_match.group(1).strip().rstrip(".")
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="create_task",
                    params={"title": title},
                    reason="The user requested a task or reminder.",
                )
            )

        note_match = re.search(r"(?:write note|save note|create note)\s+(.+)", text, flags=re.IGNORECASE)
        if note_match:
            content = note_match.group(1).strip()
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="write_note",
                    params={"filename": "jarvis-note.txt", "content": content},
                    reason="The user asked to save a note.",
                )
            )

        history_markers = [
            "what did i do",
            "did i apply",
            "have i applied",
            "what have i done",
            "show my recent actions",
            "what tasks did i perform",
        ]
        if any(marker in lowered for marker in history_markers):
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="recall_actions",
                    params={"query": text},
                    reason="The user is asking about past activity.",
                )
            )

        if not steps:
            steps.append(
                PlannedStep(
                    agent="planner",
                    action="converse",
                    params={"text": text},
                    reason="No direct automation matched, so answer conversationally.",
                )
            )
        return steps

    @staticmethod
    def _clean_path(value: str) -> str:
        cleaned = value.strip().strip("\"'")
        return cleaned.rstrip(". ")

    @staticmethod
    def _looks_like_confirm(lowered: str) -> bool:
        confirmations = ["yes", "confirm", "go ahead", "do it", "proceed", "okay", "ok", "sure"]
        return any(item in lowered for item in confirmations)

    @staticmethod
    def _looks_like_cancel(lowered: str) -> bool:
        cancels = ["no", "cancel", "stop", "abort", "dont", "don't", "do not", "never mind", "nevermind"]
        return any(item in lowered for item in cancels)

    @staticmethod
    def _extract_search_query(text: str) -> str:
        patterns = ["search for", "google", "look up", "find"]
        lowered = text.lower()
        for pattern in patterns:
            if pattern in lowered:
                idx = lowered.index(pattern) + len(pattern)
                return text[idx:].strip(" :.-")
        return ""


class ExecutorAgent:
    def __init__(self, memory: MemoryStore, automation: AutomationHub, memory_agent: MemoryAgent) -> None:
        self.memory = memory
        self.automation = automation
        self.memory_agent = memory_agent

    def execute(self, step: PlannedStep) -> ActionResult:
        action = step.action
        if action == "confirm_pending":
            pending = self.memory.get_state("pending_action")
            if not pending:
                return ActionResult(
                    name="confirm_pending",
                    ok=False,
                    message="There is no pending action to confirm.",
                    metadata={},
                )
            self.memory.clear_state("pending_action")
            return self._execute_action(pending.get("action", ""), pending.get("params", {}), allow_confirm=False)

        if action == "cancel_pending":
            self.memory.clear_state("pending_action")
            return ActionResult(
                name="cancel_pending",
                ok=True,
                message="Cancelled the pending action.",
                metadata={},
            )

        if action == "pending_requires_confirmation":
            summary = step.params.get("summary", "the previous request")
            return ActionResult(
                name="confirmation_required",
                ok=True,
                message=f"Please confirm or cancel before I proceed: {summary}.",
                metadata={"summary": summary},
            )

        return self._execute_action(action, step.params)

    def _execute_action(
        self,
        action: str,
        params: dict[str, Any],
        allow_confirm: bool = True,
    ) -> ActionResult:
        if allow_confirm and self._requires_confirmation(action):
            summary = self._summarize_action(action, params)
            self.memory.set_state(
                "pending_action",
                {"action": action, "params": params, "summary": summary},
            )
            return ActionResult(
                name="confirmation_required",
                ok=True,
                message=f"I can {summary}. Reply 'confirm' to proceed or 'cancel' to stop.",
                metadata={"summary": summary},
            )

        if action == "browser_search":
            result = self.automation.open_browser_search(params.get("query", ""))
            if result.ok:
                self.memory.add_activity(
                    kind="browser_search",
                    title="Browser search",
                    details=params.get("query", "Opened browser"),
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "open_app":
            result = self.automation.open_app(params["name"])
            if result.ok:
                self.memory.add_activity(
                    kind="app_launch",
                    title="Opened app",
                    details=params["name"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "prepare_whatsapp_message":
            result = self.automation.prepare_whatsapp_message(
                message=params["message"],
                recipient=params.get("recipient"),
            )
            if result.ok:
                self.memory.add_activity(
                    kind="whatsapp",
                    title="WhatsApp draft opened",
                    details=params["message"][:180],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "open_website":
            result = self.automation.open_website(params["website"])
            if result.ok:
                self.memory.add_activity(
                    kind="website",
                    title="Opened website",
                    details=params["website"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "create_task":
            task_id = self.memory.create_task(params["title"])
            self.memory.add_activity(
                kind="task",
                title="Task created",
                details=params["title"],
                source="agent",
                metadata={"task_id": task_id},
            )
            return ActionResult(
                name="create_task",
                ok=True,
                message=f"Created task #{task_id}: {params['title']}",
                metadata={"task_id": task_id},
            )

        if action == "write_note":
            result = self.automation.write_note(params["filename"], params["content"])
            if result.ok:
                self.memory.add_activity(
                    kind="note",
                    title="Saved note",
                    details=params["filename"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "delete_path":
            result = self.automation.delete_path(params["path"])
            if result.ok:
                self.memory.add_activity(
                    kind="file_delete",
                    title="Deleted path",
                    details=params["path"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "move_path":
            result = self.automation.move_path(params["source"], params["dest"])
            if result.ok:
                self.memory.add_activity(
                    kind="file_move",
                    title="Moved path",
                    details=f"{params['source']} -> {params['dest']}",
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "copy_path":
            result = self.automation.copy_path(params["source"], params["dest"])
            if result.ok:
                self.memory.add_activity(
                    kind="file_copy",
                    title="Copied path",
                    details=f"{params['source']} -> {params['dest']}",
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "create_folder":
            result = self.automation.create_folder(params["path"])
            if result.ok:
                self.memory.add_activity(
                    kind="folder_create",
                    title="Folder created",
                    details=params["path"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "write_file":
            result = self.automation.write_file(params["path"], params["content"])
            if result.ok:
                self.memory.add_activity(
                    kind="file_write",
                    title="File written",
                    details=params["path"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "append_file":
            result = self.automation.append_file(params["path"], params["content"])
            if result.ok:
                self.memory.add_activity(
                    kind="file_append",
                    title="File appended",
                    details=params["path"],
                    source="agent",
                    metadata=result.metadata,
                )
            return result

        if action == "recall_actions":
            results = self.memory_agent.recall_actions(params["query"])
            return ActionResult(
                name="recall_actions",
                ok=True,
                message=f"Found {len(results)} related activities.",
                metadata={"results": results},
            )

        return ActionResult(
            name="converse",
            ok=True,
            message="Handled as a conversational request.",
            metadata={},
        )

    def _requires_confirmation(self, action: str) -> bool:
        if not self.automation.config.confirm_file_changes:
            return False
        return action in {
            "delete_path",
            "move_path",
            "copy_path",
            "create_folder",
            "write_file",
            "append_file",
        }

    @staticmethod
    def _summarize_action(action: str, params: dict[str, Any]) -> str:
        if action == "delete_path":
            return f"delete {params.get('path', 'the path')}"
        if action == "move_path":
            return f"move {params.get('source', 'the path')} to {params.get('dest', 'the destination')}"
        if action == "copy_path":
            return f"copy {params.get('source', 'the path')} to {params.get('dest', 'the destination')}"
        if action == "create_folder":
            return f"create the folder {params.get('path', '')}".strip()
        if action == "write_file":
            return f"overwrite {params.get('path', 'the file')}"
        if action == "append_file":
            return f"append to {params.get('path', 'the file')}"
        return "perform this action"


class ResponderAgent:
    def __init__(self, memory: MemoryStore, ollama: OllamaClient | None, model_name: str | None) -> None:
        self.memory = memory
        self.ollama = ollama
        self.model_name = model_name

    def respond(
        self,
        user_text: str,
        context: dict[str, Any],
        steps: list[PlannedStep],
        action_results: list[ActionResult],
        captured_activity_ids: list[int] | None = None,
    ) -> str:
        if captured_activity_ids and all(item.name == "converse" for item in action_results):
            return "I have saved that in your activity history, so I can recall it later."

        if action_results:
            recall_result = next((item for item in action_results if item.name == "recall_actions"), None)
            if recall_result:
                hits = recall_result.metadata.get("results", [])
                if not hits:
                    return "I could not find a matching past activity yet."
                lines = ["Here is what I found in your activity history:"]
                for item in hits[:5]:
                    lines.append(f"- {item['created_at']}: {item['title']} - {item['details']}")
                return "\n".join(lines)

            direct_actions = [item for item in action_results if item.name != "converse"]
            if direct_actions:
                summary = " ".join(item.message for item in direct_actions)
                return summary

        return self._llm_or_fallback(user_text, context)

    def _llm_or_fallback(self, user_text: str, context: dict[str, Any]) -> str:
        if self.ollama and self.model_name:
            prompt = (
                "You are Jarvis, a concise local assistant. "
                "Answer using the provided memory context when useful.\n\n"
                f"Context: {context}\n\n"
                f"User: {user_text}"
            )
            try:
                response = self.ollama.chat(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a concise, practical Windows assistant."},
                        {"role": "user", "content": prompt},
                    ],
                    tools=None,
                )
                if response.content.strip():
                    return response.content.strip()
            except Exception:
                pass

        memory_hits = context.get("memory_hits", [])
        if memory_hits:
            top = memory_hits[0]
            return f"I found a related memory entry: {top.get('label', top.get('kind', 'memory'))} - {top.get('snippet', '')[:240]}"
        return "I am ready. Ask me to open an app, search the web, create a task, save a note, or recall what you did earlier."
