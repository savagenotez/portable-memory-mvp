# Adversarial Pruning Validation

- Source run: `run-20260324T131334Z-516d87ae.json`
- Run ID: `run-20260324T131334Z-516d87ae`
- Scenario count: `13`

## Summary by Mode

### compression_mode
- Avg exact hit rate: `0.6923`
- Avg soft hit rate: `0.6923`
- Avg adversarial variant hit rate: `0.75`
- Avg context reduction percent: `-30.22`

### hybrid_mode
- Avg exact hit rate: `0.9423`
- Avg soft hit rate: `0.9423`
- Avg adversarial variant hit rate: `1.0`
- Avg context reduction percent: `-54.76`

### phrase_fragment_per_byte_mode
- Avg exact hit rate: `0.75`
- Avg soft hit rate: `0.75`
- Avg adversarial variant hit rate: `0.8077`
- Avg context reduction percent: `-33.5`

### phrase_saver_per_byte_mode
- Avg exact hit rate: `0.9423`
- Avg soft hit rate: `0.9423`
- Avg adversarial variant hit rate: `1.0`
- Avg context reduction percent: `-54.76`

### phrase_saver_pruning_mode
- Avg exact hit rate: `0.9167`
- Avg soft hit rate: `0.9167`
- Avg adversarial variant hit rate: `0.9551`
- Avg context reduction percent: `25.78`

### recall_mode
- Avg exact hit rate: `0.9423`
- Avg soft hit rate: `0.9423`
- Avg adversarial variant hit rate: `1.0`
- Avg context reduction percent: `-255.25`

### scenario_classifier_mode
- Avg exact hit rate: `0.9423`
- Avg soft hit rate: `0.9423`
- Avg adversarial variant hit rate: `1.0`
- Avg context reduction percent: `-53.95`

### threshold_gated_adaptive_mode
- Avg exact hit rate: `0.9423`
- Avg soft hit rate: `0.9423`
- Avg adversarial variant hit rate: `1.0`
- Avg context reduction percent: `-53.95`

### title_aware_fragment_bundle_mode
- Avg exact hit rate: `0.75`
- Avg soft hit rate: `0.75`
- Avg adversarial variant hit rate: `0.8077`
- Avg context reduction percent: `-33.68`

## Scenario Winners

### Project and constraints retrieval
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=26.26
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12

### Durable update retrieval
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.1
- `phrase_fragment_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-14.78
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-14.78
- `scenario_classifier_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-14.78

### Project and constraints core retrieval
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=26.26
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12

### Durable update and current state retrieval
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.1
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25

### Workflow continuity across tools
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.43
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-25.25

### Proof boundary and non-proven areas
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.1
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04

### System identity summary retrieval
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-3.98
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-37.14
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-37.14
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-37.14

### Low-recall: lightweight repo identity
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=0.5 | exact=0.5 | reduction=22.73
- `compression_mode` | adv=1.0 | soft=0.5 | exact=0.5 | reduction=-119.19
- `hybrid_mode` | adv=1.0 | soft=0.5 | exact=0.5 | reduction=-119.19
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=0.5 | exact=0.5 | reduction=-119.19

### Low-recall: tooling note
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=29.94
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-211.86
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-211.86
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-211.86

### Low-recall: goal only
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.72
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-119.19
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-119.19
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-119.19

### Mixed-recall: project plus next step
- Winner by adversarial rate: `hybrid_mode`
- `hybrid_mode` | adv=1.0 | soft=0.75 | exact=0.75 | reduction=-25.25
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=0.75 | exact=0.75 | reduction=-25.25
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=0.75 | exact=0.75 | reduction=-25.25
- `scenario_classifier_mode` | adv=1.0 | soft=0.75 | exact=0.75 | reduction=-25.25

### Mixed-recall: constraints plus identity
- Winner by adversarial rate: `compression_mode`
- `compression_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12
- `phrase_fragment_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-15.12

### Mixed-recall: proof and workflow
- Winner by adversarial rate: `phrase_saver_pruning_mode`
- `phrase_saver_pruning_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=21.1
- `hybrid_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04
- `phrase_saver_per_byte_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04
- `threshold_gated_adaptive_mode` | adv=1.0 | soft=1.0 | exact=1.0 | reduction=-39.04
