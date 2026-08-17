import pytest

from atosaac_virtual_partner.character import (
    CharacterLoadError,
    load_character_file,
    load_default_character,
)


def test_load_default_character_uses_reviewed_profile() -> None:
    character = load_default_character()

    assert character.name == "atosaac"
    assert character.version == "0.25"
    assert "honesty over flattery" in character.instructions
    assert character.source.startswith("builtin:")


def test_load_external_character_reads_name_and_version(tmp_path) -> None:
    character_file = tmp_path / "nova.md"
    character_file.write_text("# Nova v1.2\n\nBe curious.", encoding="utf-8")

    character = load_character_file(character_file)

    assert character.name == "Nova"
    assert character.version == "1.2"
    assert character.instructions.endswith("Be curious.")
    assert character.source == str(character_file)


def test_load_external_character_rejects_empty_file(tmp_path) -> None:
    character_file = tmp_path / "empty.md"
    character_file.write_text("  \n", encoding="utf-8")

    with pytest.raises(CharacterLoadError, match="empty"):
        load_character_file(character_file)
