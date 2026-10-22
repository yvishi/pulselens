"""Task runner for every platform: `python scripts/dev.py <target>` from the repo root (there is no make).

Targets: setup, server, web, tunnel, test, test-web, e2e, lint. Stdlib only: it runs on whatever Python is on PATH,
before the venv exists.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
VENV = ROOT / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
PY_VERSION = "3.11"
REQUIREMENTS = ("server/requirements/engine.txt", "server/requirements/analysis.txt")
PYTEST = ("-m", "pytest", "-c", "server/pyproject.toml", "--rootdir", ".")


def run(*cmd: str | Path, cwd: Path = ROOT, check: bool = True, env: dict[str, str] | None = None) -> int:
    """Run a command (as a list, no shell), echoing it first."""
    args = [str(c) for c in cmd]
    exe = shutil.which(args[0]) or args[0]
    print("$", " ".join(args), flush=True)
    try:
        return subprocess.run([exe, *args[1:]], cwd=cwd, check=check, env={**os.environ, **(env or {})}).returncode
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)
    except KeyboardInterrupt:
        return 130


def need_venv() -> None:
    if not VENV_PY.exists():
        sys.exit("No .venv yet. Run `python scripts/dev.py setup` first.")


def setup(_: argparse.Namespace) -> None:
    # 1. Python 3.11 venv: uv fetches 3.11 itself; otherwise the Python running this script.
    if not VENV_PY.exists():
        if shutil.which("uv"):
            run("uv", "venv", VENV, "--python", PY_VERSION)
        else:
            if sys.version_info < (3, 11):  # noqa: UP036 -- runs on the system Python, which may be older
                sys.exit(f"Python {PY_VERSION}+ needed (found {sys.version.split()[0]}); install it or install uv.")
            run(sys.executable, "-m", "venv", VENV)
    # 2. Both requirements files, plus the server package itself (editable).
    reqs = [arg for r in REQUIREMENTS for arg in ("-r", r)]
    if shutil.which("uv"):
        run("uv", "pip", "install", "--python", VENV_PY, *reqs, "-e", "server")
    else:
        run(VENV_PY, "-m", "pip", "install", *reqs, "-e", "server")
    # 3. Web dependencies from the lockfile. No browser download: e2e drives the installed Brave
    #    (see web/playwright.config.ts; `npx playwright install chromium` in web/ adds Chromium if wanted).
    run("npm", "ci", cwd=WEB)
    # 4. A local .env from the template, so the server starts.
    env = ROOT / ".env"
    if not env.exists():
        shutil.copy(ROOT / ".env.example", env)
        print("Created .env from .env.example; set AGENT_PASSCODE before the demo.")
    # 5. Model files, when their owners' scripts exist.
    for script in ("scripts/fetch_models.py", "scripts/fetch_web_models.py"):
        if (ROOT / script).exists():
            run(VENV_PY, script, check=False)


def server(_: argparse.Namespace) -> None:
    need_venv()
    run(VENV_PY, "-m", "uvicorn", "pulselens.api.main:app", "--app-dir", "server", "--host", "127.0.0.1",
        "--port", "8000", "--reload", "--reload-dir", "server", check=False)


def web(_: argparse.Namespace) -> None:
    run("npm", "run", "dev", cwd=WEB, check=False)


def tunnel(_: argparse.Namespace) -> None:
    """A cloudflared quick tunnel to the web app: phones need HTTPS for the camera."""
    cloudflared = shutil.which("cloudflared")
    if not cloudflared:
        sys.exit("cloudflared is not installed: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")  # noqa: E501
    print("Open the console through the https://*.trycloudflare.com URL below (HTTPS customer links and QR codes).")
    run(cloudflared, "tunnel", "--url", "http://localhost:5173", check=False)


def test(args: argparse.Namespace) -> None:
    need_venv()
    run(VENV_PY, *PYTEST, *args.rest)


def test_web(_: argparse.Namespace) -> None:
    run("npm", "run", "typecheck", cwd=WEB)
    run("npm", "run", "test", cwd=WEB)


def e2e(args: argparse.Namespace) -> None:
    """Playwright in the installed Brave, headed (BRAVE_PATH overrides the location). Stop dev servers first."""
    need_venv()
    run("npx", "playwright", "test", *args.rest, cwd=WEB)


def lint(_: argparse.Namespace) -> None:
    need_venv()
    targets = [p for p in ("server", "scripts", "eval") if (ROOT / p).exists()]
    run(VENV_PY, "-m", "ruff", "check", "--config", "server/pyproject.toml", *targets)
    run("npm", "run", "lint", cwd=WEB)


TARGETS = {
    "setup": setup, "server": server, "web": web, "tunnel": tunnel,
    "test": test, "test-web": test_web, "e2e": e2e, "lint": lint,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", choices=TARGETS)
    parser.add_argument("rest", nargs=argparse.REMAINDER, help="passed through to pytest or playwright")
    args = parser.parse_args()
    TARGETS[args.target](args)


if __name__ == "__main__":
    main()
