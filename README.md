# agy-companion

A Unicode Braille TUI companion for **Antigravity CLI (`agy`)** using a split-pane terminal and Antigravity Lifecycle Hooks — **0 extra tokens** & **0 runtime dependencies**.

## Features
- **5 core states + 5 optional granular states:** `idle`, `thinking`, `coding`, `error`, `done`, plus optional `reading`, `editing`, `running`, `searching`, and `sleepy` animations (automatically falls back to `coding`/`idle` if not created yet).
- **Local Status, Mood & Dialogue (0 tokens):** configured in [dialogue.json](./dialogue.json) and automatically mentions the file/command currently being worked on (e.g., `🔍 Reading code` · `"Checking auth.ts..."`).
- **Themes, Personas & Character Packs:**
  - **5 ANSI color themes:** `mono`, `amber`, `green`, `cyan`, `pastel`
  - **4 dialogue styles/personas:** `santai`, `formal`, `tsundere`, `zen`
  - **Multi-character:** create your own character pack in [characters/README.md](./characters/README.md)
- **Live-Reload & Mini Session Stats:** automatically reloads `assets/frames/*.json` and `dialogue.json` when edited, and displays session duration (`⏱`), tool call count (`🛠`), files touched (`📄`), `done` streak (`🔥`), and a mini activity log.
- **Auto-Sleepy:** automatically enters sleepy mode after being `idle` for too long (default 5 minutes, configurable via `--sleepy-after`).
- **Multi-Session Isolation:** each `agy-live` tab uses its own state file via `AGY_COMPANION_STATE_FILE` so multiple sessions can run concurrently without overwriting each other.
- **Cross-Platform & Packaging:** supports Windows Terminal ([scripts/launch-agy-live.ps1](./scripts/launch-agy-live.ps1)), Linux/macOS/WSL via `tmux`/WezTerm ([scripts/launch-agy-live.sh](./scripts/launch-agy-live.sh)), and [pyproject.toml](./pyproject.toml).
- **PNG → Braille Converter:** [convert.py](./convert.py) converts manual PNG sketches in `assets/raw/<state>/` (or `characters/<id>/raw/<state>/`) with *natural sort* and an `--aspect` option.

---

## 1. Try It Right Now

Run interactive preview mode (no installation required):

```powershell
python companion.py --demo
```

Or cycle through all states automatically every 3 seconds with a specific theme & persona:

```powershell
python companion.py --cycle --theme amber --persona tsundere
```

### Companion Pane Hotkeys
| Key | Action |
| :---: | :--- |
| **`t`** | Cycle color theme (`mono` → `amber` → `green` → `cyan` → `pastel`) |
| **`m`** | Cycle persona/dialogue style (`santai` → `formal` → `tsundere` → `zen`) |
| **`c`** | Cycle character pack *(if >1 pack exists in `characters/`)* |
| **`s`** | Show / hide session stats footer |
| **`l`** | Show / hide recent activity mini log |
| **`1`–`6`** | Switch state manually *(`--demo` only: `1` idle, `2` think, `3` code, `4` error, `5` done, `6` sleepy)* |
| **`q`** | Quit |

---

## 2. Automatic Integration with Antigravity CLI (Windows)

Run the automatic installer from this project folder to register hooks in `~/.gemini/config/hooks.json` (creates a `.bak` backup, does not overwrite other hooks) and add the `agy-live` shortcut to your PowerShell `$PROFILE`:

```powershell
.\scripts\install.ps1
. $PROFILE
```

Then run:

```powershell
agy-live
agy-live --theme amber
agy-live --theme pastel --persona zen --log -p "please review this folder"
```

> **Manual Integration:** If not using `install.ps1`, copy/merge the contents of [hooks.json.example](./hooks.json.example) into `~/.gemini/config/hooks.json` (adjust the path to `hook_reporter.py`), then add an `agy-live` function in `$PROFILE` that calls `scripts\launch-agy-live.ps1`.
>
> **Note on `PreToolUse`:** By default, `hook_reporter.py` exits with code `0` without printing JSON for `PreToolUse` so it does not alter `agy`'s built-in permission policy. If an explicit response is needed, add `--pretool-decision ask`.

---

## 3. Linux / macOS / WSL & Packaging

For **Linux / macOS / WSL** (automatically detects `tmux` or `WezTerm`):

```bash
chmod +x scripts/launch-agy-live.sh
./scripts/launch-agy-live.sh --theme amber --persona zen
```

Install as a Python CLI package (`agy-companion`, `agy-companion-hook`, `agy-companion-convert`):

```powershell
pip install -e .              # runtime (0 dependencies)
pip install -e ".[convert]"   # includes Pillow for the PNG converter
```

---

## 4. CLI Options Reference

### `companion.py` & `agy-live`
| Option | Default | Description |
| :--- | :--- | :--- |
| `--theme <name>` | `mono` | Choose color theme: `mono`, `amber`, `green`, `cyan`, `pastel` |
| `--persona <name>` | `santai` | Choose dialogue style: `santai`, `formal`, `tsundere`, `zen` |
| `--character <id>` | `default` | Choose character pack in `characters/<id>/` |
| `--sleepy-after <seconds>` | `300` | Idle duration before entering `sleepy` mode (`0` to disable) |
| `--no-stats` | *(on)* | Hide session stats footer |
| `--log` | *(off)* | Show activity mini log from the start |
| `--demo` / `--cycle` | *(off)* | Interactive preview / auto-cycle mode *(`companion.py` only)* |

*(In `agy-live`, all other arguments are passed through to `agy`; use `--` to pass all subsequent arguments verbatim to `agy`.)*

### `convert.py`
```powershell
python convert.py --preview assets/raw/idle/idle.png --width 45 --threshold 140
python convert.py --all --width 45 --threshold 140 --aspect 1.0
python convert.py --character neko --all --width 45 --threshold 140
```

---

## 5. Sketch Assets, Character Packs & Testing
- **Manual PNG → Braille sketch guide:** [ASSET_GUIDE.md](./ASSET_GUIDE.md)
- **Character Pack creation guide:** [characters/README.md](./characters/README.md)
- **Run unit & smoke tests:**
  ```powershell
  python tests/test_mvp.py
  ```
