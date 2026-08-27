"""Shared helper for invoking this repo's headless-GIMP batch scripts."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def run_gimp_batch(script_name: str, env_var: str, job: dict, timeout: int = 500) -> str:
    """Write `job` to a temp JSON file, run `<script_name>` against it inside
    headless flatpak GIMP, and return the path to the resulting `.log` file.
    Raises RuntimeError if GIMP itself fails to run or times out (per-page
    failures are reported inside the log, not raised)."""
    script_path = SCRIPTS_DIR / script_name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(job, f)
        job_path = f.name
    log_path = job_path + ".log"
    try:
        subprocess.run(
            ["flatpak", "run", f"--env={env_var}={job_path}", "org.gimp.GIMP",
             "-idf", "--batch-interpreter=python-fu-eval",
             "-b", f"exec(open('{script_path}').read())", "--quit"],
            capture_output=True, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"GIMP timed out running {script_name}") from e
    if not os.path.exists(log_path):
        raise RuntimeError(f"GIMP produced no log for {script_name} (job: {job_path})")
    return log_path


def check_log_ok(log_path: str) -> None:
    """Raise RuntimeError if the batch script's log doesn't end in DONE, or
    print any FAIL lines it recorded per-page."""
    text = Path(log_path).read_text()
    for fail in re.findall(r"^FAIL .*(?:\n(?!OK|FAIL|DONE).*)*", text, re.MULTILINE):
        print(fail.strip())
    if "DONE" not in text:
        raise RuntimeError(f"GIMP batch script did not finish cleanly, see {log_path}")


def venv_python(repo_root: Path) -> str:
    candidate = repo_root / "venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else "python3"
