"""Runtime regression tests for the serverless GenAI evaluation entry point."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def test_evaluation_entry_point_bootstraps_bundle_root_without_pythonpath(tmp_path):
    """Serverless ``exec`` can import the bundle package from its explicit root."""
    bundle_root = Path(__file__).parents[2]
    evaluation_script = bundle_root / "src" / "genai" / "evaluate.py"
    exec_script = (
        "import pathlib, sys; "
        "script = pathlib.Path(sys.argv.pop(1)); "
        "exec(compile(script.read_text(), str(script), 'exec'), "
        "{'__name__': '__main__'})"
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            exec_script,
            str(evaluation_script),
            "--bundle-root",
            str(bundle_root),
            "--help",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "--bundle-root BUNDLE_ROOT" in completed.stdout
