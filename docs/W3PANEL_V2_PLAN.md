# W3Panel v2 — Foundation-First Architecture

## Overview

W3Panel v2 is a **container-native hosting panel** with a licensing system, plugin architecture, and one-shot wizards. Built on a clean foundation in a new folder (`w3panel-v2/`), following OpenPanel's monorepo structure patterns.

---

## Architecture (cPanel-style)

```
┌──────────────────────────────────────────────────────────┐
│                    LICENSE LAYER                          │
│  license.lkylab.com → validates → middleware enforces     │
├──────────────────────────────────────────────────────────┤
│                    PANEL LAYER                            │
│  Admin (port 2087) │ User (port 2083) │ API (port 2080)  │
├──────────────────────────────────────────────────────────┤
│                    PLUGIN LAYER                           │
│  Systemd plugins │ Container plugins │ Hybrid plugins    │
├──────────────────────────────────────────────────────────┤
│                    SERVICE LAYER                          │
│  Podman │ Wizards │ Monitoring │ Backups                 │
└──────────────────────────────────────────────────────────┘
```

---

## Project Structure (OpenPanel Pattern)

```
w3panel-v2/
├── apps/                          # Django apps
│   ├── admin/                     # Admin panel (port 2087)
│   ├── user/                      # User panel (port 2083)
│   └── api/                       # REST API (port 2080)
├── packages/                      # Shared packages
│   ├── core/                      # Models, middleware, auth
│   ├── license/                   # License system
│   ├── plugins/                   # Plugin manager
│   └── ui/                        # Shared templates, CSS
├── services/                      # External services
│   ├── podman/                    # Container management
│   └── wizards/                   # One-shot wizards
├── self-hosting/                  # Deployment configs
│   ├── systemd/                   # Service files
│   └── install.sh                 # Installer
├── docs/
│   ├── ui-refs/                   # UI references (PDFs, screenshots)
│   ├── api/                       # API documentation
│   └── W3PANEL_V2_PLAN.md         # This file
└── LICENSE                        # AGPL-3.0
```

---

## Licensing Model (Open Core)

### Tier Structure

| Tier | Price | Websites | Databases | Features |
|------|-------|----------|-----------|----------|
| **Free** | $0 | 1 | 1 | Basic management only |
| **Solo** | ~$15/mo | 5 | 5 | + Email, SSL, Backups |
| **Admin** | ~$25/mo | 25 | 25 | + Wizards, Containers, Firewall, API |
| **Pro** | ~$45/mo | 100 | 100 | + Monitoring, White-label |
| **Enterprise** | ~$75/mo | Unlimited | Unlimited | + Custom branding, SLA |

### Feature Matrix

| Feature | Free | Solo | Admin | Pro | Enterprise |
|---------|------|------|-------|-----|------------|
| Users | ✅ | ✅ | ✅ | ✅ | ✅ |
| Website CRUD | ✅ (1) | ✅ (5) | ✅ (25) | ✅ (100) | ✅ ∞ |
| Databases | ✅ (1) | ✅ (5) | ✅ (25) | ✅ (100) | ✅ ∞ |
| FTP | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cron | ✅ | ✅ | ✅ | ✅ | ✅ |
| File Manager | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Email** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **SSL** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Backups** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Wizards** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Containers** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Firewall** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **REST API** | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Monitoring** | ❌ | ❌ | ❌ | ✅ | ✅ |
| **White-label** | ❌ | ❌ | ❌ | ✅ | ✅ |
| **Custom Branding** | ❌ | ❌ | ❌ | ❌ | ✅ |

### License Server API Contract

**Endpoint:** `POST https://license.lkylab.com/api/validate`

**Request:**
```json
{
  "license_key": "W3P-XXXX-XXXX-XXXX",
  "server_fingerprint": "sha256:abc123...",
  "panel_version": "2.0.0",
  "action": "validate"
}
```

**Response (valid):**
```json
{
  "valid": true,
  "tier": "admin",
  "expires_at": "2026-12-31T00:00:00Z",
  "limits": {
    "websites": 25,
    "databases": -1,
    "email": -1,
    "ftp": -1
  },
  "features": [
    "wizards", "containers", "firewall", "api",
    "email", "ssl", "backups", "monitoring"
  ]
}
```

**Response (invalid):**
```json
{
  "valid": false,
  "error": "License expired",
  "code": "LICENSE_EXPIRED"
}
```

### License Enforcement

- **Middleware:** `LicenseEnforcementMiddleware` checks cached license on every request
- **Cache:** License status cached in `/etc/w3panel/license.json` + `/run/w3panel/license_status`
- **Validation:** APScheduler job validates every 6 hours
- **Grace period:** Expired license → 7-day read-only mode → full lockout

---

## Plugin System

### Plugin Type Resolution

```python
def get_plugin_type(plugin_id: str) -> str:
    """
    Resolution order:
    1. Plugin meta.json "type" field (forced: "host" or "container")
    2. Panel global default (SystemSetting: plugin_install_type)
    3. User override at install time
    """
    meta = load_plugin_meta(plugin_id)
    
    # 1. Forced type
    if meta.type in ('host', 'container'):
        return meta.type
    
    # 2. Panel default
    default = SystemSetting.get('plugin_install_type', 'container')
    
    # 3. User override
    state = PluginState.get(plugin_id)
    if state.preferred_type:
        return state.preferred_type
    
    return default
```

### Plugin meta.json Format

```json
{
  "name": "MariaDB",
  "description": "MySQL-compatible database server",
  "version": "11.4",
  "type": "auto",
  "category": "database",
  "dependencies": [],
  "conflicts": ["postgresql"],
  "provides": ["database", "mysql"],
  "system_packages": {
    "apt": ["mariadb-server", "mariadb-client"],
    "yum": ["mariadb-server", "mariadb-client"]
  },
  "service": "mariadb",
  "container": {
    "image": "docker.io/library/mariadb:11.4",
    "ports": {"3306": "3306"},
    "volumes": {"mariadb-data": "/var/lib/mysql"},
    "env": {"MYSQL_ROOT_PASSWORD_FILE": "/run/secrets/mysql_root"},
    "healthcheck": ["mysqladmin", "ping", "-h", "localhost"]
  },
  "firewall_ports": [3306]
}
```

### Plugin Categories

| Category | Plugins | Default Type |
|----------|---------|--------------|
| Database | MariaDB, PostgreSQL, MongoDB | container |
| Web Server | Nginx, Apache2, OpenLiteSpeed | container |
| Cache | Redis | container |
| Mail | Postfix, Dovecot, SnappyMail | host (shared) |
| DNS | PowerDNS | host (shared) |
| Security | fail2ban, UFW/CSF | host |
| Tools | phpMyAdmin, phpPgAdmin, Supervisor | host |
| Backup | Restic | host |

---

## API Framework

### Endpoint Structure

```
/api/v1/                    # API root
/api/v1/auth/               # Token management
/api/v1/websites/           # Website CRUD
/api/v1/databases/          # Database CRUD
/api/v1/email/              # Email management
/api/v1/containers/         # Container management
/api/v1/wizards/            # Wizard execution
/api/v1/stats/              # Monitoring
```

### Rate Limiting (Configurable)

| Setting | Default | Description |
|---------|---------|-------------|
| `api_rate_limit` | 50 | Requests per minute per token |
| `api_rate_limit_burst` | 100 | Burst allowance |

Configurable in admin settings page.

### API Access Control

- **Free tier:** API access blocked
- **Paid tiers:** API access enabled
- **Enforcement:** `@require_license('api')` decorator on all API views

---

## Service Layer

### Container Service

```python
class PodmanManager:
    """Manages Podman containers for user pods."""
    
    def create_user_pod(self, user_id: int, config: dict) -> Pod:
        """Create a pod with web + PHP + DB + webmail."""
        
    def destroy_user_pod(self, user_id: int) -> bool:
        """Destroy user's pod and all containers."""
        
    def get_pod_status(self, user_id: int) -> PodStatus:
        """Get pod health and resource usage."""
```

### Wizard Service

```python
class WizardBase(ABC):
    """Base class for all one-shot wizards."""
    
    @abstractmethod
    def define_steps(self) -> list[WizardStep]:
        """Define wizard steps."""
        
    def run(self) -> WizardProgress:
        """Execute wizard with automatic rollback."""
        
    def cancel(self) -> bool:
        """Cancel running wizard."""
```

---

## Implementation Phases

### Phase 1: Foundation Setup (Day 1-2)
| Task | Details |
|------|---------|
| Create `w3panel-v2/` folder | Clean slate, no legacy code |
| Setup monorepo structure | `apps/` + `packages/` pattern |
| Create shared `core` package | Models, middleware, auth |
| Create `license` package | License model, validation, feature gates |
| Create `plugins` package | Plugin manager with type resolution |
| Setup Django apps | Admin, User, API as separate apps |

### Phase 2: License System (Day 2-4)
| Task | Details |
|------|---------|
| License model | `License`, `LicenseFeature` models |
| License service | Online validation + local cache |
| License middleware | Check license on premium features |
| Feature gate decorator | `@require_license('feature')` |
| Admin license page | Activate, view status |
| License-based limits | Update `check_limit()` to use tiers |

### Phase 3: Plugin System (Day 3-5)
| Task | Details |
|------|---------|
| Plugin manager | Type resolution logic |
| Plugin state | JSON file management |
| Update 17 plugins | Add new meta.json format |
| Create `podman` plugin | Install Podman runtime |
| Create 5 container examples | MariaDB, PostgreSQL, Redis, Nginx, SnappyMail |

### Phase 4: API Framework (Day 4-6)
| Task | Details |
|------|---------|
| User-facing API | `@login_required` endpoints |
| Email API | `/api/v1/email/domains/`, `/api/v1/email/accounts/` |
| Container API | `/api/v1/containers/`, `/api/v1/pods/` |
| Monitoring API | `/api/v1/stats/`, `/api/v1/logs/` |
| Async wizards | Background thread execution |
| Rate limit config | Configurable per-user limits |
| API docs | Auto-generate OpenAPI spec |

### Phase 5: Service Layer (Day 5-7)
| Task | Details |
|------|---------|
| Container service | `PodmanManager` with pod lifecycle |
| Port allocator | Thread-safe port allocation |
| Wizard base class | `WizardBase` with SSE progress |
| Website wizard | Host + container mode |
| Email wizard | Postfix + Dovecot + DKIM |
| Database wizard | MariaDB + PostgreSQL |
| Framework wizard | WordPress, Laravel, Django, Node.js |
| Service wizard | Wraps all plugins |

### Phase 6: UI (Day 6-8)
| Task | Details |
|------|---------|
| Admin dashboard | Site overview, quick actions |
| User dashboard | Site management, getting started |
| Wizard pages | Admin + user wizard UI |
| License page | Activate, view status |
| Settings page | Plugin type, API rate limit |
| Responsive design | Mobile-friendly |

### Phase 7: Deployment (Day 7-9)
| Task | Details |
|------|---------|
| Install script | Fresh install with Podman |
| Uninstall script | Clean removal |
| Upgrade script | Migration from v1 |
| Systemd services | Admin, User, API services |
| CLI tool | `w3panel` command |

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| License server | `license.lkylab.com` | Existing infrastructure |
| License enforcement | Middleware + APScheduler | No new daemon needed |
| Plugin default | `container` | v2 is container-native |
| API access | Paid only | Premium feature |
| API rate limit | 50 req/min | Configurable, not excessive |
| Wizard access | Admin + User | Users create websites |
| Container runtime | Podman | Rootless, daemonless |
| Per-user isolation | Full pods | Maximum security |
| State management | JSON files | Simple, no DB overhead |
| Rollback | Automatic | Created resources tracked |

---

## UI References

Place UI references (PDFs, screenshots) in `docs/ui-refs/`:
- Admin dashboard screenshots
- User dashboard screenshots
- Wizard flow diagrams
- cPanel/HestiaCP comparison screenshots
- Mobile responsive mockups

---

## License Server (license.lkylab.com)

**To be built later.** API contract defined above.

**Implementation:**
- Simple Node.js/Python server
- PostgreSQL database for license keys
- Stripe integration for payments
- Admin dashboard for license management

---

## Next Steps

1. **Create `w3panel-v2/` folder** with monorepo structure
2. **Add UI references** in `docs/ui-refs/`
3. **Build foundation** starting with License + Plugin packages
4. **License server** — define API contract, build server later
5. **Iterate** through implementation phases

---

## Comparison with cPanel

| Feature | cPanel | W3Panel v2 |
|---------|--------|------------|
| License model | Per-server | Per-server (similar) |
| Pricing | $29.99-$69.99/mo | $0-$75/mo |
| Container support | ❌ (VM only) | ✅ (Podman pods) |
| One-shot wizards | ❌ | ✅ |
| API access | ✅ | ✅ (paid only) |
| Self-hosted | ✅ | ✅ |
| Open source | ❌ | ✅ (AGPL-3.0) |

---

*Last updated: 2026-08-16*
*Status: Planning*
