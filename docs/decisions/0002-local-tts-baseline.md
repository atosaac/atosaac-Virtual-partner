# Decision 0002: Establish a replaceable local TTS baseline

- Status: accepted as an experimental baseline
- Date: 2026-08-18

## Context

Both Virtual Partner and the separate desktop companion may need speech. The M4
Pro Mac has enough memory for local inference, but custom-voice training adds
model downloads, data preparation, licensing, latency, and failure modes before
the product has a tested audio boundary. Raw recordings and model weights also
must remain outside Git.

TTS（文本转语音）把角色回复合成为可播放的语音。

This decision records a TTS experiment, not a production voice architecture or
an approval to train a particular person's voice.

## Options considered

1. **Train a model from scratch now.** This requires a large curated corpus and
   substantially more compute than adapting an existing model. It does not help
   validate playback, cancellation, or provider replacement first.
2. **Start directly with a voice-cloning framework.** GPT-SoVITS and CosyVoice
   support custom voices, but bring large, fast-moving dependency stacks. Their
   training and inference environments should not be installed into the main app.
3. **Define a provider protocol and use macOS `say` as the baseline.** It has no
   model download, works offline, and can either play immediately or generate an
   audio file. Its system voices are not the final character voice.

## Decision

Choose option 3. `SpeechSynthesizer` is the application boundary and
`MacOSSaySynthesizer` is the first provider. The CLI exposes a small `speak`
command. Text is sent through standard input rather than embedded in a shell
command, and optional audio output is limited to formats supported by `say`.

Custom inference will be added as a second provider, preferably through a local
OpenAI-compatible speech endpoint so model dependencies stay in an isolated
service. Training or fine-tuning begins only after the recording owner, dataset
license, consent, held-out evaluation clips, and deletion policy are recorded.

## Consequences

- The complete text-to-audio path is testable today without a model download.
- System voices provide a safe fallback when a custom service is unavailable.
- A custom model can replace the provider without changing conversation logic.
- The baseline does not clone a character voice and does not yet speak each chat
  reply automatically; interruption and streaming audio remain separate work.
