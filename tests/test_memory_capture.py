from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from atosaac_virtual_partner.memory import (
    MemoryRecord,
    MemorySource,
    MemoryStoreError,
    MemoryWriteAction,
    MemoryWriteResult,
)
from atosaac_virtual_partner.memory_capture import (
    HeuristicMemoryCapturePolicy,
    StoreBackedMemoryCapture,
)


@pytest.mark.parametrize(
    ("user_text", "expected_content", "expected_key"),
    (
        ("我叫小明", "用户希望被称为小明。", "profile:name"),
        ("我在金店工作", "用户在金店工作。", "profile:workplace"),
        ("我的爱好是摄影", "用户的爱好是摄影。", "profile:hobby"),
    ),
)
def test_capture_policy_extracts_stable_profile_facts(
    user_text: str,
    expected_content: str,
    expected_key: str,
) -> None:
    candidates = HeuristicMemoryCapturePolicy().candidates(user_text)

    assert len(candidates) == 1
    assert candidates[0].content == expected_content
    assert candidates[0].memory_key == expected_key
    assert candidates[0].source is MemorySource.AUTOMATIC


def test_capture_policy_uses_same_key_for_changed_preference() -> None:
    policy = HeuristicMemoryCapturePolicy()

    liked = policy.candidates("我喜欢蓝色")[0]
    disliked = policy.candidates("我不喜欢蓝色")[0]

    assert liked.content == "用户喜欢蓝色。"
    assert disliked.content == "用户不喜欢蓝色。"
    assert liked.memory_key == disliked.memory_key


def test_capture_policy_marks_direct_remember_request_as_explicit() -> None:
    candidate = HeuristicMemoryCapturePolicy().candidates(
        "记住，我喜欢爵士乐"
    )[0]

    assert candidate.content == "用户喜欢爵士乐。"
    assert candidate.source is MemorySource.EXPLICIT


@pytest.mark.parametrize(
    "user_text",
    (
        "我今天喜欢蓝色",
        "我可能喜欢蓝色",
        "我喜欢蓝色吗？",
        "我的银行卡号是123",
        "我在努力工作",
        "普通聊天",
    ),
)
def test_capture_policy_skips_transient_uncertain_sensitive_or_weak_text(
    user_text: str,
) -> None:
    assert HeuristicMemoryCapturePolicy().candidates(user_text) == ()


def test_capture_policy_limits_candidates_per_turn() -> None:
    candidates = HeuristicMemoryCapturePolicy().candidates(
        "我叫小明，我在金店工作，我喜欢蓝色"
    )

    assert len(candidates) == 2


@dataclass
class RecordingMemoryStore:
    actions: list[MemoryWriteAction]
    fail: bool = False

    def __post_init__(self) -> None:
        self.writes: list[tuple[str, str, MemorySource]] = []

    def remember(self, content, memory_key, source=MemorySource.AUTOMATIC):
        self.writes.append((content, memory_key, source))
        if self.fail:
            raise MemoryStoreError("storage failed")
        action = self.actions.pop(0)
        now = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
        return MemoryWriteResult(
            record=MemoryRecord(
                id=1,
                content=content,
                created_at=now,
                updated_at=now,
                source=source,
                memory_key=memory_key,
            ),
            action=action,
        )


def test_store_backed_capture_reports_content_free_write_counts() -> None:
    store = RecordingMemoryStore(
        [MemoryWriteAction.CREATED, MemoryWriteAction.UPDATED]
    )
    capture = StoreBackedMemoryCapture(store)  # type: ignore[arg-type]

    result = capture.capture("我叫小明，我在金店工作")

    assert result.created == 1
    assert result.updated == 1
    assert result.unchanged == 0
    assert result.failed is False
    assert len(store.writes) == 2


def test_store_backed_capture_isolates_storage_failure() -> None:
    store = RecordingMemoryStore([], fail=True)
    capture = StoreBackedMemoryCapture(store)  # type: ignore[arg-type]

    result = capture.capture("我喜欢蓝色")

    assert result.failed is True
    assert result.created == 0
