# Jarvis Local Agent

Jarvis is now structured as a fuller local MVP for your laptop:

- local-first web app
- custom dashboard UI
- browser voice input and speech output
- task and activity memory in SQLite
- automation for opening apps and running browser searches
- profile-based personalization

## Core architecture

Jarvis uses multiple internal roles:

- `Planner` decides what kind of task you asked for
- `Executor` runs app or browser actions
- `Memory` recalls tasks, activities, notes, and saved facts
- `Historian` records what you did so Jarvis can answer later
- `Responder` formats a useful answer and uses Ollama when available

This keeps the system useful even when the local model is tiny or temporarily unavailable.

## What it can do now

- chat through a local browser UI
- take voice input in the browser
- speak responses back
- open your browser and search a query
- open allowed desktop apps
- create and list tasks
- remember activities like applications, submissions, or completed work
- ingest your own notes and files for recall later

## Recommended model for your current laptop

For your current hardware, the safest default is:

- `qwen2.5:0.5b`

If you later free more RAM, test:

- `qwen3:1.7b`

## Setup

```powershell
cd C:\Users\LENOVO\Documents\Codex\2026-05-27\i-want-to-build-an-agent\jarvis
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `config.json` does not exist, it will be created from `config.example.json`.

## Run the app

```powershell
python -m jarvis_app.main serve
```

Then open:

`http://127.0.0.1:8765`

## Start automatically with Windows

To register Jarvis so it starts automatically after you sign in:

```powershell
.\install_startup.ps1
```

To remove the startup registration later:

```powershell
.\remove_startup.ps1
```

## Useful commands

```powershell
python -m jarvis_app.main serve
python -m jarvis_app.main run "open my browser and search for AI internships in Bangalore"
python -m jarvis_app.main ingest --path C:\Users\LENOVO\Documents
python -m jarvis_app.main profile show
python -m jarvis_app.main tasks
```

## Personalization

Jarvis is personalized by:

- `profile.json`
- saved facts
- activity history
- ingested documents

This is much better for your laptop than trying to fine-tune or retrain models.

## Notes

- Browser voice features depend on your browser supporting Web Speech APIs.
- App launching is intentionally restricted to allowed apps from `config.json`.
- The UI is local and private, but the speech recognition quality can vary by browser.
# Jarvis
