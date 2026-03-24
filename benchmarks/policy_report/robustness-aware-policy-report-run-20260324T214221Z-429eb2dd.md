# Robustness-Aware Policy Report

- Source benchmark run: `run-20260324T214221Z-429eb2dd.json`
- Source validation: `robustness-aware-pruning-validation-run-20260324T214221Z-429eb2dd.json`
- Run ID: `run-20260324T214221Z-429eb2dd`

## Executive Summary

- Recommended policy: `robustness_aware_pruning_mode`
- Reason: Best overall balance of retrieval preservation, soft robustness, compression, and adversarial dominance in the current benchmark suite.
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `23.82`
- Total pruned lines: `25`
- Unbeaten scenarios: `13` / `13`

## Comparative Metrics

### robustness_aware_pruning_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `23.82`
- Repeated explanation items removed: `39`
- Controller choices: `{'robust_pruned_phrase_saver': 13}`
- Total pruned lines: `25`

### threshold_gated_adaptive_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `-53.95`
- Repeated explanation items removed: `39`
- Controller choices: `{'hybrid_fallback': 5, 'fragment_escalation': 1, 'phrase_saver_escalation': 4, 'compression_seed': 3}`

### hybrid_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `-54.76`
- Repeated explanation items removed: `39`

### phrase_saver_per_byte_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `-54.76`
- Repeated explanation items removed: `39`

### compression_mode
- Retrieval hit rate: `0.6282`
- Soft hit rate: `0.6282`
- Context reduction percent: `-30.22`
- Repeated explanation items removed: `26`

## Policy Spec

- Name: `Robustness-Aware Pruning`
- Purpose: Preserve required semantic continuity while pruning context only when exact match, soft match, and overlap robustness remain intact.

### Policy Steps
- Start from phrase-saver-per-byte rescued context.
- Measure exact phrase preservation.
- Measure soft phrase preservation.
- Measure phrase/token overlap robustness.
- Attempt greedy line removal.
- Reject any removal that lowers exact hit rate.
- Reject any removal that lowers soft hit rate.
- Reject any removal that causes overlap robustness to fall below the protected threshold.
- Keep only removals that preserve robustness while saving bytes.

### Protected Properties
- exact recall
- soft recall
- anchor-token overlap
- adversarial robustness

### Failure Modes Prevented
- over-pruning of project identity phrases
- loss of variant-friendly token overlap
- dropping semantic cushion needed under paraphrase

## Business Value

### Cost Value
- reduces context size while preserving meaning
- can lower inference cost compared with bloated rescue modes
- can extend usable context windows

### Product Value
- improves continuity across sessions
- makes memory behavior more interpretable
- supports enterprise-grade memory retention policies

### Research Value
- demonstrates that rescue-plus-pruning outperforms static summarization
- shows robustness-aware pruning is a better objective than raw compression
- creates a benchmarkable framework for semantic continuity preservation

## Next Actions
- package this policy into a reusable controller module
- run broader scenario expansion with more adversarial paraphrases
- measure token-cost savings against live usage traces
- draft a public-facing technical note or whitepaper summary
