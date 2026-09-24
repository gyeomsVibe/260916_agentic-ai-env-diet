"""U35: found by running the new harness for real on Linux — a stray broker socket in the project crashed the pilot."""

from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path

from v7_harness.broker.ipc import make_local_pipe_name
from v7_harness.isolation.manifest import build_manifest


@unittest.skipIf(os.name == "nt" or not hasattr(socket, "AF_UNIX"), "POSIX sockets only")
class PosixHygieneTests(unittest.TestCase):
    def test_manifest_skips_a_unix_socket_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.addCleanup(server.close)
            server.bind(str(root / "stale.sock"))
            self.assertEqual(["a.py"], [entry.path for entry in build_manifest(root).entries])

    def test_manifest_skips_a_fifo_instead_of_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            os.mkfifo(root / "pipe")
            self.assertEqual(["a.py"], [entry.path for entry in build_manifest(root).entries])

    def test_broker_socket_lives_in_the_temp_dir_not_the_project(self) -> None:
        self.assertEqual(Path(tempfile.gettempdir()), Path(make_local_pipe_name("n")).parent)


if __name__ == "__main__":
    unittest.main()
