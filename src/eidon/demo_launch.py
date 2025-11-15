from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
from typing import Final


def run_demo_web(args) -> int:
    # Path to the installed package directory (…/site-packages/eidon)
    pkg_dir: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent
    app: Final[str] = str(pkg_dir / "demo_web.py")

    # Use a stable venv in HOME so it works with pipx-installed packages
    venv_dir: Final[pathlib.Path] = pathlib.Path.home() / ".eidon-demo-venv"

    # Prefer Python 3.12 (prebuilt wheels for Streamlit deps), else fall back
    py = shutil.which("python3.12") or sys.executable

    if not venv_dir.exists():
        subprocess.run([py, "-m", "venv", str(venv_dir)], check=True)
        pip_py = str(venv_dir / "bin" / "python")
        subprocess.run([pip_py, "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([pip_py, "-m", "pip", "install", "streamlit", "pandas", "matplotlib"], check=True)

    streamlit_py = str(venv_dir / "bin" / "python")
    subprocess.run([streamlit_py, "-m", "streamlit", "run", app], check=True)
    return 0
