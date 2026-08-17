from wowhelper.raidbots import parse_report_id


def test_full_url():
    assert (
        parse_report_id("https://www.raidbots.com/simbot/report/aBcDeF123456789012345x")
        == "aBcDeF123456789012345x"
    )


def test_url_without_www_and_with_suffix():
    assert (
        parse_report_id("http://raidbots.com/simbot/report/aBcDeF123456789012345x/simc")
        == "aBcDeF123456789012345x"
    )


def test_reports_url_variant():
    assert parse_report_id("https://www.raidbots.com/reports/xyzXYZ0987654321abcdef/data.json") == (
        "xyzXYZ0987654321abcdef"
    )


def test_bare_id():
    assert parse_report_id("  aBcDeF123456789012345x ") == "aBcDeF123456789012345x"


def test_garbage():
    assert parse_report_id("kein link") is None
    assert parse_report_id("https://example.com/simbot/report/abc123456789") is None
    assert parse_report_id("") is None
    assert parse_report_id("abc!") is None
