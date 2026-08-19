import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IdleInitiativePolicy:
    """Control when silence may produce one application-triggered reply."""

    idle_seconds: float
    max_without_user_activity: int = 1

    def __post_init__(self) -> None:
        if isinstance(self.idle_seconds, bool) or not isinstance(
            self.idle_seconds,
            (int, float),
        ):
            raise ValueError("Initiative idle_seconds must be a number")
        if not math.isfinite(self.idle_seconds) or self.idle_seconds <= 0:
            raise ValueError("Initiative idle_seconds must be greater than zero")
        if isinstance(self.max_without_user_activity, bool) or not isinstance(
            self.max_without_user_activity,
            int,
        ):
            raise ValueError("Initiative maximum must be an integer")
        if self.max_without_user_activity <= 0:
            raise ValueError("Initiative maximum must be greater than zero")

    def can_trigger(self, initiatives_since_user_activity: int) -> bool:
        return initiatives_since_user_activity < self.max_without_user_activity

    def event_instructions(self) -> str:
        return "\n".join(
            (
                "# 应用主动对话事件",
                "用户有一段时间没有输入。这是应用事件，不是用户说的话。",
                "结合已有对话，自然说一句简短的话，或问一个你确实好奇的具体问题。",
                "没有上下文时，从一个微小选择、偏好或具体观点切入。",
                "不要问“最近在忙什么”“想聊什么”“今天怎么样”这类泛泛的问题。",
                "不要责怪、催促或分析用户为什么沉默，不要提到计时器、超时或检测。",
                "不要编造你在现实中听说、见过、吃过或经历过的事情。",
            )
        )
