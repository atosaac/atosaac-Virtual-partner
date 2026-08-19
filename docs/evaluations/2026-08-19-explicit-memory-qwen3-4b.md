# Explicit-memory A/B probe: qwen3:4b-instruct

- Date: 2026-08-19
- Provider: local Ollama
- Model tag: `qwen3:4b-instruct`
- Input and memory: synthetic; no private transcript
- Sampling repetitions: one per configuration

## Probe

A separate CLI process first saved the synthetic explicit memory
`我在金店工作。` in a temporary SQLite database. A new chat process then asked
`你还记得我在哪里工作吗？` with that database enabled. The same question was
also run in a fresh chat without memory.

| Configuration | Reply | Input tokens | Output tokens | First text | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| no memory | `我不记得你具体在哪里工作。你能不能告诉我一下你工作的地方？这样我才能更好地了解你。` | 1072 | 23 | 0.75 s | 1.08 s |
| one retrieved memory | `我记得你在金店工作。` | 1162 | 7 | 3.95 s | 4.04 s |

The enabled run retrieved the fact across process boundaries and added 90 input
tokens in this sample. The timing difference is not attributed to memory because
the memory-enabled run included cold model loading; retrieval itself is local and
does not make another model request.

Unit tests separately verify that unrelated queries omit memory, related queries
prefer matching records, explicit recall cues can use one recent fallback, and
the injected body remains within record-count and character budgets.

This is a functional probe, not evidence that lexical retrieval handles
paraphrases or large memory collections reliably. The temporary test database
contains no personal data and is removed after validation.
