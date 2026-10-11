import importlib
import sys

# oneshot imports main; its repeated bootstrap must not see a provisional alias.
_shim = sys.modules.pop(__name__)
try:
    _canonical = importlib.import_module('relttk.transport.oneshot')
except BaseException:
    sys.modules[__name__] = _shim
    raise
sys.modules[__name__] = _canonical
