# Decision 0004: Model silence as a controlled application event

- Status: proposed
- Date: 2026-08-18

## Context

A companion should sometimes begin a topic instead of making the user drive every
turn. It should also be able to speak after a long silence. A language model is not
running while the application waits for input, so a personality prompt alone
cannot notice elapsed time.

Unbounded autonomous generation would create the opposite problem: repeated
messages, unnecessary inference, interruptions at bad times, and eventual TTS or
notification spam. Silence can also be intentional and must not be diagnosed as
sadness, rejection, or a request for attention.

## Options considered

1. **Describe initiative only in the persona.** This influences the content of a
   reply but cannot wake a stopped model after elapsed wall-clock time.
2. **Run a continuous background agent.** This can invent goals and timing, but it
   consumes resources and creates difficult cancellation, privacy, and interruption
   behavior before the desktop workbench exists.
3. **Emit a bounded application event after an explicit idle timeout.** The
   application owns timing; the model receives a small event telling it to ask one
   natural question or make one short observation.

## Decision

Choose option 3 for the text prototype. Initiative is disabled by default and can
be enabled with `--idle-initiative-seconds`. After the configured silence:

1. the terminal emits one internal `EVENT` message;
2. the provider generates a normal streamed assistant reply;
3. the event and complete reply are committed together;
4. no second initiative is allowed until the user provides input.

The event explicitly says that it is not user-authored and forbids mentioning
timers, blaming silence, or inventing real-world experiences. Ollama receives the
internal event as a system message, while session history retains the distinct
event role for provenance. Failed, cancelled, or partial generations are not
committed.

An initial live follow-up test fabricated that the user had spilled a coffee cup
again. Runtime grounding therefore also forbids claims of real eating, seeing, or
hearsay and words such as “again” or “last time” unless supplied context supports
them. This constraint applies to ordinary and proactive replies alike.

The first initiative also used a generic “what have you been busy with” question.
The event now rejects broad interview prompts and asks for a concrete small choice,
preference, or viewpoint. A later curiosity queue is still needed for durable
self-originated questions; random prompts must not be presented as character
growth.

The macOS terminal adapter uses a timed wait on standard input rather than a
per-timeout background thread. This keeps cancellation and process shutdown
simple. A future desktop scheduler may use its own event loop behind the same
conversation method.

## Consequences

- The character can initiate a topic after silence without pretending the user
  spoke first.
- The next user reply includes the proactive question in context.
- Default-off behavior avoids surprising users and unnecessary model calls.
- The first prototype has no quiet hours, calendar awareness, notification
  permission, or activity detection outside this terminal.
- TTS can later consume the completed proactive text; it must not own initiative
  timing or conversation state.
