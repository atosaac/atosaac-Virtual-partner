from atosaac_virtual_partner.health import build_health_report


def test_build_health_report_contains_required_information() -> None:
    report = build_health_report()

    assert "Virtual Partner" in report
    assert "Python:" in report
    assert "macOS:" in report
    assert "Architecture:" in report
    assert "Status: ready" in report