#!/bin/sh
set -eu
umask 077
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PAB_UID=${PAB_UID:-$(id -u)}
export PAB_GID=${PAB_GID:-$(id -g)}
export PAB_STATE_DIR=${PAB_STATE_DIR:-$HOME/.local/state/personal-ai-brain/runtime}
export PAB_GITHUB_TOKEN_FILE=${PAB_GITHUB_TOKEN_FILE:-$HOME/.config/personal-ai-brain/github-token}
compose() { docker compose -f "$repo/compose.yaml" "$@"; }
case "${1:-health}" in
  up)
    mkdir -p "$PAB_STATE_DIR"
    test -s "$PAB_GITHUB_TOKEN_FILE"
    compose up -d --build --wait
    ;;
  down) compose down ;;
  health)
    if ! compose ps --status running --services 2>/dev/null | grep -qx core; then
      printf '{"runtime":"unavailable"}\n'
      exit 1
    fi
    compose exec -T core python -m personal_ai_brain.runtime health
    ;;
  core-report|rollup-proposals|core-snapshot)
    compose exec -T core python -m personal_ai_brain.runtime run "$1"
    ;;
  logs)
    printf 'Persistent runtime logs and results: %s\n' "$PAB_STATE_DIR"
    tail -n 100 "$PAB_STATE_DIR/service.log"
    ;;
  *) printf 'Usage: sh scripts/runtime.sh {up|down|health|core-report|rollup-proposals|core-snapshot|logs}\n' >&2; exit 2 ;;
esac
