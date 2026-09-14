#!/usr/bin/env bash
# =============================================================================
# W3Panel VM Automated Creation Script
# =============================================================================
set -euo pipefail

VM_NAME="w3panel-test"
ISO_DIR="/home/lky/Documents"
ISO_PATH="$ISO_DIR/ubuntu-24.04.1-live-server-amd64.iso"
PUB_KEY_PATH="/home/lky/.ssh/id_ed25519.pub"

echo "=== W3Panel VirtualBox Testing VM Creator ==="

# 1. Cleanup old VM if exists
if VBoxManage list vms | grep -q "\"$VM_NAME\""; then
    echo "VM $VM_NAME already exists. Powering off and deleting..."
    VBoxManage controlvm "$VM_NAME" poweroff || true
    VBoxManage unregistervm "$VM_NAME" --delete || true
fi
# Also remove leftover VDI if VM dir exists but VM is gone
rm -f "/home/lky/VirtualBox VMs/$VM_NAME/$VM_NAME.vdi" 2>/dev/null || true

# 2. Check/Download Ubuntu ISO
if [ ! -f "$ISO_PATH" ]; then
    echo "Ubuntu ISO not found at $ISO_PATH."
    echo "Downloading Ubuntu 24.04.1 Live Server ISO (approx. 2.6 GB)..."
    mkdir -p "$ISO_DIR"
    curl -L -o "$ISO_PATH" "https://old-releases.ubuntu.com/releases/24.04.1/ubuntu-24.04.1-live-server-amd64.iso"
    echo "Download completed."
else
    echo "Using existing Ubuntu ISO: $ISO_PATH"
fi


# 3. Create VM
echo "Creating VM $VM_NAME..."
VBoxManage createvm --name "$VM_NAME" --ostype Ubuntu_64 --register

# 4. Configure VM settings
echo "Configuring VM..."
VBoxManage modifyvm "$VM_NAME" \
  --memory 4096 \
  --cpus 4 \
  --nic1 nat \
  --boot1 dvd \
  --boot2 disk \
  --boot3 none \
  --boot4 none \
  --vram 16 \
  --graphicscontroller vmsvga \
  --audio-driver none

# 5. Fix VirtualBox 7.2 ps2 device reset issue
echo "Removing unsupported ps2 configuration..."
VBoxManage setextradata "$VM_NAME" "VBoxInternal/Devices/ps2/0/Config/Reset"

# 6. Create virtual hard disk
echo "Creating virtual disk..."
mkdir -p "/home/lky/VirtualBox VMs/$VM_NAME"
VBoxManage createhd \
  --filename "/home/lky/VirtualBox VMs/$VM_NAME/$VM_NAME.vdi" \
  --size 30000 \
  --format VDI

# 7. Attach Storage Controllers and Mediums
echo "Attaching virtual disk and controller..."
VBoxManage storagectl "$VM_NAME" --name "SATA" --add sata --controller IntelAhci
VBoxManage storageattach "$VM_NAME" \
  --storagectl "SATA" --port 0 --device 0 \
  --type hdd \
  --medium "/home/lky/VirtualBox VMs/$VM_NAME/$VM_NAME.vdi"

# 8. Configure Unattended Installation
echo "Configuring unattended Ubuntu installation..."
VBoxManage unattended install "$VM_NAME" \
  --iso "$ISO_PATH" \
  --user lky \
  --user-password 123 \
  --admin-password 123 \
  --hostname w3panel-test.local \
  --install-additions \
  --locale en_US \
  --country US \
  --time-zone UTC

# 9. Inject SSH Public Key into autoinstall user-data
if [ -f "$PUB_KEY_PATH" ]; then
    echo "Injecting SSH public key from $PUB_KEY_PATH into cloud-init config..."
    USER_DATA_FILE=$(find "/home/lky/VirtualBox VMs/$VM_NAME" -name "Unattended-*-user-data" | head -n 1)
    if [ -n "$USER_DATA_FILE" ] && [ -f "$USER_DATA_FILE" ]; then
        python3 -c "
import sys, re
from pathlib import Path

user_data_path = Path(sys.argv[1])
pub_key = Path(sys.argv[2]).read_text().strip()

content = user_data_path.read_text()

# Add ssh autoinstall block with public key
if 'ssh:' in content:
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == 'ssh:':
            lines.insert(idx + 1, '    authorized-keys:')
            lines.insert(idx + 2, f'      - {pub_key}')
            break
    content = '\n'.join(lines) + '\n'
else:
    content = content.replace('autoinstall:', f'autoinstall:\n  ssh:\n    install-server: true\n    allow-pw: true\n    authorized-keys:\n      - {pub_key}')

user_data_path.write_text(content)
" "$USER_DATA_FILE" "$PUB_KEY_PATH"
        echo "SSH key injected successfully."
    else
        echo "Warning: autoinstall user-data file not found."
    fi
else
    echo "Warning: Public key not found at $PUB_KEY_PATH. Skipping SSH key injection."
fi

# 10. Configure Port Forwarding NAT rules
echo "Configuring NAT Port Forwarding..."
VBoxManage modifyvm "$VM_NAME" \
  --natpf1 "ssh,tcp,,2222,,22" \
  --natpf1 "admin,tcp,,12087,,2087" \
  --natpf1 "user,tcp,,12083,,2083" \
  --natpf1 "http,tcp,,10080,,80" \
  --natpf1 "https,tcp,,10443,,443" \
  --natpf1 "ftp,tcp,,10021,,21" \
  --natpf1 "smtp,tcp,,10025,,25" \
  --natpf1 "smtp-msa,tcp,,10587,,587" \
  --natpf1 "smtps,tcp,,10465,,465" \
  --natpf1 "imap,tcp,,10143,,143" \
  --natpf1 "imaps,tcp,,10993,,993" \
  --natpf1 "pop3,tcp,,10110,,110" \
  --natpf1 "pop3s,tcp,,10995,,995" \
  --natpf1 "sieve,tcp,,14190,,4190" \
  --natpf1 "dns-tcp,tcp,,10053,,53" \
  --natpf1 "dns-udp,udp,,10053,,53"

# 11. Start VM
echo "Starting VM in headless mode..."
VBoxManage startvm "$VM_NAME" --type headless

# 12. Wait for installation to complete and take snapshot
echo ""
echo "Waiting for Ubuntu installation to complete (SSH on port 2222)..."
for i in $(seq 1 120); do
  if ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o PasswordAuthentication=no \
      -p 2222 -o ConnectTimeout=5 lky@localhost true 2>/dev/null; then
    echo "SSH is available. Taking snapshot..."
    break
  fi
  sleep 10
done

echo "Taking snapshot 'clean-base'..."
VBoxManage snapshot "$VM_NAME" take "clean-base" \
  --description "Clean Ubuntu install before W3Panel deployment"

echo ""
echo "=========================================================="
echo "VM successfully created and launched!"
echo ""
echo "Snapshot 'clean-base' created (clean Ubuntu, no W3Panel)."
echo ""
echo "SSH:  ssh -p 2222 lky@localhost"
echo "Root: root / 123"
echo ""
echo "To deploy W3Panel:"
echo "  rsync -avz -e 'ssh -p 2222' /path/to/W3Panel/ lky@localhost:/tmp/W3Panel/"
echo "  ssh -p 2222 lky@localhost 'cd /tmp/W3Panel && sudo bash install.sh'"
echo ""
echo "To revert to clean state:"
echo "  VBoxManage controlvm $VM_NAME poweroff"
echo "  VBoxManage snapshot $VM_NAME restore clean-base"
echo "  VBoxManage startvm $VM_NAME --type headless"
echo "=========================================================="
