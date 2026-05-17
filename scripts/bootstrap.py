from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    venv = root / ".venv"
    python = _venv_python(venv)

    if not python.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)], cwd=root)

    subprocess.check_call([str(python), "-m", "pip", "install", "-e", ".[dev]"], cwd=root)
    subprocess.check_call([str(python), "-m", "pytest", "-q"], cwd=root)
    subprocess.check_call([str(python), "-m", "physical_agent.cli", "setup", "--smoke-test"], cwd=root)

    print()
    print("Physical Agent is ready.")
    print("Start the GUI with:")
    if os.name == "nt":
        print(r".\.venv\Scripts\physical-agent.exe gui")
    else:
        print("./.venv/bin/physical-agent gui")
    return 0


def _venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


if __name__ == "__main__":
    raise SystemExit(main())

