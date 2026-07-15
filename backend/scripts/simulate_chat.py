import importlib
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `backend` package imports correctly
repo_root = str(Path(__file__).resolve().parents[2])
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
from types import SimpleNamespace

agent = importlib.import_module('backend.agent')
orig = agent._client.models.generate_content

calls = []

def fake_generate_content(model, contents, config):
    calls.append(model)
    n = len(calls)
    # For the configured model: two transient 503s, then a not-found
    if model == agent.settings.GEMINI_MODEL:
        if n <= 2:
            raise Exception('503 Service Unavailable: high demand')
        if n == 3:
            raise Exception(f'models/{model} not found')
    # Otherwise return a simple simulated response
    candidate = SimpleNamespace(content=SimpleNamespace(parts=None), text=f"Simulated reply from {model}")
    return SimpleNamespace(candidates=[candidate], text=f"Simulated reply from {model}")

# Patch
agent._client.models.generate_content = fake_generate_content

try:
    reply = agent.handle_message('simulate retries and fallback', credentials=None, project_id='demo-project')
    print('REPLY:', reply)
    print('CALLS:', calls)
finally:
    # Restore
    agent._client.models.generate_content = orig
