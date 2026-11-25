#!/usr/bin/env python3
"""Antigravity CLI Companion TUI (Pane Kiri) - Braille + Themes + Character Packs + Stats.

Menggunakan 100% Python standard library agar ringan, cepat, dan siap jalan
di Windows Terminal / PowerShell tanpa instalasi library tambahan.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import sys
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dialogue_engine import (
    DEFAULT_DIALOGUE_PATH,
    DEFAULT_PERSONA,
    list_personas,
    pick_presentation,
)

if os.name == "nt":
    import msvcrt
else:
    import select
    import termios
    import tty

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE_ENV = "AGY_COMPANION_STATE_FILE"
DEFAULT_STATE_PATH = Path.home() / ".agy-companion" / "state.json"
DEFAULT_FRAMES_DIR = BASE_DIR / "assets" / "frames"
CHARACTERS_DIR = BASE_DIR / "characters"

CORE_STATES = ("idle", "thinking", "coding", "error", "done")
GRANULAR_STATES = ("reading", "editing", "running", "searching", "sleepy")
VALID_STATES = CORE_STATES + GRANULAR_STATES

# Fallback animasi untuk state granular jika file JSON khususnya belum dibuat
STATE_FALLBACKS = {
    "reading": "coding",
    "editing": "coding",
    "running": "coding",
    "searching": "coding",
    "sleepy": "idle",
}

# Setelah selesai atau error, otomatis kembali ke idle setelah durasi ini (detik)
DEFAULT_COOLDOWN_SEC = {
    "done": 4.5,
    "error": 6.0,
}

DEFAULT_SLEEPY_AFTER_SEC = 300.0  # 5 menit idle -> sleepy

# Contoh skenario untuk mode --demo / --cycle
DEMO_CODING_SCENARIOS = [
    ("reading", "auth.ts"),
    ("editing", "companion.py"),
    ("running", "pytest -q"),
    ("searching", "hooks.json"),
]

# ANSI Escape Codes
ALT_SCREEN_ON = "\x1b[?1049h"
ALT_SCREEN_OFF = "\x1b[?1049l"
CURSOR_HIDE = "\x1b[?25l"
CURSOR_SHOW = "\x1b[?25h"
CLEAR_HOME = "\x1b[2J\x1b[H"
MOVE_HOME = "\x1b[H"
CLEAR_EOL = "\x1b[K"
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
ITALIC = "\x1b[3m"


@dataclass(frozen=True)
class Theme:
    name: str
    art: str
    label: str
    status: str
    mood: str
    dialogue: str
    footer: str


THEMES: dict[str, Theme] = {
    "mono": Theme(
        name="mono",
        art="",
        label=DIM,
        status=BOLD,
        mood="",
        dialogue=ITALIC,
        footer=DIM,
    ),
    "amber": Theme(
        name="amber",
        art="\x1b[38;5;214m",
        label="\x1b[38;5;172m",
        status=f"{BOLD}\x1b[38;5;220m",
        mood="\x1b[38;5;215m",
        dialogue=f"{ITALIC}\x1b[38;5;222m",
        footer="\x1b[38;5;136m",
    ),
    "green": Theme(
        name="green",
        art="\x1b[38;5;77m",
        label="\x1b[38;5;71m",
        status=f"{BOLD}\x1b[38;5;120m",
        mood="\x1b[38;5;114m",
        dialogue=f"{ITALIC}\x1b[38;5;157m",
        footer="\x1b[38;5;65m",
    ),
    "cyan": Theme(
        name="cyan",
        art="\x1b[38;5;81m",
        label="\x1b[38;5;67m",
        status=f"{BOLD}\x1b[38;5;123m",
        mood="\x1b[38;5;117m",
        dialogue=f"{ITALIC}\x1b[38;5;159m",
        footer="\x1b[38;5;73m",
    ),
    "pastel": Theme(
        name="pastel",
        art="\x1b[38;5;183m",
        label="\x1b[38;5;139m",
        status=f"{BOLD}\x1b[38;5;218m",
        mood="\x1b[38;5;158m",
        dialogue=f"{ITALIC}\x1b[38;5;225m",
        footer="\x1b[38;5;146m",
    ),
}
THEME_ORDER = tuple(THEMES.keys())


@dataclass
class Frame:
    lines: list[str]
    duration_ms: int


@dataclass
class Animation:
    state: str
    frames: list[Frame]
    loop: bool = True
    cooldown_sec: float | None = None


@dataclass
class CompanionView:
    state: str
    status: str
    mood: str
    dialogue: str
    activity: str = ""
    target: str = ""


@dataclass
class CharacterPack:
    id: str
    name: str
    frames_dir: Path
    fallback_frames_dir: Path
    dialogue_path: Path
    default_theme: str = "mono"
    sleepy_after_sec: float | None = None


@dataclass
class SessionStats:
    started_at: float = field(default_factory=time.monotonic)
    tool_calls: int = 0
    files_touched: set[str] = field(default_factory=set)
    done_streak: int = 0
    errors: int = 0
    recent: deque[str] = field(default_factory=lambda: deque(maxlen=4))

    def record_event(
        self,
        state: str,
        activity: str,
        target: str = "",
        event: str = "",
    ) -> None:
        act = activity or state
        if event == "PreToolUse" or (not event and state == "coding"):
            self.tool_calls += 1
            if act in ("reading", "editing") and target:
                self.files_touched.add(target)
        elif state == "done":
            self.done_streak += 1
        elif state == "error":
            self.done_streak = 0
            self.errors += 1

        # Catat ke mini activity feed (abaikan idle/sleepy supaya tidak noisy)
        if state in ("idle", "sleepy"):
            return
        icon = {
            "thinking": "💭",
            "reading": "🔍",
            "editing": "✏️",
            "running": "⚡",
            "searching": "🔎",
            "coding": "🛠️",
            "error": "💥",
            "done": "✅",
        }.get(act, "•")
        label = f"{icon} {target}" if target else f"{icon} {act}"
        if not self.recent or self.recent[-1] != label:
            self.recent.append(label)

    def format_compact(self, now: float | None = None) -> str:
        elapsed = max(0, int((now if now is not None else time.monotonic()) - self.started_at))
        mins, secs = divmod(elapsed, 60)
        hrs, mins = divmod(mins, 60)
        dur = f"{hrs}h{mins:02d}m" if hrs else (f"{mins}m" if mins else f"{secs}s")
        parts = [f"⏱ {dur}", f"🛠 {self.tool_calls}"]
        if self.files_touched:
            parts.append(f"📄 {len(self.files_touched)}")
        if self.done_streak >= 2:
            parts.append(f"🔥 {self.done_streak}")
        return " · ".join(parts)


def get_default_state_path() -> Path:
    env_val = os.environ.get(STATE_FILE_ENV, "").strip()
    return Path(env_val) if env_val else DEFAULT_STATE_PATH


def enable_windows_vt_mode() -> None:
    """Aktifkan dukungan ANSI escape sequence di console Windows."""
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(
                stdout_handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            )
    except Exception:
        pass


def display_width(text: str) -> int:
    """Perkiraan lebar kolom terminal (menangani emoji lebar 2 & variation selector)."""
    width = 0
    for ch in text:
        cp = ord(ch)
        if cp in (0xFE0E, 0xFE0F, 0x200D):
            continue
        if unicodedata.combining(ch):
            continue
        eaw = unicodedata.east_asian_width(ch)
        if eaw in ("W", "F") or (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF):
            width += 2
        else:
            width += 1
    return width


def truncate_display(text: str, max_cols: int) -> str:
    """Potong teks dengan aman agar tidak melampaui lebar kolom terminal."""
    if max_cols <= 0:
        return ""
    if display_width(text) <= max_cols:
        return text
    out: list[str] = []
    cur = 0
    limit = max(1, max_cols - 1)
    for ch in text:
        w = display_width(ch)
        if cur + w > limit:
            break
        out.append(ch)
        cur += w
    return "".join(out) + "…"


def wrap_display(text: str, max_cols: int, max_lines: int = 3) -> list[str]:
    """Word-wrap teks berdasarkan lebar kolom terminal (display_width)."""
    if max_cols <= 0 or not text:
        return []
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    cur = ""
    cur_w = 0

    for word in words:
        w_len = display_width(word)
        if not cur:
            if w_len <= max_cols:
                cur = word
                cur_w = w_len
            else:
                chunk = ""
                chunk_w = 0
                for ch in word:
                    cw = display_width(ch)
                    if chunk and chunk_w + cw > max_cols:
                        lines.append(chunk)
                        chunk = ch
                        chunk_w = cw
                    else:
                        chunk += ch
                        chunk_w += cw
                cur = chunk
                cur_w = chunk_w
        elif cur_w + 1 + w_len <= max_cols:
            cur = f"{cur} {word}"
            cur_w += 1 + w_len
        else:
            lines.append(cur)
            if w_len <= max_cols:
                cur = word
                cur_w = w_len
            else:
                chunk = ""
                chunk_w = 0
                for ch in word:
                    cw = display_width(ch)
                    if chunk and chunk_w + cw > max_cols:
                        lines.append(chunk)
                        chunk = ch
                        chunk_w = cw
                    else:
                        chunk += ch
                        chunk_w += cw
                cur = chunk
                cur_w = chunk_w

    if cur:
        lines.append(cur)

    return lines[:max_lines]


def discover_characters(
    default_frames_dir: Path = DEFAULT_FRAMES_DIR,
    default_dialogue_path: Path = DEFAULT_DIALOGUE_PATH,
    characters_dir: Path = CHARACTERS_DIR,
) -> list[CharacterPack]:
    """Temukan character pack default + semua pack valid di characters/<nama>/."""
    packs: list[CharacterPack] = [
        CharacterPack(
            id="default",
            name="Default",
            frames_dir=default_frames_dir,
            fallback_frames_dir=default_frames_dir,
            dialogue_path=default_dialogue_path,
            default_theme="mono",
        )
    ]

    if not characters_dir.exists() or not characters_dir.is_dir():
        return packs

    for entry in sorted(characters_dir.iterdir(), key=lambda p: p.name.lower()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        meta_file = entry / "character.json"
        frames_dir = entry / "frames"
        dialogue_file = entry / "dialogue.json"
        if not (meta_file.exists() or frames_dir.exists() or dialogue_file.exists()):
            continue

        meta: dict[str, Any] = {}
        if meta_file.exists():
            try:
                parsed = json.loads(meta_file.read_text(encoding="utf-8-sig"))
                if isinstance(parsed, dict):
                    meta = parsed
            except (OSError, json.JSONDecodeError):
                pass

        theme_name = str(meta.get("theme", "mono")).lower()
        if theme_name not in THEMES:
            theme_name = "mono"
        sleepy_raw = meta.get("sleepy_after_sec")
        sleepy_sec = safe_float(sleepy_raw, -1.0) if sleepy_raw is not None else None
        if sleepy_sec is not None and sleepy_sec < 0:
            sleepy_sec = None

        packs.append(
            CharacterPack(
                id=entry.name,
                name=str(meta.get("name") or entry.name),
                frames_dir=frames_dir if frames_dir.exists() else default_frames_dir,
                fallback_frames_dir=default_frames_dir,
                dialogue_path=dialogue_file if dialogue_file.exists() else default_dialogue_path,
                default_theme=theme_name,
                sleepy_after_sec=sleepy_sec,
            )
        )

    return packs


def frames_fingerprint(frames_dir: Path, fallback_dir: Path | None = None) -> tuple[tuple[str, int], ...]:
    """Sidik jari mtime_ns file frame JSON untuk mendeteksi perubahan (live-reload)."""
    seen: dict[str, int] = {}
    dirs = [fallback_dir, frames_dir] if fallback_dir and fallback_dir != frames_dir else [frames_dir]
    for d in dirs:
        if not d or not d.exists():
            continue
        try:
            for p in d.glob("*.json"):
                try:
                    seen[p.name] = p.stat().st_mtime_ns
                except OSError:
                    pass
        except OSError:
            pass
    return tuple(sorted(seen.items()))


def load_animations(
    frames_dir: Path,
    fallback_frames_dir: Path | None = None,
) -> dict[str, Animation]:
    """Muat file JSON animasi Braille (5 core state wajib + state granular opsional)."""
    animations: dict[str, Animation] = {}
    for state in VALID_STATES:
        path = frames_dir / f"{state}.json"
        if not path.exists() and fallback_frames_dir and fallback_frames_dir != frames_dir:
            path = fallback_frames_dir / f"{state}.json"

        if not path.exists():
            if state in CORE_STATES:
                animations[state] = Animation(
                    state=state,
                    frames=[
                        Frame(
                            lines=[f"[ missing: {state}.json ]"],
                            duration_ms=1000,
                        )
                    ],
                    cooldown_sec=DEFAULT_COOLDOWN_SEC.get(state),
                )
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            if state in CORE_STATES:
                animations[state] = Animation(
                    state=state,
                    frames=[Frame(lines=[f"[ invalid: {state}.json ]"], duration_ms=1000)],
                    cooldown_sec=DEFAULT_COOLDOWN_SEC.get(state),
                )
            continue

        raw_frames = data.get("frames", [])
        frames = [
            Frame(
                lines=list(f.get("lines", [])),
                duration_ms=max(40, int(f.get("duration_ms", 400))),
            )
            for f in raw_frames
            if f.get("lines")
        ]
        if not frames:
            if state in CORE_STATES:
                frames = [Frame(lines=[f"[ empty: {state}.json ]"], duration_ms=1000)]
            else:
                continue

        cooldown_ms = data.get("cooldown_ms")
        cooldown_sec = (
            float(cooldown_ms) / 1000.0
            if cooldown_ms is not None
            else DEFAULT_COOLDOWN_SEC.get(state)
        )
        animations[state] = Animation(
            state=state,
            frames=frames,
            loop=bool(data.get("loop", True)),
            cooldown_sec=cooldown_sec,
        )
    return animations


def resolve_animation(
    animations: dict[str, Animation],
    state: str,
    activity: str = "",
) -> Animation:
    """Pilih animasi paling spesifik (mis. reading.json) dengan fallback ke state utama."""
    if activity and activity in animations:
        return animations[activity]
    if state in animations:
        return animations[state]
    fallback = STATE_FALLBACKS.get(activity or state)
    if fallback and fallback in animations:
        return animations[fallback]
    return animations["idle"]


def make_view(
    state: str,
    activity: str | None = None,
    target: str = "",
    user_input: str = "",
    dialogue_path: Path = DEFAULT_DIALOGUE_PATH,
    persona: str = DEFAULT_PERSONA,
) -> CompanionView:
    act = activity or state
    pres = pick_presentation(
        act,
        target=target,
        user_input=user_input,
        config_path=dialogue_path,
        persona=persona,
    )
    return CompanionView(
        state=state,
        status=pres["status"],
        mood=pres["mood"],
        dialogue=pres["dialogue"],
        activity=act,
        target=target,
    )


def read_state_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class TerminalInput:
    """Context manager input keyboard non-blocking lintas OS (Windows + POSIX)."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._old_attrs: Any = None

    def __enter__(self) -> "TerminalInput":
        if os.name != "nt" and sys.stdin.isatty():
            try:
                self._fd = sys.stdin.fileno()
                self._old_attrs = termios.tcgetattr(self._fd)
                tty.setcbreak(self._fd)
            except Exception:
                self._fd = None
                self._old_attrs = None
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if os.name != "nt" and self._fd is not None and self._old_attrs is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_attrs)
            except Exception:
                pass
            self._fd = None
            self._old_attrs = None

    def poll_key(self) -> str | None:
        if os.name == "nt":
            if msvcrt.kbhit():
                return msvcrt.getwch().lower()
            return None
        if self._fd is None:
            return None
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            if ready:
                ch = sys.stdin.read(1)
                return ch.lower() if ch else None
        except Exception:
            return None
        return None


def poll_key() -> str | None:
    """Wrapper kompatibilitas untuk membaca tombol keyboard non-blocking."""
    if os.name == "nt" and msvcrt.kbhit():
        return msvcrt.getwch().lower()
    return None


def build_info_block(
    view: CompanionView,
    block_width: int,
    demo_mode: bool,
    theme: Theme = THEMES["mono"],
    stats: SessionStats | None = None,
    show_stats: bool = True,
    show_log: bool = False,
    char_label: str = "",
) -> list[tuple[str, int]]:
    """Bangun baris [Status], [Mood], dialog, mini log, dan footer stats di bawah karakter."""
    inner_w = max(16, block_width)
    rows: list[tuple[str, int]] = [("", 0)]

    # Baris [Status] & [Mood] rata sejajar
    status_val = truncate_display(view.status, max(6, inner_w - 10))
    mood_val = truncate_display(view.mood, max(6, inner_w - 10))

    status_plain = f"[Status]  {status_val}"
    status_styled = f"{theme.label}[Status]{RESET}  {theme.status}{status_val}{RESET}"
    rows.append((status_styled, display_width(status_plain)))

    mood_plain = f"[Mood]    {mood_val}"
    mood_styled = f"{theme.label}[Mood]{RESET}    {theme.mood}{mood_val}{RESET}"
    rows.append((mood_styled, display_width(mood_plain)))

    # Dialog dengan word-wrap rapi berbasis display_width (maks 3 baris)
    if view.dialogue:
        quoted = f'"{view.dialogue}"'
        wrapped = wrap_display(quoted, max_cols=inner_w, max_lines=3)
        if wrapped:
            rows.append(("", 0))
            for idx, wline in enumerate(wrapped):
                if idx == 2 and len(wrapped) == 3 and not wline.endswith('"'):
                    wline = truncate_display(wline, inner_w - 1) + '"'
                rows.append((f"{theme.dialogue}{wline}{RESET}", display_width(wline)))

    # Mini activity log (opsional, toggle via tombol `l`)
    if show_log and stats and stats.recent:
        rows.append(("", 0))
        for item in list(stats.recent)[-3:]:
            clipped = truncate_display(item, inner_w)
            rows.append((f"{theme.footer}{clipped}{RESET}", display_width(clipped)))

    # Footer session stats (opsional, toggle via tombol `s`)
    if show_stats and stats is not None:
        rows.append(("", 0))
        footer_parts = [stats.format_compact()]
        if char_label:
            footer_parts.append(char_label)
        footer_text = truncate_display(" · ".join(footer_parts), inner_w)
        rows.append((f"{theme.footer}{footer_text}{RESET}", display_width(footer_text)))

    if demo_mode:
        rows.append(("", 0))
        hint = "[1-6]state [t]theme [m]persona [s]stats [l]log [q]quit"
        if display_width(hint) > inner_w:
            hint = "1-6 t:thm m:prs s:stat l:log q"
        if display_width(hint) > inner_w:
            hint = "1-6 t m s l q"
        rows.append((f"{theme.footer}{hint}{RESET}", display_width(hint)))

    return rows


def render_frame(
    frame: Frame,
    view: CompanionView,
    demo_mode: bool,
    last_size: tuple[int, int],
    theme: Theme = THEMES["mono"],
    stats: SessionStats | None = None,
    show_stats: bool = False,
    show_log: bool = False,
    char_label: str = "",
) -> tuple[int, int]:
    """Render 1 frame Braille + panel Status/Mood/Dialog rata tengah tanpa overflow."""
    term = shutil.get_terminal_size(fallback=(40, 24))
    cols, rows = max(16, term.columns), max(8, term.lines)
    resized = (cols, rows) != last_size

    art_width = max((len(line) for line in frame.lines), default=28)
    block_width = min(cols - 2, max(art_width, 28))
    info_rows = build_info_block(
        view,
        block_width=block_width,
        demo_mode=demo_mode,
        theme=theme,
        stats=stats,
        show_stats=show_stats,
        show_log=show_log,
        char_label=char_label,
    )

    # Batasi baris artwork agar tidak pernah scroll/memotong kepala
    max_art_rows = max(1, rows - len(info_rows))
    visible_art = frame.lines[:max_art_rows]

    total_height = len(visible_art) + len(info_rows)
    top_pad = max(0, (rows - total_height) // 2)

    art_left_pad = max(0, (cols - art_width) // 2)
    art_pad_str = " " * art_left_pad

    info_left_pad = max(0, (cols - block_width) // 2)
    info_pad_str = " " * info_left_pad

    art_prefix = theme.art
    art_suffix = RESET if art_prefix else ""

    screen_lines: list[str] = []

    for _ in range(top_pad):
        screen_lines.append(CLEAR_EOL)

    for line in visible_art:
        if art_width > cols:
            start = (art_width - cols) // 2
            visible = line[start : start + cols]
            screen_lines.append(f"{art_prefix}{visible}{art_suffix}{CLEAR_EOL}")
        else:
            screen_lines.append(f"{art_pad_str}{art_prefix}{line}{art_suffix}{CLEAR_EOL}")

    for styled, plain_w in info_rows:
        if plain_w == 0:
            screen_lines.append(CLEAR_EOL)
        else:
            screen_lines.append(f"{info_pad_str}{styled}{CLEAR_EOL}")

    while len(screen_lines) < rows:
        screen_lines.append(CLEAR_EOL)
    screen_lines = screen_lines[:rows]

    prefix = CLEAR_HOME if resized else MOVE_HOME
    sys.stdout.write(prefix + "\n".join(screen_lines))
    sys.stdout.flush()
    return (cols, rows)


def run_companion(
    frames_dir: Path,
    state_file: Path,
    exit_file: Path | None,
    demo_mode: bool,
    auto_cycle: bool,
    theme_name: str | None = None,
    character_id: str | None = None,
    persona_name: str = DEFAULT_PERSONA,
    sleepy_after_sec: float = DEFAULT_SLEEPY_AFTER_SEC,
    show_stats: bool = True,
    show_log: bool = False,
) -> int:
    enable_windows_vt_mode()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    packs = discover_characters(default_frames_dir=frames_dir)
    pack_idx = 0
    if character_id:
        for i, p in enumerate(packs):
            if p.id.lower() == character_id.lower():
                pack_idx = i
                break

    active_pack = packs[pack_idx]
    active_theme_name = (
        theme_name if theme_name in THEMES else active_pack.default_theme
    )
    theme_idx = THEME_ORDER.index(active_theme_name)
    theme = THEMES[active_theme_name]

    personas = list_personas(active_pack.dialogue_path)
    persona_idx = 0
    if persona_name:
        for i, pname in enumerate(personas):
            if pname.lower() == persona_name.lower():
                persona_idx = i
                break
    active_persona = personas[persona_idx]

    animations = load_animations(active_pack.frames_dir, active_pack.fallback_frames_dir)
    last_frames_fp = frames_fingerprint(active_pack.frames_dir, active_pack.fallback_frames_dir)
    next_reload_check_at = time.monotonic() + 1.0

    stats = SessionStats()
    view = make_view(
        "idle",
        dialogue_path=active_pack.dialogue_path,
        persona=active_persona,
    )
    last_state_ts = 0.0
    last_state_mtime_ns = -1
    state_entered_at = time.monotonic()
    last_stats_tick = int(state_entered_at)

    frame_idx = 0
    next_frame_at = 0.0
    last_size = (0, 0)
    needs_render = True

    coding_demo_idx = 0
    cycle_sequence = [
        ("idle", "idle", "", ""),
        ("thinking", "thinking", "", "tolong fix bug di auth.ts"),
        ("coding", "reading", "auth.ts", ""),
        ("coding", "editing", "auth.ts", ""),
        ("coding", "running", "npm test", ""),
        ("error", "error", "npm test", ""),
        ("done", "done", "", ""),
        ("sleepy", "sleepy", "", ""),
    ]
    cycle_idx = 0
    next_cycle_at = time.monotonic() + 3.0

    if exit_file and exit_file.exists():
        try:
            exit_file.unlink()
        except OSError:
            pass

    sys.stdout.write(ALT_SCREEN_ON + CURSOR_HIDE + CLEAR_HOME)
    sys.stdout.flush()

    try:
        with TerminalInput() as term_in:
            while True:
                now = time.monotonic()

                if exit_file and exit_file.exists():
                    break

                # Live-reload frame JSON jika ada perubahan di disk (cek tiap 1 detik)
                if now >= next_reload_check_at:
                    next_reload_check_at = now + 1.0
                    cur_fp = frames_fingerprint(
                        active_pack.frames_dir, active_pack.fallback_frames_dir
                    )
                    if cur_fp != last_frames_fp:
                        last_frames_fp = cur_fp
                        animations = load_animations(
                            active_pack.frames_dir, active_pack.fallback_frames_dir
                        )
                        frame_idx = 0
                        next_frame_at = now
                        needs_render = True

                key = term_in.poll_key()
                if key == "q" or key == "\x03":
                    break
                if key == "t":
                    theme_idx = (theme_idx + 1) % len(THEME_ORDER)
                    theme = THEMES[THEME_ORDER[theme_idx]]
                    needs_render = True
                elif key == "m":
                    personas = list_personas(active_pack.dialogue_path)
                    if len(personas) > 1:
                        persona_idx = (persona_idx + 1) % len(personas)
                        active_persona = personas[persona_idx]
                        view = make_view(
                            view.state,
                            activity=view.activity or view.state,
                            target=view.target,
                            dialogue_path=active_pack.dialogue_path,
                            persona=active_persona,
                        )
                        needs_render = True
                elif key == "s":
                    show_stats = not show_stats
                    needs_render = True
                elif key == "l":
                    show_log = not show_log
                    needs_render = True
                elif key == "c" and len(packs) > 1:
                    pack_idx = (pack_idx + 1) % len(packs)
                    active_pack = packs[pack_idx]
                    personas = list_personas(active_pack.dialogue_path)
                    if active_persona not in personas:
                        persona_idx = 0
                        active_persona = personas[0]
                    animations = load_animations(
                        active_pack.frames_dir, active_pack.fallback_frames_dir
                    )
                    last_frames_fp = frames_fingerprint(
                        active_pack.frames_dir, active_pack.fallback_frames_dir
                    )
                    view = make_view(
                        view.state,
                        activity=view.activity or view.state,
                        target=view.target,
                        dialogue_path=active_pack.dialogue_path,
                        persona=active_persona,
                    )
                    frame_idx = 0
                    next_frame_at = now
                    needs_render = True
                elif demo_mode and key in {"1", "2", "3", "4", "5", "6"}:
                    if key == "6":
                        view = make_view(
                            "sleepy",
                            dialogue_path=active_pack.dialogue_path,
                            persona=active_persona,
                        )
                    else:
                        chosen = CORE_STATES[int(key) - 1]
                        if chosen == "coding":
                            act, tgt = DEMO_CODING_SCENARIOS[
                                coding_demo_idx % len(DEMO_CODING_SCENARIOS)
                            ]
                            coding_demo_idx += 1
                            view = make_view(
                                "coding",
                                activity=act,
                                target=tgt,
                                dialogue_path=active_pack.dialogue_path,
                                persona=active_persona,
                            )
                            stats.record_event("coding", act, tgt)
                        elif chosen == "thinking":
                            view = make_view(
                                "thinking",
                                user_input="tolong fix bug auth.ts",
                                dialogue_path=active_pack.dialogue_path,
                                persona=active_persona,
                            )
                            stats.record_event("thinking", "thinking")
                        elif chosen == "error":
                            view = make_view(
                                "error",
                                target="npm test",
                                dialogue_path=active_pack.dialogue_path,
                                persona=active_persona,
                            )
                            stats.record_event("error", "error", "npm test")
                        else:
                            view = make_view(
                                chosen,
                                dialogue_path=active_pack.dialogue_path,
                                persona=active_persona,
                            )
                            stats.record_event(chosen, chosen)
                    state_entered_at = now
                    frame_idx = 0
                    next_frame_at = now
                    needs_render = True
                    auto_cycle = False

                if auto_cycle and now >= next_cycle_at:
                    cycle_idx = (cycle_idx + 1) % len(cycle_sequence)
                    st, act, tgt, prompt = cycle_sequence[cycle_idx]
                    view = make_view(
                        st,
                        activity=act,
                        target=tgt,
                        user_input=prompt,
                        dialogue_path=active_pack.dialogue_path,
                        persona=active_persona,
                    )
                    stats.record_event(st, act, tgt)
                    state_entered_at = now
                    frame_idx = 0
                    next_frame_at = now
                    next_cycle_at = now + 3.0
                    needs_render = True

                # Baca state terbaru dari Antigravity hook (mode normal)
                if not demo_mode:
                    data: dict[str, Any] | None = None
                    try:
                        cur_mtime_ns = state_file.stat().st_mtime_ns
                    except OSError:
                        cur_mtime_ns = -1

                    if cur_mtime_ns != -1 and cur_mtime_ns != last_state_mtime_ns:
                        data = read_state_file(state_file)
                        if data is not None:
                            last_state_mtime_ns = cur_mtime_ns

                    if data:
                        incoming_state = str(data.get("state", "idle"))
                        incoming_activity = str(data.get("activity") or incoming_state)
                        incoming_target = str(data.get("detail") or "")
                        incoming_event = str(data.get("event") or "")
                        incoming_ts = safe_float(data.get("updatedAt"), 0.0)

                        if incoming_state in VALID_STATES and incoming_ts > last_state_ts:
                            last_state_ts = incoming_ts
                            use_local_dialogue = (
                                active_pack.dialogue_path != DEFAULT_DIALOGUE_PATH
                                or active_persona != DEFAULT_PERSONA
                            )
                            if (
                                not use_local_dialogue
                                and data.get("status")
                                and data.get("mood")
                                and data.get("dialogue")
                            ):
                                next_view = CompanionView(
                                    state=incoming_state,
                                    status=str(data["status"]),
                                    mood=str(data["mood"]),
                                    dialogue=str(data["dialogue"]),
                                    activity=incoming_activity,
                                    target=incoming_target,
                                )
                            else:
                                next_view = make_view(
                                    incoming_state,
                                    activity=incoming_activity,
                                    target=incoming_target,
                                    dialogue_path=active_pack.dialogue_path,
                                    persona=active_persona,
                                )

                            stats.record_event(
                                incoming_state,
                                incoming_activity,
                                incoming_target,
                                incoming_event,
                            )
                            prev_anim = resolve_animation(
                                animations, view.state, view.activity
                            )
                            next_anim = resolve_animation(
                                animations, next_view.state, next_view.activity
                            )
                            view = next_view
                            state_entered_at = now
                            if next_anim.state != prev_anim.state:
                                frame_idx = 0
                                next_frame_at = now
                            needs_render = True

                    # Auto-cooldown kembali ke idle setelah done / error
                    cur_anim = resolve_animation(animations, view.state, view.activity)
                    if (
                        cur_anim.cooldown_sec is not None
                        and (now - state_entered_at) >= cur_anim.cooldown_sec
                    ):
                        view = make_view(
                            "idle",
                            dialogue_path=active_pack.dialogue_path,
                            persona=active_persona,
                        )
                        state_entered_at = now
                        frame_idx = 0
                        next_frame_at = now
                        needs_render = True

                    # Auto-sleepy jika idle terlalu lama
                    effective_sleepy = (
                        active_pack.sleepy_after_sec
                        if active_pack.sleepy_after_sec is not None
                        else sleepy_after_sec
                    )
                    if (
                        effective_sleepy > 0
                        and view.state == "idle"
                        and (now - state_entered_at) >= effective_sleepy
                    ):
                        view = make_view(
                            "sleepy",
                            dialogue_path=active_pack.dialogue_path,
                            persona=active_persona,
                        )
                        state_entered_at = now
                        frame_idx = 0
                        next_frame_at = now
                        needs_render = True

                # Refresh timer stats footer tiap 15 detik agar durasi sesi tetap akurat
                if show_stats and int(now) - last_stats_tick >= 15:
                    last_stats_tick = int(now)
                    needs_render = True

                cur_size = shutil.get_terminal_size(fallback=(40, 24))
                if (cur_size.columns, cur_size.lines) != last_size:
                    needs_render = True

                anim = resolve_animation(animations, view.state, view.activity)
                if frame_idx >= len(anim.frames):
                    frame_idx = 0
                if now >= next_frame_at:
                    if not needs_render and len(anim.frames) > 1:
                        if frame_idx + 1 < len(anim.frames):
                            frame_idx += 1
                        elif anim.loop:
                            frame_idx = 0
                    frame = anim.frames[frame_idx]
                    next_frame_at = now + (frame.duration_ms / 1000.0)
                    needs_render = True

                if needs_render:
                    frame = anim.frames[frame_idx]
                    label_parts = []
                    if len(packs) > 1:
                        label_parts.append(active_pack.name)
                    if active_persona != DEFAULT_PERSONA:
                        label_parts.append(active_persona)
                    char_label = " · ".join(label_parts)
                    last_size = render_frame(
                        frame=frame,
                        view=view,
                        demo_mode=demo_mode,
                        last_size=last_size,
                        theme=theme,
                        stats=stats,
                        show_stats=show_stats,
                        show_log=show_log,
                        char_label=char_label,
                    )
                    needs_render = False

                time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(RESET + CURSOR_SHOW + ALT_SCREEN_OFF)
        sys.stdout.flush()
        if exit_file and exit_file.exists():
            try:
                exit_file.unlink()
            except OSError:
                pass

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Antigravity CLI Companion - Animasi Braille + Themes + Character Packs."
    )
    parser.add_argument(
        "--frames-dir",
        type=Path,
        default=DEFAULT_FRAMES_DIR,
        help=f"Folder berisi file JSON frame Braille (default: {DEFAULT_FRAMES_DIR}).",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=None,
        help=(
            f"File state.json yang ditulis hook (default: env {STATE_FILE_ENV} "
            f"atau {DEFAULT_STATE_PATH})."
        ),
    )
    parser.add_argument(
        "--exit-file",
        type=Path,
        default=None,
        help="Jika file ini muncul, companion akan keluar otomatis (dipakai launcher).",
    )
    parser.add_argument(
        "--theme",
        choices=THEME_ORDER,
        default=None,
        help=f"Tema warna ANSI ({', '.join(THEME_ORDER)}). Default mengikuti karakter.",
    )
    parser.add_argument(
        "--character",
        type=str,
        default=None,
        help="ID character pack di folder characters/<id>/ (default: default).",
    )
    parser.add_argument(
        "--persona",
        type=str,
        default=DEFAULT_PERSONA,
        help="Gaya bahasa dialog di dialogue.json (mis. santai, formal, tsundere, zen).",
    )
    parser.add_argument(
        "--sleepy-after",
        type=float,
        default=DEFAULT_SLEEPY_AFTER_SEC,
        help="Detik idle sebelum masuk mode sleepy (0 untuk menonaktifkan, default: 300).",
    )
    parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Sembunyikan footer statistik sesi di bagian bawah.",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Tampilkan mini log aktivitas terakhir sejak awal.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Mode preview interaktif: 1-6 state, t tema, m persona, c karakter, s stats, l log, q keluar.",
    )
    parser.add_argument(
        "--cycle",
        action="store_true",
        help="Putar otomatis semua state & aktivitas tiap 3 detik.",
    )
    args = parser.parse_args()
    state_file = args.state_file if args.state_file is not None else get_default_state_path()

    return run_companion(
        frames_dir=args.frames_dir,
        state_file=state_file,
        exit_file=args.exit_file,
        demo_mode=args.demo or args.cycle,
        auto_cycle=args.cycle,
        theme_name=args.theme,
        character_id=args.character,
        persona_name=args.persona,
        sleepy_after_sec=args.sleepy_after,
        show_stats=not args.no_stats,
        show_log=args.log,
    )


if __name__ == "__main__":
    raise SystemExit(main())
