# Historical credential bootstrap source

These text files preserve the non-secret source of two earlier interactive
provisioning helpers. They are reference archives, not new supported commands.
No credential value or private key is included. Neither helper runs automatically.

- store-github-token.py.txt: hidden-input bootstrap for an external read-only
  GitHub credential, with a repository-content read check before exclusive creation.
- store-control-token.py.txt: hidden-input bootstrap for a separate Issues
  credential, with an interactive-terminal requirement and exclusive creation.

Both refuse to overwrite existing credential files. Their filesystem permissions
assume a POSIX deployment host; do not treat mode bits as Windows ACL protection.
Do not run them just to validate this archive: they can create credential files and
one performs a network request. Existing credentials remain in their approved
external stores and are not migrated by this cleanup.

This preserves historical logic only. Follow current credential inventory and
runtime documentation before any separately authorized provisioning action:
[credential inventory](../../credential-inventory.md),
[control bridge](../../control-bridge.md).

The old GitHub helper remains referenced by an old bootstrap script and must stay
until that consumer is reconciled. The separate task-local control-token diagnostic
also stays until it has a durable operational replacement. An archived bootstrap
script is not a replacement for that diagnostic.
