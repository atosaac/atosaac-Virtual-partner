# Decision 0003: Bound model context by recent complete turns

- Status: proposed
- Date: 2026-08-18

## Context

Each successful reply is currently appended to in-memory history and every later
request sends the complete history. A short local test grew from 806 to 889 input
tokens in three user turns. This is harmless at first, but an unbounded session
eventually increases prompt evaluation time and can exceed a model's context
limit.

This problem is separate from model loading. Ollama model residency affects the
first response after a cold period; history selection affects how much text is
evaluated on every response.

## Options considered

1. **Send full history.** It preserves everything but has unbounded token and
   latency growth.
2. **Cut at a character or estimated-token boundary.** It is tighter, but
   estimates vary between model tokenizers and may split a user/assistant turn.
3. **Keep a fixed number of recent complete turns.** It is deterministic,
   provider-independent, has no extra model call, and preserves local continuity,
   though older details disappear from the prompt.
4. **Summarize on every turn.** It can retain older information compactly, but
   adds latency and cost each time and may turn a mistaken summary into false
   memory.

## Decision

Start with option 3 and keep option 1 as an explicit fallback. The default policy
sends the eight most recent complete user turns. `ConversationService.history`
continues to hold the full committed in-memory session, so context selection does
not delete user data or change cancellation transaction rules.

`ContextWindowPolicy` is provider-independent and replaceable. The first concrete
policy finds user-message boundaries and never starts the selected history with an
orphaned assistant reply.

## Initial measurement

A ten-turn synthetic local run used `qwen3:4b-instruct` with four-token replies.
Input grew from 814 tokens on turn 1 to 998 tokens on turn 9, when eight previous
turns were present. Turn 10 also used 998 input tokens because the oldest complete
turn was removed as the newest one entered. This confirms bounded growth for
equal-sized turns; natural conversations will fluctuate with message length.

Most warm first-text measurements in that run were 0.17–0.22 seconds. Cold model
loading remained a separate first-turn cost and is not improved by history
selection.

## Next memory layer

Do not treat discarded prompt text as long-term memory. A later compactor may run
only when a measurable threshold is crossed, such as several newly omitted turns
or a topic boundary. Its summary must remain inspectable, carry source turn IDs,
and be replaceable or deletable. Stable user facts should enter long-term memory
only through a separate reviewed retention policy.

This is “intermittent” processing: recent messages remain verbatim, compaction is
triggered occasionally rather than on every reply, and relevant durable memories
are retrieved only when needed.

## Consequences

- Prompt growth becomes bounded by complete recent turns rather than session age.
- The default adds no extra inference request and no persistent storage.
- Very long individual turns can still be expensive; a future token-aware policy
  may improve this behind the same interface.
- After eight turns, older details are unavailable to the model until a reviewed
  summary or retrieval layer is implemented.
