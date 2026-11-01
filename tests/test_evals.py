from scripts.run_evals import summarize_junit_report


def test_summarize_junit_report_counts_each_outcome(tmp_path):
    report_path = tmp_path / "results.xml"
    report_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <testsuites>
          <testsuite name="tests" tests="4" failures="1" errors="1" skipped="1">
            <testcase classname="tests.test_example" name="passed" />
            <testcase classname="tests.test_example" name="failed">
              <failure message="assertion failed" />
            </testcase>
            <testcase classname="tests.test_example" name="error">
              <error message="setup error" />
            </testcase>
            <testcase classname="tests.test_example" name="skipped">
              <skipped message="not supported" />
            </testcase>
          </testsuite>
        </testsuites>
        """,
        encoding="utf-8",
    )

    assert summarize_junit_report(report_path) == {
        "total": 4,
        "passed": 1,
        "failed": 1,
        "errors": 1,
        "skipped": 1,
    }
