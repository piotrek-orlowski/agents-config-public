"""Exercise additions and deletions through a real local Git remote."""
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
PROFILE = 'mac' if platform.system() == 'Darwin' else 'linux'

class UpdateFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.author = self.base/'author'
        self.repo = self.base/'checkout'
        self.home = self.base/'home'
        self.author.mkdir();self.home.mkdir()
        for name in ['manage.py','inventory.py','update.py','deploy.py','audit.py','settings.py','fleet.py']:
            (self.author/'scripts').mkdir(exist_ok=True)
            shutil.copy2(SOURCE/'scripts'/name,self.author/'scripts'/name)
        for runtime in ['claude','codex']:
            (self.author/f'adapters/{runtime}/skills').mkdir(parents=True)
            (self.author/f'adapters/{runtime}/skills/.gitkeep').touch()
        (self.author/'profiles').mkdir()
        (self.author/'profiles'/f'{PROFILE}.toml').write_text(f'name = "{PROFILE}"\nos = "{platform.system().lower()}"\n')
        (self.author/'migration-known.json').write_text('{}')
        (self.author/'.gitignore').write_text('__pycache__/\n*.pyc\n')
        self.skill('original')
        self.git(self.author,'init','-q')
        self.git(self.author,'symbolic-ref','HEAD','refs/heads/main')
        self.commit('initial')
        self.git(self.base,'clone','-q','--bare',str(self.author),str(self.base/'origin.git'))
        self.git(self.author,'remote','add','origin',str(self.base/'origin.git'))
        self.git(self.base,'clone','-q',str(self.base/'origin.git'),str(self.repo))

    def tearDown(self):
        self.temp.cleanup()

    def git(self,cwd,*args,ok=True):
        proc=subprocess.run(['git','-C',str(cwd),*args],capture_output=True,text=True)
        if ok:self.assertEqual(proc.returncode,0,proc.stderr)
        return proc

    def skill(self,name):
        p=self.author/'skills'/name;p.mkdir(parents=True)
        (p/'SKILL.md').write_text(f'---\nname: {name}\ndescription: A test skill.\n---\nTest.\n')

    def commit(self,message):
        self.git(self.author,'add','.')
        self.git(self.author,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','commit','-qm',message)

    def publish(self):
        self.git(self.author,'push','-q','origin','main')

    def update(self,*args,ok=True):
        proc=subprocess.run([sys.executable,str(self.repo/'scripts/update.py'),
                             '--home',str(self.home),'--profile',PROFILE,*args],capture_output=True,text=True)
        if ok:self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
        else:self.assertNotEqual(proc.returncode,0,proc.stdout+proc.stderr)
        return proc

class UpdateTests(UpdateFixture):
    def test_fetch_add_edit_delete_preserves_unmanaged(self):
        self.update()
        unmanaged=self.home/'.claude/skills/unrelated';unmanaged.mkdir()
        (unmanaged/'SKILL.md').write_text('leave me')
        self.skill('new-skill');self.commit('add skill');self.publish();self.update()
        for root in ['.agents/skills','.claude/skills']:
            self.assertTrue((self.home/root/'new-skill/SKILL.md').is_file())
        (self.author/'skills/new-skill/SKILL.md').write_text('updated skill body')
        self.commit('edit skill');self.publish();self.update()
        self.assertEqual((self.home/'.agents/skills/new-skill/SKILL.md').read_text(),'updated skill body')
        self.git(self.author,'rm','-qr','skills/new-skill');self.commit('remove skill');self.publish();self.update()
        for root in ['.agents/skills','.claude/skills']:
            self.assertFalse((self.home/root/'new-skill').is_symlink())
        self.assertEqual((unmanaged/'SKILL.md').read_text(),'leave me')
        state=json.loads((self.home/'.local/state/agents-config-public/manifest.json').read_text())
        self.assertFalse(any('new-skill' in p for p in state['links']))

    def test_dirty_checkout_is_not_changed(self):
        (self.repo/'uncommitted.txt').write_text('local work')
        self.update(ok=False)
        self.assertFalse((self.home/'.agents').exists())
        self.assertEqual((self.repo/'uncommitted.txt').read_text(),'local work')

    def test_dry_run_does_not_fetch_or_install(self):
        before=self.git(self.repo,'rev-parse','HEAD').stdout
        self.skill('later');self.commit('later source');self.publish()
        self.update('--dry-run')
        self.assertEqual(before,self.git(self.repo,'rev-parse','HEAD').stdout)
        self.assertEqual(list(self.home.iterdir()),[])

    def test_divergence_stops_before_install(self):
        self.skill('upstream');self.commit('upstream');self.publish()
        (self.repo/'local.txt').write_text('local commit')
        self.git(self.repo,'add','local.txt')
        self.git(self.repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','commit','-qm','local')
        self.update(ok=False)
        self.assertFalse((self.home/'.agents').exists())

    def test_no_fetch_applies_committed_checkout_offline(self):
        self.git(self.repo,'remote','set-url','origin',str(self.base/'missing.git'))
        self.update('--no-fetch')
        self.assertTrue((self.home/'.agents/skills/original').is_symlink())

    def test_unpushed_commits_stop_normal_update(self):
        (self.repo/'unpublished.txt').write_text('not published')
        self.git(self.repo,'add','unpublished.txt')
        self.git(self.repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','commit','-qm','unpublished')
        self.update(ok=False)
        self.assertFalse((self.home/'.agents').exists())

    def test_expected_revision_stops_a_moving_remote_before_checkout_changes(self):
        self.update()
        before=self.git(self.repo,'rev-parse','HEAD').stdout.strip()
        manifest=self.home/'.local/state/agents-config-public/manifest.json'
        previous=manifest.read_bytes()
        self.skill('newer');self.commit('concurrent publication');self.publish()
        result=self.update('--expected-revision',before,ok=False)
        self.assertIn('checkout was not changed',result.stderr)
        self.assertEqual(self.git(self.repo,'rev-parse','HEAD').stdout.strip(),before)
        self.assertEqual(manifest.read_bytes(),previous)
        self.assertFalse((self.repo/'skills/newer').exists())

    def test_offline_fleet_request_stops_before_install(self):
        self.update('--no-fetch','--fleet',ok=False)
        self.assertFalse((self.home/'.agents').exists())

    def test_configured_branch_and_remote(self):
        (self.repo/'framework.toml').write_text('branch = "stable"\nremote = "upstream"\n')
        self.git(self.repo,'switch','-qc','stable')
        self.git(self.repo,'add','framework.toml')
        self.git(self.repo,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 '-c','commit.gpgsign=false','commit','-qm','configure published branch')
        self.git(self.repo,'remote','rename','origin','upstream')
        self.git(self.repo,'push','-q','upstream','stable')
        self.update()
        self.assertTrue((self.home/'.agents/skills/original').is_symlink())

if __name__=='__main__':
    unittest.main()
