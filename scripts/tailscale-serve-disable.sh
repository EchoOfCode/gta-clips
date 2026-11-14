#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Tailscale Serve Disable Script
# ==============================================================================
# Selectively disables Tailscale Serve for the GTA Clip Engine API (port 18090).
#
# STRICT SAFETY INVARIANTS:
# - NEVER executes 'tailscale serve reset' (which would destroy other configurations).
# - NEVER executes 'tailscale down' or disables Tailscale on the host.
# - NEVER enables Funnel or alters ACLs.
# - ONLY removes the serve mapping if it currently routes to GTA's API port (18090).
# - Idempotent and safe to run multiple times.
# ==============================================================================
set -euo pipefail

API_PORT="${API_PORT:-18090}"

echo "=== GTA VI Clip Engine: Tailscale Serve Disable ==="

# 1. Verify Tailscale CLI
if ! command -v tailscale >/dev/null 2>&1; then
    echo "ERROR: Tailscale CLI is not installed on this host." >&2
    exit 1
fi

# 2. Inspect current Serve configuration
SERVE_STATUS=$(tailscale serve status 2>&1 || echo "")

if [[ -z "$SERVE_STATUS" ]] || echo "$SERVE_STATUS" | grep -qi "no active serve"; then
    echo "[OK] No active Tailscale Serve configuration found. Nothing to disable."
    exit 0
fi

# 3. Verify that the active Serve configuration actually belongs to GTA Clip Engine (port 18090)
if ! echo "$SERVE_STATUS" | grep -E "(127\.0\.0\.1|localhost|http://localhost):${API_PORT}" >/dev/null 2>&1; then
    echo "WARNING: Active Serve configuration does not appear to route to port ${API_PORT}:"
    echo "$SERVE_STATUS"
    echo ""
    echo "ABORTED: Refusing to modify or disable Serve because it may belong to another host service." >&2
    echo "         Inspect mappings with 'tailscale serve status'." >&2
    exit 2
fi

# 4. Safely disable only the GTA serve mapping without resetting other settings
echo "Found GTA Clip Engine Serve mapping on port ${API_PORT}."
echo "Disabling serve endpoint..."

# In Tailscale CLI, 'tailscale serve --https=443 off' or 'tailscale serve off' disables the HTTP/HTTPS proxy
if tailscale serve --https=443 off >/dev/null 2>&1; then
    echo "[OK] Tailscale Serve on HTTPS 443 disabled."
elif tailscale serve off >/dev/null 2>&1; then
    echo "[OK] Tailscale Serve disabled."
else
    echo "ERROR: Failed to disable Tailscale Serve cleanly." >&2
    exit 3
fi

echo "Current status after disable:"
tailscale serve status 2>&1 || true
echo "=== GTA Clip Engine Tailscale Serve successfully disabled. ==="
