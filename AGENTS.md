# Contributor instructions

This repository manages skill links for Claude Code and Codex on macOS and Linux.
Read README.md before a change. Preserve unrelated work.

- Use uv for Python commands. The framework needs only the Python standard library.
- Test installation changes in disposable homes and repositories before fleet use.
- Run `uv run --no-project --python 3.12 python -m unittest discover -s tests -v` after script changes.
- Keep real machine details in private fleet configuration. Use generic examples in tracked files.
- Never read credential files without explicit user permission. Use existing Git and SSH authentication without printing secrets.
- Never copy private Git history, inventories, installation state, or operational logs into public commits.
- Preserve adoption checks, manifest validation, conflict refusal, backups, and rollback behavior.
- Do not edit manifests or adoption fingerprints to bypass an unfamiliar installed directory.
- Limit fleet operations to the user's requested machines. Report partial failures without claiming fleet completion.
- Review public commit identities and staged files before publication.
