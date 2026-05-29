# Review queue

Time- or data-gated items to revisit later. Not bugs and not active scope —
things that need real-world data or elapsed time before they can be decided.

| Added | Revisit after | Item |
| --- | --- | --- |
| 2026-05-29 | ~4 weeks of live data (≈ 2026-06-26) | Evaluate whether the **60 min default update interval** is right. Lower risks stale data relative to how often the hourly CAMS data actually moves; higher wastes the freshness Open-Meteo provides. Decide from the live Graz instance's recorder history (how much do values change hour-to-hour vs. the polling cost). |
| 2026-05-29 | At convenience (non-urgent) | **Rotate the polleninformation.at API key.** It appeared in a browser-chat transcript (a leak surface), so request a fresh key and swap it via the integration's options flow. Low-stakes key; not urgent. |
