# LkyPanel

A lightweight, security-focused web hosting control panel built with Django. Inspired by cPanel's dual-port model — admin on port **2087**, users on port **2083**. Designed to consume minimal resources while managing OpenLiteSpeed, Pure-FTPd, Let's Encrypt SSL, Git deployments, and MariaDB databases.

---

## Quick Install

```bash
# Adding ?v=1 at the end to bypass GitHub's cache
curl -fsSL "https://raw.githubusercontent.com/lkylab/lkypanel/main/lkypanel/install.sh?v=$(date +%s)" -o install.sh && sudo bash install.sh

```

For automated/non-interactive deployments (no prompts, core only):

```bash
LKYPANEL_NONINTERACTIVE=1 sudo bash install.sh

```

Or clone and run manually:

```bash
git clone https://github.com/lkylab/lkypanel.git /usr/local/lkypanel
cd /usr/local/lkypanel
sudo bash install.sh
```

**Supported OS:** Ubuntu 20.04+, Debian 11+, AlmaLinux/Rocky/CentOS 8+

**Supported Architecture:** x86_64 (amd64) and ARM64 (aarch64) — AWS Graviton, Oracle Ampere, Raspberry Pi 4+

**Requirements:** Python 3.8+, 1 GB RAM minimum, root access

---

## Access

| Interface      | URL                          | Who          |
|----------------|------------------------------|--------------|
| Admin Panel    | `https://YOUR_IP:2087`       | Admins only  |
| User Panel     | `https://YOUR_IP:2083`       | Regular users|
| REST API       | `https://YOUR_IP:2087/api/v1/` | Token auth |

Default credentials after install: `admin` / *(shown once at install end)*

---

## Features

### Panel Architecture
- Two isolated gunicorn processes (2 workers each, ~30 MB RAM each)
- Port-level isolation enforced by `PortIsolationMiddleware` — wrong port returns HTTP 403
- Role enforcement: admins cannot use port 2083, users cannot use port 2087
- SQLite for panel metadata (no extra DB process)
- APScheduler in-process for SSL renewal (no Celery/Redis)
- All static files served by OpenLiteSpeed directly

### Plugin / Package Management

LkyPanel uses a modular plugin system. A minimal **Core** (OpenLiteSpeed, Django panel, Certbot, UFW) always installs. Optional components are plugins managed at install time and post-install via the **Packages** page.

**Built-in plugins:** `mariadb`, `pureftpd`, `redis`, `postfix`, `phpmyadmin`, `restic`, `fail2ban`

- Each plugin lives at `lkypanel/plugins/{name}/` with `meta.json`, `install.sh`, `remove.sh`
- Plugin state tracked via flag files — no database changes needed
- Install/remove runs as a background subprocess; the UI polls for completion
- Feature gating: Create Database, FTP, Backup, Email nav, and Security warnings are all tied to plugin state
- Interactive install presents a checklist to select plugins; `LKYPANEL_NONINTERACTIVE=1` skips all plugins

### Security
- **Argon2** password hashing (industry standard, memory-hard)
- **Brute-force lockout** — 3 failed attempts locks account for 15 minutes
- **Fernet symmetric encryption** for stored Git credentials
- **CSRF protection** on all form views
- **Session hardening** — `Secure`, `HttpOnly`, `SameSite=Strict`, 30-minute timeout
- **API tokens** stored as SHA-256 hashes only (raw token shown once)
- **Rate limiting** — 100 requests/minute per API token
- **Input sanitization** — domain/path traversal sequences rejected at validation layer
- **Audit log** — every security-relevant action logged with user, IP, timestamp
- All subprocess calls use `shell=False` with explicit argument lists

### User Management
- Two roles: **Admin** and **User**
- Admin: full access to all websites, users, system settings
- User: access only to their own assigned websites
- Create, list, delete users
- Reset any user's password (admin only)
- Session invalidation on user deletion

### Website Management
- Create websites with automatic directory structure: `/home/{domain}/public_html/`
- OpenLiteSpeed vhost config auto-generated at `/usr/local/lsws/conf/vhosts/{domain}/vhconf.conf`
- Configure PHP version per website (lsphp)
- OLS graceful reload on every config change (< 5 seconds)
- Delete website with optional file removal and cascade cleanup
- Assign websites to specific users

### FTP Management
- Install Pure-FTPd directly from the admin panel
- Create FTP accounts linked to specific websites
- Home directory locked to `/home/{domain}/public_html/` (no escape)
- SHA512-crypt password hashing for Pure-FTPd virtual users
- Change FTP passwords, delete accounts
- Multiple FTP accounts per website

### Git Integration
- Clone public or private repositories into website document root
- Supports **SSH key** and **access token** authentication
- SSH keys written to temp file with `600` permissions, deleted after use
- Tokens injected into URL in memory only — never logged or stored in plaintext
- `git pull` and `git push` from the panel
- Configure git user name and email per repository
- Git stderr sanitized (ANSI stripped, truncated at 2048 chars) before display

### SSL Management
- Let's Encrypt certificates via **certbot** (HTTP-01 challenge)
- Domain DNS resolution verified against server IP before requesting
- Cert path: `/etc/letsencrypt/live/{domain}/fullchain.pem`
- OLS vhost updated with SSL listener block on issuance
- **Auto-renewal** — daily check at 03:00 UTC, renews certs expiring within 30 days
- Renewal failures logged to AuditLog and retried daily

### Database Management
- Create MariaDB/MySQL databases linked to websites
- Dedicated database user per database (access limited to that DB only)
- Delete database and associated user together
- Ownership enforced — users can only manage their own website's databases

### REST API
- Base URL: `/api/v1/`
- Authentication: `Authorization: Bearer <token>` header
- All responses in JSON
- Rate limited: 100 requests/minute per token
- Endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/api/v1/websites/` | List / create websites |
| GET/PUT/DELETE | `/api/v1/websites/{id}/` | Website detail |
| GET/POST | `/api/v1/users/` | List / create users (admin only) |
| GET/POST | `/api/v1/ftp/` | List / create FTP accounts |
| GET/POST | `/api/v1/ssl/` | List / request SSL certs |
| GET/POST | `/api/v1/git/` | List / link Git repos |
| GET/POST | `/api/v1/databases/` | List / create databases |
| POST | `/api/v1/tokens/create/` | Create API token |

### Configuration Export
- Export all website configs to JSON (no credentials included)
- Export all user accounts to JSON (no password hashes)
- Includes export timestamp and panel version

---

## Command Line (lkypanel CLI)

A full CLI is available after install at `/usr/local/lkypanel/lkypanel-cli`:

```bash
# Symlinked to /usr/local/bin/lkypanel during install
lkypanel --help
```

See [CLI Usage](#cli-usage) below for all commands.

---

## Directory Structure

```
/usr/local/lkypanel/         # Panel install root
├── venv/                     # Python virtualenv
├── lkypanel/                # Django project
│   ├── settings.py
│   ├── models.py
│   ├── middleware.py
│   ├── auth.py
│   ├── audit.py
│   ├── scheduler.py
│   ├── admin_views/
│   ├── user_views/
│   ├── api/
│   ├── services/
│   │   ├── ols.py            # OpenLiteSpeed integration
│   │   ├── ftp.py            # Pure-FTPd integration
│   │   ├── git.py            # Git operations
│   │   ├── ssl.py            # certbot / Let's Encrypt
│   │   ├── db_manager.py     # MariaDB management
│   │   └── packages.py       # Plugin state & async ops
│   ├── plugins/              # Built-in plugins
│   │   ├── mariadb/          # meta.json, install.sh, remove.sh
│   │   ├── pureftpd/
│   │   ├── redis/
│   │   ├── postfix/
│   │   ├── phpmyadmin/
│   │   ├── restic/
│   │   └── fail2ban/
│   └── templates/
├── db/panel.db               # SQLite panel database
├── ssl/panel.crt             # Self-signed cert for panel ports
├── static/                   # Served by OLS
└── .env                      # Secrets (chmod 600)

/home/{domain}/public_html/   # Website document root
/usr/local/lsws/conf/vhosts/  # OLS vhost configs
/etc/letsencrypt/live/        # SSL certificates
/etc/pure-ftpd/               # FTP config
/var/log/lkypanel/           # Panel logs
```

---

## CLI Usage

```
lkypanel <command> [options]

Commands:
  status                    Show panel service status
  restart                   Restart both panel services
  stop                      Stop both panel services
  start                     Start both panel services

  user list                 List all users
  user create               Create a new user (interactive)
  user delete <username>    Delete a user
  user passwd <username>    Reset a user's password

  website list              List all websites
  website create            Create a new website (interactive)
  website delete <domain>   Delete a website
  website info <domain>     Show website details

  ftp list [domain]         List FTP accounts
  ftp create                Create FTP account (interactive)
  ftp delete <username>     Delete FTP account
  ftp passwd <username>     Change FTP password

  ssl request <domain>      Request Let's Encrypt SSL
  ssl status <domain>       Show SSL certificate status
  ssl renew <domain>        Force SSL renewal

  git status <domain>       Show linked Git repo
  git pull <domain>         Pull latest from remote
  git push <domain>         Push to remote

  db list [domain]          List databases
  db create                 Create database (interactive)
  db delete <db_name>       Delete database

  logs [--lines N]          Tail panel logs
  check                     Run system requirements check
  version                   Show panel version
```

---

## Service Management

```bash
systemctl status lky-admin    # Admin panel (port 2087)
systemctl status lky-user     # User panel (port 2083)
systemctl restart lky-admin
systemctl restart lky-user
```

---

## Updating

```bash
cd /usr/local/lkypanel
git pull
venv/bin/pip install -r requirements.txt
venv/bin/python manage.py migrate
systemctl restart lky-admin lky-user
```

---

## Resource Usage

| Component | Idle RAM | Notes |
|-----------|----------|-------|
| Admin gunicorn (2 workers) | ~30 MB | Port 2087 |
| User gunicorn (2 workers) | ~30 MB | Port 2083 |
| SQLite | ~5 MB | Panel metadata only |
| APScheduler | 0 extra | In-process, no Redis |
| **Total panel overhead** | **~65 MB** | |

---

## Architecture Support

| Architecture | Status | Tested On |
|---|---|---|
| x86_64 (amd64) | ✅ Full support | Ubuntu 22.04, Debian 12, AlmaLinux 9 |
| aarch64 / ARM64 | ✅ Full support | AWS Graviton2/3, Oracle Ampere A1, RPi 4 |
| armv7l (32-bit ARM) | ⚠ Best effort | Raspberry Pi 3 (limited RAM) |

All panel code is pure Python — no compiled extensions. OpenLiteSpeed provides official ARM64 packages via the LiteSpeed repo since OLS 1.7. Pure-FTPd, MariaDB, and certbot all have ARM64 packages in standard distro repos.

---

## License

MIT
