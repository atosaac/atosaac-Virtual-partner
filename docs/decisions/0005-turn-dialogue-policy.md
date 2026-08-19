# Decision 0005: Guide each user turn without another model request

- Status: accepted
- Date: 2026-08-19

## Context

The active character profile already says not to ask consecutive questions or use
customer-service endings. Live trials with a local 4B instruction model still
turned ordinary statements into requests for plans and details. The model was
using questions as a generic way to continue the conversation, which made the
character feel like an assistant conducting an interview.

The immediate target is behavioral: distinguish everyday sharing from explicit
help requests and reduce unnecessary follow-up questions. The policy must remain
provider-independent and must not add another inference request to every turn.

## Options considered

1. **Add more permanent persona rules.** This costs few implementation changes,
   but the existing rule has already proved too distant and general for the small
   local model to apply reliably to each turn.
2. **Ask a second language model to classify every user message.** This can handle
   subtle language better, but doubles request coordination, adds latency and
   token use, and introduces another failure before a reply can start.
3. **Classify a small set of conservative turn modes locally.** A deterministic,
   replaceable policy identifies greetings, ordinary sharing, direct questions,
   and explicit help requests. It adds one short system instruction for the
   current turn and makes no provider call.

## Decision

Choose option 3. `DialoguePolicy` is a replaceable protocol. The initial
`HeuristicDialoguePolicy` uses deliberately narrow rules and defaults uncertain
messages to sharing, because incorrectly offering a solution is the observed
failure we want to avoid.

The first live iteration made greetings too terse. It also showed that a complaint
about tone could trigger an invented physical excuse followed by excessive
appeasement. Relational feedback is therefore a separate narrow mode: acknowledge
the concrete miss, allow brief self-aware humor, and forbid fabricated bodily
states, counter-accusations, repeated apologies, and requests for forgiveness.

`ConversationService` places the guidance with the other system context but does
not save it in user-visible history. User text is never rewritten. Application
events keep their own initiative instructions and do not pass through this user
turn classifier.

Greetings never need an automatic question. Ordinary sharing uses statement-only
guidance until at least two completed assistant replies have contained no
question. The next sharing turn may ask one specific, grounded question, and an
actual question in the generated reply resets that allowance. This small question
budget preserves occasional curiosity without letting every user answer trigger
another interview prompt.

The policy does not post-process or delete punctuation from model output; editing
generated text would risk changing meaning and hiding model failures.

Prompt-only constraints remained stochastic in live trials: the same greeting
sometimes obeyed the no-question rule and sometimes appended an interview prompt.
Greetings and relational repairs are therefore buffered until their short model
draft completes. A structural constraint rejects questions, excessive length, and
known defensive or appeasing patterns. Invalid drafts are replaced by a small,
reviewed, intent-specific fallback without making a second model request. Other
turn modes keep normal fragment streaming.

This adds full-short-reply buffering latency to the two strict modes, but adds no
retry tokens and prevents invalid text from becoming visible before validation.
Provider token metrics still describe the generated draft, including when the
displayed text comes from the local fallback.

## Measurement and fallback

Synthetic, non-private tests cover each intent and the consecutive-question
boundary. Live comparison should use a fixed model and repeated prompts, then
record unnecessary-question and unrequested-advice rates separately from latency.
The pre-policy behavior remains available by injecting another `DialoguePolicy`,
so a future learned classifier can be evaluated without changing the CLI or model
provider.

The first local A/B probe is recorded in
`docs/evaluations/2026-08-19-dialogue-policy-qwen3-4b.md`. One synthetic greeting
changed from two generic follow-up questions to a single greeting, with a measured
69-input-token guidance cost. One sample is evidence for iteration, not proof of
general behavior.

The heuristic cannot fully understand irony, quoted questions, or indirect help
requests. Those misses should become synthetic evaluation cases before expanding
the rules; adding broad keyword matches would make the classifier look more
capable while increasing false positives.
