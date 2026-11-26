"""Render outgoing HTML mail with a plain-text alternative."""
from email.message import EmailMessage

from gdo.base.Util import Strings


def message_for_html(sender: str, recipient: str, subject: str, html: str) -> EmailMessage:
    """Build a multipart message; delivery and sender validation belong to the transport."""
    message = EmailMessage()
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(Strings.html_to_text(html), charset='utf-8')
    message.add_alternative(html, subtype='html', charset='utf-8')
    return message
