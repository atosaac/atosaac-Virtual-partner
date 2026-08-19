from collections.abc import Sequence

import pytest

from atosaac_virtual_partner.dialogue_policy import (
    DialogueIntent,
    HeuristicDialoguePolicy,
    ReplyConstraint,
)
from atosaac_virtual_partner.message import Message, MessageRole


@pytest.mark.parametrize(
    ("user_text", "expected_intent"),
    (
        ("早安……", DialogueIntent.GREETING),
        ("明天店里做节日活动，估计会很忙。", DialogueIntent.SHARING),
        ("刚吃完饭，心情不错。", DialogueIntent.SHARING),
        ("不用帮我，我只是吐槽一下。", DialogueIntent.SHARING),
        ("你这句怎么这么冷淡", DialogueIntent.RELATIONAL_FEEDBACK),
        ("这句也太像采访了吧", DialogueIntent.RELATIONAL_FEEDBACK),
        ("别这样嘛，ato", DialogueIntent.RELATIONAL_FEEDBACK),
        ("不要冤枉我", DialogueIntent.RELATIONAL_FEEDBACK),
        ("不是这个意思", DialogueIntent.RELATIONAL_FEEDBACK),
        ("这个安排合理吗？", DialogueIntent.DIRECT_QUESTION),
        ("你觉得这句话是什么意思", DialogueIntent.DIRECT_QUESTION),
        ("能不能换个说法", DialogueIntent.DIRECT_QUESTION),
        ("能帮我想个陈列方案吗？", DialogueIntent.HELP_REQUEST),
        ("我该怎么处理这件事？", DialogueIntent.HELP_REQUEST),
    ),
)
def test_dialogue_policy_classifies_synthetic_turns(
    user_text: str,
    expected_intent: DialogueIntent,
) -> None:
    policy = HeuristicDialoguePolicy()

    assert policy.classify(user_text) is expected_intent


def test_sharing_guidance_rejects_unrequested_problem_solving() -> None:
    guidance = HeuristicDialoguePolicy().guide(
        "节日促销估计会很忙。",
        (),
    )

    assert guidance.intent is DialogueIntent.SHARING
    assert "不是请求方案" in guidance.system_instructions
    assert "不要用泛问题维持对话" in guidance.system_instructions
    assert "不要擅自分析、给建议" in guidance.system_instructions
    assert "不安排自己或用户" in guidance.system_instructions
    assert "只输出一句" in guidance.system_instructions


def test_greeting_guidance_requires_warmth_without_an_interview() -> None:
    guidance = HeuristicDialoguePolicy().guide("晚上好～", ())

    assert guidance.intent is DialogueIntent.GREETING
    assert "只输出一句非疑问句" in guidance.system_instructions
    assert "俏皮或亲近感" in guidance.system_instructions
    assert "不编造自己刚醒" in guidance.system_instructions


def test_relational_feedback_prefers_humor_over_appeasement() -> None:
    guidance = HeuristicDialoguePolicy().guide("别乱猜嘛，ato。", ())

    assert guidance.intent is DialogueIntent.RELATIONAL_FEEDBACK
    assert "十到二十五个汉字" in guidance.system_instructions
    assert "承认具体偏差 + 轻巧撤回或自嘲" in guidance.system_instructions
    assert "贴切幽默" in guidance.system_instructions
    assert "不得否认用户的纠正" in guidance.system_instructions
    assert "机器人、AI、模型或脚本" in guidance.system_instructions
    assert "不重新问候" in guidance.system_instructions
    assert "不要猜测或反过来指控用户" in guidance.system_instructions
    assert "你别生气" in guidance.system_instructions
    assert "我闭嘴" in guidance.system_instructions
    assert "不要把它误认成用户姓名" in guidance.system_instructions
    assert guidance.reply_constraint is not None
    assert guidance.reply_constraint.fallback_text == (
        "刚才那条推理跑岔了，我撤回。"
    )
    assert guidance.reply_constraint.accepts(
        "ato，你说得对，我这就收着点。"
    ) is False
    assert guidance.reply_constraint.accepts("你眼光真准，我这就改改。") is False


def test_relational_feedback_rejects_denial_and_generic_reassurance() -> None:
    guidance = HeuristicDialoguePolicy().guide("不要冤枉我。", ())

    assert guidance.reply_constraint is not None
    assert guidance.reply_constraint.accepts("我不会，你别担心。") is False
    assert guidance.reply_constraint.accepts(
        "我没冤枉你，只是理解不同。"
    ) is False
    assert guidance.reply_constraint.fallback_text == (
        "刚才那顶帽子扣歪了，我收回。"
    )


def test_strict_reply_constraint_rejects_questions_and_appeasement() -> None:
    constraint = ReplyConstraint(
        fallback_text="合格回退。",
        max_characters=20,
        forbidden_phrases=("我闭嘴",),
    )

    assert constraint.accepts("这句确实跑偏了。") is True
    assert constraint.accepts("你今天怎么样？") is False
    assert constraint.accepts("好吧，我闭嘴。") is False
    assert constraint.accepts("这句话实在是长得超过了规定的最大字符数量。") is False


def test_greeting_guidance_has_a_tone_specific_fallback() -> None:
    guidance = HeuristicDialoguePolicy().guide("晚上好～", ())

    assert guidance.reply_constraint is not None
    assert guidance.reply_constraint.fallback_text == (
        "晚上好～你这个波浪号把气氛带亮了。"
    )


def test_policy_blocks_consecutive_questions_after_a_user_answer() -> None:
    history: Sequence[Message] = (
        Message(MessageRole.USER, "早安。"),
        Message(MessageRole.ASSISTANT, "早安。今天准备做什么？"),
    )

    guidance = HeuristicDialoguePolicy().guide(
        "上午要去店里。",
        history,
    )

    assert guidance.intent is DialogueIntent.SHARING
    assert "不得使用问句" in guidance.system_instructions


def test_policy_requires_two_nonquestion_replies_before_optional_curiosity() -> None:
    history: Sequence[Message] = (
        Message(MessageRole.USER, "早安。"),
        Message(MessageRole.ASSISTANT, "早安，今天看起来开场挺从容。"),
    )

    guidance = HeuristicDialoguePolicy().guide(
        "上午要去店里。",
        history,
    )

    assert "不得使用问句" in guidance.system_instructions


def test_policy_allows_one_specific_question_after_two_statement_replies() -> None:
    history: Sequence[Message] = (
        Message(MessageRole.USER, "早安。"),
        Message(MessageRole.ASSISTANT, "早安，今天看起来开场挺从容。"),
        Message(MessageRole.USER, "上午要去店里。"),
        Message(MessageRole.ASSISTANT, "那今天算是早早进入营业状态了。"),
    )

    guidance = HeuristicDialoguePolicy().guide(
        "店里正在做节日活动。",
        history,
    )

    assert "至少两轮没有提问" in guidance.system_instructions
    assert "一个短问题" in guidance.system_instructions


def test_dialogue_policy_rejects_empty_user_text() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        HeuristicDialoguePolicy().classify("   ")
