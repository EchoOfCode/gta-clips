#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Tailscale Host Status Check
# ==============================================================================
# Verifies host-level Tailscale status, tailnet IP, MagicDNS FQDN,
# Tailscale Serve configuration, and local loopback API health (127.0.0.1:18090).
# Never modifies any configuration. Safe and read-only.
# ==============================================================================
set -euo pipefail

API_PORT="${API_PORT:-18090}"
HEALTH_URL="http://127.0.0.1:${API_PORT}/health"
READY_URL="http://127.0.0.1:${API_PORT}/ready"

echo "======================================================================"
echo " GTA VI Clip Engine — Tailscale & Local API Status"
echo "======================================================================"

# 1. Verify Tailscale CLI availability
if ! command -v tailscale >/dev/null 2>&1; then
    echo "[!] Tailscale CLI is NOT installed on this host."
    echo "    Install via: curl -fsSL https://tailscale.com/install.sh | sh"
    exit 1
fi
echo "[OK] Tailscale CLI is installed."

# 2. Check Tailscale daemon connectivity
STATUS_JSON=$(tailscale status --json 2>/dev/null || echo "")
if [[ -z "$STATUS_JSON" ]]; then
    echo "[!] Tailscale daemon is not running or not reachable."
    exit 2
fi

BACKEND_STATE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('BackendState', 'Unknown'))" 2>/dev/null || echo "Unknown")
if [[ "$BACKEND_STATE" != "Running" ]]; then
    echo "[!] Tailscale backend is in state: $BACKEND_STATE (expected 'Running')"
    exit 3
fi
echo "[OK] Tailscale daemon is connected (State: $BACKEND_STATE)."

# 3. Extract Node info (Self) dynamically from JSON
DNS_NAME=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('Self', {}).get('DNSName', '').rstrip('.'))" 2>/dev/null || echo "")
TAILSCALE_IPS=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(' '.join(json.load(sys.stdin).get('Self', {}).get('TailscaleIPs', [])))" 2>/dev/null || echo "")
DEVICE_NAME=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('Self', {}).get('HostName', 'Unknown'))" 2>/dev/null || echo "")

echo "----------------------------------------------------------------------"
echo " Host Device Name : $DEVICE_NAME"
echo " Tailnet IPs      : $TAILSCALE_IPS"
echo " MagicDNS Domain  : ${DNS_NAME:-[Not configured]}"
if [[ -n "$DNS_NAME" ]]; then
    echo " HTTPS Serve URL  : https://${DNS_NAME}/"
fi
echo "----------------------------------------------------------------------"

# 4. Inspect current Tailscale Serve configuration
echo "Tailscale Serve Status:"
SERVE_STATUS=$(tailscale serve status 2>&1 || echo "No active serve configuration")
echo "$SERVE_STATUS"
echo "----------------------------------------------------------------------"

# 5. Check local GTA Clip Engine API loopback health
echo "Checking Local API (127.0.0.1:${API_PORT})..."
if curl -s -f -m 3 "$HEALTH_URL" >/dev/null 2>&1; then
    HEALTH_RESP=$(curl -s -m 3 "$HEALTH_URL" 2>/dev/null || echo "")
    echo "[OK] Local API is alive: $HEALTH_RESP"
else
    echo "[!] Local API is NOT responding on $HEALTH_URL."
    echo "    Ensure containers are running with: docker compose ps"
fi

if curl -s -f -m 3 "$READY_URL" >/dev/null 2>&1; then
    READY_RESP=$(curl -s -m 3 "$READY_URL" 2>/dev/null || echo "")
    echo "[OK] Local API dependencies (DB + Redis) ready: $READY_RESP"
else
    echo "[!] Local API readiness probe failed on $READY_URL."
fi
echo "======================================================================"
