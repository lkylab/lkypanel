"""
Git integration service.
Credentials never passed on CLI. SSH keys via GIT_SSH_COMMAND temp file.
Tokens injected into URL in memory only, never logged.
"""
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)
GIT_TIMEOUT = 60
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')


from lkypanel.utils.encryption import encrypt_data as encrypt_credentials, decrypt_data as decrypt_credentials


def _sanitize_stderr(stderr: str) -> str:
    cleaned = ANSI_RE.sub('', stderr)
    return cleaned[:2048]


def _build_env(auth_type: str, credentials: str | None, ssh_key_file: str | None = None) -> dict:
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    if auth_type == 'ssh' and ssh_key_file:
        env['GIT_SSH_COMMAND'] = f'ssh -i {ssh_key_file} -o StrictHostKeyChecking=no'
    return env


def _inject_token_url(repo_url: str, token: str) -> str:
    """Inject token into https URL in memory only."""
    if repo_url.startswith('https://'):
        return repo_url.replace('https://', f'https://{token}@', 1)
    return repo_url


def _run_git(args: list, cwd: str, env: dict) -> tuple[int, str, str]:
    result = subprocess.run(
        ['git'] + args,
        cwd=cwd,
        env=env,
        shell=False,
        timeout=GIT_TIMEOUT,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def clone_repo(website, repo_url: str, branch: str, auth_type: str,
               credentials: str | None) -> None:
    from lkypanel.models import GitRepo
    doc_root = website.doc_root
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    actual_url = repo_url
    ssh_tmp = None

    try:
        if auth_type == 'ssh' and credentials:
            ssh_tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
            ssh_tmp.write(credentials)
            ssh_tmp.close()
            os.chmod(ssh_tmp.name, 0o600)
            env['GIT_SSH_COMMAND'] = f'ssh -i {ssh_tmp.name} -o StrictHostKeyChecking=no'
        elif auth_type == 'token' and credentials:
            actual_url = _inject_token_url(repo_url, credentials)

        rc, stdout, stderr = _run_git(
            ['clone', '--branch', branch, actual_url, doc_root],
            cwd='/', env=env,
        )
    finally:
        if ssh_tmp and os.path.exists(ssh_tmp.name):
            os.unlink(ssh_tmp.name)

    if rc != 0:
        raise RuntimeError(_sanitize_stderr(stderr))

    # Persist encrypted credentials
    enc = encrypt_credentials(credentials) if credentials else None
    GitRepo.objects.update_or_create(
        website=website,
        defaults=dict(
            repo_url=repo_url,
            branch=branch,
            auth_type=auth_type,
            encrypted_credentials=enc,
        ),
    )


def pull_repo(git_repo) -> str:
    doc_root = git_repo.website.doc_root
    env, ssh_tmp = _prepare_env(git_repo)
    try:
        rc, stdout, stderr = _run_git(['pull', 'origin', git_repo.branch], cwd=doc_root, env=env)
    finally:
        if ssh_tmp and os.path.exists(ssh_tmp):
            os.unlink(ssh_tmp)
    if rc != 0:
        raise RuntimeError(_sanitize_stderr(stderr))
    return stdout


def push_repo(git_repo) -> str:
    doc_root = git_repo.website.doc_root
    env, ssh_tmp = _prepare_env(git_repo)
    try:
        rc, stdout, stderr = _run_git(['push', 'origin', git_repo.branch], cwd=doc_root, env=env)
    finally:
        if ssh_tmp and os.path.exists(ssh_tmp):
            os.unlink(ssh_tmp)
    if rc != 0:
        raise RuntimeError(_sanitize_stderr(stderr))
    return stdout


def _prepare_env(git_repo) -> tuple[dict, str | None]:
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    ssh_tmp = None

    if git_repo.encrypted_credentials:
        creds = decrypt_credentials(bytes(git_repo.encrypted_credentials))
        if git_repo.auth_type == 'ssh':
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False)
            tmp.write(creds)
            tmp.close()
            os.chmod(tmp.name, 0o600)
            env['GIT_SSH_COMMAND'] = f'ssh -i {tmp.name} -o StrictHostKeyChecking=no'
            ssh_tmp = tmp.name
        elif git_repo.auth_type == 'token':
            env['GIT_ASKPASS'] = 'echo'
            env['GIT_USERNAME'] = 'token'
            env['GIT_PASSWORD'] = creds

    return env, ssh_tmp
