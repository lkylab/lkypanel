# W3Panel v2 — Installation Guide

## Prerequisites

- Ubuntu 20.04+, Debian 11+, or CentOS 8+
- Root access (sudo)
- Internet connection
- Minimum 1GB RAM, 10GB disk

## Quick Install

### From GitHub (recommended)

```bash
sudo bash <(curl -fsSL https://raw.githubusercontent.com/lkylab/W3Panel/main/w3panel-v2/install.sh)
```

### From local clone

```bash
git clone -b v2 https://github.com/lkylab/W3Panel.git
cd W3Panel/w3panel-v2
sudo bash install.sh
```

## What the installer does

1. **System packages**: Installs Python 3, Podman, build tools, git, curl, openssl
2. **System user**: Creates `w3panel` user for running the panel
3. **Directories**: Creates `/usr/local/w3panel`, `/etc/w3panel`, `/var/lib/w3panel`, `/var/log/w3panel`
4. **Python environment**: Sets up virtualenv and installs Django + dependencies
5. **Database**: Runs Django migrations (SQLite by default)
6. **Admin user**: Creates `admin` user with password `123`
7. **SSL**: Generates self-signed certificate (valid 10 years)
8. **Systemd**: Installs `w3panel-admin` (port 2087) and `w3panel-user` (port 2083) services
9. **Firewall**: Opens ports 2087, 2083, 80, 443
10. **Sudoers**: Grants `w3panel` user passwordless sudo

## Default Access

| Service | URL | Credentials |
|---------|-----|-------------|
| Admin Panel | `https://<server-ip>:2087` | `admin` / `123` |
| User Panel | `https://<server-ip>:2083` | `admin` / `123` |
| API | `https://<server-ip>:2080` | Bearer token |

## Post-Installation

### Change admin password

```bash
cd /usr/local/w3panel
source venv/bin/activate
python manage.py shell -c "
from packages.core.models import User
u = User.objects.get(username='admin')
u.set_password('your-new-password')
u.save()
print('Password updated')
"
```

### Install plugins

```bash
# Install OpenLiteSpeed web server
cd /usr/local/w3panel
source venv/bin/activate
python manage.py shell -c "
from packages.plugins.manager import PluginManager
pm = PluginManager()
result = pm.install('openlitespeed')
print(result)
"
```

### Check service status

```bash
sudo systemctl status w3panel-admin
sudo systemctl status w3panel-user
```

### View logs

```bash
# Application logs
sudo journalctl -u w3panel-admin -f
sudo journalctl -u w3panel-user -f

# Access logs
sudo tail -f /var/log/w3panel/access.log

# Error logs
sudo tail -f /var/log/w3panel/error.log
```

## Upgrade

```bash
cd /usr/local/w3panel
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
sudo systemctl restart w3panel-admin w3panel-user
```

## Uninstall

```bash
sudo bash /usr/local/w3panel/uninstall.sh
```

## Ports

| Port | Service | Description |
|------|---------|-------------|
| 2087 | w3panel-admin | Admin control panel (HTTPS) |
| 2083 | w3panel-user | User control panel (HTTPS) |
| 2080 | w3panel-api | REST API (HTTPS) |

## Directory Structure

```
/usr/local/w3panel/          # Application files
├── apps/                    # Django apps
├── packages/                # Core packages
├── panel/                   # Settings
├── static/                  # CSS, JS
├── templates/               # HTML templates
├── manage.py                # Django management
├── install.sh               # Installer
├── uninstall.sh             # Uninstaller
└── requirements.txt         # Dependencies

/etc/w3panel/                # Configuration
├── ssl/                     # SSL certificates
└── installed_plugins.json   # Plugin registry

/var/lib/w3panel/            # Data
├── db/                      # SQLite database
└── plugins/                 # Plugin files

/var/log/w3panel/            # Logs
├── access.log
└── error.log
```

## Troubleshooting

### Port already in use

```bash
# Find process using the port
sudo ss -tuln | grep :2087
sudo ss -tuln | grep :2083

# Kill the process
sudo kill <pid>
```

### Service won't start

```bash
# Check status
sudo systemctl status w3panel-admin

# Check logs
sudo journalctl -u w3panel-admin -n 50

# Restart
sudo systemctl restart w3panel-admin
```

### Database locked

```bash
# Stop services
sudo systemctl stop w3panel-admin w3panel-user

# Remove database lock
rm -f /var/lib/w3panel/db/*.db-journal

# Restart
sudo systemctl start w3panel-admin w3panel-user
```

### Permission denied

```bash
# Fix ownership
sudo chown -R w3panel:w3panel /usr/local/w3panel
sudo chown -R w3panel:w3panel /etc/w3panel
sudo chown -R w3panel:w3panel /var/lib/w3panel
sudo chown -R w3panel:w3panel /var/log/w3panel
```