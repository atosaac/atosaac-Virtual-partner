import atosaac_virtual_partner
from atosaac_virtual_partner import cli
from atosaac_virtual_partner.character import CharacterProfile


def test_health_command_prints_report(capsys) -> None:
    cli.main(["health"])

    assert "Status: ready" in capsys.readouterr().out


def test_chat_command_starts_chat(monkeypatch) -> None:
    started: list[CharacterProfile] = []
    monkeypatch.setattr(
        cli,
        "run_chat",
        lambda character_profile: started.append(character_profile),
    )

    cli.main(["chat"])

    assert started[0].name == "atosaac"
    assert started[0].version == "0.25"


def test_chat_command_loads_external_character(monkeypatch, tmp_path) -> None:
    character_file = tmp_path / "nova.md"
    character_file.write_text("# Nova v1.2\n\nBe curious.", encoding="utf-8")
    started: list[CharacterProfile] = []
    monkeypatch.setattr(
        cli,
        "run_chat",
        lambda character_profile: started.append(character_profile),
    )

    cli.main(["chat", "--character-file", str(character_file)])

    assert started[0].name == "Nova"
    assert started[0].version == "1.2"


def test_package_entry_point_delegates_to_cli(monkeypatch) -> None:
    started: list[bool] = []
    monkeypatch.setattr(cli, "main", lambda: started.append(True))

    atosaac_virtual_partner.main()

    assert started == [True]
