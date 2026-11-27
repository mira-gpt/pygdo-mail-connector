import asyncio
import hashlib
from pathlib import Path

from gdo.base.Application import Application
from gdo.base.Logger import Logger
from gdo.base.Render import Mode
from gdo.core.Connector import Connector
from gdo.mail.Mail import Mail as OutgoingMail


class Mail(Connector):
    """IMAP archive connector with an optional Mira inbox handoff."""

    def __init__(self):
        super().__init__()
        self._reader = None
        self._poll_task = None

    def get_render_mode(self):
        return Mode.render_mail

    async def gdo_connect(self):
        from gdo.mail_connector.ImapReader import ImapReader
        from gdo.mail_connector.IncomingPoller import IncomingPoller
        from gdo.mail_connector.MailArchive import MailArchive
        from gdo.mail_connector.UidCheckpoint import UidCheckpoint
        from gdo.mail_connector.module_mail_connector import module_mail_connector

        module = module_mail_connector.instance()
        host = module.get_config_val('mail_connector_imap_host')
        user = module.get_config_val('mail_connector_imap_user')
        password = module.get_config_val('mail_connector_imap_password')
        folder = module.get_config_val('mail_connector_imap_folder') or 'INBOX'
        port = module.get_config_value('mail_connector_imap_port')
        if not host or not user or not password:
            Logger.warning('Mail IMAP configuration is incomplete.')
            return False
        reader = ImapReader(host, port, user, password, folder)
        try:
            await reader.connect()
            await reader.uidvalidity()
            root = Path(Application.files_path('mails/'))
            root.mkdir(parents=True, mode=0o700, exist_ok=True)
            mailbox = hashlib.sha256(f'{host}\0{user}\0{folder}'.encode('utf-8')).hexdigest()
            self._reader = reader
            self._poller = IncomingPoller(reader, UidCheckpoint(root / 'checkpoints.sqlite'),
                                          MailArchive(root), mailbox, self._incoming_mail)
            self._connected = True
            self._poll_task = asyncio.create_task(self._poll_loop())
            return True
        except Exception as error:
            Logger.warning(f'Mail IMAP connection failed: {type(error).__name__}')
            if reader.client is not None:
                await reader.close()
            self._reader = None
            self._connected = False
            return False

    async def _incoming_mail(self, path, parsed):
        from gdo.mail_connector.module_mail_connector import module_mail_connector
        if module_mail_connector.instance().get_config_value('mail_connector_mira_inbox'):
            from gdo.mira.util import send_to_mira
            await asyncio.to_thread(send_to_mira, f'$inbox {path}', interrupt=False)

    async def _poll_loop(self):
        try:
            while self._connected:
                await self._poller.poll_once()
                await self._reader.wait_for_activity(30)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            Logger.warning(f'Mail IMAP polling stopped: {type(error).__name__}')
            self.connect_failed()
        finally:
            self._connected = False
            if self._reader is not None:
                reader, self._reader = self._reader, None
                await reader.close()

    async def gdo_disconnect(self, quit_message=None):
        self._connected = False
        if self._poll_task:
            task, self._poll_task = self._poll_task, None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def gdo_send_to_user(self, message, notice=False):
        recipient = message._env_user.get_mail(confirmed=True)
        if not recipient:
            raise ValueError('Mail recipient has no confirmed email address')
        mail = OutgoingMail.from_bot().recipient(recipient).subject('PyGDO message').body(message._result)
        if OutgoingMail.is_debug():
            sent = mail.send()
        else:
            mode = Application.get_mode()

            def send():
                Application.mode(mode)
                return mail.send()

            sent = await asyncio.to_thread(send)
        if not sent:
            raise RuntimeError('Mail submission failed')

    def gdo_get_dog_user(self):
        user = self._server.get_user_by_name('Dog')
        if not user:
            raise RuntimeError('Dog mail user is not configured')
        return user
