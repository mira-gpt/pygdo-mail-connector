"""Bounded parsing of incoming mail; parsing never authenticates a sender."""
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr

from gdo.mail_connector.ImapReader import ImapReader


@dataclass(frozen=True)
class IncomingMail:
    claimed_from: str | None
    envelope_from: str | None
    subject: str
    text: str


def parse_incoming(raw: bytes) -> IncomingMail:
    if not isinstance(raw, bytes):
        raise TypeError('Incoming mail must be bytes')
    if len(raw) > ImapReader.MAX_BYTES:
        raise ValueError('Incoming mail exceeds the size limit')
    message = BytesParser(policy=policy.default).parsebytes(raw)
    headers = message.get_all('From', [])
    sender = None
    if len(headers) == 1 and not headers[0].defects:
        addresses = headers[0].addresses
        if len(addresses) == 1 and addresses[0].username and addresses[0].domain:
            sender = addresses[0].addr_spec
    # Return-Path is only evidence of SMTP MAIL FROM if a trusted receiver
    # removes untrusted copies and inserts its own. Keep it untrusted here.
    paths = message.get_all('Return-Path', [])
    envelope_from = None
    if len(paths) == 1 and str(paths[0]).strip() != '<>':
        _, address = parseaddr(str(paths[0]), strict=True)
        if address and '@' in address:
            envelope_from = address
    subject = str(message.get('Subject', ''))
    subject = ' '.join(subject.split())[:300]
    body = message.get_body(preferencelist=('plain',))
    text = body.get_content() if body else ''
    if not isinstance(text, str):
        text = ''
    return IncomingMail(sender, envelope_from, subject, text)
