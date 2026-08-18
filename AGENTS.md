# Repository Guide

This file applies to the entire repository. Read `docs/PROJECT_CONTEXT.md` before
making architectural or roadmap decisions.

## Development workflow

- Use Python 3.11, `uv` for environments and dependencies, and `pytest` for tests.
- Keep components small, testable, and replaceable; do not couple the CLI to a
  specific model, speech service, or UI implementation.
- Preserve existing uncommitted work. Inspect `git status` and relevant diffs
  before editing.
- Run focused tests while developing and the full test suite before handoff.
- Explain changes in Chinese as: what changed, why, and what the user can learn.
- When using terms such as ASR, TTS, or RAG, add a one-sentence Chinese
  explanation.
- Show the diff summary and test results before any commit, push, or merge, and
  wait for explicit user confirmation.

## Independent design and optimization

- Treat external repositories as research material, not as blueprints to copy.
  Before reusing code, review its license, provenance, constraints, and required
  attribution.
- For a meaningful new component or optimization, identify the bottleneck and
  compare at least two viable approaches when the tradeoff is not obvious.
- Prefer the simplest independently designed approach that improves a measurable
  target such as latency, throughput, memory use, privacy, reliability, or
  maintainability. Record the reasoning for architectural decisions.
- Validate optimizations with focused tests and, where performance is the goal,
  before/after measurements. Novelty alone is not evidence of improvement.
- Keep experimental paths replaceable and provide a safe fallback so a failed
  optimization does not destabilize the main conversation flow.

## Data and repository safety

- Never commit secrets, private conversations, raw recordings, local databases,
  model weights, or other large generated artifacts.
- Prefer configuration through environment variables and commit only safe
  examples with placeholder values.
- Treat local-first privacy and clear data ownership as architecture constraints.
