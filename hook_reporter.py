#!/usr/bin/env python3
"""Antigravity CLI Lifecycle Hook Bridge -> agy-companion state.json.

Dijalankan oleh Antigravity CLI melalui ~/.gemini/config/hooks.json.
100% Python standard library & 100% lokal (0 token tambahan).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from dialogue_engine import classify_tool_call, pick_presentation

STATE_FILE_ENV = "AGY_COMPANION_STATE_FILE"
DEFAULT_STATE_PATH = Path.home() / ".agy-companion" / "state.json"


def get_default_state_path() -> Path:
    env_val = os.environ.get(STATE_FILE_ENV, "").strip()
    return Path(env_val) if env_val else DEFAULT_STATE_PATH


def atomic_write_json(path: Path, data: dict[str, Any], retries: int = 4) -> None:
    """Tulis JSON secara atomic agar companion tidak pernah membaca file setengah jadi.

    Di Windows, os.replace sesekali bisa terkena PermissionError jika reader sedang
    membuka file di milidetik yang sama; lakukan retry singkat sebelum menyerah.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".state_", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        for attempt in range(max(1, retries)):
            try:
                os.replace(tmp_name, path)
                return
            except PermissionError:
                if attempt + 1 >= retries:
                    raise
                time.sleep(0.015 * (attempt + 1))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def map_event_to_update(event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Petakan event Antigravity ke state animasi + [Status], [Mood], dan dialog lokal."""
    tool_call = payload.get("toolCall") if isinstance(payload.get("toolCall"), dict) else None
    tool_name = str(tool_call.get("name", "")) if tool_call else ""
    last_user_input = str(payload.get("lastUserInput", ""))

    if event == "SessionStart":
        pres = pick_presentation("idle")
        return {"state": "idle", "detail": "ready", **pres}

    if event == "PreInvocation":
        pres = pick_presentation("thinking", user_input=last_user_input)
        return {"state": "thinking", "detail": "analyzing", **pres}

    if event == "PreToolUse":
        activity, target = classify_tool_call(tool_call)
        pres = pick_presentation(activity, target=target)
        return {"state": "coding", "detail": target or tool_name, **pres}

    if event == "PostToolUse":
        # Hanya ubah tampilan jika tool gagal agar dialog PreToolUse tidak berkedip
        if payload.get("error"):
            _, target = classify_tool_call(tool_call)
            pres = pick_presentation("error", target=target or tool_name)
            return {"state": "error", "detail": target or tool_name or "error", **pres}
        return None

    if event == "Stop":
        reason = str(payload.get("terminationReason", "")).upper()
        if reason == "ERROR" or payload.get("error"):
            pres = pick_presentation("error")
            return {"state": "error", "detail": reason.lower() or "error", **pres}
        pres = pick_presentation("done")
        return {"state": "done", "detail": reason.lower() or "completed", **pres}

    return None


def emit_hook_response(event: str, pretool_decision: str) -> None:
    """Keluarkan kontrak JSON stdout yang aman sesuai event Antigravity."""
    if event == "PreToolUse":
        if pretool_decision in {"allow", "ask", "force_ask", "deny"}:
            print(json.dumps({"decision": pretool_decision}))
        return

    if event == "Stop":
        print(json.dumps({"decision": "stop"}))
        return

    print("{}")


def read_stdin_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Laporkan state Antigravity CLI ke agy-companion (0 token)."
    )
    parser.add_argument(
        "--event",
        help="Override nama event hook (default: ambil dari hookEventName di stdin).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help=(
            f"Lokasi file state JSON (default: env {STATE_FILE_ENV} "
            f"atau {DEFAULT_STATE_PATH})."
        ),
    )
    parser.add_argument(
        "--pretool-decision",
        choices=["none", "ask", "allow"],
        default="none",
        help="Respons stdout untuk PreToolUse (default: none / pass-through).",
    )
    args = parser.parse_args()
    state_file = args.state_file if args.state_file is not None else get_default_state_path()

    payload = read_stdin_payload()
    event = args.event or str(payload.get("hookEventName", ""))

    update = map_event_to_update(event, payload)
    if update is not None:
        state_data = {
            **update,
            "event": event,
            "conversationId": payload.get("conversationId", ""),
            "updatedAt": time.time(),
        }
        try:
            atomic_write_json(state_file, state_data)
        except OSError:
            pass

    emit_hook_response(event, args.pretool_decision)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
