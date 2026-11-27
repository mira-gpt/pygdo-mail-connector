# PyGDO Mail Connector

> **Security warning:** This connector is experimental and insecure for
> authenticating incoming mail. Sender addresses and mail headers can be
> forged; do not grant account permissions or run privileged commands based
> on them. Sender verification is not implemented. Keep the connector disabled
> until its mailbox access and event handoff have been tested in isolation.

An experimental PyGDO email connector. Mail rendering uses HTML with a
plain-text alternative derived through PyGDO's `Strings.html_to_text`.

The module registers the `{mail}` connector and creates a disabled mail server
and `Dog{mail}` user on install if missing. Set `mail.sender` to the configured
Dog email address before installation. Outgoing user mail uses the existing
PyGDO Mail API and protected mail configuration; recipients must have a
confirmed address. The inbound transport archives mail and can optionally
dispatch it as an unauthenticated ghost message; it does not verify senders.
It does not replace or consume Mira's existing inbox queue.

Confirmed email addresses emit a confirmation event. The module schedules
creation and linking of a mail-server account for that address; it refuses to
take over an existing account linked elsewhere. Email addresses are not used as
account names. These hooks need a loaded module and have not been deployed.
During installation, existing non-mail users with confirmed addresses are also
backfilled. Unconfirmed addresses and conflicting existing links are skipped.

The IMAP reader connects over TLS, polls or uses IDLE when available, fetches
by UID without marking messages read, and limits message size. It archives raw
messages under `files/mails/` and keeps a durable UID/UIDVALIDITY checkpoint.
Sender verification and account-link authorization are not implemented. A
matching From address, an allowlist, or a DKIM signature alone does not prove
the sender controls a specific mailbox.

`From` and `Return-Path` are untrusted claims. A checkpoint cannot make message
delivery exactly once: a crash between handing off an event and saving the
checkpoint can cause a repeat. The checkpoint rejects a changed UIDVALIDITY
rather than guessing whether old UIDs are safe. Oversized messages stop the
batch for operator review.

`mail_connector_mira_inbox` defaults to `1`: each archived message is sent to
the Mira session as `$inbox <path>`. Set it to `0` on installations without
Mira or when this handoff is unwanted. `mail_connector_userstuff` defaults to
`0`. When enabled, nonempty plain-text mail is also dispatched as a PyGDO
message from an unauthenticated ghost. The claimed sender and envelope address
remain untrusted metadata and are never resolved to a linked account. A body
starting with the mail server's trigger can invoke methods available to a ghost;
do not enable this path unless that behavior is desired. Ghost replies have no
confirmed recipient and cannot be sent by the mail connector.
On first use, the cursor starts at UID zero, so existing messages in the
selected mailbox will be archived and, when opted in, generate events too.
The event is submitted without interrupting the current task; submission is
not confirmation that it was processed. Ensure the Dog and Mira accounts can
read the private archive, and check web-server access rules independently.

## Private IMAP settings

`gdo_module_config()` reads defaults from `protected/mail_connector/secret.toml`;
see `secret.toml.example` for the format. Restrict the private file to mode 600,
keep it out of version control, and back it up separately. Existing values saved
in the module configuration database override these defaults. Saving settings
through PyGDO stores them in the database, including the password; `GDT_Secret`
masks display but does not encrypt it. Protect database backups accordingly.
Restart or reload the module to pick up file changes. The IMAP host and password
must be supplied locally. Configuring them does not itself enable the disabled
server; outgoing SMTP remains configured separately in the existing mail settings.

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
