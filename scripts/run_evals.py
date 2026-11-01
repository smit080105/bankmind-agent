"""Run the offline test suite and report measured results."""
import sys
import subprocess
import time
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


def summarize_junit_report(report_path: Path) -> dict[str, int]:
    """Count test outcomes from pytest's JUnit XML report."""
    totals = {"total": 0, "passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for testcase in ET.parse(report_path).iter("testcase"):
        totals["total"] += 1
        if testcase.find("skipped") is not None:
            totals["skipped"] += 1
        elif testcase.find("failure") is not None:
            totals["failed"] += 1
        elif testcase.find("error") is not None:
            totals["errors"] += 1
        else:
            totals["passed"] += 1
    return totals


def main():
    print("=" * 72)
    print("  BANKMIND OFFLINE EVALUATION")
    print("=" * 72)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    print("Running the offline pytest suite...\n")

    with tempfile.TemporaryDirectory(prefix="bankmind-evals-") as temp_dir:
        report_path = Path(temp_dir) / "results.xml"
        cmd = [
            sys.executable, "-m", "pytest", "tests/", "-q", "--disable-warnings",
            f"--junitxml={report_path}",
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )

        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")

        totals = summarize_junit_report(report_path)

    print("-" * 72)
    print(
        "  Tests: {total} | Passed: {passed} | Failed: {failed} | "
        "Errors: {errors} | Skipped: {skipped}".format(**totals)
    )
    status = "PASS" if result.returncode == 0 else "FAIL"
    print(f"  RESULT: {status}")
    print("=" * 72)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
