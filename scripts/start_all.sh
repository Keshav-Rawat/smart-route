#!/usr/bin/env bash
# ============================================================
#  SmartRoute — Start All Services
#  Usage: bash scripts/start_all.sh
#  Stop:  Ctrl+C  (kills all background processes)
# ============================================================

set -e  # exit on first error

# ── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

echo -e "${BOLD}${CYAN}"
echo "  ███████╗███╗   ███╗ █████╗ ██████╗ ████████╗"
echo "  ██╔════╝████╗ ████║██╔══██╗██╔══██╗╚══██╔══╝"
echo "  ███████╗██╔████╔██║███████║██████╔╝   ██║   "
echo "  ╚════██║██║╚██╔╝██║██╔══██║██╔══██╗   ██║   "
echo "  ███████║██║ ╚═╝ ██║██║  ██║██║  ██║   ██║   "
echo "  ╚══════╝╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   "
echo "            🚦 SmartRoute — Adaptive Traffic    "
echo -e "${RESET}"

# Track PIDs to kill on exit
PIDS=()
cleanup() {
    echo -e "\n${YELLOW}⏹  Stopping all services...${RESET}"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    echo -e "${GREEN}✓ All services stopped.${RESET}"
}
trap cleanup EXIT INT TERM

# ── Helpers ──────────────────────────────────────────────────
start_service() {
    local name="$1"
    local dir="$2"
    local cmd="$3"
    local log="$LOG_DIR/${name}.log"

    echo -e "${CYAN}▶ Starting ${BOLD}${name}${RESET}${CYAN}...${RESET}"

    pushd "$dir" > /dev/null
    eval "$cmd" > "$log" 2>&1 &
    local pid=$!
    PIDS+=($pid)
    popd > /dev/null

    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo -e "  ${GREEN}✓ ${name} running${RESET} (PID $pid | log: logs/${name}.log)"
    else
        echo -e "  ${RED}✗ ${name} FAILED to start! Check logs/${name}.log${RESET}"
    fi
}

wait_for_port() {
    local port="$1"
    local name="$2"
    local retries=15
    echo -n "  Waiting for $name on :$port "
    for i in $(seq 1 $retries); do
        if nc -z localhost "$port" 2>/dev/null; then
            echo -e " ${GREEN}✓${RESET}"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    echo -e " ${RED}timeout${RESET}"
    return 1
}

# ── Check prerequisites ───────────────────────────────────────
echo -e "${BOLD}Checking prerequisites...${RESET}"

command -v python3   &>/dev/null && echo -e "  ${GREEN}✓${RESET} python3" || { echo -e "  ${RED}✗ python3 not found${RESET}"; exit 1; }
command -v node      &>/dev/null && echo -e "  ${GREEN}✓${RESET} node"    || { echo -e "  ${RED}✗ node not found${RESET}"; exit 1; }
command -v npm       &>/dev/null && echo -e "  ${GREEN}✓${RESET} npm"     || { echo -e "  ${RED}✗ npm not found${RESET}"; exit 1; }

# SUMO_HOME check (only warn, simulation is optional)
if [ -z "$SUMO_HOME" ]; then
    echo -e "  ${YELLOW}⚠  SUMO_HOME not set — simulation will not start${RESET}"
    RUN_SIMULATION=false
else
    echo -e "  ${GREEN}✓${RESET} SUMO_HOME = $SUMO_HOME"
    RUN_SIMULATION=true
fi

echo ""

# ── 1. Backend API ───────────────────────────────────────────
start_service "backend" \
    "$ROOT_DIR/backend" \
    "python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

wait_for_port 8000 "Backend API"

# ── 2. Blockchain Audit Bridge ───────────────────────────────
if [ -d "$ROOT_DIR/blockchain/node_modules" ]; then
    start_service "blockchain" \
        "$ROOT_DIR/blockchain" \
        "node bridge.js"
    wait_for_port 3001 "Blockchain Bridge"
else
    echo -e "  ${YELLOW}⚠  blockchain/node_modules missing. Run: cd blockchain && npm install${RESET}"
fi

# ── 3. Forecasting Prediction API ───────────────────────────
start_service "forecasting" \
    "$ROOT_DIR/forecasting" \
    "python3 predict_api.py"
wait_for_port 8001 "Forecasting API"

# ── 4. Dashboard ─────────────────────────────────────────────
if [ -d "$ROOT_DIR/dashboard/node_modules" ]; then
    start_service "dashboard" \
        "$ROOT_DIR/dashboard" \
        "npm run dev"
    wait_for_port 5173 "Dashboard"
else
    echo -e "  ${YELLOW}⚠  dashboard/node_modules missing. Run: cd dashboard && npm install${RESET}"
fi

# ── 5. Simulation (optional) ─────────────────────────────────
if [ "$RUN_SIMULATION" = true ]; then
    start_service "simulation" \
        "$ROOT_DIR/simulation" \
        "python3 adaptive_controller.py"
fi

# ── Summary ──────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}  🚦 SmartRoute is running!${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${CYAN}Dashboard  ${RESET}→  http://localhost:5173"
echo -e "  ${CYAN}Backend API${RESET}→  http://localhost:8000/docs"
echo -e "  ${CYAN}Forecasting${RESET}→  http://localhost:8001/docs"
echo -e "  ${CYAN}Blockchain ${RESET}→  http://localhost:3001/stats"
echo ""
echo -e "  Logs: ${LOG_DIR}/"
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop all services."
echo ""

# Keep running until user stops
wait
