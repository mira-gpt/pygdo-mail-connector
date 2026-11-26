import unittest

from gdo.mail_connector.MailRendering import message_for_html
from gdo.mail_connector.module_mail_connector import module_mail_connector


class MailRenderingTest(unittest.TestCase):
    def test_skeleton_depends_on_mail(self):
        self.assertEqual(['mail'], module_mail_connector().gdo_dependencies())

    def test_multipart_uses_html_to_text_for_plain_alternative(self):
        message = message_for_html('dog@example.test', 'user@example.test', 'Test', '<p>Hello <b>duck</b> &amp; friends</p>')
        self.assertEqual('multipart/alternative', message.get_content_type())
        text, html = list(message.iter_parts())
        self.assertEqual('text/plain', text.get_content_type())
        self.assertIn('Hello duck & friends', text.get_content())
        self.assertEqual('text/html', html.get_content_type())
        self.assertIn('<b>duck</b>', html.get_content())

    def test_header_injection_is_rejected(self):
        with self.assertRaises(ValueError):
            message_for_html('dog@example.test', 'user@example.test\nBcc: bad@example.test', 'Test', 'Hello')
