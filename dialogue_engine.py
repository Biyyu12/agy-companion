#!/usr/bin/env python3
"""Engine lokal (0 token) untuk menentukan [Status], [Mood], dan dialog santai.

Membaca template dari dialogue.json sehingga kamu bisa bebas mengubah
kepribadian karakter tanpa menyentuh kode Python.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

DEFAULT_DIALOGUE_PATH = Path(__file__).resolve().parent / "dialogue.json"

READ_TOOLS = {
    "read_file",
    "view_file",
    "view_file_outline",
    "view_code_item",
    "list_dir",
    "read_resource",
}
EDIT_TOOLS = {
    "edit_file",
    "write_file",
    "write_to_file",
    "replace_file_content",
    "multi_replace_file_content",
}
RUN_TOOLS = {
    "run_command",
    "execute_command",
    "command_status",
    "bash",
    "shell",
}
SEARCH_TOOLS = {
    "grep_search",
    "find_by_name",
    "search_web",
    "read_url_content",
    "search_marketplace",
}


_DIALOGUE_CACHE: dict[Path, tuple[int, dict[str, Any]]] = {}


def load_dialogue_config(path: Path = DEFAULT_DIALOGUE_PATH) -> dict[str, Any]:
    """Baca dialogue.json dengan cache berbasis mtime_ns (mendukung live-reload)."""
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        _DIALOGUE_CACHE.pop(path, None)
        return {"activities": {}}

    cached = _DIALOGUE_CACHE.get(path)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        result = data if isinstance(data, dict) else {"activities": {}}
        _DIALOGUE_CACHE[path] = (mtime_ns, result)
        return result
    except (OSError, json.JSONDecodeError):
        return cached[1] if cached is not None else {"activities": {}}


def _basename(raw_path: str) -> str:
    cleaned = raw_path.strip().strip("\"'")
    if not cleaned:
        return ""
    # Tangani separator Windows maupun POSIX
    parts = cleaned.replace("\\", "/").rstrip("/").split("/")
    return parts[-1] if parts else cleaned


def _shorten(text: str, max_len: int = 22) -> str:
    compact = " ".join(text.strip().split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1].rstrip() + "…"


def classify_tool_call(tool_call: dict[str, Any] | None) -> tuple[str, str]:
    """Klasifikasikan toolCall dari payload hook -> (activity, target_singkat)."""
    if not isinstance(tool_call, dict):
        return "coding", ""

    name = str(tool_call.get("name", "")).strip()
    lower_name = name.lower()
    args = tool_call.get("args")
    args_dict = args if isinstance(args, dict) else {}

    def first_arg(*keys: str) -> str:
        for k in keys:
            val = args_dict.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
        return ""

    if lower_name in READ_TOOLS or "read" in lower_name or "view" in lower_name:
        raw = first_arg("Path", "path", "AbsolutePath", "TargetFile", "File", "file_path", "DirectoryPath")
        return "reading", _shorten(_basename(raw), 24) if raw else ""

    if lower_name in EDIT_TOOLS or "edit" in lower_name or "write" in lower_name or "replace" in lower_name:
        raw = first_arg("Path", "path", "TargetFile", "file_path")
        return "editing", _shorten(_basename(raw), 24) if raw else ""

    if lower_name in RUN_TOOLS or "command" in lower_name:
        raw = first_arg("CommandLine", "command", "cmd")
        if raw:
            # Ambil 2-3 kata pertama agar ringkas & enak dibaca
            tokens = raw.split()
            snippet = " ".join(tokens[:3])
            return "running", _shorten(snippet, 22)
        return "running", ""

    if lower_name in SEARCH_TOOLS or "search" in lower_name or "grep" in lower_name or "find" in lower_name:
        raw = first_arg("Query", "query", "Pattern", "pattern", "SearchTerm")
        return "searching", _shorten(raw, 22) if raw else ""

    return "coding", _shorten(name, 22)


DEFAULT_PERSONA = "santai"


def list_personas(config_path: Path = DEFAULT_DIALOGUE_PATH) -> list[str]:
    """Kembalikan daftar gaya bahasa/persona yang tersedia di dialogue.json."""
    cfg = load_dialogue_config(config_path)
    personas = cfg.get("personas")
    names = [DEFAULT_PERSONA]
    if isinstance(personas, dict):
        for key in personas:
            k = str(key).strip()
            if k and k not in names:
                names.append(k)
    return names


def pick_presentation(
    activity: str,
    target: str = "",
    user_input: str = "",
    config_path: Path = DEFAULT_DIALOGUE_PATH,
    persona: str = DEFAULT_PERSONA,
) -> dict[str, str]:
    """Pilih status, mood, dan 1 kalimat dialog berdasarkan konteks lokal & persona."""
    cfg = load_dialogue_config(config_path)
    activities = cfg.get("activities", {})
    base_entry = activities.get(activity) or activities.get("idle") or {}
    entry: dict[str, Any] = dict(base_entry) if isinstance(base_entry, dict) else {}

    # Terapkan override persona (jika bukan persona default)
    if persona and persona != DEFAULT_PERSONA:
        personas = cfg.get("personas")
        if isinstance(personas, dict):
            persona_map = personas.get(persona)
            if isinstance(persona_map, dict):
                override = persona_map.get(activity)
                if isinstance(override, dict):
                    entry.update(override)

    status = str(entry.get("status", activity.title()))
    mood = str(entry.get("mood", "Santai"))

    # Cek kata kunci prompt (khususnya saat thinking) untuk mood yang lebih ekspresif
    chosen_lines: list[str] | None = None
    if (
        persona == DEFAULT_PERSONA
        and user_input
        and isinstance(entry.get("keyword_moods"), list)
    ):
        lower_prompt = user_input.lower()
        for rule in entry["keyword_moods"]:
            keywords = rule.get("keywords", [])
            if any(str(kw).lower() in lower_prompt for kw in keywords):
                if rule.get("mood"):
                    mood = str(rule["mood"])
                if rule.get("lines"):
                    chosen_lines = [str(x) for x in rule["lines"]]
                break

    if chosen_lines is None:
        if target and entry.get("lines_with_target"):
            chosen_lines = [str(x) for x in entry["lines_with_target"]]
        elif entry.get("lines"):
            chosen_lines = [str(x) for x in entry["lines"]]
        else:
            chosen_lines = [""]

    template = random.choice(chosen_lines) if chosen_lines else ""
    try:
        dialogue = template.format(target=target) if target else template
    except Exception:
        dialogue = template

    return {
        "activity": activity,
        "status": status,
        "mood": mood,
        "dialogue": dialogue,
    }
