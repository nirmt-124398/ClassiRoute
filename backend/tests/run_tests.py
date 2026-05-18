from __future__ import annotations

import os
import subprocess
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.helpers import next_report_dir


def main() -> int:
    report_dir = next_report_dir(Path("reports"))
    report_file = report_dir / "pytest-report.json"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests",
        "-v",
        "--json-report",
        f"--json-report-file={report_file}",
    ]
    env = os.environ.copy()
    env["PYTEST_JSON_REPORT_FILE"] = str(report_file)
    env["PYTEST_REPORT_DIR"] = str(report_dir)
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
