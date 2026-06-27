"""
Framework installation service.
"""
import os
import subprocess
import shutil
import logging

logger = logging.getLogger(__name__)

def install_framework(website, framework):
    """
    Dispatcher for framework installers.
    """
    if framework == 'wordpress':
        return install_wordpress(website)
    elif framework == 'laravel':
        return install_laravel(website)
    elif framework == 'nodejs':
        return install_nodejs(website)
    elif framework == 'static':
        return install_static(website)
    return True

def install_wordpress(website):
    """
    Install WordPress using wp-cli.
    """
    domain = website.domain
    path = website.doc_root
    
    try:
        # Check if wp-cli exists
        if shutil.which('wp') is None:
            logger.error("wp-cli not found. Skipping WordPress installation.")
            return False
            
        # Download WP
        subprocess.run(['wp', 'core', 'download', f'--path={path}', '--allow-root'], check=True)
        
        # We don't configure wp-config here as we need DB info, 
        # which will be handled in the view/manager that calls this.
        logger.info(f"WordPress core downloaded to {path} for {domain}")
        return True
    except Exception as e:
        logger.error(f"Failed to install WordPress for {domain}: {e}")
        return False

def install_laravel(website):
    """
    Install Laravel using composer.
    """
    domain = website.domain
    path = website.doc_root
    
    try:
        if shutil.which('composer') is None:
            logger.error("composer not found. Skipping Laravel installation.")
            return False
            
        # Laravel needs to be installed in a clean dir, but doc_root might have index.php from OLS
        # We'll install in a temp dir then move or just clear doc_root
        for f in os.listdir(path):
            file_path = os.path.join(path, f)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
                
        subprocess.run(['composer', 'create-project', 'laravel/laravel', '.', '--working-dir=' + path], check=True)
        logger.info(f"Laravel installed to {path} for {domain}")
        return True
    except Exception as e:
        logger.error(f"Failed to install Laravel for {domain}: {e}")
        return False

def install_nodejs(website):
    """
    Initialize a basic Node.js structure.
    """
    domain = website.domain
    path = website.doc_root
    
    try:
        # Create package.json
        package_json = {
            "name": domain.replace('.', '-'),
            "version": "1.0.0",
            "description": f"Node.js app for {domain}",
            "main": "app.js",
            "scripts": {
                "start": "node app.js"
            },
            "dependencies": {
                "express": "^4.18.2"
            }
        }
        import json
        with open(os.path.join(path, 'package.json'), 'w') as f:
            json.dump(package_json, f, indent=4)
            
        # Create app.js
        app_js = """const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.get('/', (req, res) => {
  res.send('<h1>Hello from Node.js on LkyPanel!</h1>');
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});
"""
        with open(os.path.join(path, 'app.js'), 'w') as f:
            f.write(app_js)
            
        logger.info(f"Node.js skeleton created at {path} for {domain}")
        return True
    except Exception as e:
        logger.error(f"Failed to setup Node.js for {domain}: {e}")
        return False

def install_static(website):
    """
    Deploy a premium static template.
    """
    domain = website.domain
    path = website.doc_root
    
    try:
        index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{domain} — Coming Soon</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
        .container {{ text-align: center; border: 1px solid rgba(255,255,255,0.1); padding: 3rem; border-radius: 20px; background: rgba(255,255,255,0.02); backdrop-filter: blur(10px); }}
        h1 {{ color: #38bdf8; font-size: 2.5rem; margin-bottom: 0.5rem; }}
        p {{ color: #94a3b8; font-size: 1.1rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{domain}</h1>
        <p>This website is being built with <strong>LkyPanel</strong>.</p>
    </div>
</body>
</html>
"""
        with open(os.path.join(path, 'index.html'), 'w') as f:
            f.write(index_html)
        return True
    except Exception as e:
        logger.error(f"Failed to install static template for {domain}: {e}")
        return False
