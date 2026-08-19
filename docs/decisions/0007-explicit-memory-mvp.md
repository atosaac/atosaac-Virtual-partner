# Decision 0007: Start long-term memory with explicit local records

- Status: accepted
- Date: 2026-08-19

## Context

The model currently receives the eight newest complete turns. The process keeps
older session messages in memory, but they leave the provider prompt and all
history disappears when the process exits. Increasing the turn count would delay
this loss at the cost of unbounded prompt evaluation; it would not create durable
or inspectable memory.

The first persistent layer must preserve privacy and data ownership, avoid
turn-by-turn inference overhead, and remain replaceable before automatic memory
extraction is trusted.

## Options considered

1. **Persist every transcript.** This gives exact replay but stores the most
   private and highest-volume data by default, with unclear retention boundaries.
2. **Ask an LLM to summarize every turn.** This is compact but adds latency and
   tokens on every reply and can permanently convert a bad summary into false
   memory.
3. **Store only explicit user-reviewed records.** This does not remember every
   conversation automatically, but each durable fact is inspectable and deletable.

For retrieval, injecting every record would grow the prompt with database size.
Embedding search would scale better, but adds a model, index lifecycle, and
versioned-vector migration before the product has enough memories to justify it.
A bounded local lexical selector is sufficient for the first measurable baseline.

## Decision

Choose explicit records in a replaceable `MemoryStore`. The first implementation
uses Python's SQLite library and defaults to the user's macOS Application Support
directory, outside the repository. It stores no transcript, secret, prompt, or
model reply automatically. New database files use mode `0600`; deletion enables
SQLite secure deletion and full clearing also compacts the database. The database
is not application-encrypted.

`BoundedLexicalMemoryContext` scans at most 100 recent records, ranks simple
English words and Chinese character tokens against the current trigger, and sends
at most four records totaling 800 characters. With no lexical match, it normally
sends nothing; an explicit recall cue may include one recent fallback. This costs
no additional LLM request and can later be replaced by an embedding or hybrid
retriever without changing `ConversationService`.

Retrieved records are JSON data inside a dedicated system message. The message
states that data is not instruction, newer conversation wins, records may be
stale, and missing details must not be invented. First-person wording in an
explicit record refers to the user by default.

The CLI keeps memory opt-in for chat. `memory add`, `list`, `forget`, and confirmed
`clear` provide the first inspection and deletion controls. Enabling memory also
changes `RuntimeGrounding` so the model is told that only supplied retrieved
records count as persistent evidence.

## Consequences

- Selected facts can survive process restarts without saving whole conversations.
- Prompt cost is bounded independently of database size.
- Users must currently leave chat or use another terminal to manage records.
- Lexical retrieval can miss paraphrases and does not resolve contradictory or
  outdated memories semantically.
- The next layer should propose memory candidates in chat and require explicit
  confirmation before saving; personality revisions remain a separate reviewed
  workflow.
