# Open-Meteo weather adapter live probe

- Date: 2026-08-20
- Input: synthetic configured city `上海`
- Provider: Open-Meteo public geocoding and forecast endpoints
- Secrets: none

## Observed lifecycle

The request passed through `ToolGateway` with only read-only permission enabled.
The adapter resolved the configured city, fetched one current/same-day forecast,
and returned a successful `ToolOutput` with:

- resolved location `上海，上海市，中国`;
- timezone `Asia/Shanghai`;
- observation-valid time `2026-08-20T10:30:00+08:00`;
- current condition, temperature, apparent temperature, humidity, precipitation,
  rain, and wind speed;
- today's high, low, and maximum precipitation probability;
- `from_cache=false` and `is_stale=false`.

The probe did not use a personal location, API key, conversation transcript, or
persistent cache. Weather values are intentionally not copied here because they
become stale quickly; the purpose of this check is transport, schema, provenance,
and timestamp validation.
