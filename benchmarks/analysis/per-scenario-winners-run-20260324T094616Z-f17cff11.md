# Per-Scenario Winner Analysis

- Source run: `run-20260324T094616Z-f17cff11.json`
- Run ID: `run-20260324T094616Z-f17cff11`

## Win Counts

### best_overall
- `compression_mode`: 7
- `hybrid_mode`: 5
- `phrase_fragment_per_byte_mode`: 1

### best_above_threshold
- `hybrid_mode`: 4
- `compression_mode`: 3
- `phrase_fragment_per_byte_mode`: 1

### safest
- `compression_mode`: 7
- `hybrid_mode`: 5
- `phrase_fragment_per_byte_mode`: 1

### cheapest
- `compression_mode`: 13

## Project and constraints retrieval

- Scenario ID: `project_and_constraints`
- Best overall: `compression_mode`
- Best above threshold: `None`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `hybrid_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=hybrid_fallback | label=None
- `scenario_classifier_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=hybrid_fallback | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Durable update retrieval

- Scenario ID: `durable_update_retrieval`
- Best overall: `phrase_fragment_per_byte_mode`
- Best above threshold: `phrase_fragment_per_byte_mode`
- Safest: `phrase_fragment_per_byte_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.25 | reduction=27.91 | removed=1 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-14.78 | removed=4 | choice=fragment_escalation | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-14.78 | removed=4 | choice=fragment_escalation | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=10.47
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.75 | reduction_delta=42.69

## Project and constraints core retrieval

- Scenario ID: `project_constraints_core`
- Best overall: `compression_mode`
- Best above threshold: `None`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `hybrid_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=hybrid_fallback | label=None
- `scenario_classifier_mode` | hit=0.75 | reduction=-15.12 | removed=3 | choice=hybrid_fallback | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Durable update and current state retrieval

- Scenario ID: `durable_update_state`
- Best overall: `hybrid_mode`
- Best above threshold: `hybrid_mode`
- Safest: `hybrid_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.25 | reduction=27.91 | removed=1 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=phrase_saver_escalation | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=phrase_saver_escalation | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.75 | reduction_delta=53.16

## Workflow continuity across tools

- Scenario ID: `workflow_continuity_tools`
- Best overall: `hybrid_mode`
- Best above threshold: `hybrid_mode`
- Safest: `hybrid_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.5 | reduction=27.91 | removed=2 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=phrase_saver_escalation | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-25.25 | removed=4 | choice=phrase_saver_escalation | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.5 | reduction_delta=53.16

## Proof boundary and non-proven areas

- Scenario ID: `proof_and_scope_boundary`
- Best overall: `hybrid_mode`
- Best above threshold: `hybrid_mode`
- Safest: `hybrid_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.25 | reduction=14.12 | removed=1 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=phrase_saver_escalation | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=phrase_saver_escalation | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.75 | reduction_delta=53.16

## System identity summary retrieval

- Scenario ID: `memory_identity_summary`
- Best overall: `compression_mode`
- Best above threshold: `compression_mode`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=1.0 | reduction=-37.14 | removed=4 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-37.14 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-37.14 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-37.14 | removed=4 | choice=compression_seed | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-37.14 | removed=4 | choice=compression_seed | label=medium_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Low-recall: lightweight repo identity

- Scenario ID: `lightweight_repo_identity`
- Best overall: `compression_mode`
- Best above threshold: `None`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.5 | reduction=-119.19 | removed=1 | choice=None | label=None
- `hybrid_mode` | hit=0.5 | reduction=-119.19 | removed=1 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=0.5 | reduction=-119.19 | removed=1 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=0.5 | reduction=-119.19 | removed=1 | choice=hybrid_fallback | label=None
- `scenario_classifier_mode` | hit=0.5 | reduction=-119.19 | removed=1 | choice=compression_seed | label=low_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Low-recall: tooling note

- Scenario ID: `lightweight_tooling_note`
- Best overall: `compression_mode`
- Best above threshold: `compression_mode`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=1.0 | reduction=-211.86 | removed=2 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-211.86 | removed=2 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-211.86 | removed=2 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-211.86 | removed=2 | choice=compression_seed | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-211.86 | removed=2 | choice=compression_seed | label=low_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Low-recall: goal only

- Scenario ID: `lightweight_goal_only`
- Best overall: `compression_mode`
- Best above threshold: `compression_mode`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=1.0 | reduction=-119.19 | removed=1 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-119.19 | removed=1 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-119.19 | removed=1 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-119.19 | removed=1 | choice=compression_seed | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-119.19 | removed=1 | choice=compression_seed | label=low_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Mixed-recall: project plus next step

- Scenario ID: `mixed_project_plus_next_step`
- Best overall: `hybrid_mode`
- Best above threshold: `None`
- Safest: `hybrid_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.5 | reduction=27.91 | removed=2 | choice=None | label=None
- `hybrid_mode` | hit=0.75 | reduction=-25.25 | removed=3 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=0.75 | reduction=-25.25 | removed=3 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=0.75 | reduction=-25.25 | removed=3 | choice=hybrid_fallback | label=None
- `scenario_classifier_mode` | hit=0.75 | reduction=-25.25 | removed=3 | choice=hybrid_fallback | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.25 | reduction_delta=53.16

## Mixed-recall: constraints plus identity

- Scenario ID: `mixed_constraints_plus_identity`
- Best overall: `compression_mode`
- Best above threshold: `None`
- Safest: `compression_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.6667 | reduction=-15.12 | removed=2 | choice=None | label=None
- `hybrid_mode` | hit=0.6667 | reduction=-15.12 | removed=2 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=0.6667 | reduction=-15.12 | removed=2 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=0.6667 | reduction=-15.12 | removed=2 | choice=hybrid_fallback | label=None
- `scenario_classifier_mode` | hit=0.6667 | reduction=-15.12 | removed=2 | choice=hybrid_fallback | label=medium_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0

## Mixed-recall: proof and workflow

- Scenario ID: `mixed_proof_and_workflow`
- Best overall: `hybrid_mode`
- Best above threshold: `hybrid_mode`
- Safest: `hybrid_mode`
- Cheapest: `compression_mode`

### Key modes
- `compression_mode` | hit=0.75 | reduction=14.12 | removed=3 | choice=None | label=None
- `hybrid_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=None | label=None
- `phrase_saver_per_byte_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=None | label=None
- `threshold_gated_adaptive_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=phrase_saver_escalation | label=None
- `scenario_classifier_mode` | hit=1.0 | reduction=-39.04 | removed=4 | choice=phrase_saver_escalation | label=high_recall_need

### Comparisons
- `threshold_vs_hybrid` | hit_delta=0.0 | reduction_delta=0.0
- `classifier_vs_threshold` | hit_delta=0.0 | reduction_delta=0.0
- `compression_vs_threshold` | hit_delta=-0.25 | reduction_delta=53.16
