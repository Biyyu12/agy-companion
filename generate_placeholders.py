#!/usr/bin/env python3
"""Generator placeholder animasi Monochrome Braille untuk 5 state MVP.

Dipakai untuk mengisi assets/frames/*.json agar MVP langsung bisa dites
sebelum sketsa PNG buatanmu dimasukkan ke assets/raw/<state>/.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRAMES_DIR = BASE_DIR / "assets" / "frames"
RAW_DIR = BASE_DIR / "assets" / "raw"

BRAILLE_BITS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


class DotCanvas:
    """Kanvas piksel biner sederhana untuk dirender menjadi karakter Unicode Braille."""

    def __init__(self, width_chars: int = 28, height_chars: int = 14) -> None:
        self.dot_w = width_chars * 2
        self.dot_h = height_chars * 4
        self.grid = [[False] * self.dot_w for _ in range(self.dot_h)]

    def set(self, x: int, y: int, val: bool = True) -> None:
        if 0 <= x < self.dot_w and 0 <= y < self.dot_h:
            self.grid[y][x] = val

    def circle(self, cx: float, cy: float, r: float, fill: bool = False, thickness: float = 1.6) -> None:
        for y in range(self.dot_h):
            for x in range(self.dot_w):
                d = math.hypot(x - cx, y - cy)
                if fill:
                    if d <= r:
                        self.set(x, y, True)
                else:
                    if abs(d - r) <= thickness / 2.0:
                        self.set(x, y, True)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, fill: bool = False, thickness: float = 1.7) -> None:
        for y in range(self.dot_h):
            for x in range(self.dot_w):
                nx = (x - cx) / rx
                ny = (y - cy) / ry
                d = math.hypot(nx, ny)
                if fill:
                    if d <= 1.0:
                        self.set(x, y, True)
                else:
                    # Perkiraan jarak pinggir elips
                    if abs(d - 1.0) <= thickness / max(rx, ry):
                        self.set(x, y, True)

    def line(self, x0: int, y0: int, x1: int, y1: int, thickness: int = 1) -> None:
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for i in range(steps + 1):
            t = i / steps
            x = int(round(x0 + (x1 - x0) * t))
            y = int(round(y0 + (y1 - y0) * t))
            for dy in range(-(thickness // 2), (thickness // 2) + 1):
                for dx in range(-(thickness // 2), (thickness // 2) + 1):
                    self.set(x + dx, y + dy, True)

    def arc(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        deg_start: float,
        deg_end: float,
        thickness: int = 1,
    ) -> None:
        steps = int(abs(deg_end - deg_start) * 2) + 1
        for i in range(steps + 1):
            deg = deg_start + (deg_end - deg_start) * (i / steps)
            rad = math.radians(deg)
            x = int(round(cx + math.cos(rad) * rx))
            y = int(round(cy + math.sin(rad) * ry))
            for dy in range(-(thickness // 2), (thickness // 2) + 1):
                for dx in range(-(thickness // 2), (thickness // 2) + 1):
                    self.set(x + dx, y + dy, True)

    def rect(self, x0: int, y0: int, x1: int, y1: int, fill: bool = False) -> None:
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if fill or x in (x0, x1) or y in (y0, y1):
                    self.set(x, y, True)

    def sparkle(self, cx: int, cy: int, size: int = 3) -> None:
        self.line(cx - size, cy, cx + size, cy, 1)
        self.line(cx, cy - size, cx, cy + size, 1)

    def to_braille_lines(self) -> list[str]:
        lines: list[str] = []
        for y in range(0, self.dot_h, 4):
            chars: list[str] = []
            for x in range(0, self.dot_w, 2):
                mask = 0
                for dy in range(4):
                    for dx in range(2):
                        if self.grid[y + dy][x + dx]:
                            mask |= BRAILLE_BITS[dy][dx]
                chars.append(chr(0x2800 + mask))
            lines.append("".join(chars))
        return lines


def draw_base_character(c: DotCanvas, ox: int = 0, oy: int = 0) -> None:
    """Gambar siluet kepala, rambut poni, dan bahu dasar yang konsisten."""
    cx = 28 + ox
    cy = 25 + oy

    # Kepala oval
    c.ellipse(cx, cy, 15, 16, fill=False, thickness=2.0)

    # Poni rambut sederhana di atas
    c.arc(cx, cy - 1, 15, 16, 195, 345, thickness=2)
    c.line(cx - 12, cy - 11, cx - 7, cy - 4, 2)
    c.line(cx - 4, cy - 14, cx - 1, cy - 5, 2)
    c.line(cx + 3, cy - 14, cx + 6, cy - 5, 2)
    c.line(cx + 11, cy - 11, cx + 13, cy - 4, 2)

    # Rambut samping
    c.line(cx - 15, cy - 2, cx - 17, cy + 12, 2)
    c.line(cx + 15, cy - 2, cx + 17, cy + 12, 2)

    # Leher & bahu
    c.line(cx - 4, cy + 16, cx - 4, cy + 20, 2)
    c.line(cx + 4, cy + 16, cx + 4, cy + 20, 2)
    c.arc(cx, cy + 31, 18, 12, 200, 340, thickness=2)


def make_idle_frames() -> list[dict]:
    frames = []

    # Frame 1: Mata terbuka santai
    c1 = DotCanvas()
    draw_base_character(c1, 0, 0)
    c1.circle(22, 26, 2.3, fill=True)
    c1.circle(34, 26, 2.3, fill=True)
    c1.arc(28, 32, 4, 2.5, 20, 160, 1)
    frames.append({"duration_ms": 2800, "lines": c1.to_braille_lines()})

    # Frame 2: Berkedip
    c2 = DotCanvas()
    draw_base_character(c2, 0, 0)
    c2.line(19, 26, 25, 26, 2)
    c2.line(31, 26, 37, 26, 2)
    c2.arc(28, 32, 4, 2.5, 20, 160, 1)
    frames.append({"duration_ms": 160, "lines": c2.to_braille_lines()})

    # Frame 3: Bernapas tipis (geser 1 dot ke bawah)
    c3 = DotCanvas()
    draw_base_character(c3, 0, 1)
    c3.circle(22, 27, 2.3, fill=True)
    c3.circle(34, 27, 2.3, fill=True)
    c3.arc(28, 33, 4, 2.5, 20, 160, 1)
    frames.append({"duration_ms": 1400, "lines": c3.to_braille_lines()})

    return frames


def make_thinking_frames() -> list[dict]:
    frames = []
    for idx in range(3):
        c = DotCanvas()
        draw_base_character(c, 0, 0)
        # Mata melirik ke atas kanan
        c.circle(23, 24, 2.0, fill=True)
        c.circle(35, 24, 2.0, fill=True)
        # Alis berpikir
        c.line(19, 20, 25, 21, 1)
        c.line(31, 21, 37, 19, 1)
        # Mulut datar kecil
        c.line(26, 33, 30, 33, 1)
        # Gelembung titik pikiran animasi di kanan atas
        if idx >= 0:
            c.circle(46, 15, 1.3, fill=True)
        if idx >= 1:
            c.circle(49, 10, 1.8, fill=True)
        if idx >= 2:
            c.circle(52, 5, 2.3, fill=True)
        frames.append({"duration_ms": 420, "lines": c.to_braille_lines()})
    return frames


def make_coding_frames() -> list[dict]:
    frames = []
    for idx in range(3):
        c = DotCanvas()
        draw_base_character(c, 0, 1)
        # Kacamata fokus
        c.rect(18, 23, 26, 29, fill=False)
        c.rect(30, 23, 38, 29, fill=False)
        c.line(26, 26, 30, 26, 1)
        # Pupil fokus (gerak kanan-kiri membaca kode)
        shift = (-1, 0, 1)[idx]
        c.circle(22 + shift, 26, 1.4, fill=True)
        c.circle(34 + shift, 26, 1.4, fill=True)
        # Mulut serius
        c.line(25, 34, 31, 34, 1)
        # Garis keyboard + tangan mengetik bergantian di bawah
        c.line(12, 52, 44, 52, 1)
        left_y = 48 if idx % 2 == 0 else 50
        right_y = 50 if idx % 2 == 0 else 48
        c.circle(20, left_y, 2.3, fill=True)
        c.circle(36, right_y, 2.3, fill=True)
        frames.append({"duration_ms": 220, "lines": c.to_braille_lines()})
    return frames


def make_error_frames() -> list[dict]:
    frames = []
    for shake in (-1, 1):
        c = DotCanvas()
        draw_base_character(c, shake, 0)
        # Mata X / kaget
        c.line(20 + shake, 23, 24 + shake, 28, 2)
        c.line(24 + shake, 23, 20 + shake, 28, 2)
        c.line(32 + shake, 23, 36 + shake, 28, 2)
        c.line(36 + shake, 23, 32 + shake, 28, 2)
        # Mulut terbuka kaget
        c.ellipse(28 + shake, 34, 3.5, 2.8, fill=False, thickness=1.8)
        # Tanda seru di kanan atas
        c.line(48, 8, 48, 17, 2)
        c.circle(48, 21, 1.3, fill=True)
        frames.append({"duration_ms": 200, "lines": c.to_braille_lines()})
    return frames


def make_done_frames() -> list[dict]:
    frames = []
    for idx in range(2):
        oy = 0 if idx == 0 else -1
        c = DotCanvas()
        draw_base_character(c, 0, oy)
        # Mata tersenyum ^ ^
        c.arc(22, 27 + oy, 3.5, 3.0, 200, 340, 2)
        c.arc(34, 27 + oy, 3.5, 3.0, 200, 340, 2)
        # Senyum lebar
        c.arc(28, 31 + oy, 5.5, 4.0, 15, 165, 2)
        # Efek kilau (sparkle) bergantian
        if idx == 0:
            c.sparkle(8, 12, 3)
            c.sparkle(48, 16, 4)
        else:
            c.sparkle(10, 18, 4)
            c.sparkle(47, 10, 3)
        frames.append({"duration_ms": 340, "lines": c.to_braille_lines()})
    return frames


def main() -> None:
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    specs = {
        "idle": (make_idle_frames(), None),
        "thinking": (make_thinking_frames(), None),
        "coding": (make_coding_frames(), None),
        "error": (make_error_frames(), 6000),
        "done": (make_done_frames(), 4500),
    }

    for state, (frames, cooldown_ms) in specs.items():
        (RAW_DIR / state).mkdir(parents=True, exist_ok=True)
        out = FRAMES_DIR / f"{state}.json"
        payload = {
            "state": state,
            "loop": True,
            "cooldown_ms": cooldown_ms,
            "frames": frames,
        }
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Generated placeholder: {out}")


if __name__ == "__main__":
    main()
