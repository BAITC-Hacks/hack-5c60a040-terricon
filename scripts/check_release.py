"""Reproduce the offline acceptance checks and retain their complete output.

Run: python scripts/check_release.py --output docs/check_local.txt
The report contains no environment variables or API credentials.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def junit_counts(path):
    """Fail closed when pytest's machine-readable evidence is missing or empty."""
    cases = ET.parse(path).getroot().findall(".//testcase")
    counts = {"tests": len(cases), "failures": 0, "errors": 0, "skipped": 0}
    for case in cases:
        for key, tag in (("failures", "failure"), ("errors", "error"), ("skipped", "skipped")):
            counts[key] += int(case.find(tag) is not None)
    return counts


def accepted(counts):
    return counts["tests"] > 0 and not any(counts[k] for k in ("failures", "errors", "skipped"))


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    target = args.output.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8", AKIM_NO_LLM="1")
    env.pop("OPENAI_API_KEY", None)
    success = True
    # Never silently overwrite earlier evidence or a source file.
    with target.open("x", encoding="utf-8", newline="\n") as report:
        def note(value):
            report.write(str(value) + "\n")
            report.flush()
            print(value, flush=True)

        def run(label, command):
            nonlocal success
            note(f"\n=== {label} ===")
            started = time.monotonic()
            result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
            note(result.stdout.rstrip().replace("\0", "\n"))
            note(f"exit_code={result.returncode}; seconds={time.monotonic() - started:.2f}")
            success = success and result.returncode == 0
            return result

        note("Offline acceptance report")
        note(f"started_utc={datetime.now(timezone.utc).isoformat()}")
        note(f"python={platform.python_version()}; platform={platform.platform()}")
        run("Git commit", ["git", "rev-parse", "HEAD"])
        run("Tracked working-tree changes (empty means clean)", ["git", "diff", "HEAD", "--stat"])
        tracked = run("Tracked files", ["git", "ls-files", "-z"])
        # Hashes identify local content,
        # including code changes not committed yet, without reading .env or untracked files.
        note("\n=== SHA256 of tracked implementation and data ===")
        for name in sorted(tracked.stdout.rstrip("\n").split("\0")):
            path = ROOT / name
            if name and (path.suffix in {".py", ".json", ".toml"} or name == "requirements.txt"
                         or name.startswith("docs/environments/")) and path.is_file():
                note(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}")
        run("Installed versions", [sys.executable, "-m", "pip", "list", "--format=freeze"])
        run("Dependency consistency", [sys.executable, "-m", "pip", "check"])
        scenario = run("python scripts/check_scenario.py", [sys.executable, "scripts/check_scenario.py"])
        success = success and "11/11" in scenario.stdout
        with tempfile.TemporaryDirectory(prefix="akim-check-") as temp:
            xml = Path(temp) / "pytest.xml"
            run("python -m pytest -q", [sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"])
            try:
                counts = junit_counts(xml)
                note("pytest_counts=" + json.dumps(counts, sort_keys=True))
                success = success and accepted(counts)
            except (OSError, ET.ParseError) as exc:
                note(f"pytest_evidence_error={type(exc).__name__}")
                success = False
        note(f"finished_utc={datetime.now(timezone.utc).isoformat()}")
        note("RESULT=" + ("PASS" if success else "FAIL"))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
