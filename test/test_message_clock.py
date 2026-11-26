import contextlib
import unittest
from unittest.mock import AsyncMock, patch

from gdo.base.Message import Message
from gdo.base.Render import Mode


class MessageClockTest(unittest.IsolatedAsyncioTestCase):
    async def test_execution_ticks_before_message_processing(self):
        message = Message('hello', Mode.render_txt)
        message._env_server = None
        with patch('gdo.base.Message.Application.tick') as tick, \
             patch('gdo.base.Trans.Trans.message_context', return_value=contextlib.nullcontext()), \
             patch.object(message, '_execute_in_context', new_callable=AsyncMock) as execute:
            execute.side_effect = lambda: tick.assert_called_once_with()
            await message.execute()
        execute.assert_awaited_once()
