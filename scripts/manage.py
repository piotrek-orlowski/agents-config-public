"""Install managed skill directory links with explicit adoption and rollback."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib
import re
from inventory import files, executable_modes
from settings import state_directory

REPO = Path(__file__).resolve().parents[1]
MANAGED_PATH = re.compile(r'\.(?:agents|codex|claude)/skills/[a-z0-9]+(?:-[a-z0-9]+)*\Z')
BACKUP_NAME = re.compile(r'\d{8}T\d{6}\.\d{6}Z\Z')

def install_path(home,rel):
    if not isinstance(rel,str) or not MANAGED_PATH.fullmatch(rel):
        raise ValueError(f'Invalid installation path: {rel}')
    path=home/rel
    for parent in path.parents:
        if parent == home:
            break
        if parent.is_symlink():
            raise ValueError(f'Refusing symlinked install parent: {parent}')
    return path

def validate_manifest(state):
    if state is None:
        return
    if not isinstance(state,dict) or not isinstance(state.get('schema'),int) or state['schema'] not in {1,2,3}:
        raise ValueError('Invalid installation manifest schema')
    if state.get('repository') != str(REPO):
        raise ValueError('Installation manifest belongs to another repository; review before reinstalling')
    if not isinstance(state.get('profile'),str) or not re.fullmatch(r'[a-z0-9-]+',state['profile']):
        raise ValueError('Invalid installation manifest profile')
    if not isinstance(state.get('revision'),str) or not re.fullmatch(r'[a-f0-9]{40,64}',state['revision']):
        raise ValueError('Invalid installation manifest revision')
    links=state.get('links')
    if not isinstance(links,dict):
        raise ValueError('Invalid installation manifest links')
    for rel,target in links.items():
        if not isinstance(rel,str) or not MANAGED_PATH.fullmatch(rel):
            raise ValueError(f'Invalid manifest path: {rel}')
        name=Path(rel).name
        runtime='claude' if rel.startswith('.claude/') else 'codex'
        allowed={str(REPO/'skills'/name),str(REPO/f'adapters/{runtime}/skills'/name)}
        if not isinstance(target,str) or target not in allowed:
            raise ValueError(f'Invalid manifest target: {rel}')
    for field in ['content_hashes','executables']:
        values=state.get(field,{})
        if not isinstance(values,dict) or any(not isinstance(v,dict) for v in values.values()):
            raise ValueError(f'Invalid manifest {field}')

def load(path):
    if path.is_symlink():
        raise ValueError(f'Refusing symlinked state file: {path}')
    return json.loads(path.read_text()) if path.exists() else None

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)

def exists(path):
    return path.exists() or path.is_symlink()

def revision():
    return subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip()

def desired(profile):
    shared = {p.name: p for p in sorted((REPO/'skills').glob('*')) if (p/'SKILL.md').is_file()}
    result = {}
    runtimes = profile.get('runtimes', ['codex', 'claude'])
    if not isinstance(runtimes, list) or not runtimes or any(r not in {'codex', 'claude'} for r in runtimes):
        raise ValueError('Profile runtimes must contain codex, claude, or both')
    for runtime in runtimes:
        root = '.agents/skills' if runtime == 'codex' else '.claude/skills'
        variants = {p.name: p for p in (REPO/f'adapters/{runtime}/skills').glob('*') if (p/'SKILL.md').is_file()}
        for name, source in (shared | variants).items():
            if name not in profile.get('exclude_skills', []):
                result[f'{root}/{name}'] = str(source)
    return result

def profile_data(name, seen=()):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise ValueError('Invalid profile name')
    if name in seen:
        raise ValueError('Profile inheritance cycle')
    if '/' in name or name.startswith('.'):
        raise ValueError('Invalid profile name')
    data = tomllib.loads((REPO/'profiles'/f'{name}.toml').read_text())
    if data.get('extends'):
        parent = profile_data(data.pop('extends'), (*seen, name))
        parent.update(data)
        return parent
    return data

def plan(home, profile, old, adopt):
    links = desired(profile)
    previous = (old or {}).get('links', {})
    names = {Path(p).name for p in links}
    # Remove only known legacy copies of skills now installed through .agents.
    legacy = {f'.codex/skills/{n}' for n in names if exists(home/'.codex/skills'/n)}
    keys = sorted(set(links) | set(previous) | legacy)
    known = load(REPO/'migration-known.json') or {}
    operations = []
    for rel in keys:
        path = install_path(home,rel)
        target = links.get(rel)
        current = os.readlink(path) if path.is_symlink() else None
        if path.is_symlink() and current == target:
            continue
        if exists(path):
            if rel in previous:
                if not path.is_symlink() or current != previous[rel]:
                    raise ValueError(f'Managed path was changed locally: {path}')
            else:
                if not adopt:
                    raise ValueError(f'Existing unmanaged path; use --adopt-known after review: {path}')
                if not path.is_dir() or files(path) not in known.get(Path(rel).name, []):
                    raise ValueError(f'Unfamiliar local content; preserve and review first: {path}')
        operations.append({'path': rel, 'target': target, 'had_original': exists(path)})
    return links, operations

def check(home, profile, state):
    expected = desired(profile)
    errors = []
    if not state:
        errors.append('No installed manifest')
    else:
        if state['links'] != expected:
            errors.append('Installed manifest differs from selected profile/repository')
        if state['revision'] != revision():
            errors.append('Repository HEAD differs from installed revision; run install')
    for rel, target in expected.items():
        p = home/rel
        if not p.is_symlink() or os.readlink(p) != target or not (p/'SKILL.md').is_file():
            errors.append(f'Incorrect or broken skill link: {p}')
        if rel.startswith('.agents/') and exists(home/'.codex/skills'/p.name):
            errors.append(f'Duplicate legacy Codex path: {p.name}')
    print(json.dumps({'profile': profile['name'], 'revision': revision(), 'links': len(expected), 'errors': errors}, indent=2))
    return bool(errors)

def restore(home, state_dir, journal):
    validate_manifest(journal.get('previous_manifest'))
    backup=Path(journal['backup'])
    if backup.parent != state_dir/'backups' or not BACKUP_NAME.fullmatch(backup.name) or backup.is_symlink():
        raise ValueError('Invalid rollback backup location')
    ops = journal['operations']
    if not isinstance(ops,list):
        raise ValueError('Invalid rollback operations')
    seen=set()
    for op in ops:
        rel=op.get('path')
        if not isinstance(rel,str) or not MANAGED_PATH.fullmatch(rel) or rel in seen:
            raise ValueError('Invalid rollback installation path')
        seen.add(rel)
        install_path(home,rel)
        install_path(backup,rel)
        if not isinstance(op.get('had_original'),bool):
            raise ValueError('Invalid rollback original-entry flag')
        if op.get('target') is not None:
            candidate=dict(journal.get('previous_manifest') or {},schema=3,repository=str(REPO),
                           profile='rollback',revision='0'*40,links={rel:op['target']})
            validate_manifest(candidate)
    # Preflight everything before touching the installed state.
    for op in ops:
        p = home/op['path']
        if exists(p) and (not p.is_symlink() or os.readlink(p) != op['target']):
            raise ValueError(f'Rollback refuses locally changed path: {p}')
        if op['had_original'] and not exists(Path(journal['backup'])/op['path']):
            raise ValueError(f'Missing original backup: {op["path"]}')
    for op in reversed(ops):
        p = home/op['path']
        if p.is_symlink():
            p.unlink()
        backup = Path(journal['backup'])/op['path']
        if op['had_original']:
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup), str(p))
    if journal['previous_manifest']:
        write(state_dir/'manifest.json', journal['previous_manifest'])
    else:
        (state_dir/'manifest.json').unlink(missing_ok=True)
    journal['rolled_back'] = True
    write(Path(journal['backup'])/'journal.json', journal)
    if journal.get('previous_latest'):
        write(state_dir/'latest.json', journal['previous_latest'])
    else:
        (state_dir/'latest.json').unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'check', 'rollback'])
    parser.add_argument('--profile')
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--adopt-known', action='store_true')
    args = parser.parse_args()
    home = args.home.expanduser().absolute()
    state_dir = state_directory(home)
    state = load(state_dir/'manifest.json')
    validate_manifest(state)
    if args.action == 'rollback':
        latest = load(state_dir/'latest.json')
        if not latest:
            raise ValueError('No installation to roll back')
        journal_path=Path(latest['journal'])
        if (journal_path.name != 'journal.json' or journal_path.parent.parent != state_dir/'backups'
                or not BACKUP_NAME.fullmatch(journal_path.parent.name)):
            raise ValueError('Invalid rollback journal location')
        journal = load(journal_path)
        if args.dry_run:
            print(json.dumps(journal, indent=2)); return 0
        restore(home, state_dir, journal)
        print('Restored previous skill installation'); return 0
    name = args.profile or (state or {}).get('profile')
    if not name:
        raise ValueError('--profile is required for first installation')
    profile = profile_data(name)
    if profile['os'] != platform.system().lower():
        raise ValueError(f'Profile {name} requires {profile["os"]}')
    if args.action == 'check':
        return check(home, profile, state)
    links, ops = plan(home, profile, state, args.adopt_known)
    if args.dry_run:
        print(json.dumps({'profile':name,'operations':ops,'links':len(links)}, indent=2)); return 0
    if not ops and state and state.get('schema') == 3 and state['revision'] == revision() and state['profile'] == name:
        print('Already installed; no changes'); return 0
    state_dir.mkdir(parents=True, exist_ok=True)
    # A directory lock prevents two installers from moving the same originals.
    lock = state_dir/'install.lock'
    lock.mkdir()
    try:
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        backup = state_dir/'backups'/stamp
        backup.mkdir(parents=True, mode=0o700)
        journal = {'backup':str(backup),'previous_manifest':state,'previous_latest':load(state_dir/'latest.json'),'operations':ops}
        write(backup/'journal.json', journal)
        completed = []
        try:
            for op in ops:
                p = home/op['path']
                p.parent.mkdir(parents=True, exist_ok=True)
                if op['had_original']:
                    dst = backup/op['path']; dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(p), str(dst))
                completed.append(op)
                if op['target']:
                    p.symlink_to(op['target'], target_is_directory=True)
            content_hashes = {rel: files(Path(target)) for rel, target in links.items()}
            executables = {rel: executable_modes(Path(target),content_hashes[rel]) for rel,target in links.items()}
            write(state_dir/'manifest.json', {'schema':3,'profile':name,'revision':revision(),'repository':str(REPO),'links':links,'content_hashes':content_hashes,'executables':executables})
            write(state_dir/'latest.json', {'journal':str(backup/'journal.json')})
        except BaseException:
            partial = dict(journal, operations=completed)
            restore(home, state_dir, partial)
            raise
        print(f'Installed {len(links)} links; backup: {backup}')
        return check(home, profile, load(state_dir/'manifest.json'))
    finally:
        lock.rmdir()

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, FileExistsError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)
