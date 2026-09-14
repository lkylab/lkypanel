# W3Panel v2 — Testing Guide

## Quick Test (Local Development)

### 1. Start the dev server

```bash
cd /home/lky/Documents/Projects/W3Panel/w3panel-v2
source venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

### 2. Access the panel

- **Admin Panel**: http://localhost:8000/login/
- **User Panel**: http://localhost:8000/user/login/

### 3. Login credentials

- **Username**: `admin`
- **Password**: `123`

---

## Full Test (VM Deployment)

### Option A: Install on VM via SSH

```bash
ssh -o StrictHostKeyChecking=no -p 2222 lky@localhost "echo '123' | sudo -S bash -c '
  export TOKEN="<YOUR_GITHUB_PAT>"
  cd /tmp
  rm -rf W3Panel
  git clone -b v2 \"https://x-access-token:\$TOKEN@github.com/lkylab/W3Panel.git\"
  cd W3Panel/w3panel-v2
  bash install.sh
'"
```

### Option B: Test on local VM

```bash
# SSH into VM
ssh -p 2222 lky@localhost

# Clone and install
cd /tmp
git clone -b v2 https://github.com/lkylab/W3Panel.git
cd W3Panel/w3panel-v2
sudo bash install.sh
```

### Access after install

- **Admin Panel**: `https://<vm-ip>:2087`
- **User Panel**: `https://<vm-ip>:2083`
- **Login**: `admin` / `123`

---

## Test Checklist

### Admin Panel (port 2087)

- [ ] Login page loads
- [ ] Dashboard shows stats (Users, Websites, Databases, Plugins)
- [ ] System metrics display (CPU, RAM, Disk, Load)
- [ ] Activity log shows recent actions
- [ ] System info displays versions
- [ ] Quick actions work (Create Website, Add User, etc.)
- [ ] Users page lists all users
- [ ] Create user form works
- [ ] Websites page lists all websites
- [ ] Create website form works
- [ ] Plugins page shows available plugins
- [ ] License page shows current tier
- [ ] License activation form works
- [ ] Settings page loads

### User Panel (port 2083)

- [ ] Login page loads
- [ ] Dashboard shows grouped sections
- [ ] Usage bars display correctly
- [ ] Websites section shows user's sites
- [ ] Databases section shows user's databases
- [ ] Quick links work

### API (port 2080)

- [ ] License status endpoint: `GET /api/v1/license/status/`
- [ ] License activate endpoint: `POST /api/v1/license/activate/`
- [ ] Website list endpoint: `GET /api/v1/websites/` (requires API token)
- [ ] Website create endpoint: `POST /api/v1/websites/` (requires API token)

---

## API Testing

### Get license status

```bash
curl -k https://localhost:2080/api/v1/license/status/
```

### Activate license

```bash
curl -k -X POST https://localhost:2080/api/v1/license/activate/ \
  -H "Content-Type: application/json" \
  -d '{"license_key": "W3P-TEST-XXXX-XXXX"}'
```

### List websites (requires API token)

```bash
curl -k https://localhost:2080/api/v1/websites/ \
  -H "Authorization: Bearer <your-api-token>"
```

---

## Troubleshooting

### Server won't start

```bash
# Check logs
sudo journalctl -u w3panel-admin -f
sudo journalctl -u w3panel-user -f

# Check if ports are in use
sudo ss -tuln | grep -E ':(2083|2087|2080)'

# Restart services
sudo systemctl restart w3panel-admin w3panel-user
```

### Database errors

```bash
# Re-run migrations
cd /usr/local/w3panel
source venv/bin/activate
python manage.py migrate
```

### Permission errors

```bash
# Fix ownership
sudo chown -R w3panel:w3panel /usr/local/w3panel
sudo chown -R w3panel:w3panel /etc/w3panel
sudo chown -R w3panel:w3panel /var/lib/w3panel
sudo chown -R w3panel:w3panel /var/log/w3panel
```

---

## Uninstall

```bash
sudo bash /usr/local/w3panel/uninstall.sh
```

Or from the cloned repo:

```bash
cd /home/lky/Documents/Projects/W3Panel/w3panel-v2
sudo bash uninstall.sh
```