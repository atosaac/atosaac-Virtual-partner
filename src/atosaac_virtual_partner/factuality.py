import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from .message import Message, MessageRole


class GroundingRisk(StrEnum):
    """Describe one locally detectable unsupported factual claim."""

    UNSUPPORTED_MEMORY = "unsupported_memory"
    UNSUPPORTED_PERCEPTION = "unsupported_perception"
    UNSUPPORTED_PHYSICAL_STATE = "unsupported_physical_state"
    UNSUPPORTED_SELF_HISTORY = "unsupported_self_history"


@dataclass(frozen=True, slots=True)
class GroundingAudit:
    """Contain content-free risk labels for one completed reply."""

    risks: tuple[GroundingRisk, ...] = ()


class ReplyGroundingAuditor(Protocol):
    """Audit a completed reply without coupling it to one model provider."""

    def audit(
        self,
        reply_text: str,
        evidence: Sequence[Message],
    ) -> GroundingAudit:
        """Return locally detected grounding risks."""
        ...


_UNSUPPORTED_MEMORY_PATTERN = re.compile(
    r"(?:你(?:上次|上回).{0,20}(?:说|做|煮|去|吃)|"
    r"我.{0,8}(?:记得|记着).{0,20}"
    r"(?:你(?:上次|上回)|那次|以前你)|"
    r"到现在还.{0,12}(?:记着|存着.{0,4}记忆)|还存着记忆)"
)
_UNSUPPORTED_PERCEPTION_PATTERN = re.compile(
    r"(?:我.{0,8}(?:看见|看到|偷看|瞄见|望见).{0,16}"
    r"(?:你(?:的)?(?:房间|灯|屏幕|桌面|身后)|你身后)|"
    r"(?:你(?:的)?(?:房间|灯|屏幕|桌面)|你身后).{0,16}"
    r"(?:亮|开着|显示|放着|有人))"
)
_UNSUPPORTED_PHYSICAL_STATE_PATTERN = re.compile(
    r"(?:我(?:刚|才)?(?:睡醒|醒来|睁眼|打哈欠|吃过|喝过|煮过)|"
    r"我.{0,16}(?:打了?个?哈欠|钻进被窝|躺在床|睡着了)|"
    r"我(?:正|正在).{0,16}(?:数|偷看|看着|准备|吃|喝|煮|睡|躺))"
)
_UNSUPPORTED_SELF_HISTORY_PATTERN = re.compile(
    r"(?:我(?:上次|以前|曾经|小时候|第一次).{0,20}"
    r"(?:写|做|去|吃|喝|煮|学|玩)|"
    r"(?:后来|以前)我.{0,16}(?:学会|做过|去过|吃过|见过))"
)
_REPLY_IMAGINATION_PATTERN = re.compile(
    r"(?:十年后|未来(?:的)?|假如|假装|如果有一天|要是|说不定|可能|也许|想象中)"
)
_USER_IMAGINATION_PATTERN = re.compile(
    r"(?:十年后|未来(?:的)?|假如|假装|如果有一天|要是|想象中)"
)
_PRIOR_EVENT_PATTERN = re.compile(r"(?:上次|上回|以前|之前|曾经|那次)")
_QUESTION_PATTERN = re.compile(
    r"(?:吗(?:[，。！？?!\s]|$)|是不是|有没有|记得吗|[?？])"
)
_NEGATED_PERCEPTION_PATTERN = re.compile(
    r"(?:不能|无法|没法|看不见|不会).{0,6}(?:看见|看到|偷看|瞄见|望见)|"
    r"(?:没|不).{0,2}(?:亮|开着|显示|放着|有人)"
)
_EVIDENCE_NOISE_PHRASES = (
    "到现在",
    "上次",
    "上回",
    "以前",
    "之前",
    "曾经",
    "那次",
    "记得",
    "记着",
)
_EVIDENCE_NOISE_CHARACTERS = frozenset("我你他她它是了的把被还会就都又在有过那这")


def _content_characters(text: str) -> set[str]:
    normalized_text = text
    for phrase in _EVIDENCE_NOISE_PHRASES:
        normalized_text = normalized_text.replace(phrase, "")
    return {
        character
        for character in re.findall(r"[\u4e00-\u9fff]", normalized_text)
        if character not in _EVIDENCE_NOISE_CHARACTERS
    }


def _user_grounded_a_prior_event(
    reply_text: str,
    evidence: Sequence[Message],
) -> bool:
    reply_characters = _content_characters(reply_text)
    for message in evidence:
        if message.role is not MessageRole.USER:
            continue
        if _PRIOR_EVENT_PATTERN.search(message.content) and not _QUESTION_PATTERN.search(
            message.content
        ):
            evidence_characters = _content_characters(message.content)
            if len(reply_characters & evidence_characters) >= 2:
                return True
    return False


def _contains_positive_remote_perception(reply_text: str) -> bool:
    for match in _UNSUPPORTED_PERCEPTION_PATTERN.finditer(reply_text):
        if not _NEGATED_PERCEPTION_PATTERN.search(match.group(0)):
            return True
    return False


def _contains_unframed_claim(
    pattern: re.Pattern[str],
    reply_text: str,
    latest_user_text: str,
) -> bool:
    if _USER_IMAGINATION_PATTERN.search(latest_user_text):
        return False
    for match in pattern.finditer(reply_text):
        framing_prefix = reply_text[max(0, match.start() - 16) : match.start()]
        if not _REPLY_IMAGINATION_PATTERN.search(framing_prefix):
            return True
    return False


class HeuristicReplyGroundingAuditor:
    """Flag narrow factual risks while preserving explicit imagination."""

    def audit(
        self,
        reply_text: str,
        evidence: Sequence[Message],
    ) -> GroundingAudit:
        normalized_reply = reply_text.strip()
        if not normalized_reply:
            raise ValueError("Reply text cannot be empty")

        latest_user_text = ""
        for message in reversed(evidence):
            if message.role is MessageRole.USER:
                latest_user_text = message.content
                break

        risks: list[GroundingRisk] = []
        if (
            _UNSUPPORTED_MEMORY_PATTERN.search(normalized_reply)
            and not _user_grounded_a_prior_event(normalized_reply, evidence)
        ):
            risks.append(GroundingRisk.UNSUPPORTED_MEMORY)
        if _contains_positive_remote_perception(normalized_reply):
            risks.append(GroundingRisk.UNSUPPORTED_PERCEPTION)

        if _contains_unframed_claim(
            _UNSUPPORTED_PHYSICAL_STATE_PATTERN,
            normalized_reply,
            latest_user_text,
        ):
            risks.append(GroundingRisk.UNSUPPORTED_PHYSICAL_STATE)
        if _contains_unframed_claim(
            _UNSUPPORTED_SELF_HISTORY_PATTERN,
            normalized_reply,
            latest_user_text,
        ):
            risks.append(GroundingRisk.UNSUPPORTED_SELF_HISTORY)

        return GroundingAudit(tuple(risks))


DEFAULT_REPLY_GROUNDING_AUDITOR = HeuristicReplyGroundingAuditor()
