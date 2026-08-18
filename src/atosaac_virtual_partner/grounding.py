from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeGrounding:
    """Facts about capabilities and preferences available in this runtime."""

    persistent_memory_available: bool = False
    enabled_tools: tuple[str, ...] = ()
    parental_title: str | None = None

    def __post_init__(self) -> None:
        normalized_tools: list[str] = []
        for tool in self.enabled_tools:
            if not isinstance(tool, str) or not tool.strip():
                raise ValueError("Enabled tool names must be non-empty strings")
            normalized_tool = tool.strip()
            if normalized_tool in normalized_tools:
                raise ValueError("Enabled tool names must be unique")
            normalized_tools.append(normalized_tool)
        object.__setattr__(self, "enabled_tools", tuple(normalized_tools))

        if self.parental_title is None:
            return
        if not isinstance(self.parental_title, str) or not self.parental_title.strip():
            raise ValueError("Parental title must be a non-empty string")
        object.__setattr__(self, "parental_title", self.parental_title.strip())

    def system_instructions(self) -> str:
        """Render current application facts as a concise system message."""
        if self.persistent_memory_available:
            memory_rule = (
                "已连接持久记忆，但只有本次上下文明确提供的记忆记录才是事实；"
                "未提供的往事仍必须说不知道或不记得。"
            )
        else:
            memory_rule = (
                "未连接持久记忆。只能引用本次上下文已有消息，禁止编造“上次”、"
                "“以前”发生过的共同经历。"
            )

        if self.enabled_tools:
            tools = "、".join(self.enabled_tools)
            tool_rule = (
                f"应用声明的可用工具只有：{tools}。只有收到真实工具结果后才能说"
                "已经查询；不能把准备查询说成已经查到。"
            )
        else:
            tool_rule = (
                "当前没有可用工具或实时数据。禁止声称看过天气、网络、位置、日历"
                "或其他实时信息，也不要主动承诺可以查询。"
            )

        if self.parental_title is None:
            title_rule = (
                "未记录家长称呼偏好，默认只用“你”，不要擅自称呼“爸爸”或“妈妈”。"
            )
        else:
            title_rule = f"用户已确认接受称呼“{self.parental_title}”。"

        return "\n".join(
            (
                "# 当前运行事实",
                "以下内容由应用提供，优先于角色的猜测：",
                f"- 记忆：{memory_rule}",
                f"- 工具：{tool_rule}",
                f"- 称呼：{title_rule}",
            )
        )


DEFAULT_RUNTIME_GROUNDING = RuntimeGrounding()
