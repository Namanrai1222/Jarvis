from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .automation import ActionResult, AutomationHub
from .brains import MemoryAgent, PlannerAgent, ResponderAgent, ExecutorAgent
from .config import AppConfig
from .memory import MemoryStore
from .ollama_client import OllamaClient
from .profile import ProfileStore


class JarvisAgent:
    def __init__(
        self,
        config: AppConfig,
        memory: MemoryStore,
        profile: ProfileStore,
        ollama: OllamaClient | None,
        model_name: str | None,
        automation: AutomationHub,
    ) -> None:
        self.config = config
        self.memory = memory
        self.profile = profile
        self.ollama = ollama
        self.model_name = model_name
        self.memory_agent = MemoryAgent(memory, profile)
        self.planner = PlannerAgent(memory)
        self.executor = ExecutorAgent(memory, automation, self.memory_agent)
        self.responder = ResponderAgent(memory, ollama, model_name)

    def handle(self, user_text: str) -> dict[str, Any]:
        captured_ids = self.memory_agent.capture_user_activity(user_text)
        context = self.memory_agent.build_context(user_text)
        steps = self.planner.plan(user_text)

        action_results: list[ActionResult] = []
        for step in steps:
            result = self.executor.execute(step)
            action_results.append(result)

        reply = self.responder.respond(
            user_text,
            context,
            steps,
            action_results,
            captured_activity_ids=captured_ids,
        )
        actions_payload = [asdict(item) for item in action_results]

        self.memory.log_interaction(
            user_text=user_text,
            assistant_text=reply,
            tool_trace=str(actions_payload),
        )
        return {
            "reply": reply,
            "actions": actions_payload,
            "captured_activity_ids": captured_ids,
            "dashboard": self.memory.dashboard_state(),
            "model_name": self.model_name,
        }

    def reply(self, user_text: str) -> str:
        return self.handle(user_text)["reply"]
