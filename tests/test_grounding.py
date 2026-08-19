import pytest

from atosaac_virtual_partner.grounding import RuntimeGrounding


def test_default_grounding_reports_actual_missing_capabilities() -> None:
    instructions = RuntimeGrounding().system_instructions()

    assert "未连接持久记忆" in instructions
    assert "当前没有可用工具或实时数据" in instructions
    assert "禁止声称看过天气" in instructions
    assert "默认只用“你”" in instructions
    assert "不得声称自己在现实中吃过、见过或听说某事" in instructions
    assert "不得用“又”“上次”等词预设" in instructions
    assert "当前没有身体或现实活动状态" in instructions
    assert "不得声称自己刚睡醒" in instructions
    assert "可以自由使用未来假设、童话联想和比喻" in instructions
    assert "不能把想象写成看见用户房间" in instructions
    assert "不得改用“那次”“当时”或“后来”" in instructions
    assert "如果真发生过" in instructions


def test_grounding_names_only_explicitly_enabled_capabilities() -> None:
    grounding = RuntimeGrounding(
        persistent_memory_available=True,
        enabled_tools=("weather", "calendar"),
        parental_title="爸爸",
    )

    instructions = grounding.system_instructions()

    assert "已连接持久记忆" in instructions
    assert "可用工具只有：weather、calendar" in instructions
    assert "收到真实工具结果后" in instructions
    assert "用户已确认接受称呼“爸爸”" in instructions


@pytest.mark.parametrize(
    "enabled_tools",
    (("",), ("weather", "weather")),
)
def test_grounding_rejects_invalid_tool_names(
    enabled_tools: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="tool names"):
        RuntimeGrounding(enabled_tools=enabled_tools)


def test_grounding_rejects_empty_parental_title() -> None:
    with pytest.raises(ValueError, match="Parental title"):
        RuntimeGrounding(parental_title="  ")
