import unittest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from gdo.base.Render import Mode
from gdo.base.Application import Application
from gdo.core.Connector import Connector
from gdo.mail_connector.connector.Mail import Mail
from gdo.mail_connector.module_mail_connector import module_mail_connector


class MailConnectorTest(unittest.IsolatedAsyncioTestCase):
    def test_account_name_is_short_salted_and_requires_salt(self):
        module = module_mail_connector()
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value=''):
            with self.assertRaises(ValueError):
                module.mail_account_name('person@example.test')
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='salt-a'):
            first = module.mail_account_name('person@example.test')
            self.assertEqual(first, module.mail_account_name('person@example.test'))
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='salt-b'):
            self.assertNotEqual(first, module.mail_account_name('person@example.test'))
        self.assertRegex(first, r'^mail_[0-9a-f]{24}$')

    def test_imap_defaults_are_loaded_from_private_toml(self):
        Application.mode(Mode.render_cli)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret.toml'
            path.write_text('[imap]\nhost="example.test"\nport=1993\nusername="mira@example.test"\npassword="test-only"\nfolder="Mail"\n')
            with patch('gdo.mail_connector.module_mail_connector.Application.file_path', return_value=str(path)):
                fields = {field.get_name(): field for field in module_mail_connector().gdo_module_config()}
            self.assertEqual('example.test', fields['mail_connector_imap_host'].get_val())
            self.assertEqual('1993', fields['mail_connector_imap_port'].get_val())
            self.assertEqual('mira@example.test', fields['mail_connector_imap_user'].get_val())
            self.assertEqual('test-only', fields['mail_connector_imap_password'].get_val())
            self.assertTrue(fields['mail_connector_imap_password'].is_secret())
            self.assertEqual('Mail', fields['mail_connector_imap_folder'].get_val())

    def test_imap_rejects_invalid_secret_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'secret.toml'
            path.write_text('[imap]\nport = true\n')
            with patch('gdo.mail_connector.module_mail_connector.Application.file_path', return_value=str(path)):
                with self.assertRaises(ValueError):
                    module_mail_connector().gdo_module_config()

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
             patch.object(module_mail_connector, 'backfill_confirmed_users', new_callable=AsyncMock), \
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
             patch.object(module_mail_connector, 'backfill_confirmed_users', new_callable=AsyncMock), \
             patch('gdo.mail_connector.module_mail_connector.GDO_Server.blank') as blank:
            field.return_value.validate.return_value = True
            await module_mail_connector().gdo_install()
        blank.assert_not_called()

    async def test_backfill_only_uses_confirmed_non_mail_users(self):
        module = module_mail_connector()
        server, confirmed, unconfirmed, mail_account = (MagicMock() for _ in range(4))
        server.get_id.return_value = 8
        confirmed.get_server_id.return_value = 1
        confirmed.get_mail.return_value = 'confirmed@example.test'
        unconfirmed.get_server_id.return_value = 1
        unconfirmed.get_mail.return_value = None
        mail_account.get_server_id.return_value = 8
        with patch('gdo.mail_connector.module_mail_connector.GDO_User.table') as table, \
             patch.object(module, 'link_confirmed_email', new_callable=AsyncMock) as link:
            table.return_value.select.return_value.exec.return_value.fetch_object.side_effect = [confirmed, unconfirmed, mail_account, None]
            await module.backfill_confirmed_users(server)
        link.assert_awaited_once_with(confirmed, 'confirmed@example.test', server)

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
        user.get_name.return_value = 'person'
        user.get_effective_user.return_value = user
        user.get_id.return_value = 123
        server.get_user_by_name.return_value = None
        server.create_user = AsyncMock(return_value=mail_user)
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='test-salt'), \
             patch('gdo.mail_connector.module_mail_connector.module_mail.instance') as mail_module:
            await module.link_confirmed_email(user, 'person@example.test', server)
            name = module.mail_account_name('person@example.test')
        server.create_user.assert_awaited_once_with(name, 'person')
        self.assertEqual(29, len(name))
        mail_module.return_value.set_email_for.assert_called_once_with(mail_user, 'person@example.test', confirmed=True)
        mail_user.save_val.assert_called_once_with('user_link', 123)

    async def test_existing_unlinked_account_is_not_taken_over(self):
        module = module_mail_connector()
        user, server, existing = MagicMock(), MagicMock(), MagicMock()
        user.get_mail.return_value = 'person@example.test'
        user.get_effective_user.return_value = user
        server.get_user_by_name.return_value = existing
        existing.get_linked_user.return_value = None
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='test-salt'), \
             patch('gdo.mail_connector.module_mail_connector.Logger.warning'):
            await module.link_confirmed_email(user, 'person@example.test', server)
        existing.save_val.assert_not_called()
        server.create_user.assert_not_called()

    async def test_existing_confirmed_link_updates_display_name_only(self):
        module = module_mail_connector()
        user, server, existing = MagicMock(), MagicMock(), MagicMock()
        user.get_mail.return_value = 'person@example.test'
        user.get_name.return_value = 'a' * 40
        user.get_effective_user.return_value = user
        user.get_id.return_value = 123
        server.get_user_by_name.return_value = existing
        existing.get_mail.return_value = 'person@example.test'
        existing.get_linked_user.return_value = user
        existing.get_displayname.return_value = 'old'
        with patch('gdo.mail_connector.module_mail_connector.Application.config', return_value='test-salt'):
            await module.link_confirmed_email(user, 'person@example.test', server)
        existing.save_val.assert_called_once_with('user_displayname', 'a' * 32)
        server.create_user.assert_not_called()

    async def test_stale_confirmation_does_not_create_user(self):
        user, server = MagicMock(), MagicMock()
        user.get_mail.return_value = 'new@example.test'
        await module_mail_connector().link_confirmed_email(user, 'old@example.test', server)
        server.create_user.assert_not_called()
