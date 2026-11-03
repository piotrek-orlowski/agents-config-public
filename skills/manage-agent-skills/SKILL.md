---
name: manage-agent-skills
description: Add, edit, import, update, or audit skills in a repository managed by the agents-config framework. Use for skill maintenance and authorized fleet updates through its install, update, and audit scripts.
---

# Manage repository skills

Locate the source checkout from the installed skill's resolved path or the user's requested repository.
Read its README and `framework.toml`, then check Git status.
Do not assume a checkout path, Git account, branch, controller OS, or fleet scope.
Preserve unrelated changes and credentials.

## Audit and import

Run `scripts/audit` before and after maintenance.
It reports managed-link failures, supporting-file changes, executable permissions, and outside additions without changing files.
Source edits through an installed link are repository edits.

For a requested outside addition, inspect its complete directory before import.
Compare same-named sources before a replacement.
Review resources for private details and secrets before public publication.
Put shared content under `skills/<name>/`, or use the appropriate runtime adapter.
Preserve scripts, references, licenses, and attribution.
Commit and publish the intended import within the user's scope.
Move the original installed directory into a timestamped backup under the configured state directory's `import-backups/`.
Then run update and audit. Keep the backup.
Never widen adoption fingerprints or edit manifests to suppress a conflict.

## Add, edit, or remove

- Use matching lowercase directory and frontmatter names with hyphens.
- Write a focused frontmatter description. Keep automatic invocation enabled unless the user requests otherwise.
- Use `adapters/claude/skills/<name>/` or `adapters/codex/skills/<name>/` for runtime-specific behavior.
- Keep supporting resources and relative references intact.
- For complete removal, delete the requested shared and adapter sources through Git.
- For one-profile removal, change that profile's `exclude_skills` list.

An adapter can fall back to a same-named shared skill.
Check that fallback before complete removal.
Do not manage plugin, system, synced, or project-local skills through this repository.
The installer discovers source directories automatically.

## Publish and apply

Review the diff and run relevant script tests.
Use uv for Python commands.
Do not run data extractions or infrastructure workflows merely to test skill packaging.
Commit intended changes and push the configured branch to the configured remote within the authorized scope.
Never stash, reset, or force-push unrelated work.

Run `scripts/update` for the local installation.
It requires a clean checkout and refuses divergence or unpublished local commits.
Use `--dry-run` to preview the current checkout without network access or changes.
Use `--no-fetch` to apply an already committed checkout locally without fetching.

For authorized fleet updates, read `docs/fleet.md` and the selected fleet configuration.
Check that the agent can run noninteractive SSH from its actual environment.
Use `scripts/update --fleet`, with `--target NAME` for restricted scope.
Use `--fleet-config PATH` for an alternative private target file.
Each target uses its own Git authentication. Never copy credentials.
For targets without Git-server access, use `--bundle-fleet` within the same authorized scope.
For bootstrap, use `scripts/deploy.py` as documented.

Fleet operations pin the published commit and stop on failure.
Earlier targets can remain updated after a later failure.
Report the revision, affected skills, successful targets, failed targets, and checks.
Do not claim fleet completion after a local update.
If access fails, report the error without opening credential files.
