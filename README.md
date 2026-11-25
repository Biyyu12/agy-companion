# agy-companion

Companion TUI berbasis Unicode Braille untuk **Antigravity CLI (`agy`)** menggunakan split-pane terminal dan Antigravity Lifecycle Hooks — **0 token tambahan** & **0 dependency di runtime**.

## Fitur
- **5 state inti + 5 state granular opsional:** `idle`, `thinking`, `coding`, `error`, `done`, plus animasi opsional `reading`, `editing`, `running`, `searching`, dan `sleepy` (otomatis fallback ke `coding`/`idle` jika belum dibuat).
- **Status, Mood & Dialog lokal (0 token):** diatur di [dialogue.json](./dialogue.json) dan otomatis menyebut nama file/perintah yang sedang dikerjakan (mis. `🔍 Reading code` · `"Lagi cek auth.ts nih..."`).
- **Theme, Persona & Character Packs:**
  - **5 tema warna ANSI:** `mono`, `amber`, `green`, `cyan`, `pastel`
  - **4 gaya bahasa/persona:** `santai`, `formal`, `tsundere`, `zen`
  - **Multi-karakter:** buat pack karakter sendiri di [characters/README.md](./characters/README.md)
- **Live-Reload & Mini Session Stats:** otomatis muat ulang `assets/frames/*.json` dan `dialogue.json` saat diedit, serta tampilkan durasi sesi (`⏱`), jumlah tool call (`🛠`), file disentuh (`📄`), streak `done` (`🔥`), dan mini activity log.
- **Auto-Sleepy:** otomatis masuk mode ngantuk setelah `idle` terlalu lama (default 5 menit, bisa diatur lewat `--sleepy-after`).
- **Isolasi Multi-Sesi:** setiap tab `agy-live` memakai state file sendiri via `AGY_COMPANION_STATE_FILE` sehingga beberapa sesi bisa berjalan bersamaan tanpa saling menimpa.
- **Cross-Platform & Packaging:** mendukung Windows Terminal ([scripts/launch-agy-live.ps1](./scripts/launch-agy-live.ps1)), Linux/macOS/WSL via `tmux`/WezTerm ([scripts/launch-agy-live.sh](./scripts/launch-agy-live.sh)), dan [pyproject.toml](./pyproject.toml).
- **Konverter PNG → Braille:** [convert.py](./convert.py) mengubah sketsa manual PNG di `assets/raw/<state>/` (atau `characters/<id>/raw/<state>/`) dengan *natural sort* dan opsi `--aspect`.

---

## 1. Coba Langsung Sekarang

Jalankan mode preview interaktif (tidak perlu install apa-apa):

```powershell
python companion.py --demo
```

Atau putar semua state otomatis tiap 3 detik dengan tema & persona tertentu:

```powershell
python companion.py --cycle --theme amber --persona tsundere
```

### Hotkey di Pane Companion
| Tombol | Fungsi |
| :---: | :--- |
| **`t`** | Ganti tema warna (`mono` → `amber` → `green` → `cyan` → `pastel`) |
| **`m`** | Ganti persona/gaya bahasa (`santai` → `formal` → `tsundere` → `zen`) |
| **`c`** | Ganti character pack *(jika ada >1 pack di `characters/`)* |
| **`s`** | Tampilkan / sembunyikan footer statistik sesi |
| **`l`** | Tampilkan / sembunyikan mini log aktivitas terakhir |
| **`1`–`6`** | Ganti state manual *(khusus `--demo`: `1` idle, `2` think, `3` code, `4` error, `5` done, `6` sleepy)* |
| **`q`** | Keluar |

---

## 2. Integrasi Otomatis dengan Antigravity CLI (Windows)

Jalankan installer otomatis dari folder project ini untuk memasang hook di `~/.gemini/config/hooks.json` (membuat backup `.bak`, tidak menimpa hook lain) sekaligus memasang shortcut `agy-live` ke PowerShell `$PROFILE`:

```powershell
.\scripts\install.ps1
. $PROFILE
```

Lalu jalankan:

```powershell
agy-live
agy-live --theme amber
agy-live --theme pastel --persona zen --log -p "tolong review folder ini"
```

> **Integrasi Manual:** Jika tidak memakai `install.ps1`, salin/gabungkan isi [hooks.json.example](./hooks.json.example) ke `~/.gemini/config/hooks.json` (sesuaikan path ke `hook_reporter.py`), lalu tambahkan fungsi `agy-live` di `$PROFILE` yang memanggil `scripts\launch-agy-live.ps1`.
>
> **Catatan tentang `PreToolUse`:** Secara default `hook_reporter.py` keluar dengan exit code `0` tanpa mencetak JSON untuk `PreToolUse` agar tidak mengubah kebijakan izin (*permission*) bawaan `agy`. Jika perlu respons eksplisit, tambahkan `--pretool-decision ask`.

---

## 3. Linux / macOS / WSL & Packaging

Untuk **Linux / macOS / WSL** (otomatis mendeteksi `tmux` atau `WezTerm`):

```bash
chmod +x scripts/launch-agy-live.sh
./scripts/launch-agy-live.sh --theme amber --persona zen
```

Install sebagai CLI package Python (`agy-companion`, `agy-companion-hook`, `agy-companion-convert`):

```powershell
pip install -e .              # runtime (0 dependency)
pip install -e ".[convert]"   # termasuk Pillow untuk konverter PNG
```

---

## 4. Referensi Opsi CLI

### `companion.py` & `agy-live`
| Opsi | Default | Keterangan |
| :--- | :--- | :--- |
| `--theme <nama>` | `mono` | Pilih tema warna: `mono`, `amber`, `green`, `cyan`, `pastel` |
| `--persona <nama>` | `santai` | Pilih gaya bahasa dialog: `santai`, `formal`, `tsundere`, `zen` |
| `--character <id>` | `default` | Pilih character pack di `characters/<id>/` |
| `--sleepy-after <detik>` | `300` | Durasi idle sebelum masuk mode `sleepy` (`0` untuk nonaktifkan) |
| `--no-stats` | *(aktif)* | Sembunyikan footer statistik sesi |
| `--log` | *(off)* | Tampilkan mini log aktivitas sejak awal |
| `--demo` / `--cycle` | *(off)* | Mode preview interaktif / putar otomatis *(khusus `companion.py`)* |

*(Pada `agy-live`, semua argumen lain diteruskan ke `agy`; gunakan `--` untuk meneruskan seluruh argumen setelahnya secara mentah ke `agy`).*

### `convert.py`
```powershell
python convert.py --preview assets/raw/idle/idle.png --width 45 --threshold 140
python convert.py --all --width 45 --threshold 140 --aspect 1.0
python convert.py --character neko --all --width 45 --threshold 140
```

---

## 5. Aset Sketsa, Character Pack & Testing
- **Panduan sketsa manual PNG → Braille:** [ASSET_GUIDE.md](./ASSET_GUIDE.md)
- **Panduan membuat Character Pack:** [characters/README.md](./characters/README.md)
- **Jalankan unit & smoke test:**
  ```powershell
  python tests/test_mvp.py
  ```
