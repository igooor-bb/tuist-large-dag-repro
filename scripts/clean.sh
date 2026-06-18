#!/usr/bin/env bash
set -euo pipefail

./scripts/clean-tuist-output.sh

rm -rf \
  Projects \
  Workspace.swift \
  graph.json \
  tuist-repro*.log
