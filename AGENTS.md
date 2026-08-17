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

## Data and repository safety

- Never commit secrets, private conversations, raw recordings, local databases,
  model weights, or other large generated artifacts.
- Prefer configuration through environment variables and commit only safe
  examples with placeholder values.
- Treat local-first privacy and clear data ownership as architecture constraints.
