import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from gdo.base.Render import Mode
from gdo.core.Connector import Connector
from gdo.mail_connector.connector.Mail import Mail
from gdo.mail_connector.module_mail_connector import module_mail_connector


class MailConnectorTest(unittest.IsolatedAsyncioTestCase):
    def test_registers_mail_as_text_connector(self):
        with patch.object(Connector, 'register') as register:
            module_mail_connector().gdo_init()
        register.assert_called_once_with(Mail, True)
        self.assertEqual(Mode.render_mail, Mail().get_render_mode())

    async def test_install_creates_only_missing_disabled_server(self):
        server = MagicMock()
        dog = MagicMock()
        dog.get_mail.return_value = None
        server.get_user_by_name.return_value = None
        server.create_user = AsyncMock(return_value=dog)
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='dog@example.test'), \
             patch('gdo.mail_connector.module_mail_connector.GDT_Email') as field, \
             patch('gdo.mail_connector.module_mail_connector.module_mail.instance') as mail_module, \
             patch('gdo.mail_connector.module_mail_connector.GDO_Server.get_by_connector', return_value=None), \
             patch('gdo.mail_connector.module_mail_connector.GDO_Server.blank') as blank:
            field.return_value.validate.return_value = True
            blank.return_value.insert.return_value = server
            await module_mail_connector().gdo_install()
        blank.assert_called_once_with({'serv_name': 'mail', 'serv_connector': 'mail', 'serv_trigger': '.', 'serv_enabled': '0'})
        blank.return_value.insert.assert_called_once_with()
        server.create_user.assert_awaited_once_with('Dog', 'Dog')
        mail_module.return_value.set_email_for.assert_called_once_with(dog, 'dog@example.test', confirmed=True)
        server.get_user_by_name.return_value = dog
        dog.get_mail.return_value = 'dog@example.test'
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='dog@example.test'), \
             patch('gdo.mail_connector.module_mail_connector.GDT_Email') as field, \
             patch('gdo.mail_connector.module_mail_connector.GDO_Server.get_by_connector', return_value=server), \
             patch('gdo.mail_connector.module_mail_connector.GDO_Server.blank') as blank:
            field.return_value.validate.return_value = True
            await module_mail_connector().gdo_install()
        blank.assert_not_called()

    async def test_unimplemented_transport_never_reports_connected(self):
        connector = Mail()
        self.assertFalse(await connector.gdo_connect())
        self.assertFalse(connector.is_connected())

    async def test_outgoing_mail_uses_mail_module_and_confirmed_address(self):
        message = MagicMock()
        message._env_user.get_mail.return_value = 'user@example.test'
        message._result = '<b>Hello</b>'
        builder = MagicMock()
        builder.recipient.return_value = builder
        builder.subject.return_value = builder
        builder.body.return_value = builder
        builder.send.return_value = True
        with patch('gdo.mail_connector.connector.Mail.OutgoingMail.from_bot', return_value=builder), \
             patch('gdo.mail_connector.connector.Mail.OutgoingMail.is_debug', return_value=True):
            await Mail().gdo_send_to_user(message)
        message._env_user.get_mail.assert_called_once_with(confirmed=True)
        builder.recipient.assert_called_once_with('user@example.test')
        builder.body.assert_called_once_with('<b>Hello</b>')
        builder.send.assert_called_once_with()

    async def test_confirmed_address_creates_and_links_mail_user(self):
        module = module_mail_connector()
        user, server, mail_user = MagicMock(), MagicMock(), MagicMock()
        user.get_mail.return_value = 'person@example.test'
        user.get_effective_user.return_value = user
        user.get_id.return_value = 123
        server.get_user_by_name.return_value = None
        server.create_user = AsyncMock(return_value=mail_user)
        with patch('gdo.mail_connector.module_mail_connector.module_mail.instance') as mail_module:
            await module.link_confirmed_email(user, 'person@example.test', server)
        mail_module.return_value.set_email_for.assert_called_once_with(mail_user, 'person@example.test', confirmed=True)
        mail_user.save_val.assert_called_once_with('user_link', 123)

    async def test_existing_unlinked_account_is_not_taken_over(self):
        module = module_mail_connector()
        user, server, existing = MagicMock(), MagicMock(), MagicMock()
        user.get_mail.return_value = 'person@example.test'
        user.get_effective_user.return_value = user
        server.get_user_by_name.return_value = existing
        existing.get_linked_user.return_value = None
        with patch('gdo.mail_connector.module_mail_connector.Logger.warning'):
            await module.link_confirmed_email(user, 'person@example.test', server)
        existing.save_val.assert_not_called()
        server.create_user.assert_not_called()

    async def test_stale_confirmation_does_not_create_user(self):
        user, server = MagicMock(), MagicMock()
        user.get_mail.return_value = 'new@example.test'
        await module_mail_connector().link_confirmed_email(user, 'old@example.test', server)
        server.create_user.assert_not_called()
