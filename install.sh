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
# The repository has a nested structure where the app is in the root directory (manage.py, requirements.txt)
APP_ROOT="$INSTALL_DIR"
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
echo ""

# ── Helper: wait for dpkg lock ────────────────────────────────────────────────
wait_for_apt() {
    local max_wait=120
    local waited=0
    while fuser /var/lib/dpkg/lock-frontend &>/dev/null 2>&1 || fuser /var/lib/apt/lists/lock &>/dev/null 2>&1; do
        if [[ $waited -eq 0 ]]; then
            info "Waiting for other package managers (apt/dpkg) to finish..."
        fi
        sleep 5
        waited=$((waited + 5))
        if [[ $waited -ge $max_wait ]]; then
            warn "Timed out waiting for dpkg lock after ${max_wait}s — attempting to proceed."
            break
        fi
    done
}

# ── System packages ───────────────────────────────────────────────────────────
info "Cleaning up conflicting services (Apache)..."
if command -v apache2 &>/dev/null; then
    systemctl stop apache2 || true
    systemctl disable apache2 || true
elif command -v httpd &>/dev/null; then
    systemctl stop httpd || true
    systemctl disable httpd || true
fi

# Stop unattended-upgrades to prevent dpkg lock conflicts
if systemctl is-active --quiet unattended-upgrades 2>/dev/null; then
    info "Stopping unattended-upgrades to prevent lock conflicts..."
    systemctl stop unattended-upgrades || true
    systemctl disable unattended-upgrades || true
fi
wait_for_apt

# Add deadsnakes PPA for Python 3.12 on older Ubuntu
if [[ "$OS_ID" == "ubuntu" ]] && [[ "$OS_VER" < "24.04" ]]; then
    info "Adding deadsnakes PPA for Python 3.12 support..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y -qq software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
fi

# Add NodeSource for Node.js 22 (required for Vite 8)
info "Adding NodeSource repository for Node.js 22..."
curl -fsSL https://deb.nodesource.com/setup_22.x | bash - -y 2>/dev/null

info "Installing system packages..."

if [[ "$PKG_MGR" == "apt-get" ]]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq --no-install-recommends \
        python3.12 python3.12-venv python3.12-dev python3-pip \
        nodejs git curl wget openssl certbot \
        build-essential libssl-dev libffi-dev ufw unzip zip
else
    yum install -y -q \
        python3.12 python3.12-devel python3-pip \
        git curl wget openssl certbot \
        gcc openssl-devel libffi-devel firewalld unzip zip
fi
success "System packages installed"

# ── OpenLiteSpeed ─────────────────────────────────────────────────────────────
info "Installing OpenLiteSpeed..."

if ! command -v lswsctrl &>/dev/null && [[ ! -f /usr/local/lsws/bin/lswsctrl ]]; then
    if [[ "$IS_ARM" == true ]]; then
        info "ARM architecture detected — using LiteSpeed repo (aarch64 supported since OLS 1.7)"
    fi

    if [[ "$PKG_MGR" == "apt-get" ]]; then
        wget -qO - https://repo.litespeed.sh | bash
        apt-get update -qq
        apt-get install -y -qq openlitespeed lsphp83 lsphp83-common lsphp83-mysql \
            lsphp83-curl lsphp83-intl lsphp83-imagick lsphp83-imap 2>/dev/null || \
        apt-get install -y -qq openlitespeed lsphp83 lsphp83-common lsphp83-mysql lsphp83-curl
    else
        wget -qO - https://repo.litespeed.sh | bash
        yum install -y -q openlitespeed lsphp83 lsphp83-common lsphp83-mysql \
            lsphp83-curl lsphp83-intl lsphp83-imagick lsphp83-imap 2>/dev/null || \
        yum install -y -q openlitespeed lsphp83 lsphp83-common lsphp83-mysql lsphp83-curl
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


# ── Create system user and directories ────────────────────────────────────────
info "Creating system user and core directories..."

if ! getent group "$PANEL_USER" >/dev/null; then
    groupadd --system "$PANEL_USER"
fi

if ! getent passwd "$PANEL_USER" >/dev/null; then
    useradd --system \
        --gid "$PANEL_USER" \
        --create-home \
        --home-dir "/home/$PANEL_USER" \
        --shell /sbin/nologin \
        --comment "LkyPanel System User" \
        "$PANEL_USER"
fi

# Core directories
mkdir -p "/home/$PANEL_USER" "$LOG_DIR"
mkdir -p /usr/local/lsws/conf/vhosts

chown "$PANEL_USER":"$PANEL_USER" "/home/$PANEL_USER"
chown "$PANEL_USER":"$PANEL_USER" "$LOG_DIR"
chmod 700 "/home/$PANEL_USER"
chmod 750 "$LOG_DIR"

success "Core environment prepared"

# ── Clone repository ──────────────────────────────────────────────────────────
info "Cloning LkyPanel from ${REPO_URL}..."

if [[ -d "$INSTALL_DIR" ]] && [[ ! -d "$INSTALL_DIR/.git" ]] && [[ "$(ls -A "$INSTALL_DIR" 2>/dev/null)" ]]; then
    warn "Installation directory $INSTALL_DIR exists, is not empty and is not a git repo. Cleaning up..."
    rm -rf "$INSTALL_DIR"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
    warn "Repository already exists — pulling latest..."
    git config --global --add safe.directory "$INSTALL_DIR"
    git -C "$INSTALL_DIR" pull --ff-only
else
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# Create internal subdirectories and set permissions
mkdir -p "$DB_DIR" "$SSL_DIR"
chown -R "$PANEL_USER":"$PANEL_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
chmod 700 "$DB_DIR" "$SSL_DIR"

success "Repository cloned to $INSTALL_DIR"

# ── Python virtualenv and dependencies ────────────────────────────────────────
info "Setting up Python virtualenv..."

python3.12 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet --no-deps -r "$APP_ROOT/requirements.txt"
"$VENV_DIR/bin/pip" install --quiet -r "$APP_ROOT/requirements.txt"

success "Python dependencies installed"

# ── Generate secrets and .env ────────────────────────────────────────────────
info "Generating secrets..."

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

    # Detect public IP for dynamic CSRF trust
    SERVER_IP=$(curl -4 -fsSL https://ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')

    cat > "$ENV_FILE" <<EOF
SECRET_KEY=${SECRET_KEY}
FERNET_KEY=${FERNET_KEY}
SERVER_IP=${SERVER_IP}
EOF
    chmod 600 "$ENV_FILE"
    chown "$PANEL_USER":"$PANEL_USER" "$ENV_FILE"
    success "Secrets generated → $ENV_FILE"
fi

# ── Self-signed SSL cert for panel ports ──────────────────────────────────────
info "Generating self-signed SSL certificate for panel..."

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

# ── Frontend build ────────────────────────────────────────────────────────────
info "Building frontend assets..."

# Ensure static directory exists to satisfy Django's STATICFILES_DIRS check
mkdir -p "$INSTALL_DIR/lkypanel/static/dist"

if [[ -d "$INSTALL_DIR/frontend" ]] && command -v npm &>/dev/null; then
    cd "$INSTALL_DIR/frontend"
    npm install --quiet
    npm run build
    chown -R "$PANEL_USER":"$PANEL_USER" "$INSTALL_DIR/lkypanel/static"
    success "Frontend built and assets generated"
else
    warn "Frontend directory not found or npm not installed — skipping build"
fi

# ── Django setup ──────────────────────────────────────────────────────────────
info "Running Django migrations and setup..."

cd "$APP_ROOT"
export DJANGO_SETTINGS_MODULE=lkypanel.settings

# Check requirements
"$VENV_DIR/bin/python" manage.py check_requirements 2>/dev/null || true

# Run migrations
"$VENV_DIR/bin/python" manage.py migrate --run-syncdb

# Collect static files
"$VENV_DIR/bin/python" manage.py collectstatic --noinput 2>/dev/null || true

# Create initial admin user
# Password must be min 12 chars, upper, lower, digit, and special (!@#$%^&*()_+-=[]{}|;:,.<>?)
ADMIN_PASS=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9!@#$%^&*()_+-=' | head -c 20)
# Always append a special character (!) to ensure compliance
ADMIN_PASS="${ADMIN_PASS}!"
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
info "Deploying sudoers hardening..."
cat > "/etc/sudoers.d/lkypanel" <<EOF
lkypanel ALL=(ALL) NOPASSWD: /usr/local/lsws/bin/lswsctrl, /usr/bin/pure-pw, /usr/bin/certbot, /usr/bin/openssl, /usr/bin/apt-get, /usr/bin/yum, /usr/bin/dnf, /usr/sbin/ufw, /usr/sbin/firewall-cmd, /usr/bin/systemctl, /bin/systemctl, /usr/bin/fail2ban-client, /usr/bin/tail, /usr/bin/restic, /bin/mkdir, /usr/bin/mkdir, /bin/chown, /usr/bin/chown, /bin/chmod, /usr/bin/chmod, /usr/bin/tee, /bin/tee, /bin/rm, /usr/bin/rm, /bin/rmdir, /usr/bin/rmdir, /bin/cat, /usr/bin/cat, /usr/bin/cp, /bin/cp, /usr/bin/tar, /bin/tar, /usr/bin/touch, /bin/touch, /usr/sbin/useradd, /usr/sbin/usermod, /usr/sbin/userdel, /usr/sbin/adduser, /usr/sbin/groupadd, /usr/sbin/groupdel, /usr/bin/wget, /usr/bin/curl, /usr/sbin/postconf, /usr/sbin/postmap, /usr/bin/doveadm, /usr/bin/debconf-set-selections, /bin/ls, /usr/bin/ls, /bin/mv, /usr/bin/mv, /usr/bin/find, /bin/find, /usr/bin/unzip, /bin/unzip, /usr/bin/zip, /bin/zip, /usr/bin/du, /bin/du, /usr/bin/stat, /bin/stat
EOF
chmod 440 "/etc/sudoers.d/lkypanel"

if [[ "$PKG_MGR" == "apt-get" ]]; then
    PKG_LIST="mariadb-server mariadb-client curl wget git python3-venv python3-pip certbot ufw build-essential python3-dev"
fi
# Services and hardening deployed

success "Services and hardening deployed"

# ── CLI symlink ───────────────────────────────────────────────────────────────
info "Installing lky CLI..."
chmod +x "$APP_ROOT/lky"
# Fix shebang to use venv
sed -i "1s|#!.*|#!${VENV_DIR}/bin/python3.12|" "$APP_ROOT/lky"
ln -sf "$APP_ROOT/lky" /usr/local/bin/lky
success "CLI installed → /usr/local/bin/lky"

# ── OLS Panel Integration ───────────────────────────────────────────────────
info "Configuring OpenLiteSpeed for LkyPanel ports (2087/2083)..."
lky ols setup-panel

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
