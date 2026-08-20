# Decision 0009: Keep realtime tools behind an application-owned gateway

- Status: accepted
- Date: 2026-08-20

## Context

Weather, calendar, and future desktop context require external data, but giving an
LLM unrestricted network access would make permissions, failure recovery, and
provider replacement difficult. Ollama and future cloud providers may also expose
different native function-calling formats.

Timeouts need a truthful boundary. Running arbitrary work in a Python thread and
returning on a timer does not stop that work; this is especially unsafe for future
tools that can change external state.

## Options considered

1. **Call adapters directly from the CLI or conversation service.** Small at first,
   but validation, permissions, and errors would become scattered.
2. **Use each LLM provider's native tool API as the product interface.** Convenient
   for one provider, but couples product capabilities to provider-specific schemas.
3. **Use a provider-independent application gateway.** The application validates a
   typed request, checks a capability registry and permission class, passes a
   bounded timeout to a small adapter, and normalizes its result.

## Decision

Choose option 3. `ToolRequest`, `ToolDescriptor`, `ToolRegistry`, `ToolGateway`, and
`ToolResult` form the provider-independent boundary. Arguments and output are
bounded JSON scalar mappings, tool names are normalized, duplicate registrations
are rejected, and no permission is enabled by default.

The initial gateway distinguishes read-only capabilities from external actions.
Adapters receive a timeout budget and must apply it to their underlying I/O. The
gateway maps invalid input, timeout, unavailability, permission, and unexpected
errors to stable Chinese-facing results without leaking transport or exception
details. It deliberately does not claim that Python can safely kill arbitrary
adapter work after a timer.

## Consequences

- Mock, Ollama, and future cloud models can share the same application capability
  boundary even if their request-planning formats differ.
- Realtime adapters remain small and independently testable.
- Future external actions still require an explicit confirmation policy; merely
  registering an adapter does not grant permission.
- Each network adapter must implement the supplied timeout correctly. A later
  subprocess boundary may add hard cancellation for tools that require it.
