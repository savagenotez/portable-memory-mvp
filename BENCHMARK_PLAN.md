# BENCHMARK PLAN

## Purpose

The benchmark system is intended to measure whether the project creates meaningful continuity improvements across sessions and agent workflows.

## Core questions

1. Does it reduce how much context must be re-explained?
2. Does it reduce prompt/context length for continuation?
3. Does retrieval return the right current state?
4. Do merges succeed without silent loss?
5. Does the resulting workflow feel more continuous to a human evaluator?

## Planned benchmark metrics

### Technical metrics
- merge_success_rate
- conflicts_created
- conflicts_resolved
- retrieval_hit_rate
- retrieval_relevance_score
- context_bytes_without_memory
- context_bytes_with_memory
- context_reduction_percent
- repeated_explanation_items_removed
- package_count_used
- session_count_used

### Human evaluation fields
- continuity_rating_0_to_5
- reduced_reexplaining_yes_no
- retrieved_right_state_yes_no
- felt_like_same_project_yes_no
- evaluator_notes

## Planned result storage

### Files
- benchmarks/results/latest.json
- benchmarks/results/history.json
- benchmarks/results/run-<timestamp>.json

### Long-term data model
Possible future tables or structured stores:
- benchmark_runs
- benchmark_scenarios
- benchmark_metrics
- benchmark_human_scores

## Comparison modes

### Mode A
Without structured memory

### Mode B
With structured memory

The same scenario should be run in both modes wherever possible.

## Example benchmark scenarios

1. Continue a project after two earlier sessions
2. Add a durable update note and verify it is retrievable
3. Merge multiple session packages and retrieve current constraints
4. Compare transcript-only continuation vs structured memory continuation

## Initial success criteria

Reasonable early targets:
- merge succeeds in basic scenarios
- retrieval surfaces core project state
- measurable reduction in re-explaining
- measurable reduction in continuation context size
- human continuity rating trends upward with structured memory enabled

## Current state

Benchmark scaffolding exists.
Runner implementation is still pending.
