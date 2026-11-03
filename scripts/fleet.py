"""Quote remote commands and run bounded, noninteractive SSH operations."""
import shlex
import subprocess

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
SCP = ['scp', '-q', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']


def remote_prefix(target):
    path = shlex.quote(target['path'])
    # Relative paths are relative to the remote login user's home directory.
    location = path if target['path'].startswith('/') else '"$HOME"/' + path
    return f'''set -eu
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"
export GIT_TERMINAL_PROMPT=0
target={location}
'''


def pull(target, revision):
    command = remote_prefix(target) + f'''
cd "$target"
scripts/update --profile {shlex.quote(target['profile'])} --expected-revision {shlex.quote(revision)}
test "$(git rev-parse HEAD)" = {shlex.quote(revision)}
'''
    subprocess.run(SSH + [target['ssh_host'], command], check=True, timeout=240)
