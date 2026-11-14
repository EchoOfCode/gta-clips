#!/usr/bin/env bash
set -u
printf '\n=== OS ===\n'
cat /etc/os-release | grep -E '^(PRETTY_NAME|VERSION_CODENAME)=' || true
printf '\n=== Architecture / CPU ===\n'
uname -m
nproc
printf '\n=== Memory ===\n'
free -h
printf '\n=== Disks / Mounts ===\n'
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS,MODEL
printf '\n=== Filesystems ===\n'
df -hT
printf '\n=== Docker ===\n'
docker --version 2>&1 || true
docker compose version 2>&1 || true
printf '\n=== Running containers ===\n'
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>&1 || true
printf '\n=== HDD mount check ===\n'
findmnt /mnt/data || true
