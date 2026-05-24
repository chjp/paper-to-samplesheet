#!/usr/bin/env python3
"""Create/check the local environment used by the paper-to-samplesheet skill."""

from __future__ import annotations

import argparse
import subprocess
import sys
import venv
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def venv_python(root: Path) -> Path:
    if sys.platform == "win32":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def docling_importable(python: Path) -> bool:
    result = subprocess.run(
        [str(python), "-c", "import docling"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def ensure_env(root: Path) -> Path:
    python = venv_python(root)
    if not python.exists():
        venv.EnvBuilder(with_pip=True).create(root / ".venv")

    if not docling_importable(python):
        requirements = root / "requirements.txt"
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", str(requirements)],
            check=True,
        )

    return python


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=project_root())
    args = parser.parse_args()
    python = ensure_env(args.root.resolve())
    print(python)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
