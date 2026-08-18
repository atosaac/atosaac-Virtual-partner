import argparse
from collections.abc import Sequence
from pathlib import Path

from .character import CharacterLoadError, load_character
from .chat import run_chat
from .health import build_health_report
from .initiative import IdleInitiativePolicy
from .providers import DEFAULT_OLLAMA_URL, OllamaReplyProvider
from .reply import MockReplyProvider, ReplyProvider


PROVIDER_NAMES = ("mock", "ollama")


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
    chat_parser.add_argument(
        "--provider",
        choices=PROVIDER_NAMES,
        default="mock",
        help="Reply provider to use (default: mock).",
    )
    chat_parser.add_argument(
        "--model",
        help=(
            "Model name required by the Ollama provider, "
            "for example qwen3:4b-instruct."
        ),
    )
    chat_parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help=f"Ollama server URL (default: {DEFAULT_OLLAMA_URL}).",
    )
    chat_parser.add_argument(
        "--show-metrics",
        action="store_true",
        help="Show latency and token metrics after each successful reply.",
    )
    chat_parser.add_argument(
        "--idle-initiative-seconds",
        type=float,
        help=(
            "Let the character speak once after this many idle seconds "
            "(disabled by default)."
        ),
    )

    return parser


def build_reply_provider(
    provider_name: str,
    model: str | None,
    ollama_url: str,
) -> ReplyProvider:
    """Build a configured provider without coupling it to the chat loop."""
    if provider_name == "mock":
        return MockReplyProvider()
    if provider_name == "ollama":
        if model is None or not model.strip():
            raise ValueError("--model is required when --provider ollama is used")
        return OllamaReplyProvider(model=model, base_url=ollama_url)
    raise ValueError(f"Unknown reply provider: {provider_name}")


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
            reply_provider = build_reply_provider(
                provider_name=args.provider,
                model=args.model,
                ollama_url=args.ollama_url,
            )
            initiative_policy = (
                None
                if args.idle_initiative_seconds is None
                else IdleInitiativePolicy(args.idle_initiative_seconds)
            )
        except (CharacterLoadError, ValueError) as exc:
            parser.error(str(exc))
        run_chat(
            character_profile=character,
            reply_provider=reply_provider,
            show_metrics=args.show_metrics,
            initiative_policy=initiative_policy,
        )
