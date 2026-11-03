"""Audit real temporary installations without touching personal configuration."""
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
from unittest.mock import patch
from test_update import UpdateFixture

class AuditTests(UpdateFixture):
    def report(self,*args):
        result=subprocess.run([sys.executable,str(self.repo/'scripts/audit.py'),
                               '--home',str(self.home),*args],capture_output=True,text=True)
        self.assertIn(result.returncode,[0,1],result.stderr)
        return result.returncode,json.loads(result.stdout)

    def test_clean_installation_has_no_findings(self):
        self.update()
        code,report=self.report()
        self.assertEqual(code,0)
        self.assertEqual(report['findings'],[])

    def test_outside_addition_has_import_advice_and_is_preserved(self):
        self.update()
        p=self.home/'.claude/skills/local-only';p.mkdir()
        (p/'SKILL.md').write_text('outside content')
        before=(p/'SKILL.md').read_bytes()
        code,report=self.report()
        self.assertEqual(code,1)
        outside=[f for f in report['findings'] if f['kind']=='unmanaged_skill']
        self.assertEqual(len(outside),1)
        self.assertIn('commit and push',outside[0]['advice'])
        self.assertEqual((p/'SKILL.md').read_bytes(),before)
        self.assertEqual(self.report('--allow-unmanaged')[0],0)

    def test_supporting_file_drift_is_detected(self):
        helper=self.author/'skills/original/helper.py';helper.write_text('original helper')
        self.commit('add helper');self.publish();self.update()
        (self.repo/'skills/original/helper.py').write_text('changed helper')
        (self.repo/'skills/original/new.txt').write_text('new resource')
        code,report=self.report()
        self.assertEqual(code,1)
        drift=[f for f in report['findings'] if f['kind']=='content_drift']
        self.assertEqual(len(drift),2)
        self.assertEqual(drift[0]['changed_files'],['helper.py'])
        self.assertEqual(drift[0]['added_files'],['new.txt'])
        (self.repo/'skills/original/helper.py').unlink()
        code,report=self.report()
        self.assertTrue(any('helper.py' in f.get('missing_files',[]) for f in report['findings']))

    def test_reviewed_import_becomes_managed_after_backup(self):
        self.update()
        outside=self.home/'.claude/skills/outside';outside.mkdir()
        (outside/'SKILL.md').write_text('---\nname: outside\ndescription: Imported fixture.\n---\nFixture.\n')
        (outside/'helper.py').write_text('helper resource')
        shutil.copytree(outside,self.author/'skills/outside')
        self.commit('formal import');self.publish()
        self.update(ok=False)  # Unknown installed content must remain untouched.
        backup=self.home/'.local/state/agents-config-public/import-backups/reviewed-outside'
        backup.parent.mkdir(parents=True)
        outside.rename(backup)
        self.update()
        self.assertTrue(outside.is_symlink())
        self.assertEqual((backup/'helper.py').read_text(),'helper resource')
        self.assertEqual(self.report()[1]['findings'],[])

    def test_lost_executable_permission_is_detected(self):
        helper=self.author/'skills/original/helper.sh'
        helper.write_text('#!/bin/sh\nexit 0\n');helper.chmod(0o755)
        self.commit('executable helper');self.publish();self.update()
        (self.repo/'skills/original/helper.sh').chmod(0o644)
        code,report=self.report()
        self.assertEqual(code,1)
        drift=[f for f in report['findings'] if f['kind']=='executable_mode_drift']
        self.assertEqual(len(drift),2)
        self.assertEqual(drift[0]['changed_files'],['helper.sh'])

    def test_retargeted_and_missing_links_are_reported(self):
        self.update()
        p=self.home/'.agents/skills/original';p.unlink();p.symlink_to(self.base/'untrusted')
        code,report=self.report()
        self.assertEqual(code,1)
        self.assertTrue(any(f['kind']=='retargeted_managed_link' for f in report['findings']))
        p.unlink()
        self.assertTrue(any(f['kind']=='missing_managed_link' for f in self.report()[1]['findings']))

    def test_system_synced_and_disabled_skills_are_not_import_candidates(self):
        self.update()
        for path in ['.claude/skills/synced/account/test/SKILL.md',
                     '.codex/skills/.system/test/SKILL.md',
                     '.claude/skills/tool-plugin/SKILL.md',
                     '.claude/skills/tool-plugin/.claude-plugin/plugin.json',
                     '.agents/skills/retired/SKILL.md.disabled']:
            p=self.home/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('not managed here')
        self.assertEqual(self.report()[1]['findings'],[])

    def test_nested_symlink_fingerprint_does_not_read_its_target(self):
        sys.path.insert(0,str(self.repo/'scripts'))
        from inventory import files
        skill=self.base/'isolated-skill';skill.mkdir()
        external=self.base/'outside';external.write_text('must not be read')
        (skill/'helper').symlink_to(external)
        with patch.object(Path,'read_bytes',side_effect=AssertionError('unexpected content read')):
            result=files(skill)
        self.assertTrue(result['helper'].startswith('symlink:'))

    def test_manifest_path_cannot_redirect_a_scan(self):
        self.update()
        p=self.home/'.local/state/agents-config-public/manifest.json'
        state=json.loads(p.read_text());state['links']['../../outside']='unexpected'
        p.write_text(json.dumps(state))
        code,report=self.report()
        self.assertEqual(code,1)
        self.assertTrue(any(f['kind']=='invalid_manifest_path' for f in report['findings']))
