"""
W3Panel v2 — Plugin Models
Meta.json parsing and state management.
"""
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger('w3panel.plugins')

PLUGINS_DIR = Path('/usr/local/w3panel/panel/plugins')
STATE_FILE = Path('/etc/w3panel/plugin_state.json')


# ---------------------------------------------------------------------------
# Plugin Meta (from meta.json)
# ---------------------------------------------------------------------------

@dataclass
class PluginMeta:
    """Parsed plugin meta.json."""
    id: str
    name: str
    description: str = ''
    version: str = ''
    type: str = 'auto'  # 'host', 'container', or 'auto'
    category: str = ''
    dependencies: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    provides: list = field(default_factory=list)
    system_packages: dict = field(default_factory=dict)
    service: str = ''
    firewall_ports: list = field(default_factory=list)
    container: dict = field(default_factory=dict)
    install_script: str = 'install.sh'
    remove_script: str = 'remove.sh'

    @classmethod
    def from_file(cls, meta_path: Path) -> 'PluginMeta':
        """Load plugin from meta.json file."""
        try:
            data = json.loads(meta_path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            logger.error('Failed to load %s: %s', meta_path, e)
            return None

        return cls(
            id=data.get('id', meta_path.parent.name),
            name=data.get('name', ''),
            description=data.get('description', ''),
            version=data.get('version', ''),
            type=data.get('type', 'auto'),
            category=data.get('category', ''),
            dependencies=data.get('dependencies', []),
            conflicts=data.get('conflicts', []),
            provides=data.get('provides', []),
            system_packages=data.get('system_packages', {}),
            service=data.get('service', ''),
            firewall_ports=data.get('firewall_ports', []),
            container=data.get('container', {}),
            install_script=data.get('install_script', 'install.sh'),
            remove_script=data.get('remove_script', 'remove.sh'),
        )

    @classmethod
    def load_all(cls) -> list:
        """Load all plugins from plugins directory."""
        plugins = []
        if not PLUGINS_DIR.exists():
            return plugins

        for plugin_dir in PLUGINS_DIR.iterdir():
            if not plugin_dir.is_dir():
                continue
            meta_file = plugin_dir / 'meta.json'
            if meta_file.exists():
                meta = cls.from_file(meta_file)
                if meta:
                    plugins.append(meta)

        return plugins

    @property
    def supports_container(self):
        """Check if plugin supports container mode."""
        return bool(self.container)

    @property
    def supports_host(self):
        """Check if plugin supports host mode."""
        return bool(self.service) or bool(self.system_packages)


# ---------------------------------------------------------------------------
# Plugin State (installed status, preferred type)
# ---------------------------------------------------------------------------

@dataclass
class PluginState:
    """Plugin installation state."""
    plugin_id: str
    installed: bool = False
    preferred_type: str = ''  # 'host' or 'container' (user override)
    installed_type: str = ''  # Actual installed type
    installed_at: str = ''
    version: str = ''

    @classmethod
    def load_all(cls) -> dict:
        """Load all plugin states from state file."""
        if not STATE_FILE.exists():
            return {}

        try:
            data = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}

        states = {}
        for plugin_id, state_data in data.get('plugins', {}).items():
            states[plugin_id] = cls(
                plugin_id=plugin_id,
                installed=state_data.get('installed', False),
                preferred_type=state_data.get('preferred_type', ''),
                installed_type=state_data.get('installed_type', ''),
                installed_at=state_data.get('installed_at', ''),
                version=state_data.get('version', ''),
            )
        return states

    @classmethod
    def save_all(cls, states: dict):
        """Save all plugin states to state file."""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {'plugins': {}}
        for plugin_id, state in states.items():
            data['plugins'][plugin_id] = {
                'installed': state.installed,
                'preferred_type': state.preferred_type,
                'installed_type': state.installed_type,
                'installed_at': state.installed_at,
                'version': state.version,
            }

        STATE_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def get(cls, plugin_id: str) -> 'PluginState':
        """Get state for a specific plugin."""
        states = cls.load_all()
        return states.get(plugin_id, cls(plugin_id=plugin_id))

    @classmethod
    def set(cls, plugin_id: str, **kwargs):
        """Update state for a specific plugin."""
        states = cls.load_all()
        if plugin_id in states:
            state = states[plugin_id]
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
        else:
            state = cls(plugin_id=plugin_id, **kwargs)
        states[plugin_id] = state
        cls.save_all(states)
        return state
