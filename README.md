# W3Panel v2

Container-native hosting control panel with Podman-based per-user isolation.

## Features

- **Per-user isolation**: Full pods (web server + PHP-FPM + MariaDB/PostgreSQL per user)
- **Plugin system**: Install web servers and databases as plugins (OpenLiteSpeed, MariaDB)
- **Licensing**: Open core model (Free → Solo → Admin → Pro → Enterprise)
- **One-shot wizards**: Email, Database, Website, Framework, Service setup
- **Modern UI**: Light theme with blue accents, card-based layout

## Quick Install

```bash
# From GitHub
bash <(curl -fsSL https://raw.githubusercontent.com/lkylab/W3Panel/main/install.sh)

# From local clone
git clone https://github.com/lkylab/W3Panel.git
cd W3Panel/w3panel-v2
sudo bash install.sh
```

## Default Credentials

- **Username**: `admin`
- **Password**: `123`

## Ports

- **2087**: Admin Panel (HTTPS)
- **2083**: User Panel (HTTPS)
- **2080**: API (HTTPS)

## Development

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create admin user
python manage.py shell -c "
from packages.core.models import User
User.objects.create_user('admin', 'admin@localhost', '123', role='admin')
"

# Start dev server
python manage.py runserver 0.0.0.0:8000
```

## License Tiers

| Feature | Free | Solo | Admin | Pro | Enterprise |
|---------|------|------|-------|-----|------------|
| Websites | 1 | 5 | 25 | 100 | Unlimited |
| Databases | 1 | 5 | 25 | 100 | Unlimited |
| Email | — | ✓ | ✓ | ✓ | ✓ |
| SSL | — | ✓ | ✓ | ✓ | ✓ |
| Backups | — | ✓ | ✓ | ✓ | ✓ |
| Wizards | — | — | ✓ | ✓ | ✓ |
| Containers | — | — | ✓ | ✓ | ✓ |
| API Access | — | — | ✓ | ✓ | ✓ |
| Monitoring | — | — | — | ✓ | ✓ |
| White Label | — | — | — | ✓ | ✓ |

## Project Structure

```
w3panel-v2/
├── apps/
│   ├── admin/          # Admin views and URLs
│   ├── api/            # REST API endpoints
│   └── user/           # User views and URLs
├── packages/
│   ├── core/           # Models, middleware, auth
│   ├── license/        # License system
│   └── plugins/        # Plugin manager
├── panel/              # Django settings and URLs
├── static/             # CSS, JS, images
├── templates/          # HTML templates
├── manage.py           # Django management
├── install.sh          # Installer script
├── uninstall.sh        # Uninstaller script
└── requirements.txt    # Python dependencies
```