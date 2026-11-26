# PyGDO Mail Connector

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

## Ideas

- Optionally show incoming mail flying into the video media window, with an
  entrance effect. Keep this opt-in and protect private message contents from
  appearing on a shared screen or stream without the recipient's consent.
