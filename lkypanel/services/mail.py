"""
SnappyMail installation service.
"""
import os
import subprocess
import shutil
import logging
import requests

logger = logging.getLogger(__name__)

SNAPPYMAIL_URL = "https://github.com/the-djmaze/snappymail/releases/download/v2.38.2/snappymail-2.38.2.tar.gz"
INSTALL_PATH = "/usr/local/lkypanel/webmail"

def install_snappymail():
    """
    Download and install SnappyMail to the panel's webmail directory.
    """
    try:
        # Create directory if not exists
        if not os.path.exists(INSTALL_PATH):
            subprocess.run(['sudo', 'mkdir', '-p', INSTALL_PATH], check=True)
            
        # Download
        tar_path = "/tmp/snappymail.tar.gz"
        r = requests.get(SNAPPYMAIL_URL, stream=True)
        with open(tar_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
        # Extract using sudo to preserve permissions
        subprocess.run(['sudo', 'tar', '-xzf', tar_path, '-C', INSTALL_PATH], check=True)
        
        # Set permissions for OLS user (usually nobody/nogroup or lsws user)
        # On Ubuntu, OLS runs as 'nobody:nogroup' by default for some configurations, 
        # but let's check what's best. Usually OLS needs read/write access to 'data' dir.
        subprocess.run(['sudo', 'chown', '-R', 'nobody:nogroup', INSTALL_PATH], check=True)
        subprocess.run(['sudo', 'chmod', '-R', '755', INSTALL_PATH], check=True)
        
        # Ensure 'data' dir is writable
        data_dir = os.path.join(INSTALL_PATH, 'data')
        if os.path.exists(data_dir):
            subprocess.run(['sudo', 'chmod', '-R', '777', data_dir], check=True)
            
        logger.info(f"SnappyMail installed successfully to {INSTALL_PATH}")
        return True
    except Exception as e:
        logger.error(f"Failed to install SnappyMail: {e}")
        return False

def get_webmail_url():
    """
    Return the URL to access webmail.
    """
    # Assuming OLS is proxying /webmail/ to this directory on the main port or internal tools port
    return "/webmail/"
