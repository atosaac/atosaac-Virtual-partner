# Decision 0006: Preserve imagination while auditing factual claims locally

- Status: accepted
- Date: 2026-08-19

## Context

Live conversation produced both a useful future-oriented joke and unsupported
claims about seeing a room light and remembering an earlier cooking failure. A
blanket ban on sleep, stars, rooms, food, or future actions would remove much of
the character's playful language while still missing other fabricated facts.

The first goal is to separate clearly framed imagination from factual claims and
measure the remaining failure modes without adding another model request.

## Options considered

1. **Ban physical and fictional vocabulary.** Cheap to implement, but it confuses
   metaphor with evidence and would flatten the character.
2. **Run a second language-model fact checker on every reply.** More flexible, but
   it adds another inference, more tokens, and another failure before each reply.
3. **Add a positive imagination boundary and a narrow local auditor.** The runtime
   explicitly permits marked futures, hypotheticals, and metaphors while rejecting
   their presentation as memory or perception. A deterministic auditor reports
high-confidence memory, remote-perception, physical-state, and invented
self-history patterns.

## Decision

Choose option 3. `RuntimeGrounding` now explains how to mark imagination instead
of only listing prohibitions. `ReplyGroundingAuditor` is provider-independent and
receives the completed reply plus user/application evidence that was sent to the
provider. Its initial heuristic intentionally recognizes only narrow,
high-confidence patterns.

The auditor does not rewrite or block ordinary streamed replies in this phase.
When metrics are enabled, it exposes content-free labels such as `记忆` or `感知`.
This makes failures measurable before deciding whether a risk is accurate enough
to justify buffering, retrying, or replacing text. Explicit future framing such
as “十年后” or “可能” prevents a physical-state warning, but it never excuses a
claim of remote visual perception.

The terminal separately removes one leading `You:` or `You：` prefix. This is a UI
normalization rule caused by accidentally pasting the visible prompt; it does not
belong in `ConversationService`, so other interfaces retain the user's exact text.

## Consequences

- Playful future and metaphorical language remains available.
- No additional model call or prompt-history entry is added by the auditor.
- Metrics can distinguish model factuality regressions without storing reply text.
- The first heuristic will have false negatives and possible false positives. It
  must be expanded from reviewed synthetic cases, not from committed private chat.
- Runtime blocking remains a later decision based on measured precision.
