import queue
import threading

import pytest

pytest.importorskip("requests")

# Salt sends events with non-ASCII characters unescaped
TEXT = "caf\u00e9 \u00c5ngstr\u00f6m a\u2028b"


def test_events(pepper_client, session_minion_id):
    events = queue.Queue()
    stream = pepper_client.events()

    def listen():
        for event in stream:
            events.put(event)

    threading.Thread(target=listen, daemon=True).start()
    # Give the stream a moment to connect before starting the job
    jid = None
    for _ in range(10):
        jid = pepper_client.local_async("*", "test.echo", [TEXT])["return"][0]["jid"]
        try:
            while True:
                event = events.get(timeout=3)
                if event["tag"] == f"salt/job/{jid}/ret/{session_minion_id}":
                    assert event["data"]["return"] == TEXT
                    return
        except queue.Empty:
            continue
    pytest.fail(f"No return event for job {jid}")
