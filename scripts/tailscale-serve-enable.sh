#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Tailscale Serve Enable Script
# ==============================================================================
# Safely enables private Tailscale HTTPS access to the local GTA Clip Engine API
# running on 127.0.0.1:18090.
#
# INVARIANTS:
# - Only touches the host Tailscale instance (host-managed).
# - NEVER runs 'tailscale serve reset'.
# - NEVER enables Tailscale Funnel (remains private to your tailnet only).
# - NEVER overwrites unrelated existing Serve configurations.
# - Verifies API liveness before enabling.
# - Idempotent: safe to run multiple times.
# - Requires confirmation (--yes / -y) in non-interactive environments.
# ==============================================================================
set -euo pipefail

API_PORT="${API_PORT:-18090}"
HEALTH_URL="http://127.0.0.1:${API_PORT}/health"
CONFIRMED=false

for arg in "$@"; do
    case "$arg" in
        -y|--yes)
            CONFIRMED=true
            ;;
        -h|--help)
            echo "Usage: $0 [--yes|-y]"
            echo "  --yes, -y  Confirm configuration change without interactive prompt."
            exit 0
            ;;
    esac
done

echo "=== GTA VI Clip Engine: Tailscale Serve Enablement ==="

# 1. Verify Tailscale CLI
if ! command -v tailscale >/dev/null 2>&1; then
    echo "ERROR: Tailscale CLI is not installed on this host." >&2
    exit 1
fi

# 2. Verify Tailscale daemon connectivity
STATUS_JSON=$(tailscale status --json 2>/dev/null || echo "")
if [[ -z "$STATUS_JSON" ]]; then
    echo "ERROR: Tailscale daemon is not reachable." >&2
    exit 2
fi

BACKEND_STATE=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('BackendState', 'Unknown'))" 2>/dev/null || echo "Unknown")
if [[ "$BACKEND_STATE" != "Running" ]]; then
    echo "ERROR: Tailscale daemon is not running (State: $BACKEND_STATE)." >&2
    exit 3
fi

DNS_NAME=$(echo "$STATUS_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('Self', {}).get('DNSName', '').rstrip('.'))" 2>/dev/null || echo "")
if [[ -z "$DNS_NAME" ]]; then
    echo "WARNING: MagicDNS domain name could not be resolved from Tailscale status."
fi

# 3. Verify local API health on 127.0.0.1:18090
echo "[1/4] Verifying local API liveness on 127.0.0.1:${API_PORT}..."
if ! curl -s -f -m 3 "$HEALTH_URL" >/dev/null 2>&1; then
    echo "ERROR: API is not healthy or unreachable on $HEALTH_URL." >&2
    echo "       Start containers with: docker compose up -d" >&2
    exit 4
fi
echo "      Local API is responding normally."

# 4. Inspect existing Tailscale Serve configuration
echo "[2/4] Inspecting existing Tailscale Serve configuration..."
SERVE_STATUS=$(tailscale serve status 2>&1 || echo "")

# Check if 18090 is already served
if echo "$SERVE_STATUS" | grep -E "(127\.0\.0\.1|localhost|http://localhost):${API_PORT}" >/dev/null 2>&1; then
    echo "[OK] Tailscale Serve is ALREADY configured for 127.0.0.1:${API_PORT}."
    if [[ -n "$DNS_NAME" ]]; then
        echo "     Private HTTPS URL: https://${DNS_NAME}/"
    fi
    exit 0
fi

# Check if an unrelated serve configuration is already active on root / or port 443
if [[ -n "$SERVE_STATUS" ]] && ! echo "$SERVE_STATUS" | grep -qi "no active serve"; then
    echo "WARNING: Existing Tailscale Serve configuration detected:"
    echo "$SERVE_STATUS"
    echo ""
    echo "ERROR: Existing unrelated Serve configuration is present. Refusing to overwrite automatically." >&2
    echo "       Please inspect existing mappings with 'tailscale serve status'." >&2
    exit 5
fi

# 5. Confirmation check
if [[ "$CONFIRMED" != "true" ]]; then
    if [[ -t 0 ]]; then
        read -r -p "Configure Tailscale Serve for 127.0.0.1:${API_PORT} in background? [y/N]: " response
        case "$response" in
            [yY][eE][sS]|[yY])
                CONFIRMED=true
                ;;
            *)
                echo "Aborted by user."
                exit 0
                ;;
        esac
    else
        echo "ERROR: Non-interactive session detected. Pass --yes flag to confirm." >&2
        exit 6
    fi
fi

# 6. Apply Tailscale Serve command
echo "[3/4] Configuring Tailscale Serve (background mode, port ${API_PORT})..."
tailscale serve --bg "${API_PORT}"

# 7. Verification and URL reporting
echo "[4/4] Verifying configuration..."
NEW_SERVE_STATUS=$(tailscale serve status 2>&1 || echo "")
echo "$NEW_SERVE_STATUS"

if [[ -n "$DNS_NAME" ]]; then
    HTTPS_URL="https://${DNS_NAME}/"
    echo ""
    echo "======================================================================"
    echo " Tailscale Serve successfully enabled!"
    echo " Private Tailnet URL: $HTTPS_URL"
    echo " Health Check       : ${HTTPS_URL}health"
    echo " Documentation      : ${HTTPS_URL}docs"
    echo "======================================================================"
fi
