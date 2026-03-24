# Decision Boundary Mining

- Source analysis file: `per-scenario-winners-run-20260324T094616Z-f17cff11.json`
- Source run ID: `run-20260324T094616Z-f17cff11`
- Scenario count: `13`

## Feature Breakdown

- `low_recall`: 3
- `mixed_recall`: 3
- `project_identity`: 6
- `constraints`: 3
- `proof`: 2
- `workflow`: 3
- `next_step`: 1
- `goal`: 1

## Mined Rules

### low_recall_default
- Preferred mode: `compression_mode`
- Evidence count: `3`
- If all: `low_recall`
- Notes: Derived from scenarios marked low-recall.

### mixed_recall_default
- Preferred mode: `hybrid_mode`
- Evidence count: `2`
- If all: `mixed_recall`
- Notes: Derived from scenarios marked mixed-recall.

### proof_queries
- Preferred mode: `hybrid_mode`
- Evidence count: `2`
- If any: `proof`
- Notes: Proof/proven style queries often need stronger preservation.

### constraint_queries
- Preferred mode: `compression_mode`
- Evidence count: `3`
- If any: `constraints`
- Notes: Constraint-heavy queries often benefit from stronger semantic retention.

### workflow_queries
- Preferred mode: `hybrid_mode`
- Evidence count: `2`
- If any: `workflow`
- Notes: Workflow/tooling language may need structured preservation.

### goal_queries
- Preferred mode: `compression_mode`
- Evidence count: `1`
- If any: `goal`
- Notes: Goal-only questions may be more compressible.

### global_fallback
- Preferred mode: `compression_mode`
- Evidence count: `7`
- Notes: Fallback winner across all analyzed scenarios.
