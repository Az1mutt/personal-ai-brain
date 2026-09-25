#!/bin/sh
set -eu
umask 077
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
export PAB_UID=${PAB_UID:-$(id -u)}
export PAB_GID=${PAB_GID:-$(id -g)}
export PAB_STATE_DIR=${PAB_STATE_DIR:-$HOME/.local/state/personal-ai-brain/runtime}
export PAB_CONTROL_STATE=${PAB_CONTROL_STATE:-$HOME/.local/state/personal-ai-brain/control}
export PAB_GITHUB_TOKEN_FILE=${PAB_GITHUB_TOKEN_FILE:-$HOME/.config/personal-ai-brain/github-token}
export PAB_CONTROL_TOKEN_FILE=${PAB_CONTROL_TOKEN_FILE:-$HOME/.config/personal-ai-brain/github-control-token}
compose() { docker compose -f "$repo/compose.control.yaml" "$@"; }
case "${1:-health}" in
  up)
    mkdir -p "$PAB_CONTROL_STATE"
    test -s "$PAB_GITHUB_TOKEN_FILE"
    test -s "$PAB_CONTROL_TOKEN_FILE"
    compose up -d --build --wait
    ;;
  down) compose down ;;
  health)
    if ! compose ps --status running --services 2>/dev/null | grep -qx control; then
      printf '{"runtime":"unavailable"}\n'
      exit 1
    fi
    compose exec -T control python -m personal_ai_brain.control_worker health
    ;;
  logs)
    printf 'Private audit records: %s\n' "$PAB_CONTROL_STATE"
    compose logs --tail 50 control
    ;;
  *) printf 'Usage: sh scripts/control.sh {up|down|health|logs}\n' >&2; exit 2 ;;
esac
