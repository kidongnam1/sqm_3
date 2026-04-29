"""Ollama local runtime manager.

This module intentionally never installs Ollama. It can detect the CLI, check
the local HTTP server, start `ollama serve`, and run an explicit model pull when
the user confirms it from the UI.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class OllamaStatus:
    installed: bool
    server_running: bool
    model_available: bool
    cli_path: str = ""
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:14b"
    message: str = ""


def find_ollama_cli() -> str:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return ""


def _request_json(url: str, timeout: float = 2.0) -> dict:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw or "{}")


def check_ollama_server(base_url: str = "http://localhost:11434") -> bool:
    try:
        _request_json(f"{base_url.rstrip('/')}/api/tags", timeout=2.0)
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("Ollama health check failed: %s", exc)
        return False


def start_ollama_server() -> bool:
    cli = find_ollama_cli()
    if not cli:
        return False
    try:
        kwargs = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen([cli, "serve"], **kwargs)
        for _ in range(10):
            time.sleep(0.4)
            if check_ollama_server():
                return True
        return check_ollama_server()
    except (OSError, ValueError) as exc:
        logger.warning("[Ollama] server start failed: %s", exc)
        return False


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    try:
        data = _request_json(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        logger.debug("Ollama model list failed: %s", exc)
        return []
    models = data.get("models", [])
    names = []
    for item in models:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def has_ollama_model(model: str, base_url: str = "http://localhost:11434") -> bool:
    target = str(model or "").strip()
    if not target:
        return False
    names = list_ollama_models(base_url)
    return any(name == target or name.startswith(f"{target}:") for name in names)


def pull_ollama_model(model: str) -> bool:
    cli = find_ollama_cli()
    if not cli:
        return False
    try:
        proc = subprocess.Popen(
            [cli, "pull", model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        return proc.wait() == 0
    except (OSError, ValueError) as exc:
        logger.warning("[Ollama] model pull failed: %s", exc)
        return False


def get_ollama_status(
    base_url: str = "http://localhost:11434",
    model: str = "qwen2.5:14b",
) -> OllamaStatus:
    cli = find_ollama_cli()
    installed = bool(cli)
    server_running = check_ollama_server(base_url) if installed else False
    model_available = has_ollama_model(model, base_url) if server_running else False
    if not installed:
        message = "Ollama CLI 미설치"
    elif not server_running:
        message = "Ollama 서버 중지"
    elif not model_available:
        message = f"Ollama 모델 없음: {model}"
    else:
        message = "Ollama 사용 가능"
    return OllamaStatus(
        installed=installed,
        server_running=server_running,
        model_available=model_available,
        cli_path=cli,
        base_url=base_url,
        model=model,
        message=message,
    )

