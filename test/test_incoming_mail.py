import unittest

from gdo.mail_connector.IncomingMail import parse_incoming
from gdo.mail_connector.ImapReader import ImapReader


class IncomingMailTest(unittest.TestCase):
    def test_claimed_sender_is_only_metadata(self):
        result = parse_incoming(b'From: Example <person@example.test>\r\nSubject: Hi\r\n\r\nHello!')
        self.assertEqual('person@example.test', result.claimed_from)
        self.assertEqual('Hi', result.subject)
        self.assertEqual('Hello!', result.text)

    def test_ambiguous_sender_is_unidentified(self):
        for raw in (b'From: a@example.test, b@example.test\r\n\r\nHi',
                    b'From: a@example.test\r\nFrom: b@example.test\r\n\r\nHi'):
            self.assertIsNone(parse_incoming(raw).claimed_from)

    def test_return_path_is_separate_untrusted_envelope_metadata(self):
        raw = b'From: author@example.test\r\nReturn-Path: <bounce@example.test>\r\n\r\nHi'
        result = parse_incoming(raw)
        self.assertEqual('author@example.test', result.claimed_from)
        self.assertEqual('bounce@example.test', result.envelope_from)
        self.assertIsNone(parse_incoming(b'Return-Path: <>\r\n\r\nHi').envelope_from)
        self.assertIsNone(parse_incoming(b'Return-Path: <a@b.test>\r\nReturn-Path: <c@d.test>\r\n\r\nHi').envelope_from)

    def test_html_only_and_oversized_mail_are_not_processed_as_plain_text(self):
        result = parse_incoming(b'Content-Type: text/html\r\n\r\n<b>hello</b>')
        self.assertEqual('', result.text)
        with self.assertRaises(ValueError):
            parse_incoming(b'x' * (ImapReader.MAX_BYTES + 1))
