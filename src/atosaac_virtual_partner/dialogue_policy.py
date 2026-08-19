import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .message import Message, MessageRole


class DialogueIntent(StrEnum):
    """Describe the conversational job of the current user turn."""

    GREETING = "greeting"
    SHARING = "sharing"
    RELATIONAL_FEEDBACK = "relational_feedback"
    DIRECT_QUESTION = "direct_question"
    HELP_REQUEST = "help_request"


@dataclass(frozen=True, slots=True)
class ReplyConstraint:
    """Validate a short generated reply before it becomes user-visible."""

    fallback_text: str
    max_characters: int
    forbidden_phrases: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.fallback_text.strip():
            raise ValueError("Reply fallback cannot be empty")
        if self.max_characters <= 0:
            raise ValueError("Reply character limit must be greater than zero")
        if any(not phrase for phrase in self.forbidden_phrases):
            raise ValueError("Forbidden reply phrases cannot be empty")

    def accepts(self, reply_text: str) -> bool:
        normalized_text = reply_text.strip()
        if not normalized_text or len(normalized_text) > self.max_characters:
            return False
        if _DIRECT_QUESTION_PATTERN.search(normalized_text):
            return False
        casefolded_text = normalized_text.casefold()
        return not any(
            phrase.casefold() in casefolded_text
            for phrase in self.forbidden_phrases
        )


@dataclass(frozen=True, slots=True)
class DialogueGuidance:
    """Carry provider-independent, per-turn reply guidance."""

    intent: DialogueIntent
    system_instructions: str
    reply_constraint: ReplyConstraint | None = None

    def __post_init__(self) -> None:
        if not self.system_instructions.strip():
            raise ValueError("Dialogue guidance cannot be empty")


class DialoguePolicy(Protocol):
    """Choose a reply mode without coupling conversation flow to one model."""

    def guide(
        self,
        user_text: str,
        history: Sequence[Message],
    ) -> DialogueGuidance | None:
        """Return short instructions for responding to one user turn."""
        ...


_GREETING_PATTERN = re.compile(
    r"^(?:早上好|早安|上午好|中午好|下午好|晚上好|晚安|你好|嗨|哈喽|hello|hi)"
    r"[\s，,。.!！?？…~～]*$",
    re.IGNORECASE,
)
_HELP_REQUEST_PATTERN = re.compile(
    r"(?:帮我|请帮|麻烦你(?:帮|看|查|解释|分析|写|改|找)|告诉我|"
    r"给我(?:一些|一点|点|个)?(?:建议|方案|办法|主意)|"
    r"给我(?:写|列|做|查|找|解释|分析)|"
    r"我(?:该|应该)(?:怎么|如何)|(?:怎么|如何)(?:做|办|处理|解决|安排|选择|开始))"
)
_NO_HELP_PATTERN = re.compile(
    r"(?:不用|不需要|别)(?:帮我|给我建议|给建议|出主意)|"
    r"只是(?:说说|分享|吐槽)|没(?:让|叫)你(?:帮忙|给建议|出主意)"
)
_RELATIONAL_FEEDBACK_PATTERN = re.compile(
    r"(?:怎么这么(?:冷淡|敷衍|生硬|官方|客气|像(?:采访|客服|机器人))|"
    r"(?:这句|回复|语气).{0,8}(?:太|好)(?:冷|像(?:采访|客服|机器人))|"
    r"(?:别|不要)(?:这样|乱猜|瞎猜|诬陷|冤枉|误会)|"
    r"你(?:误会|说错|搞错|理解错)了|"
    r"不是(?:这个|那个|这|那)意思|"
    r"(?:太|好)(?:冷淡|敷衍|生硬)(?:了|吧)?)"
)
_DIRECT_QUESTION_PATTERN = re.compile(
    r"[?？]|(?:吗|么|嘛)[\s，,。.!！…~～]*$|"
    r"(?:为什么|为何|谁|哪里|哪儿|哪个|哪些|哪种|多少|是否|是不是|"
    r"有没有|要不要|能不能|可不可以|你觉得|你认为|你怎么看)|"
    r"(?:什么|几时|何时|怎么样)"
    r"[\s，,。.!！…~～]*$"
)

_INTENT_RULES = {
    DialogueIntent.GREETING: (
        "用户这轮只是在日常问候，不是请求帮助。硬性格式：只输出一句非疑问句，"
        "随后立即停止，不得出现问号或询问“今天怎么样”“有什么计划”。这一句要接住"
        "用户的轻松语气，带一点贴切的俏皮或亲近感，不能只像按钮回显；也不编造自己"
        "刚醒、正在做事等现实状态。"
    ),
    DialogueIntent.SHARING: (
        "用户这轮主要是在分享或陈述，不是请求方案。先回应其中的具体内容；不要"
        "擅自分析、给建议或索取细节，也不要用泛问题维持对话；只表达对用户所说"
        "具体内容的反应，不安排自己或用户接下来要做什么。"
    ),
    DialogueIntent.RELATIONAL_FEEDBACK: (
        "用户正在指出你的语气、误解或轻微越界。硬性格式：只输出约十到二十五个"
        "汉字的一句非疑问句，随后立即停止。内容只保留“承认具体偏差 + 轻巧撤回或"
        "自嘲”；不得否认用户的纠正，不用“但是、不过、其实、故意”等词辩解。轻松"
        "语境可用贴切幽默，但不把自己叫作机器人、AI、模型或脚本。不要猜测或反过来"
        "指控用户，不编造身体状态，不重新问候，也不说“你别生气”“我闭嘴”或连续"
        "道歉。用户放在句尾的称呼通常是在叫你，不要把它误认成用户姓名。"
    ),
    DialogueIntent.DIRECT_QUESTION: (
        "用户这轮提出了直接问题。先给明确回答，不要用反问代替回答；只有确实缺少"
        "关键事实时才问一个简短的澄清问题。"
    ),
    DialogueIntent.HELP_REQUEST: (
        "用户这轮明确请求帮助。直接处理请求；只有缺少关键事实时才问一个澄清问题，"
        "不要把交流变成连续的信息采集。"
    ),
}
MIN_NONQUESTION_REPLIES_BEFORE_ASKING = 2


def _greeting_fallback(user_text: str) -> str:
    normalized_text = user_text.casefold()
    if "晚上好" in normalized_text:
        return "晚上好～你这个波浪号把气氛带亮了。"
    if any(greeting in normalized_text for greeting in ("早上好", "早安")):
        return "早安～这个开场总算有点温度了。"
    if any(greeting in normalized_text for greeting in ("中午好", "下午好")):
        return "你好～这一声招呼来得正轻快。"
    if "晚安" in normalized_text:
        return "晚安～这句收尾听起来软乎乎的。"
    return "你好～这次的开场挺轻快。"


def _relational_feedback_fallback(user_text: str) -> str:
    if re.search(r"(?:冷淡|敷衍|生硬|官方|客气|采访|客服|机器人)", user_text):
        return "刚才那句确实像客服话术，我把工牌摘了。"
    if re.search(r"(?:乱猜|瞎猜)", user_text):
        return "刚才那条推理跑岔了，我撤回。"
    if re.search(r"(?:诬陷|冤枉)", user_text):
        return "刚才那顶帽子扣歪了，我收回。"
    if "误会" in user_text:
        return "刚才是我把意思听反了，我收回。"
    return "刚才那句确实跑偏了，我把方向调回来。"


def _trailing_latin_address(user_text: str) -> str | None:
    match = re.search(
        r"[,，]\s*([A-Za-z][A-Za-z0-9_-]{1,20})\s*[。.!！?？~～]*$",
        user_text,
    )
    if match is None:
        return None
    return match.group(1)


def _assistant_replies_since_question(history: Sequence[Message]) -> int:
    reply_count = 0
    for message in reversed(history):
        if message.role is MessageRole.ASSISTANT:
            if _DIRECT_QUESTION_PATTERN.search(message.content):
                return reply_count
            reply_count += 1
    return reply_count


class HeuristicDialoguePolicy:
    """Select a conservative reply mode with no extra model request."""

    def classify(self, user_text: str) -> DialogueIntent:
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("User text cannot be empty")
        if _GREETING_PATTERN.fullmatch(normalized_text):
            return DialogueIntent.GREETING
        if _RELATIONAL_FEEDBACK_PATTERN.search(normalized_text):
            return DialogueIntent.RELATIONAL_FEEDBACK
        if _NO_HELP_PATTERN.search(normalized_text):
            return DialogueIntent.SHARING
        if _HELP_REQUEST_PATTERN.search(normalized_text):
            return DialogueIntent.HELP_REQUEST
        if _DIRECT_QUESTION_PATTERN.search(normalized_text):
            return DialogueIntent.DIRECT_QUESTION
        return DialogueIntent.SHARING

    def guide(
        self,
        user_text: str,
        history: Sequence[Message],
    ) -> DialogueGuidance:
        intent = self.classify(user_text)
        instructions = ["# 本轮硬性回应约束", f"- {_INTENT_RULES[intent]}"]
        reply_constraint: ReplyConstraint | None = None
        if intent is DialogueIntent.GREETING:
            reply_constraint = ReplyConstraint(
                fallback_text=_greeting_fallback(user_text),
                max_characters=40,
                forbidden_phrases=("我刚醒", "我刚睡醒", "我正在"),
            )
        elif intent is DialogueIntent.RELATIONAL_FEEDBACK:
            forbidden_phrases = [
                "机器人",
                "AI",
                "模型",
                "脚本",
                "你生气",
                "你别生气",
                "我闭嘴",
                "改天",
                "其实",
                "故意",
                "但是",
                "不过",
                "你眼光真准",
                "你说得太对",
                "我这就改",
                "我会改",
                "我改改",
                "我不会",
                "别担心",
                "我没冤枉",
                "我没有冤枉",
                "我没误会",
                "我没有误会",
            ]
            trailing_address = _trailing_latin_address(user_text)
            if trailing_address is not None:
                forbidden_phrases.extend(
                    (f"{trailing_address}，", f"{trailing_address},")
                )
            reply_constraint = ReplyConstraint(
                fallback_text=_relational_feedback_fallback(user_text),
                max_characters=32,
                forbidden_phrases=tuple(forbidden_phrases),
            )
        if intent is DialogueIntent.SHARING:
            replies_since_question = _assistant_replies_since_question(history)
            if replies_since_question < MIN_NONQUESTION_REPLIES_BEFORE_ASKING:
                instructions.append(
                    "- 本轮只输出一句简短陈述、感受或贴切玩笑，句号后立即停止。不得"
                    "使用问句、提醒或祈使句。"
                )
            else:
                instructions.append(
                    "- 最近已有至少两轮没有提问。如果当前内容确实引发具体好奇，可以在"
                    "回应后问一个短问题；否则仍用陈述自然收尾。"
                )
        return DialogueGuidance(
            intent=intent,
            system_instructions="\n".join(instructions),
            reply_constraint=reply_constraint,
        )


class PassthroughDialoguePolicy:
    """Provide an explicit fallback that adds no per-turn instructions."""

    def guide(
        self,
        user_text: str,
        history: Sequence[Message],
    ) -> None:
        del user_text, history
        return None


DEFAULT_DIALOGUE_POLICY = HeuristicDialoguePolicy()
