#!/usr/bin/env bash
# Reclaim disk when WSL/Docker acts up (low disk = the #1 cause of WSL crashes / FS lockups — see 03).
# Conservative by default (dangling only). Pass --aggressive to also drop ALL unused images + build cache.
# RUN:  bash .memory/tools/scripts/disk_cleanup.sh [--aggressive]
set -uo pipefail
AGG="${1:-}"
echo "=== disk BEFORE ==="; df -h / 2>/dev/null | tail -1

echo "--- docker: dangling images/containers/networks ---"
docker system prune -f 2>/dev/null || echo "(docker not available)"
docker builder prune -f 2>/dev/null || true

# Next.js build cache is large (~138M) and safe to delete — rebuilt on next dev/build.
for d in csharp/src/frontend/.next csharp/src/frontend/.turbo; do
  if [ -d "$(git rev-parse --show-toplevel)/$d" ]; then rm -rf "$(git rev-parse --show-toplevel)/$d" && echo "removed $d"; fi
done

if [ "$AGG" = "--aggressive" ]; then
  echo "--- AGGRESSIVE: all unused docker images + volumes + full build cache ---"
  docker system prune -a -f 2>/dev/null || true
  docker volume prune -f 2>/dev/null || true       # NOTE: vvf typesense-data volume will be dropped -> reindex after (see 03)
  docker builder prune -a -f 2>/dev/null || true
fi

echo "=== disk AFTER ==="; df -h / 2>/dev/null | tail -1
echo "If WSL's virtual disk stays full after this, compact the vhdx: see wsl_compact_vhdx.ps1 (admin)."
