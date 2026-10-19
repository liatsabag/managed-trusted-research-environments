"""App package for Central Administrator Portal."""

import sys
import types
from pathlib import Path

# Provide 'backend' package resolution when invoked from inside backend/
if "backend" not in sys.modules:
    _backend_dir = Path(__file__).resolve().parent.parent
    _b = types.ModuleType("backend")
    _b.__path__ = [str(_backend_dir)]
    sys.modules["backend"] = _b
    try:
        import app
        _b.app = app
        sys.modules["backend.app"] = app
    except ImportError:
        pass
