"""systemd bootstrap: silence fd sinks before importing the CLI or dependencies."""
import os
import sys


def entry():
    output = None
    try:
        output = os.dup(1)
        with open(os.devnull, 'w') as muted:
            os.dup2(muted.fileno(), 1)
            os.dup2(muted.fileno(), 2)
            sys.stdout = sys.stderr = muted
            from relttk.compat import enable
            enable()
            from relttk.operations import cli_entry
            def invoke():
                if len(sys.argv) < 2 or sys.argv[1] not in ('schedule-tick','operational-status','ledger-backup') or '--operational-output' not in sys.argv:
                    return 3
                import main
                return main.main()
            return cli_entry(invoke, output_fd=output)
    except BaseException:
        return 3  # No raw traceback even when the operational module is unavailable.
    finally:
        if output is not None:
            os.close(output)


if __name__ == '__main__':
    sys.exit(entry())
