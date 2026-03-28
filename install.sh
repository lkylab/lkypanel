#!/usr/bin/env bash
# =============================================================================
# LkyPanel Installer
# Usage: bash <(curl -fsSL https://raw.githubusercontent.com/lkylab/lkypanel/main/install.sh)
# =============================================================================
set -euo pipefail

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()     { error "$*"; exit 1; }

# ── Config ────────────────────────────────────────────────────────────────────
REPO_URL="${LKYPANEL_REPO:-https://github.com/lkylab/lkypanel.git}"
INSTALL_DIR="/usr/local/lkypanel"
# The repository has a nested structure where the app is in the 'lkypanel' directory
APP_ROOT="$INSTALL_DIR/lkypanel"
VENV_DIR="$INSTALL_DIR/venv"
LOG_DIR="/var/log/lkypanel"
DB_DIR="$INSTALL_DIR/db"
SSL_DIR="$INSTALL_DIR/ssl"
SERVICE_DIR="/etc/systemd/system"
PANEL_USER="lkypanel"
ADMIN_PORT=2087
USER_PORT=2083

# ── Root check ────────────────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || die "Run as root: sudo bash install.sh"

# ── OS + Architecture detection ──────────────────────────────────────────────
if [[ -f /etc/os-release ]]; then
    source /etc/os-release
    OS_ID="${ID:-unknown}"
    OS_VER="${VERSION_ID:-0}"
else
    die "Cannot detect OS. /etc/os-release not found."
fi

ARCH=$(uname -m)
case "$ARCH" in
    x86_64)          ARCH_LABEL="x86_64"  ; IS_ARM=false ;;
    aarch64|arm64)   ARCH_LABEL="aarch64" ; IS_ARM=true  ;;
    armv7l)          ARCH_LABEL="armv7"   ; IS_ARM=true  ;;
    *) die "Unsupported architecture: $ARCH. Supported: x86_64, aarch64/arm64." ;;
esac

case "$OS_ID" in
    ubuntu|debian) PKG_MGR="apt-get" ;;
    centos|rhel|almalinux|rocky) PKG_MGR="yum" ;;
    *) die "Unsupported OS: $OS_ID. Supported: Ubuntu, Debian, CentOS, AlmaLinux, Rocky." ;;
esac

info "Detected: OS=${OS_ID} ${OS_VER}, Arch=${ARCH_LABEL}"

echo -e "${BOLD}"
echo "  ██╗     ██╗  ██╗██╗   ██╗██████╗  █████╗ ███╗   ██╗███████╗██╗     "
echo "  ██║     ██║ ██╔╝╚██╗ ██╔╝██╔══██╗██╔══██╗████╗  ██║██╔════╝██║     "
echo "  ██║     █████╔╝  ╚████╔╝ ██████╔╝███████║██╔██╗ ██║█████╗  ██║     "
echo "  ██║     ██╔═██╗   ╚██╔╝  ██╔═══╝ ██╔══██║██║╚██╗██║██╔══╝  ██║     "
echo "  ███████╗██║  ██╗   ██║   ██║     ██║  ██║██║ ╚████║███████╗███████╗"
echo "  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝"
echo -e "${NC}"
echo -e "  ${CYAN}Lightweight Hosting Control Panel${NC}"
echo -e "  Arch:  ${ARCH_LABEL}   OS: ${OS_ID} ${OS_VER}"
echo -e "  Admin: https://YOUR_IP:${ADMIN_PORT}   User: https://YOUR_IP:${USER_PORT}"
echo ""

# ── Step 1: System packages ───────────────────────────────────────────────────
info "Step 1/9 — Installing system packages..."

if [[ "$PKG_MGR" == "apt-get" ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    
    PACKAGES=(
        python3 python3-pip python3-venv python3-dev git curl wget openssl certbot build-essential libssl-dev libffi-dev ufw
    )

    for PKG in "${PACKAGES[@]}"; do
        info "Installing: $PKG"
        if apt-get install -y -qq "$PKG" 2>/dev/null; then
            success "$PKG installed"
        else
            warn "Failed to install $PKG — attempting to fix and retry..."
            apt-get install -y "$PKG" || die "FATAL: Could not install $PKG"
        fi
    done
else
    yum install -y -q \
        python3 python3-pip python3-devel \
        git curl wget openssl \
        certbot \
        gcc openssl-devel libffi-devel \
        firewalld
fi
success "System packages installed"

# ── Step 2: OpenLiteSpeed ─────────────────────────────────────────────────────
info "Step 2/9 — Installing OpenLiteSpeed..."

if ! command -v lswsctrl &>/dev/null && [[ ! -f /usr/local/lsws/bin/lswsctrl ]]; then
    if [[ "$IS_ARM" == true ]]; then
        # ARM: OLS repo script handles aarch64 since OLS 1.7.x
        # Verify the repo supports this arch before proceeding
        info "ARM architecture detected — using LiteSpeed repo (aarch64 supported since OLS 1.7)"
    fi

    if [[ "$PKG_MGR" == "apt-get" ]]; then
        wget -qO - https://repo.litespeed.sh | bash
        apt-get update -qq
        apt-get install -y -qq openlitespeed
    else
        wget -qO - https://repo.litespeed.sh | bash
        yum install -y -q openlitespeed
    fi

    # Verify install succeeded
    if [[ ! -f /usr/local/lsws/bin/lswsctrl ]]; then
        die "OpenLiteSpeed installation failed. Check https://openlitespeed.org/kb/install-ols-from-litespeed-repositories/"
    fi
    success "OpenLiteSpeed installed (${ARCH_LABEL})"
else
    success "OpenLiteSpeed already installed — skipping"
fi

# Ensure lswsctrl is in PATH
export PATH="$PATH:/usr/local/lsws/bin"

# Skip Step 3 (MariaDB setup) during initial install — handle via Packages panel
info "Step 3/9 — Skipping MariaDB setup (optional package)..."

# ── Step 4: Create system user and directories ────────────────────────────────
info "Step 4/9 — Creating directories and system user..."

# System user (no login shell)
if ! id "$PANEL_USER" &>/dev/null; then
    info "Creating system user $PANEL_USER..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "$PANEL_USER"
    success "User $PANEL_USER created"
else
    success "User $PANEL_USER already exists — skipping"
fi

mkdir -p "$INSTALL_DIR" "$LOG_DIR" "$DB_DIR" "$SSL_DIR"
mkdir -p /usr/local/lsws/conf/vhosts

chown -R "$PANEL_USER":"$PANEL_USER" "$INSTALL_DIR" "$LOG_DIR"
chmod 750 "$INSTALL_DIR" "$LOG_DIR"
chmod 700 "$DB_DIR" "$SSL_DIR"

success "Directories created"

# ── Step 5: Clone repository ──────────────────────────────────────────────────
info "Step 5/9 — Cloning LkyPanel from ${REPO_URL}..."

if [[ -d "$INSTALL_DIR" ]] && [[ ! -d "$INSTALL_DIR/.git" ]]; then
    warn "Installation directory $INSTALL_DIR exists but is not a git repo. Cleaning up..."
    rm -rf "$INSTALL_DIR"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
    warn "Repository already exists — pulling latest..."
    git config --global --add safe.directory "$INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

success "Repository cloned to $INSTALL_DIR"

# ── Step 6: Python virtualenv and dependencies ────────────────────────────────
info "Step 6/9 — Setting up Python virtualenv..."

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$APP_ROOT/requirements.txt"

success "Python dependencies installed"

# ── Step 7: Generate secrets and .env ────────────────────────────────────────
info "Step 7/9 — Generating secrets..."

ENV_FILE="$INSTALL_DIR/.env"

if [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists — skipping secret generation (keeping existing)"
else
    SECRET_KEY=$("$VENV_DIR/bin/python" -c \
        "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" \
        2>/dev/null || openssl rand -base64 50 | tr -d '\n')

    FERNET_KEY=$("$VENV_DIR/bin/python" -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" \
        2>/dev/null || openssl rand -base64 32 | tr -d '\n')

    cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET_KEY}
FERNET_KEY=${FERNET_KEY}
EOF
    chmod 600 "$ENV_FILE"
    chown "$PANEL_USER":"$PANEL_USER" "$ENV_FILE"
    success "Secrets generated → $ENV_FILE"
fi

# ── Step 8: Self-signed SSL cert for panel ports ──────────────────────────────
info "Step 8/9 — Generating self-signed SSL certificate for panel..."

mkdir -p "$SSL_DIR"
if [[ ! -f "$SSL_DIR/panel.crt" ]] || [[ ! -f "$SSL_DIR/panel.key" ]]; then
    SERVER_IP=$(curl -4 -fsSL https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
    openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
        -keyout "$SSL_DIR/panel.key" \
        -out "$SSL_DIR/panel.crt" \
        -subj "/C=US/ST=State/L=City/O=LkyPanel/CN=${SERVER_IP}" \
        -addext "subjectAltName=IP:${SERVER_IP}" \
        2>/dev/null
    chmod 600 "$SSL_DIR/panel.key" "$SSL_DIR/panel.crt"
    success "Self-signed cert generated (valid 10 years)"
else
    success "SSL cert already exists — skipping"
fi

# ── Step 9: Django setup ──────────────────────────────────────────────────────
info "Step 9/9 — Running Django migrations and setup..."

cd "$APP_ROOT"
export DJANGO_SETTINGS_MODULE=lkypanel.settings

# Check requirements
"$VENV_DIR/bin/python" manage.py check_requirements 2>/dev/null || true

# Run migrations
"$VENV_DIR/bin/python" manage.py migrate --run-syncdb

# Collect static files
"$VENV_DIR/bin/python" manage.py collectstatic --noinput --clear 2>/dev/null || true

# Create initial admin user
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)
"$VENV_DIR/bin/python" - <<PYEOF
import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'lkypanel.settings'
django.setup()
from lkypanel.models import User
if not User.objects.filter(username='admin').exists():
    u = User.objects.create_user(
        username='admin',
        email='admin@localhost',
        password='${ADMIN_PASS}',
        role='admin',
    )
    print(f'Admin user created: admin / ${ADMIN_PASS}')
else:
    print('Admin user already exists — skipping')
PYEOF

success "Django setup complete"

# ── Plugin selection ──────────────────────────────────────────────────────────

show_plugin_checklist() {
    local plugins_dir="$APP_ROOT/lkypanel/plugins"
    declare -A selected
    declare -a plugin_ids

    for dir in "$plugins_dir"/*/; do
        [[ -d "$dir" ]] || continue
        local id; id=$(basename "$dir")
        plugin_ids+=("$id")
        selected["$id"]=0
    done

    while true; do
        echo ""
        echo "  Select plugins to install (enter number to toggle, Enter to confirm):"
        for i in "${!plugin_ids[@]}"; do
            local id="${plugin_ids[$i]}"
            local desc; desc=$(python3 -c "import json; d=json.load(open('$plugins_dir/$id/meta.json')); print(d['description'])" 2>/dev/null || echo "$id")
            local mark="[ ]"; [[ "${selected[$id]}" == "1" ]] && mark="[x]"
            echo "  $((i+1))) $mark $id — $desc"
        done
        echo ""
        read -rp "  Toggle number (or press Enter to confirm): " choice
        [[ -z "$choice" ]] && break
        if [[ "$choice" =~ ^[0-9]+$ ]]; then
            local idx=$((choice - 1))
            local id="${plugin_ids[$idx]:-}"
            [[ -n "$id" ]] && selected["$id"]=$(( 1 - ${selected[$id]} ))
        fi
    done

    for id in "${plugin_ids[@]}"; do
        if [[ "${selected[$id]}" == "1" ]]; then
            info "Installing plugin: $id"
            bash "$plugins_dir/$id/install.sh" || warn "Plugin $id install failed — continuing"
        fi
    done
}

if [[ "${LKYPANEL_NONINTERACTIVE:-0}" == "1" ]]; then
    info "Non-interactive mode — skipping plugin selection"
else
    show_plugin_checklist
fi

# ── Systemd services ──────────────────────────────────────────────────────────
info "Installing systemd services..."

cp "$APP_ROOT/lky-admin.service" "$SERVICE_DIR/lky-admin.service"
cp "$APP_ROOT/lky-user.service"  "$SERVICE_DIR/lky-user.service"

# Fix paths in service files to use venv
sed -i "s|/usr/local/lkypanel/venv|${VENV_DIR}|g" \
    "$SERVICE_DIR/lky-admin.service" \
    "$SERVICE_DIR/lky-user.service"

systemctl daemon-reload
systemctl enable --now lky-admin
systemctl enable --now lky-user

# Deploy hardening configs
info "Deploying hardening configurations..."
cp "$APP_ROOT/hardening/lkypanel.sudoers" "/etc/sudoers.d/lkypanel"
chmod 440 "/etc/sudoers.d/lkypanel"

if [[ "$PKG_MGR" == "apt-get" ]]; then
    PKG_LIST="mariadb-server mariadb-client curl wget git python3-venv python3-pip certbot ufw build-essential python3-dev"
fi
cp "$APP_ROOT/hardening/fail2ban-lkypanel.conf" "/etc/fail2ban/jail.d/lkypanel.conf"
cp "$APP_ROOT/hardening/lkypanel.filter" "/etc/fail2ban/filter.d/lkypanel.conf"

success "Services and hardening deployed"

# ── CLI symlink ───────────────────────────────────────────────────────────────
info "Installing lky CLI..."
chmod +x "$APP_ROOT/lky"
# Fix shebang to use venv
sed -i "1s|#!.*|#!${VENV_DIR}/bin/python3|" "$APP_ROOT/lky"
ln -sf "$APP_ROOT/lky" /usr/local/bin/lky
success "CLI installed → /usr/local/bin/lky"

# ── Firewall ──────────────────────────────────────────────────────────────────
info "Configuring firewall..."

if command -v ufw &>/dev/null; then
    ufw allow 22/tcp   comment "SSH"    2>/dev/null || true
    ufw allow 80/tcp   comment "HTTP"   2>/dev/null || true
    ufw allow 443/tcp  comment "HTTPS"  2>/dev/null || true
    ufw allow 2087/tcp comment "LkyPanel Admin" 2>/dev/null || true
    ufw allow 2083/tcp comment "LkyPanel User"  2>/dev/null || true
    ufw --force enable 2>/dev/null || true
    success "UFW firewall configured"
elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-port=2087/tcp 2>/dev/null || true
    firewall-cmd --permanent --add-port=2083/tcp 2>/dev/null || true
    firewall-cmd --permanent --add-service=http  2>/dev/null || true
    firewall-cmd --permanent --add-service=https 2>/dev/null || true
    firewall-cmd --permanent --add-service=ftp   2>/dev/null || true
    firewall-cmd --reload 2>/dev/null || true
    success "firewalld configured"
fi

# Final ownership fix
info "Ensuring correct file permissions..."
chown -R "$PANEL_USER":"$PANEL_USER" "$INSTALL_DIR" "$LOG_DIR"
chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true

success "LkyPanel installation complete! 🛡️"

# ── Done ──────────────────────────────────────────────────────────────────────
SERVER_IP=$(curl -4 -fsSL https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}  LkyPanel installed successfully!${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Admin Panel:${NC}  https://${SERVER_IP}:${ADMIN_PORT}"
echo -e "  ${BOLD}User Panel:${NC}   https://${SERVER_IP}:${USER_PORT}"
echo ""
echo -e "  ${BOLD}Admin login:${NC}  admin / ${ADMIN_PASS}"
echo -e "  ${YELLOW}  ↑ Save this password — it won't be shown again!${NC}"
echo ""
echo -e "  ${BOLD}Install dir:${NC}  ${INSTALL_DIR}"
echo -e "  ${BOLD}Logs:${NC}         ${LOG_DIR}"
echo -e "  ${BOLD}DB:${NC}           ${DB_DIR}/panel.db"
echo ""
echo -e "  ${CYAN}Check service status:${NC}"
echo -e "    systemctl status lky-admin"
echo -e "    systemctl status lky-user"
echo ""
echo -e "  ${CYAN}Check requirements:${NC}"
echo -e "    ${VENV_DIR}/bin/python ${INSTALL_DIR}/manage.py check_requirements"
echo ""

echo -e "  ${CYAN}CLI quick start:${NC}"
echo -e "    lkypanel status"
echo -e "    lkypanel website list"
echo -e "    lkypanel user create"
echo -e "    lkypanel ssl request example.com"
echo -e "    lkypanel --help"
echo ""
