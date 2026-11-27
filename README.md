# PyGDO Mail Connector

> **Security warning:** This connector is experimental and insecure for
> authenticating incoming mail. Sender addresses and mail headers can be
> forged; do not grant account permissions or run privileged commands based
> on them. Incoming transport and sender verification are not yet implemented.
> Keep the connector disabled and do not use it with a production mailbox.

An inactive module skeleton for a future PyGDO email connector. Mail rendering uses HTML with a
plain-text alternative derived through PyGDO's `Strings.html_to_text`.

The module registers the `{mail}` connector and creates a disabled mail server
and `Dog{mail}` user on install if missing. Set `mail.sender` to the configured
Dog email address before installation. Outgoing user mail uses the existing
PyGDO Mail API and protected mail configuration; recipients must have a
confirmed address. Inbound transport, sender authentication policy and mailbox
ownership are not implemented yet. Do not enable this as a connector or
point it at a production mailbox until those parts have been designed and
tested. It does not replace or consume Mira's existing inbox queue.

Confirmed email addresses emit a confirmation event. The module schedules
creation and linking of a mail-server account for that address; it refuses to
take over an existing account linked elsewhere. Email addresses are not used as
account names. These hooks need a loaded module and have not been deployed.
During installation, existing non-mail users with confirmed addresses are also
backfilled. Unconfirmed addresses and conflicting existing links are skipped.

The IMAP reader is a standalone, read-only TLS primitive: it polls or uses IDLE
when available, fetches by UID without marking messages read, and limits message
size. It is not connected to Dog. Safe integration still needs durable UID and
UIDVALIDITY tracking, sender verification and account-link authorization. A
matching From address, an allowlist, or a DKIM signature alone does not prove
the sender controls a specific mailbox.

The incoming parser and UID checkpoint are development primitives, not an
active connector: `From` and `Return-Path` are untrusted claims, and a
checkpoint cannot make message delivery exactly once by itself. The checkpoint
rejects a changed UIDVALIDITY rather than guessing whether old UIDs are safe.
Verification, ghost-only dispatch and the polling integration remain to be built.

## Private IMAP settings

`gdo_module_config()` reads defaults from `protected/mail_connector/secret.toml`;
see `secret.toml.example` for the format. Restrict the private file to mode 600,
keep it out of version control, and back it up separately. Existing values saved
in the module configuration database override these defaults. Saving settings
through PyGDO stores them in the database, including the password; `GDT_Secret`
masks display but does not encrypt it. Protect database backups accordingly.
Restart or reload the module to pick up file changes. The IMAP host and password
must be supplied locally. This does not enable or connect the inactive connector,
and outgoing SMTP remains configured separately in the existing mail settings.

The connector uses the existing `core.secret` as its salt. Keep it stable and
back it up securely: changing it changes account identifiers. The connector forms `mail_` plus 16 hexadecimal MD5
characters and eight CRC32 hexadecimal characters, both calculated once over
the salt, a NUL separator and the UTF-8 email address. This is a compact
identifier, not password hashing or strong protection against email guessing.
Colliding existing account names are not automatically linked. Old account
identifiers are not migrated or looked up by this scheme.

## Ideas

- Optionally show incoming mail flying into the video media window, with an
  entrance effect. Keep this opt-in and protect private message contents from
  appearing on a shared screen or stream without the recipient's consent.
