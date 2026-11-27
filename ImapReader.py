"""TLS IMAP primitives; does not mark messages read or authenticate senders."""
import asyncio
import imaplib
import re


class ImapReader:
    MAX_BYTES = 256 * 1024

    def __init__(self, host, port, username, password, folder='INBOX'):
        self.host, self.port, self.username, self.password, self.folder = host, port, username, password, folder
        self.client = None
        self._lock = asyncio.Lock()

    async def _run(self, func, *args):
        async with self._lock:
            task = asyncio.create_task(asyncio.to_thread(func, *args))
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                # Don't let a cancelled coroutine overlap another IMAP command.
                try:
                    await asyncio.shield(task)
                finally:
                    raise

    def _connect(self):
        client = imaplib.IMAP4_SSL(self.host, self.port, timeout=45)
        try:
            client.login(self.username, self.password)
            status, _ = client.select(self.folder, readonly=True)
            if status != 'OK':
                raise RuntimeError('Cannot select IMAP folder')
            return client
        except BaseException:
            try:
                client.logout()
            except (OSError, imaplib.IMAP4.error):
                pass
            raise

    async def connect(self):
        if self.client is not None:
            raise RuntimeError('IMAP reader is already connected')
        self.client = await self._run(self._connect)

    def _idle(self, seconds):
        with self.client.idle(duration=seconds) as responses:
            for response in responses:
                return response
        return None

    async def wait_for_activity(self, seconds=30):
        if self.client is None:
            raise RuntimeError('IMAP reader is not connected')
        if not 1 <= seconds <= 30:
            raise ValueError('IMAP wait must be between 1 and 30 seconds')
        if b'IDLE' in self.client.capabilities and hasattr(self.client, 'idle'):
            return await self._run(self._idle, seconds)
        await asyncio.sleep(seconds)
        return await self._run(self.client.noop)

    def _fetch_after(self, last_uid):
        status, data = self.client.uid('search', None, 'UID', f'{last_uid + 1}:*')
        if status != 'OK' or not data or data[0] is None:
            raise RuntimeError('IMAP UID search failed')
        uids = sorted(int(uid) for uid in data[0].split() if uid.isdigit() and int(uid) > last_uid)
        result = []
        for uid in uids:
            status, parts = self.client.uid('fetch', str(uid), '(RFC822.SIZE)')
            metadata = b' '.join(part for part in (parts or []) if isinstance(part, bytes))
            match = re.search(rb'RFC822\.SIZE\s+(\d+)', metadata, re.I)
            if status != 'OK' or not match:
                raise RuntimeError('IMAP message size unavailable')
            if int(match.group(1)) > self.MAX_BYTES:
                result.append((uid, None))
                continue
            status, parts = self.client.uid('fetch', str(uid), '(BODY.PEEK[])')
            bodies = [part[1] for part in (parts or []) if isinstance(part, tuple) and isinstance(part[1], bytes)]
            if status != 'OK' or len(bodies) != 1 or len(bodies[0]) > self.MAX_BYTES:
                raise RuntimeError('IMAP message fetch failed')
            result.append((uid, bodies[0]))
        return result

    async def fetch_after(self, last_uid):
        if self.client is None:
            raise RuntimeError('IMAP reader is not connected')
        if not isinstance(last_uid, int) or isinstance(last_uid, bool) or last_uid < 0:
            raise ValueError('Invalid IMAP UID')
        return await self._run(self._fetch_after, last_uid)

    def _uidvalidity(self):
        status, data = self.client.response('UIDVALIDITY')
        if status != 'UIDVALIDITY' or not data or len(data) != 1 or not data[0]:
            raise RuntimeError('IMAP UIDVALIDITY unavailable')
        value = data[0]
        if not isinstance(value, bytes) or not value.isdigit() or int(value) < 1:
            raise RuntimeError('Invalid IMAP UIDVALIDITY')
        return int(value)

    async def uidvalidity(self):
        if self.client is None:
            raise RuntimeError('IMAP reader is not connected')
        return await self._run(self._uidvalidity)

    async def close(self):
        if self.client is not None:
            client, self.client = self.client, None
            await self._run(client.logout)
