import hashlib
import re
from dataclasses import dataclass
from typing import Protocol

from .memory import (
    MemorySource,
    MemoryStore,
    MemoryStoreError,
    MemoryWriteAction,
)


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    """Represent one high-confidence fact proposed for durable storage."""

    content: str
    memory_key: str
    source: MemorySource = MemorySource.AUTOMATIC


@dataclass(frozen=True, slots=True)
class MemoryCaptureResult:
    """Report content-free automatic-memory outcomes for one turn."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: bool = False


class MemoryCapturePolicy(Protocol):
    """Extract safe durable candidates from one completed user turn."""

    def candidates(self, user_text: str) -> tuple[MemoryCandidate, ...]: ...


class MemoryCapture(Protocol):
    """Persist automatic-memory candidates without exposing storage details."""

    def capture(self, user_text: str) -> MemoryCaptureResult: ...


_EXPLICIT_PREFIX_PATTERN = re.compile(
    r"^(?:请)?(?:你)?(?:记住|记一下|记得)(?:一下)?[：:，,\s]*"
)
_CLAUSE_SPLIT_PATTERN = re.compile(r"[。！？!?\n，,；;]+")
_QUESTION_OR_UNCERTAINTY_PATTERN = re.compile(
    r"(?:吗|么|是不是|有没有|可能|也许|大概|好像|似乎|猜|开玩笑|假如|如果)"
)
_TRANSIENT_PATTERN = re.compile(
    r"(?:今天|今晚|现在|刚才|刚刚|明天|昨天|这周|本周|最近|暂时|目前)"
)
_SENSITIVE_PATTERN = re.compile(
    r"(?:密码|验证码|身份证|银行卡|信用卡|手机号|电话号码|住址|详细地址|门牌|"
    r"邮箱|email|病历|诊断|药物|工资|收入|欠款|债务|账户|密钥|api\s*key|token)",
    re.IGNORECASE,
)
_NAME_PATTERN = re.compile(r"^我叫(.{1,30})$")
_WORKPLACE_PATTERN = re.compile(r"^我在(.{1,40})(?:工作|上班)$")
_HOBBY_PATTERN = re.compile(r"^我的爱好是(.{1,60})$")
_LIKE_PATTERN = re.compile(r"^我(?:平时|一直)?(?:很|特别|最)?(?:喜欢|爱|偏爱)(.{1,60})$")
_DISLIKE_PATTERN = re.compile(r"^我(?:一直)?(?:很|特别)?(?:不喜欢|讨厌)(.{1,60})$")
_INVALID_WORKPLACE = frozenset({"努力", "认真", "这里", "那里", "家里", "家"})
_TRAILING_PARTICLES = "呀啊呢吧哦啦了"
_MAX_CANDIDATES_PER_TURN = 2


def _stable_key(category: str, value: str | None = None) -> str:
    if value is None:
        return f"profile:{category}"
    normalized_value = "".join(value.casefold().split())
    digest = hashlib.sha256(normalized_value.encode("utf-8")).hexdigest()[:16]
    return f"profile:{category}:{digest}"


def _clean_value(value: str) -> str:
    return value.strip().rstrip(_TRAILING_PARTICLES).strip()


class HeuristicMemoryCapturePolicy:
    """Capture only narrow, stable self-disclosures without another model call."""

    def candidates(self, user_text: str) -> tuple[MemoryCandidate, ...]:
        normalized_text = user_text.strip()
        if not normalized_text:
            raise ValueError("Memory capture text cannot be empty")

        source = MemorySource.AUTOMATIC
        explicit_match = _EXPLICIT_PREFIX_PATTERN.match(normalized_text)
        if explicit_match is not None:
            normalized_text = normalized_text[explicit_match.end() :].strip()
            source = MemorySource.EXPLICIT

        candidates: list[MemoryCandidate] = []
        for raw_clause in _CLAUSE_SPLIT_PATTERN.split(normalized_text):
            clause = raw_clause.strip()
            if not clause:
                continue
            if _SENSITIVE_PATTERN.search(clause):
                continue
            if _QUESTION_OR_UNCERTAINTY_PATTERN.search(clause):
                continue
            if source is MemorySource.AUTOMATIC and _TRANSIENT_PATTERN.search(clause):
                continue

            candidate = self._candidate_for_clause(clause, source)
            if candidate is None:
                continue
            candidates.append(candidate)
            if len(candidates) >= _MAX_CANDIDATES_PER_TURN:
                break
        return tuple(candidates)

    @staticmethod
    def _candidate_for_clause(
        clause: str,
        source: MemorySource,
    ) -> MemoryCandidate | None:
        name_match = _NAME_PATTERN.fullmatch(clause)
        if name_match is not None:
            name = _clean_value(name_match.group(1))
            if name:
                return MemoryCandidate(
                    content=f"用户希望被称为{name}。",
                    memory_key=_stable_key("name"),
                    source=source,
                )

        workplace_match = _WORKPLACE_PATTERN.fullmatch(clause)
        if workplace_match is not None:
            workplace = _clean_value(workplace_match.group(1))
            if workplace and workplace not in _INVALID_WORKPLACE:
                return MemoryCandidate(
                    content=f"用户在{workplace}工作。",
                    memory_key=_stable_key("workplace"),
                    source=source,
                )

        hobby_match = _HOBBY_PATTERN.fullmatch(clause)
        if hobby_match is not None:
            hobby = _clean_value(hobby_match.group(1))
            if hobby:
                return MemoryCandidate(
                    content=f"用户的爱好是{hobby}。",
                    memory_key=_stable_key("hobby"),
                    source=source,
                )

        for pattern, verb in (
            (_LIKE_PATTERN, "喜欢"),
            (_DISLIKE_PATTERN, "不喜欢"),
        ):
            preference_match = pattern.fullmatch(clause)
            if preference_match is None:
                continue
            subject = _clean_value(preference_match.group(1))
            if not subject:
                return None
            return MemoryCandidate(
                content=f"用户{verb}{subject}。",
                memory_key=_stable_key("preference", subject),
                source=source,
            )
        return None


@dataclass(frozen=True, slots=True)
class StoreBackedMemoryCapture:
    """Persist candidates while isolating optional-memory failures."""

    memory_store: MemoryStore
    policy: MemoryCapturePolicy = HeuristicMemoryCapturePolicy()

    def capture(self, user_text: str) -> MemoryCaptureResult:
        created = 0
        updated = 0
        unchanged = 0
        try:
            for candidate in self.policy.candidates(user_text):
                result = self.memory_store.remember(
                    candidate.content,
                    candidate.memory_key,
                    source=candidate.source,
                )
                if result.action is MemoryWriteAction.CREATED:
                    created += 1
                elif result.action is MemoryWriteAction.UPDATED:
                    updated += 1
                else:
                    unchanged += 1
        except MemoryStoreError:
            return MemoryCaptureResult(
                created=created,
                updated=updated,
                unchanged=unchanged,
                failed=True,
            )
        return MemoryCaptureResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
        )


DEFAULT_MEMORY_CAPTURE_POLICY = HeuristicMemoryCapturePolicy()
