"""Security management service (Fail2Ban wrapper)."""
import subprocess
import re
import os

def get_jails():
    """Get list of active jails."""
    try:
        output = subprocess.check_output(['sudo', 'fail2ban-client', 'status'], stderr=subprocess.STDOUT).decode()
        # Parse: |- Jail list:   sshd, lky-admin
        match = re.search(r'Jail list:\s+(.*)', output)
        if match:
            return [j.strip() for j in match.group(1).split(',')]
    except Exception:
        pass
    return []

def get_jail_status(jail_name):
    """Get detailed status for a specific jail."""
    status = {'currently_failed': 0, 'total_failed': 0, 'currently_banned': 0, 'total_banned': 0, 'banned_ips': []}
    try:
        output = subprocess.check_output(['sudo', 'fail2ban-client', 'status', jail_name], stderr=subprocess.STDOUT).decode()
        
        failed_match = re.search(r'Currently failed:\s+(\d+)', output)
        total_f_match = re.search(r'Total failed:\s+(\d+)', output)
        banned_match = re.search(r'Currently banned:\s+(\d+)', output)
        total_b_match = re.search(r'Total banned:\s+(\d+)', output)
        ips_match = re.search(r'Banned IP list:\s+(.*)', output)
        
        if failed_match: status['currently_failed'] = int(failed_match.group(1))
        if total_f_match: status['total_failed'] = int(total_f_match.group(1))
        if banned_match: status['currently_banned'] = int(banned_match.group(1))
        if total_b_match: status['total_banned'] = int(total_b_match.group(1))
        if ips_match: status['banned_ips'] = [ip.strip() for ip in ips_match.group(1).split() if ip.strip()]
        
    except Exception:
        pass
    return status

def ban_ip(jail, ip):
    """Ban an IP in a specific jail."""
    try:
        subprocess.run(['sudo', 'fail2ban-client', 'set', jail, 'banip', ip], check=True, capture_output=True)
        return True, f"IP {ip} banned in {jail}."
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode()

def unban_ip(jail, ip):
    """Unban an IP from a specific jail."""
    try:
        subprocess.run(['sudo', 'fail2ban-client', 'set', jail, 'unbanip', ip], check=True, capture_output=True)
        return True, f"IP {ip} unbanned from {jail}."
    except subprocess.CalledProcessError as e:
        return False, e.stderr.decode()

def get_logs(lines=50):
    """Read the Fail2Ban log file."""
    log_path = '/var/log/fail2ban.log'
    if not os.path.exists(log_path):
        return ["Fail2Ban log not found."]
    try:
        output = subprocess.check_output(['sudo', 'tail', '-n', str(lines), log_path]).decode()
        return output.splitlines()
    except Exception as e:
        return [f"Error reading logs: {e}"]
