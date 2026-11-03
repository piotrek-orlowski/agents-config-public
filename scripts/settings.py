"""Repository settings and private, explicitly selected fleet targets."""
from pathlib import Path, PurePosixPath
import re
import tomllib

REPO = Path(__file__).resolve().parents[1]
NAME = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')


def settings():
    path = REPO / 'framework.toml'
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    result = {'remote': 'origin', 'branch': 'main', 'state_name': 'agents-config-public'} | data
    for key in ('remote', 'branch', 'state_name'):
        if not isinstance(result[key], str) or not NAME.fullmatch(result[key]):
            raise ValueError(f'Invalid framework setting: {key}')
    return result


def state_directory(home):
    return home / '.local/state' / settings()['state_name']


def targets(config, selected=()):
    path = config.expanduser() if config else REPO / 'fleet.local.toml'
    data = tomllib.loads(path.read_text()).get('targets', {})
    if not isinstance(data, dict) or not data:
        raise ValueError('Fleet configuration must contain at least one [targets.NAME] table')
    unknown = set(selected) - set(data)
    if unknown:
        raise ValueError('Unknown fleet targets: ' + ', '.join(sorted(unknown)))
    result = {}
    for name in selected or data:
        target = data[name]
        if not NAME.fullmatch(name) or not isinstance(target, dict):
            raise ValueError('Invalid fleet target name or table')
        host = target.get('ssh_host', '')
        if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.@-]*', host):
            raise ValueError(f'Invalid SSH host for target {name}; use an SSH alias')
        profile = target.get('profile', '')
        if not isinstance(profile, str) or not NAME.fullmatch(profile):
            raise ValueError(f'Invalid profile for target {name}')
        checkout = target.get('path', '')
        if (not isinstance(checkout, str) or not checkout or checkout in {'.', '/'}
                or '..' in PurePosixPath(checkout).parts or checkout.startswith(('~', '-'))
                or any(ord(char) < 32 for char in checkout)):
            raise ValueError(f'Invalid checkout path for target {name}')
        result[name] = dict(ssh_host=host, profile=profile, path=checkout)
    return result
