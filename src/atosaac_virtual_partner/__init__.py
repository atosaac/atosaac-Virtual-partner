"""Virtual Partner package."""
from .health import build_health_report


def main() -> None:
    """Keep the original package entry point working."""
    from .cli import main as cli_main

    cli_main()
