import tempfile
import unittest
from pathlib import Path

from gdo.mail_connector.UidCheckpoint import UidCheckpoint, UidValidityChanged


class UidCheckpointTest(unittest.TestCase):
    def test_persists_monotonic_and_rejects_changed_uidvalidity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cursor.sqlite'
            self.assertEqual(9, UidCheckpoint(path).advance('INBOX', 123, 9))
            self.assertEqual(9, UidCheckpoint(path).advance('INBOX', 123, 3))
            with self.assertRaises(UidValidityChanged):
                UidCheckpoint(path).advance('INBOX', 456, 10)
            self.assertEqual(9, UidCheckpoint(path).advance('INBOX', 123, 0))
