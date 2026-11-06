import http.server
import json
import logging
import socket
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

import pepper.script
from pepper.exceptions import PepperAuthException, PepperException
from pepper.libpepper import Pepper

CHERRYPY_401 = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"></meta>
    <title>401 Unauthorized</title>
</head>
    <body>
        <h2>401 Unauthorized</h2>
        <p>Could not authenticate using provided credentials</p>
        <pre id="traceback"></pre>
    <div id="powered_by">
      <span>
        Powered by <a href="http://www.cherrypy.dev">CherryPy 18.10.0</a>
      </span>
    </div>
    </body>
</html>
"""

TORNADO_401 = (
    "<html><title>401: Unauthorized</title><body>401: Unauthorized</body></html>"
)


class _Handler(http.server.BaseHTTPRequestHandler):
    status = 200
    body = "{}"

    def do_GET(self):  # pylint: disable=invalid-name
        self._reply()

    def do_POST(self):  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._reply()

    def _reply(self):
        body = self.body.encode()
        self.send_response(self.status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


@pytest.fixture
def api_server():
    """
    Start a local HTTP server and return a function that sets its response
    """
    handler = type("Handler", (_Handler,), {})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def respond(status, body):
        handler.status = status
        handler.body = body
        return f"http://127.0.0.1:{server.server_address[1]}/"

    try:
        yield respond
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "status,body,exc_class,message",
    [
        (
            500,
            json.dumps({"status": 500, "return": "An unexpected error occurred"}),
            PepperException,
            "Server error: An unexpected error occurred",
        ),
        (
            401,
            CHERRYPY_401,
            PepperAuthException,
            "Authentication denied: Could not authenticate using provided credentials",
        ),
        (401, TORNADO_401, PepperAuthException, "Authentication denied"),
        (503, "", PepperException, "HTTP 503 Service Unavailable"),
        (
            400,
            json.dumps({"status": 400, "return": {"error": "bad lowstate"}}),
            PepperException,
            'HTTP 400 Bad Request: {"error": "bad lowstate"}',
        ),
    ],
    ids=["json-500", "cherrypy-401", "tornado-401", "empty-503", "json-object"],
)
def test_http_error_detail(api_server, status, body, exc_class, message):
    api = Pepper(api_server(status, body))
    with pytest.raises(exc_class) as excinfo:
        api.req("/login", {"username": "pepper"})
    assert str(excinfo.value) == message


def test_auth_exception_is_a_pepper_exception():
    assert issubclass(PepperAuthException, PepperException)


def test_invalid_json(api_server):
    api = Pepper(api_server(200, "<html>not json</html>"))
    with pytest.raises(PepperException, match="Unable to parse the server response"):
        api.req("/login", {"username": "pepper"})


def test_connection_refused():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    api = Pepper(f"http://127.0.0.1:{port}/")
    with pytest.raises(PepperException, match="Unable to connect to"):
        api.req("/login", {"username": "pepper"})


def test_req_get_raises(api_server):
    pytest.importorskip("requests")
    api = Pepper(api_server(500, json.dumps({"return": "boom"})))
    api.auth = {"token": "abc"}
    with pytest.raises(PepperException, match="Server error: boom"):
        api.req_get("/keys")


def test_req_get_requires_token():
    pytest.importorskip("requests")
    with pytest.raises(PepperAuthException, match="Authentication required"):
        Pepper().req_get("/keys")


def test_uncaught_errors_go_to_stderr(capsys):
    sys.argv = ["pepper", "*", "test.ping"]
    with patch("pepper.cli.PepperCli.login", MagicMock(side_effect=KeyError("x"))):
        assert pepper.script.Pepper()() == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "Uncaught Pepper error: 'x'" in err


@pytest.fixture
def restore_pepper_logger():
    pepper_logger = logging.getLogger("pepper")
    handlers, propagate, level = (
        list(pepper_logger.handlers),
        pepper_logger.propagate,
        pepper_logger.level,
    )
    yield pepper_logger
    pepper_logger.handlers[:] = handlers
    pepper_logger.propagate = propagate
    pepper_logger.setLevel(level)


def _run_pepper(*args):
    sys.argv = ["pepper", *args, "*", "test.ping"]
    with (
        patch("pepper.cli.PepperCli.login", MagicMock()),
        patch("pepper.cli.PepperCli.low", MagicMock(return_value={"return": [{}]})),
    ):
        pepper.script.Pepper()()


def test_verbose_logging(capsys, restore_pepper_logger):
    # Importing salt puts a handler on the root logger, which used to keep
    # pepper from adding its own, so -v printed nothing
    _run_pepper("-vvv")
    logging.getLogger("pepper.test").debug("debug message")
    assert "debug message" in capsys.readouterr().err


def test_log_records_printed_once(capsys, restore_pepper_logger):
    _run_pepper()
    _run_pepper()
    logging.getLogger("pepper.test").error("error message")
    assert capsys.readouterr().err.count("error message") == 1
    assert restore_pepper_logger.propagate is False


def test_requests_connection_error():
    pytest.importorskip("requests")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    api = Pepper(f"http://127.0.0.1:{port}/")
    api.auth = {"token": "abc"}
    with pytest.raises(PepperException, match="Unable to connect to"):
        api.req_get("/keys")


def test_requests_invalid_json(api_server):
    pytest.importorskip("requests")
    api = Pepper(api_server(200, "<html>not json</html>"))
    api.auth = {"token": "abc"}
    with pytest.raises(PepperException, match="Unable to parse the server response"):
        api.req_get("/keys")
