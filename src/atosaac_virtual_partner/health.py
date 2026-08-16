import platform


def build_health_report() -> str:
    """Collect basic information about the local development environment."""
    python_version = platform.python_version()
    macos_version = platform.mac_ver()[0] or "unknown"
    architecture = platform.machine()

    return (
        "Virtual Partner\n"
        f"Python: {python_version}\n"
        f"macOS: {macos_version}\n"
        f"Architecture: {architecture}\n"
        "Status: ready"
    )
