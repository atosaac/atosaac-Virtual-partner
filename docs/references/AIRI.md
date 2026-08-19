# AIRI research notes

- Reviewed: 2026-08-19
- Source: <https://github.com/moeru-ai/airi>
- License: MIT, as published in
  <https://github.com/moeru-ai/airi/blob/main/LICENSE>
- Code reused in this repository: none

## Useful design signals

- Keep long-running character surfaces, model providers, audio, tools, and
  extensions behind explicit boundaries instead of treating them as one chat
  feature.
- Prefer opt-in, scheduled or manually triggered observations with bounded retry
  behavior. AIRI's screen-awareness proposal is useful research for the future
  low-power desktop observer: <https://github.com/moeru-ai/airi/issues/2060>.
- Give tools such as weather and memory explicit lifecycle and permission
  boundaries. AIRI's public roadmap provides comparison material:
  <https://github.com/moeru-ai/airi/issues/840>.
- Treat imported character content and future rendered chat content as untrusted.
  AIRI has published a character-card/chat-UI security advisory:
  <https://github.com/moeru-ai/airi/security/advisories/GHSA-9832-f8jx-hw6f>.

## Deliberate differences

This project will not copy AIRI's TypeScript monorepo or adopt continuous screen
capture as its foundation. The current Python runtime stays small and local-first.
Future observations should be normalized events with source time, permission, and
expiry metadata; the language model should run only after a relevant event rather
than continuously in the background.

These notes record architecture research and provenance. Any later code reuse
requires a separate license and attribution review.
