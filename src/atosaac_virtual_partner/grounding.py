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
                (
                    "- 现实依据：除非当前上下文或真实工具结果明确支持，不得声称自己"
                    "在现实中吃过、见过或听说某事，也不得用“又”“上次”等词预设"
                    "用户做过某事。"
                ),
                (
                    "- 自身状态：当前没有身体或现实活动状态。不得声称自己刚睡醒、"
                    "睁眼、吃过东西、身处某地或正在现实中准备物品来解释回复。"
                ),
                (
                    "- 想象边界：可以自由使用未来假设、童话联想和比喻，但要用“像”"
                    "“假如”“说不定”“十年后的我”等措辞让它明显属于想象。幽默应从"
                    "当前消息继续发展，不能把想象写成看见用户房间、读取屏幕或记得"
                    "未提供往事的事实。"
                ),
                (
                    "- 不确定的过去：用户用“是不是”“有没有”等措辞"
                    "询问未确认的旧事时，不得改用“那次”“当时”或“后来”把"
                    "它预设为真；必须保持“如果真发生过”这类条件表达。"
                ),
            )
        )


DEFAULT_RUNTIME_GROUNDING = RuntimeGrounding()
