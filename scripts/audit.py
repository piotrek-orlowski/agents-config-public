"""Read-only audit of managed skill links, file fingerprints, and outside additions."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from inventory import ROOTS, files, executable_modes
from settings import state_directory
from manage import REPO, desired, load, profile_data, revision, validate_manifest

MANAGED_PATH = re.compile(r'\.(?:agents|codex|claude)/skills/[a-z0-9]+(?:-[a-z0-9]+)*\Z')

def audit(home):
    findings = []
    def add(kind, path, advice, **details):
        findings.append(dict(kind=kind,path=str(path),advice=advice,**details))
    state = load(state_directory(home)/'manifest.json')
    if not state:
        add('missing_manifest',home,'Run scripts/install --profile NAME after reviewing existing skills.')
        return {'revision':revision(),'managed_links':0,'findings':findings}
    try:
        validate_manifest(state)
    except ValueError as error:
        kind='invalid_manifest_path' if 'Invalid manifest path:' in str(error) else 'invalid_manifest'
        add(kind,home,str(error)+'. Preserve the state and review it before running an installer.')
        return {'revision':revision(),'managed_links':0,'findings':findings}
    expected = desired(profile_data(state['profile']))
    links = state.get('links',{})
    snapshots = state.get('content_hashes',{})
    if state.get('schema') != 3:
        add('missing_fingerprints',home,'Run scripts/update to record supporting-file fingerprints for this installation.')
    if state.get('repository') != str(REPO):
        add('repository_mismatch',home,'Review the source checkout and rerun scripts/update from the canonical repository.')
    if state.get('revision') != revision():
        add('revision_mismatch',home,'Run scripts/update after committing and publishing intended changes.')
    dirty = subprocess.check_output(['git','-C',str(REPO),'status','--porcelain'],text=True).strip()
    if dirty:
        add('uncommitted_source_changes',REPO,'Review source edits, commit and push intended changes, then run scripts/update.')
    for rel in sorted(set(expected)-set(links)):
        add('pending_source_skill',rel,'Commit and push the source addition, then run scripts/update to install its link.')
    for rel,target in sorted(links.items()):
        if not MANAGED_PATH.fullmatch(rel):
            add('invalid_manifest_path',rel,'Review the manifest; do not use it to scan outside personal skill roots.')
            continue
        p = home/rel
        if rel not in expected:
            add('obsolete_managed_link',p,'Run scripts/update to remove this obsolete managed link.')
            continue
        if target != expected[rel]:
            add('unexpected_manifest_target',p,'Review the manifest target and canonical source before reinstalling.')
            continue
        # A redirected parent is not an authorized content-scanning root.
        if any(parent.is_symlink() for parent in p.parents if parent != home and home in parent.parents):
            add('redirected_install_root',p,'Review the redirected installation root before scanning or updating it.')
            continue
        if not p.is_symlink():
            kind = 'replaced_managed_link' if p.exists() else 'missing_managed_link'
            add(kind,p,'Preserve local files, compare with the repository, and resolve the conflict before running update.')
            continue
        if os.readlink(p) != target:
            add('retargeted_managed_link',p,'Preserve the alternate target and review its content before restoring the managed link.')
            continue
        if not (p/'SKILL.md').is_file():
            add('broken_managed_link',p,'Restore the source from Git, or run update for an intended source deletion.')
            continue
        snapshot = snapshots.get(rel)
        if snapshot is None:
            add('missing_skill_fingerprint',p,'Run scripts/update to record this skill after source review.')
            continue
        current = files(p)
        missing = sorted(set(snapshot)-set(current))
        added = sorted(set(current)-set(snapshot))
        changed = sorted(k for k in set(snapshot)&set(current) if snapshot[k] != current[k])
        if missing or added or changed:
            add('content_drift',p,'Review changes in the source repository; commit and push intended edits, then run update.',
                missing_files=missing,added_files=added,changed_files=changed)
        saved_modes=state.get('executables',{}).get(rel)
        if saved_modes is None:
            add('missing_executable_fingerprint',p,'Run scripts/update to upgrade this installation manifest.')
        else:
            current_modes=executable_modes(p,current)
            mode_changes=sorted(k for k in set(saved_modes)&set(current_modes) if saved_modes[k] != current_modes[k])
            if mode_changes:
                add('executable_mode_drift',p,'Review and restore the intended executable permissions in the source repository.',changed_files=mode_changes)
    for rel in ROOTS:
        root = home/rel
        if root.is_symlink() or root.parent.is_symlink() or not root.is_dir():
            continue
        for p in sorted(root.iterdir()):
            if p.name.startswith('.') or p.name == 'synced':
                continue
            key = f'{rel}/{p.name}'
            if key in links:
                continue
            if (p/'.claude-plugin/plugin.json').is_file() or (p/'.codex-plugin/plugin.json').is_file():
                continue
            # Inspect only entry metadata; do not read or hash unknown skill contents.
            active = (p/'SKILL.md').is_file()
            if active or (p.is_symlink() and not p.exists()):
                add('unmanaged_skill',p,
                    'Review this outside addition with manage-agent-skills. Import its complete skill directory into '
                    'the source repository skills/ or the correct adapter, preserve provenance, commit and push. '
                    'After comparison, move the outside installed copy into a timestamped backup under '
                    'the configured state directory import-backups/, then run scripts/update and scripts/audit. '
                    'Keep the original backup. '
                    'Do not widen adoption rules or delete it automatically.',name=p.name,
                    conflicts_with_source=(p.name in {Path(x).name for x in expected}))
    return {'revision':revision(),'installed_revision':state.get('revision'),
            'profile':state['profile'],'managed_links':len(links),'findings':findings}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--home',type=Path,default=Path.home())
    parser.add_argument('--allow-unmanaged',action='store_true',help='Report outside additions without failing solely for them')
    args = parser.parse_args()
    report = audit(args.home.expanduser().absolute())
    print(json.dumps(report,indent=2))
    fatal = [f for f in report['findings'] if not (args.allow_unmanaged and f['kind']=='unmanaged_skill')]
    return int(bool(fatal))

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except (ValueError,KeyError,json.JSONDecodeError,OSError) as error:
        print(f'ERROR: {error}',file=sys.stderr)
        raise SystemExit(1)
