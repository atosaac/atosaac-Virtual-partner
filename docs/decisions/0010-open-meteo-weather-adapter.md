# Decision 0010: Start realtime data with a bounded Open-Meteo adapter

- Status: accepted
- Date: 2026-08-20

## Context

Weather is the first read-only realtime capability. It must not require GPS,
secrets, an unrestricted URL supplied by a model, or a second LLM request. Results
need source and observation time so a cached forecast is not presented as a fresh
physical observation.

Open-Meteo's official geocoding endpoint accepts a place name and returns
coordinates. Its forecast endpoint accepts coordinates and can return selected
current and daily variables, local timezone data, and the valid time of current
conditions:

- <https://open-meteo.com/en/docs/geocoding-api>
- <https://open-meteo.com/en/docs>

## Options considered

1. **Let the LLM browse arbitrary weather pages.** Flexible but slow, difficult to
   validate, and grants a much broader network boundary than weather requires.
2. **Require a paid keyed weather API immediately.** Potentially useful later, but
   adds secret management before the tool path itself is validated.
3. **Use fixed Open-Meteo endpoints behind the tool gateway.** No key is needed for
   the initial non-commercial experiment, inputs remain bounded, and the adapter
   is replaceable.

## Decision

Choose option 3. `OpenMeteoWeatherAdapter` accepts only a city name, URL-encodes it,
and calls fixed HTTPS geocoding and forecast endpoints. It requests only current
temperature, apparent temperature, humidity, precipitation, rain, WMO weather
code and wind, plus today's high, low, and maximum precipitation probability.
WMO codes are mapped locally to a short Chinese condition.

One timeout budget is shared across both HTTP calls. Responses are bounded to one
megabyte and validated before becoming `ToolOutput`. An in-memory cache avoids
repeat network calls for ten minutes and retains the resolved coordinates, so a
refresh normally needs only the forecast call. If refresh fails, an explicitly
marked stale entry may be used for at most six hours; older data is rejected.
Cache size is bounded and contains weather data only, not conversation text.

## Consequences

- Weather lookup adds no API key and no model inference call.
- The configured city will be sent to Open-Meteo only when a lookup is actually
  requested; it is not silently derived from GPS.
- In-memory cache disappears on restart, which is acceptable for the first
  reliability baseline and avoids another local persistence policy.
- Open-Meteo remains a replaceable provider. Commercial deployment must review its
  current licence, attribution, pricing, and usage limits.
