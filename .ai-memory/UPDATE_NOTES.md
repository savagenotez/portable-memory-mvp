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
- Pull request: draft PR #1 open against main (https://github.com/savagenotez/portable-memory-mvp/pull/1). Branch pushed.
- Handoff for Codex or another agent: prediction_markets/HANDOFF.md. Calibration diagnostics: prediction_markets/diagnostics/.
- Calibration study (pre-registered: each domain's predicted rate within 2 SE of realized): no variant passes all five domains on seed blocks 912000000 or 913000000. Spec plug-in is not calibrated.
- Calibration variants added as flags, off by default: AR(1) dependence, mu uncertainty, known drift. Known drift fixes weather on block 913000000 but was found post-hoc and needs a new seed block.
- Attribution: outage shocks explain about half of the systems gap. Role-player overprediction is a shrinkage/prior-strength effect, not a wrong mean or spread (diagnostic, not verified).
- Never evaluate on a used seed block. Next steps are in prediction_markets/HANDOFF.md.
