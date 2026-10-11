import importlib
import sys

sys.modules[__name__] = importlib.import_module('relttk.transport.client')
