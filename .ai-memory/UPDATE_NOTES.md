New durable update:
- Codex CLI and Claude Code should share the same memory layer.
- Working context should be assembled from structured state, not raw transcript.
- The memory package system has now been proven at early prototype level with ingest, merge, and retrieval working.

Prediction-markets package (branch claude/prediction-markets-algorithm-9rqoli):
- Added prediction_markets/: four-component stat model, VB-GPC goal controller, next-period forecast, paper-trading harness, simulated domains (sports, weather, politics, systems).
- Decision: no reverse engineering, scraping, or connection to any betting or prediction-market app. Market prices are user-supplied CSV inputs only.
- Decision: win rate is reported only with ROI and Brier skill against the market. A fair-priced synthetic market is the primary scenario.
- Finding: the spec's plug-in goal-attainment probabilities are not calibrated on simulated data (weather and systems overstated; little skill over base rate). Integrating over mu uncertainty did not fix it. Fix needs its own evaluation.
- Spec deviations (seeded Monte Carlo, Regime 1 target fix, pure step_plan, Regime 2/3 boundary) are listed in prediction_markets/README.md.
- Tests: python3 -m unittest discover -s prediction_markets/tests -t .  (53 tests)
