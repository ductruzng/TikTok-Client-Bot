"""Read-only inbox subprocess deadline; never credentials on argv or disk.

This bounds a blocking HTTP/name-enrichment task, not a security sandbox.
The subprocess cannot claim/send or access the ledger. It is reaped before return.
"""
import json
import multiprocessing
import os
import time

TIMEOUT_SECONDS = 45
MAX_BYTES = 4 * 1024 * 1024


def _collect(output, cookies, device_id):
    try:
        # Do not forward third-party output, exception text or cookie values.
        with open(os.devnull, 'w') as sink:
            os.dup2(sink.fileno(), 1)
            os.dup2(sink.fileno(), 2)
            from core.api import get_conversations
            raw = json.dumps(get_conversations(cookies=cookies, device_id=device_id)).encode('utf-8')
            output.send_bytes(raw if len(raw) <= MAX_BYTES else b'null')
    except Exception:
        output.send_bytes(b'null')
    finally:
        output.close()


def fetch(cookies, device_id=None, *, timeout=TIMEOUT_SECONDS):
    if not isinstance(cookies, dict) or not isinstance(cookies.get('sessionid'), str) or not cookies['sessionid']:
        raise ValueError('AUTHENTICATED_SESSION_REQUIRED')
    if type(timeout) not in (int, float) or not 0 < timeout <= TIMEOUT_SECONDS:
        raise ValueError('INBOX_DEADLINE_INVALID')
    ctx = multiprocessing.get_context('spawn')
    receive, output = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_collect, args=(output, cookies, device_id), daemon=True)
    started = False
    deadline = time.monotonic() + timeout
    try:
        process.start()
        started = True
        output.close()
        if not receive.poll(max(0, deadline - time.monotonic())):
            raise TimeoutError('INBOX_DEADLINE')
        try:
            raw = receive.recv_bytes(MAX_BYTES)
        except (EOFError, OSError):
            raise ValueError('INBOX_UNAVAILABLE') from None
        result = json.loads(raw)
        if not isinstance(result, list) or time.monotonic() >= deadline:
            raise ValueError('INBOX_UNAVAILABLE')
        return result
    finally:
        output.close()
        receive.close()
        if started:
            process.join(max(0, deadline - time.monotonic()))
            if process.is_alive():
                process.terminate()
                process.join(2)
            if process.is_alive():
                process.kill()
                process.join(2)
            if process.is_alive():
                raise RuntimeError('INBOX_CHILD_NOT_REAPED')
        process.close()
