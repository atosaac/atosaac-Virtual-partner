import pytest

import atosaac_virtual_partner
from atosaac_virtual_partner import cli
from atosaac_virtual_partner.character import CharacterProfile
from atosaac_virtual_partner.providers import OllamaReplyProvider
from atosaac_virtual_partner.reply import MockReplyProvider, ReplyProvider


def test_health_command_prints_report(capsys) -> None:
    cli.main(["health"])

    assert "Status: ready" in capsys.readouterr().out


def test_chat_command_starts_chat(monkeypatch) -> None:
    started: list[tuple[CharacterProfile, ReplyProvider, bool]] = []
    monkeypatch.setattr(
        cli,
        "run_chat",
        lambda character_profile, reply_provider, show_metrics: started.append(
            (character_profile, reply_provider, show_metrics)
        ),
    )

    cli.main(["chat"])

    character, reply_provider, show_metrics = started[0]
    assert character.name == "atosaac"
    assert character.version == "0.27"
    assert isinstance(reply_provider, MockReplyProvider)
    assert show_metrics is False


def test_chat_command_loads_external_character(monkeypatch, tmp_path) -> None:
    character_file = tmp_path / "nova.md"
    character_file.write_text("# Nova v1.2\n\nBe curious.", encoding="utf-8")
    started: list[tuple[CharacterProfile, ReplyProvider, bool]] = []
    monkeypatch.setattr(
        cli,
        "run_chat",
        lambda character_profile, reply_provider, show_metrics: started.append(
            (character_profile, reply_provider, show_metrics)
        ),
    )

    cli.main(["chat", "--character-file", str(character_file)])

    character, _reply_provider, show_metrics = started[0]
    assert character.name == "Nova"
    assert character.version == "1.2"
    assert show_metrics is False


def test_chat_command_builds_ollama_provider(monkeypatch) -> None:
    started: list[tuple[CharacterProfile, ReplyProvider, bool]] = []
    monkeypatch.setattr(
        cli,
        "run_chat",
        lambda character_profile, reply_provider, show_metrics: started.append(
            (character_profile, reply_provider, show_metrics)
        ),
    )

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
        ]
    )

    _character, reply_provider, show_metrics = started[0]
    assert isinstance(reply_provider, OllamaReplyProvider)
    assert reply_provider.model == "qwen3:4b-instruct"
    assert reply_provider.chat_url == "http://127.0.0.1:11434/api/chat"
    assert show_metrics is True


def test_chat_command_requires_model_for_ollama(capsys) -> None:
    with pytest.raises(SystemExit):
        cli.main(["chat", "--provider", "ollama"])

    assert "--model is required" in capsys.readouterr().err


def test_package_entry_point_delegates_to_cli(monkeypatch) -> None:
    started: list[bool] = []
    monkeypatch.setattr(cli, "main", lambda: started.append(True))

    atosaac_virtual_partner.main()

    assert started == [True]
