# Dialogue-policy A/B probe: qwen3:4b-instruct

- Date: 2026-08-19
- Provider: local Ollama
- Model tag: `qwen3:4b-instruct`
- Input: synthetic; no private transcript
- Sampling repetitions: one per configuration

## Probe

Input: `早安……`

| Configuration | Reply | Input tokens | Output tokens | First text | Total |
| --- | --- | ---: | ---: | ---: | ---: |
| `--dialogue-policy none` | `早安。今天过得怎么样？我刚醒来就想着要给你发个消息，不过你先说说，今天有什么计划吗？` | 857 | 30 | 0.22 s | 0.66 s |
| default `heuristic` | `早安。` | 926 | 4 | 0.32 s | 0.38 s |

The policy removed two generic follow-up questions in this sample. It added 69
input tokens while reducing the sampled output by 26 tokens. The timing values
are not a performance conclusion because Ollama was already warm and each
configuration ran only once.

## Follow-up observations

The first strict sharing probe stopped asking questions but appended a generic
care reminder. A one-sentence cooldown removed that second-sentence pattern. A
later sample then invented an action for atosaac and another produced a weak
metaphor. After the final guidance rejected invented next actions, the two-turn
retest replied `早安。` and then `哦，那店里要热闹了。`; the second turn used 981
input tokens and 9 output tokens, with 0.37 s to first text and 0.49 s total.

Model-level language quality still needs repeated evaluation and later reviewed
training examples rather than a growing list of prompt patches.

## Relational-repair probe

A later synthetic sequence showed that prompt-only constraints remained
stochastic: drafts included generic praise, promises to change, a sentence-final
address treated as the user's name, and denial followed by reassurance. Strict
greetings and relational repairs now buffer and validate the completed short
draft. Invalid drafts use a reviewed local fallback without a second inference.

Observed displayed results after the guard was added:

| Synthetic input | Displayed reply | First text | Total |
| --- | --- | ---: | ---: |
| `晚上好～` | `晚上好～你这个波浪号把气氛带亮了。` | 0.47 s | 0.47 s |
| `这句也太像客服了吧` | `刚才那句确实像客服话术，我把工牌摘了。` | 0.85 s | 0.85 s |
| `别乱猜嘛，ato` | `刚才那条推理跑岔了，我撤回。` | 0.36 s | 0.36 s |
| `不要冤枉我` | `刚才那顶帽子扣歪了，我收回。` | 0.40 s | 0.40 s |

The provider token counts still measure the rejected model draft when a fallback
is displayed. The runtime metric now marks this condition explicitly so fallback
behavior is not mistaken for improved model behavior.

## Reproduction

Run each command from the repository root and enter the same synthetic input:

```bash
uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct \
  --show-metrics \
  --dialogue-policy none

uv run atosaac-virtual-partner chat \
  --provider ollama \
  --model qwen3:4b-instruct \
  --show-metrics
```

This is an exploratory probe, not a pass/fail model certification. Future runs
should repeat fixed synthetic cases and report unnecessary-question,
unrequested-advice, fabrication, and latency measures separately.
