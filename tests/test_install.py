"""Exercise installation against disposable source trees and home directories."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from test_update import UpdateFixture, PROFILE


class InstallTests(UpdateFixture):
    def run_cmd(self, action='install', *args, ok=True):
        result = subprocess.run([sys.executable, str(self.repo/'scripts/manage.py'), action,
                                 '--home', str(self.home), '--profile', PROFILE, *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_fresh_install_is_idempotent_and_rolls_back(self):
        self.run_cmd('install', '--dry-run')
        self.assertEqual(list(self.home.iterdir()), [])
        self.run_cmd()
        self.run_cmd('check')
        state = self.home/'.local/state/agents-config-public'
        before = (state/'latest.json').read_bytes()
        self.run_cmd()
        self.assertEqual((state/'latest.json').read_bytes(), before)
        self.assertTrue((self.home/'.agents/skills/original').is_symlink())
        self.run_cmd('rollback')
        self.assertFalse((self.home/'.agents/skills/original').is_symlink())
        self.assertFalse((state/'manifest.json').exists())

    def test_runtime_override_and_profile_exclusion(self):
        adapter = self.repo/'adapters/codex/skills/original'
        adapter.mkdir()
        (adapter/'SKILL.md').write_text('Codex variant')
        self.run_cmd()
        self.assertEqual((self.home/'.agents/skills/original').resolve(), adapter)
        self.assertEqual((self.home/'.claude/skills/original').resolve(), self.repo/'skills/original')
        profile = self.repo/'profiles'/f'{PROFILE}.toml'
        with profile.open('a') as handle:
            handle.write('exclude_skills = ["original"]\n')
        self.run_cmd()
        self.assertFalse((self.home/'.agents/skills/original').is_symlink())
        self.assertFalse((self.home/'.claude/skills/original').is_symlink())

    def test_reviewed_adoption_and_backup_restore(self):
        sys.path.insert(0, str(self.repo/'scripts'))
        from inventory import files
        old = self.home/'.codex/skills/original'
        old.parent.mkdir(parents=True)
        shutil.copytree(self.repo/'skills/original', old)
        (self.repo/'migration-known.json').write_text(json.dumps({'original': [files(old)]}))
        self.run_cmd(ok=False)
        self.run_cmd('install', '--adopt-known')
        self.assertFalse(old.exists())
        self.run_cmd('rollback')
        self.assertTrue((old/'SKILL.md').is_file())
        self.assertFalse(old.is_symlink())

    def test_unfamiliar_content_prevents_all_replacements(self):
        old = self.home/'.claude/skills/original'
        old.mkdir(parents=True)
        (old/'SKILL.md').write_text('private local work')
        self.run_cmd('install', '--adopt-known', ok=False)
        self.assertEqual((old/'SKILL.md').read_text(), 'private local work')
        self.assertFalse((self.home/'.agents').exists())

    def test_changed_link_blocks_install_and_rollback(self):
        self.run_cmd()
        link = self.home/'.agents/skills/original'
        link.unlink()
        link.mkdir()
        (link/'SKILL.md').write_text('new local work')
        self.run_cmd(ok=False)
        self.run_cmd('rollback', ok=False)
        self.assertEqual((link/'SKILL.md').read_text(), 'new local work')

    def test_symlink_parent_cannot_redirect_installation(self):
        outside = self.home/'outside'
        outside.mkdir()
        (self.home/'.agents').symlink_to(outside)
        self.run_cmd(ok=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_cannot_redirect_paths_or_repository(self):
        self.run_cmd()
        path = self.home/'.local/state/agents-config-public/manifest.json'
        state = json.loads(path.read_text())
        state['links']['../outside'] = str(self.repo/'skills/original')
        path.write_text(json.dumps(state))
        self.assertIn('Invalid manifest path', self.run_cmd(ok=False).stderr)
        del state['links']['../outside']
        state['repository'] = '/unrelated/repository'
        path.write_text(json.dumps(state))
        self.assertIn('another repository', self.run_cmd(ok=False).stderr)

    def test_single_runtime_and_separate_state_namespace(self):
        (self.repo/'framework.toml').write_text('state_name = "test-collection"\n')
        profile = self.repo/'profiles'/f'{PROFILE}.toml'
        with profile.open('a') as handle:
            handle.write('runtimes = ["codex"]\n')
        self.run_cmd()
        self.assertTrue((self.home/'.local/state/test-collection/manifest.json').exists())
        self.assertFalse((self.home/'.claude').exists())

    def test_profile_inheritance_cycle_fails_without_changes(self):
        (self.repo/'profiles'/f'{PROFILE}.toml').write_text(f'extends = "{PROFILE}"\n')
        self.assertIn('inheritance cycle', self.run_cmd(ok=False).stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_rollback_rejects_outside_journal(self):
        self.run_cmd()
        state = self.home/'.local/state/agents-config-public'
        outside = self.home/'outside'
        outside.write_text('not a journal')
        (state/'latest.json').write_text(json.dumps({'journal': str(outside)}))
        self.assertIn('Invalid rollback journal', self.run_cmd('rollback', ok=False).stderr)
        self.assertEqual(outside.read_text(), 'not a journal')
