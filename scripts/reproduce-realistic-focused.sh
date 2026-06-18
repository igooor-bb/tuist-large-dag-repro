#!/usr/bin/env bash
set -euo pipefail

exec ./scripts/reproduce.sh realistic --focus "$@"
