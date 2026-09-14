# W3Panel v2 — Progress & Feature Status

**Last Updated:** 2026-08-22  
**Architecture:** Lightweight, Container-Native / Host-Modular Django Monorepo  
**VM Endpoints:**
* **Admin Panel:** `https://localhost:12087/` (guest `2087`)
* **User Panel:** `https://localhost:12083/` (guest `2083`)
* **Default Admin:** `admin` / `123`
* **Test Client User:** `client1` / `123`

---

## 1. Core Architecture & Lightweight Design
* **Zero Initial Service Overhead:** `install.sh` provisions only the minimal panel runtime (~80MB RAM). Zero heavy hosting services (Nginx, MariaDB, Postfix, Dovecot, SnappyMail) are pre-forced.
* **On-Demand Package Management:** All engines (Nginx, MariaDB, PHP-FPM, Postfix, Dovecot, OpenDKIM, SnappyMail, Redis, UFW, Pure-FTPd) are installed, uninstalled, started, stopped, and restarted individually with 1-click from **Admin $\rightarrow$ Services** (`/services/`).
* **Non-Blocking Error Boundaries:** If a feature is used before its underlying daemon is installed, the panel displays a friendly banner guiding the user to the Services page instead of throwing errors.

---

## 2. Completed Milestones

### Phase 1: Full Monorepo Backend & Django Apps
* `packages/core`: Auth, User/Package models, Middleware (Port isolation, Role enforcement, CSRF trusted origins)
* `packages/license`: Open-core tier management
* `packages/plugins`: Dual host/container lifecycle manager
* `apps/admin`: 27 Administration routes and views
* `apps/user`: 12 User portal routes and views
* `apps/api`: REST API v1 suite with Bearer token authentication

### Phase 2: Complete Frontend Design System
* Modern Tailwind CSS + Alpine.js + Tabler Icons across all 39 templates
* Live navbar system resource monitors (CPU, RAM, Disk, Load averages)
* Web File Manager with in-browser dark code editor, multi-file upload, and jail protection

### Phase 3: Hosting Engine Services (`services/`)
* **Web Server (`services/webserver/`):** Auto-generates Nginx VHosts, provisions document roots, configures PHP-FPM fastcgi proxying, and reloads Nginx dynamically.
* **Database Engine (`services/database/`):** Executes real SQL for MariaDB / MySQL and PostgreSQL, creates users with random secure passwords, and drops databases on delete.
* **SSL Manager (`services/ssl/`):** Certbot Let's Encrypt automated HTTP-01 issuance with 2048-bit RSA self-signed certificates with SANs for testing.
* **Mail Stack (`services/mail/`):** Postfix virtual mailboxes, Dovecot Maildir provisioning, OpenDKIM RSA key generation, and automatic DNS TXT record publishing.
* **Webmail (`services/mail/`):** SnappyMail Webmail Suite integration with 1-click launcher in User Email Accounts.
* **FTP (`services/ftp/`):** Pure-FTPd virtual user management and database compilation (`pure-pw mkdb`).
* **Cron (`services/cron/`):** User scheduled tasks synced directly to `/etc/cron.d/w3panel_<username>`.
* **Backups (`services/backup/`):** Automated database dumps and `.tar.gz` archive snapshots in `/var/lib/w3panel/backups/`.
* **DNS (`services/dns/`):** RFC 1035 zone file exporter for BIND / PowerDNS in `/var/lib/w3panel/dns/zones/`.
* **1-Click WordPress Wizard (`services/wizards/`):** Full installer downloading WordPress, provisioning database, setting up `wp-config.php`, and configuring Nginx permalinks.

---

### Phase 4: User Management, Admin Impersonation & Web Terminals
* **Admin Impersonation ("Login as User"):**
  * One-click SSO authentication allows administrators to log in to the User Portal as any tenant without knowing or changing their password.
  * Cross-port security handled via time-limited one-time tokens (`LoginToken` model, 120s TTL) bridging port 2087 (Admin) to port 2083 (User).
  * Prominent Amber top-banner with tenant context and 1-click "Exit Impersonation" return link.
* **User Modification & Password Reset:**
  * Admin user editor (`/users/<id>/edit/`) for updating email, package plan, access role, active/suspended status, and shell permissions.
  * Instant password resets synced with underlying Linux POSIX accounts (`chpasswd`).
  * Built-in secure 16-character password generator on both account creation and edit views.
* **Linux Shell & Terminal Access Control:**
  * Per-user toggle for SSH / Web Terminal permissions (`shell_enabled`).
  * Real Linux OS enforcement: sets login shell to `/bin/bash` when enabled, `/bin/false` (jailed) when disabled.
  * Account suspension actively locks POSIX user (`usermod -L`) and unlocks on activation (`usermod -U`).
* **Interactive Web Terminals:**
  * **Admin Terminal (`/terminal/`):** Root-level diagnostic console with quick system shortcuts (`uptime`, `free -m`, `df -h`, `nginx status`, `w3panel status`, `listening ports`, `nginx error log`).
  * **User Terminal (`/user/terminal/`):** Strictly sandboxed web console running commands as the isolated Linux tenant user (`sudo -n -u {username}`) jailed in `/var/lib/w3panel/users/{username}`.
  * Alpine.js xterm-style UI with history traversal, command shortcuts, safety filters, and execution output scrolling.

---

## 3. Automated Test Suite (`tests/`)
* **26 Unit & Integration Tests:**
  * Authentication, session validation, brute-force lockout
  * Admin impersonation & SSO token flow validation
  * Admin user editing, password reset & POSIX sync
  * User status and shell permission toggling
  * Admin & User Web Terminal execution and safety filters
  * VirtualHost generator & removal with defense-in-depth security headers & static caching
  * Per-site Reverse Proxy Real-IP toggle & scoped CIDR injection (User Panel)
  * Dedicated per-tenant PHP-FPM pool generation & open_basedir jailing
  * OS & Kernel Tuning (`sysctl`, 1M limits, OPcache JIT tracing)
  * Native Systemd Daemon Supervisor for Node.js (0 idle RAM bloat, auto-restart, resource limits)
  * Production Laravel Application Deployment Wizard (.env, APP_KEY, storage permissions, /public vhost)
  * Atomic Zero-Downtime Releases Engine with atomic symlink swapping & instant rollback
  * High-performance low-memory MariaDB engine tuning (skip-name-resolve, performance_schema=OFF, 128M buffer pool)
  * Database provisioning & secure password generation
  * SSL certificate issuance
  * DNS RFC 1035 zone export
  * WordPress config generation
  * REST API CRUD operations & unauthorized request handling
* **Result:** **100% OK (26 / 26 passing in local suite & live Ubuntu 24.04 VM)**

---

## 4. Production High-Performance & Security Highlights
1. **Zero Daemon Bloat:** Native Systemd process units (`/etc/systemd/system/w3panel-app-*.service`) replace heavy supervisors like PM2, saving ~60-80MB RAM per tenant while preserving auto-restart, resource quotas (`MemoryMax=512M`), and journald logging.
2. **Nginx Defense-in-Depth & Static Caching:** Security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`), 404 denial for sensitive config files (`.env`, `.git`, `composer.json`), and 30-day static asset cache without access logging to minimize disk I/O.
3. **Tenant Socket Isolation:** Each website owner runs on their isolated UNIX socket (`/run/php/php8.3-fpm-<username>.sock`), restricted by tenant user UID and isolated session/tmp directories.
4. **Per-Site Scoped Real-IP:** Direct-traffic sites never trust forwarded headers, preventing header spoofing; Cloudflare/proxy sites restore client IPs with 1 click in the User Panel.
5. **Atomic Releases:** Atomic symlink switching (`current` -> `releases/<timestamp>`) guarantees zero downtime during code updates and enables instantaneous rollbacks.
6. **MariaDB Low-Memory Tuning:** Adding `skip-name-resolve = 1` eliminates connection DNS latency, and `performance_schema = OFF` frees 100MB+ RAM.
7. **POSIX Tenant Jailing & Shell Control:** Disabling terminal permissions sets the system user's login shell to `/bin/false` and locks the account on suspension. Interactive commands are always executed strictly under tenant UID credentials without elevating privileges.


