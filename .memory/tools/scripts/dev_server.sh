#!/usr/bin/env bash
# Manage the frontend dev server for Playwright proofs (see 00). Handles the port-3000 leftover-node
# problem agents kept hitting. Complements the repo (`pnpm dev` is the repo's command).
# RUN (IMPORTANT — invoke with a BOUNDED tool timeout, e.g. 30000ms, and do NOT pipe it through
# Select-Object): on Windows the backgrounded node/Next process can keep the tool call's stdout pipe
# open even when fully backgrounded, so the tool call may not return until its timeout. That's why
# agents "got stuck" for the default 2-3 min. The server itself comes up in a few seconds — once the
# log/output shows `up on http://localhost:3000` it is READY; proceed (a timeout-return with that line
# is success, not a failure). See 03 "Session setup" / 00.
#   & "C:\Program Files\Git\bin\bash.exe" .memory/tools/scripts/dev_server.sh start   # bounded timeout ~30s
#   bash .memory/tools/scripts/dev_server.sh stop    # kill whatever holds :3000
#   bash .memory/tools/scripts/dev_server.sh status  # is :3000 up? (use this to confirm, cheaply)
set -uo pipefail
ROOT="$(git rev-parse --show-toplevel)"; FE="$ROOT/csharp/src/frontend"
CMD="${1:-status}"
port_pids(){ # PIDs listening on :3000 (Windows netstat via git-bash)
  netstat -ano 2>/dev/null | grep -E 'LISTENING' | grep -E ':3000\b' | awk '{print $NF}' | sort -u
}
stop(){ for p in $(port_pids); do [ -n "$p" ] && taskkill //F //PID "$p" >/dev/null 2>&1 && echo "killed pid $p"; done; }
case "$CMD" in
  start)
    stop; cd "$FE"
    LOG="$ROOT/.memory/temp/devserver.log"
    echo "starting pnpm dev (log: $LOG) ..."
    mkdir -p "$ROOT/.memory/temp"
    # Detach as hard as git-bash allows: new session (setsid if present), stdin from /dev/null, all
    # output to the log, and disown — so the child does NOT hold this shell's stdout pipe. (On Windows
    # this still isn't always enough — hence the bounded-timeout guidance in the header.)
    if command -v setsid >/dev/null 2>&1; then
      setsid pnpm dev </dev/null >"$LOG" 2>&1 &
    else
      nohup pnpm dev </dev/null >"$LOG" 2>&1 &
    fi
    DEV_PID=$!; disown "$DEV_PID" 2>/dev/null || true
    for i in $(seq 1 40); do curl -s -o /dev/null http://localhost:3000 && { echo "up on http://localhost:3000 (pid $DEV_PID)"; exit 0; }; sleep 2; done
    echo "did NOT come up in 80s — check $LOG"; exit 1;;
  stop) stop; echo "stopped";;
  status) pids="$(port_pids)"; [ -n "$pids" ] && echo ":3000 held by pid(s): $pids" || echo ":3000 free";;
  *) echo "usage: dev_server.sh start|stop|status"; exit 2;;
esac
