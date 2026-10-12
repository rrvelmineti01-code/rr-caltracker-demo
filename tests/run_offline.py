"""Run all checks with network connections and unmocked HTTP requests forbidden."""
import socket
import sys
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

if __name__ == "__main__":
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Offline tests cannot connect to the network")), \
         patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Offline tests cannot connect to the network")), \
         patch.object(urllib.request, "urlopen", side_effect=AssertionError("Unmocked HTTP request blocked in offline test")):
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
