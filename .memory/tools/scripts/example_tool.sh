#!/usr/bin/env bash
# example_tool.sh — placeholder tool showing the expected shape of a memory script.
#
# What: replace this with your own reusable helper (orientation, verify gate, API caller, …).
# Why:  every script here must be parametrised and reusable — one-off scripts live in ../temp/
#       and get deleted. Add an index row in ../README.md and link the script from the topic
#       file it serves.
# How:  bash .memory/tools/scripts/example_tool.sh [args]
#
# Conventions:
# - Fail fast, explain usage.
# - Load secrets by path into a variable (never print them), e.g.:
#     TOKEN=$(jq -r .token path/to/secret.json)
set -euo pipefail

echo "This is a placeholder. Copy it as the starting point for your own memory tools."
