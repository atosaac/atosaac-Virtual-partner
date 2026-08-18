import pytest

from atosaac_virtual_partner.character import (
    CharacterLoadError,
    load_character_file,
    load_default_character,
)


def test_load_default_character_uses_reviewed_profile() -> None:
    character = load_default_character()

    assert character.name == "atosaac"
    assert character.version == "0.27"
    assert "用户的女儿和长期虚拟伙伴" in character.instructions
    assert "名字始终写作小写 `atosaac`" in character.instructions
    assert "默认使用“你/我”" in character.instructions
    assert "普通闲聊默认用一到三句话" in character.instructions
    assert "不要无故按字面展开童话" in character.instructions
    assert "不得编造共同经历" in character.instructions
    assert "不得声称能查天气" in character.instructions
    assert "用户唯一的支持来源" in character.instructions
    assert "younger-sister" not in character.instructions
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
