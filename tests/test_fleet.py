"""Run fleet commands through local SSH/SCP substitutes and real Git bundles."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from test_update import UpdateFixture, PROFILE


class FleetTests(UpdateFixture):
    def setUp(self):
        super().setUp()
        self.remote_home = self.base/'remote-home'
        self.remote_home.mkdir()
        self.bin = self.base/'bin'
        self.bin.mkdir()
        self.log = self.base/'transport.log'
        # The substitutes execute the generated POSIX commands against a disposable home.
        self.script('ssh', '''
import subprocess
env = os.environ | {'HOME': os.environ['TEST_REMOTE_HOME']}
raise SystemExit(subprocess.run(['/bin/sh', '-c', sys.argv[-1]], env=env).returncode)
''')
        self.script('scp', '''
import shutil
shutil.copy2(sys.argv[-2], sys.argv[-1].split(':', 1)[1])
''')
        self.env = os.environ | {'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                                 'TEST_REMOTE_HOME': str(self.remote_home), 'TEST_TRANSPORT_LOG': str(self.log)}
        # Existing shell wrappers also need to travel in the bundle.
        source = Path(__file__).resolve().parents[1]
        for name in ['install', 'check', 'audit', 'update', 'rollback']:
            import shutil
            shutil.copy2(source/'scripts'/name, self.author/'scripts'/name)
        self.commit('add shell wrappers')
        self.publish()
        self.git(self.repo, 'pull', '-q', '--ff-only')
        self.config = self.base/'private-fleet.toml'
        self.config.write_text(f'[targets.worker]\nssh_host = "test-worker"\nprofile = "{PROFILE}"\npath = "collections/skill source"\n')
        self.checkout = self.remote_home/'collections/skill source'
        # Keep a credential-free transferable origin while Git uses a local fixture remote.
        self.git(self.repo, 'remote', 'set-url', 'origin', 'https://example.invalid/skills.git')
        self.git(self.repo, 'config', f'url.{self.base}/.insteadOf', 'https://example.invalid/')
        # Match the mapped remote path without contacting a server.
        (self.base/'skills.git').symlink_to(self.base/'origin.git', target_is_directory=True)

    def script(self, name, body):
        path = self.bin/name
        path.write_text('#!' + sys.executable + '\nimport os, sys\n'
                        'with open(os.environ["TEST_TRANSPORT_LOG"], "a") as log:\n'
                        '    log.write(sys.argv[0] + "\\n")\n' + body)
        path.chmod(0o755)

    def deploy(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(self.repo/'scripts/deploy.py'),
                                 '--fleet-config', str(self.config), *args],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def test_bundle_bootstrap_repeat_and_audit(self):
        self.deploy('worker')
        expected = self.git(self.repo, 'rev-parse', 'HEAD').stdout.strip()
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD').stdout.strip(), expected)
        self.assertEqual(self.git(self.checkout, 'remote', 'get-url', 'origin').stdout.strip(), 'https://example.invalid/skills.git')
        manifest = self.remote_home/'.local/state/agents-config-public/manifest.json'
        self.assertEqual(json.loads(manifest.read_text())['revision'], expected)
        self.deploy('worker')
        self.assertTrue((self.remote_home/'.agents/skills/original').is_symlink())

    def test_dry_run_never_contacts_targets_or_changes_local_checkout(self):
        before = self.git(self.repo, 'rev-parse', 'HEAD').stdout
        self.deploy('--dry-run')
        self.assertFalse(self.log.exists())
        self.assertFalse(self.checkout.exists())
        self.assertEqual(self.git(self.repo, 'rev-parse', 'HEAD').stdout, before)

    def test_unknown_target_and_invalid_host_fail_before_transport(self):
        self.deploy('unknown', ok=False)
        self.config.write_text(f'[targets.worker]\nssh_host = "-oProxyCommand=bad"\nprofile = "{PROFILE}"\npath = "skills"\n')
        self.deploy('worker', ok=False)
        self.assertFalse(self.log.exists())

    def test_credential_bearing_origin_is_refused_before_transport(self):
        # Dummy values exercise rejection; no credential store is involved.
        for origin in ['https://user:dummy@example.invalid/skills.git',  # pragma: allowlist secret (synthetic rejection fixture)
                       'https://example.invalid/skills.git?access=dummy',
                       'ssh://user:dummy@example.invalid/skills.git']:  # pragma: allowlist secret (synthetic rejection fixture)
            self.git(self.repo, 'remote', 'set-url', 'origin', origin)
            self.deploy('worker', ok=False)
        self.assertFalse(self.log.exists())

    def test_remote_dirty_checkout_is_preserved(self):
        self.deploy('worker')
        (self.checkout/'local-work').write_text('keep')
        self.deploy('worker', ok=False)
        self.assertEqual((self.checkout/'local-work').read_text(), 'keep')

    def test_pull_fleet_pins_revision_and_uses_profile(self):
        self.deploy('worker')
        # Install a repository-local URL rewrite for the disposable target's Git fetch.
        self.git(self.checkout, 'config', f'url.{self.base}/.insteadOf', 'https://example.invalid/')
        result = subprocess.run([sys.executable, str(self.repo/'scripts/update.py'),
                                 '--home', str(self.home), '--profile', PROFILE,
                                 '--fleet', '--fleet-config', str(self.config), '--target', 'worker'],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for home in [self.home, self.remote_home]:
            self.assertTrue((home/'.agents/skills/original').is_symlink())

    def test_remote_divergence_stops_before_checkout_change(self):
        self.deploy('worker')
        (self.checkout/'local-commit').write_text('keep')
        self.git(self.checkout, 'add', 'local-commit')
        self.git(self.checkout, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', 'commit', '-qm', 'local')
        before = self.git(self.checkout, 'rev-parse', 'HEAD').stdout
        self.deploy('worker', ok=False)
        self.assertEqual(self.git(self.checkout, 'rev-parse', 'HEAD').stdout, before)
        self.assertEqual((self.checkout/'local-commit').read_text(), 'keep')
