"""
W3Panel v2 — Plugin Manager
Type resolution, installation, and lifecycle management.
"""
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

from .models import PluginMeta, PluginState, PLUGINS_DIR

logger = logging.getLogger('w3panel.plugins')


def get_plugin_type(plugin_id: str, user_override: str = '') -> str:
    """
    Determine plugin type (systemd vs container).
    
    Resolution order:
    1. Plugin meta.json "type" field (forced: "host" or "container")
    2. Panel global default (SystemSetting: plugin_install_type)
    3. User override at install time
    """
    from ..core.models import SystemSetting

    # Load plugin meta
    plugin_dir = PLUGINS_DIR / plugin_id
    meta_file = plugin_dir / 'meta.json'
    if not meta_file.exists():
        raise ValueError(f'Plugin {plugin_id} not found')

    meta = PluginMeta.from_file(meta_file)
    if not meta:
        raise ValueError(f'Failed to load plugin {plugin_id}')

    # 1. Forced type
    if meta.type in ('host', 'container'):
        return meta.type

    # 2. Panel global default
    default = SystemSetting.get('plugin_install_type', 'container')

    # 3. User override
    if user_override in ('host', 'container'):
        return user_override

    # 4. Check if plugin supports the default type
    if default == 'container' and not meta.supports_container:
        return 'host'
    if default == 'host' and not meta.supports_host:
        return 'container'

    return default


class PluginManager:
    """Manages plugin installation and lifecycle."""

    def __init__(self):
        self.plugins_dir = PLUGINS_DIR

    def list_plugins(self) -> list:
        """List all available plugins with their state."""
        plugins = PluginMeta.load_all()
        states = PluginState.load_all()

        result = []
        for plugin in plugins:
            state = states.get(plugin.id, PluginState(plugin_id=plugin.id))
            result.append({
                'id': plugin.id,
                'name': plugin.name,
                'description': plugin.description,
                'version': plugin.version,
                'category': plugin.category,
                'installed': state.installed,
                'installed_type': state.installed_type,
                'supports_host': plugin.supports_host,
                'supports_container': plugin.supports_container,
                'provides': plugin.provides,
                'dependencies': plugin.dependencies,
                'conflicts': plugin.conflicts,
            })

        return result

    def install(self, plugin_id: str, plugin_type: str = '') -> dict:
        """
        Install a plugin.
        
        Args:
            plugin_id: Plugin identifier
            plugin_type: 'host' or 'container' (optional, uses default if not specified)
        
        Returns:
            {'success': bool, 'error': str, 'type': str}
        """
        # Check if already installed
        state = PluginState.get(plugin_id)
        if state.installed:
            return {'success': False, 'error': 'Plugin already installed', 'type': state.installed_type}

        # Resolve type
        install_type = get_plugin_type(plugin_id, plugin_type)

        # Check dependencies
        meta = self._load_meta(plugin_id)
        if not meta:
            return {'success': False, 'error': f'Plugin {plugin_id} not found'}

        dep_check = self._check_dependencies(meta)
        if not dep_check['satisfied']:
            return {'success': False, 'error': f'Missing dependencies: {dep_check["missing"]}'}

        # Check conflicts
        conflict_check = self._check_conflicts(meta)
        if conflict_check['conflicts']:
            return {'success': False, 'error': f'Conflicting plugins: {conflict_check["conflicts"]}'}

        # Install
        try:
            if install_type == 'container':
                result = self._install_container(meta)
            else:
                result = self._install_host(meta)

            if result['success']:
                # Update state
                PluginState.set(
                    plugin_id,
                    installed=True,
                    installed_type=install_type,
                    installed_at=datetime.now().isoformat(),
                    version=meta.version,
                )
                logger.info('Installed plugin %s as %s', plugin_id, install_type)

            return result

        except Exception as e:
            logger.exception('Failed to install plugin %s', plugin_id)
            return {'success': False, 'error': str(e)}

    def uninstall(self, plugin_id: str) -> dict:
        """Uninstall a plugin."""
        state = PluginState.get(plugin_id)
        if not state.installed:
            return {'success': False, 'error': 'Plugin not installed'}

        meta = self._load_meta(plugin_id)
        if not meta:
            return {'success': False, 'error': f'Plugin {plugin_id} not found'}

        try:
            if state.installed_type == 'container':
                result = self._uninstall_container(meta)
            else:
                result = self._uninstall_host(meta)

            if result['success']:
                PluginState.set(plugin_id, installed=False, installed_type='')
                logger.info('Uninstalled plugin %s', plugin_id)

            return result

        except Exception as e:
            logger.exception('Failed to uninstall plugin %s', plugin_id)
            return {'success': False, 'error': str(e)}

    def start(self, plugin_id: str) -> dict:
        """Start a plugin's service."""
        state = PluginState.get(plugin_id)
        if not state.installed:
            return {'success': False, 'error': 'Plugin not installed'}

        meta = self._load_meta(plugin_id)
        if not meta:
            return {'success': False, 'error': f'Plugin {plugin_id} not found'}

        if state.installed_type == 'container':
            return self._start_container(meta)
        else:
            return self._start_host(meta)

    def stop(self, plugin_id: str) -> dict:
        """Stop a plugin's service."""
        state = PluginState.get(plugin_id)
        if not state.installed:
            return {'success': False, 'error': 'Plugin not installed'}

        meta = self._load_meta(plugin_id)
        if not meta:
            return {'success': False, 'error': f'Plugin {plugin_id} not found'}

        if state.installed_type == 'container':
            return self._stop_container(meta)
        else:
            return self._stop_host(meta)

    def restart(self, plugin_id: str) -> dict:
        """Restart a plugin's service."""
        stop_result = self.stop(plugin_id)
        if not stop_result['success'] and 'not running' not in stop_result.get('error', ''):
            return stop_result
        return self.start(plugin_id)

    def status(self, plugin_id: str) -> dict:
        """Get plugin status."""
        state = PluginState.get(plugin_id)
        if not state.installed:
            return {'installed': False, 'status': 'not_installed'}

        meta = self._load_meta(plugin_id)
        if not meta:
            return {'installed': False, 'status': 'error'}

        if state.installed_type == 'container':
            return self._status_container(meta)
        else:
            return self._status_host(meta)

    # ---------------------------------------------------------------------------
    # Internal: Host (systemd) operations
    # ---------------------------------------------------------------------------

    def _install_host(self, meta: PluginMeta) -> dict:
        """Install host plugin via install.sh."""
        install_script = self.plugins_dir / meta.id / meta.install_script
        if not install_script.exists():
            return {'success': False, 'error': 'Install script not found'}

        result = _run_sudo(['bash', str(install_script)])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        return {'success': True, 'type': 'host'}

    def _uninstall_host(self, meta: PluginMeta) -> dict:
        """Uninstall host plugin via remove.sh."""
        remove_script = self.plugins_dir / meta.id / meta.remove_script
        if not remove_script.exists():
            return {'success': False, 'error': 'Remove script not found'}

        result = _run_sudo(['bash', str(remove_script)])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        return {'success': True}

    def _start_host(self, meta: PluginMeta) -> dict:
        """Start host plugin service."""
        if not meta.service:
            return {'success': False, 'error': 'No service defined'}

        result = _run_sudo(['systemctl', 'start', meta.service])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        return {'success': True}

    def _stop_host(self, meta: PluginMeta) -> dict:
        """Stop host plugin service."""
        if not meta.service:
            return {'success': False, 'error': 'No service defined'}

        result = _run_sudo(['systemctl', 'stop', meta.service])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}

        return {'success': True}

    def _status_host(self, meta: PluginMeta) -> dict:
        """Get host plugin status."""
        if not meta.service:
            return {'installed': True, 'status': 'unknown'}

        result = _run_sudo(['systemctl', 'is-active', meta.service])
        status = 'running' if result.returncode == 0 else 'stopped'

        return {'installed': True, 'status': status}

    # ---------------------------------------------------------------------------
    # Internal: Container operations
    # ---------------------------------------------------------------------------

    def _install_container(self, meta: PluginMeta) -> dict:
        """Install container plugin via Podman."""
        container_config = meta.container
        if not container_config:
            return {'success': False, 'error': 'No container configuration'}

        image = container_config.get('image')
        if not image:
            return {'success': False, 'error': 'No container image specified'}

        # Pull image
        result = _run_sudo(['podman', 'pull', image])
        if result.returncode != 0:
            return {'success': False, 'error': f'Failed to pull image: {result.stderr}'}

        # Create container
        container_name = f'w3panel-{meta.id}'
        ports = container_config.get('ports', {})
        volumes = container_config.get('volumes', {})
        env = container_config.get('env', {})

        cmd = ['podman', 'create', '--name', container_name, '--restart', 'unless-stopped']

        for host_port, container_port in ports.items():
            cmd.extend(['-p', f'{host_port}:{container_port}'])

        for vol_name, vol_path in volumes.items():
            cmd.extend(['-v', f'{vol_name}:{vol_path}'])

        for env_key, env_val in env.items():
            cmd.extend(['-e', f'{env_key}={env_val}'])

        cmd.append(image)

        result = _run_sudo(cmd)
        if result.returncode != 0:
            return {'success': False, 'error': f'Failed to create container: {result.stderr}'}

        # Start container
        result = _run_sudo(['podman', 'start', container_name])
        if result.returncode != 0:
            return {'success': False, 'error': f'Failed to start container: {result.stderr}'}

        return {'success': True, 'type': 'container'}

    def _uninstall_container(self, meta: PluginMeta) -> dict:
        """Uninstall container plugin."""
        container_name = f'w3panel-{meta.id}'

        # Stop and remove container
        _run_sudo(['podman', 'stop', container_name])
        result = _run_sudo(['podman', 'rm', container_name])

        # Remove volumes
        for vol_name in meta.container.get('volumes', {}).keys():
            _run_sudo(['podman', 'volume', 'rm', vol_name])

        return {'success': True}

    def _start_container(self, meta: PluginMeta) -> dict:
        """Start container plugin."""
        container_name = f'w3panel-{meta.id}'
        result = _run_sudo(['podman', 'start', container_name])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}
        return {'success': True}

    def _stop_container(self, meta: PluginMeta) -> dict:
        """Stop container plugin."""
        container_name = f'w3panel-{meta.id}'
        result = _run_sudo(['podman', 'stop', container_name])
        if result.returncode != 0:
            return {'success': False, 'error': result.stderr}
        return {'success': True}

    def _status_container(self, meta: PluginMeta) -> dict:
        """Get container plugin status."""
        container_name = f'w3panel-{meta.id}'
        result = _run_sudo(['podman', 'inspect', '--format', '{{.State.Status}}', container_name])
        if result.returncode != 0:
            return {'installed': True, 'status': 'not_running'}

        status = result.stdout.strip()
        return {'installed': True, 'status': status}

    # ---------------------------------------------------------------------------
    # Internal: Dependency/conflict checks
    # ---------------------------------------------------------------------------

    def _check_dependencies(self, meta: PluginMeta) -> dict:
        """Check if plugin dependencies are satisfied."""
        states = PluginState.load_all()
        missing = []

        for dep_id in meta.dependencies:
            dep_state = states.get(dep_id)
            if not dep_state or not dep_state.installed:
                missing.append(dep_id)

        return {'satisfied': len(missing) == 0, 'missing': missing}

    def _check_conflicts(self, meta: PluginMeta) -> dict:
        """Check if plugin conflicts with installed plugins."""
        states = PluginState.load_all()
        conflicts = []

        for conflict_id in meta.conflicts:
            conflict_state = states.get(conflict_id)
            if conflict_state and conflict_state.installed:
                conflicts.append(conflict_id)

        return {'conflicts': conflicts}

    def _load_meta(self, plugin_id: str) -> PluginMeta:
        """Load plugin meta."""
        meta_file = self.plugins_dir / plugin_id / 'meta.json'
        if not meta_file.exists():
            return None
        return PluginMeta.from_file(meta_file)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_sudo(cmd: list, check=False) -> subprocess.CompletedProcess:
    """Run command with sudo."""
    return subprocess.run(
        ['sudo', '-n'] + cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )
