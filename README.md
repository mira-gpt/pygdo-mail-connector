# PyGDO Mail Connector

An inactive module skeleton for a future PyGDO email connector. Mail rendering uses HTML with a
plain-text alternative derived through PyGDO's `Strings.html_to_text`.

The module does not register a connector or create a server. The transport,
account association, authentication policy and mailbox
ownership are not implemented yet. Do not enable this as a connector or
point it at a production mailbox until those parts have been designed and
tested. It does not replace or consume Mira's existing inbox queue.
