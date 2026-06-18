#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/reproduce.sh [realistic|stress] [--focus|--no-focus] [--skip-repeat]

Default:
  scripts/reproduce.sh stress --no-focus

Presets:
  realistic  Smaller smoke fixture with bounded longest path.
  stress     Primary recursive stack-safety stress fixture.

Modes:
  --no-focus     Run `tuist generate --no-open`.
  --focus        Run `tuist generate --no-open App`.
  --skip-repeat  Do not repeat Tuist generation from already generated DSL.
USAGE
}

preset="stress"
focus=0
repeat_existing_dsl=1

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    realistic|stress)
      preset="$1"
      ;;
    --focus|-f)
      focus=1
      ;;
    --no-focus)
      focus=0
      ;;
    --skip-repeat)
      repeat_existing_dsl=0
      ;;
    -h|--help|help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

tuist_bin="${TUIST_BIN:-tuist}"
tuist_args=(generate --no-open)
if [[ "$focus" -eq 1 ]]; then
  tuist_args+=(App)
fi

run_tuist_generate() {
  "$tuist_bin" "${tuist_args[@]}"
}

python3 scripts/generate-fixture.py --preset "$preset"
python3 scripts/verify-graph.py --preset "$preset"
python3 scripts/graph-stats.py

run_tuist_generate

if [[ "$repeat_existing_dsl" -eq 1 ]]; then
  echo
  echo "Repeating Tuist generation from existing DSL after cleaning Tuist output..."
  ./scripts/clean-tuist-output.sh
  run_tuist_generate
fi
