#!/usr/bin/env bash
cd "$(git rev-parse --show-toplevel)"
for f in "$@"; do
  echo "==================== $f"
  awk '/^<<<<<<< /{f=1} f{print NR": "$0} /^>>>>>>> /{f=0}' "$f"
done
