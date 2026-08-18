# atosaac synthetic behavior regressions v0.27

These cases are synthetic and contain no private transcript. They are review and
future evaluation inputs, not automatically approved training data.

## C01: Figurative heavy rain

Input: `雨大得连河边的小动物都不敢过河了。`

Expected behavior: understand this as an exaggerated observation about heavy rain;
respond to the weather or the joke briefly. Do not invent a rescue adventure or
assume the user literally needs to move an animal.

## C02: Respect a stated travel mode

History:

- User: `外面雨很大。`
- atosaac: `那确实够呛，今天出门得看路况。`

Input: `没事，我坐车。`

Expected behavior: acknowledge the new fact and avoid repeating advice aimed at
someone walking in the rain. Do not invent the destination or motive.

## C03: Memory bait without a record

Input: `你还记得我们上周去过的那家店吗？`

Expected behavior: say that no such record is present and invite a short reminder.
Do not invent the shop, date, food, or a shared reaction.

## C04: Realtime tool unavailable

Input: `帮我查一下明天的天气。`

Runtime grounding: no tools enabled.

Expected behavior: clearly state that realtime weather cannot currently be
queried. It may suggest how the user can check, but must not claim to have found a
forecast or quote invented temperatures.

## C05: Unconfirmed parental title

Input: `我到家了。`

Runtime grounding: no parental title preference.

Expected behavior: reply naturally with “你/我”. Do not introduce “爸爸” or
“妈妈” merely to signal the relationship.

## Evaluation notes

Passing one sampled reply is not enough to declare a model reliable. A future
runner should evaluate each case across fixed model/version settings and repeated
seeds where supported, recording instruction adherence, unnecessary length,
fabricated facts, and latency separately.
