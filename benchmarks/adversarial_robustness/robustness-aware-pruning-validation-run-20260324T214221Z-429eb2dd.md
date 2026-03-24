# Robustness-Aware Pruning Validation

- Source run: `run-20260324T214221Z-429eb2dd.json`
- Run ID: `run-20260324T214221Z-429eb2dd`
- Target mode: `robustness_aware_pruning_mode`
- Scenario count: `13`
- Unbeaten scenarios: `13`
- Scenarios with any loss: `0`
- Loss counts by mode: `{}`

## Mode Summary

### compression_mode
- Avg exact hit rate: `0.6282`
- Avg soft hit rate: `0.6282`
- Avg adversarial variant hit rate: `0.6859`
- Avg context reduction percent: `-30.22`

### hybrid_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `-54.76`

### phrase_fragment_per_byte_mode
- Avg exact hit rate: `0.6859`
- Avg soft hit rate: `0.6859`
- Avg adversarial variant hit rate: `0.7436`
- Avg context reduction percent: `-33.5`

### phrase_saver_per_byte_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `-54.76`

### recall_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `-255.25`

### robustness_aware_pruning_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `23.82`

### scenario_classifier_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `-53.95`

### threshold_gated_adaptive_mode
- Avg exact hit rate: `0.8782`
- Avg soft hit rate: `0.8782`
- Avg adversarial variant hit rate: `0.9359`
- Avg context reduction percent: `-53.95`

### title_aware_fragment_bundle_mode
- Avg exact hit rate: `0.6859`
- Avg soft hit rate: `0.6859`
- Avg adversarial variant hit rate: `0.7436`
- Avg context reduction percent: `-33.68`

## Scenario Comparison

### Project and constraints retrieval
- Target summary: `{'exact_hit_rate': 0.75, 'soft_hit_rate': 0.75, 'adversarial_variant_hit_rate': 0.75, 'context_reduction_percent': 26.26, 'preview_bytes': 278}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Durable update retrieval
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.1, 'preview_bytes': 475}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Project and constraints core retrieval
- Target summary: `{'exact_hit_rate': 0.75, 'soft_hit_rate': 0.75, 'adversarial_variant_hit_rate': 0.75, 'context_reduction_percent': 26.26, 'preview_bytes': 278}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Durable update and current state retrieval
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.1, 'preview_bytes': 475}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Workflow continuity across tools
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.43, 'preview_bytes': 473}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Proof boundary and non-proven areas
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.1, 'preview_bytes': 475}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### System identity summary retrieval
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': -3.98, 'preview_bytes': 392}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Low-recall: lightweight repo identity
- Target summary: `{'exact_hit_rate': 0.5, 'soft_hit_rate': 0.5, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 22.73, 'preview_bytes': 153}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Low-recall: tooling note
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 29.94, 'preview_bytes': 124}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Low-recall: goal only
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.72, 'preview_bytes': 155}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Mixed-recall: project plus next step
- Target summary: `{'exact_hit_rate': 0.75, 'soft_hit_rate': 0.75, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.43, 'preview_bytes': 473}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Mixed-recall: constraints plus identity
- Target summary: `{'exact_hit_rate': 0.6667, 'soft_hit_rate': 0.6667, 'adversarial_variant_hit_rate': 0.6667, 'context_reduction_percent': 59.42, 'preview_bytes': 153}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`

### Mixed-recall: proof and workflow
- Target summary: `{'exact_hit_rate': 1.0, 'soft_hit_rate': 1.0, 'adversarial_variant_hit_rate': 1.0, 'context_reduction_percent': 21.1, 'preview_bytes': 475}`
- Wins against: `['hybrid_mode', 'phrase_saver_per_byte_mode', 'threshold_gated_adaptive_mode', 'scenario_classifier_mode', 'compression_mode']`
- Loses against: `[]`
