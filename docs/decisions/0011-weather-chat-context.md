# Decision 0011: Trigger configured-city weather before reply generation

- Status: accepted
- Date: 2026-08-20

## Context

The weather adapter is useful only after conversation orchestration can decide
when to call it and can give the result to any reply provider. Calling weather on
every mention of rain would add unnecessary latency and external requests.
Depending on Ollama-native function calling would also move product behavior back
into one provider-specific protocol.

## Options considered

1. **Query weather on every turn.** Gives maximum availability but wastes network
   calls, increases first-text latency, and sends the configured city when weather
   is irrelevant.
2. **Ask a second LLM to plan every tool call.** More flexible language coverage,
   but adds inference latency and tokens before each possible lookup.
3. **Use a narrow local policy now, behind a replaceable context provider.** Query
   only when a turn contains both a weather topic and explicit lookup intent, then
   place the structured result in ephemeral tool context.

## Decision

Choose option 3. `--weather-city` explicitly enables the read-only capability for
one configured city. `HeuristicWeatherQueryPolicy` recognizes weather questions
and direct lookup requests without another model call. Statements such as “我喜欢
下雨天” or “今天雨好大” do not query merely because they mention rain. Past or
future-day questions are not routed to this current/same-day adapter.

`WeatherToolContextProvider` executes `weather.current` through `ToolGateway` and
renders success or failure as a dedicated `TOOL` message. Tool messages map to
system data for Ollama, exist only for the current provider request, and never
enter conversation history or automatic memory. Success includes source,
observation time, cache state, and bounded weather fields. Failure instructs the
model to disclose unavailability rather than guess.

Runtime grounding advertises the tool only when configured. Content-free metrics
record tool latency, failure code, and fresh/cache/stale state. The end-to-end
first-text metric still includes lookup time because that is the latency the user
experiences.

## Consequences

- Weather questions can use real data with one ordinary LLM generation and no
  tool-planning inference.
- Narrow rules have false negatives and do not yet support arbitrary locations or
  tomorrow/later forecasts in one message; the configured city remains the
  privacy-preserving default.
- A provider-native or learned planner can replace the local policy later without
  replacing the gateway, weather adapter, or conversation interface.
- Tool failure does not become durable history, but the assistant reply explaining
  that failure does, like any other completed reply.
