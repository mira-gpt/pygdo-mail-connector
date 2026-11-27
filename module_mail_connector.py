import hashlib
from pathlib import Path
import tomllib
import zlib

from gdo.base.GDO_Module import GDO_Module
from gdo.base.Application import Application
from gdo.base.Logger import Logger
from gdo.core.Connector import Connector
from gdo.core.GDO_Server import GDO_Server
from gdo.core.GDO_User import GDO_User
from gdo.core.GDT_Secret import GDT_Secret
from gdo.core.GDT_Bool import GDT_Bool
from gdo.core.GDT_String import GDT_String
from gdo.core.GDT_UInt import GDT_UInt
from gdo.mail_connector.connector.Mail import Mail
from gdo.mail.GDT_Email import GDT_Email
from gdo.mail.module_mail import module_mail


class module_mail_connector(GDO_Module):
    """Mail connector registration and inactive server skeleton."""

    def gdo_dependencies(self) -> list[str]:
        return ['mail']

    def gdo_module_config(self):
        path = Path(Application.file_path('protected/mail_connector/secret.toml'))
        settings = {}
        if path.is_file():
            with path.open('rb') as stream:
                config = tomllib.load(stream)
            settings = config.get('imap', {})
            if not isinstance(settings, dict):
                raise ValueError('mail connector secret.toml: [imap] must be a table')
        port = settings.get('port', 993)
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError('mail connector IMAP port must be between 1 and 65535')
        for key in ('host', 'username', 'password', 'folder'):
            if key in settings and not isinstance(settings[key], str):
                raise ValueError(f'mail connector IMAP {key} must be a string')
        return [
            GDT_String('mail_connector_imap_host').initial(str(settings.get('host', ''))),
            GDT_UInt('mail_connector_imap_port').not_null().initial(str(port)).min(1).max(65535),
            GDT_String('mail_connector_imap_user').initial(str(settings.get('username', ''))),
            GDT_Secret('mail_connector_imap_password').initial(str(settings.get('password', ''))),
            GDT_String('mail_connector_imap_folder').not_null().initial(str(settings.get('folder', 'INBOX'))),
            GDT_Bool('mail_connector_userstuff').not_null().initial('0'),
            GDT_Bool('mail_connector_mira_inbox').not_null().initial('1'),
        ]

    def gdo_init(self):
        Connector.register(Mail, True)

    def gdo_subscribe_events(self):
        Application.EVENTS.subscribe('user_email_confirmed', self.on_user_email_confirmed)

    def mail_account_name(self, email):
        salt = Application.config('core.secret')
        if not isinstance(salt, str) or not salt:
            raise ValueError('Configure core.secret before linking mail accounts')
        data = str(salt).encode('utf-8') + b'\0' + email.encode('utf-8')
        digest = hashlib.md5(data, usedforsecurity=False).hexdigest()[:16]
        checksum = f'{zlib.crc32(data):08x}'
        return 'mail_' + digest + checksum

    def on_user_email_confirmed(self, user, email, previous_email=None):
        server = GDO_Server.get_by_connector('mail')
        if not server or str(user.get_server_id()) == str(server.get_id()) or not email:
            return
        Application.run_coro(self.link_confirmed_email(user, email, server, previous_email), 'mail_connector_link_confirmed')

    async def link_confirmed_email(self, user, email, server, previous_email=None):
        # The scheduled task may run after a later address change.
        if user.get_mail(confirmed=True) != email:
            return
        master = user.get_effective_user()
        if previous_email and previous_email != email:
            old = server.get_user_by_name(self.mail_account_name(previous_email))
            if old and old.get_mail(confirmed=False) == previous_email:
                linked = old.get_linked_user()
                if linked and str(linked.get_id()) == str(master.get_id()):
                    old.save_val('user_link', None)
        # Account names are ASCII and limited to 64 chars.  Hash the entire
        # address instead of putting an email address into the user name.
        name = self.mail_account_name(email)
        # GDT_UserName limits display names to 32 characters; user_name can
        # be up to 64. The hashed mail user_name remains the unique lookup key.
        displayname = user.get_name()[:32]
        existing = server.get_user_by_name(name)
        if existing:
            linked = existing.get_linked_user()
            if (existing.get_mail(confirmed=False) != email or not linked
                    or str(linked.get_id()) != str(master.get_id())):
                Logger.warning('Mail account already exists; refusing automatic relink.')
            elif existing.get_displayname() != displayname:
                existing.save_val('user_displayname', displayname)
            return
        mail_user = await server.create_user(name, displayname)
        # Check again after the asynchronous creation and do not attach a
        # now-stale confirmation to the wrong account.
        if user.get_mail(confirmed=True) != email:
            return
        module_mail.instance().set_email_for(mail_user, email, confirmed=True)
        mail_user.save_val('user_link', master.get_id())

    async def gdo_install(self):
        sender = Application.config('mail.sender')
        if not sender or not GDT_Email('sender').validate(sender):
            raise ValueError('Configure a valid mail.sender before installing mail_connector')
        server = GDO_Server.get_by_connector('mail')
        if not server:
            server = GDO_Server.blank({
                'serv_name': 'mail',
                'serv_connector': 'mail',
                'serv_trigger': '.',
                'serv_enabled': '0',
            }).insert()
        dog = server.get_user_by_name('Dog')
        if dog:
            existing = dog.get_mail(confirmed=False)
            if existing and existing.lower() != sender.lower():
                raise ValueError('Existing Dog mail user has a different email address')
        else:
            dog = await server.create_user('Dog', 'Dog')
        if not dog.get_mail(confirmed=True):
            module_mail.instance().set_email_for(dog, sender, confirmed=True)
        await self.backfill_confirmed_users(server)

    async def backfill_confirmed_users(self, server):
        result = GDO_User.table().select().exec()
        while user := result.fetch_object():
            if str(user.get_server_id()) == str(server.get_id()):
                continue
            if email := user.get_mail(confirmed=True):
                await self.link_confirmed_email(user, email, server)
