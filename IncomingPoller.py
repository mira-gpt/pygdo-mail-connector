"""One explicit inbound batch; no sender authentication or auto-replies."""
from gdo.mail_connector.IncomingMail import parse_incoming


class IncomingPoller:
    def __init__(self, reader, checkpoint, archive, mailbox, on_message):
        self.reader = reader
        self.checkpoint = checkpoint
        self.archive = archive
        self.mailbox = mailbox
        self.on_message = on_message

    async def poll_once(self):
        validity = await self.reader.uidvalidity()
        cursor = self.checkpoint.advance(self.mailbox, validity, 0)
        processed = 0
        for uid, raw in await self.reader.fetch_after(cursor):
            if raw is None:
                raise ValueError(f'IMAP message UID {uid} exceeds size limit')
            parsed = parse_incoming(raw)
            path = self.archive.store(self.mailbox, validity, uid, raw)
            await self.on_message(path, parsed)
            self.checkpoint.advance(self.mailbox, validity, uid)
            processed += 1
        return processed
