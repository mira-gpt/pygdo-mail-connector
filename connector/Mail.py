import asyncio

from gdo.base.Application import Application
from gdo.base.Render import Mode
from gdo.core.Connector import Connector
from gdo.mail.Mail import Mail as OutgoingMail


class Mail(Connector):
    """Reserved mail connector; no transport is connected by this skeleton."""

    def get_render_mode(self):
        return Mode.render_mail

    async def gdo_connect(self):
        # Never claim to be connected until the transport is implemented.
        self._connected = False
        return False

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
