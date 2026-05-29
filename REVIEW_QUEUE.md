# Review queue

Time- or data-gated items to revisit later. Not bugs and not active scope —
things that need real-world data or elapsed time before they can be decided.

| Added | Revisit after | Item |
| --- | --- | --- |
| 2026-05-29 | ~4 weeks of live data (≈ 2026-06-26) | Evaluate whether the **60 min default update interval** is right. Lower risks stale data relative to how often the hourly CAMS data actually moves; higher wastes the freshness Open-Meteo provides. Decide from the live Graz instance's recorder history (how much do values change hour-to-hour vs. the polling cost). |
| 2026-05-29 | At convenience (non-urgent) | **Rotate the polleninformation.at API key.** It appeared in a browser-chat transcript (a leak surface), so request a fresh key and swap it via the integration's options flow. Low-stakes key; not urgent. |
| 2026-05-29 | After 3b ships | **Open-Meteo 92-day backfill is re-fetched hourly** (for recent_percentile). Past data doesn't change, so this is wasteful payload. Consider fetching the backfill once/day and only the forecast hourly, or caching the historical daily peaks. |
| 2026-05-29 | After real dual-source data | **Divergence ">1 level apart" threshold** — confirm how often it fires once consensus/divergence ship; tune if too noisy/quiet. |
| 2026-05-29 | After real 3-source data | **3-source consensus `{1,1,2}` wart (interim, documented).** With ≥3 sources, take-the-higher lets a lone escalating outlier pull consensus up (e.g. {1,1,2}→high) while divergence stays **off** (spread is only 1), so a minority high reading presents as confident consensus — the opposite of what the consensus/divergence pair is for. Neither pure take-higher nor mode is right; the honest fix is a **divergence-semantics change** (divergence on when sources don't *unanimously* agree even within spread 1), which interacts with the 2-source case and wants a fresh-head redesign. Observe-then-tune; theoretical until a 3rd source is live (DWD doesn't cover Graz). |
| 2026-05-29 | Before 3b ships / soon | **recent_percentile reads 50% for an all-zero window.** Out-of-season allergens (mugwort/ragweed: 92 days all 0, today 0) give midrank percentile = 50%, which *looks* "moderate" but means "no signal." Observed live. Consider special-casing an all-zero (or today==window-max==0) window to 0% or a distinct "off-season" state. Flagged at the 3b checkpoint. |
| 2026-05-29 | Whenever convenient | Record verbatim UPI 4/5 `indexDescription` strings in ANALYTICS.md from Google's published category docs (no code change needed; 0–3 already captured, mapping doesn't depend on it). |
