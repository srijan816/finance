"""Lightweight experiment registry for reproducible research runs."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

RUNS_DIR = Path(__file__).parent.parent / "runs"


def save_run(kind: str, params: Dict[str, Any], result: Dict[str, Any]) -> str:
    RUNS_DIR.mkdir(exist_ok=True)
    manifest = build_run_manifest(kind, params, result)
    payload = {
        "kind": kind,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git_sha": manifest["git"]["sha"],
        "git_dirty": manifest["git"]["dirty"],
        "params": params,
        "result": result,
        "manifest": manifest,
    }
    run_id = _run_id(payload)
    path = RUNS_DIR / f"{run_id}.json"
    path.write_text(json.dumps({"run_id": run_id, **payload}, default=_json_default, indent=2, sort_keys=True))
    return str(path)


def build_run_manifest(kind: str, params: Dict[str, Any], result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Create a reproducibility manifest for saved research artifacts."""
    status = (result or {}).get("research_grade_status") if isinstance(result, dict) else None
    return {
        "kind": kind,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "git": {
            "sha": _git_sha(),
            "dirty": _git_dirty(),
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "params_hash": _stable_hash(params),
        "result_hash": None if result is None else _stable_hash(result),
        "research_grade_status": status,
        "data_quality_level": None if not status else status.get("level"),
        "data_source": None if not status else status.get("data_source"),
        "universe_source": None if not status else status.get("universe_source"),
        "validation_method": None if not status else status.get("validation_method"),
    }


def _run_id(payload: Dict[str, Any]) -> str:
    stable = json.dumps({
        "kind": payload["kind"],
        "created_at": payload["created_at"],
        "params": payload["params"],
    }, sort_keys=True)
    return hashlib.sha256(stable.encode()).hexdigest()[:16]


def _stable_hash(value: Any) -> str:
    encoded = json.dumps(value, default=_json_default, sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def _git_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return completed.stdout.strip()
    except Exception:
        return None


def _git_dirty() -> bool | None:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=Path(__file__).parent.parent,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(completed.stdout.strip())
    except Exception:
        return None


def _json_default(value):
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")
