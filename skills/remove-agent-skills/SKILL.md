---
name: remove-agent-skills
description: Remove or disable named repository-managed skills or runtime variants, then reconcile local or authorized fleet installations. Use for deletion, retirement, uninstallation, or profile-specific exclusion.
---

# Remove managed skills

Find the source checkout from this installed skill's resolved path or the user's requested repository.
Read its README and `framework.toml`. Check Git status.
Limit changes to the requested skills and machines.
An explicit removal request authorizes that named removal.

1. Locate the named shared and adapter directories under `skills/` and `adapters/<runtime>/skills/`.
2. Check dependencies and references before removal.
3. For complete removal, use Git to delete the exact requested source paths.
4. For one-profile removal, add the name to that profile's `exclude_skills` list instead.
5. Review, commit, and publish the change on the configured branch within the user's scope.
6. Run `scripts/update` for the local installation.
7. For authorized fleet removal, read `docs/fleet.md`, then use `scripts/update --fleet` with the requested targets.
8. Run `scripts/audit`. Report the commit, removed names, successful targets, and failures.

Removing an adapter can expose a same-named shared skill.
Determine whether the requested result is that fallback or complete removal.
The updater removes obsolete managed links and preserves unrelated installed directories.
It refuses to overwrite locally changed managed paths.

Do not delete plugin, system, synced, or project-local skills through this workflow.
Never edit manifests or adoption fingerprints to bypass a conflict.
If a skill belongs to another manager, explain its ownership and use that manager only within the user's scope.

Use `--dry-run` for a local preview without fetching or link changes.
Use `--no-fetch` for a committed local installation without fetching.
For targets without Git-server access, use `--bundle-fleet` within the authorized scope.
Never read or copy credential files to resolve access failures.

To undo source deletion, restore it in a new Git commit and rerun update after publication.
Installer rollback restores installation entries. It does not restore deleted repository sources.
