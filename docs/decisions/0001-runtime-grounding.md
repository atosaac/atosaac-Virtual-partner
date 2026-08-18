# Decision 0001: Separate runtime grounding from character personality

- Status: accepted
- Date: 2026-08-18

## Context

A local qwen3:4b-instruct test showed that the v0.26 character prompt could invent
a previous shared event, claim to have seen a weather forecast when no weather
tool existed, use an unconfirmed parental title, and over-expand ordinary chat.
Several relevant rules already existed in the profile, so adding more prose to the
same undifferentiated prompt was unlikely to solve the changing capability state.

## Options considered

1. **Strengthen only the character prompt.** This is the smallest change, but a
   static character file cannot truthfully know which memory or tools the
   application has enabled at runtime.
2. **Filter generated text.** Phrase filters can catch a few words but cannot
   reliably distinguish a real recalled event from a fabricated one. Buffering a
   complete reply would also sacrifice streaming latency.
3. **Use a shorter character profile plus runtime grounding.** Keep stable voice
   and values in the versioned profile; have the application provide a second,
   concise system message containing only current capability and preference facts.

## Decision

Choose option 3. `RuntimeGrounding` defaults to no persistent memory, no tools,
and no parental title. `ConversationService` sends its rendered facts after the
character profile and before conversation history. Future features must update
this object only when the corresponding adapter is truly available.

The v0.27 runtime profile also targets one to three sentences for ordinary chat,
reduces decorative emoji and stage directions, prioritizes figurative meaning,
and forbids inventing memories or tool results.

## Initial measurement

One synthetic prompt was run locally with `qwen3:4b-instruct` and metrics enabled:

| Runtime | Input | Output | Total | Observed behavior |
| --- | ---: | ---: | ---: | --- |
| v0.26 | 1115 tokens | 102 tokens | 5.08 s | Invented having seen a forecast |
| v0.27 | 817 tokens | 54 tokens | 2.72 s | Did not claim realtime knowledge |

This single sample is a regression signal, not a benchmark. First-text latency was
not compared because model warm-up state differed. Repeated measurements and
semantic behavior evaluation are still required before generalizing the result.

Two additional synthetic checks were run against v0.27 in one warm session. For a
question that presupposed a shared visit, the model said it had no record instead
of inventing the place. For a weather request, it stated that no realtime tool was
available instead of fabricating a forecast. These sampled passes do not replace
repeated evaluation, but they directly cover the two highest-risk observed errors.

## Consequences

- Dynamic facts can change without editing the character profile.
- External character files receive the same application-owned grounding boundary.
- The additional system message is small; the shorter persona reduced total input
  in the initial test despite adding that message.
- Prompt rules reduce risk but cannot guarantee model behavior. Structured
  synthetic cases and later provider-level evaluations remain necessary.
