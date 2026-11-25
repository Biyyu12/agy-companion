#!/usr/bin/env python3
"""Konverter PNG Sketsa Manual -> Monochrome Unicode Braille JSON.

Contoh pemakaian:
  # Konversi semua folder state di assets/raw/<state>/*.png -> assets/frames/<state>.json
  python convert.py --all --width 30 --threshold 140

  # Preview 1 gambar PNG langsung di terminal (untuk tuning threshold & lebar)
  python convert.py --preview assets/raw/idle/01_open.png --width 30 --threshold 140

  # Jika sketsamu berupa garis hitam di atas kertas putih (default):
  # gunakan --dark-lines (aktif secara default).
  # Jika sketsamu berupa garis putih di atas background gelap:
  # gunakan --light-lines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "assets" / "raw"
FRAMES_DIR = BASE_DIR / "assets" / "frames"
CHARACTERS_DIR = BASE_DIR / "characters"
CORE_STATES = ("idle", "thinking", "coding", "error", "done")
EXTRA_STATES = ("reading", "editing", "running", "searching", "sleepy")
STATES = CORE_STATES + EXTRA_STATES

# Default timing (ms) jika assets/raw/<state>/timing.json belum dibuat
DEFAULT_TIMING_MS = {
    "idle": [2800, 200, 5000, 3800],
    "thinking": [450, 450],
    "coding": [220, 220],
    "reading": [380, 380],
    "editing": [200, 200],
    "running": [260, 260],
    "searching": [320, 320],
    "sleepy": [2400, 2400],
    "error": [220, 220],
    "done": [150, 400, 300],
}

DEFAULT_COOLDOWN_MS = {
    "done": 4500,
    "error": 6000,
}

# Mapping bit dot Unicode Braille (2 kolom x 4 baris)
BRAILLE_BITS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


def import_pillow() -> Any:
    try:
        from PIL import Image, ImageOps  # type: ignore

        return Image, ImageOps
    except ImportError:
        print(
            "Error: Pillow belum terpasang.\n"
            "Jalankan: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)


def png_to_braille_lines(
    image_path: Path,
    width_chars: int = 30,
    threshold: int = 140,
    dark_lines: bool = True,
    dither: bool = False,
    aspect_correction: float = 1.0,
) -> list[str]:
    """Konversi 1 gambar PNG menjadi list baris teks Unicode Braille."""
    Image, ImageOps = import_pillow()

    with Image.open(image_path) as raw_img:
        # Ratakan transparansi ke latar putih (untuk dark_lines) atau hitam (untuk light_lines)
        bg_color = (255, 255, 255, 255) if dark_lines else (0, 0, 0, 255)
        rgba = raw_img.convert("RGBA")
        canvas = Image.new("RGBA", rgba.size, bg_color)
        canvas.alpha_composite(rgba)
        gray = canvas.convert("L")

    # Ukuran target dalam satuan titik (dots): 1 karakter Braille = 2x4 dots
    dot_w = max(2, width_chars * 2)
    orig_w, orig_h = gray.size
    raw_dot_h = int(round((orig_h / orig_w) * dot_w * aspect_correction))
    # Bulatkan tinggi ke kelipatan 4
    dot_h = max(4, ((raw_dot_h + 3) // 4) * 4)

    resized = gray.resize((dot_w, dot_h), Image.Resampling.LANCZOS)

    if dither:
        if dark_lines:
            resized = ImageOps.invert(resized)
        mono = resized.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        pixels = mono.load()

        def is_dot_on(x: int, y: int) -> bool:
            return pixels[x, y] > 0

    else:
        pixels = resized.load()

        def is_dot_on(x: int, y: int) -> bool:
            val = pixels[x, y]
            return val < threshold if dark_lines else val >= threshold

    lines: list[str] = []
    for y in range(0, dot_h, 4):
        row_chars: list[str] = []
        for x in range(0, dot_w, 2):
            mask = 0
            for dy in range(4):
                for dx in range(2):
                    if is_dot_on(x + dx, y + dy):
                        mask |= BRAILLE_BITS[dy][dx]
            row_chars.append(chr(0x2800 + mask))
        lines.append("".join(row_chars))

    return lines


def load_timing_overrides(state_raw_dir: Path) -> dict[str, int]:
    """Baca assets/raw/<state>/timing.json jika ada.

    Format contoh:
      {
        "01_open.png": 3200,
        "02_blink.png": 150
      }
    """
    timing_file = state_raw_dir / "timing.json"
    if not timing_file.exists():
        return {}
    try:
        data = json.loads(timing_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): max(40, int(v)) for k, v in data.items()}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Peringatan: gagal membaca {timing_file}: {exc}", file=sys.stderr)
    return {}


def natural_sort_key(path: Path) -> list[tuple[int, int | str]]:
    """Urutkan nama file secara natural berdasarkan stem (tanpa ekstensi).

    Contoh urutan hasil:
      idle.png -> idle-2.png -> idle-3.png -> idle-10.png
      01_open.png -> 02_blink.png -> 10_end.png
    """
    tokens = re.split(r"(\d+)", path.stem.lower())
    return [
        (1, int(tok)) if tok.isdigit() else (0, tok)
        for tok in tokens
        if tok
    ]


def convert_state(
    state: str,
    width: int,
    threshold: int,
    dark_lines: bool,
    dither: bool,
    aspect_correction: float = 1.0,
    raw_dir: Path = RAW_DIR,
    frames_dir: Path = FRAMES_DIR,
) -> bool:
    state_raw_dir = raw_dir / state
    if not state_raw_dir.exists():
        return False

    png_files = sorted(
        (
            p
            for p in state_raw_dir.iterdir()
            if p.is_file() and p.suffix.lower() == ".png"
        ),
        key=natural_sort_key,
    )
    if not png_files:
        return False

    timing_overrides = load_timing_overrides(state_raw_dir)
    default_timings = DEFAULT_TIMING_MS.get(state, [400])

    frames: list[dict[str, Any]] = []
    for idx, png_path in enumerate(png_files):
        lines = png_to_braille_lines(
            image_path=png_path,
            width_chars=width,
            threshold=threshold,
            dark_lines=dark_lines,
            dither=dither,
            aspect_correction=aspect_correction,
        )
        duration = timing_overrides.get(
            png_path.name,
            default_timings[idx % len(default_timings)],
        )
        frames.append(
            {
                "source": png_path.name,
                "duration_ms": duration,
                "lines": lines,
            }
        )

    frames_dir.mkdir(parents=True, exist_ok=True)
    out_path = frames_dir / f"{state}.json"
    payload = {
        "state": state,
        "loop": True,
        "cooldown_ms": DEFAULT_COOLDOWN_MS.get(state),
        "frames": frames,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] {state}: {len(frames)} frame -> {out_path}")
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Konverter sketsa PNG -> animasi Monochrome Braille untuk agy-companion."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--preview",
        type=Path,
        help="Tampilkan hasil konversi 1 file PNG langsung di terminal.",
    )
    group.add_argument(
        "--state",
        choices=STATES,
        help="Konversi semua PNG untuk satu state tertentu.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Konversi semua state yang memiliki file PNG di assets/raw/<state>/.",
    )

    parser.add_argument(
        "--width",
        type=int,
        default=30,
        help="Lebar output dalam karakter Braille (default: 30 = 60 dots).",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=140,
        help="Ambang gelap/terang 0-255 untuk mode garis tegas (default: 140).",
    )
    parser.add_argument(
        "--light-lines",
        action="store_true",
        help="Gunakan jika sketsa berupa garis putih di atas background gelap.",
    )
    parser.add_argument(
        "--dither",
        action="store_true",
        help="Aktifkan Floyd-Steinberg dithering (cocok untuk gambar bergradasi/foto).",
    )
    parser.add_argument(
        "--aspect",
        type=float,
        default=1.0,
        help="Koreksi rasio tinggi/lebar font terminal (default: 1.0).",
    )
    parser.add_argument(
        "--character",
        type=str,
        default=None,
        help="Konversi aset milik character pack tertentu di characters/<nama>/.",
    )

    args = parser.parse_args()
    dark_lines = not args.light_lines

    if args.character:
        raw_dir = CHARACTERS_DIR / args.character / "raw"
        frames_dir = CHARACTERS_DIR / args.character / "frames"
    else:
        raw_dir = RAW_DIR
        frames_dir = FRAMES_DIR

    if args.preview:
        if not args.preview.exists():
            print(f"File tidak ditemukan: {args.preview}", file=sys.stderr)
            return 1
        lines = png_to_braille_lines(
            image_path=args.preview,
            width_chars=args.width,
            threshold=args.threshold,
            dark_lines=dark_lines,
            dither=args.dither,
            aspect_correction=args.aspect,
        )
        print("\n".join(lines))
        return 0

    targets = STATES if args.all else (args.state,)
    converted_any = False
    for st in targets:
        if convert_state(
            state=st,
            width=args.width,
            threshold=args.threshold,
            dark_lines=dark_lines,
            dither=args.dither,
            aspect_correction=args.aspect,
            raw_dir=raw_dir,
            frames_dir=frames_dir,
        ):
            converted_any = True
        elif st in CORE_STATES or not args.all:
            print(f"[SKIP] {st}: belum ada file PNG di {raw_dir / st}")

    if not converted_any:
        print(
            f"\nBelum ada file PNG yang dikonversi. "
            f"Taruh sketsa PNG di {raw_dir}/<state>/ lalu jalankan lagi."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
