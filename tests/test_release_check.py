import pytest

from scripts.check_release import accepted, junit_counts


@pytest.mark.parametrize("body, expected", [
    ('<testcase name="ok"/>', True),
    ('<testcase name="skipped"><skipped/></testcase>', False),
    ('<testcase name="failed"><failure/></testcase>', False),
    ('<testcase name="error"><error/></testcase>', False),
    ('', False),
])
def test_acceptance_requires_executed_tests_without_skips(tmp_path, body, expected):
    xml = tmp_path / "result.xml"
    xml.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")
    assert accepted(junit_counts(xml)) is expected
