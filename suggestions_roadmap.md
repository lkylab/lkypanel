# LkyPanel: Suggested Features & Roadmap

Based on the current implementation of `lkypanel`, here is a comprehensive list of suggestions for new features and updates to bridge the gap with professional hosting panels.

## 1. System & Monitoring [PRIORITY]
- **Real-Time Dashboard**: Visual charts for CPU, RAM, Disk I/O, and Network traffic (using `psutil` or Netdata integration).
- **In-house Alerts & Notifications**: Panel alerts for failures and issues like disk full percentage, service outages, etc.
- **Service Status Manager**: A UI to check, restart, or stop system services (OLS, MariaDB, Postfix, etc.).
- **Log Viewer Improvements**: Categorized logs (OLS Access/Error, Mail, System) with search/filter capabilities.

## 2. Advanced Web Management [PRIORITY]
- **Framework Selection on Site Creation**: Support for WordPress, Laravel, Node.js, and more during the website creation process.
- **Process Manager (Node.js/Python/Go)**: Integrated support for managing non-PHP applications using PM2 or Phusion Passenger.
- **Website Staging/Cloning**: One-click staging environment creation for testing updates before pushing to production.
- **Directory Protection**: UI for `htpasswd` protection on specific directories.

## 3. Database & Storage
- **Remote Database Access**: Manage internal/external access for MariaDB users.
- **phpMyAdmin Single Sign-On (SSO)**: Automatic login from the panel into phpMyAdmin.
- **File Manager**: A web-based file explorer for managing website files directly in the browser.

## 4. Security Enhancements
- **Two-Factor Authentication (2FA)**: [DO LATER] Support for TOTP (Google Authenticator) for panel admin/user accounts.
- **Firewall UI**: Interface for managing `UFW` or `nftables` (open/close ports, whitelist/blacklist IPs).
- **SSH Key Manager**: Manage authorized keys for the server directly from the panel.
- **Security Checkup**: A "health check" script that identifies common security misconfigurations.

## 5. Email Features
- **SnappyMail Integration**: Automated installation and SSO for webmail.
- **DNS Records Wizard**: Automated DKIM/SPF/DMARC record generation for better mail deliverability.

## 6. Developer Tools
- **Cron Job Manager**: UI for scheduling system and user-level tasks.
- **API Documentation**: Interactive documentation (Swagger/Redoc) for the existing `/api/` endpoints.

---

### Suggested Next Steps
1. **Critical Path**: Choose 1-2 items from the list above to implement first (e.g., Cron Manager or Dashboard).
2. **Refinement**: Update existing services (like [firewall.py](file:///home/lky/Documents/git%20projects/ols-manager/Panel/lkypanel/services/firewall.py)) to support more robust rules.
3. **UI/UX**: Transition the frontend to **Vite** for a dynamic, premium feel. [PRIORITY]
