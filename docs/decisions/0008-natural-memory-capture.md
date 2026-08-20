# Decision 0008: Capture narrow stable memories without interrupting dialogue

- Status: accepted
- Date: 2026-08-19

## Context

Explicit CLI-managed memory proves persistence and retrieval, but asking for a
confirmation every time the user states a preference, name, hobby, or workplace
would make the companion feel like a form. Persisting full transcripts or asking
an LLM to extract memory on every turn would be more natural at the surface but
would increase privacy exposure, latency, token use, and false-memory risk.

The code review also found two reliability gaps: changed facts could accumulate
as contradictory rows, and an unavailable optional database could abort the main
conversation flow.

## Options considered

1. **Store every successful user turn.** Natural and complete, but effectively a
   private transcript archive with weak retention semantics.
2. **Run a second LLM memory extractor after every reply.** Flexible, but adds an
   inference and can silently turn interpretation mistakes into durable facts.
3. **Use narrow local capture with keyed updates.** Less coverage, but no extra
   model call, deterministic privacy exclusions, measurable behavior, and a safe
   path to a later intermittent semantic extractor.

## Decision

Choose option 3 when memory is enabled. `HeuristicMemoryCapturePolicy` recognizes
only narrow first-person forms for a preferred name, workplace, hobbies, and
positive or negative preferences. It skips question-like, uncertain, transient,
and sensitive patterns. A direct `记住` request marks the resulting record as
explicit; other matched facts are labeled automatic. At most two candidates are
processed after one normally completed user turn. Failed, cancelled, or
application-initiative turns do not become user memory.

Keyed `MemoryStore.remember` writes create, update, or leave a record unchanged.
Names, workplaces, and hobbies have stable profile keys; preference keys derive
from a short hash of the preference subject, so changing `喜欢` to `不喜欢` updates
the same row without exposing the subject in index metadata. Existing version-1
databases migrate in place and retain their records as explicit data.

Normal chat does not announce capture. Opt-in metrics expose only content-free
counts such as `记忆新增 1` or `记忆更新 1`, and `memory list` shows `[明确]` or
`[自动]`. `--no-auto-memory` disables capture while retaining retrieval.

Memory reads and writes are optional side effects. A read failure omits memory and
continues the provider request; a capture failure preserves the completed turn.
Metrics expose those fallbacks without recording chat text.

## Consequences

- Common stable facts can be remembered naturally across processes without
  storing complete conversations or making a second model request.
- Automatic extraction has false negatives by design and may still misunderstand
  unusual phrasing; records remain inspectable and deletable.
- Automatic facts can change in place, while explicit records retain higher
  retrieval priority.
- Sensitive life details and temporary events require future, more deliberate
  retention policies rather than a growing set of permissive patterns.
- Personality files are never rewritten by this mechanism.
