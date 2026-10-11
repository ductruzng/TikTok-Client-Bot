"""Strict schedule input and encoding-safe presentation; never alter stored data."""
import builtins
import sys


class TerminalInputError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def read(prompt):
    # A replacement decoder could corrupt a reason before input() returns it.
    if getattr(sys.stdin, 'errors', None) not in (None, 'strict', 'surrogateescape'):
        raise TerminalInputError('TERMINAL_STRICT_INPUT_REQUIRED')
    try:
        value = builtins.input(prompt)
    except UnicodeDecodeError:
        raise TerminalInputError('TERMINAL_INPUT_ENCODING: configure strict UTF-8 stdin') from None
    except UnicodeEncodeError:
        raise TerminalInputError('TERMINAL_PROMPT_ENCODING: configure UTF-8 stdout') from None
    except EOFError:
        raise TerminalInputError('TERMINAL_INPUT_EOF: no confirmation recorded') from None
    except KeyboardInterrupt:
        raise TerminalInputError('TERMINAL_INPUT_CANCELLED: no confirmation recorded') from None
    try:
        # POSIX surrogateescape preserves undecodable bytes; refuse them explicitly.
        value.encode('utf-8', errors='strict')
    except UnicodeEncodeError:
        raise TerminalInputError('TERMINAL_INPUT_ENCODING: configure strict UTF-8 stdin') from None
    return value


def write(*values, sep=' ', end='\n'):
    text = sep.join(str(value) for value in values) + end
    encoding = getattr(sys.stdout, 'encoding', None) or 'utf-8'
    # Escape only unrepresentable output. Reasons, challenges and payloads stay exact.
    text = text.encode(encoding, errors='backslashreplace').decode(encoding)
    sys.stdout.write(text)
