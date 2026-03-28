#!/usr/bin/env bash
set -euo pipefail
# Restic install script — full implementation in Task 2
FLAG_DIR="${FLAG_DIR:-/usr/local/lkypanel/plugins}"
FLAG_FILE="${FLAG_FILE:-$FLAG_DIR/restic}"
LOG_FILE="${LOG_FILE:-/usr/local/lkypanel/plugin_install.log}"

trap 'echo "Plugin operation failed.[404]" >> "$LOG_FILE"' ERR

if [[ -f "$FLAG_FILE" ]]; then
    echo "Plugin already installed.[200]" >> "$LOG_FILE"
    exit 0
fi

if command -v apt-get &>/dev/null; then
    apt-get install -y restic
else
    yum install -y restic
fi

mkdir -p "$FLAG_DIR"
touch "$FLAG_FILE"
echo "Plugin installed.[200]" >> "$LOG_FILE"
