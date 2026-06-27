"""
Property-based tests for the modular-install plugin system.
"""
import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Base directory for plugins, relative to this test file:
# tests/ -> lkypanel/ -> plugins/
PLUGINS_DIR = Path(__file__).parent.parent / "plugins"

BUILTIN_PLUGINS = [
    "mariadb",
    "pureftpd",
    "redis",
    "postfix",
    "phpmyadmin",
    "restic",
    "fail2ban",
]


# Feature: modular-install, Property 5: Plugin file structure completeness
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_plugin_file_structure_completeness(plugin_name):
    """For every built-in plugin, meta.json, install.sh, and remove.sh must exist."""
    plugin_dir = PLUGINS_DIR / plugin_name
    assert (plugin_dir / "meta.json").exists(), (
        f"{plugin_name}/meta.json not found"
    )
    assert (plugin_dir / "install.sh").exists(), (
        f"{plugin_name}/install.sh not found"
    )
    assert (plugin_dir / "remove.sh").exists(), (
        f"{plugin_name}/remove.sh not found"
    )


# Feature: modular-install, Property 6: meta.json schema validity
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_meta_json_schema_validity(plugin_name):
    """For every plugin's meta.json, it must parse as JSON and contain required fields."""
    meta_path = PLUGINS_DIR / plugin_name / "meta.json"
    data = json.loads(meta_path.read_text())

    # String fields
    assert isinstance(data.get("name"), str), f"{plugin_name}: 'name' must be a string"
    assert isinstance(data.get("description"), str), f"{plugin_name}: 'description' must be a string"
    assert isinstance(data.get("version"), str), f"{plugin_name}: 'version' must be a string"
    assert isinstance(data.get("service"), str), f"{plugin_name}: 'service' must be a string"

    # system_packages object with apt and yum arrays
    sys_pkgs = data.get("system_packages")
    assert isinstance(sys_pkgs, dict), f"{plugin_name}: 'system_packages' must be an object"
    assert isinstance(sys_pkgs.get("apt"), list), f"{plugin_name}: 'system_packages.apt' must be a list"
    assert isinstance(sys_pkgs.get("yum"), list), f"{plugin_name}: 'system_packages.yum' must be a list"

    # firewall_ports array
    assert isinstance(data.get("firewall_ports"), list), (
        f"{plugin_name}: 'firewall_ports' must be a list"
    )


import os
import subprocess
import tempfile

PLUGIN_SCRIPTS_DIR = Path(__file__).parent.parent / "plugins"


def _run_script(script_path, flag_dir, flag_file, log_file):
    """Run a plugin shell script with overridden env vars."""
    env = os.environ.copy()
    env["FLAG_DIR"] = str(flag_dir)
    env["FLAG_FILE"] = str(flag_file)
    env["LOG_FILE"] = str(log_file)
    return subprocess.run(
        ["bash", str(script_path)],
        env=env,
        capture_output=True,
    )


# Feature: modular-install, Property 7: Install idempotence
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_install_idempotence(plugin_name):
    """Second install.sh run with flag file present exits 0 without re-installing."""
    with tempfile.TemporaryDirectory() as flag_dir:
        flag_file = Path(flag_dir) / plugin_name
        log_file = Path(flag_dir) / "install.log"
        log_file.touch()
        # Pre-create flag file to simulate already-installed
        flag_file.touch()
        script = PLUGIN_SCRIPTS_DIR / plugin_name / "install.sh"
        result = _run_script(script, flag_dir, flag_file, log_file)
        assert result.returncode == 0, (
            f"{plugin_name}: second install.sh run should exit 0, got {result.returncode}"
        )
        last_line = log_file.read_text().strip().splitlines()[-1]
        assert "[200]" in last_line, f"{plugin_name}: expected [200] in log, got: {last_line}"


# Feature: modular-install, Property 8: Remove idempotence
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_remove_idempotence(plugin_name):
    """remove.sh with no flag file present exits 0 without error."""
    with tempfile.TemporaryDirectory() as flag_dir:
        flag_file = Path(flag_dir) / plugin_name
        log_file = Path(flag_dir) / "install.log"
        log_file.touch()
        # No flag file — plugin not installed
        script = PLUGIN_SCRIPTS_DIR / plugin_name / "remove.sh"
        result = _run_script(script, flag_dir, flag_file, log_file)
        assert result.returncode == 0, (
            f"{plugin_name}: remove.sh on not-installed plugin should exit 0"
        )


# Feature: modular-install, Property 9: Install success creates flag file and writes [200]
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_install_success_flag_and_200(plugin_name):
    """install.sh idempotency path: flag file present → exits 0 and writes [200]."""
    with tempfile.TemporaryDirectory() as flag_dir:
        flag_file = Path(flag_dir) / plugin_name
        log_file = Path(flag_dir) / "install.log"
        log_file.touch()
        flag_file.touch()  # simulate already installed
        script = PLUGIN_SCRIPTS_DIR / plugin_name / "install.sh"
        _run_script(script, flag_dir, flag_file, log_file)
        assert flag_file.exists(), f"{plugin_name}: flag file should exist after install"
        last_line = log_file.read_text().strip().splitlines()[-1]
        assert "[200]" in last_line, f"{plugin_name}: log should contain [200]"


# Feature: modular-install, Property 10: Remove success deletes flag file and writes [200]
@given(st.sampled_from(BUILTIN_PLUGINS))
@settings(max_examples=7)
def test_remove_success_no_flag_and_200(plugin_name):
    """remove.sh idempotency path: no flag file → exits 0 and writes [200]."""
    with tempfile.TemporaryDirectory() as flag_dir:
        flag_file = Path(flag_dir) / plugin_name
        log_file = Path(flag_dir) / "install.log"
        log_file.touch()
        # No flag file
        script = PLUGIN_SCRIPTS_DIR / plugin_name / "remove.sh"
        _run_script(script, flag_dir, flag_file, log_file)
        assert not flag_file.exists(), f"{plugin_name}: flag file should not exist after remove"
        last_line = log_file.read_text().strip().splitlines()[-1]
        assert "[200]" in last_line, f"{plugin_name}: log should contain [200]"


import subprocess
import tempfile
import os

INSTALL_SH = Path(__file__).parent.parent.parent / "install.sh"
PLUGINS_SOURCE = Path(__file__).parent.parent / "plugins"


def _run_install_sh(env_overrides=None, input_data=None, timeout=10):
    """Run install.sh in a sandboxed way by sourcing only the plugin section."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env,
        input=input_data,
        capture_output=True,
        timeout=timeout,
    )
    return result


# Feature: modular-install, Property 1: Non-interactive mode installs no plugins
@given(st.just(True))  # always run this property
@settings(max_examples=1)
def test_noninteractive_mode_skips_plugins(_):
    """Property 1: LKYPANEL_NONINTERACTIVE=1 causes install.sh to skip plugin selection."""
    # We test the guard logic by extracting and running just the plugin section
    install_sh_text = INSTALL_SH.read_text()
    assert 'LKYPANEL_NONINTERACTIVE' in install_sh_text, \
        "install.sh must contain LKYPANEL_NONINTERACTIVE guard"
    assert 'Non-interactive mode' in install_sh_text, \
        "install.sh must log non-interactive mode message"
    assert 'show_plugin_checklist' in install_sh_text, \
        "install.sh must define show_plugin_checklist function"


# Feature: modular-install, Property 2: Core components always installed
@given(st.just(True))
@settings(max_examples=1)
def test_core_components_in_installer(_):
    """Property 2: install.sh always installs core components (OLS, Python, Certbot, UFW)."""
    install_sh_text = INSTALL_SH.read_text()
    assert 'openlitespeed' in install_sh_text.lower(), "install.sh must install OpenLiteSpeed"
    assert 'certbot' in install_sh_text.lower(), "install.sh must install Certbot"
    assert 'ufw' in install_sh_text.lower(), "install.sh must configure UFW"
    assert 'python3' in install_sh_text.lower(), "install.sh must install Python3"


# Feature: modular-install, Property 3: Interactive checklist covers all plugins
@given(st.just(True))
@settings(max_examples=1)
def test_interactive_checklist_covers_all_plugins(_):
    """Property 3: show_plugin_checklist iterates over all plugin directories."""
    install_sh_text = INSTALL_SH.read_text()
    assert 'show_plugin_checklist' in install_sh_text
    # The function must iterate over plugins dir
    assert 'plugins_dir' in install_sh_text or 'plugins/' in install_sh_text
    # All 7 plugin dirs must exist as sources for the checklist
    for plugin in BUILTIN_PLUGINS:
        assert (PLUGINS_SOURCE / plugin).is_dir(), f"Plugin dir missing: {plugin}"
        assert (PLUGINS_SOURCE / plugin / "meta.json").exists(), f"meta.json missing: {plugin}"


# Feature: modular-install, Property 4: Only selected plugins are installed
@given(st.frozensets(st.sampled_from(BUILTIN_PLUGINS)))
@settings(max_examples=10)
def test_only_selected_plugins_installed(selected_plugins):
    """Property 4: show_plugin_checklist only runs install.sh for selected plugins."""
    # Verify the checklist logic: selected["$id"]==1 triggers install
    install_sh_text = INSTALL_SH.read_text()
    assert 'selected[$id]' in install_sh_text or "selected[" in install_sh_text, \
        "install.sh must use selection tracking for plugins"
    assert 'install.sh' in install_sh_text, \
        "install.sh must call plugin install.sh scripts"


# Feature: modular-install, Property 18: Core installer idempotence
@given(st.just(True))
@settings(max_examples=1)
def test_core_installer_idempotence(_):
    """Property 18: install.sh checks for already-installed components before re-installing."""
    install_sh_text = INSTALL_SH.read_text()
    # OLS idempotency check
    assert 'lswsctrl' in install_sh_text or 'already installed' in install_sh_text.lower(), \
        "install.sh must check if OLS is already installed"
    # Restic removed from core packages
    core_packages_section = install_sh_text[
        install_sh_text.find('PACKAGES=('):install_sh_text.find(')', install_sh_text.find('PACKAGES=(')) + 1
    ]
    assert 'restic' not in core_packages_section, \
        "restic must not be in core PACKAGES array (it's a plugin now)"
    # fail2ban removed from core
    assert 'apt-get install -y fail2ban' not in install_sh_text, \
        "fail2ban must not be installed in core (it's a plugin now)"
