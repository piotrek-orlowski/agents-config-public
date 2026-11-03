# Management details

## Add or import a skill

Read the source and all supporting resources before an import.
Keep shared content under `skills/<name>/`.
Use `adapters/<runtime>/skills/<name>/` for runtime-specific behavior.
Each directory needs `SKILL.md`, with matching `name` and a focused `description` in YAML frontmatter.
Use lowercase names with hyphens. Preserve licenses and upstream attribution.

Run `scripts/audit` before and after maintenance.
For an outside addition, compare the complete installed directory with any same-named repository source.
Review resources for private paths and secrets before you copy them.
Commit and publish the intended import.
Move the original installed copy to a timestamped directory under your configured state directory's `import-backups/`.
Then run update to create its managed link.
Keep the original backup.

The audit reports outside additions but never imports or deletes them automatically.
Do not change a manifest or adoption fingerprints to suppress a conflict.
An installed link points into the checkout, so source edits through that link also need review and publication.

## Adoption

`--adopt-known` is an optional migration mechanism for reviewed legacy copies.
The starter's `migration-known.json` is empty, so it accepts no existing copies by default.
Normal installation accepts existing managed links only.

For a reviewed migration, generate fingerprints with `files()` from `scripts/inventory.py`.
The JSON map uses skill names as keys. Each value lists accepted complete directory fingerprints.
Review those contents and fingerprints before publication.
The installer compares a complete directory fingerprint before it moves the original to backup.
Unfamiliar contents stop the entire plan before replacements.

Private copies can contain secrets that the fingerprint helper excludes.
Never treat a matching fingerprint as a secret scan or permission to publish the directory.
For a small import, the manual backup workflow is usually easier to review.

## Runtime and source boundaries

Shared skills install for both runtimes by default.
A runtime-specific directory overrides a shared directory with the same name.
Removal of an adapter can expose that shared fallback.
Check this fallback before you promise complete removal.

System, plugin, synced, disabled, and project-local skill trees retain their existing managers.
This repository does not replace agent definitions, global instructions, runtime configuration, or authentication.
The installer refuses symlinked installation parents rather than redirect a whole skill tree.
Review such layouts before installation.

The manifest belongs to one checkout path and one state name.
Do not move the checkout or reuse another collection's manifest without a migration plan.
The scripts refuse a manifest from another repository.

## Audit and rollback limits

Audit checks manifest paths before it scans managed content.
It records nested symlinks as links rather than reading their external targets.
Credential filenames and cache directories are excluded from fingerprints.
This exclusion reduces accidental reads. It does not make a skill directory safe to publish.

Backups preserve replaced entries and the previous manifest.
Rollback checks that installation paths still match the recorded operation.
Changed local entries block rollback until you preserve and review them.
Deleted repository sources need restoration through Git separately.

Before you undo a published change, restore its sources in a new commit and publish that commit.
Then update the requested machines.
A backward checkout alone can conflict with fast-forward fleet updates.
