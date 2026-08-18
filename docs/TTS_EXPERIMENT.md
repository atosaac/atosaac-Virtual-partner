# TTS Experiment Handoff

## Status

This is an **experimental TTS attempt**, added on 2026-08-18. It is deliberately
small and replaceable. It is not the final Virtual Partner voice system.

TTS（文本转语音）把文字合成为可播放的语音。

## What exists

- `src/atosaac_virtual_partner/tts.py` defines the provider-independent
  `SpeechSynthesizer` protocol.
- `MacOSSaySynthesizer` uses the built-in macOS `/usr/bin/say` command as a
  zero-download fallback.
- `atosaac-virtual-partner speak` can play text immediately or generate an AIFF
  or CAF file.
- `tests/test_tts.py` covers command construction, standard-input handling,
  output validation, and failures.

## What does not exist

- No voice model is downloaded or trained.
- No real-person or fictional-character voice is cloned.
- Chat replies are not spoken automatically.
- Streaming playback, interruption, device selection, and audio queues are not
  implemented.
- The desktop-companion repository is not coupled to this experiment.

## Safe continuation boundary

Keep custom model dependencies and weights outside this repository. Add future
engines as new `SpeechSynthesizer` providers or as clients of an isolated local
speech service. Before training or fine-tuning, record the voice owner's consent,
dataset provenance and license, evaluation split, retention rule, and deletion
procedure. Raw recordings, reference clips, datasets, and model weights must not
be committed.

The next useful experiment is an OpenAI-compatible local speech client with the
macOS provider retained as a fallback. Automatic chat speech should only follow
after cancellation and playback-queue behavior are designed and tested.
