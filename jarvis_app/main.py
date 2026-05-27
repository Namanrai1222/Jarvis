from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn

from .agent import JarvisAgent
from .automation import AutomationHub
from .config import AppConfig, get_paths, load_config
from .ingest import ingest_path
from .memory import MemoryStore
from .ollama_client import OllamaClient
from .profile import ProfileStore
from .server import create_app


def choose_model(config: AppConfig, ollama: OllamaClient) -> str:
    installed = ollama.list_models()
    if config.main_model in installed:
        return config.main_model

    preferred_fallbacks = [
        "qwen2.5:0.5b",
        "tinyllama:latest",
        "llama3.2:1b",
        "qwen3:1.7b",
    ]
    for model in preferred_fallbacks:
        if model in installed:
            return model
    if installed:
        return installed[0]
    raise RuntimeError("No Ollama models are installed.")


def build_agent() -> tuple[JarvisAgent, MemoryStore, ProfileStore, AppConfig]:
    paths = get_paths()
    config = load_config(paths)
    memory = MemoryStore(paths.db_path)
    profile = ProfileStore(paths.profile_path)
    automation = AutomationHub(config, paths)

    ollama: OllamaClient | None = None
    model_name: str | None = None
    try:
        ollama = OllamaClient(config.ollama_base_url)
        model_name = choose_model(config, ollama)
    except Exception:
        ollama = None
        model_name = None

    agent = JarvisAgent(
        config=config,
        memory=memory,
        profile=profile,
        ollama=ollama,
        model_name=model_name,
        automation=automation,
    )
    return agent, memory, profile, config


def cmd_chat() -> int:
    agent, _, _, _ = build_agent()
    print("Jarvis is ready. Type 'exit' to quit.")
    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_text:
            continue
        if user_text.lower() in {"exit", "quit"}:
            return 0
        print(f"jarvis> {agent.reply(user_text)}")


def cmd_run(text: str) -> int:
    agent, _, _, _ = build_agent()
    print(agent.reply(text))
    return 0


def cmd_ingest(path_text: str) -> int:
    _, memory, _, _ = build_agent()
    path = Path(path_text).expanduser()
    if not path.exists():
        print(f"Path not found: {path}")
        return 1
    stored = ingest_path(memory, path)
    print(f"Ingested {len(stored)} file(s).")
    for item in stored[:20]:
        print(f"- {item}")
    return 0


def cmd_profile_show() -> int:
    _, _, profile, _ = build_agent()
    print(profile.load())
    return 0


def cmd_profile_set(key: str, value: str) -> int:
    _, _, profile, _ = build_agent()
    print(profile.set(key, value))
    return 0


def cmd_tasks() -> int:
    _, memory, _, _ = build_agent()
    tasks = memory.list_tasks()
    if not tasks:
        print("No tasks found.")
        return 0
    for task in tasks:
        print(f"[{task['id']}] {task['status']} - {task['title']}")
        if task["details"]:
            print(f"    {task['details']}")
    return 0


def cmd_serve() -> int:
    agent, memory, profile, config = build_agent()
    paths = get_paths()
    app = create_app(agent, paths, memory, profile)
    uvicorn.run(app, host=config.server_host, port=config.server_port, log_level="info")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jarvis local agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("chat", help="Start interactive chat")
    sub.add_parser("serve", help="Start the local web app")

    run_parser = sub.add_parser("run", help="Run a one-shot instruction")
    run_parser.add_argument("text", help="Instruction for Jarvis")

    ingest_parser = sub.add_parser("ingest", help="Ingest files or folders into memory")
    ingest_parser.add_argument("--path", required=True, help="File or folder path")

    profile_parser = sub.add_parser("profile", help="View or update profile")
    profile_sub = profile_parser.add_subparsers(dest="profile_command", required=True)
    profile_sub.add_parser("show", help="Show profile")
    profile_set_parser = profile_sub.add_parser("set", help="Set profile field")
    profile_set_parser.add_argument("key")
    profile_set_parser.add_argument("value")

    sub.add_parser("tasks", help="List tasks")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "chat":
        return cmd_chat()
    if args.command == "serve":
        return cmd_serve()
    if args.command == "run":
        return cmd_run(args.text)
    if args.command == "ingest":
        return cmd_ingest(args.path)
    if args.command == "profile":
        if args.profile_command == "show":
            return cmd_profile_show()
        if args.profile_command == "set":
            return cmd_profile_set(args.key, args.value)
    if args.command == "tasks":
        return cmd_tasks()

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
