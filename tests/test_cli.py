from collections.abc import Callable
from pathlib import Path

import pytest

import atosaac_virtual_partner
from atosaac_virtual_partner import cli
from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.dialogue_policy import (
    DialoguePolicy,
    HeuristicDialoguePolicy,
    PassthroughDialoguePolicy,
)
from atosaac_virtual_partner.initiative import IdleInitiativePolicy
from atosaac_virtual_partner.grounding import RuntimeGrounding
from atosaac_virtual_partner.memory_context import (
    BoundedLexicalMemoryContext,
    MemoryContextProvider,
)
from atosaac_virtual_partner.memory_capture import (
    MemoryCapture,
    StoreBackedMemoryCapture,
)
from atosaac_virtual_partner.providers import OllamaReplyProvider
from atosaac_virtual_partner.reply import MockReplyProvider, ReplyProvider
from atosaac_virtual_partner.tts import SpeechSynthesizer
from atosaac_virtual_partner.tool_context import (
    ToolContextProvider,
    WeatherToolContextProvider,
)


ChatStart = tuple[
    CharacterProfile,
    ReplyProvider,
    bool,
    IdleInitiativePolicy | None,
    DialoguePolicy,
    RuntimeGrounding,
    MemoryContextProvider | None,
    MemoryCapture | None,
    ToolContextProvider | None,
]


def capture_chat_start(started: list[ChatStart]) -> Callable[..., None]:
    def capture(
        character_profile: CharacterProfile,
        reply_provider: ReplyProvider,
        show_metrics: bool,
        initiative_policy: IdleInitiativePolicy | None,
        dialogue_policy: DialoguePolicy,
        runtime_grounding: RuntimeGrounding,
        memory_context_provider: MemoryContextProvider | None,
        memory_capture: MemoryCapture | None,
        tool_context_provider: ToolContextProvider | None,
    ) -> None:
        started.append(
            (
                character_profile,
                reply_provider,
                show_metrics,
                initiative_policy,
                dialogue_policy,
                runtime_grounding,
                memory_context_provider,
                memory_capture,
                tool_context_provider,
            )
        )

    return capture


def test_health_command_prints_report(capsys) -> None:
    cli.main(["health"])

    assert "Status: ready" in capsys.readouterr().out


def test_speak_command_uses_local_tts_provider(monkeypatch, tmp_path, capsys) -> None:
    calls: list[tuple[str, Path | None]] = []
    output = tmp_path / "voice.aiff"

    class RecordingSynthesizer:
        def synthesize(self, text: str, output_path: Path | None = None):
            calls.append((text, output_path))
            return output_path

    def build(voice: str, rate: int) -> SpeechSynthesizer:
        assert voice == "Tingting"
        assert rate == 210
        return RecordingSynthesizer()

    monkeypatch.setattr(cli, "build_speech_synthesizer", build)

    cli.main(["speak", "你好", "--rate", "210", "--output", str(output)])

    assert calls == [("你好", output)]
    assert str(output) in capsys.readouterr().out


def test_chat_command_starts_chat(monkeypatch) -> None:
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))

    cli.main(["chat"])

    (
        character,
        reply_provider,
        show_metrics,
        initiative_policy,
        dialogue_policy,
        runtime_grounding,
        memory_context_provider,
        memory_capture,
        tool_context_provider,
    ) = started[0]
    assert character.name == "atosaac"
    assert character.version == "0.27"
    assert isinstance(reply_provider, MockReplyProvider)
    assert show_metrics is False
    assert initiative_policy is None
    assert isinstance(dialogue_policy, HeuristicDialoguePolicy)
    assert runtime_grounding.persistent_memory_available is False
    assert memory_context_provider is None
    assert memory_capture is None
    assert tool_context_provider is None


def test_chat_command_loads_external_character(monkeypatch, tmp_path) -> None:
    character_file = tmp_path / "nova.md"
    character_file.write_text("# Nova v1.2\n\nBe curious.", encoding="utf-8")
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))

    cli.main(["chat", "--character-file", str(character_file)])

    (
        character,
        _reply_provider,
        show_metrics,
        initiative_policy,
        dialogue_policy,
        _runtime_grounding,
        _memory_context_provider,
        _memory_capture,
        _tool_context_provider,
    ) = started[0]
    assert character.name == "Nova"
    assert character.version == "1.2"
    assert show_metrics is False
    assert initiative_policy is None
    assert isinstance(dialogue_policy, HeuristicDialoguePolicy)


def test_chat_command_builds_ollama_provider(monkeypatch) -> None:
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))

    cli.main(
        [
            "chat",
            "--provider",
            "ollama",
            "--model",
            "qwen3:4b-instruct",
            "--ollama-url",
            "http://127.0.0.1:11434/api",
            "--show-metrics",
            "--dialogue-policy",
            "none",
            "--idle-initiative-seconds",
            "30",
        ]
    )

    (
        _character,
        reply_provider,
        show_metrics,
        initiative_policy,
        dialogue_policy,
        _runtime_grounding,
        _memory_context_provider,
        _memory_capture,
        _tool_context_provider,
    ) = started[0]
    assert isinstance(reply_provider, OllamaReplyProvider)
    assert reply_provider.model == "qwen3:4b-instruct"
    assert reply_provider.chat_url == "http://127.0.0.1:11434/api/chat"
    assert show_metrics is True
    assert initiative_policy == IdleInitiativePolicy(idle_seconds=30)
    assert isinstance(dialogue_policy, PassthroughDialoguePolicy)


def test_chat_command_requires_model_for_ollama(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["chat", "--provider", "ollama"])

    assert "--model is required" in capsys.readouterr().err


def test_chat_command_rejects_nonpositive_idle_timeout(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["chat", "--idle-initiative-seconds", "0"])

    assert "idle_seconds must be greater than zero" in capsys.readouterr().err


def test_chat_command_enables_explicit_memory_database(monkeypatch, tmp_path) -> None:
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))
    database = tmp_path / "memory.sqlite3"

    cli.main(["chat", "--memory-database", str(database)])

    runtime_grounding = started[0][5]
    memory_context_provider = started[0][6]
    memory_capture = started[0][7]
    assert runtime_grounding.persistent_memory_available is True
    assert isinstance(memory_context_provider, BoundedLexicalMemoryContext)
    assert isinstance(memory_capture, StoreBackedMemoryCapture)


def test_chat_command_enables_weather_for_one_configured_city(monkeypatch) -> None:
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))

    cli.main(["chat", "--weather-city", "上海"])

    runtime_grounding = started[0][5]
    tool_context_provider = started[0][8]
    assert runtime_grounding.enabled_tools == ("weather.current",)
    assert isinstance(tool_context_provider, WeatherToolContextProvider)
    assert tool_context_provider.city == "上海"


def test_chat_command_rejects_invalid_weather_city(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["chat", "--weather-city", "上"])

    assert "Weather city" in capsys.readouterr().err


def test_chat_command_can_disable_automatic_memory(monkeypatch, tmp_path) -> None:
    started: list[ChatStart] = []
    monkeypatch.setattr(cli, "run_chat", capture_chat_start(started))

    cli.main(
        [
            "chat",
            "--memory-database",
            str(tmp_path / "memory.sqlite3"),
            "--no-auto-memory",
        ]
    )

    assert isinstance(started[0][6], BoundedLexicalMemoryContext)
    assert started[0][7] is None


def test_chat_command_rejects_auto_memory_switch_without_memory(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["chat", "--no-auto-memory"])

    assert "requires --memory" in capsys.readouterr().err


def test_memory_commands_add_list_forget_and_clear(tmp_path, capsys) -> None:
    database = tmp_path / "memory.sqlite3"
    base_args = ["memory", "--database", str(database)]

    cli.main([*base_args, "add", "我在金店工作。"])
    assert "已保存记忆 #1" in capsys.readouterr().out

    cli.main([*base_args, "list"])
    assert "#1 [明确] 我在金店工作。" in capsys.readouterr().out

    cli.main([*base_args, "forget", "1"])
    assert "已删除记忆 #1" in capsys.readouterr().out

    cli.main([*base_args, "add", "我喜欢蓝色。"])
    capsys.readouterr()
    cli.main([*base_args, "clear", "--yes"])
    assert "已清空 1 条记忆" in capsys.readouterr().out


def test_memory_clear_requires_explicit_confirmation(tmp_path, capsys) -> None:
    database = tmp_path / "memory.sqlite3"

    with pytest.raises(SystemExit):
        cli.main(["memory", "--database", str(database), "clear"])

    assert "memory clear requires --yes" in capsys.readouterr().err


def test_memory_command_reports_duplicate_record(tmp_path, capsys) -> None:
    database = tmp_path / "memory.sqlite3"
    args = ["memory", "--database", str(database), "add"]
    cli.main([*args, "Likes Python"])
    capsys.readouterr()

    with pytest.raises(SystemExit):
        cli.main([*args, " likes   python "])

    assert "已经保存为 #1" in capsys.readouterr().err


def test_package_entry_point_delegates_to_cli(monkeypatch) -> None:
    started: list[bool] = []
    monkeypatch.setattr(cli, "main", lambda: started.append(True))

    atosaac_virtual_partner.main()

    assert started == [True]
