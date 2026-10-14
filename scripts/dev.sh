#!/usr/bin/env bash
# Run the LEDGEIT stack natively (no Docker): hardhat node, AI inspector, API, anchor worker, web.
# Needs: Postgres reachable at DATABASE_URL (see .env), `make install` done.
#   scripts/dev.sh start|stop|status|restart [service...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="$ROOT/var/run"; LOG="$ROOT/var/log"; PY="$ROOT/.venv/bin"
mkdir -p "$RUN" "$LOG"
ALL=(hardhat ai api worker web)

cmd_for() {
  case "$1" in
    hardhat) echo "cd $ROOT/contracts && exec npx hardhat node --hostname 127.0.0.1" ;;
    ai)      echo "cd $ROOT/services/ai-inspector && exec $PY/uvicorn app.main:app --port 8001" ;;
    api)     echo "cd $ROOT && exec $PY/uvicorn ledgeit_api.main:app --port 8000" ;;
    worker)  echo "cd $ROOT && exec $PY/python -m ledgeit_api.anchoring.run" ;;
    web)     echo "cd $ROOT/apps/web && exec npx vite --port 5173 --host 127.0.0.1" ;;
  esac
}

running() { [[ -f "$RUN/$1.pid" ]] && kill -0 "$(cat "$RUN/$1.pid")" 2>/dev/null; }

start() {
  local s=$1
  if running "$s"; then echo "  $s already running (pid $(cat "$RUN/$s.pid"))"; return; fi
  if [[ $s == web && ! -d $ROOT/apps/web/node_modules ]]; then echo "  web: run 'npm ci --prefix apps/web' first"; return; fi
  nohup bash -c "$(cmd_for "$s")" >"$LOG/$s.log" 2>&1 &
  echo $! >"$RUN/$s.pid"
  echo "  $s started (pid $!, log var/log/$s.log)"
  [[ $s == hardhat ]] && sleep 4 || true
  [[ $s == api ]] && sleep 2 || true
}

stop() {
  local s=$1
  if running "$s"; then
    pkill -TERM -P "$(cat "$RUN/$s.pid")" 2>/dev/null || true
    kill "$(cat "$RUN/$s.pid")" 2>/dev/null || true
    echo "  $s stopped"
  fi
  rm -f "$RUN/$s.pid"
}

action=${1:-status}; shift || true
services=("$@"); [[ ${#services[@]} -eq 0 ]] && services=("${ALL[@]}")
case "$action" in
  start)   [[ " ${services[*]} " == *" api "* ]] && "$PY/python" -m ledgeit_api.db.migrate >/dev/null
           for s in "${services[@]}"; do start "$s"; done ;;
  stop)    for s in "${services[@]}"; do stop "$s"; done ;;
  restart) for s in "${services[@]}"; do stop "$s"; done; sleep 1; for s in "${services[@]}"; do start "$s"; done ;;
  status)  for s in "${ALL[@]}"; do running "$s" && echo "  $s: running (pid $(cat "$RUN/$s.pid"))" || echo "  $s: stopped"; done ;;
  *) echo "usage: $0 start|stop|status|restart [${ALL[*]}]"; exit 2 ;;
esac
