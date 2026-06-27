"""Firewall management service (UFW wrapper)."""
import subprocess
import re

def get_ufw_status():
    """Check if UFW is active."""
    try:
        output = subprocess.check_output(['sudo', 'ufw', 'status'], stderr=subprocess.STDOUT).decode()
        return "active" in output.lower()
    except Exception:
        return False

def get_rules():
    """Parse ufw status numbered and return a list of rules."""
    rules = []
    try:
        output = subprocess.check_output(['sudo', 'ufw', 'status', 'numbered'], stderr=subprocess.STDOUT).decode()
        # Regex to parse: [ 1] 2087/tcp                   ALLOW IN    Anywhere
        # Or: [ 2] 80/tcp                     ALLOW IN    1.2.3.4
        pattern = re.compile(r'\[\s*(\d+)\]\s+([\d\w/]+)\s+(ALLOW|DENY) IN\s+(.*)')
        
        for line in output.splitlines():
            match = pattern.search(line)
            if match:
                rules.append({
                    'index': match.group(1),
                    'to': match.group(2),
                    'action': match.group(3),
                    'from': match.group(4).strip()
                })
    except Exception as e:
        print(f"Error getting firewall rules: {e}")
    return rules

def add_rule(port, proto='tcp', from_ip='Anywhere', action='allow'):
    """Add a UFW rule."""
    try:
        cmd = ['sudo', 'ufw', action]
        if from_ip and from_ip.lower() != 'anywhere':
            cmd += ['from', from_ip, 'to', 'any', 'port', str(port)]
        else:
            cmd += [f"{port}/{proto}"]
            
        subprocess.run(cmd, check=True, capture_output=True)
        return True, "Rule added successfully."
    except subprocess.CalledProcessError as e:
        return False, f"Failed to add rule: {e.stderr.decode()}"

def delete_rule(index):
    """Delete a UFW rule by index."""
    try:
        # Use --force to avoid interactive prompt
        subprocess.run(['sudo', 'ufw', '--force', 'delete', str(index)], check=True, capture_output=True)
        return True, "Rule deleted successfully."
    except subprocess.CalledProcessError as e:
        return False, f"Failed to delete rule: {e.stderr.decode()}"
