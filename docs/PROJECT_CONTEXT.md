# Virtual Partner: Project Context

## Product vision

Build a personal AI companion inspired by Neuro-sama. The long-term product may
combine a consistent character, long-term memory, multimodal perception, speech,
an original character or Live2D avatar, and a desktop workbench.

The current goal is not model training. First establish a testable, replaceable
foundation so models and services can be changed without rewriting the product.

## Runtime and development constraints

- Primary device: macOS on an M4 Pro with 24 GB memory.
- Local responsibilities: interface, audio capture and playback, memory, privacy,
  orchestration, and control.
- Future cloud responsibilities: large-model training and inference that does not
  fit the local performance or memory budget.
- Language and tooling: Python 3.11, `uv`, and `pytest`.
- Development style: small increments with tests; show changes before committing,
  pushing, or merging.

## Current state

The project currently exposes two terminal commands:

```text
atosaac-virtual-partner health
atosaac-virtual-partner chat
```

- `health` reports local environment information.
- `chat` uses `ConversationService` to combine a versioned character profile,
  in-memory message history, and a small reply-provider protocol.
- The built-in profile is a concise runtime form of the reviewed atosaac v0.26
  design. An external Markdown profile can be selected for a chat session.
- The deterministic local mock provider validates the flow but does not yet
  exhibit the supplied character behavior.
- An optional Ollama reply provider sends the character instructions and complete
  in-memory conversation to a configurable local Chat API. It currently waits for
  a complete, non-streaming response.
- No persistent memory store, audio pipeline, avatar, or cloud service is connected
  yet.

## Architecture direction

Keep the user interface and orchestration independent from replaceable providers:

```text
CLI / future desktop workbench
             |
      conversation service
       /      |       \
LLM provider  memory   character policy
                 \
          future audio and avatar adapters
```

Recommended boundaries as features are introduced:

1. **Conversation service** owns turn handling and conversation flow.
2. **LLM provider interface** hides whether inference is mock, local, or cloud.
3. **Character policy** owns persona prompts and behavioral rules rather than
   scattering them through UI code.
4. **Memory interface** separates storage and retrieval from reply generation.
5. **Audio adapters** isolate ASR and TTS implementations.
6. **Avatar adapter** translates character state into expressions and motion.

ASR（自动语音识别）把用户说话的音频转换成文本。TTS（文本转语音）把角色回复
合成为可播放的语音。RAG（检索增强生成）先从记忆或资料中检索相关内容，再把它们
提供给模型生成回复。

## Incremental roadmap

### Phase 1: text foundation

- Stabilize the CLI conversation loop and exit/error behavior.
- Add explicit streaming and cancellation semantics to replies.
- Record provider latency and token metrics without storing private message
  content in logs.
- Add session persistence only after retention and deletion behavior is defined.

### Phase 2: memory and character

- Add session history, then an explicit long-term-memory store.
- Add retrieval, retention, deletion, and user-visible privacy controls.
- Convert reviewed positive and rejected character examples into behavioral tests.
- Add runtime character state and human-reviewed revision proposals without
  allowing the model to overwrite its baseline.

### Phase 3: voice

- Add replaceable ASR and TTS adapters.
- Build interruption, latency, device-selection, and audio-failure handling.
- Keep raw recordings local and out of Git by default.

### Phase 4: multimodal avatar and workbench

- Add image or screen inputs behind explicit permissions.
- Connect emotion and action state to an OC or Live2D avatar.
- Build a macOS workbench for configuration, logs, memory controls, and provider
  status.

### Phase 5: training and cloud scale

- Evaluate whether prompt design, retrieval, or fine-tuning best addresses measured
  shortcomings.
- Build reviewed typo-and-slip datasets: preferred replies should understand an
  obvious intended meaning and may tease briefly in light contexts; rejected
  replies should capture mechanical correction, excessive mockery, and unsafe
  guessing when the meaning matters.
- Split typo patterns between training and held-out evaluation rather than randomly
  splitting near-duplicate sentences. Measure unseen-error generalization together
  with memory fabrication, so copying a prompt example does not count as success.
- Use cloud GPU resources only after datasets, evaluations, privacy rules, and cost
  limits are defined.

## Data and security rules

Do not commit API keys, credentials, private chat transcripts, raw recordings,
local memory databases, model weights, or large generated assets. Store secrets in
environment variables or an operating-system credential store. Any future memory
feature must support inspecting and deleting stored user data.
