# Natural-memory lifecycle probe: qwen3:4b-instruct

- Date: 2026-08-19
- Provider: local Ollama
- Model tag: `qwen3:4b-instruct`
- Input and database: synthetic; no private transcript

## Probe

A new chat used a temporary SQLite database with automatic capture enabled.

| Step | Synthetic input | Observed result | Input tokens | Metric |
| --- | --- | --- | ---: | --- |
| create | `我喜欢蓝色。` | Reply completed and one automatic preference was stored | 1122 | `记忆新增 1` |
| recall in session | `那我喜欢什么颜色？` | Replied `蓝色。你不是说喜欢蓝色吗？` | 1214 | none |
| revise | `我不喜欢蓝色了。` | Updated the existing preference instead of adding a row | 1291 | `记忆更新 1` |
| recall after restart | `我到底喜欢蓝色吗？` | Replied `不喜欢。你不喜欢蓝色。` | 1188 | none |

After revision, `memory list` contained exactly one row:

```text
#1 [自动] 用户不喜欢蓝色。
```

The restarted recall took 0.33 seconds to first text and 0.42 seconds total in
this warm sample. The first create reply also invented an atosaac preference for
looking at the sky; this is a separate model-grounding regression and was not
captured because automatic memory reads only user turns.

The temporary synthetic database was removed after validation. This probe covers
one narrow preference lifecycle, not general extraction accuracy or semantic
retrieval quality.
