"""
Unit and property tests for services/packages.py and admin_views/packages.py.
"""
import json
import os
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import patch, MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st
from django.test import RequestFactory, TestCase

import lkypanel.services.packages as svc
from lkypanel.admin_views import packages as pkg_views


def _patch_flag_dir(tmp_path):
    return mock.patch.object(svc, "PLUGINS_FLAG_DIR", str(tmp_path))


def _patch_status_log(tmp_log):
    return mock.patch.object(svc, "PLUGIN_STATUS_LOG", str(tmp_log))


def _unwrap(fn):
    """Fully unwrap decorated view to reach the raw function."""
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    return fn


def _make_request(factory, method, path, body=None):
    if method == "POST":
        req = factory.post(path, data=body, content_type="application/json")
    else:
        req = factory.get(path)
    req.panel_user = MagicMock()
    req.panel_user.role = "admin"
    return req


# ---------------------------------------------------------------------------
# Task 4.1 — unit tests for is_plugin_installed
# ---------------------------------------------------------------------------

def test_is_plugin_installed_flag_present(tmp_path):
    (tmp_path / "mariadb").touch()
    with _patch_flag_dir(tmp_path):
        assert svc.is_plugin_installed("mariadb") is True


def test_is_plugin_installed_flag_absent(tmp_path):
    with _patch_flag_dir(tmp_path):
        assert svc.is_plugin_installed("mariadb") is False


def test_is_plugin_installed_directory_missing():
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", "/nonexistent/path/xyz"):
        assert svc.is_plugin_installed("mariadb") is False


def test_is_plugin_installed_oserror_returns_false():
    with mock.patch("os.path.isfile", side_effect=OSError("permission denied")):
        assert svc.is_plugin_installed("mariadb") is False




# ---------------------------------------------------------------------------
# Task 4.1 — unit tests for is_plugin_installed
# ---------------------------------------------------------------------------

def test_is_plugin_installed_flag_present(tmp_path):
    (tmp_path / "mariadb").touch()
    with _patch_flag_dir(tmp_path):
        assert svc.is_plugin_installed("mariadb") is True


def test_is_plugin_installed_flag_absent(tmp_path):
    with _patch_flag_dir(tmp_path):
        assert svc.is_plugin_installed("mariadb") is False


def test_is_plugin_installed_directory_missing():
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", "/nonexistent/path/xyz"):
        assert svc.is_plugin_installed("mariadb") is False


def test_is_plugin_installed_oserror_returns_false():
    with mock.patch("os.path.isfile", side_effect=OSError("permission denied")):
        assert svc.is_plugin_installed("mariadb") is False


# ---------------------------------------------------------------------------
# Task 4.2 — Property 11: is_plugin_installed reflects flag file state
# ---------------------------------------------------------------------------

@given(plugin_name=st.sampled_from(svc.BUILTIN_PLUGINS), installed=st.booleans())
@settings(max_examples=20)
def test_is_plugin_installed_reflects_flag_file(plugin_name, installed):
    """Property 11: is_plugin_installed returns True iff flag file exists."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        if installed:
            (Path(tmp_dir) / plugin_name).touch()
        with mock.patch.object(svc, "PLUGINS_FLAG_DIR", tmp_dir):
            result = svc.is_plugin_installed(plugin_name)
    assert result == installed


# ---------------------------------------------------------------------------
# Task 4.3 — unit tests for read_plugin_status
# ---------------------------------------------------------------------------

def test_read_plugin_status_200(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing...\nPlugin installed.[200]\n")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "success"
    assert "[200]" in status["message"]


def test_read_plugin_status_404(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing...\nPlugin operation failed.[404]\n")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "error"
    assert "[404]" in status["message"]


def test_read_plugin_status_partial_output(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing packages...\n")
    with _patch_status_log(log):
        assert svc.read_plugin_status()["state"] == "running"


def test_read_plugin_status_empty_file(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "running"
    assert status["message"] == ""


def test_read_plugin_status_missing_file(tmp_path):
    with _patch_status_log(tmp_path / "nonexistent.log"):
        status = svc.read_plugin_status()
    assert status["state"] == "running"
    assert status["message"] == ""


# ---------------------------------------------------------------------------
# Task 4.4 — Property 12: poll_status correctly parses log state
# ---------------------------------------------------------------------------

@given(last_line=st.one_of(
    st.just("[200]"), st.just("[404]"),
    st.just("Installing packages..."), st.just(""),
))
@settings(max_examples=20)
def test_poll_status_parses_log_state(last_line):
    """Property 12: read_plugin_status returns correct state based on last line."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(f"some output\n{last_line}\n")
        log_path = f.name
    try:
        with mock.patch.object(svc, "PLUGIN_STATUS_LOG", log_path):
            status = svc.read_plugin_status()
        if "[200]" in last_line:
            assert status["state"] == "success"
        elif "[404]" in last_line:
            assert status["state"] == "error"
        else:
            assert status["state"] == "running"
    finally:
        os.unlink(log_path)


# ---------------------------------------------------------------------------
# Task 4.5 — unit tests for get_all_plugins
# ---------------------------------------------------------------------------

def test_get_all_plugins_returns_all_seven(tmp_path):
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", str(tmp_path)):
        plugins = svc.get_all_plugins()
    assert set(p["id"] for p in plugins) == set(svc.BUILTIN_PLUGINS)


def test_get_all_plugins_state_installed(tmp_path):
    (tmp_path / "mariadb").touch()
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", str(tmp_path)):
        plugins = svc.get_all_plugins()
    mariadb = next(p for p in plugins if p["id"] == "mariadb")
    assert mariadb["state"] == "installed"


def test_get_all_plugins_state_not_installed(tmp_path):
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", str(tmp_path)):
        plugins = svc.get_all_plugins()
    for p in plugins:
        assert p["state"] == "not_installed"


def test_get_all_plugins_has_required_keys(tmp_path):
    with mock.patch.object(svc, "PLUGINS_FLAG_DIR", str(tmp_path)):
        plugins = svc.get_all_plugins()
    for p in plugins:
        for key in ("id", "name", "description", "version", "firewall_ports", "state"):
            assert key in p


# ---------------------------------------------------------------------------
# Task 4.2 — Property 11: is_plugin_installed reflects flag file state
# ---------------------------------------------------------------------------

@given(plugin_name=st.sampled_from(svc.BUILTIN_PLUGINS), installed=st.booleans())
@settings(max_examples=20)
def test_is_plugin_installed_reflects_flag_file(plugin_name, installed):
    with tempfile.TemporaryDirectory() as tmp_dir:
        if installed:
            (Path(tmp_dir) / plugin_name).touch()
        with mock.patch.object(svc, "PLUGINS_FLAG_DIR", tmp_dir):
            assert svc.is_plugin_installed(plugin_name) == installed


# ---------------------------------------------------------------------------
# Task 4.3 — unit tests for read_plugin_status
# ---------------------------------------------------------------------------

def test_read_plugin_status_200(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing...\nPlugin installed.[200]\n")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "success"
    assert "[200]" in status["message"]


def test_read_plugin_status_404(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing...\nPlugin operation failed.[404]\n")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "error"
    assert "[404]" in status["message"]


def test_read_plugin_status_partial_output(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("Installing packages...\n")
    with _patch_status_log(log):
        assert svc.read_plugin_status()["state"] == "running"


def test_read_plugin_status_empty_file(tmp_path):
    log = tmp_path / "install.log"
    log.write_text("")
    with _patch_status_log(log):
        status = svc.read_plugin_status()
    assert status["state"] == "running"
    assert status["message"] == ""


def test_read_plugin_status_missing_file(tmp_path):
    with _patch_status_log(tmp_path / "nonexistent.log"):
        status = svc.read_plugin_status()
    assert status["state"] == "running"
    assert status["message"] == ""




# ---------------------------------------------------------------------------
# Task 5.1 — unit tests for trigger_plugin view
# ---------------------------------------------------------------------------

class TriggerPluginViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory(enforce_csrf_checks=False)

    def _call(self, body_dict, **patches):
        req = _make_post_request(
            self.factory, "/admin/packages/trigger/", json.dumps(body_dict)
        )
        return _call_view(pkg_views.trigger_plugin, req, **patches)

    def test_unknown_plugin_returns_400(self):
        resp = self._call(
            {"plugin_id": "unknown_plugin", "operation": "install"},
            **{"lkypanel.admin_views.packages.read_plugin_status":
               MagicMock(return_value={"state": "success", "message": ""})}
        )
        assert resp.status_code == 400
        assert b"Unknown plugin" in resp.content

    def test_invalid_operation_returns_400(self):
        resp = self._call(
            {"plugin_id": "mariadb", "operation": "hack"},
            **{"lkypanel.admin_views.packages.read_plugin_status":
               MagicMock(return_value={"state": "success", "message": ""})}
        )
        assert resp.status_code == 400
        assert b"Invalid operation" in resp.content

    def test_missing_script_returns_500(self):
        resp = self._call(
            {"plugin_id": "mariadb", "operation": "install"},
            **{
                "lkypanel.admin_views.packages.read_plugin_status":
                    MagicMock(return_value={"state": "success", "message": ""}),
                "lkypanel.admin_views.packages.PLUGINS_SOURCE_DIR": Path("/nonexistent"),
            }
        )
        assert resp.status_code == 500
        assert b"not found" in resp.content

    def test_concurrent_operation_returns_400(self):
        resp = self._call(
            {"plugin_id": "mariadb", "operation": "install"},
            **{"lkypanel.admin_views.packages.read_plugin_status":
               MagicMock(return_value={"state": "running", "message": "Installing..."})}
        )
        assert resp.status_code == 400
        assert b"already in progress" in resp.content

    def test_valid_call_returns_started(self):
        mock_launch = MagicMock()
        resp = self._call(
            {"plugin_id": "mariadb", "operation": "install"},
            **{
                "lkypanel.admin_views.packages.read_plugin_status":
                    MagicMock(return_value={"state": "success", "message": ""}),
                "lkypanel.admin_views.packages.launch_plugin_op": mock_launch,
            }
        )
        assert resp.status_code == 200
        assert json.loads(resp.content) == {"status": "started"}
        mock_launch.assert_called_once_with("mariadb", "install")


# ---------------------------------------------------------------------------
# Task 5.2 — unit tests for poll_status view
# ---------------------------------------------------------------------------

class PollStatusViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory(enforce_csrf_checks=False)

    def _call(self, mock_status):
        req = _make_get_request(self.factory, "/admin/packages/status/")
        return _call_view(
            pkg_views.poll_status, req,
            **{"lkypanel.admin_views.packages.read_plugin_status":
               MagicMock(return_value=mock_status)}
        )

    def test_poll_status_returns_correct_json_shape(self):
        resp = self._call({"state": "running", "message": "Installing..."})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "state" in data
        assert "message" in data

    def test_poll_status_success_state(self):
        resp = self._call({"state": "success", "message": "Plugin installed.[200]"})
        assert json.loads(resp.content)["state"] == "success"

    def test_poll_status_error_state(self):
        resp = self._call({"state": "error", "message": "Plugin operation failed.[404]"})
        assert json.loads(resp.content)["state"] == "error"


# ---------------------------------------------------------------------------
# Task 5.3 — Property 13: Packages page renders all plugins
# ---------------------------------------------------------------------------

@given(installed_set=st.frozensets(st.sampled_from(svc.BUILTIN_PLUGINS)))
@settings(max_examples=20)
def test_packages_page_renders_all_plugins(installed_set):
    """Property 13: get_all_plugins always returns all 7 built-in plugins with correct state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        for pid in installed_set:
            (Path(tmp_dir) / pid).touch()
        with mock.patch.object(svc, "PLUGINS_FLAG_DIR", tmp_dir):
            plugins = svc.get_all_plugins()

    assert len(plugins) == 7
    assert {p["id"] for p in plugins} == set(svc.BUILTIN_PLUGINS)
    for p in plugins:
        expected = "installed" if p["id"] in installed_set else "not_installed"
        assert p["state"] == expected


# ---------------------------------------------------------------------------
# Task 4.4 — Property 12: poll_status correctly parses log state
# ---------------------------------------------------------------------------

@given(last_line=st.one_of(
    st.just("[200]"), st.just("[404]"),
    st.just("Installing packages..."), st.just(""),
))
@settings(max_examples=20)
def test_poll_status_parses_log_state(last_line):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write(f"some output\n{last_line}\n")
        log_path = f.name
    try:
        with mock.patch.object(svc, "PLUGIN_STATUS_LOG", log_path):
            status = svc.read_plugin_status()
        if "[200]" in last_line:
            assert status["state"] == "success"
        elif "[404]" in last_line:
            assert status["state"] == "error"
        else:
            assert status["state"] == "running"
    finally:
        os.unlink(log_path)


# ---------------------------------------------------------------------------
# Task 4.5 — unit tests for get_all_plugins
# ---------------------------------------------------------------------------

def test_get_all_plugins_returns_all_seven(tmp_path):
    with _patch_flag_dir(tmp_path):
        plugins = svc.get_all_plugins()
    assert set(p["id"] for p in plugins) == set(svc.BUILTIN_PLUGINS)


def test_get_all_plugins_state_installed(tmp_path):
    (tmp_path / "mariadb").touch()
    with _patch_flag_dir(tmp_path):
        plugins = svc.get_all_plugins()
    mariadb = next(p for p in plugins if p["id"] == "mariadb")
    assert mariadb["state"] == "installed"


def test_get_all_plugins_state_not_installed(tmp_path):
    with _patch_flag_dir(tmp_path):
        plugins = svc.get_all_plugins()
    assert all(p["state"] == "not_installed" for p in plugins)


def test_get_all_plugins_has_required_keys(tmp_path):
    with _patch_flag_dir(tmp_path):
        plugins = svc.get_all_plugins()
    for p in plugins:
        for key in ("id", "name", "description", "version", "firewall_ports", "state"):
            assert key in p



# ---------------------------------------------------------------------------
# Task 5.1 — trigger_plugin view tests (fully unwrapped)
# ---------------------------------------------------------------------------

_trigger_fn = _unwrap(pkg_views.trigger_plugin)
_poll_fn = _unwrap(pkg_views.poll_status)


class TriggerPluginViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory(enforce_csrf_checks=False)

    def test_unknown_plugin_returns_400(self):
        req = _make_request(self.factory, "POST", "/admin/packages/trigger/",
                            json.dumps({"plugin_id": "unknown_plugin", "operation": "install"}))
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "success", "message": ""}):
            resp = _trigger_fn(req)
        assert resp.status_code == 400
        assert b"Unknown plugin" in resp.content

    def test_invalid_operation_returns_400(self):
        req = _make_request(self.factory, "POST", "/admin/packages/trigger/",
                            json.dumps({"plugin_id": "mariadb", "operation": "hack"}))
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "success", "message": ""}):
            resp = _trigger_fn(req)
        assert resp.status_code == 400
        assert b"Invalid operation" in resp.content

    def test_missing_script_returns_500(self):
        req = _make_request(self.factory, "POST", "/admin/packages/trigger/",
                            json.dumps({"plugin_id": "mariadb", "operation": "install"}))
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "success", "message": ""}):
            with patch("lkypanel.admin_views.packages.PLUGINS_SOURCE_DIR", Path("/nonexistent")):
                resp = _trigger_fn(req)
        assert resp.status_code == 500
        assert b"not found" in resp.content

    def test_concurrent_operation_returns_400(self):
        req = _make_request(self.factory, "POST", "/admin/packages/trigger/",
                            json.dumps({"plugin_id": "mariadb", "operation": "install"}))
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "running", "message": "Installing..."}):
            resp = _trigger_fn(req)
        assert resp.status_code == 400
        assert b"already in progress" in resp.content

    def test_valid_call_returns_started(self):
        req = _make_request(self.factory, "POST", "/admin/packages/trigger/",
                            json.dumps({"plugin_id": "mariadb", "operation": "install"}))
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "success", "message": ""}):
            with patch("lkypanel.admin_views.packages.launch_plugin_op") as mock_launch:
                resp = _trigger_fn(req)
        assert resp.status_code == 200
        assert json.loads(resp.content) == {"status": "started"}
        mock_launch.assert_called_once_with("mariadb", "install")



# ---------------------------------------------------------------------------
# Task 5.2 — poll_status view tests
# ---------------------------------------------------------------------------

class PollStatusViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory(enforce_csrf_checks=False)

    def test_poll_status_returns_correct_json_shape(self):
        req = _make_request(self.factory, "GET", "/admin/packages/status/")
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "running", "message": "Installing..."}):
            resp = _poll_fn(req)
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert "state" in data and "message" in data

    def test_poll_status_success_state(self):
        req = _make_request(self.factory, "GET", "/admin/packages/status/")
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "success", "message": "Plugin installed.[200]"}):
            resp = _poll_fn(req)
        assert json.loads(resp.content)["state"] == "success"

    def test_poll_status_error_state(self):
        req = _make_request(self.factory, "GET", "/admin/packages/status/")
        with patch("lkypanel.admin_views.packages.read_plugin_status",
                   return_value={"state": "error", "message": "Plugin operation failed.[404]"}):
            resp = _poll_fn(req)
        assert json.loads(resp.content)["state"] == "error"


# ---------------------------------------------------------------------------
# Task 5.3 — Property 13: Packages page renders all plugins
# ---------------------------------------------------------------------------

@given(installed_set=st.frozensets(st.sampled_from(svc.BUILTIN_PLUGINS)))
@settings(max_examples=20)
def test_packages_page_renders_all_plugins(installed_set):
    """Property 13: get_all_plugins always returns all 7 built-in plugins with correct state."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        for pid in installed_set:
            (Path(tmp_dir) / pid).touch()
        with mock.patch.object(svc, "PLUGINS_FLAG_DIR", tmp_dir):
            plugins = svc.get_all_plugins()

    assert len(plugins) == 7
    assert {p["id"] for p in plugins} == set(svc.BUILTIN_PLUGINS)
    for p in plugins:
        expected = "installed" if p["id"] in installed_set else "not_installed"
        assert p["state"] == expected


# ---------------------------------------------------------------------------
# Task 6.1 — Property 14: Button state matches plugin state
# ---------------------------------------------------------------------------

from django.template import Context, Template
from django.test import override_settings

@given(
    plugin_id=st.sampled_from(svc.BUILTIN_PLUGINS),
    state=st.sampled_from(["installed", "not_installed"]),
)
@settings(max_examples=20)
def test_button_state_matches_plugin_state(plugin_id, state):
    """Property 14: installed → Remove button; not_installed → Install button."""
    plugins = [
        {"id": pid, "name": pid, "description": "", "version": "1.0",
         "firewall_ports": [], "state": state if pid == plugin_id else "not_installed"}
        for pid in svc.BUILTIN_PLUGINS
    ]
    # mariadb_installed needed for phpmyadmin dependency check
    mariadb_installed = any(p["id"] == "mariadb" and p["state"] == "installed" for p in plugins)

    factory = RequestFactory()
    req = factory.get("/admin/packages/")
    req.panel_user = MagicMock()

    _list_fn = _unwrap(pkg_views.list_packages)
    with patch("lkypanel.admin_views.packages.get_all_plugins", return_value=plugins):
        with patch("lkypanel.admin_views.packages.is_plugin_installed",
                   side_effect=lambda n: n == "mariadb" and mariadb_installed):
            resp = _list_fn(req)

    assert resp.status_code == 200
    content = resp.content.decode()

    # Find the card for our plugin
    card_marker = f'id="card-{plugin_id}"'
    assert card_marker in content, f"Card for {plugin_id} not found in rendered HTML"

    card_start = content.index(card_marker)
    # Find next card or end of grid
    next_card = content.find('class="package-card', card_start + 1)
    card_html = content[card_start: next_card if next_card != -1 else len(content)]

    if state == "installed":
        assert 'data-op="remove"' in card_html, \
            f"{plugin_id} installed: expected Remove button, got: {card_html[:300]}"
    else:
        # phpmyadmin with no mariadb gets disabled button — skip that case
        if plugin_id == "phpmyadmin" and not mariadb_installed:
            assert "disabled" in card_html
        else:
            assert 'data-op="install"' in card_html, \
                f"{plugin_id} not_installed: expected Install button, got: {card_html[:300]}"
