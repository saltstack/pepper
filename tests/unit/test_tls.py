import datetime
import http.server
import ipaddress
import json
import ssl
import sys
import threading

import pytest

import pepper.cli
import pepper.libpepper
from pepper.exceptions import PepperArgumentsException, PepperException

x509 = pytest.importorskip("cryptography.x509")
hashes = pytest.importorskip("cryptography.hazmat.primitives.hashes")
serialization = pytest.importorskip("cryptography.hazmat.primitives.serialization")
ec = pytest.importorskip("cryptography.hazmat.primitives.asymmetric.ec")

LOGIN_RESPONSE = {"return": [{"token": "abc", "expire": 0}]}


def _write_key(key, path):
    path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )


def _write_cert(cert, path):
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _cert(subject, issuer, public_key, signing_key, extensions):
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=1))
    )
    for extension, critical in extensions:
        builder = builder.add_extension(extension, critical=critical)
    return builder.sign(signing_key, hashes.SHA256())


@pytest.fixture(scope="module")
def tls_files(tmp_path_factory):
    """
    A CA certificate and a localhost server certificate signed by it
    """
    path = tmp_path_factory.mktemp("tls")
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name(
        [x509.NameAttribute(x509.NameOID.COMMON_NAME, "pepper test CA")]
    )
    ca_ski = x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key())
    ca_cert = _cert(
        ca_name,
        ca_name,
        ca_key.public_key(),
        ca_key,
        [
            (x509.BasicConstraints(ca=True, path_length=None), True),
            (
                x509.KeyUsage(
                    digital_signature=False,
                    content_commitment=False,
                    key_encipherment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=True,
                    crl_sign=True,
                    encipher_only=False,
                    decipher_only=False,
                ),
                True,
            ),
            (ca_ski, False),
        ],
    )

    server_key = ec.generate_private_key(ec.SECP256R1())
    server_cert = _cert(
        x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost")]),
        ca_name,
        server_key.public_key(),
        ca_key,
        [
            (x509.BasicConstraints(ca=False, path_length=None), True),
            (
                x509.SubjectAlternativeName(
                    [
                        x509.DNSName("localhost"),
                        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                    ]
                ),
                False,
            ),
            (x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.SERVER_AUTH]), False),
            (
                x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski),
                False,
            ),
        ],
    )

    client_key = ec.generate_private_key(ec.SECP256R1())
    client_cert = _cert(
        x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "pepper")]),
        ca_name,
        client_key.public_key(),
        ca_key,
        [
            (x509.BasicConstraints(ca=False, path_length=None), True),
            (x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]), False),
            (
                x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski),
                False,
            ),
        ],
    )

    files = {
        "ca_cert": path / "ca.pem",
        "server_cert": path / "server.pem",
        "server_key": path / "server.key",
        "client_cert": path / "client.pem",
        "client_key": path / "client.key",
        "client_combined": path / "client-combined.pem",
    }
    _write_cert(ca_cert, files["ca_cert"])
    _write_cert(server_cert, files["server_cert"])
    _write_key(server_key, files["server_key"])
    _write_cert(client_cert, files["client_cert"])
    _write_key(client_key, files["client_key"])
    files["client_combined"].write_bytes(
        files["client_cert"].read_bytes() + files["client_key"].read_bytes()
    )
    return files


class _LoginHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # pylint: disable=invalid-name
        self._reply()

    def do_POST(self):  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._reply()

    def _reply(self):
        body = json.dumps(LOGIN_RESPONSE).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


class _QuietHTTPServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        # The client aborting the TLS handshake is expected in these tests
        pass


@pytest.fixture(params=[False], ids=["no-client-cert"])
def https_api(request, tls_files):
    """
    The URL of a local HTTPS server that answers every request with a login token

    Parametrize indirectly with True to require a client certificate.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tls_files["server_cert"], tls_files["server_key"])
    if request.param:
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(tls_files["ca_cert"])
    server = _QuietHTTPServer(("127.0.0.1", 0), _LoginHandler)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://localhost:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_import_keeps_default_https_context():
    assert ssl._create_default_https_context is ssl.create_default_context


def test_untrusted_certificate_is_rejected(https_api):
    api = pepper.libpepper.Pepper(https_api)
    with pytest.raises(PepperException, match="certificate verification failed") as exc:
        api.req("/login", {"username": "pepper"})
    assert ".." not in str(exc.value)


def test_ignore_ssl_errors(https_api):
    api = pepper.libpepper.Pepper(https_api, ignore_ssl_errors=True)
    assert api.req("/login", {"username": "pepper"}) == LOGIN_RESPONSE


def test_ca_bundle(https_api, tls_files):
    api = pepper.libpepper.Pepper(https_api, ca_bundle=str(tls_files["ca_cert"]))
    assert api.req("/login", {"username": "pepper"}) == LOGIN_RESPONSE


def test_ca_bundle_requests(https_api, tls_files):
    pytest.importorskip("requests")
    api = pepper.libpepper.Pepper(https_api, ca_bundle=str(tls_files["ca_cert"]))
    api.auth = {"token": "abc"}
    assert api.req_get("/keys") == LOGIN_RESPONSE


def test_ca_bundle_directory(tmp_path, monkeypatch):
    calls = []

    def create_default_context(**kwargs):
        calls.append(kwargs)
        return ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    monkeypatch.setattr(ssl, "create_default_context", create_default_context)
    pepper.libpepper.Pepper(ca_bundle=str(tmp_path))._ssl_context()
    assert calls == [{"capath": str(tmp_path)}]


@pytest.mark.parametrize("https_api", [True], ids=["client-cert"], indirect=True)
def test_client_cert_required(https_api, tls_files):
    api = pepper.libpepper.Pepper(https_api, ca_bundle=str(tls_files["ca_cert"]))
    with pytest.raises(OSError):
        api.req("/login", {"username": "pepper"})


@pytest.mark.parametrize("https_api", [True], ids=["client-cert"], indirect=True)
@pytest.mark.parametrize("separate_key", [True, False], ids=["key-file", "combined"])
def test_client_cert(https_api, tls_files, separate_key):
    if separate_key:
        cert = {
            "client_cert": str(tls_files["client_cert"]),
            "client_cert_key": str(tls_files["client_key"]),
        }
    else:
        cert = {"client_cert": str(tls_files["client_combined"])}
    api = pepper.libpepper.Pepper(
        https_api, ca_bundle=str(tls_files["ca_cert"]), **cert
    )
    assert api.req("/login", {"username": "pepper"}) == LOGIN_RESPONSE


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, {"verify": True, "cert": None}),
        ({"ignore_ssl_errors": True}, {"verify": False, "cert": None}),
        ({"ca_bundle": "ca.pem"}, {"verify": "ca.pem", "cert": None}),
        (
            {"ignore_ssl_errors": True, "ca_bundle": "ca.pem"},
            {"verify": False, "cert": None},
        ),
        ({"client_cert": "c.pem"}, {"verify": True, "cert": "c.pem"}),
        (
            {"client_cert": "c.pem", "client_cert_key": "c.key"},
            {"verify": True, "cert": ("c.pem", "c.key")},
        ),
    ],
)
def test_requests_tls(kwargs, expected):
    assert pepper.libpepper.Pepper(**kwargs)._requests_tls() == expected


def test_parse_tls_precedence(tmp_path, monkeypatch):
    rcfile = tmp_path / "pepperrc"
    rcfile.write_text(
        "[main]\nSALTAPI_CA_BUNDLE=file-ca.pem\nSALTAPI_CLIENT_CERT=file-cert.pem\n"
    )
    monkeypatch.setenv("SALTAPI_CLIENT_CERT", "env-cert.pem")
    monkeypatch.setattr(
        sys,
        "argv",
        ["pepper", "-c", str(rcfile), "--client-cert-key", "cli-key.pem"],
    )
    assert pepper.cli.PepperCli().parse_tls() == {
        "ca_bundle": "file-ca.pem",
        "client_cert": "env-cert.pem",
        "client_cert_key": "cli-key.pem",
    }


def test_parse_tls_key_without_cert(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["pepper", "-c", str(tmp_path / "none"), "--client-cert-key", "key.pem"],
    )
    with pytest.raises(PepperArgumentsException):
        pepper.cli.PepperCli().parse_tls()


def test_missing_ca_bundle_is_reported(tmp_path):
    missing = str(tmp_path / "missing.pem")
    api = pepper.libpepper.Pepper("https://localhost:1/", ca_bundle=missing)
    with pytest.raises(
        PepperException, match=f"Unable to load the CA bundle {missing}"
    ):
        api.req("/login", {"username": "pepper"})


def test_missing_client_cert_is_reported(tmp_path, tls_files):
    missing = str(tmp_path / "missing.pem")
    api = pepper.libpepper.Pepper(
        "https://localhost:1/", ca_bundle=str(tls_files["ca_cert"]), client_cert=missing
    )
    with pytest.raises(
        PepperException, match=f"Unable to load the client certificate {missing}"
    ):
        api.req("/login", {"username": "pepper"})


def test_ssl_context_is_built_once(tls_files):
    api = pepper.libpepper.Pepper(ca_bundle=str(tls_files["ca_cert"]))
    assert api._ssl_context() is api._ssl_context()


def test_http_does_not_load_tls_files(tmp_path, monkeypatch):
    api = pepper.libpepper.Pepper(
        "http://127.0.0.1:1/", ca_bundle=str(tmp_path / "missing.pem")
    )
    monkeypatch.setattr(api, "_ssl_context", lambda: pytest.fail("built a context"))
    with pytest.raises(Exception) as exc:
        api.req("/login", {"username": "pepper"})
    assert "built a context" not in str(exc.value)
