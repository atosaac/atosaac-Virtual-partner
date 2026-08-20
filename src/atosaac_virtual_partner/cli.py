import argparse
from collections.abc import Sequence
from pathlib import Path

from .character import CharacterLoadError, load_character
from .chat import run_chat
from .dialogue_policy import (
    DialoguePolicy,
    HeuristicDialoguePolicy,
    PassthroughDialoguePolicy,
)
from .grounding import DEFAULT_RUNTIME_GROUNDING, RuntimeGrounding
from .health import build_health_report
from .initiative import IdleInitiativePolicy
from .memory import (
    DEFAULT_MEMORY_DATABASE_PATH,
    DuplicateMemoryError,
    MemorySource,
    MemoryStore,
    MemoryStoreError,
    SQLiteMemoryStore,
)
from .memory_capture import MemoryCapture, StoreBackedMemoryCapture
from .memory_context import BoundedLexicalMemoryContext, MemoryContextProvider
from .providers import DEFAULT_OLLAMA_URL, OllamaReplyProvider
from .reply import MockReplyProvider, ReplyProvider
from .tts import (
    DEFAULT_MACOS_VOICE,
    DEFAULT_SPEECH_RATE,
    MacOSSaySynthesizer,
    SpeechSynthesisError,
    SpeechSynthesizer,
)


PROVIDER_NAMES = ("mock", "ollama")
DIALOGUE_POLICY_NAMES = ("heuristic", "none")


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
        "--dialogue-policy",
        choices=DIALOGUE_POLICY_NAMES,
        default="heuristic",
        help=(
            "Per-turn dialogue guidance (default: heuristic; "
            "use none for a baseline comparison)."
        ),
    )
    chat_parser.add_argument(
        "--idle-initiative-seconds",
        type=float,
        help=(
            "Let the character speak once after this many idle seconds "
            "(disabled by default)."
        ),
    )
    chat_parser.add_argument(
        "--memory",
        action="store_true",
        help="Enable local long-term memory from the default database.",
    )
    chat_parser.add_argument(
        "--memory-database",
        type=Path,
        help="Enable local long-term memory from a custom SQLite database.",
    )
    chat_parser.add_argument(
        "--no-auto-memory",
        action="store_true",
        help="Read long-term memory without silently capturing stable facts.",
    )
    memory_parser = subcommands.add_parser(
        "memory",
        help="Manage local long-term memories.",
    )
    memory_parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_MEMORY_DATABASE_PATH,
        help=f"Local SQLite database (default: {DEFAULT_MEMORY_DATABASE_PATH}).",
    )
    memory_actions = memory_parser.add_subparsers(
        dest="memory_action",
        required=True,
    )
    memory_add_parser = memory_actions.add_parser(
        "add",
        help="Save one explicit memory.",
    )
    memory_add_parser.add_argument("content", help="Memory text to save.")
    memory_list_parser = memory_actions.add_parser(
        "list",
        help="List recent memories.",
    )
    memory_list_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of memories to show (default: 50).",
    )
    memory_forget_parser = memory_actions.add_parser(
        "forget",
        help="Delete one memory by id.",
    )
    memory_forget_parser.add_argument("memory_id", type=int)
    memory_clear_parser = memory_actions.add_parser(
        "clear",
        help="Delete every memory.",
    )
    memory_clear_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm deletion of every memory.",
    )
    speak_parser = subcommands.add_parser(
        "speak",
        help="Try the experimental local macOS TTS baseline.",
    )
    speak_parser.add_argument("text", help="Text to speak.")
    speak_parser.add_argument(
        "--voice",
        default=DEFAULT_MACOS_VOICE,
        help=f"Installed macOS voice name (default: {DEFAULT_MACOS_VOICE}).",
    )
    speak_parser.add_argument(
        "--rate",
        type=int,
        default=DEFAULT_SPEECH_RATE,
        help=f"Speech rate from 80 to 500 (default: {DEFAULT_SPEECH_RATE}).",
    )
    speak_parser.add_argument(
        "--output",
        type=Path,
        help="Save to .aiff/.aif/.aifc/.caf instead of playing immediately.",
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


def build_speech_synthesizer(voice: str, rate: int) -> SpeechSynthesizer:
    """Build the experimental TTS provider behind a replaceable protocol."""
    return MacOSSaySynthesizer(voice=voice, rate=rate)


def build_dialogue_policy(policy_name: str) -> DialoguePolicy:
    """Build replaceable per-turn guidance with an explicit fallback."""
    if policy_name == "heuristic":
        return HeuristicDialoguePolicy()
    if policy_name == "none":
        return PassthroughDialoguePolicy()
    raise ValueError(f"Unknown dialogue policy: {policy_name}")


def build_memory_store(database_path: Path) -> MemoryStore:
    """Build local memory storage behind a replaceable protocol."""
    return SQLiteMemoryStore(database_path)


def _run_memory_command(args: argparse.Namespace) -> None:
    store = build_memory_store(args.database)
    if args.memory_action == "add":
        record = store.add(args.content)
        print(f"已保存记忆 #{record.id}：{record.content}")
        return
    if args.memory_action == "list":
        records = store.list_recent(args.limit)
        if not records:
            print("还没有已保存的记忆。")
            return
        for record in records:
            source_label = (
                "明确" if record.source is MemorySource.EXPLICIT else "自动"
            )
            print(f"#{record.id} [{source_label}] {record.content}")
        return
    if args.memory_action == "forget":
        if store.delete(args.memory_id):
            print(f"已删除记忆 #{args.memory_id}。")
        else:
            print(f"没有找到记忆 #{args.memory_id}。")
        return
    if args.memory_action == "clear":
        if not args.yes:
            raise ValueError("memory clear requires --yes")
        deleted_count = store.clear()
        print(f"已清空 {deleted_count} 条记忆。")
        return
    raise ValueError(f"Unknown memory action: {args.memory_action}")


def main(argv: Sequence[str] | None = None) -> None:
    """Run the selected Virtual Partner command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        print(build_health_report())
        return

    if args.command == "memory":
        try:
            _run_memory_command(args)
        except DuplicateMemoryError as exc:
            parser.error(f"这条记忆已经保存为 #{exc.existing_id}")
        except (MemoryStoreError, ValueError) as exc:
            parser.error(str(exc))
        return

    if args.command == "speak":
        try:
            synthesizer = build_speech_synthesizer(args.voice, args.rate)
            output_path = synthesizer.synthesize(args.text, args.output)
        except SpeechSynthesisError as exc:
            parser.error(str(exc))
        if output_path is not None:
            print(f"语音已生成：{output_path}")
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
            dialogue_policy = build_dialogue_policy(args.dialogue_policy)
            memory_database = args.memory_database
            if memory_database is None and args.memory:
                memory_database = DEFAULT_MEMORY_DATABASE_PATH
            memory_context_provider: MemoryContextProvider | None = None
            memory_capture: MemoryCapture | None = None
            runtime_grounding: RuntimeGrounding = DEFAULT_RUNTIME_GROUNDING
            if memory_database is not None:
                memory_store = build_memory_store(memory_database)
                memory_context_provider = BoundedLexicalMemoryContext(memory_store)
                if not args.no_auto_memory:
                    memory_capture = StoreBackedMemoryCapture(memory_store)
                runtime_grounding = RuntimeGrounding(
                    persistent_memory_available=True
                )
            elif args.no_auto_memory:
                raise ValueError(
                    "--no-auto-memory requires --memory or --memory-database"
                )
        except (CharacterLoadError, MemoryStoreError, ValueError) as exc:
            parser.error(str(exc))
        run_chat(
            character_profile=character,
            reply_provider=reply_provider,
            show_metrics=args.show_metrics,
            initiative_policy=initiative_policy,
            dialogue_policy=dialogue_policy,
            runtime_grounding=runtime_grounding,
            memory_context_provider=memory_context_provider,
            memory_capture=memory_capture,
        )
