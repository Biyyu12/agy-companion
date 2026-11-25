#!/usr/bin/env bash
# Launcher cross-platform (Linux / macOS / WSL) untuk agy-companion + agy.
# Mendukung tmux (otomatis jika di dalam/tersedia tmux) dan WezTerm.
#
# Contoh:
#   ./scripts/launch-agy-live.sh --theme amber --persona tsundere
#   ./scripts/launch-agy-live.sh --theme pastel -- -p "tolong review folder ini"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPANION_SCRIPT="$PROJECT_ROOT/companion.py"
STATE_DIR="$HOME/.agy-companion"
mkdir -p "$STATE_DIR"

# Bersihkan file state/exit sesi lama (> 24 jam)
find "$STATE_DIR" -maxdepth 1 \( -name 'state_*.json' -o -name 'exit_*.flag' \) -mmin +1440 -delete 2>/dev/null || true

COMPANION_ARGS=()
AGY_ARGS=()
PASS_ALL=0

while (($# > 0)); do
  if ((PASS_ALL)); then
    AGY_ARGS+=("$1")
    shift
    continue
  fi
  case "$1" in
    --)
      PASS_ALL=1
      shift
      ;;
    --theme|--character|--persona|--sleepy-after)
      if (($# < 2)); then
        echo "Error: $1 membutuhkan nilai argumen." >&2
        exit 1
      fi
      COMPANION_ARGS+=("$1" "$2")
      shift 2
      ;;
    --theme=*|--character=*|--persona=*|--sleepy-after=*)
      COMPANION_ARGS+=("$1")
      shift
      ;;
    --no-stats|--log)
      COMPANION_ARGS+=("$1")
      shift
      ;;
    *)
      AGY_ARGS+=("$1")
      shift
      ;;
  esac
done

SESSION_ID="$(python3 -c 'import uuid; print(uuid.uuid4().hex[:8])')"
STATE_FILE="$STATE_DIR/state_${SESSION_ID}.json"
EXIT_FILE="$STATE_DIR/exit_${SESSION_ID}.flag"
WORK_DIR="$(pwd)"

python3 - "$STATE_FILE" <<'PY'
import json, sys, time
from pathlib import Path
Path(sys.argv[1]).write_text(
    json.dumps({"state": "idle", "detail": "ready", "event": "LauncherStart", "updatedAt": time.time()}),
    encoding="utf-8",
)
PY

printf -v COMP_CMD 'python3 %q --state-file %q --exit-file %q' "$COMPANION_SCRIPT" "$STATE_FILE" "$EXIT_FILE"
for arg in "${COMPANION_ARGS[@]}"; do
  printf -v COMP_CMD '%s %q' "$COMP_CMD" "$arg"
done
COMP_CMD="${COMP_CMD}; rm -f $(printf '%q' "$STATE_FILE")"

printf -v AGY_CMD 'AGY_COMPANION_STATE_FILE=%q agy' "$STATE_FILE"
for arg in "${AGY_ARGS[@]}"; do
  printf -v AGY_CMD '%s %q' "$AGY_CMD" "$arg"
done
AGY_CMD="${AGY_CMD}; touch $(printf '%q' "$EXIT_FILE")"

if [[ -n "${WEZTERM_PANE:-}" ]] && command -v wezterm >/dev/null 2>&1; then
  wezterm cli split-pane --left --percent 32 --cwd "$WORK_DIR" -- bash -lc "$COMP_CMD" >/dev/null
  eval "$AGY_CMD"
elif [[ -n "${TMUX:-}" ]]; then
  tmux split-window -h -b -l 32% -c "$WORK_DIR" "$COMP_CMD"
  eval "$AGY_CMD"
elif command -v tmux >/dev/null 2>&1; then
  TMUX_NAME="agy-live-${SESSION_ID}"
  tmux new-session -d -s "$TMUX_NAME" -c "$WORK_DIR" "$COMP_CMD"
  tmux split-window -h -l 68% -t "$TMUX_NAME" -c "$WORK_DIR" "$AGY_CMD"
  tmux attach-session -t "$TMUX_NAME"
else
  echo "Error: butuh tmux atau WezTerm untuk split-pane di Linux/macOS." >&2
  echo "Kamu tetap bisa menjalankan companion di terminal terpisah:" >&2
  echo "  AGY_COMPANION_STATE_FILE=$STATE_FILE python3 $COMPANION_SCRIPT" >&2
  exit 1
fi
