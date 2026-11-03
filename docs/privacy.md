# Public repository privacy

Public files, Git history, commit identities, repository ownership, and issue activity can disclose identity or infrastructure details.
A public repository on a personal account necessarily links to that account.
File cleanup cannot remove this association.

## Before publication

Create a fresh Git repository from an explicit list of reviewed files.
Do not copy `.git`, private skill collections, old profiles, deployment evidence, inventories, manifests, or provenance from a private repository.
Inspect all file contents and filenames, including hidden files and symlink targets.

Keep actual host aliases, addresses, usernames, home paths, institution names, and private repository URLs outside public files.
Use `fleet.local.toml` or another private configuration path for fleet details.
Keep credentials in the platform's credential stores.
Never place credential files in skills, even when a fingerprint helper ignores them.

Review staged files with `git diff --cached` and `git ls-files`.
Run a secret scanner if available.
For example, scan tracked files without external credential verification:

```sh
uvx --from detect-secrets detect-secrets scan --no-verify
```

Also review Git author and committer identities, signatures, commit messages, and remote URLs.
Use a suitable public identity or a generic identity before the first commit.
Do not print access tokens or open credential stores during these checks.

Ignore rules prevent accidental additions of some local files.
They do not prevent forced additions, redact ordinary documents, or remove already tracked files.
Every imported skill and resource needs its own review.

## Operational output

Installation manifests, rollback journals, audit output, and inventory output contain local paths and source fingerprints.
Fleet commands can print SSH aliases and checkout paths.
Keep these outputs private when they describe your real environment.
Do not upload logs as public debugging attachments without review.

Git bundles contain branch history. Removing a secret from the latest file does not remove it from a bundle.
If a credential reaches public history, revoke it immediately and follow your hosting provider's removal procedure.
Publish this starter from a new history, then continue to review later commits.
