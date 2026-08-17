# Character System

## Current files

- `docs/character/ATOSAAC_PERSONA_V0.25.md` is the complete human-authored design
  source. It includes examples and rejected behaviors for review and future
  evaluation; it is not automatically approved as training data.
- `src/atosaac_virtual_partner/characters/atosaac_v0.25.md` is the concise runtime
  profile passed to reply providers.
- `CharacterProfile` is an immutable value containing a name, version,
  instructions, and source.
- `ConversationService` combines the runtime profile, conversation history, and
  current user message before requesting a reply.

Keeping the full design source separate avoids spending context tokens on dozens
of examples during every reply. The runtime profile should contain stable identity
and rules; examples should become evaluation cases or carefully reviewed training
data later.

## External profiles

Load a Markdown profile for one chat session with:

```bash
uv run atosaac-virtual-partner chat \
  --character-file "/absolute/path/to/character.md"
```

A heading such as `# Nova v1.2` supplies the profile name and version. Without a
versioned heading, the filename becomes the name and the version is `external`.
External files are read-only and are not copied into the repository automatically.

Do not put API keys, private transcripts, or other secrets in a character file.
Once a real cloud model is connected, its active character instructions may be
sent to that provider as part of the request.

## Safe character growth

Character growth should not mean silently rewriting the baseline after every
conversation. Use three separate layers:

1. **Reviewed baseline**: stable identity, values, voice, and boundaries in a
   versioned Markdown file.
2. **Runtime state**: mood, interests, open topics, relationship state, and small
   goals. This changes frequently and can expire.
3. **Revision proposals**: durable changes suggested by the character or user,
   each with a reason, evidence, and proposed diff.

The intended revision flow is:

```text
conversation evidence
        ↓
revision proposal
        ↓
behavior tests and human review
        ↓
new profile version
        ↓
explicit activation or rollback
```

The model must never overwrite the active profile directly. A future workbench
should show proposals, comparisons, evaluation results, activation history, and a
rollback button.

## Current limitation

The default `MockReplyProvider` intentionally echoes the latest user message. It
receives the character context through `ConversationService`, but it does not use
the instructions. This keeps architecture tests deterministic. Observable
character behavior begins when a real or character-aware test provider is added.
