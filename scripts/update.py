"""Fast-forward published sources and reconcile local or configured fleet skills."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from fleet import pull
from settings import REPO, settings, targets


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', help='Defaults to the installed profile')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--no-fetch', action='store_true')
    parser.add_argument('--expected-revision')
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument('--fleet', action='store_true', help='Update local installation, then configured SSH targets')
    scope.add_argument('--bundle-fleet', action='store_true', help='Update locally, then transfer published Git history to SSH targets')
    parser.add_argument('--fleet-config', type=Path)
    parser.add_argument('--target', action='append', default=[], help='Select a configured target; repeat as needed')
    parser.add_argument('--dry-run', action='store_true', help='Preview only; no network or mutations')
    args = parser.parse_args()
    config = settings()
    if (args.fleet_config or args.target) and not (args.fleet or args.bundle_fleet):
        raise ValueError('--fleet-config and --target require a fleet mode')
    selected = targets(args.fleet_config, args.target) if args.fleet or args.bundle_fleet else {}
    if git('status', '--porcelain'):
        raise ValueError('Commit or preserve repository edits before updating')
    if git('branch', '--show-current') != config['branch']:
        raise ValueError(f"Run update from {config['branch']}; preserve other branch work first")
    if args.no_fetch and selected:
        raise ValueError('Fleet updates require a published revision; omit --no-fetch')
    if not args.no_fetch and not args.dry_run:
        subprocess.run(['git', '-C', str(REPO), 'fetch', config['remote'], config['branch']],
                       check=True, timeout=60, env=os.environ | {'GIT_TERMINAL_PROMPT': '0'})
        published = git('rev-parse', 'FETCH_HEAD')
        if args.expected_revision and published != args.expected_revision:
            raise ValueError(f'Published revision is {published}, expected {args.expected_revision}; checkout was not changed')
        subprocess.run(['git', '-C', str(REPO), 'merge', '--ff-only', 'FETCH_HEAD'], check=True, timeout=30)
        if git('rev-parse', 'HEAD') != published:
            raise ValueError('Push local commits before updating, or use --no-fetch for a local installation')
    if args.expected_revision and git('rev-parse', 'HEAD') != args.expected_revision:
        raise ValueError('Current checkout does not match --expected-revision')
    options = ['--home', str(args.home)]
    if args.profile:
        options += ['--profile', args.profile]
    install = [sys.executable, str(REPO / 'scripts/manage.py'), 'install', *options]
    if args.dry_run:
        subprocess.run(install + ['--dry-run'], check=True)
        print('Dry run: current checkout only; no fetch, installation, or fleet deployment.')
        for name, target in selected.items():
            print(f"Target {name}: {target['ssh_host']} / {target['path']} / {target['profile']}")
        return
    subprocess.run(install, check=True)
    subprocess.run([sys.executable, str(REPO / 'scripts/manage.py'), 'check', *options], check=True)
    subprocess.run([sys.executable, str(REPO / 'scripts/audit.py'), '--home', str(args.home), '--allow-unmanaged'], check=True)
    if args.fleet:
        for name, target in selected.items():
            print('Updating target ' + name, flush=True)
            pull(target, git('rev-parse', 'HEAD'))
    elif args.bundle_fleet:
        command = [sys.executable, str(REPO / 'scripts/deploy.py')]
        if args.fleet_config:
            command += ['--fleet-config', str(args.fleet_config)]
        subprocess.run(command + list(selected), check=True)
    print('Updated additions, edits, and removals at ' + git('rev-parse', 'HEAD'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
