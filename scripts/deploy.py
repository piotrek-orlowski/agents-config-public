"""Bootstrap or update configured targets with a published Git bundle."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import uuid
from fleet import SSH, SCP, remote_prefix
from settings import REPO, settings, targets


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], text=True).strip()


def safe_origin(origin):
    """Only transfer credential-free HTTPS or SSH remote addresses."""
    import re
    parsed = urlsplit(origin)
    if parsed.scheme in {'https', 'ssh'}:
        if (not parsed.hostname or parsed.password or parsed.query or parsed.fragment
                or (parsed.scheme == 'https' and parsed.username)):
            raise ValueError('Use a credential-free HTTPS or SSH repository remote')
    elif not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+', origin):
        raise ValueError('Bundle deployment requires a credential-free HTTPS or SSH repository remote')
    if any(ord(char) < 32 for char in origin):
        raise ValueError('Invalid repository remote')
    return origin


def deploy_command(target, revision, origin, remote, config, adopt=False):
    q = shlex.quote
    remote_ref = q('refs/heads/' + config['branch'])
    origin_option = '' if config['remote'] == 'origin' else ' --origin ' + q(config['remote'])
    adopt_option = ' --adopt-known' if adopt else ''
    return remote_prefix(target) + f'''
trap 'rm -f {remote}' EXIT
if [ -e "$target" ]; then
  test "$(git -C "$target" rev-parse --show-toplevel)" = "$target"
  test -z "$(git -C "$target" status --porcelain)"
  test "$(git -C "$target" branch --show-current)" = {q(config['branch'])}
  test "$(git -C "$target" config --get {q("remote." + config["remote"] + ".url")})" = {q(origin)}
  git -C "$target" fetch {q(remote)} {remote_ref}
  test "$(git -C "$target" rev-parse FETCH_HEAD)" = {q(revision)}
  git -C "$target" merge-base --is-ancestor HEAD FETCH_HEAD
  git -C "$target" merge --ff-only FETCH_HEAD
else
  mkdir -p "$(dirname "$target")"
  git clone{origin_option} --branch {q(config['branch'])} {q(remote)} "$target"
  git -C "$target" remote set-url {q(config['remote'])} {q(origin)}
fi
test "$(git -C "$target" rev-parse HEAD)" = {q(revision)}
"$target/scripts/install" --profile {q(target['profile'])}{adopt_option}
"$target/scripts/audit" --allow-unmanaged
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('targets', nargs='*', help='Configured targets; defaults to all')
    parser.add_argument('--fleet-config', type=Path)
    parser.add_argument('--adopt-known', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='List targets only; no network or mutations')
    args = parser.parse_args()
    config = settings()
    selected = targets(args.fleet_config, args.targets)
    if git('status', '--porcelain') or git('branch', '--show-current') != config['branch']:
        raise ValueError('Deploy from a clean checkout of the configured branch')
    revision = git('rev-parse', 'HEAD')
    origin = safe_origin(git('config', '--get', 'remote.' + config['remote'] + '.url'))
    if args.dry_run:
        for name, target in selected.items():
            print(f"Target {name}: {target['ssh_host']} / {target['path']} / {target['profile']}")
        return
    subprocess.run(['git', '-C', str(REPO), 'fetch', config['remote'], config['branch']],
                   check=True, timeout=60, env=os.environ | {'GIT_TERMINAL_PROMPT': '0'})
    if git('rev-parse', 'FETCH_HEAD') != revision:
        raise ValueError('Deploy exactly the published branch revision; push or update first')
    with tempfile.TemporaryDirectory(prefix='agents-config-bundle-') as temporary:
        bundle = Path(temporary) / 'source.bundle'
        subprocess.run(['git', '-C', str(REPO), 'bundle', 'create', str(bundle),
                        'refs/heads/' + config['branch']], check=True, timeout=60)
        for name, target in selected.items():
            remote = '/tmp/agents-config-' + uuid.uuid4().hex + '.bundle'
            print('Deploying ' + revision + ' to target ' + name, flush=True)
            try:
                subprocess.run(SCP + [str(bundle), f"{target['ssh_host']}:{remote}"], check=True, timeout=120)
                subprocess.run(SSH + [target['ssh_host'], deploy_command(target, revision, origin, remote, config, args.adopt_known)],
                               check=True, timeout=240)
            finally:
                subprocess.run(SSH + [target['ssh_host'], 'rm -f ' + shlex.quote(remote)], timeout=30, check=False)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
