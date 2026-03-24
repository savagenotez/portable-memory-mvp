# Portable Memory MVP - Founder One-Pager

Run ID: `run-20260324T214221Z-429eb2dd`

## What it is

Robustness-aware pruning preserves continuity while shrinking context, and it remained unbeaten across the current adversarial benchmark suite.

## Key Metrics

- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `23.82`
- Total pruned lines: `25`
- Unbeaten scenarios: `13` / `13`

## Why it matters

- Most memory systems either preserve signal but bloat context, or compress context but lose important meaning.
- This policy keeps the high-signal rescue behavior, then prunes only when robustness is preserved.
- The result is lower context cost without losing continuity quality on the tested scenarios.

## What we built

- A rescue-and-prune memory policy for session continuity.
- A benchmark suite with exact, soft, and adversarial evaluation.
- An interpretable policy that protects exact recall, soft recall, and anchor-token overlap.

## Why this is better

### robustness_aware_pruning_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `23.82`

### threshold_gated_adaptive_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `-53.95`

### hybrid_mode
- Retrieval hit rate: `0.8782`
- Soft hit rate: `0.8782`
- Context reduction percent: `-54.76`

### compression_mode
- Retrieval hit rate: `0.6282`
- Soft hit rate: `0.6282`
- Context reduction percent: `-30.22`

## Business value

### Cost savings
- reduces context size while preserving meaning
- can lower inference cost compared with bloated rescue modes
- can extend usable context windows

### Product value
- improves continuity across sessions
- makes memory behavior more interpretable
- supports enterprise-grade memory retention policies

### Research value
- demonstrates that rescue-plus-pruning outperforms static summarization
- shows robustness-aware pruning is a better objective than raw compression
- creates a benchmarkable framework for semantic continuity preservation

## Founder talking points
- We are not just summarizing context; we are preserving the minimum robust meaning needed for continuity.
- The system is benchmarked against multiple weaker policies and wins on the current suite.
- The policy is interpretable, measurable, and can be productized as a memory controller layer.
- This can support lower inference cost, longer usable sessions, and more trustworthy enterprise memory behavior.

## Proof points
- Recommended policy: `robustness_aware_pruning_mode`
- Unbeaten scenarios: `13 / 13`
- Loss counts by mode: `{}`

## Next steps
- Expand the adversarial suite and scenario coverage.
- Test the policy against live usage traces and token-cost accounting.
- Package the controller as a reusable module.
- Prepare a technical note and a business-facing pitch deck.
