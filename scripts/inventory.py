"""Inventory only personal skill files; never inspect runtime configuration."""
import hashlib
import json
import os
from pathlib import Path

ROOTS = ('.agents/skills', '.codex/skills', '.claude/skills')
SKIP_DIRS = {'.git', '.venv', '__pycache__', 'node_modules', '.system', 'synced', '.trash', '.ssh', '.aws'}
SECRET_NAMES = {'.env', '.pgpass', '.pg_service.conf', '.netrc', 'credentials', '.credentials', 'credentials.json', 'auth.json', 'odbc.ini', '.odbc.ini', 'id_rsa', 'id_ed25519', 'token', 'tokens.json', 'secrets.json', 'secrets.yaml', 'secrets.yml', 'client_secret.json', 'service-account.json', 'service_account.json'}

def safe(path):
    return not (set(path.parts) & SKIP_DIRS or path.name in SECRET_NAMES or path.name.startswith('.env.') or path.suffix in {'.pyc', '.pem', '.key'} or path.name == '.DS_Store')

def files(path):
    result = {}
    for f in sorted(path.rglob('*')):
        rel = f.relative_to(path)
        if not safe(rel):
            continue
        if f.is_symlink():
            # Record the link itself without reading an external target.
            result[str(rel)] = 'symlink:' + hashlib.sha256(os.fsencode(os.readlink(f))).hexdigest()
        elif f.is_file():
            result[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return result

def executable_modes(path, contents):
    """Record owner execution permission without following nested symlinks."""
    return {rel: bool((path/rel).stat().st_mode & 0o100)
            for rel,digest in contents.items() if not digest.startswith('symlink:')}

def inventory(home):
    result = []
    for rel in ROOTS:
        root = home / rel
        if not root.exists():
            continue
        for p in sorted(root.iterdir()):
            if p.name.startswith('.') or p.name == 'synced' or not (p/'SKILL.md').is_file():
                continue
            result.append(dict(root=rel, name=p.name, symlink=p.is_symlink(),
                               resolved=str(p.resolve()), files=files(p)))
    return result

if __name__ == '__main__':
    print(json.dumps(inventory(Path.home()), indent=2))
