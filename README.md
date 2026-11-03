# Agent skill configuration

Keep Claude Code and Codex skills in one Git repository. Install them as directory links on macOS and Linux.
Publish changes once, then update each machine from the same commit.

This starter includes the management framework and two skills: `manage-agent-skills` and `remove-agent-skills`.
Add your own skills after you create your copy.
The installer preserves resources, scripts, and runtime variants within each skill directory.

## Requirements

- Git and [uv](https://docs.astral.sh/uv/) on every machine.
- Python 3.12 through uv. The scripts use the standard library and need no project environment.
- A persistent, writable checkout and home directory for each installation.
- Claude Code, Codex, or both, with access to their normal user skill directories.
- For fleet operations, working noninteractive SSH and SCP from the controlling machine to each target.
- For normal updates, noninteractive Git access to your repository on each target.

The coding agent that manages your fleet must have permission and network access to run SSH on the controlling machine.
A connection that works in your terminal can still fail inside an agent sandbox.
Configure SSH keys, host trust, VPN access, and agent forwarding outside this repository.
The framework never provisions those services or copies credentials.
See [fleet setup](docs/fleet.md) for access tests and bundle deployment.

Native Windows is not supported. Use a Linux environment with persistent storage, such as WSL.
Skill installation does not install external tools or services that your own skills need.

## Start with a small installation

Create your own repository from this starter. Clone **your copy**, then enter its checkout.
The example URL is a placeholder.

```sh
git clone https://github.com/YOUR-ACCOUNT/YOUR-REPOSITORY.git agents-config-public
cd agents-config-public
scripts/install --profile linux --dry-run
scripts/install --profile linux
scripts/check
scripts/audit
```

On macOS, use `--profile mac`.
The installer requires a Git commit because the installation manifest records its revision.
Keep the checkout at a stable path. Installed links point into that checkout.
Restart or reload your coding agent after an update to refresh skill discovery.

Existing unmanaged directories block installation. Compare them before you move them to a private backup.
Do not delete them or broaden adoption rules to force installation.
For reviewed legacy copies, see [adoption](docs/management.md#adoption).

## Repository layout

- `skills/`: shared skills, with `SKILL.md` and any supporting resources.
- `adapters/claude/skills/`: optional Claude-specific replacements for shared skills.
- `adapters/codex/skills/`: optional Codex-specific replacements for shared skills.
- `profiles/`: operating-system profiles and optional profile inheritance.
- `scripts/`: install, update, audit, check, rollback, and fleet deployment.
- `framework.toml`: shared branch, remote, and installation state name.
- `fleet.example.toml`: example fleet configuration. Copy it to ignored `fleet.local.toml`.
- `migration-known.json`: reviewed content fingerprints for optional adoption. The starter contains an empty map.

The installer discovers new skill directories automatically.
Claude links live in `~/.claude/skills`.
Codex links live in `~/.agents/skills`.
A same-named runtime adapter takes priority over the shared skill.
The installer also handles reviewed legacy copies under `~/.codex/skills`.

Plugin caches, system skills, account-synced skills, application settings, credentials, and conversation history remain outside this framework.
Agent definitions and global instructions also remain outside its scope.

## Profiles and shared configuration

Profiles select an operating system, runtimes, and excluded skill names.
Create a profile under `profiles/`, or use an existing profile.

```toml
extends = "linux"
name = "local-worker"
runtimes = ["codex"]
exclude_skills = ["example-skill"]
```

`exclude_skills` replaces the inherited list. Omit `runtimes` to install for both runtimes.
Files named `profiles/local-*.toml` stay outside Git by default.
For fleet use, provision these private profiles separately on each applicable target.
Shared profiles must exist in the published commit.
Use generic profile names in public repositories.

`framework.toml` defaults to remote `origin`, branch `main`, and state name `agents-config-public`.
These settings accept lowercase names with digits and hyphens.
Change the remote or branch before you publish your copy if your workflow needs different names.
Choose a unique state name before the first installation if another managed collection uses the same home.
Keep this name stable afterward. A changed name creates a separate installation record.
Different collections must also use different skill names or disjoint runtime profiles.

## Edit, publish, and update

Edit skills in the checkout. Edits through installed links change the same source files.
Review and commit the intended changes, then push the configured branch to the configured remote.
Run:

```sh
scripts/update
```

Update requires a clean checkout on the configured branch.
It fetches the published branch and accepts only a fast-forward update.
It refuses divergent history and unpublished local commits.
Each installation records its selected profile.
Later updates reuse that profile unless you provide `--profile NAME`.

Useful options:

- `--dry-run`: preview the current checkout without network access or installation changes.
- `--no-fetch`: apply the current committed checkout locally without a fetch.
- `--fleet`: update locally, then update configured SSH targets from the published branch.
- `--bundle-fleet`: update locally, then transfer published Git history to configured SSH targets.
- `--fleet-config PATH`: select an alternative private fleet file.
- `--target NAME`: select a fleet target. Repeat this option for several targets.
- `--expected-revision SHA`: stop if the published commit differs from the expected commit.

Fleet operations require explicit scope. See [fleet setup](docs/fleet.md) before the first deployment.

## Audit, removal, and recovery

```sh
scripts/check
scripts/audit
scripts/rollback --dry-run
scripts/rollback
```

Check compares the manifest, links, and installed revision.
Audit also checks content hashes, executable permissions, source edits, and unmanaged skill directories.
Audit is read-only and returns a nonzero status for findings.
`--allow-unmanaged` makes outside additions advisory. Managed integrity failures still return a nonzero status.

Delete requested source directories through Git to remove a skill everywhere.
Use `exclude_skills` to remove it from one profile.
After publication, update the requested machines.
The updater removes only obsolete links from its previous manifest.
It preserves unrelated directories and refuses to overwrite changed managed paths.

State and timestamped backups live under `~/.local/state/<state_name>/`.
Rollback restores the previous installation entries and manifest.
It refuses to overwrite entries that changed after installation.
Rollback does not restore deleted source files. Restore those through Git history first.
See [management details](docs/management.md) for imports, adoption, and recovery limits.

## Privacy and tests

Keep machine addresses, private paths, and access details in ignored configuration.
Never commit credentials, installation manifests, audit output, or private skill resources to a public repository.
Ignore rules are convenience controls. They do not sanitize files or Git history.
See [publication checks](docs/privacy.md) before you publish your copy.

```sh
uv run --no-project --python 3.12 python -m unittest discover -s tests -v
```

Tests use disposable homes and repositories.
Fleet tests use local transport substitutes and require no access to real machines.
They do not establish compatibility with every installed agent version or SSH environment.
