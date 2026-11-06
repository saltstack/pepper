import http.server
import json
import logging
import threading

import pytest

import pepper.libpepper

LOGIN = {"return": [{"token": "s3cr3t-token", "expire": 0, "user": "pepper"}]}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        body = json.dumps(LOGIN).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "session_id=s3cr3t-token; Path=/")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


@pytest.fixture
def api_url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_debug_http_redacts_credentials(api_url, capsys, caplog):
    api = pepper.libpepper.Pepper(api_url, debug_http=True)
    api.auth = {"token": "0ld-token"}
    with caplog.at_level(logging.DEBUG, logger="pepper"):
        api.req("/login", {"username": "pepper", "password": "hunter2"})
        api.req("/run", [{"client": "local", "token": "run-token"}])
    out, err = capsys.readouterr()
    logged = caplog.text
    assert out == ""
    assert "send:" in err and "header:" in err
    for secret in ("hunter2", "s3cr3t-token", "0ld-token", "run-token"):
        assert secret not in err
        assert secret not in logged
    assert "X-Auth-Token: [redacted]" in err
    assert '"password": "[redacted]"' in err
    assert "Set-Cookie: [redacted]" in err


@pytest.mark.parametrize(
    "text,expected",
    [
        ("X-Auth-Token: abc\r\nAccept: x", "X-Auth-Token: [redacted]\r\nAccept: x"),
        (
            '{"password": "a\\"b", "user": "u"}',
            '{"password": "[redacted]", "user": "u"}',
        ),
        (b"authorization: Basic Zm9v", "authorization: [redacted]"),
    ],
)
def test_redact(text, expected):
    assert pepper.libpepper.redact(text) == expected
