import importlib
import sys

# cli imports main, which rechecks compatibility. Do not present this temporary
# import shim as a conflicting implementation during that reentrant bootstrap.
_shim = sys.modules.pop(__name__)
try:
    _canonical = importlib.import_module('relttk.application.cli')
except BaseException:
    sys.modules[__name__] = _shim
    raise
sys.modules[__name__] = _canonical
