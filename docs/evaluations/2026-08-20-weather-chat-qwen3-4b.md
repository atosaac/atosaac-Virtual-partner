# Weather chat end-to-end probe: qwen3:4b-instruct

- Date: 2026-08-20
- Provider: local Ollama
- Model: `qwen3:4b-instruct`
- Configured city: synthetic `上海`
- Persistent memory: disabled

## Results

The first question, `今天会下雨吗？`, triggered `weather.current`. Open-Meteo
returned current and same-day data, and the model used the condition, rain amount,
and precipitation probability in one natural reply.

```text
首字 6.34s | 总耗时 7.06s | 输入 1331 tokens | 输出 47 tokens
工具 weather.current 2.10s
```

The immediate follow-up, `那现在多少度？`, reused the same in-process weather
cache. The model used temperature and apparent temperature without enumerating the
JSON fields.

```text
首字 0.43s | 总耗时 0.92s | 输入 1392 tokens | 输出 30 tokens
工具 weather.current 0.00s 缓存
```

A non-query statement, `我喜欢下雨天`, did not show a tool metric, confirming
that a weather-topic mention without lookup intent did not access the provider.

This is one warm local sample, not a general latency benchmark. The non-query
reply still used a physically suggestive companionship phrase; that is an existing
model-behavior/evaluation issue rather than a tool-routing failure.
