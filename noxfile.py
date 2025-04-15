import datetime
import os
import pathlib
import shutil

import nox
from nox.command import CommandFailed


API_BACKEND = [os.environ.get("API_BACKEND")] or ["cherrypy", "tornado"]
PYTHON_VERSIONS = [os.environ.get("PYTHON_VERSIONS")] or ["3.8", "3.9", "3.10", "3.11"]

# Nox options
# Reuse existing virtualenvs
nox.options.reuse_existing_virtualenvs = True
#  Don't fail on missing interpreters
nox.options.error_on_missing_interpreters = False

# Be verbose when running under a CI context
CI_RUN = os.environ.get("CI")
PIP_INSTALL_SILENT = CI_RUN is False
SKIP_REQUIREMENTS_INSTALL = "SKIP_REQUIREMENTS_INSTALL" in os.environ
EXTRA_REQUIREMENTS_INSTALL = os.environ.get("EXTRA_REQUIREMENTS_INSTALL")
SALT_REQUIREMENT = os.environ.get("SALT_REQUIREMENT") or "salt"
COVERAGE_VERSION_REQUIREMENT = "coverage==5.5"

# Prevent Python from writing bytecode
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# Global Path Definitions
REPO_ROOT = pathlib.Path(__file__).resolve().parent
# Change current directory to REPO_ROOT
os.chdir(str(REPO_ROOT))

ARTIFACTS_DIR = REPO_ROOT / "artifacts"
# Make sure the artifacts directory exists
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
RUNTESTS_LOGFILE = ARTIFACTS_DIR / "runtests-{}.log".format(
    datetime.datetime.now().strftime("%Y%m%d%H%M%S.%f")
)
COVERAGE_REPORT_DB = REPO_ROOT / ".coverage"
COVERAGE_REPORT_PROJECT = ARTIFACTS_DIR.relative_to(REPO_ROOT) / "coverage-project.xml"
COVERAGE_REPORT_TESTS = ARTIFACTS_DIR.relative_to(REPO_ROOT) / "coverage-tests.xml"
JUNIT_REPORT = ARTIFACTS_DIR.relative_to(REPO_ROOT) / "junit-report.xml"


def _install_requirements(
    session,
    *passed_requirements,  # pylint: disable=unused-argument
    install_coverage_requirements=True,
    install_test_requirements=True,
    install_source=True,
    install_salt=True,
    install_extras=None,
):
    install_extras = install_extras or []
    if SKIP_REQUIREMENTS_INSTALL is False:
        # Always have the wheel package installed
        session.install("--progress-bar=off", "wheel", silent=PIP_INSTALL_SILENT)
        if install_coverage_requirements:
            session.install(
                "--progress-bar=off", COVERAGE_VERSION_REQUIREMENT, silent=PIP_INSTALL_SILENT
            )
        # Install the latest salt package
        if install_salt:
            session.install("--progress-bar=off", SALT_REQUIREMENT, silent=PIP_INSTALL_SILENT)

        if install_test_requirements:
            requirements_file = REPO_ROOT / "tests" / "requirements.txt"
            install_command = [
                "--progress-bar=off",
                "-r",
                str(requirements_file.relative_to(REPO_ROOT)),
            ]
            session.install(*install_command, silent=PIP_INSTALL_SILENT)

        if EXTRA_REQUIREMENTS_INSTALL:
            session.log(
                "Installing the following extra requirements because the "
                "EXTRA_REQUIREMENTS_INSTALL environment variable was set: "
                "EXTRA_REQUIREMENTS_INSTALL='%s'",
                EXTRA_REQUIREMENTS_INSTALL,
            )
            install_command = ["--progress-bar=off"]
            install_command += [req.strip() for req in EXTRA_REQUIREMENTS_INSTALL.split()]
            session.install(*install_command, silent=PIP_INSTALL_SILENT)

        if install_source:
            pkg = "."
            if install_extras:
                pkg += f"[{','.join(install_extras)}]"
            session.install("-e", pkg, silent=PIP_INSTALL_SILENT)
        elif install_extras:
            pkg = f".[{','.join(install_extras)}]"
            session.install(pkg, silent=PIP_INSTALL_SILENT)


"""
Nox session to run tests for corresponding python versions and salt versions
"""


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("api_backend", API_BACKEND)
def tests(session, api_backend):
    _install_requirements(session)

    args = [
        "--rootdir",
        str(REPO_ROOT),
        f"--log-file={RUNTESTS_LOGFILE.relative_to(REPO_ROOT)}",
        "--log-file-level=debug",
        "--show-capture=no",
        f"--junitxml={JUNIT_REPORT}",
        "--showlocals",
        "-ra",
        "-s",
    ]

    if session._runner.global_config.forcecolor:
        args.append("--color=yes")
    if not session.posargs:
        args.append("tests/")
    else:
        for arg in session.posargs:
            if arg.startswith("--color") and args[0].startswith("--color"):
                args.pop(0)
            args.append(arg)
        for arg in session.posargs:
            if arg.startswith("-"):
                continue
            if arg.startswith(f"tests{os.sep}"):
                break
            try:
                pathlib.Path(arg).resolve().relative_to(REPO_ROOT / "tests")
                break
            except ValueError:
                continue
        else:
            args.append("tests/")
    try:
        session.run(
            "coverage", "run", "-m", "pytest", f"--salt-api-backend=rest_{api_backend}", *args
        )
    finally:
        # Always combine and generate the XML coverage report
        try:
            session.run("coverage", "combine")
        except CommandFailed:
            # Sometimes some of the coverage files are corrupt which would
            # trigger a CommandFailed exception
            pass

        # Generate report for salt code coverage
        session.run(
            "coverage",
            "xml",
            "-o",
            str(COVERAGE_REPORT_PROJECT),
        )
        try:
            session.run("coverage", "report", "--show-missing", "--include=pepper/*")
        finally:
            # Move the coverage DB to artifacts/coverage in order for it to be archived by CI
            if COVERAGE_REPORT_DB.exists():
                shutil.move(str(COVERAGE_REPORT_DB), str(ARTIFACTS_DIR / COVERAGE_REPORT_DB.name))


@nox.session(python="3.10")
def flake8(session):
    _install_requirements(session)
    # Install flake8
    session.install("flake8")
    # Run flake8
    session.run("flake8", "tests/", "pepper/", "scripts/pepper", "setup.py")
