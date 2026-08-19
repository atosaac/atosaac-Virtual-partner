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

The project currently exposes three terminal commands:

```text
atosaac-virtual-partner health
atosaac-virtual-partner chat
atosaac-virtual-partner speak
```

- `health` reports local environment information.
- `chat` uses `ConversationService` to combine a versioned character profile,
  in-memory message history, and a small reply-provider protocol.
- The built-in atosaac v0.27 profile is a concise runtime revision of the reviewed
  v0.26 design. An external Markdown profile can be selected for a chat session.
- Character personality is separated from `RuntimeGrounding`, which tells every
  profile the memory, tool, and parental-title facts actually available now.
- A replaceable `DialoguePolicy` gives each user turn a short reply mode. The
  initial local heuristic distinguishes greetings, sharing, relational feedback,
  questions, and help requests without another model call. It discourages
  consecutive interview-like questions and handles light corrections without
  invented excuses or appeasement. Guidance is not persisted as conversation
  history.
- Strict greetings and relational repairs buffer their short model draft for
  structural validation. Invalid questions, defensive patterns, or appeasement are
  replaced by a reviewed local line without a second inference call. Metrics mark
  the fallback explicitly; other turn types continue to stream normally.
- Runtime grounding positively distinguishes marked imagination from factual
  memory or perception. A local `ReplyGroundingAuditor` adds content-free risk
  labels for memory, perception, physical state, and invented self-history to
  opt-in metrics without another model call or automatic rewriting.
- The terminal strips one accidentally pasted leading `You:` prompt prefix before
  exit-command and conversation handling; non-terminal interfaces are unchanged.
- The deterministic local mock provider validates the flow but does not yet
  exhibit the supplied character behavior.
- An optional Ollama reply provider sends character instructions and a bounded
  recent conversation window to a configurable local Chat API. It consumes NDJSON
  reply fragments and exposes them to the CLI as they arrive.
- Complete committed history remains in memory for the session, while a replaceable
  `ContextWindowPolicy` sends the latest eight complete turns by default. No
  summary or older memory is fabricated when earlier turns leave the prompt.
- The terminal can opt into one idle-triggered initiative with a configured
  timeout. The application records a distinct event plus the completed assistant
  reply, then waits for real user activity before it may trigger again.
- Reply generation has an explicit cancellation token. In a macOS terminal, the
  CLI maps `Control+C` (not `Command+C`) during generation to cancellation and
  returns to the next prompt.
- A user/assistant turn is committed to in-memory history only after the provider
  reports normal completion; partial, cancelled, and failed replies are discarded.
- Each completed reply can expose in-memory first-text latency, end-to-end latency,
  input/output token counts, and generation speed. Metrics are opt-in at the CLI
  and contain no prompt, reply, or character text.
- No persistent memory store, realtime-data tool gateway, audio pipeline, avatar,
  or cloud service is connected yet.
- An **experimental TTS baseline** now exposes a `speak` CLI command through a
  replaceable `SpeechSynthesizer` protocol and macOS `say`. It only validates the
  text-to-audio boundary: it does not train or clone a voice, does not speak chat
  replies automatically, and is not the final audio architecture. See
  `docs/TTS_EXPERIMENT.md` before extending it.
- This repository owns only generic TTS foundations. Angelina-specific voice
  configuration, integration, reference manifests, and future trained artifacts
  belong to `angelina-macos-companion`; large or private files stay in that
  project's ignored local storage rather than Git.

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
7. **Tool gateway** validates model-requested capabilities such as weather before
   dispatching them to small, replaceable adapters.

### Independent design and measurable optimization

External projects are references for understanding solved problems, failure modes,
and useful interfaces; they are not default implementation templates. For each
substantial component, first state the product constraint and likely bottleneck,
then compare viable designs and implement the smallest independently reasoned
solution that can be tested.

Optimization should target evidence such as lower first-response latency, fewer
unnecessary model calls, better throughput, lower memory use, stronger privacy, or
clearer failure recovery. Capture a baseline before performance work and compare
the result afterward. A different implementation is valuable when it produces a
measurable benefit or a cleaner boundary, not merely because it is novel.

When external code is reused, record its source and license, keep attribution, and
adapt it behind a replaceable interface. Experiments should retain a known-good
fallback and must not weaken tests, privacy controls, or data ownership.

Realtime data must not mean giving the model unrestricted network access. The
intended flow is:

```text
model proposes a structured tool request
                  |
          capability registry
                  |
       permission and parameter checks
                  |
       weather / future data adapter
                  |
   result with source and observation time
                  |
        model writes the final reply
```

The model may decide that a weather lookup would help, but the application owns
execution. Read-only tools may be pre-approved individually; actions that contact
people, publish data, spend money, or change external state still require explicit
confirmation. Location should default to a user-configured city rather than silent
GPS access, and realtime results should carry a source timestamp so stale data is
not presented as current.

ASR（自动语音识别）把用户说话的音频转换成文本。TTS（文本转语音）把角色回复
合成为可播放的语音。RAG（检索增强生成）先从记忆或资料中检索相关内容，再把它们
提供给模型生成回复。

工具调用（tool calling）是模型提出结构化查询或操作请求，由应用校验权限并执行，
再把结果交还模型组织回答；它和让模型直接、无限制地访问网络不是一回事。

## Incremental roadmap

### Phase 1: text foundation

- Stabilize the CLI conversation loop and exit/error behavior.
- Measure the recent-turn context budget in longer chats before adding triggered
  summaries; retain full-history fallback for comparison.
- Add session persistence only after retention and deletion behavior is defined.

### Phase 2: tools, memory, and character

- Introduce typed tool requests/results, a capability registry, permission checks,
  timeouts, and user-visible error handling before enabling realtime data.
- Use a read-only weather adapter as the first realtime tool. Support a configured
  city, source/observation timestamps, caching, and graceful offline behavior.
- Allow the character to propose an enabled lookup when context makes it useful,
  while keeping tool execution and permissions under application control.
- Add session history, then an explicit long-term-memory store.
- Add retrieval, retention, deletion, and user-visible privacy controls.
- Convert reviewed positive and rejected character examples into behavioral tests.
- Add a provider-independent evaluation runner for the structured v0.27 synthetic
  regression cases before treating prompt changes or training as improvements.
- Measure unnecessary-question and unrequested-advice rates on fixed model/version
  settings before replacing the local turn policy with a learned classifier.
- Add runtime character state and human-reviewed revision proposals without
  allowing the model to overwrite its baseline.
- Evolve opt-in idle initiative into a user-controlled scheduler with quiet hours,
  topic selection, notification permissions, and TTS playback after text behavior
  is evaluated.

### Phase 3: voice

- Keep the existing macOS `say` path explicitly experimental and available as a
  fallback while comparing custom local inference providers.
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
- Treat tokenizer name/version and token counts as dataset metadata. Token budgets
  still determine context length, batching, memory use, training time, and
  generation speed even when the model is trained and hosted by this project.
- Start with reviewed SFT or LoRA experiments on an open base model rather than
  pretraining a foundation model from scratch. Keep the original base checkpoint,
  adapter version, dataset version, and evaluation results reproducible.
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
