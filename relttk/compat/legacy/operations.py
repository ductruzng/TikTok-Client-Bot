"""Fixed legacy alias for the canonical operations implementation."""
import importlib
import sys
sys.modules[__name__] = importlib.import_module("relttk.operations")
