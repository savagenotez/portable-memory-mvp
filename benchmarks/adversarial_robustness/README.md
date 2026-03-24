# Robustness-Aware Pruning Validation

This folder contains adversarial validation outputs focused specifically on robustness-aware pruning mode.

## Purpose

These reports test whether robustness-aware pruning:
- remains strong under variant wording
- fixes the known pruning failure cases
- stays competitive against hybrid, compression, and threshold-gated routing

## Why this matters

Plain pruning was strong but had adversarial weak spots.
This validation checks whether robustness-aware pruning preserves the compactness win while closing those weak spots.
