#!/usr/bin/env bash
# ==============================================================================
# GTA VI Clip Engine — Host Preflight Verification Script
# ==============================================================================
# Verifies system requirements, storage mounts, existing services, and ports
# on Ubuntu Server 26.04.1 LTS before deployment.
# ==============================================================================
set -euo pipefail

printf '\n=== [1/6] OS & Kernel ===\n'
cat /etc/os-release | grep -E '^(PRETTY_NAME|VERSION_CODENAME)=' || true
uname -srm

printf '\n=== [2/6] CPU & Memory Resources ===\n'
CPUS=$(nproc)
echo "Logical CPUs: $CPUS"
free -h

printf '\n=== [3/6] Storage Mounts & HDD Verification ===\n'
df -hT / /mnt/data 2>&1 || true

if findmnt /mnt/data >/dev/null 2>&1; then
    MOUNT_SRC=$(findmnt -n -o SOURCE /mnt/data)
    ROOT_SRC=$(findmnt -n -o SOURCE /)
    if [[ "$MOUNT_SRC" == "$ROOT_SRC" ]]; then
        echo "[CRITICAL] /mnt/data is on the root filesystem! It is NOT a separate HDD mount."
    else
        echo "[OK] /mnt/data is a verified separate mount ($MOUNT_SRC)."
    fi
else
    echo "[CRITICAL] /mnt/data is NOT mounted! Check /etc/fstab or mount the HDD before proceeding."
fi

printf '\n=== [4/6] Docker & Compose Versions ===\n'
docker --version 2>&1 || true
docker compose version 2>&1 || true

printf '\n=== [5/6] Port Collision Checks (Host Network) ===\n'
# Check if 18090 is in use
if ss -tuln 2>/dev/null | grep -q ":18090 "; then
    echo "[WARNING] Port 18090 is already in use on the host!"
else
    echo "[OK] Target GTA API port 18090 is free."
fi

# Existing services check
echo "Existing monitored host services:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1 || true

printf '\n=== [6/6] Host Tailscale Status ===\n'
if command -v tailscale >/dev/null 2>&1; then
    tailscale status 2>&1 | head -n 5 || true
else
    echo "Tailscale CLI not found on host."
fi

echo "=== Preflight check complete ==="
