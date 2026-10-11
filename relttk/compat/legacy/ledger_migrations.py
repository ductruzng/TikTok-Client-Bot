import importlib
import sys

sys.modules[__name__] = importlib.import_module('relttk.storage.ledger_migrations')
