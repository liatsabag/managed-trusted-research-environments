"""Unit test suite package."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

# Defensive shim for environments where anyio subdependency is not installed
class AnyioMock(ModuleType):
    def __getattr__(self, name):
        return MagicMock

for mod_name in ["anyio", "anyio.abc", "anyio.to_thread", "anyio.lowlevel"]:
    if mod_name not in sys.modules:
        m = AnyioMock(mod_name)
        m.ObjectReceiveStream = MagicMock
        m.ObjectSendStream = MagicMock
        m.CapacityLimiter = MagicMock
        m.to_thread = MagicMock()
        sys.modules[mod_name] = m
