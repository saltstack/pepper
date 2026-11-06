import datetime
import http.server
import ipaddress
import json
import ssl
import threading

import pytest

import pepper.libpepper
from pepper.exceptions import PepperException

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

    files = {
        "ca_cert": path / "ca.pem",
        "server_cert": path / "server.pem",
        "server_key": path / "server.key",
    }
    _write_cert(ca_cert, files["ca_cert"])
    _write_cert(server_cert, files["server_cert"])
    _write_key(server_key, files["server_key"])
    return files


class _LoginHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # pylint: disable=invalid-name
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
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


@pytest.fixture
def https_api(tls_files):
    """
    The URL of a local HTTPS server that answers every POST with a login token
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tls_files["server_cert"], tls_files["server_key"])
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
