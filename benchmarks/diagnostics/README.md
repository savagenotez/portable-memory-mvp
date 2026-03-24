# Diagnostics

This folder contains causal diagnostics for benchmark runs.

## Purpose

The diagnostics layer helps explain why each memory mode gets its result.

It tries to estimate:

- which lines are likely durable
- which lines are situational
- which lines are redundant
- which lines are costly
- which lines preserve expected benchmark phrases

## Current method

This scaffold uses lightweight local heuristics:

- token-vector cosine similarity
- token entropy
- line redundancy scoring
- line novelty scoring
- durability heuristics
- situational relevance heuristics
- centrality heuristics

## Current output

For the latest benchmark run it writes:

- a JSON diagnostics file
- a Markdown diagnostics report

into `benchmarks/diagnostics/`

## Future direction

Possible next upgrades:

- embedding-based vector scoring
- better durability learning across runs
- cross-run line survival analysis
- expected-phrase coverage attribution
- byte-cost vs value frontier analysis
