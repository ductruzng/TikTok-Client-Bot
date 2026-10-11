import importlib
import sys

sys.modules[__name__] = importlib.import_module('relttk.application.tui')
