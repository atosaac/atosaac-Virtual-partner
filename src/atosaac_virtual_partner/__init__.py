from .health import build_health_report


def main() -> None:
    report = build_health_report()
    print(report)