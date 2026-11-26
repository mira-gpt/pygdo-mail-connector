import unittest
from unittest.mock import MagicMock, patch

from gdo.mail.module_mail import module_mail


class ConfirmationEventTest(unittest.TestCase):
    def test_confirmation_event_fires_even_for_same_timestamp(self):
        user = MagicMock()
        user.get_setting_val.return_value = 'person@example.test'
        with patch('gdo.mail.module_mail.Time.get_date', return_value='2026-01-01 00:00:00.000000'), \
             patch('gdo.mail.module_mail.Application.publish_event') as publish:
            module_mail().set_mail_confirmed_for(user)
            module_mail().set_mail_confirmed_for(user)
        self.assertEqual(2, publish.call_count)
        publish.assert_called_with('user_email_confirmed', user, 'person@example.test', None)

    def test_changed_address_clears_previous_confirmation_first(self):
        user = MagicMock()
        user.get_setting_val.return_value = 'old@example.test'
        module_mail().set_email_for(user, 'new@example.test', confirmed=False)
        self.assertEqual([('email_confirmed', None), ('email', 'new@example.test')],
                         [call.args for call in user.save_setting.call_args_list])
