# Fleet setup and operation

Any supported machine can control the fleet. Each target needs its own persistent checkout, home directory, Git, and uv.
The controlling account needs write access to your repository.
Normal target updates need read access to that repository.

## Prepare access

Configure SSH aliases, keys, and host trust outside this repository.
Use your existing authentication system, including a VPN or Tailscale if necessary.
Do not disable host-key checks to bypass a failed connection.

From the same environment that runs your coding agent, test one target:

```sh
ssh -o BatchMode=yes -o ConnectTimeout=10 skill-worker 'command -v git; command -v uv'
```

Both commands must print a path without an interactive password, key passphrase, or host-trust prompt.
The framework adds `~/.local/bin` and `/usr/local/bin` to the remote PATH.
For other tool locations, configure the remote noninteractive environment.
SCP must also work for bundle deployment.
Keep SSH private keys and credential stores outside all skill directories.

Agents need authorization to run fleet commands and access the intended machines.
Fleet configuration lists targets. Its existence does not authorize unrelated changes on those machines.
The scripts use your existing SSH setup without reading its credential files directly.

## Configure targets

```sh
cp fleet.example.toml fleet.local.toml
```

Edit `fleet.local.toml` with your target aliases, profile names, and checkout paths.
A relative path starts at the remote user's home. An absolute path is also accepted.
Use a concrete path without `~`, environment variables, or parent traversal.
Each target runs as the SSH login user and manages that user's skill directories.
The scripts do not use sudo.

```toml
[targets.worker]
ssh_host = "skill-worker"
profile = "linux"
path = "git/agents-config-public"
```

Keep this file private. For configuration elsewhere, pass `--fleet-config /path/to/fleet.toml`.
Ensure that each profile exists on its target.
Ignored local profiles need separate provisioning because Git and bundles do not carry them.

## Bootstrap one target

Publish your reviewed source commit before deployment.
For a normal installation, clone your repository on the target and run `scripts/install --profile NAME` there.
For bundle bootstrap, run:

```sh
uv run --no-project --python 3.12 python scripts/deploy.py worker --dry-run
uv run --no-project --python 3.12 python scripts/deploy.py worker
```

The controlling machine checks the published revision before it creates a bundle.
The target can receive the bundle without Git-server access.
It still needs uv's Python runtime, or network access to obtain that runtime.
A bundle contains all reachable history for the configured branch. It is not a privacy filter.

For an existing checkout, bundle deployment requires a matching origin, a clean configured branch, and fast-forward history.
It checks the bundle revision before it updates that checkout.
A new checkout uses the source repository's credential-free HTTPS or SSH origin.
Origins with embedded HTTPS credentials, passwords, query strings, or fragments are refused.

After bootstrap, run `scripts/check` and `scripts/audit` on the target.
Check skill discovery in the installed runtime.
Once this small test passes, add other targets.

## Update the fleet

```sh
scripts/update --fleet --target worker --dry-run
scripts/update --fleet --target worker
scripts/update --fleet
```

Normal fleet update updates the controller first. Then each target fetches and applies the same published commit.
Each target uses its own Git authentication. Credentials never travel with the update.
Targets stop before checkout changes if the published branch moves beyond the requested revision.

If targets cannot access the Git server, use the explicit bundle fallback:

```sh
scripts/update --bundle-fleet --target worker
```

For remote bootstrap without a controller installation, use `scripts/deploy.py` directly.
All dry runs use local sources only. They do not contact targets or test connectivity.

## Failures and recovery

Targets update in order. A failure stops the command, but earlier installations remain updated.
There is no distributed rollback across machines.
Record the successful targets and the reported revision before a retry.
Fix access or local conflicts, then rerun only the failed targets.

Check interrupted installations on each affected machine.
If an interrupted process leaves `install.lock`, first establish that no installer is active.
Preserve the manifest and backup journal before you remove a stale lock.
Use `scripts/rollback --dry-run` to inspect the latest rollback record.
Never delete backups or credentials to bypass an installation conflict.

The fleet file stays on the controller. Each target retains its own selected profile and installation state.
Container recreation must preserve the checkout, installation state, and home mount that contains the links.
