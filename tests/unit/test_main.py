import subprocess
import sys


def test_python_m_pepper_help_names_pepper():
    proc = subprocess.run(
        [sys.executable, "-m", "pepper", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.startswith("Usage: pepper [opts]")
