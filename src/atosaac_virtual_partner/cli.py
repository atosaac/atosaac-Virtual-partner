import argparse
from collections.abc import Sequence
from pathlib import Path

from .character import CharacterLoadError, load_character
from .chat import run_chat
from .health import build_health_report


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Local AI virtual companion for macOS."
    )

    subcommands = parser.add_subparsers(
        dest="command",
        required=True,
    )
    subcommands.add_parser(
        "health",
        help="Show information about the local environment.",
    )
    chat_parser = subcommands.add_parser(
        "chat",
        help="Start a terminal chat session.",
    )
    chat_parser.add_argument(
        "--character-file",
        type=Path,
        help="Load an external Markdown character profile.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected Virtual Partner command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        print(build_health_report())
        return

    if args.command == "chat":
        try:
            character = load_character(args.character_file)
        except CharacterLoadError as exc:
            parser.error(str(exc))
        run_chat(character_profile=character)
