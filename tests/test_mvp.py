#!/usr/bin/env python3
"""Smoke & unit tests untuk hook_reporter.py, dialogue_engine.py, companion.py, dan convert.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import companion  # noqa: E402
import convert  # noqa: E402
import dialogue_engine  # noqa: E402


def test_hooks() -> None:
    with tempfile.TemporaryDirectory() as td:
        sf = Path(td) / "state.json"
        cases = [
            (
                "SessionStart",
                {"hookEventName": "SessionStart"},
                "idle",
                "☕ Standby",
                "Santai",
                "{}",
            ),
            (
                "PreInvocation",
                {"hookEventName": "PreInvocation", "lastUserInput": "tolong fix bug auth.ts"},
                "thinking",
                "💭 Thinking",
                "Serius",
                "{}",
            ),
            (
                "PreToolUse_read",
                {
                    "hookEventName": "PreToolUse",
                    "toolCall": {"name": "read_file", "args": {"Path": "C:/app/src/auth.ts"}},
                },
                "coding",
                "🔍 Reading code",
                "Fokus",
                "",
            ),
            (
                "PreToolUse_edit",
                {
                    "hookEventName": "PreToolUse",
                    "toolCall": {"name": "edit_file", "args": {"Path": "C:/app/src/auth.ts"}},
                },
                "coding",
                "✏️ Editing code",
                "Fokus",
                "",
            ),
            (
                "PostToolUse_ok",
                {
                    "hookEventName": "PostToolUse",
                    "toolCall": {"name": "edit_file", "args": {"Path": "C:/app/src/auth.ts"}},
                },
                "coding",
                "✏️ Editing code",
                "Fokus",
                "{}",
            ),
            (
                "PostToolUse_err",
                {
                    "hookEventName": "PostToolUse",
                    "toolCall": {"name": "run_command", "args": {"CommandLine": "npm test"}},
                    "error": "exit 1",
                },
                "error",
                "💥 Error",
                "Panik",
                "{}",
            ),
            (
                "Stop",
                {"hookEventName": "Stop", "terminationReason": "NO_TOOL_CALL"},
                "done",
                "✅ Done",
                "Puas",
                json.dumps({"decision": "stop"}),
            ),
        ]
        for label, payload, exp_state, exp_status, exp_mood, exp_out in cases:
            res = subprocess.run(
                [sys.executable, str(BASE_DIR / "hook_reporter.py"), "--state-file", str(sf)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                check=True,
            )
            st = json.loads(sf.read_text(encoding="utf-8"))
            assert st["state"] == exp_state, f"{label}: expected {exp_state}, got {st}"
            assert st["status"] == exp_status, f"{label}: expected {exp_status}, got {st}"
            assert st["mood"] == exp_mood, f"{label}: expected {exp_mood}, got {st}"
            assert st.get("dialogue"), f"{label}: missing dialogue in {st}"
            if label == "PreToolUse_read":
                assert "auth.ts" in st["dialogue"], f"expected auth.ts in {st['dialogue']}"
            assert res.stdout.strip() == exp_out, f"{label}: stdout got {res.stdout!r}"
            print(
                f"[PASS] {label:16s} | {st['status']} | {st['mood']} | \"{st['dialogue']}\""
            )


def test_hook_env_isolation() -> None:
    with tempfile.TemporaryDirectory() as td:
        sf = Path(td) / "state_session123.json"
        env = os.environ.copy()
        env["AGY_COMPANION_STATE_FILE"] = str(sf)
        subprocess.run(
            [sys.executable, str(BASE_DIR / "hook_reporter.py")],
            input=json.dumps({"hookEventName": "SessionStart"}),
            text=True,
            capture_output=True,
            check=True,
            env=env,
        )
        assert sf.exists(), "Expected hook_reporter to write to AGY_COMPANION_STATE_FILE"
        st = json.loads(sf.read_text(encoding="utf-8"))
        assert st["state"] == "idle"
        print("[PASS] hook_reporter AGY_COMPANION_STATE_FILE isolation")


def test_natural_sort() -> None:
    names = ["idle-10.png", "idle-2.png", "idle.png", "idle-3.png", "idle-4.png"]
    ordered = [p.name for p in sorted((Path(n) for n in names), key=convert.natural_sort_key)]
    assert ordered == ["idle.png", "idle-2.png", "idle-3.png", "idle-4.png", "idle-10.png"], ordered

    numbered = ["10_end.png", "02_blink.png", "01_open.png"]
    ordered_num = [p.name for p in sorted((Path(n) for n in numbered), key=convert.natural_sort_key)]
    assert ordered_num == ["01_open.png", "02_blink.png", "10_end.png"], ordered_num
    print("[PASS] convert.natural_sort_key")


def test_companion_bom_and_wrap() -> None:
    with tempfile.TemporaryDirectory() as td:
        bom_file = Path(td) / "state_bom.json"
        bom_file.write_text(
            json.dumps({"state": "idle", "updatedAt": 123.0}),
            encoding="utf-8-sig",
        )
        data = companion.read_state_file(bom_file)
        assert data is not None and data["state"] == "idle", f"Failed reading UTF-8 BOM: {data}"

    assert companion.safe_float(None, 0.0) == 0.0
    assert companion.safe_float("invalid", 1.5) == 1.5
    assert companion.safe_float("42.5", 0.0) == 42.5

    wrapped = companion.wrap_display('"☕ Lagi cek auth.ts nih, bentar ya!"', max_cols=16, max_lines=3)
    assert len(wrapped) <= 3
    for line in wrapped:
        assert companion.display_width(line) <= 16, f"Line exceeded 16 cols: {line!r}"
    print("[PASS] companion UTF-8 BOM, safe_float, wrap_display")


def test_dialogue_cache_reload() -> None:
    with tempfile.TemporaryDirectory() as td:
        cfg_path = Path(td) / "dialogue.json"
        cfg_path.write_text(
            json.dumps({"activities": {"idle": {"status": "A", "mood": "M1", "lines": ["Halo 1"]}}}),
            encoding="utf-8",
        )
        p1 = dialogue_engine.pick_presentation("idle", config_path=cfg_path)
        assert p1["status"] == "A" and p1["dialogue"] == "Halo 1"

        # Ubah file dan pastikan mtime berubah agar cache reload
        time.sleep(0.02)
        cfg_path.write_text(
            json.dumps({"activities": {"idle": {"status": "B", "mood": "M2", "lines": ["Halo 2"]}}}),
            encoding="utf-8-sig",
        )
        p2 = dialogue_engine.pick_presentation("idle", config_path=cfg_path)
        assert p2["status"] == "B" and p2["dialogue"] == "Halo 2"
        print("[PASS] dialogue_engine cache & live-reload")


def test_fase2_features() -> None:
    # 1. Granular animation resolution & fallback
    dummy_idle = companion.Animation(state="idle", frames=[companion.Frame(["i"], 100)])
    dummy_coding = companion.Animation(state="coding", frames=[companion.Frame(["c"], 100)])
    dummy_reading = companion.Animation(state="reading", frames=[companion.Frame(["r"], 100)])
    anims = {"idle": dummy_idle, "coding": dummy_coding, "reading": dummy_reading}

    assert companion.resolve_animation(anims, "coding", "reading").state == "reading"
    assert companion.resolve_animation(anims, "coding", "editing").state == "coding"
    assert companion.resolve_animation(anims, "sleepy", "sleepy").state == "idle"

    # 2. SessionStats tracking
    stats = companion.SessionStats(started_at=time.monotonic() - 125)
    stats.record_event("coding", "reading", "auth.ts", "PreToolUse")
    stats.record_event("coding", "editing", "auth.ts", "PreToolUse")
    stats.record_event("coding", "running", "pytest", "PreToolUse")
    stats.record_event("done", "done", "", "Stop")
    stats.record_event("done", "done", "", "Stop")
    assert stats.tool_calls == 3
    assert stats.files_touched == {"auth.ts"}
    assert stats.done_streak == 2
    compact = stats.format_compact()
    assert "🛠 3" in compact and "📄 1" in compact and "🔥 2" in compact, compact

    # 3. Character pack discovery + frames fallback + live-reload fingerprint
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        default_frames = root / "default_frames"
        default_frames.mkdir()
        for st in companion.CORE_STATES:
            (default_frames / f"{st}.json").write_text(
                json.dumps({"state": st, "frames": [{"duration_ms": 200, "lines": [st]}]}),
                encoding="utf-8",
            )

        chars_dir = root / "characters"
        neko_dir = chars_dir / "neko"
        (neko_dir / "frames").mkdir(parents=True)
        (neko_dir / "character.json").write_text(
            json.dumps({"name": "Neko Dev", "theme": "amber", "sleepy_after_sec": 60}),
            encoding="utf-8",
        )
        (neko_dir / "frames" / "reading.json").write_text(
            json.dumps({"state": "reading", "frames": [{"duration_ms": 200, "lines": ["neko-read"]}]}),
            encoding="utf-8",
        )

        packs = companion.discover_characters(
            default_frames_dir=default_frames,
            characters_dir=chars_dir,
        )
        assert len(packs) == 2
        neko = packs[1]
        assert neko.id == "neko" and neko.name == "Neko Dev" and neko.default_theme == "amber"
        assert neko.sleepy_after_sec == 60.0

        loaded = companion.load_animations(neko.frames_dir, neko.fallback_frames_dir)
        assert loaded["reading"].frames[0].lines == ["neko-read"]
        assert loaded["idle"].frames[0].lines == ["idle"]

        fp1 = companion.frames_fingerprint(neko.frames_dir, neko.fallback_frames_dir)
        time.sleep(0.02)
        (neko_dir / "frames" / "reading.json").write_text(
            json.dumps({"state": "reading", "frames": [{"duration_ms": 200, "lines": ["neko-read-v2"]}]}),
            encoding="utf-8",
        )
        fp2 = companion.frames_fingerprint(neko.frames_dir, neko.fallback_frames_dir)
        assert fp1 != fp2, "Expected fingerprint change after frame edit"

    # 4. Sleepy dialogue entry + themed info block
    sleepy_view = companion.make_view("sleepy")
    assert sleepy_view.status == "💤 Sleepy" and sleepy_view.dialogue
    rows = companion.build_info_block(
        sleepy_view,
        block_width=45,
        demo_mode=False,
        theme=companion.THEMES["amber"],
        stats=stats,
        show_stats=True,
        show_log=True,
        char_label="Neko Dev",
    )
    rendered = "\n".join(r[0] for r in rows)
    assert "Neko Dev" in rendered and "\x1b[38;5;" in rendered
    print("[PASS] Fase 2: granular animations, stats, character packs, themes, sleepy, live-reload")


def test_fase3_features() -> None:
    # 1. Persona list & overrides
    personas = dialogue_engine.list_personas()
    assert personas[:4] == ["santai", "formal", "tsundere", "zen"], personas

    p_formal = dialogue_engine.pick_presentation("reading", target="auth.ts", persona="formal")
    assert p_formal["mood"] == "Teliti" and "auth.ts" in p_formal["dialogue"], p_formal

    p_tsun = dialogue_engine.pick_presentation("done", persona="tsundere")
    assert p_tsun["mood"] == "Bangga" and p_tsun["dialogue"], p_tsun

    # Fallback ke base activity saat persona tidak mendefinisikan activity tsb (mis. coding)
    p_fallback = dialogue_engine.pick_presentation("coding", target="tool_x", persona="zen")
    assert p_fallback["status"] == "🛠️ Working" and "tool_x" in p_fallback["dialogue"], p_fallback

    # 2. TerminalInput context manager aman dipakai di non-TTY / Windows
    with companion.TerminalInput() as ti:
        assert ti.poll_key() is None or isinstance(ti.poll_key(), str)

    # 3. Packaging & cross-platform launcher tersedia
    pyproject = BASE_DIR / "pyproject.toml"
    assert pyproject.exists()
    toml_text = pyproject.read_text(encoding="utf-8")
    assert 'agy-companion = "companion:main"' in toml_text
    assert (BASE_DIR / "scripts" / "launch-agy-live.sh").exists()
    print("[PASS] Fase 3: personas, TerminalInput, pyproject.toml, launch-agy-live.sh")


def test_frames() -> None:
    for state in ("idle", "thinking", "coding", "error", "done"):
        path = BASE_DIR / "assets" / "frames" / f"{state}.json"
        assert path.exists(), f"Missing {path}"
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        assert len(data["frames"]) >= 2, f"{state} needs >=2 frames"
        print(f"[PASS] frames/{state}.json ({len(data['frames'])} frames)")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    test_hooks()
    test_hook_env_isolation()
    test_natural_sort()
    test_companion_bom_and_wrap()
    test_dialogue_cache_reload()
    test_fase2_features()
    test_fase3_features()
    test_frames()
    print("\nAll Fase 1, 2 & 3 tests passed!")
